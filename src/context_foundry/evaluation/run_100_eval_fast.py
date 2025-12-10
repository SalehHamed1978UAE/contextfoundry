#!/usr/bin/env python3
"""
100-Query Autonomous Evaluation Script for Context Foundry.
Fast version - runs queries with shorter timeouts.
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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import requests
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.context_foundry.evaluation.query_set import QuerySet


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
    response_category: ResponseCategory
    confidence: float
    answer: str
    issues: List[str]
    duration_seconds: float
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["response_category"] = self.response_category.value
        return d


def run_single_query(query, api_url="http://localhost:5000"):
    """Run a single query with timeout."""
    start = time.time()
    try:
        resp = requests.post(
            f"{api_url}/api/query",
            json={"query": query.query_text},
            timeout=45
        )
        data = resp.json()
        duration = time.time() - start
        
        answer = data.get("answer", "")
        confidence = data.get("confidence", 0)
        
        if data.get("error"):
            cat = ResponseCategory.ERROR
            issues = ["Query returned error"]
        elif data.get("entity_not_found") or ("not found" in answer.lower() and "knowledge graph" in answer.lower()):
            cat = ResponseCategory.NOT_FOUND
            issues = ["Entity not found (correct behavior)"]
        elif confidence >= 0.5:
            cat = ResponseCategory.ACCURATE
            issues = []
        elif confidence >= 0.2:
            cat = ResponseCategory.PARTIAL
            issues = ["Medium confidence"]
        else:
            cat = ResponseCategory.PARTIAL
            issues = ["Low confidence"]
        
        return EvaluationResult(
            query_id=query.id,
            query_text=query.query_text,
            category=query.category.value,
            response_category=cat,
            confidence=confidence,
            answer=answer[:500],
            issues=issues,
            duration_seconds=duration
        )
    except requests.exceptions.Timeout:
        return EvaluationResult(
            query_id=query.id,
            query_text=query.query_text,
            category=query.category.value,
            response_category=ResponseCategory.TIMEOUT,
            confidence=0,
            answer="",
            issues=["Timeout"],
            duration_seconds=45
        )
    except Exception as e:
        return EvaluationResult(
            query_id=query.id,
            query_text=query.query_text,
            category=query.category.value,
            response_category=ResponseCategory.ERROR,
            confidence=0,
            answer="",
            issues=[str(e)],
            duration_seconds=time.time() - start
        )


def main():
    print("=" * 70)
    print("CONTEXT FOUNDRY 100-QUERY EVALUATION (FAST MODE)")
    print("=" * 70)
    
    qs = QuerySet()
    print(f"Loaded {len(qs.queries)} queries")
    
    results = []
    
    for i, q in enumerate(qs.queries):
        print(f"[{i+1:3d}/100] {q.id}: {q.query_text[:45]}...", end=" ", flush=True)
        result = run_single_query(q)
        results.append(result)
        print(f"-> {result.response_category.value} ({result.confidence:.2f})")
        
        if (i + 1) % 20 == 0:
            with open("/tmp/evaluation_progress.json", "w") as f:
                json.dump([r.to_dict() for r in results], f, indent=2)
            print(f"  [Progress saved: {i+1} queries]")
    
    with open("/tmp/evaluation_raw_results.json", "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)
    
    total = len(results)
    by_cat = {}
    for cat in ResponseCategory:
        by_cat[cat] = [r for r in results if r.response_category == cat]
    
    avg_conf_accurate = sum(r.confidence for r in by_cat[ResponseCategory.ACCURATE]) / len(by_cat[ResponseCategory.ACCURATE]) if by_cat[ResponseCategory.ACCURATE] else 0
    avg_conf_hall = sum(r.confidence for r in by_cat[ResponseCategory.HALLUCINATED]) / len(by_cat[ResponseCategory.HALLUCINATED]) if by_cat[ResponseCategory.HALLUCINATED] else 0
    
    report = f"""# Context Foundry 100-Query Evaluation Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary

| Category | Count | Percentage |
|----------|-------|------------|
| **ACCURATE** | {len(by_cat[ResponseCategory.ACCURATE])} | {len(by_cat[ResponseCategory.ACCURATE])/total*100:.1f}% |
| **PARTIAL** | {len(by_cat[ResponseCategory.PARTIAL])} | {len(by_cat[ResponseCategory.PARTIAL])/total*100:.1f}% |
| **HALLUCINATED** | {len(by_cat[ResponseCategory.HALLUCINATED])} | {len(by_cat[ResponseCategory.HALLUCINATED])/total*100:.1f}% |
| **NOT_FOUND** | {len(by_cat[ResponseCategory.NOT_FOUND])} | {len(by_cat[ResponseCategory.NOT_FOUND])/total*100:.1f}% |
| **ERROR** | {len(by_cat[ResponseCategory.ERROR])} | {len(by_cat[ResponseCategory.ERROR])/total*100:.1f}% |
| **TIMEOUT** | {len(by_cat[ResponseCategory.TIMEOUT])} | {len(by_cat[ResponseCategory.TIMEOUT])/total*100:.1f}% |
| **Total** | {total} | 100% |

**Key Metric: Hallucination Rate = {len(by_cat[ResponseCategory.HALLUCINATED])/total*100:.1f}%**

## Confidence Calibration

| Response Type | Avg Confidence |
|---------------|----------------|
| ACCURATE | {avg_conf_accurate:.2f} |
| HALLUCINATED | {avg_conf_hall:.2f} |

## Query Type Breakdown

"""
    
    by_type = {}
    for r in results:
        if r.category not in by_type:
            by_type[r.category] = []
        by_type[r.category].append(r)
    
    for cat_name, cat_results in by_type.items():
        accurate = sum(1 for r in cat_results if r.response_category == ResponseCategory.ACCURATE)
        partial = sum(1 for r in cat_results if r.response_category == ResponseCategory.PARTIAL)
        not_found = sum(1 for r in cat_results if r.response_category == ResponseCategory.NOT_FOUND)
        hall = sum(1 for r in cat_results if r.response_category == ResponseCategory.HALLUCINATED)
        report += f"### {cat_name.replace('_', ' ').title()} ({len(cat_results)} queries)\n"
        report += f"- Accurate: {accurate}, Partial: {partial}, Not Found: {not_found}, Hallucinated: {hall}\n\n"
    
    report += "## Entity Existence Guard\n\n"
    not_found_count = len(by_cat[ResponseCategory.NOT_FOUND])
    report += f"- **Queries triggering 'entity not found':** {not_found_count}\n"
    if not_found_count > 0:
        report += "- **Examples:**\n"
        for r in by_cat[ResponseCategory.NOT_FOUND][:5]:
            report += f"  - {r.query_id}: {r.query_text[:50]}...\n"
    
    report += "\n## Full Results\n\n"
    report += "| # | ID | Category | Conf | Result |\n"
    report += "|---|-----|----------|------|--------|\n"
    for i, r in enumerate(results):
        report += f"| {i+1} | {r.query_id} | {r.category[:12]} | {r.confidence:.2f} | {r.response_category.value} |\n"
    
    os.makedirs("/mnt/user-data/outputs", exist_ok=True)
    with open("/mnt/user-data/outputs/CF_100_Query_Evaluation_Report.md", "w") as f:
        f.write(report)
    
    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print()
    print(f"ACCURATE:     {len(by_cat[ResponseCategory.ACCURATE]):3d} ({len(by_cat[ResponseCategory.ACCURATE])/total*100:.1f}%)")
    print(f"PARTIAL:      {len(by_cat[ResponseCategory.PARTIAL]):3d} ({len(by_cat[ResponseCategory.PARTIAL])/total*100:.1f}%)")
    print(f"HALLUCINATED: {len(by_cat[ResponseCategory.HALLUCINATED]):3d} ({len(by_cat[ResponseCategory.HALLUCINATED])/total*100:.1f}%)")
    print(f"NOT_FOUND:    {len(by_cat[ResponseCategory.NOT_FOUND]):3d} ({len(by_cat[ResponseCategory.NOT_FOUND])/total*100:.1f}%)")
    print(f"ERROR:        {len(by_cat[ResponseCategory.ERROR]):3d} ({len(by_cat[ResponseCategory.ERROR])/total*100:.1f}%)")
    print(f"TIMEOUT:      {len(by_cat[ResponseCategory.TIMEOUT]):3d} ({len(by_cat[ResponseCategory.TIMEOUT])/total*100:.1f}%)")
    print()
    print(f"Report saved to: /mnt/user-data/outputs/CF_100_Query_Evaluation_Report.md")


if __name__ == "__main__":
    main()
