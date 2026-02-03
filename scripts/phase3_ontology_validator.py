#!/usr/bin/env python3
"""
Phase 3 Ontology Validation Script

DETERMINISTIC VALIDATION - NO LLM JUDGMENT CALLS
This script uses hard counts and database queries to verify work completion.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# VALIDATION GATES - ALL MUST PASS
REQUIRED_DOCUMENT_COUNT = 100  # Minimum documents in vault
REQUIRED_ENTITY_COUNT = 500    # Minimum entities extracted
REQUIRED_RELATIONSHIP_COUNT = 1000  # Minimum relationships
REQUIRED_TEST_QUESTIONS = 100  # Must answer all 100 questions
MINIMUM_ACCURACY_PERCENT = 88.0  # Must match or beat baseline
REQUIRED_ONTOLOGY_TYPES_USED = 10  # Minimum ontology types actually used

class Phase3Validator:
    """Deterministic validator for Phase 3 ontology work."""

    def __init__(self, vault_id: str, vault_name: str):
        self.vault_id = vault_id
        self.vault_name = vault_name
        self.results = {
            "vault_id": vault_id,
            "vault_name": vault_name,
            "timestamp": datetime.utcnow().isoformat(),
            "gates": {},
            "overall_pass": False
        }

        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError("DATABASE_URL not set")

        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()

    def gate_1_vault_exists(self) -> Tuple[bool, str]:
        """GATE 1: Vault must exist in database."""
        self.log("GATE 1: Checking vault exists...")

        result = self.session.execute(
            text("SELECT id, name FROM platform.tenants WHERE id = :vid"),
            {"vid": self.vault_id}
        ).fetchone()

        if not result:
            return False, f"Vault {self.vault_id} does not exist in database"

        return True, f"Vault exists: {result.name}"

    def gate_2_documents_uploaded(self) -> Tuple[bool, str]:
        """GATE 2: Minimum document count."""
        self.log("GATE 2: Checking document count...")

        count = self.session.execute(
            text("SELECT COUNT(*) FROM platform.documents WHERE tenant_id = :vid"),
            {"vid": self.vault_id}
        ).scalar()

        if count < REQUIRED_DOCUMENT_COUNT:
            return False, f"Only {count} documents uploaded (need {REQUIRED_DOCUMENT_COUNT})"

        return True, f"{count} documents uploaded (required: {REQUIRED_DOCUMENT_COUNT})"

    def gate_3_extraction_completed(self) -> Tuple[bool, str]:
        """GATE 3: All documents must be extracted."""
        self.log("GATE 3: Checking extraction completion...")

        stats = self.session.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'extracted' THEN 1 ELSE 0 END) as extracted,
                    SUM(CASE WHEN extraction_level = 'ontology' THEN 1 ELSE 0 END) as ontology
                FROM platform.documents
                WHERE tenant_id = :vid
            """),
            {"vid": self.vault_id}
        ).fetchone()

        if stats.total == 0:
            return False, "No documents found"

        if stats.extracted < stats.total:
            return False, f"Only {stats.extracted}/{stats.total} documents extracted"

        if stats.ontology < stats.total:
            return False, f"Only {stats.ontology}/{stats.total} used ontology extraction (not all used --use-ontology)"

        return True, f"All {stats.total} documents extracted with ontology pipeline"

    def gate_4_entities_created(self) -> Tuple[bool, str]:
        """GATE 4: Minimum entity count."""
        self.log("GATE 4: Checking entity count...")

        count = self.session.execute(
            text("SELECT COUNT(*) FROM entities WHERE tenant_id = :vid"),
            {"vid": self.vault_id}
        ).scalar()

        if count < REQUIRED_ENTITY_COUNT:
            return False, f"Only {count} entities extracted (need {REQUIRED_ENTITY_COUNT})"

        return True, f"{count} entities extracted (required: {REQUIRED_ENTITY_COUNT})"

    def gate_5_relationships_created(self) -> Tuple[bool, str]:
        """GATE 5: Minimum relationship count."""
        self.log("GATE 5: Checking relationship count...")

        count = self.session.execute(
            text("SELECT COUNT(*) FROM relationships WHERE tenant_id = :vid"),
            {"vid": self.vault_id}
        ).scalar()

        if count < REQUIRED_RELATIONSHIP_COUNT:
            return False, f"Only {count} relationships extracted (need {REQUIRED_RELATIONSHIP_COUNT})"

        return True, f"{count} relationships extracted (required: {REQUIRED_RELATIONSHIP_COUNT})"

    def gate_6_ontology_types_used(self) -> Tuple[bool, str]:
        """GATE 6: Ontology types must actually be used."""
        self.log("GATE 6: Checking ontology type usage...")

        type_count = self.session.execute(
            text("""
                SELECT COUNT(DISTINCT entity_type)
                FROM entities
                WHERE tenant_id = :vid
            """),
            {"vid": self.vault_id}
        ).scalar()

        if type_count < REQUIRED_ONTOLOGY_TYPES_USED:
            return False, f"Only {type_count} entity types used (need {REQUIRED_ONTOLOGY_TYPES_USED})"

        return True, f"{type_count} distinct entity types used (required: {REQUIRED_ONTOLOGY_TYPES_USED})"

    def gate_7_test_results_exist(self) -> Tuple[bool, str]:
        """GATE 7: Test results file must exist."""
        self.log("GATE 7: Checking test results file...")

        status_file = Path("data/test-runner/status.json")
        if not status_file.exists():
            return False, "Test results file not found: data/test-runner/status.json"

        try:
            with open(status_file) as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Cannot read test results: {e}"

        return True, f"Test results file exists and is valid JSON"

    def gate_8_all_questions_answered(self) -> Tuple[bool, str]:
        """GATE 8: All 100 questions must be answered."""
        self.log("GATE 8: Checking all questions answered...")

        status_file = Path("data/test-runner/status.json")
        with open(status_file) as f:
            data = json.load(f)

        qa_progress = data.get("qa_progress", {})
        total = qa_progress.get("total", 0)
        answered = qa_progress.get("answered", 0)

        if total != REQUIRED_TEST_QUESTIONS:
            return False, f"Test suite has {total} questions (expected {REQUIRED_TEST_QUESTIONS})"

        if answered < total:
            return False, f"Only {answered}/{total} questions answered"

        return True, f"All {answered}/{total} questions answered"

    def gate_9_accuracy_threshold(self) -> Tuple[bool, str]:
        """GATE 9: Accuracy must meet or beat 88% baseline."""
        self.log("GATE 9: Checking accuracy threshold...")

        status_file = Path("data/test-runner/status.json")
        with open(status_file) as f:
            data = json.load(f)

        qa_progress = data.get("qa_progress", {})
        accuracy = qa_progress.get("accuracy_percent", 0.0)
        passed = qa_progress.get("passed", 0)
        failed = qa_progress.get("failed", 0)

        if accuracy < MINIMUM_ACCURACY_PERCENT:
            return False, f"Accuracy is {accuracy}% (need {MINIMUM_ACCURACY_PERCENT}%)"

        return True, f"Accuracy: {accuracy}% ({passed} passed, {failed} failed) - MEETS BASELINE"

    def run_all_gates(self) -> Dict:
        """Run all validation gates."""
        self.log("="*70)
        self.log("PHASE 3 ONTOLOGY VALIDATION - DETERMINISTIC GATES")
        self.log("="*70)

        gates = [
            ("gate_1_vault_exists", self.gate_1_vault_exists),
            ("gate_2_documents_uploaded", self.gate_2_documents_uploaded),
            ("gate_3_extraction_completed", self.gate_3_extraction_completed),
            ("gate_4_entities_created", self.gate_4_entities_created),
            ("gate_5_relationships_created", self.gate_5_relationships_created),
            ("gate_6_ontology_types_used", self.gate_6_ontology_types_used),
            ("gate_7_test_results_exist", self.gate_7_test_results_exist),
            ("gate_8_all_questions_answered", self.gate_8_all_questions_answered),
            ("gate_9_accuracy_threshold", self.gate_9_accuracy_threshold),
        ]

        all_passed = True

        for gate_name, gate_func in gates:
            try:
                passed, message = gate_func()
                self.results["gates"][gate_name] = {
                    "passed": passed,
                    "message": message
                }

                status = "✅ PASS" if passed else "❌ FAIL"
                self.log(f"{status}: {message}")

                if not passed:
                    all_passed = False

            except Exception as e:
                self.results["gates"][gate_name] = {
                    "passed": False,
                    "message": f"Exception: {str(e)}"
                }
                self.log(f"❌ FAIL: {gate_name} raised exception: {e}")
                all_passed = False

        self.results["overall_pass"] = all_passed

        self.log("="*70)
        if all_passed:
            self.log("✅ ALL GATES PASSED - PHASE 3 VALIDATION SUCCESS")
        else:
            self.log("❌ VALIDATION FAILED - SEE FAILURES ABOVE")
        self.log("="*70)

        # Write results to file
        results_file = Path("data/phase3_validation_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        self.log(f"Results written to: {results_file}")

        return self.results


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/phase3_ontology_validator.py <vault_id> <vault_name>")
        sys.exit(1)

    vault_id = sys.argv[1]
    vault_name = sys.argv[2]

    validator = Phase3Validator(vault_id, vault_name)
    results = validator.run_all_gates()

    sys.exit(0 if results["overall_pass"] else 1)


if __name__ == "__main__":
    main()
