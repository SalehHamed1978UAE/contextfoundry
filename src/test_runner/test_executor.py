import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional

from .evaluator import FuzzyEvaluator
from .vault_manager import VaultManager
from .status import update_status
from .persistence import (
    update_test_run_stage,
    update_test_run_progress,
    save_test_result,
    complete_test_run,
    get_answered_question_ids,
    get_test_run_progress
)


def log(msg: str):
    """Print with immediate flush for subprocess visibility."""
    print(msg)
    sys.stdout.flush()

class TestExecutor:
    """Run test questions against a vault with resume support."""
    
    def __init__(self, vault_manager: VaultManager, evaluator: FuzzyEvaluator):
        self.vm = vault_manager
        self.evaluator = evaluator
    
    def _get_progress_file(self, results_dir: Path, corpus_name: str, vault_id: str) -> Path:
        """Get path to progress file for incremental saving."""
        safe_name = corpus_name.lower().replace(' ', '_')
        return results_dir / f"{safe_name}_{vault_id[:8]}_progress.jsonl"
    
    def _load_completed_questions(self, progress_file: Path) -> tuple[List[Dict], Set[int]]:
        """Load previously completed questions from progress file."""
        results = []
        completed_ids = set()
        
        if not progress_file.exists():
            return results, completed_ids
        
        with open(progress_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        result = json.loads(line)
                        results.append(result)
                        completed_ids.add(result.get('q'))
                    except json.JSONDecodeError:
                        continue
        
        return results, completed_ids
    
    def _save_result_incremental(self, progress_file: Path, result: Dict):
        """Append a single result to progress file immediately."""
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(progress_file, 'a') as f:
            f.write(json.dumps(result) + '\n')
    
    def run_test(
        self, 
        vault_id: str, 
        questions_file: Optional[Path] = None,
        questions_data: Optional[List[Dict]] = None,
        results_dir: Path = None,
        corpus_name: str = "",
        min_chunks: int = 50,
        resume: bool = True,
        test_run_id: str = None
    ) -> dict:
        """Run all questions, evaluate answers, save results. Supports resume.
        
        Args:
            vault_id: The vault to query against
            questions_file: Path to questions file (optional if questions_data provided)
            questions_data: List of question dicts (optional if questions_file provided)
            results_dir: Directory to save results
            corpus_name: Name of the corpus being tested
            min_chunks: Minimum chunks required in vault
            resume: Whether to resume from previous progress
            test_run_id: Database ID of the test run (for persistence)
        """
        
        stats = self.vm.get_vault_stats(vault_id)
        chunk_count = stats.get('chunk_count', 0)
        entity_count = stats.get('entity_count', 0)
        rel_count = stats.get('relationship_count', 0)
        
        log(f"  Vault stats: {chunk_count} chunks, {entity_count} entities, {rel_count} relationships")
        
        if chunk_count < min_chunks:
            raise ValueError(
                f"Only {chunk_count} chunks in vault (expected >= {min_chunks}). "
                f"Extraction likely incomplete. Aborting test."
            )
        
        if questions_data:
            questions = questions_data
        elif questions_file:
            questions = self._load_questions(questions_file)
        else:
            raise ValueError("Either questions_file or questions_data must be provided")
        log(f"  Running {len(questions)} questions...")
        
        if test_run_id:
            update_test_run_stage(test_run_id, 'qa', questions_total=len(questions))
        
        progress_file = self._get_progress_file(results_dir, corpus_name, vault_id)
        
        if resume and test_run_id:
            db_completed_ids = get_answered_question_ids(test_run_id)
            completed_ids = db_completed_ids
            results = []
            prior_progress = get_test_run_progress(test_run_id)
            prior_passed = prior_progress['passed']
            prior_answered = prior_progress['answered']
            if progress_file.exists():
                progress_file.unlink()
            if completed_ids:
                log(f"  Resuming from DB: {len(completed_ids)} questions already answered ({prior_passed} passed)")
            log(f"  Starting Q&A loop for {len(questions)} questions (skipping {len(completed_ids)} completed)...")
        elif resume:
            results, completed_ids = self._load_completed_questions(progress_file)
            prior_passed = sum(1 for r in results if r.get('passed'))
            prior_answered = len(results)
            if completed_ids:
                log(f"  Resuming: {len(completed_ids)} questions already answered")
        else:
            results = []
            completed_ids = set()
            prior_passed = 0
            prior_answered = 0
            if progress_file.exists():
                progress_file.unlink()
        
        passed = prior_passed
        
        for i, q in enumerate(questions):
            q_num = i + 1
            
            if q_num in completed_ids or str(q_num) in completed_ids:
                continue
            
            log(f"  Processing Q{q_num}/{len(questions)}...")
            
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('expected', ''))
            category = q.get('category', q.get('type', ''))
            
            start_time = time.time()
            actual, error_type = self.vm.query(vault_id, query, timeout=60)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if error_type == 'timeout':
                log(f"  Q{q_num}: TIMEOUT after 60s - {query[:60]}...")
                is_pass = False
                match_type = 'timeout'
                failure_reason = 'timeout'
            elif error_type:
                is_pass = False
                match_type = 'error'
                failure_reason = error_type
            else:
                is_pass, match_type = self.evaluator.evaluate(expected, actual)
                failure_reason = None if is_pass else match_type
            
            if is_pass:
                passed += 1
            
            result = {
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:80],
                "expected": expected[:80],
                "actual": actual[:100] if actual else "",
                "error_type": error_type
            }
            results.append(result)
            
            self._save_result_incremental(progress_file, result)
            
            answered = prior_answered + len(results)
            failed = answered - passed
            accuracy = round(100 * passed / answered, 1) if answered > 0 else 0
            
            current_q = {'id': q_num, 'text': query[:200]}
            
            if test_run_id:
                save_test_result(
                    test_run_id=test_run_id,
                    question_id=str(q_num),
                    question_text=query,
                    expected_answer=expected,
                    actual_answer=actual or '',
                    passed=is_pass,
                    failure_reason=failure_reason,
                    category=category,
                    duration_ms=duration_ms
                )
                update_test_run_progress(
                    test_run_id=test_run_id,
                    questions_answered=answered,
                    questions_passed=passed,
                    questions_failed=failed,
                    current_question=current_q
                )
            
            update_status(
                'qa',
                stage_status='running',
                qa_progress={
                    'total': len(questions),
                    'answered': answered,
                    'passed': passed,
                    'failed': failed,
                    'accuracy_percent': accuracy
                },
                current_question=current_q
            )
            
            status = "PASS" if is_pass else "FAIL"
            if answered % 25 == 0 or answered == prior_answered + 1:
                log(f"  [{answered}/{len(questions)}] {passed}/{answered} passed ({accuracy}%)")
            elif not is_pass:
                log(f"  Q{q_num}: {status} ({match_type})")
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "corpus": corpus_name,
            "vault_id": vault_id,
            "vault_stats": {
                "chunks": chunk_count,
                "entities": entity_count,
                "relationships": rel_count
            },
            "results": {
                "total": len(questions),
                "passed": passed,
                "failed": len(questions) - passed,
                "accuracy_pct": round(100 * passed / len(questions), 1)
            },
            "breakdown": self._calculate_breakdown(results),
            "failures": [r for r in results if not r['passed']],
            "all_results": results
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = corpus_name.lower().replace(' ', '_')
        output_file = results_dir / f"{safe_name}_{timestamp}.json"
        
        results_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        log(f"\n  Results saved to: {output_file}")
        return summary
    
    def _load_questions(self, questions_file: Path) -> List[Dict]:
        """Load questions from file (supports multiple formats)."""
        with open(questions_file) as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return data
        return data.get('questions', data.get('items', []))
    
    def _calculate_breakdown(self, results: List[Dict]) -> Dict:
        """Calculate breakdown by match type."""
        breakdown = {}
        for r in results:
            mt = r.get('match_type', 'unknown')
            if mt not in breakdown:
                breakdown[mt] = {"passed": 0, "failed": 0}
            if r['passed']:
                breakdown[mt]['passed'] += 1
            else:
                breakdown[mt]['failed'] += 1
        return breakdown
