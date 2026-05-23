#!/usr/bin/env python3
"""
Corpus Evaluation Harness for Context Foundry

Loads a test corpus, ingests documents, runs Q&A evaluation,
and scores results against expected answers.

Usage:
    python eval_corpus.py nexus     # Run Nexus Industries (100 docs, 100 Q)
    python eval_corpus.py horizon   # Run Horizon Nexus (204 docs, 345 Q)
    python eval_corpus.py medsync   # Run MedSync (100 docs, 200 Q)
    python eval_corpus.py nexus --skip-ingest   # Skip ingestion, just run eval
    python eval_corpus.py nexus --extract       # Also run entity extraction
    python eval_corpus.py nexus --sample 20     # Only run 20 random questions
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
import httpx
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

API_BASE = "http://localhost:8000"
TIMEOUT = 120.0  # seconds per query

# Corpus configurations
CORPORA = {
    "nexus": {
        "name": "Nexus Industries",
        "docs_dir": os.path.expanduser("~/Downloads/ClaudeCode_NExus_Industries_corpus 2/All docs"),
        "qa_file": os.path.expanduser("~/Downloads/ClaudeCode_NExus_Industries_corpus 2/nexus_100q.json"),
        "qa_format": "json_questions",  # {questions: [{id, question, expected_answer}]}
        "doc_type": "corporate_document",
    },
    "horizon": {
        "name": "Horizon Nexus",
        "docs_dir": os.path.expanduser("~/Downloads/Codex Horizon_Nexus/docs"),
        "qa_file": os.path.expanduser("~/Downloads/Codex Horizon_Nexus/horizon_nexus_qa.json"),
        "qa_format": "json_array",  # [{id, question, expected_answer}]
        "doc_type": "corporate_document",
    },
    "medsync": {
        "name": "MedSync Health",
        "docs_dir": os.path.expanduser("~/Downloads/Manus Medsync/documents"),
        "qa_file": os.path.expanduser("~/Downloads/Manus Medsync/qa_test_set.md"),
        "qa_format": "markdown_qa",  # Markdown with ### Q1, **Question:**, **Answer:**
        "doc_type": "healthcare_document",
    },
}


def load_documents(docs_dir: str) -> list:
    """Load all .md documents from a directory"""
    docs = []
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        print(f"ERROR: Documents directory not found: {docs_dir}")
        sys.exit(1)

    for md_file in sorted(docs_path.glob("**/*.md")):
        # Skip "All docs" subfolder when loading from a parent directory
        # (contains duplicates of subfolder docs in Horizon corpus)
        # But don't skip if "All docs" IS the docs_dir itself
        if "All docs" in str(md_file) and "All docs" not in str(docs_path):
            continue
        content = md_file.read_text(encoding="utf-8", errors="replace")
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, md_file.name))
        docs.append({
            "id": doc_id,
            "title": md_file.stem.replace("_", " ").replace("-", " "),
            "type": "document",
            "content": content,
            "filename": md_file.name,
        })

    return docs


def load_qa_json_questions(qa_file: str) -> list:
    """Load Q&A from Nexus format: {questions: [{id, question, expected_answer}]}"""
    with open(qa_file) as f:
        data = json.load(f)
    questions = data.get("questions", data if isinstance(data, list) else [])
    return [
        {
            "id": q["id"],
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "category": q.get("category", ""),
            "difficulty": q.get("difficulty", ""),
        }
        for q in questions
    ]


def load_qa_json_array(qa_file: str) -> list:
    """Load Q&A from simple JSON array: [{id, question, expected_answer}]"""
    with open(qa_file) as f:
        data = json.load(f)
    return [
        {
            "id": q["id"],
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "category": q.get("category", ""),
            "difficulty": q.get("difficulty", ""),
        }
        for q in data
    ]


def load_qa_markdown(qa_file: str) -> list:
    """Load Q&A from MedSync markdown format"""
    with open(qa_file) as f:
        content = f.read()

    questions = []
    # Split by ### Q\d+
    blocks = re.split(r'### Q(\d+)', content)

    # blocks[0] is header, then alternating: id, block_text
    for i in range(1, len(blocks) - 1, 2):
        q_id = int(blocks[i])
        block = blocks[i + 1]

        # Extract question and answer
        q_match = re.search(r'\*\*Question:\*\*\s*(.+?)(?:\n|$)', block)
        a_match = re.search(r'\*\*Answer:\*\*\s*(.+?)(?:\n|$)', block)

        if q_match and a_match:
            # Extract optional metadata
            type_match = re.search(r'\*\*Type:\*\*\s*(\w+)', block)
            diff_match = re.search(r'\*\*Difficulty:\*\*\s*(\w+)', block)

            questions.append({
                "id": q_id,
                "question": q_match.group(1).strip(),
                "expected_answer": a_match.group(1).strip(),
                "category": type_match.group(1) if type_match else "",
                "difficulty": diff_match.group(1) if diff_match else "",
            })

    return questions


def load_questions(qa_file: str, qa_format: str) -> list:
    """Load questions based on format"""
    loaders = {
        "json_questions": load_qa_json_questions,
        "json_array": load_qa_json_array,
        "markdown_qa": load_qa_markdown,
    }
    loader = loaders.get(qa_format)
    if not loader:
        print(f"ERROR: Unknown QA format: {qa_format}")
        sys.exit(1)
    return loader(qa_file)


def score_answer(actual: str, expected: str, question: str = "") -> dict:
    """
    Score an answer against expected answer.
    Uses multiple strategies with increasing leniency.
    Returns dict with pass/fail, score, and reason.
    """
    actual_lower = actual.lower().strip()
    expected_lower = expected.lower().strip()
    question_lower = question.lower().strip()

    # ── 0. SPECIAL EXPECTED ANSWER PATTERNS ──

    # 0a. "[Answer depends on document content]" — unscorable by design.
    # Pass if system returned a substantive answer (not "no info").
    if "answer depends on document content" in expected_lower:
        no_info_phrases = ["does not provide", "not found", "no information",
                           "cannot determine", "not mentioned", "not specified",
                           "not contain", "not available", "not explicitly"]
        if any(p in actual_lower for p in no_info_phrases):
            return {"pass": False, "score": 0.0, "reason": "policy_no_answer"}
        if len(actual.strip()) > 20:
            return {"pass": True, "score": 0.80, "reason": "policy_answered"}
        return {"pass": False, "score": 0.0, "reason": "policy_empty"}

    # 0b. "[NOT IN DOCUMENTS]" — trick question. Pass if system correctly says not found.
    if "not in documents" in expected_lower:
        not_found_phrases = ["does not provide", "not found", "no information",
                             "cannot determine", "not mentioned", "not specified",
                             "not contain", "not available", "not explicitly",
                             "not provided", "no context", "insufficient"]
        if any(p in actual_lower for p in not_found_phrases):
            return {"pass": True, "score": 1.0, "reason": "trick_correct_reject"}
        return {"pass": False, "score": 0.0, "reason": "trick_hallucinated"}

    # ── 1. NO-INFO DETECTION (check early, but allow later stages to override) ──
    no_info_phrases = ["does not provide", "not found", "no information", "insufficient",
                       "cannot determine", "not mentioned", "no context", "not specified",
                       "not contain", "not available", "not explicitly"]
    is_no_info = any(phrase in actual_lower for phrase in no_info_phrases)

    # ── 2. EXACT SUBSTRING MATCH ──
    if expected_lower in actual_lower:
        return {"pass": True, "score": 1.0, "reason": "exact_match"}

    # ── 3. TIMELINE FORMAT MATCHING ──
    # "2024-2027" should match "from 2024 to 2027"
    timeline_match = re.match(r'^(\d{4})\s*[-–—]\s*(\d{4})$', expected_lower.strip())
    if timeline_match:
        y1, y2 = timeline_match.groups()
        patterns = [
            f"from {y1} to {y2}",
            f"{y1} to {y2}",
            f"{y1} through {y2}",
            f"{y1} - {y2}",
            f"{y1}–{y2}",
            f"{y1}—{y2}",
        ]
        if any(p in actual_lower for p in patterns):
            return {"pass": True, "score": 1.0, "reason": "timeline_match"}

    # ── 4. "NAME ONE" MATCHING ──
    # If question says "name one/a" and expected has comma-separated list,
    # pass if actual contains ANY single item from the list
    is_name_one = bool(re.search(r'\bname\s+(one|a|an|any)\b', question_lower))
    if is_name_one and (',' in expected_lower or ' or ' in expected_lower):
        items = re.split(r'[,;]|\bor\b|\band\b', expected_lower)
        items = [item.strip() for item in items if len(item.strip()) > 1]
        for item in items:
            if item in actual_lower:
                return {"pass": True, "score": 1.0, "reason": "name_one_match"}
            # Also check each significant word from the item
            item_words = [w for w in item.split() if len(w) > 2]
            if item_words and all(w in actual_lower for w in item_words):
                return {"pass": True, "score": 0.95, "reason": "name_one_words"}

    # ── 5. ALTERNATIVE ANSWERS ──
    # Handle "X (or Y)" or "X or Y" or "X, ramping to Y"
    alternatives = [expected_lower]
    paren_matches = re.findall(r'\(([^)]+)\)', expected_lower)
    for pm in paren_matches:
        alternatives.append(pm.strip())
        if pm.strip().startswith('or '):
            alternatives.append(pm.strip()[3:])
    base_text = re.sub(r'\s*\([^)]*\)', '', expected_lower).strip()
    if base_text != expected_lower:
        alternatives.append(base_text)
    if ' or ' in expected_lower:
        for part in expected_lower.split(' or '):
            alternatives.append(part.strip())

    for alt in alternatives:
        if alt and alt in actual_lower:
            return {"pass": True, "score": 1.0, "reason": "alternative_match"}

    # ── 6. NORMALIZE AND COMPARE ──
    number_words = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
                    'eleven': '11', 'twelve': '12', 'twenty': '20', 'thirty': '30',
                    'forty': '40', 'fifty': '50', 'hundred': '100'}

    def normalize(s):
        s = re.sub(r'[,$%\.\s\(\)\-–—]', '', s.lower())
        for word, num in number_words.items():
            s = s.replace(word, num)
        return s

    for alt in alternatives:
        if alt and normalize(alt) in normalize(actual):
            return {"pass": True, "score": 1.0, "reason": "normalized_match"}

    # ── 7. EXTRACT KEY FACTS ──
    def extract_numbers(text):
        """Extract all numbers from text, normalized"""
        nums = set()
        for m in re.finditer(r'[\d,]+\.?\d*', text):
            nums.add(m.group().replace(',', ''))
        return nums

    def extract_significant_words(text):
        """Extract significant words (likely proper nouns, technical terms)"""
        stop = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
                'had', 'has', 'was', 'one', 'our', 'out', 'its', 'with', 'that',
                'this', 'from', 'they', 'been', 'have', 'will', 'each', 'which',
                'their', 'about', 'would', 'there', 'these', 'other', 'into', 'more',
                'also', 'than', 'then', 'some', 'what', 'only', 'does', 'most',
                'plus', 'formerly', 'currently', 'approximately', 'around', 'total',
                'full', 'per', 'initially', 'ramping', 'year', 'vs', 'answer',
                'depends', 'document', 'content', 'provided', 'context'}
        words = set()
        for w in re.findall(r'[a-zA-Z][a-zA-Z\-]+', text):
            if len(w) > 2 and w.lower() not in stop:
                words.add(w.lower())
        return words

    expected_nums = extract_numbers(expected)
    actual_nums = extract_numbers(actual)
    expected_words = extract_significant_words(expected)
    actual_words = extract_significant_words(actual)

    # ── 8. CLOSE NUMERIC MATCHING ──
    # 6.67% ≈ 6.7%, 28.1% ≈ 28.0%, handle rounding
    if expected_nums and not is_no_info:
        def nums_close(a_str, b_str, tolerance=0.02):
            """Check if two number strings are close (within tolerance ratio)"""
            try:
                a, b = float(a_str), float(b_str)
                if b == 0:
                    return a == 0
                return abs(a - b) / max(abs(b), 1) <= tolerance
            except ValueError:
                return False

        close_matches = 0
        exact_matches = expected_nums & actual_nums
        close_matches = len(exact_matches)
        for en in expected_nums - actual_nums:
            for an in actual_nums:
                if nums_close(en, an):
                    close_matches += 1
                    break

        if close_matches >= 1:
            num_ratio = close_matches / len(expected_nums)
            word_matches = sum(1 for w in expected_words if w in actual_words or
                               any(w in aw or aw in w for aw in actual_words))
            word_ratio = word_matches / max(len(expected_words), 1)
            combined = (num_ratio * 0.6 + word_ratio * 0.4)
            if combined >= 0.35:
                return {"pass": True, "score": combined,
                        "reason": f"nums_{close_matches}/{len(expected_nums)}_words_{word_matches}/{len(expected_words)}"}

    # ── 9. WORD OVERLAP FOR NAME/TERM ANSWERS ──
    if expected_words and not is_no_info:
        word_matches = sum(1 for w in expected_words if w in actual_words or
                           any(w in aw or aw in w for aw in actual_words))
        ratio = word_matches / len(expected_words)
        if ratio >= 0.5:
            return {"pass": True, "score": ratio,
                    "reason": f"word_overlap_{word_matches}/{len(expected_words)}"}

    # ── 10. CORE WORDS CHECK ──
    core_words = [w for w in expected_lower.split() if len(w) > 3 and
                  w not in {'the', 'and', 'for', 'with', 'from', 'that', 'this',
                            'answer', 'depends', 'document', 'content'}]
    if len(core_words) <= 3 and core_words:
        matches = sum(1 for w in core_words if w in actual_lower)
        if matches == len(core_words):
            return {"pass": True, "score": 0.85, "reason": "core_words_present"}

    # ── 11. FUZZY SEQUENCE MATCH ──
    similarity = SequenceMatcher(None, actual_lower[:500], expected_lower).ratio()
    if similarity >= 0.50:
        return {"pass": True, "score": similarity, "reason": f"fuzzy_{similarity:.2f}"}

    # ── 12. FINAL NO-INFO CHECK ──
    if is_no_info:
        return {"pass": False, "score": 0.0, "reason": "no_info_found"}

    return {"pass": False, "score": similarity, "reason": f"no_match_{similarity:.2f}"}


def reset_database(client: httpx.Client):
    """Reset all data in the system"""
    print("\n  Resetting database...")
    resp = client.post(f"{API_BASE}/admin/reset", timeout=30.0)
    if resp.status_code != 200:
        print(f"  ERROR: Reset failed: {resp.text}")
        sys.exit(1)
    print("  Database reset complete.")


def ingest_documents(client: httpx.Client, documents: list, batch_size: int = 10):
    """Ingest documents in batches"""
    total = len(documents)
    total_chunks = 0
    total_embeddings = 0
    errors = []

    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]
        batch_payload = [
            {"id": d["id"], "title": d["title"], "type": d["type"], "content": d["content"]}
            for d in batch
        ]

        print(f"  Ingesting batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size} "
              f"({len(batch)} docs)...")

        try:
            resp = client.post(
                f"{API_BASE}/admin/ingest",
                json={"documents": batch_payload},
                timeout=300.0  # 5 min for batch
            )
            if resp.status_code == 200:
                result = resp.json()
                total_chunks += result.get("total_chunks", 0)
                total_embeddings += result.get("total_embeddings", 0)
                if result.get("errors"):
                    errors.extend(result["errors"])
            else:
                print(f"    ERROR: {resp.status_code}: {resp.text[:200]}")
                errors.append({"batch": i, "error": resp.text[:200]})
        except Exception as e:
            print(f"    ERROR: {e}")
            errors.append({"batch": i, "error": str(e)})

    return {
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "errors": errors,
    }


def run_extraction(client: httpx.Client, documents: list, batch_size: int = 5):
    """Run entity extraction in batches"""
    total = len(documents)
    total_entities = 0
    total_relationships = 0

    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]
        batch_payload = [
            {"id": d["id"], "type": d["type"], "content": d["content"]}
            for d in batch
        ]

        print(f"  Extracting batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...")

        try:
            resp = client.post(
                f"{API_BASE}/admin/extract",
                json={"documents": batch_payload},
                timeout=600.0  # 10 min per batch
            )
            if resp.status_code == 200:
                result = resp.json()
                total_entities += result.get("total_entities", 0)
                total_relationships += result.get("total_relationships", 0)
        except Exception as e:
            print(f"    ERROR: {e}")

    return {
        "total_entities": total_entities,
        "total_relationships": total_relationships,
    }


def run_evaluation(client: httpx.Client, questions: list) -> list:
    """Run all evaluation questions and collect results"""
    results = []

    for i, q in enumerate(questions):
        q_id = q["id"]
        question = q["question"]
        expected = q["expected_answer"]

        print(f"  [{i + 1}/{len(questions)}] Q{q_id}: {question[:80]}...")

        try:
            start = time.time()
            resp = client.post(
                f"{API_BASE}/query",
                json={"query": question},
                timeout=TIMEOUT
            )
            elapsed = time.time() - start

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("response"):
                    actual_answer = data["response"]["answer"]
                    confidence = data["response"]["confidence"]

                    # Score
                    score_result = score_answer(actual_answer, expected, question)

                    status = "PASS" if score_result["pass"] else "FAIL"
                    print(f"    {status} (score={score_result['score']:.2f}, "
                          f"conf={confidence:.2f}, {elapsed:.1f}s) "
                          f"[{score_result['reason']}]")

                    if not score_result["pass"]:
                        print(f"    Expected: {expected}")
                        print(f"    Got:      {actual_answer[:200]}")

                    results.append({
                        "q_id": q_id,
                        "question": question,
                        "expected": expected,
                        "actual": actual_answer,
                        "confidence": confidence,
                        "pass": score_result["pass"],
                        "score": score_result["score"],
                        "reason": score_result["reason"],
                        "latency_s": elapsed,
                        "category": q.get("category", ""),
                        "difficulty": q.get("difficulty", ""),
                    })
                else:
                    error = data.get("error", {}).get("message", "Unknown error")
                    print(f"    ERROR: {error}")
                    results.append({
                        "q_id": q_id, "question": question, "expected": expected,
                        "actual": f"ERROR: {error}", "confidence": 0, "pass": False,
                        "score": 0, "reason": "api_error", "latency_s": elapsed,
                        "category": q.get("category", ""), "difficulty": q.get("difficulty", ""),
                    })
            else:
                print(f"    HTTP ERROR: {resp.status_code}")
                results.append({
                    "q_id": q_id, "question": question, "expected": expected,
                    "actual": f"HTTP {resp.status_code}", "confidence": 0, "pass": False,
                    "score": 0, "reason": f"http_{resp.status_code}", "latency_s": 0,
                    "category": q.get("category", ""), "difficulty": q.get("difficulty", ""),
                })

        except httpx.TimeoutException:
            print(f"    TIMEOUT after {TIMEOUT}s")
            results.append({
                "q_id": q_id, "question": question, "expected": expected,
                "actual": "TIMEOUT", "confidence": 0, "pass": False,
                "score": 0, "reason": "timeout", "latency_s": TIMEOUT,
                "category": q.get("category", ""), "difficulty": q.get("difficulty", ""),
            })
        except Exception as e:
            print(f"    EXCEPTION: {e}")
            results.append({
                "q_id": q_id, "question": question, "expected": expected,
                "actual": f"EXCEPTION: {e}", "confidence": 0, "pass": False,
                "score": 0, "reason": "exception", "latency_s": 0,
                "category": q.get("category", ""), "difficulty": q.get("difficulty", ""),
            })

    return results


def print_report(corpus_name: str, results: list, output_file: str = None):
    """Print evaluation report"""
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    failed = total - passed
    avg_score = sum(r["score"] for r in results) / total if total else 0
    avg_latency = sum(r["latency_s"] for r in results) / total if total else 0

    report_lines = []

    def pr(line=""):
        report_lines.append(line)
        print(line)

    pr(f"\n{'=' * 70}")
    pr(f"EVALUATION REPORT: {corpus_name}")
    pr(f"{'=' * 70}")
    pr(f"  Date:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pr(f"  Total:         {total}")
    pr(f"  Passed:        {passed} ({100 * passed / total:.1f}%)")
    pr(f"  Failed:        {failed} ({100 * failed / total:.1f}%)")
    pr(f"  Avg Score:     {avg_score:.3f}")
    pr(f"  Avg Latency:   {avg_latency:.1f}s")

    # Breakdown by category
    categories = set(r.get("category", "") for r in results if r.get("category"))
    if categories:
        pr(f"\n  By Category:")
        for cat in sorted(categories):
            cat_results = [r for r in results if r.get("category") == cat]
            cat_passed = sum(1 for r in cat_results if r["pass"])
            pr(f"    {cat:30s}: {cat_passed}/{len(cat_results)} "
               f"({100 * cat_passed / len(cat_results):.0f}%)")

    # Breakdown by difficulty
    difficulties = set(r.get("difficulty", "") for r in results if r.get("difficulty"))
    if difficulties:
        pr(f"\n  By Difficulty:")
        for diff in ["easy", "EASY", "medium", "MEDIUM", "hard", "HARD"]:
            diff_results = [r for r in results if r.get("difficulty", "").lower() == diff.lower()]
            if diff_results:
                diff_passed = sum(1 for r in diff_results if r["pass"])
                pr(f"    {diff.upper():30s}: {diff_passed}/{len(diff_results)} "
                   f"({100 * diff_passed / len(diff_results):.0f}%)")

    # Failed questions
    failures = [r for r in results if not r["pass"]]
    if failures:
        pr(f"\n  Failed Questions ({len(failures)}):")
        for r in failures[:30]:  # Show first 30
            pr(f"    Q{r['q_id']}: {r['question'][:70]}")
            pr(f"      Expected: {r['expected'][:80]}")
            pr(f"      Got:      {r['actual'][:80]}")
            pr(f"      Score: {r['score']:.2f}, Reason: {r['reason']}")
            pr()

    pr(f"{'=' * 70}")

    # Save report
    if output_file:
        with open(output_file, "w") as f:
            f.write("\n".join(report_lines))
        # Also save raw results as JSON
        json_file = output_file.replace(".txt", ".json")
        with open(json_file, "w") as f:
            json.dump({
                "corpus": corpus_name,
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": round(100 * passed / total, 1) if total else 0,
                    "avg_score": round(avg_score, 3),
                    "avg_latency_s": round(avg_latency, 1),
                },
                "results": results,
            }, f, indent=2)
        print(f"\n  Report saved to: {output_file}")
        print(f"  Raw results saved to: {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Context Foundry Corpus Evaluation")
    parser.add_argument("corpus", choices=["nexus", "horizon", "medsync"],
                        help="Which corpus to evaluate")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip ingestion, assume data is already loaded")
    parser.add_argument("--extract", action="store_true",
                        help="Also run entity extraction (slow)")
    parser.add_argument("--sample", type=int, default=0,
                        help="Only run N random questions (0 = all)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file for report")
    parser.add_argument("--rescore", type=str, default=None,
                        help="Re-score existing results JSON file (skip API calls)")

    args = parser.parse_args()

    corpus_config = CORPORA[args.corpus]
    corpus_name = corpus_config["name"]

    print(f"\n{'=' * 70}")
    print(f"Context Foundry Evaluation: {corpus_name}")
    print(f"{'=' * 70}")

    # ── RESCORE MODE: re-score existing results without API calls ──
    if args.rescore:
        print(f"\n  Re-scoring from: {args.rescore}")
        with open(args.rescore) as f:
            old_data = json.load(f)
        results = old_data["results"]
        # Re-score each result
        for r in results:
            new_score = score_answer(r["actual"], r["expected"], r.get("question", ""))
            r["pass"] = new_score["pass"]
            r["score"] = new_score["score"]
            r["reason"] = new_score["reason"]
        output_file = args.output or f"eval_{args.corpus}_rescored.txt"
        print_report(corpus_name, results, output_file)
        return

    # Check API is up
    client = httpx.Client()
    try:
        resp = client.get(f"{API_BASE}/", timeout=5.0)
        if resp.status_code != 200:
            print(f"ERROR: API not responding at {API_BASE}")
            sys.exit(1)
        print(f"\n  API is up: {resp.json().get('status')}")
    except Exception as e:
        print(f"ERROR: Cannot reach API at {API_BASE}: {e}")
        sys.exit(1)

    # Load documents
    print(f"\n  Loading documents from: {corpus_config['docs_dir']}")
    documents = load_documents(corpus_config["docs_dir"])
    print(f"  Found {len(documents)} documents")

    # Load questions
    print(f"  Loading questions from: {corpus_config['qa_file']}")
    questions = load_questions(corpus_config["qa_file"], corpus_config["qa_format"])
    print(f"  Found {len(questions)} questions")

    # Sample if requested
    if args.sample > 0 and args.sample < len(questions):
        import random
        random.seed(42)
        questions = random.sample(questions, args.sample)
        print(f"  Sampled {len(questions)} questions")

    # Ingestion phase
    if not args.skip_ingest:
        print(f"\n--- PHASE 1: INGESTION ---")
        reset_database(client)

        print(f"\n  Embedding {len(documents)} documents...")
        start = time.time()
        ingest_result = ingest_documents(client, documents, batch_size=10)
        elapsed = time.time() - start
        print(f"\n  Ingestion complete: {ingest_result['total_chunks']} chunks, "
              f"{ingest_result['total_embeddings']} embeddings ({elapsed:.0f}s)")

        if ingest_result["errors"]:
            print(f"  Errors: {len(ingest_result['errors'])}")
            for err in ingest_result["errors"][:5]:
                print(f"    - {err}")

        # Optional extraction
        if args.extract:
            print(f"\n  Running entity extraction on {len(documents)} documents...")
            start = time.time()
            extract_result = run_extraction(client, documents, batch_size=5)
            elapsed = time.time() - start
            print(f"\n  Extraction complete: {extract_result['total_entities']} entities, "
                  f"{extract_result['total_relationships']} relationships ({elapsed:.0f}s)")
    else:
        print(f"\n--- SKIPPING INGESTION (--skip-ingest) ---")

    # Get stats
    try:
        stats = client.get(f"{API_BASE}/stats", timeout=10.0).json()
        print(f"\n  System stats: {stats.get('documents_embedded', 0)} docs, "
              f"{stats.get('entities_trusted', 0)} entities, "
              f"{stats.get('relationships_total', 0)} relationships")
    except Exception:
        pass

    # Evaluation phase
    print(f"\n--- PHASE 2: EVALUATION ({len(questions)} questions) ---\n")
    start = time.time()
    results = run_evaluation(client, questions)
    eval_elapsed = time.time() - start

    # Report
    output_file = args.output or f"eval_{args.corpus}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    print_report(corpus_name, results, output_file)
    print(f"  Total eval time: {eval_elapsed:.0f}s")


if __name__ == "__main__":
    main()
