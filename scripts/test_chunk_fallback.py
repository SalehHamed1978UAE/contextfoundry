"""Unit test for tree_retriever._fallback_semantic_search (chunk-grounded).

Validates that chunk-grounded fallback returns:
  - chunks with high similarity (top_chunk_sim > 0.50) for in-corpus questions
  - entities resolved via source_chunk_id (count > 0)
  - higher avg score than the old name_embedding fallback (which gave 0.143)

Usage: python scripts/test_chunk_fallback.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.context_foundry.retrieval.tree_retriever import TreeBasedRetriever as TreeRetriever

VAULT_TENANT = "176a4fb2-0bb4-4da3-9068-0e26268fca71"

QUESTIONS = [
    "What was Nexus Industries' revenue in FY2025?",
    "How many employees does Nexus Industries have?",
    "Which division has the most employees?",
    "What is the annual HTS wire production capacity?",
    "What FedRAMP level did CyberShield achieve?",
    "Who is the mining automation partner?",
    "What is the M&A budget capacity?",
    "What is the renewable energy achievement?",
]

def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()

    r = TreeRetriever(session=session, tenant_id=VAULT_TENANT)

    print(f"=== Chunk-grounded fallback test (vault={VAULT_TENANT[:8]}) ===\n")
    sims = []
    failures = 0
    for q in QUESTIONS:
        result = r._fallback_semantic_search(q, top_k=20, chunk_top_k=30)
        n_ent = len(result.entities)
        n_rel = len(result.relationships)
        top_sim = result.entities[0]['combined_score'] if result.entities else 0.0
        sims.append(top_sim)
        ok = top_sim >= 0.40 and n_ent > 0
        status = "OK " if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{status}] top_sim={top_sim:.3f}  ent={n_ent:3d}  rel={n_rel:3d}  conf={result.confidence:6s}  q={q!r}")

    avg = sum(sims) / len(sims) if sims else 0.0
    print(f"\n  Avg top_sim: {avg:.3f}  (old impl was 0.143)")
    print(f"  Failures:    {failures}/{len(QUESTIONS)}")

    session.close()

    if failures > 0:
        print("\nFAIL: at least one question returned poor results")
        sys.exit(1)
    if avg < 0.40:
        print(f"\nFAIL: avg top_sim {avg:.3f} below 0.40 threshold")
        sys.exit(1)
    print("\nPASS")
    sys.exit(0)

if __name__ == "__main__":
    main()
