"""
Systematic failure analysis for ContextFoundry.

Traces each failing question through all layers to identify root cause.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from ..models.schema import Entity, Relationship

logger = logging.getLogger(__name__)


class FailureLayer(Enum):
    """Layer where failure occurred."""
    CORPUS = "CORPUS"
    EXTRACTION = "EXTRACTION"
    INTEGRATION = "INTEGRATION"
    KG_DATA = "KG_DATA"
    QUERY = "QUERY"
    SYNTHESIS = "SYNTHESIS"
    EVALUATION = "EVALUATION"


class FailurePattern(Enum):
    """Common failure patterns."""
    MISSING_RELATIONSHIP = "MISSING_RELATIONSHIP"
    WRONG_RELATIONSHIP_TARGET = "WRONG_RELATIONSHIP_TARGET"
    MISSING_PROPERTY = "MISSING_PROPERTY"
    WRONG_PROPERTY_VALUE = "WRONG_PROPERTY_VALUE"
    ENTITY_TYPE_CONFUSION = "ENTITY_TYPE_CONFUSION"
    ANSWER_FORMAT_MISMATCH = "ANSWER_FORMAT_MISMATCH"
    SEMANTIC_EQUIVALENCE_MISS = "SEMANTIC_EQUIVALENCE_MISS"
    QUESTION_MISINTERPRETATION = "QUESTION_MISINTERPRETATION"


@dataclass
class FailureReport:
    """Complete analysis of a single failure."""

    question_id: int
    question: str
    expected: str
    actual: str
    match_type: str

    failure_layer: Optional[FailureLayer] = None
    failure_pattern: Optional[FailurePattern] = None

    corpus_evidence: Optional[str] = None
    corpus_document: Optional[str] = None
    extraction_found: bool = False
    extraction_models: List[str] = field(default_factory=list)
    kg_entity: Optional[str] = None
    kg_relationship: Optional[str] = None
    kg_value: Optional[str] = None
    query_trace: Optional[Dict] = None

    fix_suggestion: str = ""
    fix_category: str = ""
    fixed: bool = False

    def to_dict(self) -> Dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "expected": self.expected,
            "actual": self.actual,
            "match_type": self.match_type,
            "failure_layer": self.failure_layer.value if self.failure_layer else None,
            "failure_pattern": self.failure_pattern.value if self.failure_pattern else None,
            "corpus_evidence": self.corpus_evidence,
            "corpus_document": self.corpus_document,
            "extraction_found": self.extraction_found,
            "extraction_models": self.extraction_models,
            "kg_entity": self.kg_entity,
            "kg_relationship": self.kg_relationship,
            "kg_value": self.kg_value,
            "fix_suggestion": self.fix_suggestion,
            "fix_category": self.fix_category,
            "fixed": self.fixed
        }


class FailureAnalyzer:
    """
    Analyzes failing questions to identify root cause and suggest fixes.
    """

    def __init__(self, config):
        # Support both string (test results path) and dict config
        if isinstance(config, str):
            # String is treated as test results path
            self.config = {
                "test_results_path": config,
                "corpus_dir": "test documents/Manus Orion/documents/",
                "extraction_dir": "extraction_outputs/manus_orion/"
            }
        else:
            self.config = config
        
        self.test_results_path = self.config.get("test_results_path")
        self.corpus_dir = self.config.get("corpus_dir", "test documents/Manus Orion/documents/")
        self.extraction_dir = self.config.get("extraction_dir", "extraction_outputs/manus_orion/")
        self.tenant_id = self.config.get("tenant_id")
        self.failures = []

        self._corpus_cache: Dict[str, str] = {}
        self._load_corpus()

        self._session = None
        self._init_db()

    def _load_corpus(self):
        """Load all corpus documents into memory for searching."""
        if not self.corpus_dir:
            return

        corpus_path = Path(self.corpus_dir)
        if not corpus_path.exists():
            logger.warning(f"Corpus directory not found: {self.corpus_dir}")
            return

        for file_path in corpus_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt", ".json"]:
                try:
                    self._corpus_cache[str(file_path)] = file_path.read_text()
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(self._corpus_cache)} corpus documents")

    def _init_db(self):
        """Initialize database connection."""
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            try:
                engine = create_engine(database_url)
                Session = sessionmaker(bind=engine)
                self._session = Session()
                logger.info("Database connection initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize database: {e}")
                self._session = None

    def analyze_failure(self, failure: Dict) -> FailureReport:
        """
        Analyze a single failure through all layers.

        Args:
            failure: Dict with q, query, expected, actual, match_type

        Returns:
            FailureReport with diagnosis and fix suggestion
        """
        report = FailureReport(
            question_id=failure.get("q", 0),
            question=failure.get("query", ""),
            expected=failure.get("expected", ""),
            actual=failure.get("actual", ""),
            match_type=failure.get("match_type", "")
        )

        logger.info(f"Analyzing Q{report.question_id}: {report.question[:50]}...")

        corpus_result = self._check_corpus(report.expected, report.question)
        if corpus_result:
            report.corpus_evidence = corpus_result[0]
            report.corpus_document = corpus_result[1]
        else:
            report.failure_layer = FailureLayer.CORPUS
            report.fix_suggestion = "Expected answer not found in corpus. Verify question or remove from test set."
            report.fix_category = "CORPUS_GAP"
            return report

        extraction_result = self._check_extraction(report.expected, report.corpus_document)
        if extraction_result:
            report.extraction_found = True
            report.extraction_models = extraction_result
        else:
            report.failure_layer = FailureLayer.EXTRACTION
            report.failure_pattern = FailurePattern.MISSING_RELATIONSHIP
            report.fix_suggestion = f"Add targeted extraction prompt for this fact type. Source: {report.corpus_document}"
            report.fix_category = self._categorize_extraction_gap(report.question)
            return report

        kg_result = self._check_kg(report.expected, report.question)
        if kg_result.get("found"):
            report.kg_entity = kg_result.get("entity")
            report.kg_relationship = kg_result.get("relationship")
            report.kg_value = kg_result.get("value")

            if kg_result.get("value") != report.expected:
                report.failure_layer = FailureLayer.KG_DATA
                report.failure_pattern = FailurePattern.WRONG_PROPERTY_VALUE
                report.fix_suggestion = f"KG has wrong value: {kg_result.get('value')} vs expected {report.expected}"
                report.fix_category = "CONFLICT_RESOLUTION"
                return report
        else:
            report.failure_layer = FailureLayer.INTEGRATION
            report.failure_pattern = FailurePattern.WRONG_RELATIONSHIP_TARGET
            report.fix_suggestion = "Fact extracted but not in KG. Check entity resolution."
            report.fix_category = "ENTITY_RESOLUTION"
            return report

        query_result = self._check_query(report.question)
        report.query_trace = query_result

        if not query_result.get("retrieved"):
            report.failure_layer = FailureLayer.QUERY
            report.fix_suggestion = "Data in KG but query didn't retrieve it. Fix routing or retrieval."
            report.fix_category = "QUERY_ROUTING"
            return report

        if query_result.get("retrieved") and report.actual and report.expected.lower() not in report.actual.lower():
            report.failure_layer = FailureLayer.SYNTHESIS
            report.failure_pattern = self._classify_synthesis_error(report.question, report.expected, report.actual)
            report.fix_suggestion = f"LLM generated wrong answer from correct data. Pattern: {report.failure_pattern}"
            report.fix_category = "ANSWER_SYNTHESIS"
            return report

        report.failure_layer = FailureLayer.EVALUATION
        report.failure_pattern = FailurePattern.SEMANTIC_EQUIVALENCE_MISS
        report.fix_suggestion = "Answers may be equivalent but evaluator missed. Check semantic matching."
        report.fix_category = "EVALUATOR"

        return report

    def _check_corpus(self, expected: str, question: str) -> Optional[Tuple[str, str]]:
        """
        Search corpus for expected answer.

        Returns (evidence_quote, document_path) or None if not found.
        """
        expected_lower = expected.lower()
        key_terms = [t.strip() for t in expected_lower.replace(",", " ").split() if len(t.strip()) > 3]

        for doc_path, doc_text in self._corpus_cache.items():
            doc_lower = doc_text.lower()

            if expected_lower in doc_lower:
                idx = doc_lower.find(expected_lower)
                start = max(0, idx - 100)
                end = min(len(doc_text), idx + len(expected) + 100)
                evidence = doc_text[start:end].strip()
                return (evidence, doc_path)

            if key_terms:
                found = sum(1 for term in key_terms if term in doc_lower)
                if found >= len(key_terms) * 0.7:
                    for term in key_terms:
                        if term in doc_lower:
                            idx = doc_lower.find(term)
                            start = max(0, idx - 100)
                            end = min(len(doc_text), idx + 200)
                            evidence = doc_text[start:end].strip()
                            return (evidence, doc_path)

        return None

    def _check_extraction(self, expected: str, source_doc: Optional[str]) -> Optional[List[str]]:
        """
        Check if any model extracted the expected answer.

        Returns list of model names that extracted it, or None.
        """
        if not self.extraction_dir:
            return None

        models_found = []
        extraction_path = Path(self.extraction_dir)

        if not extraction_path.exists():
            logger.warning(f"Extraction directory not found: {self.extraction_dir}")
            return None

        expected_lower = expected.lower()
        expected_terms = [t.strip() for t in expected_lower.replace(",", " ").split() if len(t.strip()) > 3]

        for model_dir in extraction_path.iterdir():
            if not model_dir.is_dir():
                continue

            for extraction_file in model_dir.glob("*.json"):
                try:
                    with open(extraction_file) as f:
                        extraction = json.load(f)

                    extraction_text = json.dumps(extraction).lower()

                    if expected_lower in extraction_text:
                        if model_dir.name not in models_found:
                            models_found.append(model_dir.name)
                        continue

                    if expected_terms:
                        found = sum(1 for term in expected_terms if term in extraction_text)
                        if found >= len(expected_terms) * 0.6:
                            if model_dir.name not in models_found:
                                models_found.append(model_dir.name)

                except Exception as e:
                    logger.warning(f"Failed to check extraction {extraction_file}: {e}")

        return models_found if models_found else None

    def _check_kg(self, expected: str, question: str) -> Dict:
        """
        Check if expected answer exists in KG.

        Returns dict with found, entity, relationship, value.
        """
        if not self._session:
            return {"found": False, "reason": "No database connection"}

        try:
            expected_lower = expected.lower()
            key_terms = [t.strip() for t in expected_lower.replace(",", " ").split() if len(t.strip()) > 3]

            query = self._session.query(Entity)
            if self.tenant_id:
                query = query.filter(Entity.tenant_id == self.tenant_id)

            for entity in query.limit(500):
                entity_text = f"{entity.name} {entity.description or ''} {json.dumps(entity.properties or {})}".lower()
                
                if expected_lower in entity_text:
                    return {
                        "found": True,
                        "entity": entity.name,
                        "value": expected,
                        "entity_type": entity.entity_type
                    }

                if key_terms:
                    found = sum(1 for term in key_terms if term in entity_text)
                    if found >= len(key_terms) * 0.7:
                        return {
                            "found": True,
                            "entity": entity.name,
                            "value": entity_text[:200],
                            "partial_match": True
                        }

            rel_query = self._session.query(Relationship)
            if self.tenant_id:
                rel_query = rel_query.filter(Relationship.tenant_id == self.tenant_id)

            for rel in rel_query.limit(500):
                rel_text = f"{rel.relationship_type} {rel.description or ''} {json.dumps(rel.properties or {})}".lower()
                
                if expected_lower in rel_text:
                    return {
                        "found": True,
                        "relationship": rel.relationship_type,
                        "value": expected
                    }

        except Exception as e:
            logger.warning(f"KG check error: {e}")
            return {"found": False, "error": str(e)}

        return {"found": False}

    def _check_query(self, question: str) -> Dict:
        """
        Run the query and trace what was retrieved.

        Returns dict with retrieved data and routing info.
        """
        return {"retrieved": False, "reason": "Query tracing not implemented"}

    def _classify_synthesis_error(self, question: str, expected: str, actual: str) -> FailurePattern:
        """Classify the type of synthesis error."""
        question_lower = question.lower()
        actual_lower = actual.lower() if actual else ""

        if "responsibilities" in question_lower and ("who" in actual_lower or "is" in actual_lower[:50]):
            return FailurePattern.QUESTION_MISINTERPRETATION

        if "business unit" in question_lower and "manus orion group" in actual_lower:
            return FailurePattern.ENTITY_TYPE_CONFUSION

        if "focus" in question_lower and "information" not in actual_lower:
            return FailurePattern.MISSING_PROPERTY

        return FailurePattern.ANSWER_FORMAT_MISMATCH

    def _categorize_extraction_gap(self, question: str) -> str:
        """Categorize the extraction gap for pattern-based fixes."""
        question_lower = question.lower()

        if "responsibilities" in question_lower:
            return "PERSON_RESPONSIBILITIES"
        if "business unit" in question_lower and ("owns" in question_lower or "own" in question_lower):
            return "PROJECT_OWNERSHIP"
        if "focus" in question_lower:
            return "BU_FOCUS_AREAS"
        if "customer" in question_lower:
            return "CUSTOMER_RELATIONSHIPS"
        if "budget" in question_lower:
            return "PROJECT_BUDGETS"
        if "supplier" in question_lower:
            return "SUPPLIER_RELATIONSHIPS"
        if "partner" in question_lower:
            return "PARTNER_RELATIONSHIPS"
        if "project" in question_lower:
            return "PROJECT_INFO"
        if "who" in question_lower or "person" in question_lower:
            return "PERSON_INFO"

        return "GENERAL"

    def analyze_all_failures(self, failures: List[Dict]) -> List[FailureReport]:
        """Analyze all failures and return reports."""
        reports = []
        for failure in failures:
            report = self.analyze_failure(failure)
            reports.append(report)
        return reports

    def group_by_pattern(self, reports: List[FailureReport]) -> Dict[str, List[FailureReport]]:
        """Group failures by fix category for batch fixing."""
        groups: Dict[str, List[FailureReport]] = {}
        for report in reports:
            category = report.fix_category or "UNKNOWN"
            if category not in groups:
                groups[category] = []
            groups[category].append(report)
        return groups

    def group_by_layer(self, reports: List[FailureReport]) -> Dict[str, List[FailureReport]]:
        """Group failures by failure layer."""
        groups: Dict[str, List[FailureReport]] = {}
        for report in reports:
            layer = report.failure_layer.value if report.failure_layer else "UNKNOWN"
            if layer not in groups:
                groups[layer] = []
            groups[layer].append(report)
        return groups

    def generate_fix_plan(self, reports: List[FailureReport]) -> Dict:
        """Generate prioritized fix plan."""
        groups = self.group_by_pattern(reports)
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

        plan = {
            "total_failures": len(reports),
            "analyzed_at": datetime.utcnow().isoformat(),
            "categories": [],
            "priority_order": [],
            "layer_breakdown": {}
        }

        layer_groups = self.group_by_layer(reports)
        for layer, layer_reports in layer_groups.items():
            plan["layer_breakdown"][layer] = {
                "count": len(layer_reports),
                "questions": [r.question_id for r in layer_reports]
            }

        for category, category_reports in sorted_groups:
            plan["categories"].append({
                "name": category,
                "count": len(category_reports),
                "questions": [r.question_id for r in category_reports],
                "fix_suggestion": category_reports[0].fix_suggestion if category_reports else "",
                "failure_layer": category_reports[0].failure_layer.value if category_reports and category_reports[0].failure_layer else None,
                "sample_expected": category_reports[0].expected[:100] if category_reports else ""
            })
            plan["priority_order"].append(category)

        return plan

    def save_analysis(self, reports: List[FailureReport], output_path: str):
        """Save analysis to JSON file."""
        data = {
            "total_failures": len(reports),
            "analyzed_at": datetime.utcnow().isoformat(),
            "reports": [r.to_dict() for r in reports],
            "fix_plan": self.generate_fix_plan(reports)
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved failure analysis to {output_path}")

    @staticmethod
    def load_test_results(test_results_path: str) -> List[Dict]:
        """Load failures from a test results JSON file."""
        with open(test_results_path) as f:
            data = json.load(f)
        return data.get("failures", [])
