import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional

from .evaluator import FuzzyEvaluator
from .vault_manager import VaultManager

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
        questions_file: Path,
        results_dir: Path,
        corpus_name: str,
        min_chunks: int = 50,
        resume: bool = True
    ) -> dict:
        """Run all questions, evaluate answers, save results. Supports resume."""
        
        stats = self.vm.get_vault_stats(vault_id)
        chunk_count = stats.get('chunk_count', 0)
        entity_count = stats.get('entity_count', 0)
        rel_count = stats.get('relationship_count', 0)
        
        print(f"  Vault stats: {chunk_count} chunks, {entity_count} entities, {rel_count} relationships")
        
        if chunk_count < min_chunks:
            raise ValueError(
                f"Only {chunk_count} chunks in vault (expected >= {min_chunks}). "
                f"Extraction likely incomplete. Aborting test."
            )
        
        questions = self._load_questions(questions_file)
        print(f"  Running {len(questions)} questions...")
        
        progress_file = self._get_progress_file(results_dir, corpus_name, vault_id)
        
        if resume:
            results, completed_ids = self._load_completed_questions(progress_file)
            if completed_ids:
                print(f"  Resuming: {len(completed_ids)} questions already answered")
        else:
            results = []
            completed_ids = set()
            if progress_file.exists():
                progress_file.unlink()
        
        passed = sum(1 for r in results if r.get('passed'))
        
        for i, q in enumerate(questions):
            q_num = q.get('id', q.get('q', i + 1))
            
            if q_num in completed_ids:
                continue
            
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('expected', ''))
            
            actual = self.vm.query(vault_id, query)
            is_pass, match_type = self.evaluator.evaluate(expected, actual)
            
            if is_pass:
                passed += 1
            
            result = {
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:80],
                "expected": expected[:80],
                "actual": actual[:100] if actual else ""
            }
            results.append(result)
            
            self._save_result_incremental(progress_file, result)
            
            status = "PASS" if is_pass else "FAIL"
            answered = len(results)
            if answered % 25 == 0:
                print(f"  [{answered}/{len(questions)}] {passed}/{answered} passed ({100*passed/answered:.1f}%)")
            elif not is_pass:
                print(f"  Q{q_num}: {status} ({match_type})")
        
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
        
        print(f"\n  Results saved to: {output_file}")
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
