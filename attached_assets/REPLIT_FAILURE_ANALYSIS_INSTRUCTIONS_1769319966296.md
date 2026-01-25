# ContextFoundry: Systematic Failure Analysis Instructions for Replit

## Objective

Implement a systematic failure analysis loop to improve accuracy from 63.2% (67/106) to ≥90% (95/106) on the Manus Orion corpus.

## Current State

- **Accuracy**: 67/106 (63.2%)
- **Failures**: 39 questions
- **KG Stats**: 4,128 entities, 4,223 relationships
- **Pipeline**: Multi-model extraction (GPT-4o-mini + Claude) complete

---

## Part 1: Build the Failure Analysis Tool

### File: `src/context_foundry/analysis/failure_analyzer.py`

```python
"""
Systematic failure analysis for ContextFoundry.

Traces each failing question through all layers to identify root cause.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class FailureLayer(Enum):
    """Layer where failure occurred."""
    CORPUS = "CORPUS"           # Fact not in documents
    EXTRACTION = "EXTRACTION"   # Fact not extracted by models
    INTEGRATION = "INTEGRATION" # Entity resolution or merging error
    KG_DATA = "KG_DATA"         # Wrong value in KG
    QUERY = "QUERY"             # Routing or retrieval failure
    SYNTHESIS = "SYNTHESIS"     # LLM answer generation error
    EVALUATION = "EVALUATION"   # Semantic matching missed valid answer


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

    # Diagnosis
    failure_layer: Optional[FailureLayer] = None
    failure_pattern: Optional[FailurePattern] = None

    # Evidence
    corpus_evidence: Optional[str] = None  # Quote from document
    corpus_document: Optional[str] = None  # Source document path
    extraction_found: bool = False
    extraction_models: List[str] = field(default_factory=list)
    kg_entity: Optional[str] = None
    kg_relationship: Optional[str] = None
    kg_value: Optional[str] = None
    query_trace: Optional[Dict] = None

    # Fix
    fix_suggestion: str = ""
    fix_category: str = ""  # For grouping similar fixes
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

    def __init__(self, config: Dict):
        self.config = config
        self.corpus_dir = config.get("corpus_dir")
        self.extraction_dir = config.get("extraction_dir")

        # Load corpus text for searching
        self._corpus_cache: Dict[str, str] = {}
        self._load_corpus()

        # Initialize DB connection for KG queries
        self._init_db()

    def _load_corpus(self):
        """Load all corpus documents into memory for searching."""
        if not self.corpus_dir:
            return

        corpus_path = Path(self.corpus_dir)
        for file_path in corpus_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt", ".json"]:
                try:
                    self._corpus_cache[str(file_path)] = file_path.read_text()
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(self._corpus_cache)} corpus documents")

    def _init_db(self):
        """Initialize database connection."""
        # Use existing DB connection from config
        pass

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

        # Layer 1: Check corpus
        corpus_result = self._check_corpus(report.expected, report.question)
        if corpus_result:
            report.corpus_evidence = corpus_result[0]
            report.corpus_document = corpus_result[1]
        else:
            report.failure_layer = FailureLayer.CORPUS
            report.fix_suggestion = "Expected answer not found in corpus. Verify question or remove from test set."
            report.fix_category = "CORPUS_GAP"
            return report

        # Layer 2: Check extraction
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

        # Layer 3: Check KG
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

        # Layer 4: Check query/routing
        query_result = self._check_query(report.question)
        report.query_trace = query_result

        if not query_result.get("retrieved"):
            report.failure_layer = FailureLayer.QUERY
            report.fix_suggestion = "Data in KG but query didn't retrieve it. Fix routing or retrieval."
            report.fix_category = "QUERY_ROUTING"
            return report

        # Layer 5: Check synthesis
        if query_result.get("retrieved") and report.actual and report.expected.lower() not in report.actual.lower():
            report.failure_layer = FailureLayer.SYNTHESIS
            report.failure_pattern = self._classify_synthesis_error(report.question, report.expected, report.actual)
            report.fix_suggestion = f"LLM generated wrong answer from correct data. Pattern: {report.failure_pattern}"
            report.fix_category = "ANSWER_SYNTHESIS"
            return report

        # Layer 6: Evaluation issue
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

        # Extract key terms from expected answer
        key_terms = [t.strip() for t in expected_lower.replace(",", " ").split() if len(t.strip()) > 3]

        for doc_path, doc_text in self._corpus_cache.items():
            doc_lower = doc_text.lower()

            # Check for exact match
            if expected_lower in doc_lower:
                # Find context around match
                idx = doc_lower.find(expected_lower)
                start = max(0, idx - 100)
                end = min(len(doc_text), idx + len(expected) + 100)
                evidence = doc_text[start:end].strip()
                return (evidence, doc_path)

            # Check for key terms (at least 70% present)
            if key_terms:
                found = sum(1 for term in key_terms if term in doc_lower)
                if found >= len(key_terms) * 0.7:
                    # Find a relevant sentence
                    for term in key_terms:
                        if term in doc_lower:
                            idx = doc_lower.find(term)
                            start = max(0, idx - 100)
                            end = min(len(doc_text), idx + 200)
                            evidence = doc_text[start:end].strip()
                            return (evidence, doc_path)

        return None

    def _check_extraction(self, expected: str, source_doc: str) -> Optional[List[str]]:
        """
        Check if any model extracted the expected answer.

        Returns list of model names that extracted it, or None.
        """
        if not self.extraction_dir:
            return None

        models_found = []
        extraction_path = Path(self.extraction_dir)

        expected_lower = expected.lower()

        for model_dir in extraction_path.iterdir():
            if not model_dir.is_dir():
                continue

            for extraction_file in model_dir.glob("*.json"):
                try:
                    with open(extraction_file) as f:
                        extraction = json.load(f)

                    # Check entities
                    for entity in extraction.get("entities", []):
                        if expected_lower in json.dumps(entity).lower():
                            if model_dir.name not in models_found:
                                models_found.append(model_dir.name)
                            break

                    # Check relationships
                    for rel in extraction.get("relationships", []):
                        if expected_lower in json.dumps(rel).lower():
                            if model_dir.name not in models_found:
                                models_found.append(model_dir.name)
                            break

                except Exception as e:
                    logger.warning(f"Failed to check extraction {extraction_file}: {e}")

        return models_found if models_found else None

    def _check_kg(self, expected: str, question: str) -> Dict:
        """
        Check if expected answer exists in KG.

        Returns dict with found, entity, relationship, value.
        """
        # This would query the actual KG
        # Placeholder implementation
        return {"found": False}

    def _check_query(self, question: str) -> Dict:
        """
        Run the query and trace what was retrieved.

        Returns dict with retrieved data and routing info.
        """
        # This would run the actual query with tracing
        # Placeholder implementation
        return {"retrieved": False}

    def _classify_synthesis_error(self, question: str, expected: str, actual: str) -> FailurePattern:
        """Classify the type of synthesis error."""
        question_lower = question.lower()

        if "responsibilities" in question_lower and ("who" in actual.lower() or "is" in actual.lower()):
            return FailurePattern.QUESTION_MISINTERPRETATION

        if "business unit" in question_lower and "manus orion group" in actual.lower():
            return FailurePattern.ENTITY_TYPE_CONFUSION

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

    def generate_fix_plan(self, reports: List[FailureReport]) -> Dict:
        """Generate prioritized fix plan."""
        groups = self.group_by_pattern(reports)

        # Sort by impact (most questions affected)
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

        plan = {
            "total_failures": len(reports),
            "categories": [],
            "priority_order": []
        }

        for category, category_reports in sorted_groups:
            plan["categories"].append({
                "name": category,
                "count": len(category_reports),
                "questions": [r.question_id for r in category_reports],
                "fix_suggestion": category_reports[0].fix_suggestion if category_reports else "",
                "failure_layer": category_reports[0].failure_layer.value if category_reports and category_reports[0].failure_layer else None
            })
            plan["priority_order"].append(category)

        return plan

    def save_analysis(self, reports: List[FailureReport], output_path: str):
        """Save analysis to JSON file."""
        data = {
            "total_failures": len(reports),
            "reports": [r.to_dict() for r in reports],
            "fix_plan": self.generate_fix_plan(reports)
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved failure analysis to {output_path}")
```

---

## Part 2: Build the Targeted Extractor

### File: `src/context_foundry/extraction/targeted_extractor.py`

```python
"""
Targeted extraction for specific failure patterns.

Creates specialized prompts for each failure category.
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


TARGETED_PROMPTS = {
    "PERSON_RESPONSIBILITIES": """
Your ONLY task is to extract RESPONSIBILITIES for people mentioned in this document.

For each person, extract:
- name: Full name
- title: Job title (CEO, CFO, CTO, COO, etc.)
- responsibilities: Their key duties, what they are accountable for

Look for phrases like:
- "responsible for..."
- "oversees..."
- "accountable for..."
- "leads..."
- "manages..."

Return JSON:
{
    "people": [
        {
            "name": "Person Name",
            "title": "Their Title",
            "responsibilities": ["responsibility 1", "responsibility 2"]
        }
    ]
}

Only include responsibilities explicitly stated in the document.
""",

    "PROJECT_OWNERSHIP": """
Your ONLY task is to extract OWNERSHIP relationships between PROJECTS and BUSINESS UNITS.

For each project/program mentioned, identify which business unit OWNS it.

Look for phrases like:
- "[Project] is led by [BU]"
- "[Project] is part of [BU]"
- "[BU] owns/manages/runs [Project]"
- "[Project] under [BU] division"

Business units are divisions like:
- Aerospace
- Energy Solutions
- Logistics
- SmartCity

Return JSON:
{
    "ownership": [
        {
            "project": "Project Name",
            "business_unit": "Business Unit Name",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated ownership relationships.
""",

    "BU_FOCUS_AREAS": """
Your ONLY task is to extract FOCUS AREAS for each business unit.

For each business unit mentioned, identify what they specialize in.

Look for phrases like:
- "[BU] focuses on..."
- "[BU] specializes in..."
- "[BU] products include..."
- "[BU] handles..."

Return JSON:
{
    "focus_areas": [
        {
            "business_unit": "BU Name",
            "focus_areas": ["area 1", "area 2", "area 3"],
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated focus areas.
""",

    "CUSTOMER_RELATIONSHIPS": """
Your ONLY task is to extract CUSTOMER relationships.

Identify organizations that are CUSTOMERS of the company.

A customer is an organization that:
- Purchases products or services
- Has a contract or agreement
- Is described as client, buyer, or customer

Return JSON:
{
    "customers": [
        {
            "customer_name": "Organization Name",
            "relationship": "CUSTOMER_OF",
            "supplier": "Manus Orion Group",
            "product_or_service": "what they buy (if mentioned)",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated customer relationships.
""",

    "PROJECT_BUDGETS": """
Your ONLY task is to extract BUDGET information for projects.

For each project, extract budget/funding amounts.

Look for:
- Total budget
- Annual budget
- Funding allocation
- Investment amount

Return JSON:
{
    "budgets": [
        {
            "project": "Project Name",
            "budget": "$XXM",
            "budget_type": "total|annual|phase",
            "source_document_type": "strategic_plan|status_update|financial_statement",
            "evidence": "quote from document"
        }
    ]
}

Preserve exact figures as stated. Note the document type for authority ranking.
""",

    "SUPPLIER_RELATIONSHIPS": """
Your ONLY task is to extract SUPPLIER relationships.

Identify organizations that are SUPPLIERS to the company.

A supplier is an organization that:
- Provides components, materials, or services
- Is described as vendor, supplier, or partner
- Has a supply contract

Return JSON:
{
    "suppliers": [
        {
            "supplier_name": "Organization Name",
            "relationship": "SUPPLIER_OF",
            "customer": "Manus Orion Group or specific project",
            "what_they_supply": "components, materials, services",
            "evidence": "quote from document"
        }
    ]
}

Only include explicitly stated supplier relationships.
"""
}


class TargetedExtractor:
    """
    Runs targeted extraction for specific failure patterns.
    """

    def __init__(self, config: Dict):
        self.config = config

        from openai import OpenAI
        self.openai_client = OpenAI(api_key=config.get("openai_api_key"))

        # Optionally add Claude
        if config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self.anthropic_client = Anthropic(api_key=config["anthropic_api_key"])
        else:
            self.anthropic_client = None

    def extract_for_category(self, category: str, documents: List[Dict]) -> List[Dict]:
        """
        Run targeted extraction for a specific failure category.

        Args:
            category: One of the TARGETED_PROMPTS keys
            documents: List of {"path": str, "text": str}

        Returns:
            List of extracted facts
        """
        if category not in TARGETED_PROMPTS:
            logger.warning(f"No targeted prompt for category: {category}")
            return []

        prompt_template = TARGETED_PROMPTS[category]
        results = []

        for doc in documents:
            logger.info(f"Targeted extraction ({category}) from {doc['path']}")

            prompt = f"{prompt_template}\n\nDocument:\n{doc['text'][:15000]}"

            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                import json
                result = json.loads(response.choices[0].message.content)
                result["_source_document"] = doc["path"]
                result["_extraction_type"] = "targeted"
                result["_category"] = category
                results.append(result)

            except Exception as e:
                logger.error(f"Targeted extraction failed: {e}")

        return results

    def extract_all_categories(self, categories: List[str], documents: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Run targeted extraction for multiple categories.

        Returns dict mapping category to extracted results.
        """
        all_results = {}

        for category in categories:
            results = self.extract_for_category(category, documents)
            all_results[category] = results

        return all_results
```

---

## Part 3: Build the Fix Applier

### File: `src/context_foundry/analysis/fix_applier.py`

```python
"""
Applies fixes based on failure analysis.

Integrates targeted extraction results into the KG.
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class FixApplier:
    """
    Applies fixes from targeted extraction to the KG.
    """

    def __init__(self, config: Dict):
        self.config = config
        # Initialize KG connection

    def apply_person_responsibilities(self, extractions: List[Dict]) -> Dict:
        """Add responsibilities to Person entities."""
        stats = {"updated": 0, "created": 0, "errors": 0}

        for extraction in extractions:
            for person in extraction.get("people", []):
                try:
                    # Find or create person entity
                    # Add responsibilities property
                    stats["updated"] += 1
                except Exception as e:
                    logger.error(f"Failed to apply: {e}")
                    stats["errors"] += 1

        return stats

    def apply_project_ownership(self, extractions: List[Dict]) -> Dict:
        """Add OWNED_BY relationships."""
        stats = {"created": 0, "updated": 0, "errors": 0}

        for extraction in extractions:
            for ownership in extraction.get("ownership", []):
                try:
                    project = ownership["project"]
                    bu = ownership["business_unit"]

                    # Create OWNED_BY relationship
                    # Project -> OWNED_BY -> BusinessUnit
                    stats["created"] += 1
                except Exception as e:
                    logger.error(f"Failed to apply: {e}")
                    stats["errors"] += 1

        return stats

    def apply_bu_focus_areas(self, extractions: List[Dict]) -> Dict:
        """Add FOCUSES_ON relationships."""
        stats = {"created": 0, "errors": 0}

        for extraction in extractions:
            for focus in extraction.get("focus_areas", []):
                try:
                    bu = focus["business_unit"]
                    areas = focus["focus_areas"]

                    for area in areas:
                        # Create FOCUSES_ON relationship
                        # BusinessUnit -> FOCUSES_ON -> Concept
                        stats["created"] += 1
                except Exception as e:
                    logger.error(f"Failed to apply: {e}")
                    stats["errors"] += 1

        return stats

    def apply_customer_relationships(self, extractions: List[Dict]) -> Dict:
        """Add CUSTOMER_OF relationships."""
        stats = {"created": 0, "errors": 0}

        for extraction in extractions:
            for customer in extraction.get("customers", []):
                try:
                    # Create CUSTOMER_OF relationship
                    stats["created"] += 1
                except Exception as e:
                    logger.error(f"Failed to apply: {e}")
                    stats["errors"] += 1

        return stats

    def apply_all(self, category: str, extractions: List[Dict]) -> Dict:
        """Apply fixes for a category."""
        appliers = {
            "PERSON_RESPONSIBILITIES": self.apply_person_responsibilities,
            "PROJECT_OWNERSHIP": self.apply_project_ownership,
            "BU_FOCUS_AREAS": self.apply_bu_focus_areas,
            "CUSTOMER_RELATIONSHIPS": self.apply_customer_relationships,
        }

        if category in appliers:
            return appliers[category](extractions)
        else:
            logger.warning(f"No applier for category: {category}")
            return {"error": f"No applier for {category}"}
```

---

## Part 4: Implement the Main Loop

### File: `src/context_foundry/analysis/improvement_loop.py`

```python
"""
Main improvement loop for systematic accuracy improvement.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

from .failure_analyzer import FailureAnalyzer
from ..extraction.targeted_extractor import TargetedExtractor
from .fix_applier import FixApplier

logger = logging.getLogger(__name__)


class ImprovementLoop:
    """
    Orchestrates the systematic improvement process.

    Loop:
    1. Run test, get failures
    2. Analyze failures
    3. Group by pattern
    4. Run targeted extraction for each pattern
    5. Apply fixes
    6. Re-run test
    7. Repeat until target accuracy
    """

    def __init__(self, config: Dict):
        self.config = config
        self.analyzer = FailureAnalyzer(config)
        self.extractor = TargetedExtractor(config)
        self.applier = FixApplier(config)

        self.target_accuracy = config.get("target_accuracy", 0.90)
        self.max_iterations = config.get("max_iterations", 10)

        self.output_dir = Path(config.get("output_dir", "/tmp/improvement_loop"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, test_results_path: str, corpus_documents: List[Dict]) -> Dict:
        """
        Run the improvement loop.

        Args:
            test_results_path: Path to test results JSON
            corpus_documents: List of {"path": str, "text": str}

        Returns:
            Summary of improvements made
        """
        # Load test results
        with open(test_results_path) as f:
            test_results = json.load(f)

        current_accuracy = test_results["results"]["accuracy_pct"] / 100
        failures = test_results.get("failures", [])

        logger.info(f"Starting improvement loop. Current accuracy: {current_accuracy:.1%}")
        logger.info(f"Target accuracy: {self.target_accuracy:.1%}")
        logger.info(f"Failures to analyze: {len(failures)}")

        iteration = 0
        history = []

        while current_accuracy < self.target_accuracy and iteration < self.max_iterations:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration}")
            logger.info(f"{'='*60}")

            # Step 1: Analyze failures
            logger.info("Step 1: Analyzing failures...")
            reports = self.analyzer.analyze_all_failures(failures)

            # Save analysis
            analysis_path = self.output_dir / f"analysis_iter{iteration}.json"
            self.analyzer.save_analysis(reports, str(analysis_path))

            # Step 2: Group by pattern
            logger.info("Step 2: Grouping by pattern...")
            groups = self.analyzer.group_by_pattern(reports)
            fix_plan = self.analyzer.generate_fix_plan(reports)

            logger.info(f"Found {len(groups)} failure categories:")
            for category, category_reports in groups.items():
                logger.info(f"  - {category}: {len(category_reports)} questions")

            # Step 3: Run targeted extraction for top categories
            logger.info("Step 3: Running targeted extraction...")

            # Process top 3 categories by impact
            categories_to_fix = fix_plan["priority_order"][:3]

            for category in categories_to_fix:
                if category in ["CORPUS_GAP", "UNKNOWN"]:
                    continue

                logger.info(f"  Extracting for: {category}")
                extractions = self.extractor.extract_for_category(category, corpus_documents)

                # Save extractions
                extraction_path = self.output_dir / f"extraction_{category}_iter{iteration}.json"
                with open(extraction_path, 'w') as f:
                    json.dump(extractions, f, indent=2)

                # Step 4: Apply fixes
                logger.info(f"  Applying fixes for: {category}")
                stats = self.applier.apply_all(category, extractions)
                logger.info(f"  Applied: {stats}")

            # Step 5: Re-run test (would trigger actual test runner)
            logger.info("Step 5: Re-running test...")
            # new_results = run_test(...)  # This would call the actual test runner

            # For now, we just record the iteration
            history.append({
                "iteration": iteration,
                "accuracy_before": current_accuracy,
                "failures_analyzed": len(failures),
                "categories_fixed": categories_to_fix,
            })

            # In real implementation, update current_accuracy and failures from new test
            break  # For now, just one iteration

        # Generate summary
        summary = {
            "iterations": iteration,
            "starting_accuracy": test_results["results"]["accuracy_pct"] / 100,
            "final_accuracy": current_accuracy,
            "target_accuracy": self.target_accuracy,
            "target_met": current_accuracy >= self.target_accuracy,
            "history": history
        }

        summary_path = self.output_dir / "improvement_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\nImprovement loop complete. Summary saved to {summary_path}")

        return summary
```

---

## Part 5: CLI Entry Point

### File: `src/context_foundry/analysis/cli.py`

```python
"""
CLI for running failure analysis and improvement loop.
"""

import argparse
import json
import logging
from pathlib import Path

from .failure_analyzer import FailureAnalyzer
from .improvement_loop import ImprovementLoop

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description="ContextFoundry Failure Analysis")

    subparsers = parser.add_subparsers(dest="command")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze failures")
    analyze_parser.add_argument("--test-results", required=True, help="Path to test results JSON")
    analyze_parser.add_argument("--corpus-dir", required=True, help="Path to corpus directory")
    analyze_parser.add_argument("--extraction-dir", help="Path to extraction outputs")
    analyze_parser.add_argument("--output", default="failure_analysis.json", help="Output path")

    # Improve command
    improve_parser = subparsers.add_parser("improve", help="Run improvement loop")
    improve_parser.add_argument("--test-results", required=True, help="Path to test results JSON")
    improve_parser.add_argument("--corpus-dir", required=True, help="Path to corpus directory")
    improve_parser.add_argument("--target-accuracy", type=float, default=0.90, help="Target accuracy")
    improve_parser.add_argument("--max-iterations", type=int, default=10, help="Max iterations")
    improve_parser.add_argument("--output-dir", default="/tmp/improvement_loop", help="Output directory")

    args = parser.parse_args()

    if args.command == "analyze":
        config = {
            "corpus_dir": args.corpus_dir,
            "extraction_dir": args.extraction_dir,
        }

        analyzer = FailureAnalyzer(config)

        with open(args.test_results) as f:
            test_results = json.load(f)

        failures = test_results.get("failures", [])
        reports = analyzer.analyze_all_failures(failures)
        analyzer.save_analysis(reports, args.output)

        # Print summary
        plan = analyzer.generate_fix_plan(reports)
        print(f"\nFailure Analysis Summary")
        print(f"========================")
        print(f"Total failures: {plan['total_failures']}")
        print(f"\nCategories (priority order):")
        for cat in plan["categories"]:
            print(f"  {cat['name']}: {cat['count']} questions")
            print(f"    Layer: {cat['failure_layer']}")
            print(f"    Questions: {cat['questions']}")

    elif args.command == "improve":
        # Load corpus
        corpus_path = Path(args.corpus_dir)
        documents = []
        for file_path in corpus_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt"]:
                try:
                    documents.append({
                        "path": str(file_path),
                        "text": file_path.read_text()
                    })
                except:
                    pass

        config = {
            "corpus_dir": args.corpus_dir,
            "target_accuracy": args.target_accuracy,
            "max_iterations": args.max_iterations,
            "output_dir": args.output_dir,
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        }

        loop = ImprovementLoop(config)
        summary = loop.run(args.test_results, documents)

        print(f"\nImprovement Summary")
        print(f"===================")
        print(f"Iterations: {summary['iterations']}")
        print(f"Starting accuracy: {summary['starting_accuracy']:.1%}")
        print(f"Final accuracy: {summary['final_accuracy']:.1%}")
        print(f"Target met: {summary['target_met']}")


if __name__ == "__main__":
    import os
    main()
```

---

## Part 6: Execution Order

### Step 1: Analyze Current Failures

```bash
python -m src.context_foundry.analysis.cli analyze \
    --test-results /path/to/vault_aab0ec76_20260125_053141.json \
    --corpus-dir /path/to/manus_orion_corpus \
    --extraction-dir extraction_outputs/manus_orion \
    --output failure_analysis.json
```

### Step 2: Review Analysis

Check `failure_analysis.json` for:
- Which layer each failure occurs at
- Grouped categories with counts
- Priority order for fixes

### Step 3: Run Targeted Extraction for Top Categories

Based on analysis, run targeted extraction:

```python
from src.context_foundry.extraction.targeted_extractor import TargetedExtractor

extractor = TargetedExtractor({"openai_api_key": "..."})

# For person responsibilities (Q13-16)
results = extractor.extract_for_category("PERSON_RESPONSIBILITIES", documents)

# For project ownership (Q26, Q30, Q36)
results = extractor.extract_for_category("PROJECT_OWNERSHIP", documents)

# For BU focus areas (Q18-24)
results = extractor.extract_for_category("BU_FOCUS_AREAS", documents)
```

### Step 4: Apply Fixes to KG

```python
from src.context_foundry.analysis.fix_applier import FixApplier

applier = FixApplier(config)
stats = applier.apply_all("PERSON_RESPONSIBILITIES", extractions)
```

### Step 5: Re-run Test

```bash
python -m src.test_runner.runner \
    --corpus "Manus Orion" \
    --questions /path/to/orion_verified_106q.json
```

### Step 6: Repeat Until Target

Continue the loop until 90% accuracy is reached.

---

## Success Criteria

- [ ] FailureAnalyzer correctly diagnoses failure layer for each question
- [ ] Failures grouped by pattern for batch fixing
- [ ] Targeted extraction prompts produce correct facts
- [ ] Fixes applied to KG without errors
- [ ] Re-test shows improvement after each iteration
- [ ] Loop terminates when target accuracy reached

---

## Expected Improvement Path

| Iteration | Category Fixed | Questions Recovered | Accuracy |
|-----------|----------------|---------------------|----------|
| 0 | Baseline | - | 63.2% |
| 1 | PERSON_RESPONSIBILITIES | +4 (Q13-16) | 67% |
| 2 | PROJECT_OWNERSHIP | +3 (Q26,30,36) | 70% |
| 3 | BU_FOCUS_AREAS | +5 (Q18-24) | 75% |
| 4 | CUSTOMER_RELATIONSHIPS | +5 (Q87-95) | 80% |
| 5 | PROJECT_BUDGETS | +3 (Q27,31,40) | 83% |
| 6 | Remaining fixes | +7 | 90% |
