#!/usr/bin/env python3
"""
Manual test script for inference validation.
Run this to test the verification loop on specific queries.

Usage:
    python test_inference_validation.py

Set VAULT_ID environment variable or edit VAULT_ID below.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configuration - set your vault ID here
VAULT_ID = os.environ.get('VAULT_ID', 'e7c8b55c-a4e7-41be-aae7-82652cedb0d3')

# Test queries - these are the ones that were failing
TEST_QUERIES = [
    # Q16 - Toyota partnership (was returning "NextGen")
    "Who does Nexus Industries partner with for solid-state battery development?",

    # Q31 - JV ownership percentage
    "What percentage ownership does Nexus hold in the solid-state battery joint venture?",

    # Q82 - Company founding date
    "When was Nexus Industries founded?",
]


def main():
    print("=" * 60)
    print("INFERENCE VALIDATION MANUAL TEST")
    print("=" * 60)
    print(f"\nVault ID: {VAULT_ID}")
    print("\nInitializing Context Foundry...")

    try:
        from context_foundry.core import ContextFoundry

        cf = ContextFoundry(tenant_id=VAULT_ID)

        for i, query in enumerate(TEST_QUERIES, 1):
            print("\n" + "=" * 60)
            print(f"TEST {i}: {query}")
            print("=" * 60)

            try:
                result = cf.query(query, display_output=True, save_to_log=False)

                # Show key fields
                print("\n--- KEY RESPONSE FIELDS ---")
                print(f"Answer: {result.get('answer', 'N/A')[:200]}")
                print(f"Confidence: {result.get('confidence', 0):.2%}")
                print(f"Answer Source: {result.get('answer_source', 'N/A')}")

                # Inference validation specific
                print("\n--- INFERENCE VALIDATION ---")
                if result.get('inference_validated') is not None:
                    print(f"Validated: {result.get('inference_validated')}")
                    if result.get('inference_correction_reason'):
                        print(f"CORRECTED - Reason: {result.get('inference_correction_reason')}")
                    if result.get('inference_confidence'):
                        print(f"Validation Confidence: {result.get('inference_confidence'):.2%}")
                    if result.get('inference_needs_review'):
                        print("⚠️  NEEDS HUMAN REVIEW")
                    if result.get('inference_suggested_search'):
                        print(f"Suggested Search: {result.get('inference_suggested_search')}")
                else:
                    print("(Inference validation did not run)")

            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"Failed to initialize Context Foundry: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
