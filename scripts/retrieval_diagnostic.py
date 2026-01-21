"""
Retrieval Pipeline Diagnostic Tool

Traces the retrieval path for specific questions:
1. Checks if relevant chunks exist (chunking stage)
2. Runs semantic search and captures top-K results (embedding/ranking stage)
3. Compares retrieved chunks with expected source content (post-retrieval stage)
"""

import sys
sys.path.insert(0, '.')

import os
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# Database and models
from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.memory.episodic import EpisodicMemory

@dataclass
class DiagnosticResult:
    """Result of diagnosing a single query."""
    question_id: int
    query: str
    expected_answer: str
    source_file: str
    source_content: str
    
    # Stage 1: Chunking
    chunk_exists: bool = False
    chunk_id: Optional[str] = None
    chunk_text: Optional[str] = None
    chunk_similarity: float = 0.0
    
    # Stage 2: Retrieval ranking
    top_chunks: List[Dict] = field(default_factory=list)
    expected_chunk_rank: Optional[int] = None  # Where expected chunk ranks in results
    
    # Stage 3: Failure diagnosis
    failure_stage: str = "unknown"
    diagnosis: str = ""


def find_chunk_containing_text(session, tenant_id: str, search_text: str) -> Optional[Dict]:
    """Search for a chunk containing specific text."""
    result = session.execute(text("""
        SELECT dc.id, dc.text, dc.chunk_index, d.name as doc_name
        FROM document_chunks dc
        JOIN platform.documents d ON dc.document_id = d.id
        WHERE dc.tenant_id = :tid
        AND dc.text ILIKE :search
        LIMIT 1
    """), {"tid": tenant_id, "search": f"%{search_text}%"})
    
    row = result.fetchone()
    if row:
        return {"id": str(row[0]), "text": row[1], "chunk_index": row[2], "doc_name": row[3]}
    return None


def run_semantic_search(episodic: EpisodicMemory, query: str, limit: int = 10) -> List[Dict]:
    """Run semantic search and return top chunks with scores."""
    results = episodic.search_similar(query, limit=limit)
    return results


def diagnose_query(
    session, 
    tenant_id: str, 
    episodic: EpisodicMemory,
    q_id: int,
    query: str, 
    expected: str, 
    source_file: str,
    key_text: str  # The actual text that should be in a chunk
) -> DiagnosticResult:
    """
    Run full diagnostic for a single query.
    """
    result = DiagnosticResult(
        question_id=q_id,
        query=query,
        expected_answer=expected,
        source_file=source_file,
        source_content=key_text
    )
    
    # Stage 1: Check if chunk containing key text exists
    chunk = find_chunk_containing_text(session, tenant_id, key_text)
    if chunk:
        result.chunk_exists = True
        result.chunk_id = chunk["id"]
        result.chunk_text = chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
    else:
        result.failure_stage = "chunking"
        result.diagnosis = f"No chunk contains key text: '{key_text[:50]}...'"
        return result
    
    # Stage 2: Run semantic search and check ranking
    top_chunks = run_semantic_search(episodic, query, limit=20)
    result.top_chunks = [
        {"rank": i+1, "score": c.get("similarity", 0), "text": c["text"][:100] + "...", "doc": c.get("source_document", "?")}
        for i, c in enumerate(top_chunks[:10])
    ]
    
    # Find where the expected chunk ranks
    expected_chunk_rank = None
    for i, c in enumerate(top_chunks):
        if key_text.lower() in c.get("text", "").lower():
            expected_chunk_rank = i + 1
            result.chunk_similarity = c.get("similarity", 0)
            break
    
    result.expected_chunk_rank = expected_chunk_rank
    
    if expected_chunk_rank is None:
        result.failure_stage = "embedding"
        result.diagnosis = f"Chunk exists but not in top-20 results. Semantic similarity too low."
    elif expected_chunk_rank > 5:
        result.failure_stage = "ranking"
        result.diagnosis = f"Chunk found at rank {expected_chunk_rank} (score: {result.chunk_similarity:.3f}), outside default top-5 limit."
    else:
        result.failure_stage = "none"
        result.diagnosis = f"Chunk found at rank {expected_chunk_rank} (score: {result.chunk_similarity:.3f}). Should be retrievable."
    
    return result


def main():
    """Run diagnostics for Track 2 questions."""
    session = get_session()
    
    # Find tenant with documents
    result = session.execute(text("""
        SELECT t.id, t.name, COUNT(d.id) as doc_count
        FROM platform.tenants t
        JOIN platform.documents d ON d.tenant_id = t.id
        GROUP BY t.id, t.name
        HAVING COUNT(d.id) > 10
        ORDER BY COUNT(d.id) DESC
        LIMIT 1
    """))
    
    row = result.fetchone()
    if not row:
        print("ERROR: No tenant with documents found. Run a test first to create a vault.")
        print("\nTo create a vault, run: python -m src.test_runner.runner --corpus 'Manus Healthtec'")
        return
    
    tenant_id, tenant_name, doc_count = row[0], row[1], row[2]
    print(f"Using tenant: {tenant_name} ({tenant_id[:8]}...) with {doc_count} documents")
    
    # Initialize episodic memory for this tenant
    episodic = EpisodicMemory(session=session, tenant_id=tenant_id)
    
    # Track 2 questions to diagnose
    track2_questions = [
        {
            "q": 14,
            "query": "What is the total funding raised by MedSync Health?",
            "expected": "$165 million",
            "source": "company_profile.md",
            "key_text": "Total Funding"  # Key text that should be in chunk
        },
        {
            "q": 16,
            "query": "When was MedSync Health's European operations established?",
            "expected": "2022",
            "source": "company_profile.md", 
            "key_text": "European Operations"
        },
        {
            "q": 55,
            "query": "What CRM system does MedSync Health use?",
            "expected": "Salesforce",
            "source": "vendor_list.md",
            "key_text": "Salesforce"
        },
        {
            "q": 56,
            "query": "What team communication tool does MedSync Health use?",
            "expected": "Slack",
            "source": "vendor_list.md",
            "key_text": "Slack"
        },
        {
            "q": 183,
            "query": "What is the preferred ground transportation method for local travel?",
            "expected": "Ride-sharing services (Uber, Lyft)",
            "source": "hr_policies.md",
            "key_text": "ride-sharing"
        }
    ]
    
    print("\n" + "="*80)
    print("RETRIEVAL PIPELINE DIAGNOSTICS - TRACK 2 QUESTIONS")
    print("="*80)
    
    results = []
    for q in track2_questions:
        print(f"\n--- Q{q['q']}: {q['query'][:50]}... ---")
        diag = diagnose_query(
            session, tenant_id, episodic,
            q["q"], q["query"], q["expected"], q["source"], q["key_text"]
        )
        results.append(diag)
        
        print(f"  Expected: {q['expected']}")
        print(f"  Source: {q['source']}")
        print(f"  Chunk exists: {diag.chunk_exists}")
        if diag.chunk_exists:
            print(f"  Chunk rank: {diag.expected_chunk_rank or 'Not in top-20'}")
            print(f"  Similarity: {diag.chunk_similarity:.3f}")
        print(f"  FAILURE STAGE: {diag.failure_stage.upper()}")
        print(f"  Diagnosis: {diag.diagnosis}")
        
        if diag.top_chunks:
            print(f"\n  Top 5 retrieved chunks:")
            for c in diag.top_chunks[:5]:
                print(f"    #{c['rank']} (score: {c['score']:.3f}) [{c['doc']}]: {c['text'][:60]}...")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    by_stage = {}
    for r in results:
        by_stage.setdefault(r.failure_stage, []).append(r.question_id)
    
    for stage, qs in by_stage.items():
        print(f"  {stage.upper()}: Q{', Q'.join(map(str, qs))}")
    
    # Save results to file
    output = {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "results": [
            {
                "q": r.question_id,
                "query": r.query,
                "expected": r.expected_answer,
                "source": r.source_file,
                "chunk_exists": r.chunk_exists,
                "chunk_rank": r.expected_chunk_rank,
                "similarity": r.chunk_similarity,
                "failure_stage": r.failure_stage,
                "diagnosis": r.diagnosis,
                "top_chunks": r.top_chunks[:5]
            }
            for r in results
        ]
    }
    
    with open("test_results/track2_diagnostic.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nDetailed results saved to: test_results/track2_diagnostic.json")


if __name__ == "__main__":
    main()
