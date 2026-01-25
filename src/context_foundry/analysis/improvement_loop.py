"""
Improvement Loop for Context Foundry.

Orchestrates the failure analysis, targeted extraction, and fix application cycle
to systematically improve accuracy toward a target.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .failure_analyzer import FailureAnalyzer, FailureReport
from .targeted_extractor import TargetedExtractor
from .fix_applier import FixApplier, FixResult

logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    """Result of a single improvement iteration."""
    iteration: int
    categories_processed: List[str]
    questions_before: int
    questions_fixed: int
    fix_results: List[FixResult]
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "categories_processed": self.categories_processed,
            "questions_before": self.questions_before,
            "questions_fixed": self.questions_fixed,
            "fix_results": [r.to_dict() for r in self.fix_results],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class LoopSummary:
    """Summary of the entire improvement loop."""
    iterations: int
    starting_accuracy: float
    final_accuracy: float
    target_accuracy: float
    target_met: bool
    total_fixes: int
    iteration_results: List[IterationResult]
    started_at: datetime
    completed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iterations": self.iterations,
            "starting_accuracy": self.starting_accuracy,
            "final_accuracy": self.final_accuracy,
            "target_accuracy": self.target_accuracy,
            "target_met": self.target_met,
            "total_fixes": self.total_fixes,
            "iteration_results": [r.to_dict() for r in self.iteration_results],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
        }


class ImprovementLoop:
    """
    Orchestrates the improvement loop:
    1. Load test results
    2. Analyze failures with FailureAnalyzer
    3. Group by pattern
    4. Run targeted extraction for top categories
    5. Apply fixes with FixApplier
    6. Save progress and stats
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        self.corpus_dir = self.config.get("corpus_dir", "test documents/Manus Orion/documents/")
        self.extraction_dir = self.config.get("extraction_dir", "extraction_outputs/manus_orion/")
        self.output_dir = self.config.get("output_dir", "/tmp/improvement_loop")
        self.target_accuracy = self.config.get("target_accuracy", 0.90)
        self.max_iterations = self.config.get("max_iterations", 10)
        self.categories_per_iteration = self.config.get("categories_per_iteration", 2)
        self.tenant_id = self.config.get("tenant_id")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        self.analyzer = FailureAnalyzer({
            "corpus_dir": self.corpus_dir,
            "extraction_dir": self.extraction_dir,
            "tenant_id": self.tenant_id
        })

        self.extractor = TargetedExtractor({
            "openai_api_key": self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY"),
            "model": self.config.get("model", "gpt-4o")
        })

        self.fix_applier = FixApplier({
            "tenant_id": self.tenant_id
        })

        self._documents: Optional[List[Dict]] = None

    def _load_documents(self) -> List[Dict]:
        """Load corpus documents if not already loaded."""
        if self._documents is None:
            self._documents = TargetedExtractor.load_corpus_documents(self.corpus_dir)
        return self._documents

    def run(self, test_results_path: str, documents: Optional[List[Dict]] = None) -> LoopSummary:
        """
        Run the improvement loop.

        Args:
            test_results_path: Path to test results JSON
            documents: Optional list of documents (loaded from corpus_dir if not provided)

        Returns:
            LoopSummary with all iteration results
        """
        started_at = datetime.utcnow()
        
        if documents:
            self._documents = documents
        else:
            self._load_documents()

        with open(test_results_path) as f:
            test_results = json.load(f)

        failures = test_results.get("failures", [])
        total_questions = test_results.get("results", {}).get("total", 106)
        passed = test_results.get("results", {}).get("passed", 0)
        starting_accuracy = passed / total_questions if total_questions > 0 else 0

        logger.info(f"Starting improvement loop: {len(failures)} failures, {starting_accuracy:.1%} accuracy")

        iteration_results: List[IterationResult] = []
        current_failures = failures
        current_accuracy = starting_accuracy
        total_fixes = 0

        for iteration in range(1, self.max_iterations + 1):
            if current_accuracy >= self.target_accuracy:
                logger.info(f"Target accuracy {self.target_accuracy:.1%} reached!")
                break

            if not current_failures:
                logger.info("No more failures to process")
                break

            logger.info(f"\n=== Iteration {iteration} ===")
            logger.info(f"Current failures: {len(current_failures)}")

            iteration_result = self._run_iteration(
                iteration=iteration,
                failures=current_failures
            )
            iteration_results.append(iteration_result)
            total_fixes += iteration_result.questions_fixed

            self._save_iteration_result(iteration_result)

            logger.info(f"Iteration {iteration} complete: {iteration_result.questions_fixed} fixes applied")

        completed_at = datetime.utcnow()

        passed_after = passed + total_fixes
        final_accuracy = passed_after / total_questions if total_questions > 0 else 0

        summary = LoopSummary(
            iterations=len(iteration_results),
            starting_accuracy=starting_accuracy,
            final_accuracy=final_accuracy,
            target_accuracy=self.target_accuracy,
            target_met=final_accuracy >= self.target_accuracy,
            total_fixes=total_fixes,
            iteration_results=iteration_results,
            started_at=started_at,
            completed_at=completed_at
        )

        self._save_summary(summary)

        return summary

    def _run_iteration(self, iteration: int, failures: List[Dict]) -> IterationResult:
        """Run a single iteration of the improvement loop."""
        result = IterationResult(
            iteration=iteration,
            categories_processed=[],
            questions_before=len(failures),
            questions_fixed=0,
            fix_results=[]
        )

        reports = self.analyzer.analyze_all_failures(failures)

        fix_plan = self.analyzer.generate_fix_plan(reports)
        self._save_analysis(reports, fix_plan, iteration)

        top_categories = fix_plan.get("priority_order", [])[:self.categories_per_iteration]
        
        extractable_categories = [c for c in top_categories if c in [
            "PERSON_RESPONSIBILITIES", "PROJECT_OWNERSHIP", "BU_FOCUS_AREAS",
            "CUSTOMER_RELATIONSHIPS", "PROJECT_BUDGETS", "SUPPLIER_RELATIONSHIPS",
            "PARTNER_RELATIONSHIPS", "PROJECT_INFO", "PERSON_INFO"
        ]]

        if not extractable_categories:
            logger.warning("No extractable categories found in top priorities")
            result.completed_at = datetime.utcnow()
            return result

        documents = self._load_documents()

        for category in extractable_categories:
            logger.info(f"Processing category: {category}")
            result.categories_processed.append(category)

            extractions = self.extractor.extract_for_category(category, documents)
            
            if extractions:
                self._save_extractions(category, extractions, iteration)

                fix_result = self.fix_applier.apply_all(category, extractions)
                result.fix_results.append(fix_result)

                questions_for_category = len([
                    r for r in reports 
                    if r.fix_category == category
                ])
                result.questions_fixed += min(
                    questions_for_category,
                    fix_result.entities_updated + fix_result.relationships_created + fix_result.properties_added
                )

                logger.info(f"Category {category}: {fix_result.entities_created} entities, "
                           f"{fix_result.relationships_created} relationships, "
                           f"{fix_result.properties_added} properties")

        result.completed_at = datetime.utcnow()
        return result

    def _save_analysis(self, reports: List[FailureReport], fix_plan: Dict, iteration: int):
        """Save analysis results for an iteration."""
        output_path = Path(self.output_dir) / f"iteration_{iteration}_analysis.json"
        
        data = {
            "iteration": iteration,
            "total_failures": len(reports),
            "fix_plan": fix_plan,
            "reports": [r.to_dict() for r in reports]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved analysis to {output_path}")

    def _save_extractions(self, category: str, extractions: List[Dict], iteration: int):
        """Save extraction results for a category."""
        output_path = Path(self.output_dir) / f"iteration_{iteration}_{category.lower()}_extractions.json"
        
        with open(output_path, 'w') as f:
            json.dump({
                "category": category,
                "iteration": iteration,
                "count": len(extractions),
                "extractions": extractions
            }, f, indent=2)

        logger.info(f"Saved {len(extractions)} extractions to {output_path}")

    def _save_iteration_result(self, result: IterationResult):
        """Save iteration result."""
        output_path = Path(self.output_dir) / f"iteration_{result.iteration}_result.json"
        
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        logger.info(f"Saved iteration result to {output_path}")

    def _save_summary(self, summary: LoopSummary):
        """Save the loop summary."""
        output_path = Path(self.output_dir) / "loop_summary.json"
        
        with open(output_path, 'w') as f:
            json.dump(summary.to_dict(), f, indent=2)

        logger.info(f"Saved loop summary to {output_path}")

    def analyze_only(self, test_results_path: str) -> Dict:
        """
        Run analysis only without applying fixes.
        
        Useful for understanding failure patterns before running the full loop.
        """
        failures = FailureAnalyzer.load_test_results(test_results_path)
        
        reports = self.analyzer.analyze_all_failures(failures)
        fix_plan = self.analyzer.generate_fix_plan(reports)

        output_path = Path(self.output_dir) / "failure_analysis.json"
        self.analyzer.save_analysis(reports, str(output_path))

        return fix_plan

    def close(self):
        """Clean up resources."""
        self.fix_applier.close()
