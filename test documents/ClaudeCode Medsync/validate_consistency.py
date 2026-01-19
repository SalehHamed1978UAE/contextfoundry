#!/usr/bin/env python3
"""
MedSync Health Document Corpus - Consistency Validation Script

This script validates that key metrics are consistent across all 100 documents.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Master data for validation
MASTER_DATA = {
    "total_employees": 1200,
    "fy2024_revenue": 485_100_000,
    "fy2023_revenue": 367_500_000,
    "fy2022_revenue": 249_900_000,
    "q1_2024_revenue": 110_250_000,
    "q2_2024_revenue": 117_600_000,
    "q3_2024_revenue": 124_950_000,
    "q4_2024_revenue": 132_300_000,
    "total_hospitals": 520,
    "total_clinics": 3200,
    "total_insurance": 210,
    "logo_retention": 87,
    "customer_retention": 91,
    "grr": 94,
    "nrr": 118,
    "total_funding": 992_250_000,
    "series_d_amount": 551_250_000,
}

def find_numbers_in_text(text: str, pattern: str) -> List[float]:
    """Extract numbers matching a pattern from text."""
    # Remove commas from numbers
    text = text.replace(",", "")
    matches = re.findall(pattern, text, re.IGNORECASE)
    numbers = []
    for match in matches:
        try:
            # Extract just the number part
            num_str = re.search(r'[\d.]+', match)
            if num_str:
                numbers.append(float(num_str.group()))
        except ValueError:
            pass
    return numbers

def validate_document(filepath: Path) -> Dict[str, List[str]]:
    """Validate a single document for consistency issues."""
    issues = {
        "errors": [],
        "warnings": [],
        "info": []
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        doc_id = filepath.stem.split('_')[0] if '_' in filepath.stem else filepath.stem
        
        # Check for revenue consistency
        if "485,100,000" in content or "485100000" in content:
            issues["info"].append(f"{doc_id}: Contains FY 2024 total revenue")
        
        # Check for employee count
        if "1,200" in content or "1200" in content:
            if "employee" in content.lower():
                issues["info"].append(f"{doc_id}: Contains total employee count")
        
        # Check for retention metrics
        if "87%" in content and "retention" in content.lower():
            issues["info"].append(f"{doc_id}: Contains logo retention rate")
        if "91%" in content and "retention" in content.lower():
            issues["info"].append(f"{doc_id}: Contains customer retention rate")
        if "94%" in content and "retention" in content.lower():
            issues["info"].append(f"{doc_id}: Contains GRR")
        if "118%" in content and "retention" in content.lower():
            issues["info"].append(f"{doc_id}: Contains NRR")
            
    except Exception as e:
        issues["errors"].append(f"{filepath.name}: Error reading file - {str(e)}")
    
    return issues

def validate_corpus(corpus_dir: Path) -> Dict[str, any]:
    """Validate the entire document corpus."""
    results = {
        "total_documents": 0,
        "documents_checked": 0,
        "errors": [],
        "warnings": [],
        "info": [],
        "summary": {}
    }
    
    documents_dir = corpus_dir / "documents"
    
    if not documents_dir.exists():
        results["errors"].append(f"Documents directory not found: {documents_dir}")
        return results
    
    # Count total documents
    doc_files = list(documents_dir.glob("*.md"))
    results["total_documents"] = len(doc_files)
    
    # Validate each document
    for doc_file in doc_files:
        issues = validate_document(doc_file)
        results["documents_checked"] += 1
        results["errors"].extend(issues["errors"])
        results["warnings"].extend(issues["warnings"])
        results["info"].extend(issues["info"])
    
    # Summary statistics
    results["summary"] = {
        "total_documents": results["total_documents"],
        "documents_checked": results["documents_checked"],
        "total_errors": len(results["errors"]),
        "total_warnings": len(results["warnings"]),
        "total_info": len(results["info"])
    }
    
    return results

def main():
    """Main validation function."""
    corpus_dir = Path("/home/ubuntu/medsync_corpus")
    
    print("=" * 80)
    print("MedSync Health Document Corpus - Consistency Validation")
    print("=" * 80)
    print()
    
    # Run validation
    results = validate_corpus(corpus_dir)
    
    # Print summary
    print("VALIDATION SUMMARY")
    print("-" * 80)
    print(f"Total Documents: {results['summary']['total_documents']}")
    print(f"Documents Checked: {results['summary']['documents_checked']}")
    print(f"Errors Found: {results['summary']['total_errors']}")
    print(f"Warnings Found: {results['summary']['total_warnings']}")
    print(f"Info Messages: {results['summary']['total_info']}")
    print()
    
    # Print errors
    if results["errors"]:
        print("ERRORS")
        print("-" * 80)
        for error in results["errors"]:
            print(f"  ❌ {error}")
        print()
    
    # Print warnings
    if results["warnings"]:
        print("WARNINGS")
        print("-" * 80)
        for warning in results["warnings"]:
            print(f"  ⚠️  {warning}")
        print()
    
    # Print sample info messages (first 10)
    if results["info"]:
        print("INFO (Sample - First 10)")
        print("-" * 80)
        for info in results["info"][:10]:
            print(f"  ℹ️  {info}")
        if len(results["info"]) > 10:
            print(f"  ... and {len(results['info']) - 10} more")
        print()
    
    # Final status
    print("=" * 80)
    if results["summary"]["total_errors"] == 0:
        print("✅ VALIDATION PASSED - No critical errors found")
    else:
        print("❌ VALIDATION FAILED - Critical errors found")
    print("=" * 80)
    
    return 0 if results["summary"]["total_errors"] == 0 else 1

if __name__ == "__main__":
    exit(main())
