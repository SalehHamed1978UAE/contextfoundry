#!/usr/bin/env python3
"""Validate that all expected answers exist in the corpus."""

import json
import sys
import re
from pathlib import Path
from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_questions(questions_file: str, corpus_dir: str) -> Tuple[List, List]:
    """
    Validate each question's expected answer exists in corpus.

    Returns:
        - missing: list of (question_id, question, expected_answer) for missing answers
        - found: list of (question_id, question, expected_answer) for found answers
    """
    with open(questions_file) as f:
        questions = json.load(f)

    corpus_path = Path(corpus_dir)
    corpus_text = ""
    file_count = 0
    
    for file_path in corpus_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.md', '.txt', '.json', '.csv', '.html']:
            try:
                corpus_text += file_path.read_text(errors='ignore') + "\n"
                file_count += 1
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")

    logger.info(f"Loaded {file_count} files from corpus ({len(corpus_text):,} characters)")
    corpus_lower = corpus_text.lower()

    missing = []
    found = []
    
    for q in questions:
        qid = q.get('id', 0)
        question = q.get('question', '')
        expected = q.get('expected_answer', '')

        if _answer_exists_in_corpus(expected, corpus_lower):
            found.append((qid, question, expected))
        else:
            missing.append((qid, question, expected))

    return missing, found


def _answer_exists_in_corpus(expected: str, corpus_lower: str) -> bool:
    """Check if expected answer exists in corpus."""
    if not expected:
        return True
    
    expected_lower = expected.lower()
    
    if "[not in documents]" in expected_lower or "can be inferred" in expected_lower:
        return True

    if expected_lower in corpus_lower:
        return True

    components = re.split(r'[,|]|\s+and\s+', expected_lower)
    components = [c.strip() for c in components if len(c.strip()) > 3]

    if components:
        found = sum(1 for c in components if c in corpus_lower)
        if found >= len(components) * 0.6:
            return True

    numbers = re.findall(r'\d+(?:\.\d+)?', expected_lower)
    if numbers:
        found_nums = sum(1 for n in numbers if n in corpus_lower)
        if found_nums >= len(numbers) * 0.7:
            return True

    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_questions.py <questions.json> [corpus_dir]")
        print("\nIf corpus_dir not specified, uses the default for the corpus name in questions file")
        sys.exit(1)

    questions_file = sys.argv[1]
    
    if len(sys.argv) >= 3:
        corpus_dir = sys.argv[2]
    else:
        if 'orion' in questions_file.lower():
            corpus_dir = "test documents/Manus Orion"
        elif 'medsync' in questions_file.lower():
            corpus_dir = "test_documents/manus_medsync"
        else:
            print("Could not determine corpus directory. Please specify explicitly.")
            sys.exit(1)

    logger.info(f"Validating: {questions_file}")
    logger.info(f"Against corpus: {corpus_dir}")
    
    missing, found = validate_questions(questions_file, corpus_dir)

    print(f"\n{'='*70}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*70}")
    print(f"Total questions: {len(missing) + len(found)}")
    print(f"Found in corpus: {len(found)} ({100*len(found)/(len(found)+len(missing)):.1f}%)")
    print(f"NOT in corpus:   {len(missing)} ({100*len(missing)/(len(found)+len(missing)):.1f}%)")
    
    if missing:
        print(f"\n{'='*70}")
        print("QUESTIONS WITH ANSWERS NOT FOUND IN CORPUS:")
        print(f"{'='*70}")
        for qid, question, expected in missing[:20]:
            print(f"\n  Q{qid}: {question}")
            print(f"       Expected: {expected[:80]}{'...' if len(expected) > 80 else ''}")
        
        if len(missing) > 20:
            print(f"\n  ... and {len(missing) - 20} more")
        
        sys.exit(1)
    else:
        print("\nAll expected answers found in corpus!")
        sys.exit(0)


if __name__ == "__main__":
    main()
