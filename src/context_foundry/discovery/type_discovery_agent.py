"""TypeDiscoveryAgent — Component 2 of the Intelligent Auto-Discovery System.

Observes extraction outputs (relationships emitted by the LLM, with their raw
predicate phrases and the source-text evidence) and proposes new ontology types
based on observed patterns.

Two discovery modes:

1. Frequent unmapped predicate phrases — the LLM keeps emitting a phrase that
   isn't in the ontology (e.g. PRESIDENT_OF, HAS_BUDGET, AUTHORED_BY). After
   ``min_observations`` occurrences across documents, the agent proposes it as
   a new top-level relationship type.

2. Compound-role patterns — the source text contains "<Role> of <Org>" mentions
   (e.g. "President of Nexus Digital Solutions"). When a base role appears
   enough times across distinct organisations, the agent proposes
   ``<ROLE>_OF`` as a subtype of ``HOLDS_POSITION``.

Inheritance is encoded via ``parent_type`` on the proposal so downstream
ontology storage can record the subtype relationship.
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)


# ----------------------------- data records -----------------------------------

@dataclass
class ObservedPattern:
    """A single relationship observation from one extraction."""
    source_type: str                  # entity_type of source
    target_type: str                  # entity_type of target
    relationship_phrase: str          # raw_relationship_type as emitted by LLM
    source_text: str                  # evidence sentence / chunk excerpt
    document_type: str                # e.g. 'communications', 'financials'
    confidence: float                 # extraction confidence


@dataclass
class TypeProposal:
    """A proposed addition to the ontology."""
    proposed_type: str
    source_types: Set[str]
    target_types: Set[str]
    observation_count: int
    example_evidence: List[str]
    confidence: float
    proposal_reason: str
    parent_type: Optional[str] = None     # subtype-of, when known


# ------------------------------- agent ----------------------------------------

class TypeDiscoveryAgent:
    """Observes extraction outputs and proposes new ontology types.

    Args:
        session: SQLAlchemy session, used to load the *current* ontology so
            we don't propose duplicates. Optional — when None, ``known_types``
            must be provided directly.
        min_observations: a phrase must be observed this many times before
            it's proposed (defaults to 5 per the spec).
        known_types: optional pre-supplied set of known types. Skips DB lookup
            when provided (useful for tests, dry-runs, and tight loops).
        compound_min_distinct_orgs: a base role must appear with at least this
            many distinct organisations before a compound-role proposal is
            emitted (defends against single-doc noise).
    """

    # Compound-role pattern: "<Role> of <Org>". The role group is a closed
    # vocabulary of common executive titles; the org group is permissive
    # because organisation names vary widely.
    _COMPOUND_ROLE_RE = re.compile(
        r"\b(President|CEO|CFO|CTO|COO|CIO|CISO|VP|Vice\s+President|"
        r"Director|Manager|Head|Chief|Chair|Chairman|Chairwoman|Chairperson)\s+"
        r"of\s+([A-Z][\w&'.-]*(?:\s+[A-Z][\w&'.-]*){0,5})",
        re.IGNORECASE,
    )

    def __init__(
        self,
        session: Any = None,
        min_observations: int = 5,
        known_types: Optional[Set[str]] = None,
        compound_min_distinct_orgs: int = 2,
        known_types_loader: Optional[Callable[[], Set[str]]] = None,
        tenant_id: Optional[str] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.min_observations = min_observations
        self.compound_min_distinct_orgs = compound_min_distinct_orgs
        self._known_types: Optional[Set[str]] = (
            {t.upper() for t in known_types} if known_types is not None else None
        )
        self._known_types_loader = known_types_loader
        self.observation_log: List[ObservedPattern] = []

    # -------------------- ingestion --------------------
    def observe(self, pattern: ObservedPattern) -> None:
        """Append a single observation."""
        self.observation_log.append(pattern)

    def observe_extraction(
        self,
        relationships: Iterable[Any],
        document_type: str = "unknown",
        evidence_lookup: Optional[Callable[[Any], str]] = None,
    ) -> int:
        """Observe an entire document's extracted relationships.

        Args:
            relationships: iterable of relation-like objects. Each must expose
                ``raw_relationship_type`` (or ``relation_type``),
                ``source_type``/``target_type`` (or ``source_entity_type``/
                ``target_entity_type``), and ``confidence``.
            document_type: a free-form tag for the document's category.
            evidence_lookup: optional callable that returns the evidence text
                for a relation (used when the relation object doesn't carry it
                directly — e.g., chunk text fetched separately).

        Returns:
            Number of observations recorded.
        """
        added = 0
        for rel in relationships:
            phrase = (
                getattr(rel, "raw_relationship_type", None)
                or getattr(rel, "relation_type", None)
                or getattr(rel, "relationship_type", None)
                or ""
            )
            if not phrase:
                continue
            evidence = (
                getattr(rel, "evidence_text", None)
                or getattr(rel, "source_span", None)
                or getattr(rel, "provenance_text", None)
                or getattr(rel, "source_sentence", None)
                or ""
            )
            if not evidence and evidence_lookup is not None:
                try:
                    evidence = evidence_lookup(rel) or ""
                except Exception as e:  # pragma: no cover
                    logger.debug(f"evidence_lookup failed: {e}")
                    evidence = ""

            self.observation_log.append(ObservedPattern(
                source_type=(
                    getattr(rel, "source_type", None)
                    or getattr(rel, "source_entity_type", None)
                    or "UNKNOWN"
                ),
                target_type=(
                    getattr(rel, "target_type", None)
                    or getattr(rel, "target_entity_type", None)
                    or "UNKNOWN"
                ),
                relationship_phrase=phrase,
                source_text=evidence,
                document_type=document_type,
                confidence=float(getattr(rel, "confidence", 0.0) or 0.0),
            ))
            added += 1
        return added

    # -------------------- discovery --------------------
    def discover_types(self) -> List[TypeProposal]:
        """Run all discovery passes and return de-duplicated proposals."""
        proposals: List[TypeProposal] = []
        proposals.extend(self._discover_frequent_unmapped())
        proposals.extend(self._discover_compound_roles())
        # De-dupe by proposed_type (compound-role + raw frequency may overlap)
        by_type: Dict[str, TypeProposal] = {}
        for p in proposals:
            existing = by_type.get(p.proposed_type)
            if existing is None or p.confidence > existing.confidence:
                by_type[p.proposed_type] = p
        return sorted(by_type.values(), key=lambda x: -x.confidence)

    def _discover_frequent_unmapped(self) -> List[TypeProposal]:
        """Cluster 1: predicate phrases the LLM uses repeatedly that aren't
        in the ontology yet."""
        if not self.observation_log:
            return []
        known = self._get_known_types()
        # Index observations by normalised phrase
        groups: Dict[str, List[ObservedPattern]] = defaultdict(list)
        for obs in self.observation_log:
            norm = self._normalize_phrase(obs.relationship_phrase)
            if not norm:
                continue
            groups[norm].append(obs)

        proposals: List[TypeProposal] = []
        for phrase, examples in groups.items():
            if len(examples) < self.min_observations:
                continue
            if phrase in known:
                continue
            source_types = {ex.source_type for ex in examples if ex.source_type}
            target_types = {ex.target_type for ex in examples if ex.target_type}
            doc_types = {ex.document_type for ex in examples if ex.document_type}
            evidence = [ex.source_text for ex in examples if ex.source_text][:3]
            proposals.append(TypeProposal(
                proposed_type=phrase,
                source_types=source_types or {"UNKNOWN"},
                target_types=target_types or {"UNKNOWN"},
                observation_count=len(examples),
                example_evidence=evidence,
                confidence=self._compute_confidence(examples),
                proposal_reason=(
                    f"Observed {len(examples)} times across "
                    f"{len(doc_types)} document types"
                ),
            ))
        return proposals

    def _discover_compound_roles(self) -> List[TypeProposal]:
        """Cluster 2: compound-role patterns ('<Role> of <Org>') that imply
        a subtype of HOLDS_POSITION (e.g. PRESIDENT_OF, VP_OF, DIRECTOR_OF)."""
        if not self.observation_log:
            return []
        known = self._get_known_types()

        # Per base role: count distinct (role_phrase, org) mentions across obs.
        # Using a Counter keyed by mention text gives us evidence + counts.
        per_role_mentions: Dict[str, Counter] = defaultdict(Counter)
        per_role_orgs: Dict[str, Set[str]] = defaultdict(set)
        per_role_obs: Dict[str, List[ObservedPattern]] = defaultdict(list)

        for obs in self.observation_log:
            if not obs.source_text:
                continue
            for match in self._COMPOUND_ROLE_RE.finditer(obs.source_text):
                base_role_raw, org = match.group(1), match.group(2)
                base_role = self._canonical_role(base_role_raw)
                mention = f"{base_role_raw} of {org}".strip()
                per_role_mentions[base_role][mention] += 1
                per_role_orgs[base_role].add(org.strip())
                per_role_obs[base_role].append(obs)

        proposals: List[TypeProposal] = []
        for base_role, mentions in per_role_mentions.items():
            total = sum(mentions.values())
            distinct_orgs = len(per_role_orgs[base_role])
            if total < self.min_observations:
                continue
            if distinct_orgs < self.compound_min_distinct_orgs:
                continue
            proposed = f"{base_role}_OF"
            if proposed in known:
                continue
            doc_types = {ex.document_type for ex in per_role_obs[base_role]}
            evidence = list(mentions.keys())[:5]
            # Confidence blends mention-density, org-diversity, and doc-diversity.
            count_score = min(total, 20) * 0.025      # up to +0.5
            org_score = min(distinct_orgs, 10) * 0.04  # up to +0.4
            doc_score = min(len(doc_types), 5) * 0.03  # up to +0.15
            confidence = round(min(0.5 + count_score + org_score + doc_score, 0.95), 3)
            proposals.append(TypeProposal(
                proposed_type=proposed,
                source_types={"PERSON"},
                target_types={"ORGANIZATION"},
                observation_count=total,
                example_evidence=evidence,
                confidence=confidence,
                proposal_reason=(
                    f"Compound role '{base_role.replace('_', ' ').title()} of X' "
                    f"observed {total} times across {distinct_orgs} distinct "
                    f"organisations and {len(doc_types)} document types"
                ),
                parent_type="HOLDS_POSITION",
            ))
        return proposals

    # -------------------- helpers --------------------
    @staticmethod
    def _normalize_phrase(phrase: str) -> str:
        if not phrase:
            return ""
        p = phrase.strip().upper()
        p = re.sub(r"\s+", "_", p)
        # Strip surrounding punctuation
        p = re.sub(r"[^\w]+", "_", p).strip("_")
        return p

    @staticmethod
    def _canonical_role(role: str) -> str:
        r = role.strip().upper().replace(" ", "_")
        # Normalise common variants
        return {
            "VICE_PRESIDENT": "VP",
            "CHAIRMAN": "CHAIR",
            "CHAIRWOMAN": "CHAIR",
            "CHAIRPERSON": "CHAIR",
        }.get(r, r)

    def _compute_confidence(self, examples: Sequence[ObservedPattern]) -> float:
        count = len(examples)
        type_consistency = len({(ex.source_type, ex.target_type) for ex in examples})
        doc_diversity = len({ex.document_type for ex in examples})
        avg_conf = sum(ex.confidence for ex in examples) / max(count, 1)
        # Per the spec formula, but capped at 0.95 and floored at 0.3
        score = 0.3 + (count * 0.02) + (doc_diversity * 0.08) + (avg_conf * 0.3)
        # Penalise scattered / inconsistent source/target type mixtures
        if type_consistency > 5:
            score -= 0.05
        return round(min(max(score, 0.3), 0.95), 3)

    def _get_known_types(self) -> Set[str]:
        """Return uppercase set of known relationship types from the ontology.

        Resolution order:
          1. Explicit ``known_types`` passed to __init__ (used for tests).
          2. Custom ``known_types_loader`` callable.
          3. ``domain_schema.get_schema_loader()`` + ontology_candidates APPROVED.
        """
        if self._known_types is not None:
            return self._known_types
        if self._known_types_loader is not None:
            try:
                self._known_types = {t.upper() for t in self._known_types_loader()}
                return self._known_types
            except Exception as e:
                logger.warning(f"known_types_loader failed: {e}")

        known: Set[str] = set()
        # YAML schema (the same source the staging loader consults)
        try:
            from ..config.domain_schema import get_schema_loader
            loader = get_schema_loader()
            known |= {t.upper() for t in loader.schema.get_relationship_type_names()}
        except Exception as e:
            logger.debug(f"could not load schema types: {e}")
        # Approved candidates in DB — MUST be tenant-scoped to prevent
        # cross-tenant signal contamination (a type approved by tenant A
        # would otherwise suppress proposals for tenant B).
        if self.session is not None:
            try:
                from sqlalchemy import text
                if self.tenant_id:
                    rows = self.session.execute(text(
                        "SELECT DISTINCT UPPER(normalized_name) FROM ontology_candidates "
                        "WHERE candidate_type='RELATIONSHIP' AND status='APPROVED' "
                        "AND tenant_id = CAST(:tid AS uuid)"
                    ), {"tid": self.tenant_id}).fetchall()
                else:
                    # No tenant scope provided — fall back to unscoped read,
                    # but warn loudly because this can leak signal across
                    # tenants and is only safe for single-tenant test setups.
                    logger.warning(
                        "TypeDiscoveryAgent has no tenant_id; loading "
                        "ontology_candidates unscoped. Pass tenant_id=... "
                        "in production to enforce isolation."
                    )
                    rows = self.session.execute(text(
                        "SELECT DISTINCT UPPER(normalized_name) FROM ontology_candidates "
                        "WHERE candidate_type='RELATIONSHIP' AND status='APPROVED'"
                    )).fetchall()
                known |= {r[0] for r in rows if r[0]}
            except Exception as e:
                logger.debug(f"could not load approved candidates: {e}")
        # ontology.relations ACTIVE (canonical source)
        if self.session is not None:
            try:
                from sqlalchemy import text
                rows = self.session.execute(text(
                    "SELECT UPPER(relation_type) FROM ontology.relations WHERE status='ACTIVE'"
                )).fetchall()
                known |= {r[0] for r in rows if r[0]}
            except Exception as e:
                logger.debug(f"could not load ontology.relations: {e}")

        self._known_types = known
        return known

    # -------------------- persistence --------------------
    def persist_proposals(
        self,
        proposals: Sequence[TypeProposal],
        tenant_id: str,
        auto_approve_confidence: float = 0.85,
        clear_observation_log: bool = True,
    ) -> Tuple[int, int]:
        """Write proposals to the ``ontology_candidates`` table.

        Proposals with confidence >= ``auto_approve_confidence`` are written
        with status='APPROVED' so the staging loader picks them up immediately.
        Lower-confidence proposals are written PENDING for human review.

        Side effects after a successful commit:
          - the cached known-types set is invalidated so the next discovery
            cycle treats just-persisted types as known,
          - the observation_log is cleared (toggle via
            ``clear_observation_log=False`` for tests) to prevent stale-data
            re-proposal.

        Persisted columns capture real signal — actual document_count,
        deterministic source/target type chosen by frequency, and
        example_mentions populated from evidence — rather than placeholder
        values, so downstream review has the data it needs.

        Returns:
            (approved_count, pending_count)
        """
        if self.session is None:
            raise RuntimeError("persist_proposals requires a DB session")
        import json
        from sqlalchemy import text
        approved = 0
        pending = 0
        # Build observation index for accurate per-proposal stats.
        obs_by_norm: Dict[str, List[ObservedPattern]] = defaultdict(list)
        for obs in self.observation_log:
            obs_by_norm[self._normalize_phrase(obs.relationship_phrase)].append(obs)

        for p in proposals:
            status = "APPROVED" if p.confidence >= auto_approve_confidence else "PENDING"
            related_obs = obs_by_norm.get(p.proposed_type, [])
            distinct_doc_types = {o.document_type for o in related_obs if o.document_type}
            doc_count = max(len(distinct_doc_types), 1)
            # Deterministic source/target selection: pick the most common.
            src_counter = Counter(o.source_type for o in related_obs if o.source_type)
            tgt_counter = Counter(o.target_type for o in related_obs if o.target_type)
            src_type = (
                src_counter.most_common(1)[0][0]
                if src_counter
                else (sorted(p.source_types)[0] if p.source_types else "UNKNOWN")
            )
            tgt_type = (
                tgt_counter.most_common(1)[0][0]
                if tgt_counter
                else (sorted(p.target_types)[0] if p.target_types else "UNKNOWN")
            )
            example_mentions = (p.example_evidence or [])[:5]
            properties = {"parent_type": p.parent_type} if p.parent_type else {}
            try:
                self.session.execute(text("""
                    INSERT INTO ontology_candidates (
                        tenant_id, candidate_type, proposed_name, normalized_name,
                        source_entity_type, target_entity_type,
                        detected_properties, example_mentions,
                        document_count, mention_count, confidence_score, status,
                        created_at, updated_at
                    )
                    VALUES (
                        CAST(:tid AS uuid), 'RELATIONSHIP', :proposed, :norm,
                        :src_type, :tgt_type,
                        CAST(:props AS jsonb), CAST(:examples AS jsonb),
                        :doc_count, :mention_count, :conf, :status,
                        NOW(), NOW()
                    )
                    ON CONFLICT DO NOTHING
                """), {
                    "tid": tenant_id,
                    "proposed": p.proposed_type,
                    "norm": p.proposed_type,
                    "src_type": src_type,
                    "tgt_type": tgt_type,
                    "props": json.dumps(properties),
                    "examples": json.dumps(example_mentions),
                    "doc_count": doc_count,
                    "mention_count": p.observation_count,
                    "conf": p.confidence,
                    "status": status,
                })
                if status == "APPROVED":
                    approved += 1
                else:
                    pending += 1
            except Exception as e:
                logger.warning(f"failed to persist proposal {p.proposed_type}: {e}")
        try:
            self.session.commit()
            # Invalidate caches & rotate the observation window so future
            # cycles work on fresh signal and don't re-propose just-persisted
            # types.
            self._known_types = None
            if clear_observation_log:
                self.observation_log = []
        except Exception as e:
            logger.warning(f"commit failed: {e}")
            self.session.rollback()
        return approved, pending
