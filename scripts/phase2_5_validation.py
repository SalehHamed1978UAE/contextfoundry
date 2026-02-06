#!/usr/bin/env python3
"""
Phase 2.5: Automated Validation Pass

Runs comprehensive automated validation on slice extraction output BEFORE looking at test scores.
This is the CRITICAL gate that finds bugs the test didn't surface.

Validation Checks:
1. Type consistency - Any suspicious entity types?
2. Schema coverage - Which relationship types have zero instances?
3. Degree anomalies - Any entity with >10 edges?
4. Distribution analysis - Does relationship distribution look reasonable?
5. Cardinality violations - Any 1-to-1 relationships with multiple values?
6. Regression detection (Category 0 Gate) - Diff old KG vs new KG

Usage:
    python scripts/phase2_5_validation.py --vault-id <slice-vault-id>
    python scripts/phase2_5_validation.py --vault-id <slice-vault-id> --baseline-vault-id <old-vault-id>
    python scripts/phase2_5_validation.py --vault-id <slice-vault-id> --output report.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Color codes for terminal output
class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def log(msg: str, level: str = "INFO"):
    """Log message with color coding."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": Color.OKBLUE,
        "SUCCESS": Color.OKGREEN,
        "WARNING": Color.WARNING,
        "ERROR": Color.FAIL,
        "HEADER": Color.HEADER
    }
    color = colors.get(level, "")
    print(f"{color}[{timestamp}] {msg}{Color.ENDC}")
    sys.stdout.flush()


def get_db_engine():
    """Get database engine from environment."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    return create_engine(database_url)


# ============================================================================
# Validation Check 1: Type Consistency
# ============================================================================

def check_type_consistency(session, vault_id: str) -> Dict[str, Any]:
    """Check for suspicious entity types."""
    log("Running Type Consistency Check...", "HEADER")

    # Known organizations that should NEVER be PERSON
    known_orgs = ["boeing", "siemens", "nexus industries", "nel hydrogen",
                  "airbus", "lockheed", "raytheon", "northrop grumman",
                  "shell", "first solar", "honeywell"]

    issues = []

    # Check for major companies typed as PERSON
    query = text("""
        SELECT canonical_name, entity_type, degree
        FROM cf_entities
        WHERE tenant_id = :vault_id
          AND entity_type = 'PERSON'
          AND (
            LOWER(canonical_name) LIKE '%boeing%'
            OR LOWER(canonical_name) LIKE '%siemens%'
            OR LOWER(canonical_name) LIKE '%nexus industries%'
            OR LOWER(canonical_name) LIKE '%nel hydrogen%'
            OR LOWER(canonical_name) LIKE '%shell%'
            OR LOWER(canonical_name) LIKE '%honeywell%'
          )
    """)

    result = session.execute(query, {"vault_id": vault_id})
    for row in result:
        issues.append({
            "type": "COMPANY_AS_PERSON",
            "entity": row.canonical_name,
            "actual_type": row.entity_type,
            "expected_type": "ORGANIZATION",
            "degree": row.degree,
            "severity": "CRITICAL"
        })
        log(f"  ✗ CRITICAL: {row.canonical_name} typed as PERSON (should be ORGANIZATION, has {row.degree} edges)", "ERROR")

    # Check for suspiciously high-degree PERSON entities (potential mistyping)
    query = text("""
        SELECT canonical_name, entity_type, degree
        FROM cf_entities
        WHERE tenant_id = :vault_id
          AND entity_type = 'PERSON'
          AND degree > 10
        ORDER BY degree DESC
    """)

    result = session.execute(query, {"vault_id": vault_id})
    for row in result:
        issues.append({
            "type": "HIGH_DEGREE_PERSON",
            "entity": row.canonical_name,
            "entity_type": row.entity_type,
            "degree": row.degree,
            "severity": "WARNING"
        })
        log(f"  ⚠ WARNING: PERSON '{row.canonical_name}' has {row.degree} edges (suspiciously high)", "WARNING")

    if not issues:
        log("  ✓ No type consistency issues found", "SUCCESS")

    return {
        "check": "Type Consistency",
        "status": "FAIL" if any(i["severity"] == "CRITICAL" for i in issues) else "PASS",
        "issues_found": len(issues),
        "critical_issues": len([i for i in issues if i["severity"] == "CRITICAL"]),
        "issues": issues
    }


# ============================================================================
# Validation Check 2: Schema Coverage
# ============================================================================

def check_schema_coverage(session, vault_id: str) -> Dict[str, Any]:
    """Check which ontology relationship types have zero instances."""
    log("Running Schema Coverage Check...", "HEADER")

    # Load ontology from domain_schema.yaml
    schema_path = Path(__file__).parent.parent / "config" / "domain_schema.yaml"

    import yaml
    with open(schema_path) as f:
        schema = yaml.safe_load(f)

    ontology_types = {rt["name"] for rt in schema.get("relationship_types", [])}

    # Get actual relationship types in KG
    query = text("""
        SELECT DISTINCT relation_type
        FROM cf_relationships
        WHERE tenant_id = :vault_id
    """)

    result = session.execute(query, {"vault_id": vault_id})
    actual_types = {row.relation_type for row in result}

    missing_types = ontology_types - actual_types
    extra_types = actual_types - ontology_types

    # Critical: Supply-chain types should appear
    critical_types = {"SUPPLIES", "CUSTOMER_OF", "PROCURES_FROM", "VENDOR_OF"}
    missing_critical = critical_types & missing_types

    log(f"  Ontology defines: {len(ontology_types)} relationship types", "INFO")
    log(f"  KG contains: {len(actual_types)} relationship types", "INFO")
    log(f"  Missing from KG: {len(missing_types)} types", "WARNING" if missing_types else "SUCCESS")
    log(f"  Not in ontology: {len(extra_types)} types", "INFO")

    if missing_critical:
        for rel_type in missing_critical:
            log(f"  ✗ CRITICAL: Supply-chain type '{rel_type}' has ZERO instances", "ERROR")

    if missing_types:
        log(f"  Missing types: {', '.join(sorted(missing_types))}", "WARNING")

    return {
        "check": "Schema Coverage",
        "status": "FAIL" if missing_critical else ("WARN" if missing_types else "PASS"),
        "ontology_types": len(ontology_types),
        "actual_types": len(actual_types),
        "missing_types": sorted(missing_types),
        "missing_critical": sorted(missing_critical),
        "extra_types": sorted(extra_types)
    }


# ============================================================================
# Validation Check 3: Degree Anomalies
# ============================================================================

def check_degree_anomalies(session, vault_id: str) -> Dict[str, Any]:
    """Check for entities with suspiciously high degree (>10 edges)."""
    log("Running Degree Anomaly Check...", "HEADER")

    query = text("""
        SELECT canonical_name, entity_type, degree
        FROM cf_entities
        WHERE tenant_id = :vault_id
          AND degree > 10
        ORDER BY degree DESC
        LIMIT 20
    """)

    result = session.execute(query, {"vault_id": vault_id})
    anomalies = []

    for row in result:
        severity = "CRITICAL" if row.degree > 15 else "WARNING"
        anomalies.append({
            "entity": row.canonical_name,
            "entity_type": row.entity_type,
            "degree": row.degree,
            "severity": severity
        })

        if severity == "CRITICAL":
            log(f"  ✗ CRITICAL: {row.canonical_name} ({row.entity_type}) has {row.degree} edges (>15 threshold)", "ERROR")
        else:
            log(f"  ⚠ WARNING: {row.canonical_name} ({row.entity_type}) has {row.degree} edges", "WARNING")

    if not anomalies:
        log("  ✓ No degree anomalies found (all entities <10 edges)", "SUCCESS")

    return {
        "check": "Degree Anomalies",
        "status": "FAIL" if any(a["severity"] == "CRITICAL" for a in anomalies) else ("WARN" if anomalies else "PASS"),
        "anomalies_found": len(anomalies),
        "critical_anomalies": len([a for a in anomalies if a["severity"] == "CRITICAL"]),
        "anomalies": anomalies
    }


# ============================================================================
# Validation Check 4: Distribution Analysis
# ============================================================================

def check_distribution(session, vault_id: str) -> Dict[str, Any]:
    """Check if relationship type distribution looks reasonable."""
    log("Running Distribution Analysis...", "HEADER")

    query = text("""
        SELECT
            relation_type,
            COUNT(*) as count,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
        FROM cf_relationships
        WHERE tenant_id = :vault_id
        GROUP BY relation_type
        ORDER BY count DESC
    """)

    result = session.execute(query, {"vault_id": vault_id})
    distribution = []
    issues = []

    for row in result:
        distribution.append({
            "type": row.relation_type,
            "count": row.count,
            "percentage": float(row.percentage)
        })

        # Flag if WORKS_AT dominates (>20%)
        if row.relation_type == "WORKS_AT" and row.percentage > 20.0:
            issues.append({
                "type": "WORKS_AT_DOMINANCE",
                "percentage": float(row.percentage),
                "severity": "WARNING"
            })
            log(f"  ⚠ WARNING: WORKS_AT represents {row.percentage}% of relationships (should be <20%)", "WARNING")

        log(f"  {row.relation_type}: {row.count} ({row.percentage}%)", "INFO")

    # Check for supply-chain presence
    supply_chain_types = {"SUPPLIES", "CUSTOMER_OF", "PROCURES_FROM", "VENDOR_OF"}
    supply_chain_present = any(d["type"] in supply_chain_types for d in distribution)

    if not supply_chain_present:
        issues.append({
            "type": "NO_SUPPLY_CHAIN",
            "severity": "CRITICAL"
        })
        log("  ✗ CRITICAL: No supply-chain relationships found", "ERROR")
    else:
        log("  ✓ Supply-chain relationships present", "SUCCESS")

    return {
        "check": "Distribution Analysis",
        "status": "FAIL" if any(i["severity"] == "CRITICAL" for i in issues) else ("WARN" if issues else "PASS"),
        "distribution": distribution,
        "issues": issues
    }


# ============================================================================
# Validation Check 5: Cardinality Violations
# ============================================================================

def check_cardinality_violations(session, vault_id: str) -> Dict[str, Any]:
    """Check for 1-to-1 relationships with multiple values."""
    log("Running Cardinality Violation Check...", "HEADER")

    # Define 1-to-1 relationships from ontology
    one_to_one_types = ["REPORTS_TO", "OCCURRED_ON"]  # Add more as needed

    violations = []

    for rel_type in one_to_one_types:
        query = text("""
            SELECT
                source_entity_id,
                e.canonical_name,
                COUNT(*) as target_count
            FROM cf_relationships r
            JOIN cf_entities e ON e.id = r.source_entity_id
            WHERE r.tenant_id = :vault_id
              AND r.relation_type = :rel_type
            GROUP BY source_entity_id, e.canonical_name
            HAVING COUNT(*) > 1
        """)

        result = session.execute(query, {"vault_id": vault_id, "rel_type": rel_type})

        for row in result:
            violations.append({
                "relation_type": rel_type,
                "entity": row.canonical_name,
                "expected_cardinality": "1-to-1",
                "actual_count": row.target_count,
                "severity": "WARNING"
            })
            log(f"  ⚠ WARNING: {row.canonical_name} has {row.target_count} {rel_type} relationships (should be 1)", "WARNING")

    if not violations:
        log("  ✓ No cardinality violations found", "SUCCESS")

    return {
        "check": "Cardinality Violations",
        "status": "WARN" if violations else "PASS",
        "violations_found": len(violations),
        "violations": violations
    }


# ============================================================================
# Validation Check 6: Regression Detection (Category 0 Gate)
# ============================================================================

def check_regressions(session, vault_id: str, baseline_vault_id: Optional[str] = None) -> Dict[str, Any]:
    """Diff old KG vs new KG to detect regressions."""
    log("Running Regression Detection (Category 0 Gate)...", "HEADER")

    if not baseline_vault_id:
        log("  ⚠ No baseline vault provided - skipping regression check", "WARNING")
        return {
            "check": "Regression Detection",
            "status": "SKIPPED",
            "message": "No baseline vault provided"
        }

    # Compare relationship type counts
    query = text("""
        WITH new_dist AS (
            SELECT relation_type, COUNT(*) as count
            FROM cf_relationships
            WHERE tenant_id = :new_vault
            GROUP BY relation_type
        ),
        old_dist AS (
            SELECT relation_type, COUNT(*) as count
            FROM cf_relationships
            WHERE tenant_id = :old_vault
            GROUP BY relation_type
        )
        SELECT
            COALESCE(n.relation_type, o.relation_type) as relation_type,
            COALESCE(o.count, 0) as old_count,
            COALESCE(n.count, 0) as new_count,
            COALESCE(n.count, 0) - COALESCE(o.count, 0) as delta
        FROM new_dist n
        FULL OUTER JOIN old_dist o ON n.relation_type = o.relation_type
        ORDER BY ABS(COALESCE(n.count, 0) - COALESCE(o.count, 0)) DESC
    """)

    result = session.execute(query, {"new_vault": vault_id, "old_vault": baseline_vault_id})

    improvements = []
    regressions = []

    for row in result:
        change = {
            "type": row.relation_type,
            "old_count": row.old_count,
            "new_count": row.new_count,
            "delta": row.delta
        }

        if row.delta > 0:
            improvements.append(change)
            log(f"  ✓ IMPROVEMENT: {row.relation_type} +{row.delta} ({row.old_count} → {row.new_count})", "SUCCESS")
        elif row.delta < 0:
            regressions.append(change)
            log(f"  ✗ REGRESSION: {row.relation_type} {row.delta} ({row.old_count} → {row.new_count})", "ERROR")

    # Check for disappeared relationship types
    disappeared_types = [r for r in regressions if r["new_count"] == 0]
    if disappeared_types:
        log(f"  ✗ CRITICAL: {len(disappeared_types)} relationship types completely disappeared", "ERROR")

    return {
        "check": "Regression Detection",
        "status": "FAIL" if disappeared_types else ("WARN" if regressions else "PASS"),
        "improvements": improvements,
        "regressions": regressions,
        "disappeared_types": disappeared_types
    }


# ============================================================================
# Main Validation Runner
# ============================================================================

def run_validation(vault_id: str, baseline_vault_id: Optional[str] = None) -> Dict[str, Any]:
    """Run all validation checks and generate comprehensive report."""

    log("="*70, "HEADER")
    log("PHASE 2.5: Automated Validation Pass", "HEADER")
    log("="*70, "HEADER")
    log("", "INFO")
    log(f"Slice Vault ID: {vault_id}", "INFO")
    if baseline_vault_id:
        log(f"Baseline Vault ID: {baseline_vault_id}", "INFO")
    log("", "INFO")

    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    results = {
        "timestamp": datetime.now().isoformat(),
        "vault_id": vault_id,
        "baseline_vault_id": baseline_vault_id,
        "checks": []
    }

    try:
        # Run all validation checks
        checks = [
            check_type_consistency(session, vault_id),
            check_schema_coverage(session, vault_id),
            check_degree_anomalies(session, vault_id),
            check_distribution(session, vault_id),
            check_cardinality_violations(session, vault_id),
            check_regressions(session, vault_id, baseline_vault_id)
        ]

        results["checks"] = checks

        # Overall decision
        critical_failures = [c for c in checks if c["status"] == "FAIL"]
        warnings = [c for c in checks if c["status"] == "WARN"]

        log("", "INFO")
        log("="*70, "HEADER")
        log("VALIDATION SUMMARY", "HEADER")
        log("="*70, "HEADER")

        for check in checks:
            status = check["status"]
            name = check["check"]

            if status == "PASS":
                log(f"  ✓ {name}: PASS", "SUCCESS")
            elif status == "WARN":
                log(f"  ⚠ {name}: WARNING", "WARNING")
            elif status == "FAIL":
                log(f"  ✗ {name}: FAIL", "ERROR")
            else:
                log(f"  ⊘ {name}: SKIPPED", "INFO")

        log("", "INFO")
        log("-"*70, "HEADER")

        if critical_failures:
            results["decision"] = "FAIL"
            log(f"DECISION: ✗ FAIL ({len(critical_failures)} critical failures)", "ERROR")
            log("", "INFO")
            log("DO NOT PROCEED to Phase 3 (full re-extraction)", "ERROR")
            log("Iterate on prompt improvements and re-run Phase 2", "ERROR")
        elif warnings:
            results["decision"] = "WARN"
            log(f"DECISION: ⚠ PASS WITH WARNINGS ({len(warnings)} warnings)", "WARNING")
            log("", "INFO")
            log("Review warnings before proceeding to Phase 3", "WARNING")
            log("Consider iterating if warnings indicate serious issues", "WARNING")
        else:
            results["decision"] = "PASS"
            log("DECISION: ✓ PASS (all checks passed)", "SUCCESS")
            log("", "INFO")
            log("Proceed to Phase 3 (full vault re-extraction)", "SUCCESS")

        log("="*70, "HEADER")

    finally:
        session.close()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2.5: Automated validation of slice extraction"
    )
    parser.add_argument(
        "--vault-id",
        required=True,
        help="Slice vault ID to validate"
    )
    parser.add_argument(
        "--baseline-vault-id",
        help="Baseline vault ID for regression detection (optional)"
    )
    parser.add_argument(
        "--output",
        help="Output file for validation report (JSON)"
    )

    args = parser.parse_args()

    results = run_validation(args.vault_id, args.baseline_vault_id)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        log("", "INFO")
        log(f"Validation report saved to: {args.output}", "SUCCESS")

    # Exit with appropriate code
    if results["decision"] == "FAIL":
        sys.exit(1)
    elif results["decision"] == "WARN":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
