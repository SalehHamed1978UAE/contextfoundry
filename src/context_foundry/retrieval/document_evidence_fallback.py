"""Stage 2D — DOCUMENT_EVIDENCE fallback.

Conservative chunk-grounded fallback for attribute/spec/date/metric questions
that the Knowledge Graph cannot answer. Tenant-scoped. Cites every chunk.
Never claims TRUSTED_GRAPH provenance.

Design constraints (Stage 2D plan):
  - Fallback only triggers when KG returns no_data / "I don't know" / NOT_FOUND.
  - Initial trigger set: revenue, amount, budget, backlog, capex, date, when,
    year, specification, endurance, temperature, qubits, capacity, certification,
    compliance, credential, degree, education, milestone, target, goal.
  - Tenant-scoped retrieval (every SQL filter includes tenant_id).
  - Provenance carried on every answer: chunk_id, document_id, document_title,
    char range, snippet.
  - `answer_source` is one of:
      TRUSTED_GRAPH_FACT | STAGING_GRAPH_FACT | DOCUMENT_EVIDENCE | GAP
  - Refuses to answer (returns None) when the LLM cannot ground the answer
    in the supplied chunks (says "NOT_IN_DOCUMENTS").
  - Read-only: never writes entities / relationships / documents / chunks /
    extraction_requests. Reuses ConversationStore writes if invoked through
    ToolAgent (a known append-only side-effect of the live API surface).

Stage 1J vault has 0/435 chunks with embeddings, so this module uses
ILIKE token-overlap ranking on `document_chunks.text` (NOT pgvector).
That keeps it portable to vaults whose extraction skipped embeddings.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

logger = logging.getLogger(__name__)


ANSWER_SOURCE_TRUSTED_GRAPH = "TRUSTED_GRAPH_FACT"
ANSWER_SOURCE_STAGING_GRAPH = "STAGING_GRAPH_FACT"
ANSWER_SOURCE_DOCUMENT_EVIDENCE = "DOCUMENT_EVIDENCE"
ANSWER_SOURCE_GAP = "GAP"

# Stage 3A: Property plane sources — DocEv should not override these
ANSWER_SOURCE_TRUSTED_PROPERTY = "TRUSTED_PROPERTY"
ANSWER_SOURCE_STAGING_PROPERTY = "STAGING_PROPERTY"


_ATTRIBUTE_TRIGGERS: Dict[str, List[str]] = {
    "money": [
        "revenue", "amount", "budget", "backlog", "capex", "cost", "cogs",
        "expenditure", "spend", "investment", "valuation", "ebitda", "margin",
        "price", "fee", "salary", "compensation", "funding", "raised",
    ],
    "date": [
        "when", "date", "year", "month", "quarter", "deadline", "anniversary",
        "founded", "established", "incorporated", "appointed", "hired",
        "joined", "left", "resigned", "retired", "succeeded", "replaced",
    ],
    "spec": [
        "specification", "spec", "endurance", "temperature", "qubits",
        "capacity", "throughput", "bandwidth", "latency", "voltage",
        "watt", "watts", "kilowatt", "megawatt", "gigawatt", "energy density",
        "horsepower", "rpm", "psi", "torque", "weight", "dimension",
        "tolerance", "resolution", "frequency", "speed", "range",
    ],
    "certification": [
        "certification", "certified", "compliance", "compliant", "iso",
        "fedramp", "soc 2", "soc2", "hipaa", "pci", "fips", "nist",
        "accredited", "accreditation", "audited", "audit",
    ],
    "credential": [
        "credential", "degree", "education", "alma mater", "university",
        "college", "phd", "mba", "doctorate", "bachelor", "master", "alumna",
        "alumnus", "graduated", "studied",
    ],
    "milestone": [
        "milestone", "target", "goal", "objective", "deliverable",
        "completion", "rollout", "launch", "ship date", "go-live",
    ],
    "metric": [
        "metric", "kpi", "trir", "ltir", "rate", "ratio", "score",
        "headcount", "fte", "employees", "count", "number of",
        "how many", "how much",
    ],
    "list_lookup": [
        "list of", "all the", "which ", "who is the chair", "name the",
        "what are the", "top ", "largest", "smallest",
    ],
}

_NO_DATA_TEXT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bi don'?t (have|know)\b",
        r"\bi do not (have|know)\b",
        r"\bcouldn'?t find\b",
        r"\bcould not find\b",
        r"\bno (information|data|records?) (available|found)\b",
        r"\bnot (available|found|specified|provided)\b",
        r"\binsufficient (information|data|context)\b",
        r"\bunable to (find|determine|provide)\b",
        r"\bnot enough (information|context)\b",
        r"\bunknown\b",
        r"\bI'?m not sure\b",
    ]
]

_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "did",
    "for", "from", "has", "have", "had", "he", "her", "his", "how",
    "i", "in", "is", "it", "its", "of", "on", "or", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were", "what",
    "when", "where", "which", "who", "whom", "whose", "why", "will",
    "with", "you", "your", "about", "into",
}


@dataclass
class EvidenceChunk:
    chunk_id: str
    document_id: str
    document_title: Optional[str]
    chunk_index: int
    char_start: Optional[int]
    char_end: Optional[int]
    text: str
    overlap_score: float


@dataclass
class FallbackResult:
    """Returned when the fallback successfully grounds an answer in chunks."""
    answer: str
    answer_source: str  # always DOCUMENT_EVIDENCE for this dataclass
    attribute_category: str
    chunks: List[EvidenceChunk]
    citations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "answer_source": self.answer_source,
            "attribute_category": self.attribute_category,
            "chunks": [asdict(c) for c in self.chunks],
            "citations": self.citations,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_attribute_query(query: str) -> Optional[str]:
    """Return the attribute category if `query` matches a Stage 2D trigger.

    Returns None if the query is not an attribute/spec/date/metric question.
    Categories: money, date, spec, certification, credential, milestone,
    metric, list_lookup.
    """
    if not query:
        return None
    q = query.lower()
    for category, terms in _ATTRIBUTE_TRIGGERS.items():
        for term in terms:
            if term in q:
                return category
    return None


def looks_like_no_data(answer: str) -> bool:
    """Detect 'I don't know' style answers from the KG path."""
    if not answer:
        return True
    a = answer.strip()
    if not a:
        return True
    for pat in _NO_DATA_TEXT_PATTERNS:
        if pat.search(a):
            return True
    return False


def _tokenize(text_in: str) -> List[str]:
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.]+", (text_in or "").lower())
    return [t for t in raw if t not in _STOPWORDS and len(t) > 1]


def find_evidence_chunks(
    session,
    tenant_id: str,
    query: str,
    top_k: int = 5,
    sample_size: int = 200,
) -> List[EvidenceChunk]:
    """Tenant-scoped chunk retrieval via ILIKE token-overlap.

    Pulls up to `sample_size` chunks that contain ANY query token, ranks by
    distinct-token-overlap count, returns top `top_k`.

    Pure read. ORDER BY id ASC for determinism (then by overlap desc in Python).
    Never returns chunks from a different tenant.
    """
    tokens = _tokenize(query)
    if not tokens:
        return []

    sql = """
        SELECT
            dc.id::text          AS chunk_id,
            dc.document_id::text AS document_id,
            d.title              AS document_title,
            dc.chunk_index       AS chunk_index,
            dc.char_start        AS char_start,
            dc.char_end          AS char_end,
            dc.text              AS text
        FROM document_chunks dc
        LEFT JOIN documents d
               ON d.id = dc.document_id AND d.tenant_id = dc.tenant_id
        WHERE dc.tenant_id = :tid
          AND (
    """
    or_clauses = []
    params: Dict[str, Any] = {"tid": tenant_id}
    for i, tok in enumerate(tokens):
        key = f"t{i}"
        or_clauses.append(f"dc.text ILIKE :{key}")
        params[key] = f"%{tok}%"
    sql += " OR ".join(or_clauses)
    sql += f"""
          )
        ORDER BY dc.id ASC
        LIMIT {int(sample_size)}
    """

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return []

    out: List[EvidenceChunk] = []
    for r in rows:
        chunk_text = r.text or ""
        lower = chunk_text.lower()
        score = sum(1 for tok in set(tokens) if tok in lower)
        if score == 0:
            continue
        out.append(EvidenceChunk(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            chunk_index=r.chunk_index,
            char_start=r.char_start,
            char_end=r.char_end,
            text=chunk_text,
            overlap_score=float(score),
        ))

    out.sort(key=lambda c: (-c.overlap_score, c.chunk_id))
    return out[:top_k]


def synthesize_from_chunks(
    query: str,
    chunks: List[EvidenceChunk],
    openai_client=None,
    model: str = "gpt-4o-mini",
) -> Optional[str]:
    """Ask the LLM to answer `query` using ONLY the provided chunks.

    Returns None if the LLM says NOT_IN_DOCUMENTS (or if the call fails).
    """
    if not chunks:
        return None

    if openai_client is None:
        try:
            from openai import OpenAI
            api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
            if not api_key:
                logger.warning("[DOC_EV] No OpenAI key — fallback cannot synthesize")
                return None
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            openai_client = OpenAI(**kwargs)
        except Exception as e:
            logger.warning(f"[DOC_EV] OpenAI client init failed: {e}")
            return None

    chunk_blocks = []
    for i, c in enumerate(chunks, 1):
        title = c.document_title or "(untitled)"
        chunk_blocks.append(
            f"[CHUNK {i}] document=\"{title}\" chunk_id={c.chunk_id} chunk_index={c.chunk_index}\n{c.text}"
        )
    chunks_str = "\n\n---\n\n".join(chunk_blocks)

    system = (
        "You answer questions ONLY using the provided document chunks. "
        "If the answer is not present in the chunks, you must respond with the "
        "single token NOT_IN_DOCUMENTS and nothing else. "
        "Do not use any prior knowledge. Be concise. "
        "Quote concrete values (numbers, dates, names) verbatim from the chunks."
    )
    user = (
        f"Question: {query}\n\n"
        f"Document chunks (tenant-scoped):\n\n{chunks_str}\n\n"
        f"Answer the question using ONLY the chunks above. "
        f"If the answer is not in the chunks, output exactly: NOT_IN_DOCUMENTS"
    )

    try:
        resp = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            max_tokens=400,
        )
        ans = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning(f"[DOC_EV] LLM synthesis failed: {e}")
        return None

    if not ans:
        return None
    if ans.upper().startswith("NOT_IN_DOCUMENTS"):
        return None
    return ans


def attempt_document_evidence_fallback(
    session,
    tenant_id: str,
    query: str,
    *,
    kg_answer: Optional[str] = None,
    kg_answer_source: Optional[str] = None,
    openai_client=None,
    model: str = "gpt-4o-mini",
    top_k: int = 5,
) -> Optional[FallbackResult]:
    """Top-level orchestrator. Returns None when no fallback should be applied.

    Returns a FallbackResult only when:
      - the query is an attribute query (is_attribute_query → not None),
      - AND the KG answer is missing OR looks_like_no_data,
      - AND we found relevant chunks,
      - AND the LLM grounded a non-NOT_IN_DOCUMENTS answer in those chunks.

    Otherwise returns None — caller keeps the original KG answer (which may
    itself be a GAP / no_data response).
    """
    if kg_answer_source == ANSWER_SOURCE_TRUSTED_GRAPH:
        return None

    category = is_attribute_query(query)
    if not category:
        return None

    if kg_answer is not None and not looks_like_no_data(kg_answer):
        return None

    chunks = find_evidence_chunks(session, tenant_id, query, top_k=top_k)
    if not chunks:
        return None

    answer = synthesize_from_chunks(
        query=query,
        chunks=chunks,
        openai_client=openai_client,
        model=model,
    )
    if not answer:
        return None

    citations = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "document_title": c.document_title,
            "chunk_index": c.chunk_index,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "snippet": (c.text or "")[:200],
        }
        for c in chunks
    ]

    logger.info(
        f"[DOC_EV] Fallback fired: category={category} chunks={len(chunks)} "
        f"top_overlap={chunks[0].overlap_score:.0f} answer_len={len(answer)}"
    )

    return FallbackResult(
        answer=answer,
        answer_source=ANSWER_SOURCE_DOCUMENT_EVIDENCE,
        attribute_category=category,
        chunks=chunks,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Stage 2E-1: production-route helper
# ---------------------------------------------------------------------------

# QA-verifier statuses that web_app.py replaces with no-data text
_QA_NO_DATA_STATUSES = {"OFF_TOPIC", "INSUFFICIENT", "UNSUPPORTED", "SUSPICIOUS"}


def classify_agent_kg_source(
    agent_result: Optional[Dict[str, Any]],
    qa_verdict: Optional[Dict[str, Any]] = None,
) -> str:
    """Classify the agent's KG-side answer_source for fallback gating.

    Returns ANSWER_SOURCE_GAP if any of:
      - agent_result is None
      - agent_result.extra.not_found_response is truthy
      - qa_verdict.status is in {OFF_TOPIC, INSUFFICIENT, UNSUPPORTED, SUSPICIOUS}
      - the answer text looks like a no-data response

    Otherwise returns ANSWER_SOURCE_TRUSTED_GRAPH_FACT — which the orchestrator
    treats as a hard block (Stage 2E-1 must NOT override confident KG answers).
    """
    if not agent_result:
        return ANSWER_SOURCE_GAP
    extra = agent_result.get("extra") or {}
    if extra.get("not_found_response"):
        return ANSWER_SOURCE_GAP
    if qa_verdict and qa_verdict.get("status") in _QA_NO_DATA_STATUSES:
        return ANSWER_SOURCE_GAP
    # Stage 3A: property plane answers are authoritative — treat as trusted
    answer_source = agent_result.get("answer_source") or ""
    if answer_source in (ANSWER_SOURCE_TRUSTED_PROPERTY, ANSWER_SOURCE_STAGING_PROPERTY):
        return ANSWER_SOURCE_TRUSTED_GRAPH

    answer = agent_result.get("answer") or ""
    if not answer or looks_like_no_data(answer):
        return ANSWER_SOURCE_GAP
    return ANSWER_SOURCE_TRUSTED_GRAPH


def is_fallback_enabled(
    request_payload_value: Any = None,
    env_var_name: str = "CF_DOCUMENT_EVIDENCE_FALLBACK",
) -> bool:
    """Stage 2E-1 feature-flag check — default OFF.

    Per-request payload (`document_evidence_fallback`) takes priority over env.
    Accepts True/False/"true"/"false"/None. Anything else falsy.
    """
    if request_payload_value is not None:
        if isinstance(request_payload_value, bool):
            return request_payload_value
        if isinstance(request_payload_value, str):
            return request_payload_value.strip().lower() == "true"
        return False
    env_val = os.environ.get(env_var_name, "false")
    return str(env_val).strip().lower() == "true"


def apply_to_agent_result(
    agent_result: Dict[str, Any],
    *,
    session,
    tenant_id: str,
    query: str,
    request_payload_value: Any = None,
    qa_verdict: Optional[Dict[str, Any]] = None,
    openai_client=None,
    model: str = "gpt-4o-mini",
    top_k: int = 5,
    env_var_name: str = "CF_DOCUMENT_EVIDENCE_FALLBACK",
) -> Dict[str, Any]:
    """Stage 2E-1 production-route helper.

    Mutates `agent_result` in place to add Stage 2D fallback diagnostics and,
    if the fallback fires, to replace the answer with DOCUMENT_EVIDENCE.

    Always sets `agent_result['document_evidence_diagnostics']` so the route
    can surface diagnostics regardless of whether the fallback fired.

    Honours the standing read-only contract: never writes to KG/ontology/
    documents/document_chunks/extraction_requests.

    Returns the same `agent_result` dict for ergonomic chaining.
    """
    diagnostics: Dict[str, Any] = {
        "flag_enabled": False,
        "fallback_attempted": False,
        "fallback_used": False,
        "gate_block_reason": None,
        "kg_source": None,
        "attribute_category": None,
        "chunks_considered": 0,
    }
    agent_result["document_evidence_diagnostics"] = diagnostics

    if not is_fallback_enabled(request_payload_value, env_var_name):
        diagnostics["gate_block_reason"] = "flag_off"
        return agent_result

    diagnostics["flag_enabled"] = True

    kg_source = classify_agent_kg_source(agent_result, qa_verdict)
    diagnostics["kg_source"] = kg_source

    if kg_source == ANSWER_SOURCE_TRUSTED_GRAPH:
        # Stage 2E-1: never override confident KG answers — diagnostic only.
        diagnostics["gate_block_reason"] = "trusted_kg_answer"
        return agent_result

    category = is_attribute_query(query)
    if not category:
        diagnostics["gate_block_reason"] = "not_attribute_query"
        return agent_result
    diagnostics["attribute_category"] = category

    diagnostics["fallback_attempted"] = True
    try:
        # The route helper has already authoritatively classified the result
        # as GAP. Pass kg_answer=None so the inner function's defensive
        # looks_like_no_data check (which doesn't recognize QA-verifier stubs
        # like the OFF_TOPIC text) cannot block the fallback.
        fb = attempt_document_evidence_fallback(
            session=session,
            tenant_id=tenant_id,
            query=query,
            kg_answer=None,
            kg_answer_source=kg_source,
            openai_client=openai_client,
            model=model,
            top_k=top_k,
        )
    except Exception as e:
        logger.warning(f"[DOC_EV] route helper failure: {e}")
        diagnostics["gate_block_reason"] = f"exception:{type(e).__name__}"
        return agent_result

    if fb is None:
        diagnostics["gate_block_reason"] = "no_grounded_answer"
        return agent_result

    # Fallback fired and grounded — replace the answer.
    diagnostics["fallback_used"] = True
    diagnostics["chunks_considered"] = len(fb.chunks)
    agent_result["answer"] = fb.answer
    agent_result["answer_source"] = ANSWER_SOURCE_DOCUMENT_EVIDENCE
    agent_result["document_evidence"] = fb.citations
    return agent_result
