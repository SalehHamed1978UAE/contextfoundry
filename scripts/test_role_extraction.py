#!/usr/bin/env python3
"""
Test script to validate role extraction prompt changes on sample documents.
Runs extraction on 5-10 documents and shows role verification results.
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.context_foundry.extraction.entity_extractor import EntityExtractor
from src.context_foundry.extraction.role_verifier import (
    verify_role_assignment,
    verify_all_person_entities,
    RoleVerificationResult,
)


SAMPLE_TEXTS = {
    "executive_leadership": """
# Nexus Industries Executive Leadership

**Document Type:** Organizational Reference
**Last Updated:** January 2026

## Executive Team

**Dr. Victoria Chen, Chief Executive Officer**
Dr. Chen has led Nexus Industries since 2019, transforming the company into a diversified technology leader.

**Michael Chang, Chief Financial Officer**
Michael Chang serves as CFO and oversees all financial operations.

**Dr. Elena Rodriguez, Chief Engineer**
Chief Engineer: Dr. Elena Rodriguez leads the company's technology strategy across all divisions.

**Thomas Wright** leads the UAV engineering team and reports to Dr. Rodriguez.
He manages a team of 45 engineers focused on the Falcon X program.

**Jennifer Walsh, VP Investor Relations**
Jennifer Walsh is the VP of Investor Relations and also serves as interim CISO.
""",

    "division_leadership": """
# Nexus Industries Business Divisions

## Nexus Aerospace
**Division President:** Michael Torres
Headquarters: Seattle, Washington
Annual Revenue: $1.1 billion

Michael Torres has been president since 2022.

## Nexus Energy Systems  
**Division President:** Dr. Elena Rodriguez
Houston, Texas headquarters with 2,800 employees.

Dr. Rodriguez oversees all renewable energy operations.

## Nexus Digital Solutions
**President:** Robert Kim
Robert Kim replaced Thomas Anderson as Digital Solutions President in January 2026.
""",

    "project_team": """
# Falcon X Program Status Update

**Project Director:** Thomas Wright
**Chief Engineer:** Dr. Elena Rodriguez (Chair)

## Design Review Board

| Name | Role | Status |
|------|------|--------|
| Dr. Elena Rodriguez | Chief Engineer (Chair) | Present |
| Thomas Mueller | Falcon X Systems Lead | Present |
| Sarah Kim | Manufacturing Lead | Present |
| James Park | Quality Director | Present |

## Technical Team
- Thomas Wright manages overall program execution
- Dr. Rodriguez provides technical oversight as Chief Engineer
- Thomas Mueller leads systems integration
""",

    "press_release": """
# PRESS RELEASE: FY2025 Results

PHOENIX, AZ – January 28, 2026 – Nexus Industries, Inc. (NYSE: NEXS) today announced financial results.

"FY2025 was a transformational year," said Dr. Victoria Chen, CEO.

CFO Michael Chang added: "Our diversified portfolio positions us well for continued growth."

The company's Chief Engineer, Dr. Elena Rodriguez, presented the technology roadmap at the annual investor day.

Contact:
Jennifer Walsh, VP Investor Relations
ir@nexus-industries.com
""",

    "organizational_chart": """
# Nexus Industries Organization

CEO: Dr. Victoria Chen
├── CFO: Michael Chang
├── Chief Engineer: Dr. Elena Rodriguez
│   ├── Aerospace Engineering: Thomas Wright (Lead)
│   ├── Energy Systems: James Park (Lead)
│   └── Digital Systems: Alan Chen (Lead)
├── Division Presidents:
│   ├── Aerospace: Michael Torres
│   ├── Energy: Dr. Elena Rodriguez
│   └── Digital: Robert Kim
└── VP Investor Relations: Jennifer Walsh
""",
}

EXPECTED_ROLES = {
    "Dr. Victoria Chen": "CEO",
    "Michael Chang": "CFO",
    "Dr. Elena Rodriguez": "Chief Engineer",
    "Thomas Wright": None,
    "Jennifer Walsh": "VP Investor Relations",
    "Michael Torres": "Division President",
    "Robert Kim": "President",
}


def run_extraction_test():
    """Run extraction on sample documents and validate role assignments."""
    print("=" * 70)
    print("ROLE EXTRACTION VALIDATION TEST")
    print("=" * 70)
    print()
    
    extractor = EntityExtractor(model="gpt-4o-mini", temperature=0.0)
    
    all_results = []
    
    for doc_name, text in SAMPLE_TEXTS.items():
        print(f"\n{'='*60}")
        print(f"Document: {doc_name}")
        print(f"{'='*60}")
        print(f"Text length: {len(text)} chars")
        
        try:
            entities = extractor.extract_with_core_foundation(
                text=text,
                document_id=f"test_{doc_name}",
                chunk_id="chunk_0",
            )
            
            person_entities = [e for e in entities if e.entity_type == "PERSON"]
            print(f"Extracted {len(person_entities)} PERSON entities")
            
            for entity in person_entities:
                role = entity.properties.get("role")
                print(f"\n  Person: {entity.canonical_name}")
                print(f"  Extracted role: {role or '(none)'}")
                print(f"  Confidence: {entity.confidence}")
                
                verification = verify_role_assignment(
                    person_name=entity.canonical_name,
                    extracted_role=role,
                    source_text=text,
                )
                
                print(f"  Verification status: {verification.verification_status}")
                print(f"  Verification confidence: {verification.verification_confidence:.2f}")
                if verification.matched_pattern:
                    print(f"  Matched pattern: {verification.matched_pattern}")
                if verification.evidence_span:
                    print(f"  Evidence: ...{verification.evidence_span}...")
                if verification.issues:
                    print(f"  Issues: {verification.issues}")
                
                expected = EXPECTED_ROLES.get(entity.canonical_name)
                if expected is not None:
                    if role and expected.lower() in role.lower():
                        print(f"  ✓ CORRECT: Expected '{expected}', got '{role}'")
                    elif role is None and expected is None:
                        print(f"  ✓ CORRECT: Expected no role, got no role")
                    else:
                        print(f"  ✗ MISMATCH: Expected '{expected}', got '{role}'")
                
                all_results.append({
                    "document": doc_name,
                    "person": entity.canonical_name,
                    "extracted_role": role,
                    "expected_role": expected,
                    "verification": verification.to_dict(),
                })
        
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total = len(all_results)
    verified = sum(1 for r in all_results if r["verification"]["verification_confidence"] >= 0.8)
    weak = sum(1 for r in all_results if 0.5 <= r["verification"]["verification_confidence"] < 0.8)
    unverified = sum(1 for r in all_results if r["verification"]["verification_confidence"] < 0.5)
    
    print(f"Total PERSON entities: {total}")
    print(f"Verified (≥0.8 confidence): {verified}")
    print(f"Weak match (0.5-0.8): {weak}")
    print(f"Unverified (<0.5): {unverified}")
    
    correct = 0
    incorrect = 0
    for r in all_results:
        expected = r["expected_role"]
        actual = r["extracted_role"]
        if expected is not None:
            if expected is None and actual is None:
                correct += 1
            elif actual and expected.lower() in actual.lower():
                correct += 1
            else:
                incorrect += 1
    
    if correct + incorrect > 0:
        print(f"\nAgainst expected roles:")
        print(f"  Correct: {correct}/{correct + incorrect}")
        print(f"  Incorrect: {incorrect}/{correct + incorrect}")
    
    output_file = "test_results/role_extraction_validation.json"
    os.makedirs("test_results", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    run_extraction_test()
