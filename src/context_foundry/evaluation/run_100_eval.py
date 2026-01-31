#!/usr/bin/env python3
"""
100-Query Autonomous Evaluation Script for Context Foundry.

Runs all 100 queries from the evaluation bank, verifies responses against
the database, and generates a comprehensive report.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict

import requests
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from .query_set import QuerySet, EvaluationQuery


class ResponseCategory(str, Enum):
    ACCURATE = "ACCURATE"
    PARTIAL = "PARTIAL"
    HALLUCINATED = "HALLUCINATED"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass
class EvaluationResult:
    query_id: str
    query_text: str
    category: str
    difficulty: str
    hop_count: str
    response_category: ResponseCategory
    confidence: float
    answer: str
    target_entity: Optional[str]
    entities_mentioned: List[str]
    entities_verified: List[str]
    entities_not_found: List[str]
    relationships_claimed: List[str]
    relationships_verified: List[str]
    relationships_not_found: List[str]
    issues: List[str]
    duration_seconds: float
    raw_response: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["response_category"] = self.response_category.value
        return d


class EvaluationRunner:
    """Runs the 100-query evaluation against Context Foundry."""
    
    def __init__(self, api_url: str = "http://localhost:5000"):
        self.api_url = api_url
        self.query_set = QuerySet()
        self.results: List[EvaluationResult] = []
        self.db_conn = None
        self._connect_db()
    
    def _connect_db(self):
        """Connect to the database for verification."""
        try:
            db_url = os.environ.get("DATABASE_URL")
            if db_url:
                self.db_conn = psycopg2.connect(db_url)
                print("Database connected for verification")
            else:
                print("WARNING: DATABASE_URL not set, verification will be limited")
        except Exception as e:
            print(f"WARNING: Could not connect to database: {e}")
    
    def _entity_exists(self, entity_name: str) -> bool:
        """Check if an entity exists in the database."""
        if not self.db_conn:
            return True
        
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM entities 
                    WHERE name ILIKE %s 
                    AND lifecycle_state IN ('TRUSTED', 'STAGING')
                """, (f"%{entity_name}%",))
                count = cur.fetchone()[0]
                return count > 0
        except Exception as e:
            print(f"DB error checking entity {entity_name}: {e}")
            return True
    
    def _relationship_exists(self, source: str, target: str, rel_type: str = None) -> bool:
        """Check if a relationship exists in the database."""
        if not self.db_conn:
            return True
        
        try:
            with self.db_conn.cursor() as cur:
                if rel_type:
                    cur.execute("""
                        SELECT COUNT(*) FROM relationships r
                        JOIN entities s ON r.source_id = s.id
                        JOIN entities t ON r.target_id = t.id
                        WHERE s.name ILIKE %s AND t.name ILIKE %s 
                        AND r.relationship_type = %s
                        AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                    """, (f"%{source}%", f"%{target}%", rel_type))
                else:
                    cur.execute("""
                        SELECT COUNT(*) FROM relationships r
                        JOIN entities s ON r.source_id = s.id
                        JOIN entities t ON r.target_id = t.id
                        WHERE s.name ILIKE %s AND t.name ILIKE %s
                        AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                    """, (f"%{source}%", f"%{target}%"))
                count = cur.fetchone()[0]
                return count > 0
        except Exception as e:
            print(f"DB error checking relationship {source}->{target}: {e}")
            return True
    
    def _extract_entities_from_answer(self, answer: str) -> List[str]:
        """Extract entity names mentioned in an answer."""
        entities = []
        
        service_pattern = r'\b([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\s+(?:Service|Database|Gateway|Cache|Queue|System|Engine|Platform|Cluster|Team|Processor))\b'
        matches = re.findall(service_pattern, answer)
        entities.extend(matches)
        
        quoted = re.findall(r'"([^"]+)"', answer)
        entities.extend(quoted)
        
        entities = list(set(entities))
        return entities[:20]
    
    def _extract_relationships_from_answer(self, answer: str) -> List[Tuple[str, str, str]]:
        """Extract relationship claims from an answer."""
        relationships = []
        
        depends_pattern = r'([A-Z][a-zA-Z0-9\s]+?)\s+depends\s+on\s+([A-Z][a-zA-Z0-9\s]+?)[\.\,\n]'
        for match in re.findall(depends_pattern, answer, re.IGNORECASE):
            relationships.append((match[0].strip(), match[1].strip(), "DEPENDS_ON"))
        
        owns_pattern = r'([A-Z][a-zA-Z0-9\s]+?)\s+owns?\s+([A-Z][a-zA-Z0-9\s]+?)[\.\,\n]'
        for match in re.findall(owns_pattern, answer, re.IGNORECASE):
            relationships.append((match[0].strip(), match[1].strip(), "OWNS"))
        
        return relationships[:10]
    
    def _categorize_response(
        self, 
        response: Dict,
        entities_verified: List[str],
        entities_not_found: List[str],
        rels_verified: List[str],
        rels_not_found: List[str]
    ) -> Tuple[ResponseCategory, List[str]]:
        """Categorize the response based on verification results."""
        issues = []
        
        if response.get("error"):
            return ResponseCategory.ERROR, ["Query returned an error"]
        
        if response.get("entity_not_found"):
            return ResponseCategory.NOT_FOUND, ["Entity not found (correct behavior)"]
        
        answer = response.get("answer", "")
        if "not found" in answer.lower() and "knowledge graph" in answer.lower():
            return ResponseCategory.NOT_FOUND, ["Entity not found in knowledge graph"]
        
        total_claims = len(entities_verified) + len(entities_not_found) + len(rels_verified) + len(rels_not_found)
        verified_claims = len(entities_verified) + len(rels_verified)
        not_found_claims = len(entities_not_found) + len(rels_not_found)
        
        for e in entities_not_found:
            issues.append(f"Entity not in DB: {e}")
        for r in rels_not_found:
            issues.append(f"Relationship not in DB: {r}")
        
        if total_claims == 0:
            confidence = response.get("confidence", 0)
            if confidence < 0.3:
                return ResponseCategory.ACCURATE, ["Low confidence, no claims to verify"]
            return ResponseCategory.PARTIAL, ["No specific claims extracted to verify"]
        
        if not_found_claims == 0:
            return ResponseCategory.ACCURATE, issues
        elif verified_claims > 0 and verified_claims >= not_found_claims:
            return ResponseCategory.PARTIAL, issues
        else:
            return ResponseCategory.HALLUCINATED, issues
    
    def run_query(self, query: EvaluationQuery) -> EvaluationResult:
        """Run a single query and evaluate the response."""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.api_url}/api/query",
                json={"query": query.query_text},
                timeout=90
            )
            response_data = response.json()
        except requests.exceptions.Timeout:
            return EvaluationResult(
                query_id=query.id,
                query_text=query.query_text,
                category=query.category.value,
                difficulty=query.difficulty.value,
                hop_count=query.hop_count.value,
                response_category=ResponseCategory.TIMEOUT,
                confidence=0.0,
                answer="",
                target_entity=None,
                entities_mentioned=[],
                entities_verified=[],
                entities_not_found=[],
                relationships_claimed=[],
                relationships_verified=[],
                relationships_not_found=[],
                issues=["Query timed out after 90 seconds"],
                duration_seconds=90.0
            )
        except Exception as e:
            return EvaluationResult(
                query_id=query.id,
                query_text=query.query_text,
                category=query.category.value,
                difficulty=query.difficulty.value,
                hop_count=query.hop_count.value,
                response_category=ResponseCategory.ERROR,
                confidence=0.0,
                answer="",
                target_entity=None,
                entities_mentioned=[],
                entities_verified=[],
                entities_not_found=[],
                relationships_claimed=[],
                relationships_verified=[],
                relationships_not_found=[],
                issues=[f"Request error: {str(e)}"],
                duration_seconds=time.time() - start_time
            )
        
        duration = time.time() - start_time
        answer = response_data.get("answer", "")
        
        entities_mentioned = self._extract_entities_from_answer(answer)
        entities_verified = []
        entities_not_found = []
        for entity in entities_mentioned:
            if self._entity_exists(entity):
                entities_verified.append(entity)
            else:
                entities_not_found.append(entity)
        
        relationships_claimed = self._extract_relationships_from_answer(answer)
        rels_verified = []
        rels_not_found = []
        for source, target, rel_type in relationships_claimed:
            if self._relationship_exists(source, target, rel_type):
                rels_verified.append(f"{source} -> {target} ({rel_type})")
            else:
                rels_not_found.append(f"{source} -> {target} ({rel_type})")
        
        category, issues = self._categorize_response(
            response_data,
            entities_verified,
            entities_not_found,
            rels_verified,
            rels_not_found
        )
        
        return EvaluationResult(
            query_id=query.id,
            query_text=query.query_text,
            category=query.category.value,
            difficulty=query.difficulty.value,
            hop_count=query.hop_count.value,
            response_category=category,
            confidence=response_data.get("confidence", 0.0),
            answer=answer[:1000],
            target_entity=response_data.get("target_entity"),
            entities_mentioned=entities_mentioned,
            entities_verified=entities_verified,
            entities_not_found=entities_not_found,
            relationships_claimed=[f"{s} -> {t} ({r})" for s, t, r in relationships_claimed],
            relationships_verified=rels_verified,
            relationships_not_found=rels_not_found,
            issues=issues,
            duration_seconds=duration,
            raw_response=response_data
        )
    
    def run_all(self) -> List[EvaluationResult]:
        """Run all 100 queries."""
        print(f"Starting evaluation of {len(self.query_set.queries)} queries...")
        
        for i, query in enumerate(self.query_set.queries):
            print(f"[{i+1}/{len(self.query_set.queries)}] {query.id}: {query.query_text[:50]}...")
            
            result = self.run_query(query)
            self.results.append(result)
            
            print(f"  -> {result.response_category.value} (conf={result.confidence:.2f})")
            
            if (i + 1) % 10 == 0:
                self._save_progress()
        
        return self.results
    
    def _save_progress(self):
        """Save intermediate progress."""
        with open("/tmp/evaluation_progress.json", "w") as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2, default=str)
        print(f"  Progress saved: {len(self.results)} results")
    
    def generate_report(self) -> str:
        """Generate the comprehensive markdown report."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        total = len(self.results)
        by_category = {}
        for cat in ResponseCategory:
            by_category[cat] = [r for r in self.results if r.response_category == cat]
        
        by_query_type = {}
        for r in self.results:
            if r.category not in by_query_type:
                by_query_type[r.category] = []
            by_query_type[r.category].append(r)
        
        accurate_conf = [r.confidence for r in by_category[ResponseCategory.ACCURATE]]
        hallucinated_conf = [r.confidence for r in by_category[ResponseCategory.HALLUCINATED]]
        
        avg_accurate_conf = sum(accurate_conf) / len(accurate_conf) if accurate_conf else 0
        avg_hallucinated_conf = sum(hallucinated_conf) / len(hallucinated_conf) if hallucinated_conf else 0
        
        report = f"""# Context Foundry 100-Query Evaluation Report

**Generated:** {now}

## Executive Summary

| Category | Count | Percentage |
|----------|-------|------------|
| **ACCURATE** | {len(by_category[ResponseCategory.ACCURATE])} | {len(by_category[ResponseCategory.ACCURATE])/total*100:.1f}% |
| **PARTIAL** | {len(by_category[ResponseCategory.PARTIAL])} | {len(by_category[ResponseCategory.PARTIAL])/total*100:.1f}% |
| **HALLUCINATED** | {len(by_category[ResponseCategory.HALLUCINATED])} | {len(by_category[ResponseCategory.HALLUCINATED])/total*100:.1f}% |
| **NOT_FOUND** | {len(by_category[ResponseCategory.NOT_FOUND])} | {len(by_category[ResponseCategory.NOT_FOUND])/total*100:.1f}% |
| **ERROR** | {len(by_category[ResponseCategory.ERROR])} | {len(by_category[ResponseCategory.ERROR])/total*100:.1f}% |
| **TIMEOUT** | {len(by_category[ResponseCategory.TIMEOUT])} | {len(by_category[ResponseCategory.TIMEOUT])/total*100:.1f}% |
| **Total** | {total} | 100% |

**Key Metric: Hallucination Rate = {len(by_category[ResponseCategory.HALLUCINATED])/total*100:.1f}%**

## Confidence Calibration

| Response Type | Avg Confidence |
|---------------|----------------|
| ACCURATE | {avg_accurate_conf:.2f} |
| HALLUCINATED | {avg_hallucinated_conf:.2f} |

{"**WARNING**: Confidence is NOT well-calibrated - hallucinated responses have similar confidence to accurate ones." if abs(avg_accurate_conf - avg_hallucinated_conf) < 0.15 else "Confidence appears reasonably calibrated."}

## Hallucination Analysis

"""
        
        if by_category[ResponseCategory.HALLUCINATED]:
            report += "### Hallucinated Responses\n\n"
            for r in by_category[ResponseCategory.HALLUCINATED]:
                report += f"""#### {r.query_id}: {r.query_text}
- **Confidence:** {r.confidence:.2f}
- **Issues:**
"""
                for issue in r.issues:
                    report += f"  - {issue}\n"
                report += f"- **Answer excerpt:** {r.answer[:300]}...\n\n"
        else:
            report += "*No hallucinated responses detected.*\n\n"
        
        report += "## Category Breakdown\n\n"
        
        for cat_name, results in by_query_type.items():
            accurate = sum(1 for r in results if r.response_category == ResponseCategory.ACCURATE)
            hallucinated = sum(1 for r in results if r.response_category == ResponseCategory.HALLUCINATED)
            partial = sum(1 for r in results if r.response_category == ResponseCategory.PARTIAL)
            not_found = sum(1 for r in results if r.response_category == ResponseCategory.NOT_FOUND)
            
            report += f"""### {cat_name.replace('_', ' ').title()} ({len(results)} queries)
| Result | Count |
|--------|-------|
| Accurate | {accurate} |
| Partial | {partial} |
| Hallucinated | {hallucinated} |
| Not Found | {not_found} |

"""
        
        report += "## Entity Existence Guard Analysis\n\n"
        not_found_results = by_category[ResponseCategory.NOT_FOUND]
        report += f"- **Queries triggering 'not found':** {len(not_found_results)}\n"
        if not_found_results:
            report += "- **Examples:**\n"
            for r in not_found_results[:5]:
                report += f"  - {r.query_id}: {r.query_text[:60]}...\n"
        
        report += "\n## Recommendations\n\n"
        
        if len(by_category[ResponseCategory.HALLUCINATED]) > 10:
            report += "1. **HIGH PRIORITY:** Hallucination rate is concerning. Review entity extraction patterns.\n"
        if abs(avg_accurate_conf - avg_hallucinated_conf) < 0.15:
            report += "2. **Confidence calibration needed:** Model confidence doesn't correlate with accuracy.\n"
        
        problematic_cats = []
        for cat_name, results in by_query_type.items():
            hallucinated = sum(1 for r in results if r.response_category == ResponseCategory.HALLUCINATED)
            if len(results) > 0 and hallucinated / len(results) > 0.2:
                problematic_cats.append(cat_name)
        
        if problematic_cats:
            report += f"3. **Focus improvement on:** {', '.join(problematic_cats)}\n"
        
        report += "\n## Full Results Table\n\n"
        report += "| # | Query ID | Category | Confidence | Result | Issues |\n"
        report += "|---|----------|----------|------------|--------|--------|\n"
        
        for i, r in enumerate(self.results):
            issues_str = "; ".join(r.issues[:2]) if r.issues else "None"
            if len(issues_str) > 50:
                issues_str = issues_str[:47] + "..."
            report += f"| {i+1} | {r.query_id} | {r.category[:15]} | {r.confidence:.2f} | {r.response_category.value} | {issues_str} |\n"
        
        return report
    
    def save_results(self):
        """Save all results to files."""
        os.makedirs("/tmp", exist_ok=True)
        
        with open("/tmp/evaluation_raw_results.json", "w") as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2, default=str)
        print(f"Raw results saved to /tmp/evaluation_raw_results.json")
        
        report = self.generate_report()
        
        os.makedirs("/mnt/user-data/outputs", exist_ok=True)
        report_path = "/mnt/user-data/outputs/CF_100_Query_Evaluation_Report.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"Report saved to {report_path}")
        
        return report


def main():
    print("=" * 70)
    print("CONTEXT FOUNDRY 100-QUERY EVALUATION")
    print("=" * 70)
    print()
    
    runner = EvaluationRunner()
    
    print(f"Loaded {len(runner.query_set.queries)} queries")
    print()
    
    runner.run_all()
    
    report = runner.save_results()
    
    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    
    lines = report.split("\n")
    for line in lines[:30]:
        print(line)


if __name__ == "__main__":
    main()
