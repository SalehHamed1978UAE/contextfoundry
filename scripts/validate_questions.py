#!/usr/bin/env python3
"""
Pre-validation script for question sets.

Validates that all expected answers can be found in the corpus documents
BEFORE running expensive Q&A tests. Fails fast on first missing answer.

Usage:
    python scripts/validate_questions.py --corpus "Manus Orion" --questions test_questions/orion_verified_120q.json
    python scripts/validate_questions.py --corpus "ClaudeCode Medsync" --questions test_questions/medsync_235q_v2.json
"""
import argparse
import json
import os
import sys
from pathlib import Path


def load_corpus_content(corpus_path: Path) -> str:
    """Load all text content from corpus documents."""
    content = []
    
    for root, dirs, files in os.walk(corpus_path):
        if 'question_sets' in root:
            continue
        
        for fname in files:
            if fname.endswith(('.md', '.txt', '.html', '.json', '.csv')):
                try:
                    with open(os.path.join(root, fname), 'r', encoding='utf-8', errors='ignore') as f:
                        content.append(f.read().lower())
                except Exception as e:
                    print(f"  Warning: Could not read {fname}: {e}")
    
    return '\n'.join(content)


def load_questions(questions_file: Path) -> list:
    """Load questions from JSON file."""
    with open(questions_file) as f:
        data = json.load(f)
    
    if isinstance(data, list):
        return data
    return data.get('questions', data.get('items', []))


def validate_answer(answer: str, corpus_content: str) -> tuple:
    """Check if answer can be found in corpus.
    
    Returns:
        (found: bool, match_type: str)
    """
    answer_lower = answer.lower().strip()
    
    if answer_lower in corpus_content:
        return True, 'exact'
    
    key_terms = [t for t in answer_lower.split() if len(t) > 3]
    if not key_terms:
        key_terms = answer_lower.split()
    
    matches = sum(1 for t in key_terms if t in corpus_content)
    if matches >= len(key_terms) * 0.6:
        return True, 'partial'
    
    common_variants = {
        '$': '',
        ',': '',
        'million': 'm',
        'billion': 'b',
        '%': ' percent',
        'dr.': 'dr',
        'mr.': 'mr',
        'mrs.': 'mrs',
    }
    
    normalized = answer_lower
    for old, new in common_variants.items():
        normalized = normalized.replace(old, new)
    
    if normalized in corpus_content:
        return True, 'normalized'
    
    return False, 'not_found'


def main():
    parser = argparse.ArgumentParser(description='Validate question set answers against corpus')
    parser.add_argument('--corpus', required=True, help='Corpus name (e.g., "Manus Orion")')
    parser.add_argument('--questions', required=True, help='Path to questions JSON file')
    parser.add_argument('--corpus-path', help='Override corpus path (default: "test documents/<corpus>/")')
    parser.add_argument('--continue-on-error', action='store_true', help='Continue validation after first error')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all questions, not just failures')
    
    args = parser.parse_args()
    
    corpus_path = Path(args.corpus_path) if args.corpus_path else Path(f"test documents/{args.corpus}")
    questions_file = Path(args.questions)
    
    if not corpus_path.exists():
        print(f"ERROR: Corpus path not found: {corpus_path}")
        sys.exit(1)
    
    if not questions_file.exists():
        print(f"ERROR: Questions file not found: {questions_file}")
        sys.exit(1)
    
    print(f"Validating questions for corpus: {args.corpus}")
    print(f"  Corpus path: {corpus_path}")
    print(f"  Questions file: {questions_file}")
    print()
    
    print("Loading corpus content...")
    corpus_content = load_corpus_content(corpus_path)
    print(f"  Loaded {len(corpus_content):,} characters from corpus")
    
    print("Loading questions...")
    questions = load_questions(questions_file)
    print(f"  Loaded {len(questions)} questions")
    print()
    
    print("Validating answers...")
    print("-" * 60)
    
    found_count = 0
    not_found = []
    
    for i, q in enumerate(questions):
        q_id = q.get('id', i + 1)
        question = q.get('question', q.get('query', ''))[:60]
        expected = q.get('expected_answer', q.get('answer', q.get('expected', '')))
        
        found, match_type = validate_answer(expected, corpus_content)
        
        if found:
            found_count += 1
            if args.verbose:
                print(f"  Q{q_id}: OK ({match_type})")
        else:
            not_found.append({
                'id': q_id,
                'question': question,
                'expected': expected
            })
            print(f"  Q{q_id}: NOT FOUND")
            print(f"       Question: {question}...")
            print(f"       Expected: {expected[:80]}")
            print()
            
            if not args.continue_on_error:
                print("-" * 60)
                print(f"VALIDATION FAILED: Answer not found in corpus")
                print(f"  Question {q_id}: {question}")
                print(f"  Expected answer: {expected}")
                print()
                print("Fix the question set before running tests.")
                print("Use --continue-on-error to see all failures.")
                sys.exit(1)
    
    print("-" * 60)
    print()
    print(f"VALIDATION RESULTS:")
    print(f"  Total questions: {len(questions)}")
    print(f"  Found: {found_count}")
    print(f"  Not found: {len(not_found)}")
    print(f"  Match rate: {100 * found_count / len(questions):.1f}%")
    
    if not_found:
        print()
        print(f"FAILED: {len(not_found)} answers not found in corpus")
        
        report_file = questions_file.parent / f"{questions_file.stem}_validation_failures.json"
        with open(report_file, 'w') as f:
            json.dump({
                'corpus': args.corpus,
                'questions_file': str(questions_file),
                'total': len(questions),
                'found': found_count,
                'not_found': not_found
            }, f, indent=2)
        print(f"  Failure report: {report_file}")
        sys.exit(1)
    else:
        print()
        print("SUCCESS: All answers found in corpus!")
        sys.exit(0)


if __name__ == '__main__':
    main()
