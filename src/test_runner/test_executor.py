import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .evaluator import FuzzyEvaluator
from .vault_manager import VaultManager

class TestExecutor:
    """Run test questions against a vault."""
    
    def __init__(self, vault_manager: VaultManager, evaluator: FuzzyEvaluator):
        self.vm = vault_manager
        self.evaluator = evaluator
    
    def run_test(
        self, 
        vault_id: str, 
        questions_file: Path,
        results_dir: Path,
        corpus_name: str,
        min_chunks: int = 50
    ) -> dict:
        """Run all questions, evaluate answers, save results."""
        
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
        
        results = []
        passed = 0
        
        for i, q in enumerate(questions):
            q_num = q.get('id', q.get('q', i + 1))
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('expected', ''))
            
            actual = self.vm.query(vault_id, query)
            is_pass, match_type = self.evaluator.evaluate(expected, actual)
            
            if is_pass:
                passed += 1
            
            results.append({
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:80],
                "expected": expected[:80],
                "actual": actual[:100] if actual else ""
            })
            
            status = "PASS" if is_pass else "FAIL"
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(questions)}] {passed}/{i+1} passed ({100*passed/(i+1):.1f}%)")
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
