"""
QueryExecutor — Unified entry point that wires existing query components together.

Replaces scattered routing in retrieval.py / retrieval_router.py / directed_retriever.py
with a single deterministic pipeline:

    1. interpret query → QueryIntent
    2. resolve anchor entity (EntityResolver, with DisambiguationReasoner if multi-candidate)
    3. if intent.target_type == 'PERSON': delegate to RoleResolver (3-stage + multi-hop)
    4. otherwise: traverse ALL relationship types from `ontology.relations`
       (no hardcoded edge list) outbound/inbound from the anchor
    5. if intent.aggregation set: route through AggregationEngine
    6. return a populated ContextBundle

Day-1 wiring rule: this module imports ONLY from existing modules.
No new agents, no new patterns, no new extraction.
"""
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..models.context_bundle import ContextBundle, create_bundle
from ..utils.logger import logger

from .query_interpreter import (
    QueryIntent,
    QueryInterpreter,
    get_query_interpreter,
)
from .aggregation_engine import AggregationEngine, get_aggregation_engine

from ..agents.entity_resolver import EntityResolver, EntityCandidate, ResolveResult
from ..agents.disambiguation_reasoner import DisambiguationReasoner
from ..agents.role_resolver import RoleResolver, RoleResolution

from ..retrieval.anchor_resolver import AnchorResolver, RelationshipFirstRetriever
from ..ontology.repository import get_ontology_repository


class QueryExecutor:
    """Unified query executor — single entry point for KG-grounded retrieval.

    Composes existing components without introducing new ones. The intent is
    to give Context Foundry one deterministic dispatch path so we can stop
    spreading routing logic across multiple modules.
    """

    # Hard cap on how many relationships to pull during the generic anchor traversal.
    DEFAULT_TRAVERSAL_LIMIT = 200

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

        # Lazy-initialised collaborators (imported, never re-implemented).
        self._interpreter: QueryInterpreter = get_query_interpreter()
        self._aggregator: AggregationEngine = get_aggregation_engine()
        self._entity_resolver = EntityResolver(session=session, tenant_id=tenant_id)
        self._disambiguator = DisambiguationReasoner()
        self._role_resolver = RoleResolver(session=session, tenant_id=tenant_id)
        self._anchor_resolver = AnchorResolver(session=session, tenant_id=tenant_id)
        self._rel_first = RelationshipFirstRetriever(session=session, tenant_id=tenant_id)

        # Cached snapshot of all valid relationship types from ontology.relations.
        self._all_rel_types: Optional[List[str]] = None

    # ------------------------------------------------------------------ public

    def execute(
        self,
        query_text: str,
        vault_context: Optional[str] = None,
    ) -> ContextBundle:
        """Run the full query pipeline and return a ContextBundle.

        Args:
            query_text: Raw user query.
            vault_context: Vault / tenant display name (used by DisambiguationReasoner
                to prefer in-vault candidates).
        """
        try:
            return self._execute_inner(query_text, vault_context)
        except Exception as exc:
            logger.error(f"[QUERY_EXECUTOR] pipeline failed: {exc}")
            try:
                self.session.rollback()
            except Exception:
                pass
            bundle = create_bundle(query_text)
            bundle.target_entity_found = False
            bundle.retrieval_metadata["error"] = str(exc)
            bundle.calculate_uncertainty()
            return bundle

    def _execute_inner(
        self,
        query_text: str,
        vault_context: Optional[str],
    ) -> ContextBundle:
        bundle = create_bundle(query_text)

        # 1. Interpret intent ------------------------------------------------
        try:
            intent = self._interpreter.interpret(query_text).intent
        except Exception as exc:  # never crash — graceful degradation
            logger.warning(f"[QUERY_EXECUTOR] interpret failed: {exc}")
            intent = QueryIntent(query_text=query_text)

        bundle.retrieval_metadata["query_intent"] = intent.to_dict()
        logger.info(
            f"[QUERY_EXECUTOR] intent: entity={intent.entity!r} "
            f"target_type={intent.target_type} aggregation={intent.aggregation}"
        )

        # 2. PERSON queries → 3-stage role resolution (incl. multi-hop) -----
        if intent.target_type == "PERSON":
            handled = self._handle_person_query(query_text, intent, bundle)
            if handled:
                bundle.calculate_uncertainty()
                return bundle
            # fall through to generic path if role resolver had nothing to say

        # 3. Resolve the anchor entity --------------------------------------
        anchor = self._resolve_anchor(query_text, intent, vault_context, bundle)
        if anchor is None:
            logger.info("[QUERY_EXECUTOR] No anchor resolved — returning empty bundle")
            bundle.target_entity_name = intent.entity
            bundle.target_entity_found = False
            bundle.calculate_uncertainty()
            return bundle

        bundle.target_entity_name = anchor["name"]
        bundle.target_entity_found = True
        bundle.target_entity_match = anchor
        bundle.semantic_entities.append({
            "id": anchor["id"],
            "name": anchor["name"],
            "entity_type": anchor.get("entity_type"),
            "confidence": anchor.get("confidence", 0.9),
            "role": "anchor",
        })

        # 4. Generic ontology-driven traversal ------------------------------
        rels, neighbors = self._traverse_all_ontology_relations(
            anchor["id"],
            depth=max(1, intent.depth or 1),
            limit=self.DEFAULT_TRAVERSAL_LIMIT,
        )
        bundle.semantic_relationships.extend(rels)
        for n in neighbors:
            if n["id"] != anchor["id"]:
                bundle.semantic_entities.append(n)

        bundle.retrieval_metadata["traversal"] = {
            "anchor_id": anchor["id"],
            "anchor_name": anchor["name"],
            "relationship_types_considered": len(self._get_all_relationship_types()),
            "relationships_found": len(rels),
            "neighbors_found": len(neighbors),
        }

        # 5. Aggregation routing --------------------------------------------
        agg_kind = intent.aggregation or self._aggregator.should_aggregate(query_text)
        if agg_kind:
            self._apply_aggregation(agg_kind, neighbors, query_text, bundle)

        bundle.calculate_uncertainty()
        return bundle

    # ----------------------------------------------------------------- person

    def _handle_person_query(
        self,
        query_text: str,
        intent: QueryIntent,
        bundle: ContextBundle,
    ) -> bool:
        """Use RoleResolver (which already chains Stage-0 graph traversal +
        multi-hop role traversal). Returns True iff we resolved a person."""
        role_text = intent.entity or query_text
        try:
            resolution: RoleResolution = self._role_resolver.resolve_from_anchor(
                role_text, query=query_text
            )
        except Exception as exc:
            logger.warning(f"[QUERY_EXECUTOR] role resolution failed: {exc}")
            return False

        if not resolution.is_resolved:
            logger.info(f"[QUERY_EXECUTOR] role '{role_text}' did not resolve via Stage-0")
            return False

        # If the role resolver returned multiple equally-good matches, route
        # them through the DisambiguationReasoner for a single primary answer.
        all_matches = resolution.all_matches or []
        primary: Dict[str, Any] = {
            "id": resolution.resolved_entity_id,
            "name": resolution.resolved_name,
            "role": role_text,
            "confidence": resolution.confidence,
        }
        if len(all_matches) > 1:
            anchor_for_disamb = ""
            try:
                anchor_info = self._anchor_resolver.get_primary_organization()
                if anchor_info and anchor_info.get("name"):
                    anchor_for_disamb = anchor_info["name"]
            except Exception:
                anchor_for_disamb = ""
            try:
                disamb = self._disambiguator.resolve(
                    query=query_text,
                    matches=all_matches,
                    vault_context=anchor_for_disamb,
                    ambiguity_type="role",
                )
                if disamb.single_answer and disamb.primary_result:
                    primary = disamb.primary_result
                    bundle.retrieval_metadata["disambiguation"] = {
                        "used_llm": disamb.used_llm,
                        "reasoning": disamb.reasoning,
                    }
            except Exception as exc:
                logger.warning(f"[QUERY_EXECUTOR] disambiguation failed: {exc}")

        bundle.target_entity_name = primary.get("name")
        bundle.target_entity_found = True
        bundle.target_entity_match = primary
        bundle.semantic_entities.append({
            "id": primary.get("id") or primary.get("entity_id"),
            "name": primary.get("name"),
            "entity_type": "PERSON",
            "confidence": primary.get("confidence", resolution.confidence),
            "role": role_text,
            "resolution_method": resolution.resolution_method,
        })
        bundle.retrieval_metadata["role_resolution"] = resolution.to_dict()
        return True

    # ----------------------------------------------------------------- anchor

    def _resolve_anchor(
        self,
        query_text: str,
        intent: QueryIntent,
        vault_context: Optional[str],
        bundle: ContextBundle,
    ) -> Optional[Dict[str, Any]]:
        """Resolve the anchor entity for the query.

        Order:
          1. EntityResolver against intent.entity (typed if hint given).
             If multi-candidate, route via DisambiguationReasoner.
          2. AnchorResolver.identify_anchor (vault primary org / explicit mention).
        """
        if intent.entity:
            try:
                result: ResolveResult = self._entity_resolver.resolve(
                    intent.entity,
                    entity_type_hint=intent.entity_type_hint,
                )
            except Exception as exc:
                logger.warning(f"[QUERY_EXECUTOR] entity resolve failed: {exc}")
                result = ResolveResult(match_stage="error")

            chosen: Optional[EntityCandidate] = result.entity
            if result.needs_disambiguation and result.candidates:
                # Use the cheap heuristic picker — no LLM call on the hot path.
                chosen = self._disambiguator.select_best_candidate(
                    result.candidates, query_context=intent.entity
                )
                bundle.retrieval_metadata["entity_disambiguation"] = {
                    "candidate_count": len(result.candidates),
                    "picked": getattr(chosen, "name", None),
                }

            if chosen:
                return {
                    "id": chosen.entity_id,
                    "name": chosen.name,
                    "entity_type": chosen.entity_type,
                    "confidence": chosen.confidence,
                }

        # Fall back to vault anchor (primary organisation).
        try:
            anchor = self._anchor_resolver.identify_anchor(query_text)
        except Exception as exc:
            logger.warning(f"[QUERY_EXECUTOR] anchor identify failed: {exc}")
            anchor = None
        if anchor:
            anchor.setdefault("entity_type", anchor.get("entity_type", "ORGANIZATION"))
            anchor.setdefault("confidence", 0.8)
        return anchor

    # ------------------------------------------------------------- traversal

    def _get_all_relationship_types(self) -> List[str]:
        """Return ALL relationship types from `ontology.relations` — never hardcoded.

        Falls back to an empty list if the ontology table is unavailable, in
        which case the SQL traversal will simply find nothing.
        """
        if self._all_rel_types is not None:
            return self._all_rel_types
        try:
            repo = get_ontology_repository()
            relations = repo.get_all_relations()
            seen = []
            seen_set = set()
            for rel in relations:
                rt = (rel.relation_type or "").strip()
                if rt and rt not in seen_set:
                    seen_set.add(rt)
                    seen.append(rt)
            self._all_rel_types = seen
            logger.info(
                f"[QUERY_EXECUTOR] loaded {len(seen)} relationship types from ontology.relations"
            )
        except Exception as exc:
            logger.warning(f"[QUERY_EXECUTOR] ontology relations load failed: {exc}")
            self._all_rel_types = []
        return self._all_rel_types

    def _traverse_all_ontology_relations(
        self,
        anchor_id: str,
        depth: int = 1,
        limit: int = 200,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generic traversal: pull every relationship from the anchor whose
        type belongs to the ontology — no hardcoded edge list.

        Returns (relationships, neighbor_entities) as plain dicts ready to put
        into a ContextBundle.
        """
        rel_types = self._get_all_relationship_types()
        if not rel_types:
            # No ontology — fall back to "all relationships" so we still have data.
            type_filter_sql = ""
            params: Dict[str, Any] = {
                "anchor_id": anchor_id,
                "tenant_id": self.tenant_id,
                "limit": limit,
            }
        else:
            placeholders = []
            params = {
                "anchor_id": anchor_id,
                "tenant_id": self.tenant_id,
                "limit": limit,
            }
            for i, rt in enumerate(rel_types):
                key = f"rt_{i}"
                placeholders.append(f":{key}")
                params[key] = rt
            type_filter_sql = f"AND r.relationship_type IN ({', '.join(placeholders)})"

        query = sql_text(f"""
            SELECT
                r.id              AS relationship_id,
                r.relationship_type,
                r.source_id, r.target_id,
                r.confidence,
                src.name          AS source_name,
                src.entity_type   AS source_type,
                tgt.name          AS target_name,
                tgt.entity_type   AS target_type,
                CASE WHEN r.source_id = :anchor_id THEN 'outbound' ELSE 'inbound' END AS direction
            FROM relationships r
            JOIN entities src ON r.source_id = src.id
            JOIN entities tgt ON r.target_id = tgt.id
            WHERE r.tenant_id = :tenant_id
              AND (r.source_id = :anchor_id OR r.target_id = :anchor_id)
              {type_filter_sql}
            ORDER BY r.confidence DESC NULLS LAST, r.relationship_type
            LIMIT :limit
        """)

        try:
            rows = self.session.execute(query, params).fetchall()
        except Exception as exc:
            logger.error(f"[QUERY_EXECUTOR] traversal SQL failed: {exc}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return [], []

        rels: List[Dict[str, Any]] = []
        neighbors: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            rels.append({
                "relationship_id": str(row.relationship_id),
                "relationship_type": row.relationship_type,
                "source_id": str(row.source_id),
                "source_name": row.source_name,
                "source_type": row.source_type,
                "target_id": str(row.target_id),
                "target_name": row.target_name,
                "target_type": row.target_type,
                "direction": row.direction,
                "confidence": float(row.confidence) if row.confidence is not None else 0.7,
                "depth": 1,
            })
            # Neighbour = the entity on the OTHER side of the anchor.
            if str(row.source_id) == str(anchor_id):
                nid, nname, ntype = str(row.target_id), row.target_name, row.target_type
            else:
                nid, nname, ntype = str(row.source_id), row.source_name, row.source_type
            if nid not in neighbors:
                neighbors[nid] = {
                    "id": nid,
                    "name": nname,
                    "entity_type": ntype,
                    "confidence": float(row.confidence) if row.confidence is not None else 0.7,
                    "discovered_via": row.relationship_type,
                }

        # Optional 2nd hop — only expand if intent.depth requested it.
        if depth > 1 and neighbors:
            extra_rels, extra_neighbors = self._expand_one_hop(
                list(neighbors.keys()), rel_types, anchor_id, limit
            )
            rels.extend(extra_rels)
            for n in extra_neighbors:
                neighbors.setdefault(n["id"], n)

        return rels, list(neighbors.values())

    def _expand_one_hop(
        self,
        seed_ids: List[str],
        rel_types: List[str],
        anchor_id: str,
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not seed_ids:
            return [], []
        params: Dict[str, Any] = {"tenant_id": self.tenant_id, "limit": limit}
        seed_ph = []
        for i, sid in enumerate(seed_ids):
            k = f"sid_{i}"
            seed_ph.append(f":{k}")
            params[k] = sid
        type_sql = ""
        if rel_types:
            type_ph = []
            for i, rt in enumerate(rel_types):
                k = f"hop_rt_{i}"
                type_ph.append(f":{k}")
                params[k] = rt
            type_sql = f"AND r.relationship_type IN ({', '.join(type_ph)})"

        query = sql_text(f"""
            SELECT r.id AS relationship_id, r.relationship_type,
                   r.source_id, r.target_id, r.confidence,
                   src.name AS source_name, src.entity_type AS source_type,
                   tgt.name AS target_name, tgt.entity_type AS target_type
            FROM relationships r
            JOIN entities src ON r.source_id = src.id
            JOIN entities tgt ON r.target_id = tgt.id
            WHERE r.tenant_id = :tenant_id
              AND (r.source_id IN ({', '.join(seed_ph)}) OR r.target_id IN ({', '.join(seed_ph)}))
              {type_sql}
            ORDER BY r.confidence DESC NULLS LAST
            LIMIT :limit
        """)
        try:
            rows = self.session.execute(query, params).fetchall()
        except Exception as exc:
            logger.warning(f"[QUERY_EXECUTOR] hop-2 SQL failed: {exc}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return [], []

        rels: List[Dict[str, Any]] = []
        neighbors: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            rels.append({
                "relationship_id": str(row.relationship_id),
                "relationship_type": row.relationship_type,
                "source_id": str(row.source_id),
                "source_name": row.source_name,
                "source_type": row.source_type,
                "target_id": str(row.target_id),
                "target_name": row.target_name,
                "target_type": row.target_type,
                "confidence": float(row.confidence) if row.confidence is not None else 0.6,
                "depth": 2,
            })
            for nid, nname, ntype in (
                (str(row.source_id), row.source_name, row.source_type),
                (str(row.target_id), row.target_name, row.target_type),
            ):
                if nid != anchor_id and nid not in neighbors:
                    neighbors[nid] = {
                        "id": nid,
                        "name": nname,
                        "entity_type": ntype,
                        "confidence": 0.6,
                        "depth": 2,
                    }
        return rels, list(neighbors.values())

    # --------------------------------------------------------------- aggregation

    def _apply_aggregation(
        self,
        agg_kind: str,
        neighbors: List[Dict[str, Any]],
        query_text: str,
        bundle: ContextBundle,
    ) -> None:
        """Route to AggregationEngine and stash the result on the bundle."""
        try:
            if agg_kind == "list":
                result = self._aggregator.handle_list_query(neighbors)
            elif agg_kind == "count":
                result = self._aggregator.handle_count_query(neighbors)
            elif agg_kind == "max":
                result = self._aggregator.handle_max_query(neighbors, attribute="budget")
            elif agg_kind == "min":
                result = self._aggregator.handle_min_query(neighbors, attribute="budget")
            elif agg_kind == "sum":
                result = self._aggregator.handle_sum_query(neighbors, attribute="value")
            else:
                return
        except Exception as exc:
            logger.warning(f"[QUERY_EXECUTOR] aggregation '{agg_kind}' failed: {exc}")
            return

        bundle.is_aggregation_query = True
        bundle.aggregation_type = agg_kind
        bundle.aggregation_count = len(neighbors)
        bundle.aggregation_result = result
        bundle.counted_entities = neighbors[:50]
        bundle.retrieval_metadata["aggregation"] = {
            "kind": agg_kind,
            "result": getattr(result, "result", None),
            "source_entity_count": len(getattr(result, "source_entities", []) or []),
        }


__all__ = ["QueryExecutor"]
