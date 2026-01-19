"""
Test executor for running questions against a vault.

Handles:
- Loading questions from markdown format
- Running queries against vault
- Evaluating answers with fuzzy matching
- Saving results
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .evaluator import FuzzyEvaluator
from .vault_manager import VaultManager


def parse_question_bank(md_file: Path) -> List[dict]:
    """
    Parse markdown question bank into list of questions.
    
    Format expected:
    **Q1:** question text
    **A1:** answer text
    **Source:** source_file.md (optional)
    **Type:** SIMPLE (optional)
    
    Returns list of {id, question, expected, source, type}
    """
    content = md_file.read_text(encoding='utf-8')
    questions = []
    
    # Pattern: **Q1:** question text followed by **A1:** answer text
    # Handles multi-line answers by capturing until next **Q or end of file
    pattern = r'\*\*Q(\d+):\*\*\s*(.*?)\n\*\*A\1:\*\*\s*(.*?)(?=\n\*\*(?:Q\d+|Source|Type):|$)'
    
    for match in re.finditer(pattern, content, re.DOTALL):
        q_id = int(match.group(1))
        question = match.group(2).strip()
        answer = match.group(3).strip()
        
        # Clean up answer - remove trailing Source/Type lines if captured
        answer_lines = []
        for line in answer.split('\n'):
            if line.startswith('**Source:') or line.startswith('**Type:'):
                break
            answer_lines.append(line)
        answer = '\n'.join(answer_lines).strip()
        
        questions.append({
            "id": q_id,
            "question": question,
            "expected": answer
        })
    
    return sorted(questions, key=lambda x: x['id'])


def parse_json_questions(json_file: Path) -> List[dict]:
    """
    Parse JSON question file.
    
    Handles formats:
    - List of {question, expected_answer/expected/answer}
    - {questions: [...]} or {qa_pairs: [...]}
    """
    with open(json_file) as f:
        data = json.load(f)
    
    # Extract questions list
    if isinstance(data, list):
        items = data
    elif 'questions' in data:
        items = data['questions']
    elif 'qa_pairs' in data:
        items = data['qa_pairs']
    elif 'items' in data:
        items = data['items']
    else:
        raise ValueError(f"Unknown JSON format in {json_file}")
    
    questions = []
    for i, item in enumerate(items):
        q_id = item.get('id', item.get('q', i + 1))
        if isinstance(q_id, str) and q_id.startswith('Q'):
            q_id = int(q_id[1:])
        
        question = item.get('question', item.get('query', ''))
        expected = item.get('expected_answer', item.get('expected', item.get('answer', '')))
        
        questions.append({
            "id": q_id,
            "question": question,
            "expected": expected
        })
    
    return sorted(questions, key=lambda x: x['id'])


def load_questions(file_path: Path) -> List[dict]:
    """Load questions from file (auto-detect format)."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Questions file not found: {file_path}")
    
    if file_path.suffix.lower() == '.json':
        return parse_json_questions(file_path)
    elif file_path.suffix.lower() == '.md':
        return parse_question_bank(file_path)
    else:
        raise ValueError(f"Unknown file format: {file_path.suffix}")


class TestExecutor:
    """Run test questions against a vault."""
    
    def __init__(self, vault_manager: VaultManager, evaluator: FuzzyEvaluator = None):
        self.vault_manager = vault_manager
        self.evaluator = evaluator or FuzzyEvaluator()
    
    def run_test(
        self, 
        vault_id: str, 
        questions_file: Path,
        results_dir: Path,
        corpus_name: str,
        min_chunks: int = 50
    ) -> dict:
        """
        Run all questions, evaluate answers, save results.
        
        Args:
            vault_id: Vault to query
            questions_file: Path to questions file (MD or JSON)
            results_dir: Where to save results
            corpus_name: For labeling output
            min_chunks: Minimum chunks required (sanity check)
            
        Returns:
            Summary dict with results
        """
        
        # Sanity check: verify vault has enough data
        chunk_count = self.vault_manager.get_chunk_count(vault_id)
        print(f"  Vault has {chunk_count} chunks")
        
        if chunk_count < min_chunks:
            print(f"  ⚠ Warning: Only {chunk_count} chunks (expected >= {min_chunks})")
            print(f"  Proceeding anyway, but results may be unreliable")
        
        # Load questions
        questions = load_questions(questions_file)
        print(f"  Loaded {len(questions)} questions from {questions_file.name}")
        
        print(f"  Running {len(questions)} questions...")
        
        results = []
        passed = 0
        
        for i, q in enumerate(questions):
            q_num = q['id']
            query = q['question']
            expected = q['expected']
            
            # Query the vault
            actual = self.vault_manager.query_vault(vault_id, query)
            
            # Evaluate
            is_pass, match_type = self.evaluator.evaluate(expected, actual)
            
            if is_pass:
                passed += 1
            
            results.append({
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:50],
                "expected": expected[:50],
                "answer": actual[:60] if actual else ""
            })
            
            # Progress indicator
            status = "✓" if is_pass else "✗"
            if (i + 1) % 25 == 0 or not is_pass:
                print(f"  [{q_num}] {status} {match_type}")
        
        # Build summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = {
            "timestamp": timestamp,
            "corpus": corpus_name,
            "vault_id": vault_id,
            "chunk_count": chunk_count,
            "summary": {
                "total": len(questions),
                "passed": passed,
                "failed": len(questions) - passed,
                "accuracy_pct": round(100 * passed / len(questions), 1) if questions else 0
            },
            "breakdown": self._calculate_breakdown(results),
            "failures": [r for r in results if not r['passed']],
            "all_results": results
        }
        
        # Save results
        results_dir = Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = results_dir / f"{corpus_name}_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Also save as latest
        latest_file = results_dir / f"{corpus_name}_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n  Results saved to: {results_file}")
        
        return summary
    
    def _calculate_breakdown(self, results: List[dict]) -> dict:
        """Calculate breakdown by question range."""
        breakdown = {}
        
        ranges = [(1, 100), (101, 200), (201, 300)]
        
        for start, end in ranges:
            range_results = [r for r in results if start <= r['q'] <= end]
            if range_results:
                passed = sum(1 for r in range_results if r['passed'])
                breakdown[f"Q{start}-{end}"] = {
                    "passed": passed,
                    "total": len(range_results)
                }
        
        return breakdown
    
    def print_summary(self, summary: dict) -> None:
        """Print a formatted summary."""
        s = summary['summary']
        print(f"\n{'='*50}")
        print(f"  TEST RESULTS: {summary['corpus']}")
        print(f"{'='*50}")
        print(f"  Total:    {s['total']}")
        print(f"  Passed:   {s['passed']}")
        print(f"  Failed:   {s['failed']}")
        print(f"  Accuracy: {s['accuracy_pct']}%")
        print(f"{'='*50}")
        
        if summary.get('breakdown'):
            print("\n  Breakdown:")
            for range_name, data in summary['breakdown'].items():
                print(f"    {range_name}: {data['passed']}/{data['total']}")
        
        if summary.get('failures'):
            print(f"\n  Failed Questions ({len(summary['failures'])}):")
            for f in summary['failures'][:10]:
                print(f"    Q{f['q']}: {f['match_type']}")
            if len(summary['failures']) > 10:
                print(f"    ... and {len(summary['failures']) - 10} more")
