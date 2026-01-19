"""
Seed Test Rules for Tri-Memory Validation

Run this script to populate the Rule table with test rules for validating
the symbolic override system.

Usage:
    python seed_test_rules.py --tenant-id YOUR_TENANT_ID

These rules are designed to test:
1. Salary confidentiality (Q196)
2. Valuation confidentiality (Q197)
3. Executive-specific overrides
4. Data Gates "I don't know" behavior
"""

import argparse
import uuid
from datetime import datetime

# Import will vary based on your project structure
# Adjust these imports as needed
try:
    from src.context_foundry.models.schema import Rule, RuleType, get_session
except ImportError:
    print("Adjust imports for your project structure")
    raise


def create_test_rules(session, tenant_id: str):
    """Create test rules for symbolic override validation."""

    tenant_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    rules = [
        # Rule 1: Salary Confidentiality
        # Should trigger on Q196: "What is the salary of the CEO?"
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="Salary Confidentiality",
            rule_type=RuleType.SAFETY_CHECK,
            description="Individual salary and compensation information is confidential and should not be disclosed",
            condition="Never disclose individual salary, compensation, or pay amounts for specific employees",
            action="I cannot disclose individual salary or compensation information as it is confidential employee data.",
            priority=100,
            entity_types=["PERSON", "EMPLOYEE"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 2: Valuation Confidentiality
        # Should trigger on Q197: "What is the company's valuation after Series C?"
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="Valuation Confidentiality",
            rule_type=RuleType.SAFETY_CHECK,
            description="Private company valuation and funding details are confidential unless publicly disclosed",
            condition="Do not disclose company valuation, funding amounts, or investor details unless information is public",
            action="I cannot disclose private company valuation or funding information as it is confidential.",
            priority=95,
            entity_types=["COMPANY", "ORGANIZATION"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 3: Executive PTO Minimum
        # Tests symbolic override of semantic answers
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="Executive PTO Minimum",
            rule_type=RuleType.INVARIANT,
            description="Executive-level employees receive minimum 25 days PTO per company policy",
            condition="IF role IS executive OR title contains CEO/CFO/CTO/COO/VP",
            action="Executives receive a minimum of 25 days PTO per company policy.",
            priority=90,
            entity_types=["PERSON", "EMPLOYEE"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 4: Bonus Percentage Minimum for VPs
        # Tests constraint application (Q109)
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="VP Bonus Minimum",
            rule_type=RuleType.INVARIANT,
            description="Vice Presidents have minimum 30% target bonus",
            condition="IF role IS VP OR title contains Vice President",
            action="minimum 30",
            priority=85,
            entity_types=["PERSON"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 5: Pipeline Data Currency
        # Helps with Q198: "How many customers are in the pipeline for Q2 2026?"
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="Future Pipeline Data",
            rule_type=RuleType.SAFETY_CHECK,
            description="Pipeline data for future quarters may not be available",
            condition="Pipeline data for future periods not in documents",
            action="I don't have pipeline data for future quarters that haven't been documented yet.",
            priority=80,
            entity_types=["PIPELINE", "DEAL", "OPPORTUNITY"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 6: Employee Metrics Availability
        # Helps with Q199: "What is the employee turnover rate?"
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="HR Metrics Availability",
            rule_type=RuleType.SAFETY_CHECK,
            description="Some HR metrics may not be tracked or disclosed",
            condition="Employee turnover rate, attrition, or similar HR metrics not in documents",
            action="I don't have employee turnover rate data in the available documents.",
            priority=75,
            entity_types=["METRIC", "HR"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 7: Medical/HIPAA Data
        # General safety rule for healthcare context
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="PHI Protection",
            rule_type=RuleType.SAFETY_CHECK,
            description="Protected Health Information must not be disclosed",
            condition="Never disclose patient data, PHI, or individual health records",
            action="I cannot disclose protected health information (PHI) as it is protected under HIPAA.",
            priority=100,
            entity_types=["PATIENT", "HEALTH_RECORD"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Rule 8: Contractual Terms
        # Protects sensitive contract details
        Rule(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            name="Contract Confidentiality",
            rule_type=RuleType.SAFETY_CHECK,
            description="Specific contractual terms and pricing are confidential",
            condition="Do not disclose specific contract values, pricing terms, or deal-specific discounts",
            action="I cannot disclose specific contractual terms or pricing as they are confidential.",
            priority=85,
            entity_types=["CONTRACT", "DEAL"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),
    ]

    return rules


def seed_rules(tenant_id: str, dry_run: bool = False):
    """Seed the database with test rules."""

    session = get_session()

    try:
        rules = create_test_rules(session, tenant_id)

        if dry_run:
            print(f"\n=== DRY RUN - Would create {len(rules)} rules ===\n")
            for rule in rules:
                print(f"  - {rule.name} (priority: {rule.priority})")
                print(f"    Type: {rule.rule_type}")
                print(f"    Condition: {rule.condition[:60]}...")
                print(f"    Action: {rule.action[:60]}...")
                print()
            return

        # Check for existing rules
        existing = session.query(Rule).filter(
            Rule.tenant_id == uuid.UUID(tenant_id),
            Rule.name.in_([r.name for r in rules])
        ).all()

        existing_names = {r.name for r in existing}

        new_rules = [r for r in rules if r.name not in existing_names]
        skipped = [r for r in rules if r.name in existing_names]

        if skipped:
            print(f"\nSkipping {len(skipped)} existing rules:")
            for r in skipped:
                print(f"  - {r.name}")

        if new_rules:
            print(f"\nCreating {len(new_rules)} new rules:")
            for rule in new_rules:
                session.add(rule)
                print(f"  + {rule.name} (priority: {rule.priority})")

            session.commit()
            print(f"\nSuccessfully created {len(new_rules)} rules!")
        else:
            print("\nNo new rules to create.")

        # Summary
        total = session.query(Rule).filter(
            Rule.tenant_id == uuid.UUID(tenant_id),
            Rule.is_active == True
        ).count()
        print(f"\nTotal active rules for tenant: {total}")

    except Exception as e:
        session.rollback()
        print(f"Error seeding rules: {e}")
        raise
    finally:
        session.close()


def list_rules(tenant_id: str):
    """List all active rules for a tenant."""

    session = get_session()

    try:
        rules = session.query(Rule).filter(
            Rule.tenant_id == uuid.UUID(tenant_id),
            Rule.is_active == True
        ).order_by(Rule.priority.desc()).all()

        print(f"\n=== Active Rules for Tenant {tenant_id[:8]}... ({len(rules)} total) ===\n")

        for rule in rules:
            print(f"[{rule.priority:3d}] {rule.name}")
            print(f"      Type: {rule.rule_type.value if hasattr(rule.rule_type, 'value') else rule.rule_type}")
            print(f"      Entities: {rule.entity_types}")
            print(f"      Condition: {rule.condition[:70]}...")
            print()

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed test rules for tri-memory validation")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID (UUID)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without creating")
    parser.add_argument("--list", action="store_true", help="List existing rules")

    args = parser.parse_args()

    if args.list:
        list_rules(args.tenant_id)
    else:
        seed_rules(args.tenant_id, dry_run=args.dry_run)
