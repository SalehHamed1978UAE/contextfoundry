import json
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor

from .evaluator import FuzzyEvaluator
from .vault_manager import VaultManager
from .status import update_status
from .trace_logger import QuestionTraceLogger
from .persistence import (
    update_test_run_stage,
    update_test_run_progress,
    save_test_result,
    complete_test_run,
    get_answered_question_ids,
    get_test_run_progress
)
from .question_queue import (
    ensure_question_queue_schema,
    seed_questions,
    reclaim_stale_questions,
    lease_next_question,
    complete_question,
    fail_question,
    get_queue_progress,
    list_question_results,
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
        test_run_id: str = None,
        enable_tracing: bool = True,
        tree_based_retrieval: bool = None,
        parallel_workers: int = 1
    ) -> dict:
        if tree_based_retrieval is None:
            import os as _os
            tree_based_retrieval = _os.environ.get("CF_TREE_BASED_RETRIEVAL", "true").lower() == "true"
            log(f"  [executor] tree_based_retrieval default: {tree_based_retrieval} (env CF_TREE_BASED_RETRIEVAL={_os.environ.get('CF_TREE_BASED_RETRIEVAL', '<unset>')})")
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
            enable_tracing: Whether to log per-question retrieval traces (default True)
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

        parallel_workers = max(1, int(parallel_workers or 1))
        if test_run_id and parallel_workers > 1:
            log(f"  Parallel execution enabled ({parallel_workers} workers)")
            return self._run_test_parallel(
                vault_id=vault_id,
                questions=questions,
                results_dir=results_dir,
                corpus_name=corpus_name,
                test_run_id=test_run_id,
                tree_based_retrieval=tree_based_retrieval,
                parallel_workers=parallel_workers,
            )
        
        if test_run_id:
            update_test_run_stage(test_run_id, 'qa', questions_total=len(questions))
        
        progress_file = self._get_progress_file(results_dir, corpus_name, vault_id)
        
        trace_logger = None
        if enable_tracing:
            trace_dir = results_dir / "traces"
            trace_logger = QuestionTraceLogger(trace_dir, corpus_name, test_run_id or vault_id[:8])
            log(f"  Trace logging enabled: {trace_logger.trace_file}")
        
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
            expected = q.get('expected_answer', q.get('answer', q.get('expected', '')))
            category = q.get('category', q.get('type', ''))
            
            start_time = time.time()
            
            if trace_logger:
                actual, error_type, retrieval_metadata = self.vm.query(
                    vault_id, query, timeout=60, return_metadata=True, tree_based_retrieval=tree_based_retrieval
                )
            else:
                actual, error_type = self.vm.query(vault_id, query, timeout=60, tree_based_retrieval=tree_based_retrieval)
                retrieval_metadata = {}
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            if error_type == 'timeout':
                log(f"  Q{q_num}: TIMEOUT after 60s - {query[:60]}...")
                is_pass = False
                match_type = 'timeout'
                failure_reason = 'timeout'
                failure_category = 'TIMEOUT'
                expected_norm = expected
                actual_norm = ''
            elif error_type:
                is_pass = False
                match_type = 'error'
                failure_reason = error_type
                failure_category = 'ERROR'
                expected_norm = expected
                actual_norm = actual or ''
            else:
                eval_details = self.evaluator.evaluate_with_details(expected, actual)
                is_pass = eval_details['passed']
                match_type = eval_details['match_type']
                expected_norm = eval_details.get('expected_normalized', expected)
                actual_norm = eval_details.get('actual_normalized', actual or '')
                
                if not is_pass:
                    failure_classification = self.evaluator.classify_failure(expected, actual, match_type)
                    failure_reason = failure_classification.get('reason', eval_details.get('failure_reason'))
                    failure_category = failure_classification.get('category', 'MISMATCH')
                else:
                    failure_reason = None
                    failure_category = None
            
            if is_pass:
                passed += 1
            
            if trace_logger:
                trace_logger.log_question(
                    question_id=q_num,
                    question_text=query,
                    expected_answer=expected,
                    actual_answer=actual or '',
                    passed=is_pass,
                    match_type=match_type,
                    retrieval_data=retrieval_metadata,
                    duration_ms=duration_ms
                )
            
            result = {
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:200],
                "expected": expected[:200],
                "expected_normalized": expected_norm[:200] if expected_norm else '',
                "actual": actual[:500] if actual else "",
                "actual_normalized": actual_norm[:500] if actual_norm else '',
                "error_type": error_type,
                "failure_reason": failure_reason,
                "failure_category": failure_category
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
        
        trace_summary = None
        if trace_logger:
            trace_summary = trace_logger.finalize()
            log(f"  Trace summary saved to: {trace_logger.summary_file}")
            log(f"  Trace stats: avg_score={trace_summary['stats']['avg_semantic_score']:.3f}, "
                f"low_score_queries={trace_summary['stats']['low_score_queries']}")
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "corpus": corpus_name,
            "vault_id": vault_id,
            "config": {
                "tree_based_retrieval": tree_based_retrieval
            },
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
        
        if trace_summary and trace_logger:
            summary["trace_stats"] = trace_summary["stats"]
            summary["trace_file"] = str(trace_logger.trace_file)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = corpus_name.lower().replace(' ', '_')
        output_file = results_dir / f"{safe_name}_{timestamp}.json"
        
        results_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        log(f"\n  Results saved to: {output_file}")
        return summary
    
    def _run_test_parallel(
        self,
        vault_id: str,
        questions: List[Dict[str, Any]],
        results_dir: Path,
        corpus_name: str,
        test_run_id: str,
        tree_based_retrieval: bool,
        parallel_workers: int,
    ) -> Dict[str, Any]:
        """Run Q&A with per-question leasing and parallel workers."""
        ensure_question_queue_schema()
        inserted = seed_questions(test_run_id, questions)
        if inserted:
            log(f"  Seeded queue rows: {inserted}")

        worker_stop = threading.Event()
        max_attempts = 2
        lease_seconds = 180

        def process_task(vm_local: VaultManager, evaluator_local: FuzzyEvaluator, task: Dict[str, Any]) -> None:
            q = task['question'] or {}
            q_num = task['question_index']
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('answer', q.get('expected', '')))
            category = q.get('category', q.get('type', ''))
            start_time = time.time()

            try:
                actual, error_type, retrieval_metadata = vm_local.query(
                    vault_id, query, timeout=60, return_metadata=True, tree_based_retrieval=tree_based_retrieval
                )
                duration_ms = int((time.time() - start_time) * 1000)

                if error_type == 'timeout':
                    state = fail_question(task['row_id'], 'timeout', retryable=True, max_attempts=max_attempts)
                    if state == 'failed':
                        save_test_result(
                            test_run_id=test_run_id, question_id=str(q_num), question_text=query,
                            expected_answer=expected, actual_answer='', passed=False,
                            failure_reason='timeout', category=category, duration_ms=duration_ms
                        )
                    return

                if error_type:
                    state = fail_question(task['row_id'], error_type, retryable=True, max_attempts=max_attempts)
                    if state == 'failed':
                        save_test_result(
                            test_run_id=test_run_id, question_id=str(q_num), question_text=query,
                            expected_answer=expected, actual_answer=actual or '', passed=False,
                            failure_reason=error_type, category=category, duration_ms=duration_ms
                        )
                    return

                eval_details = evaluator_local.evaluate_with_details(expected, actual)
                is_pass = eval_details['passed']
                match_type = eval_details['match_type']
                failure_reason = None
                failure_category = None
                if not is_pass:
                    failure = evaluator_local.classify_failure(expected, actual, match_type)
                    failure_reason = failure.get('reason', eval_details.get('failure_reason'))
                    failure_category = failure.get('category', 'MISMATCH')

                complete_question(
                    row_id=task['row_id'],
                    actual_answer=actual or '',
                    match_type=match_type,
                    passed=is_pass,
                    failure_reason=failure_reason,
                    category=category,
                    duration_ms=duration_ms,
                    retrieval_metadata=retrieval_metadata
                )

                save_test_result(
                    test_run_id=test_run_id,
                    question_id=str(q_num),
                    question_text=query,
                    expected_answer=expected,
                    actual_answer=actual or '',
                    passed=is_pass,
                    failure_reason=failure_reason,
                    category=failure_category or category,
                    duration_ms=duration_ms
                )
            except Exception as e:
                fail_question(task['row_id'], f"worker_error: {e}", retryable=True, max_attempts=max_attempts)

        def worker_loop(worker_index: int) -> None:
            worker_id = f"w{worker_index}-{os.getpid()}"
            vm_local = VaultManager(self.vm.api)
            if not vm_local.authenticate_dev(tenant_id=vault_id):
                log(f"  [{worker_id}] authentication failed")
                return
            evaluator_local = FuzzyEvaluator()

            while not worker_stop.is_set():
                task = lease_next_question(test_run_id, worker_id, lease_seconds=lease_seconds)
                if not task:
                    prog = get_queue_progress(test_run_id)
                    if prog['pending'] == 0 and prog['running'] == 0:
                        return
                    time.sleep(0.4)
                    continue
                process_task(vm_local, evaluator_local, task)

        with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
            futures = [pool.submit(worker_loop, i + 1) for i in range(parallel_workers)]
            last_refresh = 0.0
            while True:
                reclaimed = reclaim_stale_questions(test_run_id)
                if reclaimed:
                    log(f"  Reclaimed stale leases: {reclaimed}")

                prog = get_queue_progress(test_run_id)
                total = prog['total']
                answered = prog['answered_terminal']
                passed = prog['passed']
                failed = prog['failed']
                accuracy = round(100 * passed / max(answered, 1), 1) if answered else 0.0

                if time.time() - last_refresh >= 1.0:
                    update_test_run_progress(
                        test_run_id=test_run_id,
                        questions_answered=answered,
                        questions_passed=passed,
                        questions_failed=failed,
                        current_question=None
                    )
                    update_status(
                        'qa',
                        stage_status='running',
                        qa_progress={
                            'total': total,
                            'answered': answered,
                            'passed': passed,
                            'failed': failed,
                            'accuracy_percent': accuracy
                        }
                    )
                    last_refresh = time.time()

                if prog['pending'] == 0 and prog['running'] == 0:
                    break
                time.sleep(0.5)

            worker_stop.set()
            for f in futures:
                try:
                    f.result(timeout=5)
                except Exception:
                    pass

        results = list_question_results(test_run_id)
        passed = sum(1 for r in results if r.get('passed'))
        total = len(results)
        failed = total - passed

        summary = {
            "timestamp": datetime.now().isoformat(),
            "corpus": corpus_name,
            "vault_id": vault_id,
            "config": {
                "tree_based_retrieval": tree_based_retrieval,
                "parallel_workers": parallel_workers
            },
            "vault_stats": self.vm.get_vault_stats(vault_id),
            "results": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "accuracy_pct": round(100 * passed / max(total, 1), 1)
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
