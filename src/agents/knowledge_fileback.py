"""
Knowledge File-back — post-query entity confidence adjustment.

After a query is answered, boosts confidence of entities that contributed
to a successful response, and demotes entities involved in low-confidence answers.
"""

from typing import Dict, Any
from uuid import UUID

from src.agents.gardener import GardenerAgent


class KnowledgeFileBack:
    """Post-query feedback loop from query results back into the graph."""

    BOOST_DELTA = 0.01
    DEMOTE_DELTA = 0.02
    LOW_CONFIDENCE_THRESHOLD = 0.4

    def __init__(self, db_manager):
        self.db = db_manager
        self.gardener = GardenerAgent(db_manager)

    async def process(self, query: str, response, bundle) -> Dict[str, Any]:
        """
        Adjust entity confidence based on query outcome.

        Args:
            query: The original query text.
            response: ReasoningResponse from the reasoning agent.
            bundle: ContextBundle with semantic_entities.

        Returns:
            Stats dict with entities_boosted and entities_demoted.
        """
        entities = bundle.semantic_entities or []
        if not entities:
            return {"entities_boosted": 0, "entities_demoted": 0}

        boosted = 0
        demoted = 0

        if response.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            # Low confidence response — demote accessed entities
            for entity in entities:
                entity_id = entity.get("entity_id")
                if not entity_id:
                    continue
                try:
                    await self.gardener.decrease_confidence(
                        entity_id, self.DEMOTE_DELTA, "low_confidence_query"
                    )
                    demoted += 1
                except Exception:
                    pass
        else:
            # Normal/high confidence — boost accessed entities
            for entity in entities:
                entity_id = entity.get("entity_id")
                if not entity_id:
                    continue
                try:
                    await self.gardener.increase_confidence(
                        entity_id, self.BOOST_DELTA, "query_access"
                    )
                    boosted += 1
                except Exception:
                    pass

        return {"entities_boosted": boosted, "entities_demoted": demoted}
