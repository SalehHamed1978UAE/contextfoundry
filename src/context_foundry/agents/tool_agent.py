"""
Tool-Calling Agent for Context Foundry.

Implements ReAct-style reasoning: Think → Tool Call → Observe → Repeat → Answer

Enhanced with Query Pipeline for intelligent routing:
- QueryClassifier: Detects query type, role references, list expectations
- RoleResolver: Resolves role references (CEO → Sarah Chen)
- RetrievalRouter: Routes to optimal retrieval strategy
"""
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from .tools.definitions import TOOL_DEFINITIONS
from .tools.wrappers import ToolExecutor
from .retrieval_router import QueryPipeline, RetrievalResult, AmbiguityResult
from .disambiguation_reasoner import DisambiguationReasoner, DisambiguationResult
from .query_interpreter import QueryInterpreter, QueryIntent
from .directed_retriever import DirectedGraphRetriever, RetrievalResult as DirectedRetrievalResult
from ..models.schema import set_tenant_context
from ..utils.response_helpers import build_qa_evidence, calculate_confidence, build_response, QAEvidence
from ..rlm.router import QueryComplexityRouter, QueryTier
from ..rlm.executor import execute_rlm_query

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = '''You are Context Foundry, an AI assistant with access to a knowledge graph and documents.

RULES:
0. ANSWER FORMAT: Answer the question directly and concisely. Lead with the specific answer (name, number, date, supplier) in the first sentence. If needed, follow with one sentence of supporting context. Avoid lengthy preambles like "The X is provided by..." - just state the answer.
1. For entity/relationship COUNTS (how many X, count of Y), use run_aggregation. Never guess counts.
2. For FINANCIAL VALUES (backlog, revenue, budget, metrics, dollar amounts), use search_documents - these are stored in documents, not the knowledge graph.
3. Always resolve_entities FIRST before KG operations to get canonical IDs.
4. For ambiguous queries, use discover_relationships to see what data exists before counting.
5. Use get_knowledge_bundle to fetch relationship details after you know what types exist.
6. Use search_documents for information not in structured data.
7. IGNORE document metadata fields like "Document Owner", "Classification", "Version", "Effective Date" in document content. These are NOT people or entities - they are metadata headers. Never treat "Document Owner" as a person's name or role.

HANDLING AMBIGUOUS QUERIES:
When queries use ambiguous terms like "jobs", "work", "projects", "experience", "connections":
1. FIRST call discover_relationships to see what relationship types exist with counts
2. Reason about which types are relevant to the user's intent
3. Call get_knowledge_bundle for the relevant relationship types to get details
4. Provide complete answer covering all relevant interpretations

QUERY PATTERNS - ALWAYS use resolve_entities + discover_relationships:

1. PERSON queries ("How many jobs has X done?"):
   - resolve_entities("X") → get entity_id
   - discover_relationships(entity_id) → shows HOLDS_POSITION (7), WORKED_AT (7), etc.
   - Answer with counts from discover_relationships

2. EVENT queries ("How many speakers at X Summit?"):
   - resolve_entities("X Summit") → get entity_id for the EVENT
   - discover_relationships(entity_id) → shows incoming SPEAKS_AT (12), PRESENTS_AT (5), etc.
   - Answer: "X Summit has 12 speakers" (from SPEAKS_AT count)

3. ORGANIZATION queries ("How many subsidiaries does X have?"):
   - resolve_entities("X") → get entity_id
   - discover_relationships(entity_id) → shows outgoing OWNS (6), HAS_SUBSIDIARY (3), etc.
   - Answer with counts from discover_relationships

4. INVESTMENT queries ("How many companies has X invested in?"):
   - resolve_entities("X") → get entity_id
   - discover_relationships(entity_id) → shows outgoing INVESTED_IN (12), FUNDED (5), etc.
   - Answer with counts from discover_relationships

5. AUTHORSHIP queries ("How many authors wrote X paper?"):
   - resolve_entities("X paper") → get entity_id for the DOCUMENT
   - discover_relationships(entity_id) → shows incoming AUTHORED (5), WROTE (3), etc.
   - Answer with counts from discover_relationships

IMPORTANT: NEVER skip resolve_entities. Always resolve the entity first, then discover its relationships.

TOOLS:
- resolve_entities: Look up entity IDs by name. Returns canonical IDs, confidence, disambiguation candidates.
- discover_relationships: See all relationship types for an entity with counts. Use for ambiguous queries.
- run_aggregation: Get exact counts/sums. Returns result_kind: EXACT, LOWER_BOUND ("at least N"), or RANGE.
- get_knowledge_bundle: Get ALL relationships and context for entities. Shows relationship_summary with type counts.
- search_documents: Search uploaded documents via vector similarity.

When answering:
1. Think about what tools you need AND whether the query is ambiguous
2. For ambiguous terms, discover what relationships exist FIRST
3. For numbers, cite result_kind (e.g., "exactly 7" for EXACT, "at least 7" for LOWER_BOUND)
4. Compose response that addresses all reasonable interpretations
5. For enumeration questions, list ALL items - do NOT summarize'''


class ToolAgent:
    """
    ReAct-style tool-calling agent.
    
    Usage:
        agent = ToolAgent(session, tenant_id)
        response = agent.query("How many jobs has Saleh done?", conversation_history=[])
    """
    
    MAX_TOOL_CALLS = 5
    TOOL_TIMEOUT = 10.0
    
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        model: str = "gpt-4o-mini"
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.model = model
        set_tenant_context(session, tenant_id)
        
        self.tool_executor = ToolExecutor(session, tenant_id)
        self.query_pipeline = QueryPipeline(session, tenant_id)
        self.disambiguator = DisambiguationReasoner(model=model)
        self.complexity_router = QueryComplexityRouter(complexity_threshold=0.10)
        
        self.query_interpreter = QueryInterpreter(model=model, session=session, tenant_id=tenant_id)
        self.directed_retriever = DirectedGraphRetriever(session, tenant_id)
        
        self.client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
    
    def _build_context_injection(self, pipeline_result: RetrievalResult) -> str:
        """Build context string from pipeline pre-processing results."""
        context_parts = []
        
        if pipeline_result.role_resolution and pipeline_result.role_resolution.is_resolved:
            role = pipeline_result.role_resolution.role
            name = pipeline_result.role_resolution.resolved_name
            context_parts.append(f"ROLE RESOLVED: {role} = {name}")
        
        if pipeline_result.classification:
            cls = pipeline_result.classification
            if cls.expects_list:
                context_parts.append(f"NOTE: This query expects a LIST of results (use limit=15)")
            if cls.query_type:
                context_parts.append(f"QUERY TYPE: {cls.query_type}")
        
        if pipeline_result.entities:
            entity_names = [e['name'] for e in pipeline_result.entities[:5]]
            context_parts.append(f"PRE-FETCHED ENTITIES: {', '.join(entity_names)}")
        
        if pipeline_result.relationships:
            rel_summary = {}
            for r in pipeline_result.relationships[:10]:
                rel_type = r.get('type', 'UNKNOWN')
                rel_summary[rel_type] = rel_summary.get(rel_type, 0) + 1
            rel_str = ", ".join([f"{k}({v})" for k, v in rel_summary.items()])
            context_parts.append(f"PRE-FETCHED RELATIONSHIPS: {rel_str}")
        
        if pipeline_result.chunks:
            doc_names = list(set([c.get('document', 'Unknown') for c in pipeline_result.chunks[:5]]))
            context_parts.append(f"PRE-FETCHED DOCUMENTS: {', '.join(doc_names[:3])}")
            chunks_preview = []
            for chunk in pipeline_result.chunks[:3]:
                text = chunk.get('text', '')[:200]
                chunks_preview.append(f"- {text}...")
            if chunks_preview:
                context_parts.append("DOCUMENT EXCERPTS:\n" + "\n".join(chunks_preview))
        
        if context_parts:
            return "\n\n[PRE-PROCESSING CONTEXT]\n" + "\n".join(context_parts) + "\n[END PRE-PROCESSING]"
        return ""
    
    def _can_answer_directly(self, pipeline_result: RetrievalResult) -> bool:
        """
        Determine if pre-retrieval gathered enough to answer without tool loop.
        
        This is the KEY DECISION POINT:
        - True → Synthesize directly from pre-fetched data (skip tools)
        - False → Run ReAct tool loop
        """
        if not pipeline_result or not pipeline_result.classification:
            return False
        
        classification = pipeline_result.classification
        num_chunks = len(pipeline_result.chunks)
        num_entities = len(pipeline_result.entities)
        num_relationships = len(pipeline_result.relationships)
        has_resolved_role = pipeline_result.role_resolution and pipeline_result.role_resolution.is_resolved
        
        if has_resolved_role and num_chunks >= 3:
            logger.info(f"[AGENT] Direct answer: role resolved + {num_chunks} chunks")
            return True
        
        # PERSON_DOCS_FALLBACK: When KG entity lookup fails but documents have relevant info
        if pipeline_result.strategy_used == "PERSON_DOCS_FALLBACK" and num_chunks >= 3:
            logger.info(f"[AGENT] Direct answer: person docs fallback with {num_chunks} chunks")
            return True
        
        if classification.query_type == "RELATIONSHIP" and num_relationships >= 1:
            logger.info(f"[AGENT] Direct answer: relationship query + {num_relationships} relationships found")
            return True
        
        if classification.query_type == "ATTRIBUTE" and num_chunks >= 2:
            logger.info(f"[AGENT] Direct answer: attribute query + {num_chunks} chunks")
            return True
        
        if classification.query_type == "EXPLORATION":
            if num_chunks >= 3:
                logger.info(f"[AGENT] Direct answer: exploration + {num_chunks} chunks")
                return True
            if num_entities >= 1 and num_relationships >= 2:
                logger.info(f"[AGENT] Direct answer: exploration + entity with {num_relationships} relationships")
                return True
        
        if classification.query_type == "AGGREGATION" and classification.expects_list:
            if num_chunks >= 5 or num_relationships >= 3:
                logger.info(f"[AGENT] Direct answer: aggregation with list data")
                return True
        
        logger.info(f"[AGENT] Insufficient for direct answer: type={classification.query_type}, "
                    f"chunks={num_chunks}, entities={num_entities}, rels={num_relationships}")
        return False
    
    def _synthesize_direct_answer(self, question: str, pipeline_result: RetrievalResult, intent: Optional[QueryIntent] = None) -> str:
        """Synthesize answer directly from pre-fetched data without tool calls."""
        logger.info(f"[TOOL_AGENT] _synthesize_direct_answer: question='{question[:80]}...'")
        logger.info(f"[TOOL_AGENT] Pipeline result: entities={len(pipeline_result.entities) if pipeline_result.entities else 0}, "
                    f"rels={len(pipeline_result.relationships) if pipeline_result.relationships else 0}, "
                    f"chunks={len(pipeline_result.chunks) if pipeline_result.chunks else 0}")
        if pipeline_result.entities:
            for e in pipeline_result.entities[:5]:
                logger.info(f"[TOOL_AGENT] Entity: {e.get('name')} ({e.get('type')})")
        if pipeline_result.role_resolution and pipeline_result.role_resolution.is_resolved:
            logger.info(f"[TOOL_AGENT] Role resolution: {pipeline_result.role_resolution.role} = {pipeline_result.role_resolution.resolved_name}")
        context_parts = []
        
        classification = pipeline_result.classification
        expects_list = classification.expects_list if classification else False
        is_attribute_query = classification.query_type == "ATTRIBUTE" if classification else False
        is_supplier_query = 'SUPPLIER' in (pipeline_result.strategy_used or '')
        
        entity_limit = 15 if is_supplier_query else (10 if expects_list else 5)
        rel_limit = 25 if is_supplier_query else (20 if expects_list else 10)
        chunk_limit = 10 if expects_list else 5
        chunk_text_limit = 2500 if (expects_list or is_attribute_query) else 1500  # Increased to preserve full financial data
        
        if pipeline_result.role_resolution and pipeline_result.role_resolution.is_resolved:
            context_parts.append(f"Role resolution: {pipeline_result.role_resolution.role} = {pipeline_result.role_resolution.resolved_name}")
        
        if pipeline_result.entities:
            entity_details = []
            for e in pipeline_result.entities[:entity_limit]:
                entity_str = f"{e['name']} ({e['type']})"
                # Include entity properties if available
                if e.get('properties'):
                    props = e['properties']
                    prop_strs = []
                    for k, v in props.items():
                        if v and k not in ('_sources', '_layer', '_confidence', 'source_document'):
                            prop_strs.append(f"{k}: {v}")
                    if prop_strs:
                        entity_str += f" - Properties: {', '.join(prop_strs)}"
                entity_details.append(entity_str)
            context_parts.append(f"Entities found:\n" + "\n".join(entity_details))
        
        if pipeline_result.relationships:
            rel_info = []
            for r in pipeline_result.relationships[:rel_limit]:
                rel_info.append(f"{r.get('source', '?')} --[{r.get('type', '?')}]--> {r.get('target', '?')}")
            context_parts.append(f"Relationships:\n" + "\n".join(rel_info))
        
        if pipeline_result.chunks:
            context_parts.append("Document content:")
            
            # For ranking queries, prioritize chunks with "Total" patterns (financial tables)
            chunks_to_use = pipeline_result.chunks
            if classification and getattr(classification, 'has_ranking_intent', False):
                import re
                total_pattern = re.compile(r'\bTotal[:\s]*\$[\d,\.]+|\$[\d,\.]+\s*(million|billion|M|B)\b', re.IGNORECASE)
                
                # Separate table-like chunks (with Total patterns) from regular chunks
                table_chunks = []
                regular_chunks = []
                for chunk in pipeline_result.chunks:
                    text = chunk.get('text', '')
                    if total_pattern.search(text):
                        table_chunks.append(chunk)
                        logger.info(f"[RANKING] Boosted table chunk from: {chunk.get('document', 'Unknown')}")
                    else:
                        regular_chunks.append(chunk)
                
                # Put table chunks first, then regular chunks
                chunks_to_use = table_chunks + regular_chunks
                if table_chunks:
                    logger.info(f"[RANKING] Prioritized {len(table_chunks)} table chunks for ranking query")
            
            for chunk in chunks_to_use[:chunk_limit]:
                text = chunk.get('text', '')[:chunk_text_limit]
                doc = chunk.get('document', 'Unknown')
                context_parts.append(f"\n[From {doc}]\n{text}")
        
        context = "\n\n".join(context_parts)
        
        list_instruction = ""
        if expects_list:
            list_instruction = "\n\nIMPORTANT: This question expects a LIST of items. Make sure to enumerate ALL items mentioned in the retrieved information. Do not stop at just one example - list every relevant item you can find in the data."
        
        # Question-type-aware prompting for better answer synthesis
        # Only apply role/ownership prompt constraints when KG relationships are actually present
        query_lower = question.lower()
        question_type_instruction = ""
        
        # Check if we have role-related relationships from KG
        has_role_relationships = any(
            r.get('type') in ('HOLDS_POSITION', 'HAS_ROLE', 'WORKS_AS', 'IS_A') 
            for r in pipeline_result.relationships
        ) if pipeline_result.relationships else False
        
        # Check if we have ownership/structure relationships from KG
        has_ownership_relationships = any(
            r.get('type') in ('OWNS', 'OWNED_BY', 'BELONGS_TO', 'MANAGES', 'HANDLES', 'PART_OF', 'HAS_UNIT', 'CONTAINS')
            for r in pipeline_result.relationships
        ) if pipeline_result.relationships else False
        
        if 'responsibilities' in query_lower or 'duties' in query_lower:
            question_type_instruction = "\n\nIMPORTANT: This question asks about RESPONSIBILITIES or DUTIES. Return a concise list of responsibilities/duties. Do NOT just return the person's name or title."
        
        elif ("'s role" in query_lower or "role of" in query_lower) and has_role_relationships:
            question_type_instruction = "\n\nIMPORTANT: This question asks about a person's ROLE or JOB TITLE. Return ONLY the job title (e.g., 'CEO', 'CFO', 'CTO'). Do NOT return a description of the person. If you see a relationship like 'HOLDS_POSITION', extract the position name from it."
        
        elif ("'s position" in query_lower or "position of" in query_lower) and has_role_relationships:
            question_type_instruction = "\n\nIMPORTANT: This question asks about a person's POSITION or TITLE. Return the specific position/title. Look for HOLDS_POSITION relationships in the data."
        
        elif ("who is" in query_lower or "who's" in query_lower) and has_role_relationships:
            question_type_instruction = "\n\nIMPORTANT: This question asks WHO someone is. Provide their name and role/title if available from HOLDS_POSITION relationships."
        
        elif "which" in query_lower and ("owns" in query_lower or "handles" in query_lower or "responsible" in query_lower) and has_ownership_relationships:
            question_type_instruction = "\n\nIMPORTANT: This question asks about OWNERSHIP or RESPONSIBILITY. Look for relationships that show ownership or assignment, and return the owning entity/unit."
        
        elif ("belongs to" in query_lower or "part of" in query_lower) and has_ownership_relationships:
            question_type_instruction = "\n\nIMPORTANT: This question asks about organizational membership or structure. Look for relationships showing containment or membership."
        
        # Ranking query instruction - help LLM identify and compare values
        ranking_instruction = ""
        has_ranking_intent = classification.has_ranking_intent if classification else False
        ranking_type = classification.ranking_type if classification else None
        
        if has_ranking_intent:
            ranking_direction = "highest/largest" if ranking_type in ('largest', 'top_n') else "lowest/smallest" if ranking_type == 'smallest' else "ranked"
            ranking_instruction = f"""\n\nRANKING QUERY INSTRUCTION:
This is a RANKING query looking for the {ranking_direction} value.
1. Look for financial values (dollar amounts with $, million, M, billion, B) in the retrieved documents
2. Compare the TOTAL or AGGREGATE values for each entity (not partial contract values)
3. When multiple values exist for an entity, use the LARGEST/TOTAL value for comparison
4. Look for patterns like "Total: $X" or "Total Contract Value: $X" which indicate the full amount
5. Answer with the entity that has the {ranking_direction} total value based on the documents"""
        
        # Component-supplier matching instruction for specific component queries
        component_supplier_instruction = ""
        if is_supplier_query or any(term in query_lower for term in ['provides', 'supplies', 'supplier', 'vendor', 'manufacturer']):
            component_supplier_instruction = """\n\nCOMPONENT-SUPPLIER MATCHING RULE:
When asked about a SPECIFIC component (SAR radar, flight computers, electrolyzers, etc.), ONLY mention the supplier for THAT EXACT component.
- "Who provides SAR radar?" → ONLY Raytheon (NOT Honeywell - Honeywell provides flight computers)
- "Who provides flight computers?" → ONLY Honeywell (NOT Raytheon - Raytheon provides SAR radar)
If the context lists multiple suppliers with different components, match the supplier to the specific component asked about. Do NOT list all suppliers."""
        
        # KG prioritization instruction for person/role queries
        kg_prioritization = ""
        if pipeline_result.relationships and ('role' in query_lower or 'position' in query_lower or 'who is' in query_lower):
            kg_prioritization = "\n\nWhen answering person/role questions, prioritize the Relationships data (e.g., HOLDS_POSITION, HAS_ROLE) over document content. The relationship data is the authoritative source for organizational roles."
        
        intent_guidance = ""
        if intent:
            if intent.target_type:
                intent_guidance = f"\n\nUser is asking for: {intent.target_type}"
            if intent.query_type == "property_lookup":
                intent_guidance += "\nProvide the specific attribute value, not a description."
            if intent.reasoning:
                intent_guidance += f"\nQuery interpretation: {intent.reasoning}"
        
        synthesis_prompt = f"""Based on the following retrieved information, answer the user's question.

QUESTION: {question}

RETRIEVED INFORMATION:
{context}

Provide a clear, comprehensive answer based on the information above. If specific data is present, include it. If the information is incomplete, acknowledge what is known and what is not.{list_instruction}{question_type_instruction}{ranking_instruction}{component_supplier_instruction}{kg_prioritization}{intent_guidance}"""

        try:
            max_tokens = 900 if expects_list else 600
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided information."},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.0,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content or "Unable to generate answer."
        except Exception as e:
            logger.error(f"[AGENT] Direct synthesis failed: {e}")
            return f"Error synthesizing answer: {str(e)}"
    
    def _synthesize_from_kg(
        self,
        question: str,
        kg_result: DirectedRetrievalResult,
        intent: QueryIntent,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Synthesize answer directly from KG data without document search.
        
        This is the KG-first path where the answer comes purely from
        structured knowledge graph data.
        """
        logger.info(f"[AGENT] Synthesizing from KG: entity='{kg_result.entity_name}', rels={len(kg_result.relationships)}")
        
        context_parts = []
        context_parts.append(f"Entity: {kg_result.entity_name} ({kg_result.entity_type})")
        source_docs = set()
        
        if kg_result.relationships:
            rel_lines = []
            for rel in kg_result.relationships[:20]:
                rel_lines.append(f"- {rel.source_name} --[{rel.relationship_type}]--> {rel.target_name}")
                if hasattr(rel, 'source_location') and rel.source_location:
                    source_docs.add(rel.source_location)
            context_parts.append(f"Relationships:\n" + "\n".join(rel_lines))
            if source_docs:
                context_parts.append(f"Source documents: {', '.join(list(source_docs)[:5])}")
        
        context = "\n\n".join(context_parts)
        
        intent_guidance = ""
        if intent.target_type:
            intent_guidance = f"\nUser is asking for: {intent.target_type}"
        if intent.query_type == "property_lookup":
            intent_guidance += "\nProvide the specific attribute value, not a description."
        if intent.reasoning:
            intent_guidance += f"\nQuery interpretation: {intent.reasoning}"
        
        prompt = f"""Question: {question}
{intent_guidance}

Knowledge Graph data:
{context}

Answer the specific question asked based on the structured data above.
Match your answer type to what was asked. If asking for a role, give the role. If asking for a list, enumerate all items."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.0
            )
            answer = response.choices[0].message.content or "Unable to generate answer."
        except Exception as e:
            logger.error(f"[AGENT] KG synthesis failed: {e}")
            answer = f"Error synthesizing answer from knowledge graph: {str(e)}"
        
        evidence = QAEvidence(
            entity_names=[kg_result.entity_name] if kg_result.entity_name else [],
            chunk_sources=list(source_docs)[:5]
        )
        evidence.relationship_count = len(kg_result.relationships)
        evidence.entity_count = 1
        
        confidence = calculate_confidence("SUPPORTED", evidence, answer)
        
        return build_response(
            answer=answer,
            confidence=confidence,
            qa_verdict={"status": "SUPPORTED", "reason": "Answered from Knowledge Graph"},
            evidence=evidence,
            iterations=0,
            time_ms=int((time.time() - start_time) * 1000),
            success=True,
            pipeline_result=None,
            extra={
                "mode": "KG_FIRST",
                "intent_entity": intent.entity,
                "intent_type": intent.query_type,
                "relationship_count": len(kg_result.relationships),
                "answer_source": "knowledge_graph"
            }
        )
    
    def _extract_anchor_org_name(self, vault_context: str) -> Optional[str]:
        """
        Extract the primary organization name from vault context.
        
        Examples:
        - "ClaudeCode Nexus Industries 3 - 1/28/2026" -> "Nexus Industries"
        - "Manus Medsync Corp - 2/1/2026" -> "Medsync Corp"
        - "Orion Technologies Q1" -> "Orion Technologies"
        """
        import re
        
        if not vault_context:
            return None
        
        name_part = vault_context
        for pattern in [r'\s*-\s*\d+/\d+/\d+', r'\s*\d+\s*-', r'\s*Q[1-4]\s*$', r'\s*\d{4}$']:
            name_part = re.sub(pattern, '', name_part)
        
        for prefix in ['ClaudeCode ', 'Manus ', 'Test ', 'Demo ']:
            if name_part.startswith(prefix):
                name_part = name_part[len(prefix):]
        
        name_part = re.sub(r'\s+\d+$', '', name_part).strip()
        
        return name_part if name_part else None
    
    def _get_vault_matching_org(self, match: Dict[str, Any], vault_context: Optional[str]) -> Optional[str]:
        """
        Find the organization from match that best matches vault context.
        
        If the match has multiple organizations (e.g., TechVentures, HR Operations),
        return the one that matches the vault context for display purposes.
        """
        if not vault_context:
            orgs = match.get("organizations", [])
            return orgs[0] if orgs else match.get("organization")
        
        vault_lower = vault_context.lower()
        vault_words = [w.lower() for w in vault_context.split() if len(w) > 2]
        
        organizations = match.get("organizations", [])
        if not organizations and match.get("organization"):
            organizations = [match.get("organization")]
        
        for org in organizations:
            org_lower = (org or "").lower()
            if org_lower in vault_lower or vault_lower in org_lower:
                return org
            for word in vault_words:
                if word in org_lower:
                    return org
        
        return organizations[0] if organizations else match.get("organization")
    
    def _build_disambiguation_response(
        self,
        question: str,
        pipeline_result,
        start_time: float,
        vault_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a response for ambiguous queries using LLM reasoning.
        
        This method uses DisambiguationReasoner to determine:
        1. Fast path: Single match or exact vault match → direct answer
        2. LLM reasoning: Determine best match based on vault context
        
        If a clear primary answer is found, returns that answer with alternatives.
        Otherwise, asks user to clarify.
        """
        ambiguity = pipeline_result.ambiguity
        ambiguity_type = ambiguity.ambiguity_type if ambiguity else "item"
        query_term = ambiguity.query_term if ambiguity else "the item"
        all_matches = ambiguity.matches if ambiguity else []
        
        disambiguation_result = self.disambiguator.resolve(
            query=question,
            matches=all_matches,
            vault_context=vault_context or "",
            ambiguity_type=ambiguity_type
        )
        
        if disambiguation_result.single_answer and disambiguation_result.primary_result:
            return self._build_resolved_disambiguation_response(
                question=question,
                query_term=query_term,
                ambiguity_type=ambiguity_type,
                disambiguation_result=disambiguation_result,
                pipeline_result=pipeline_result,
                start_time=start_time,
                vault_context=vault_context
            )
        
        return self._build_clarification_response(
            query_term=query_term,
            ambiguity_type=ambiguity_type,
            all_matches=all_matches,
            pipeline_result=pipeline_result,
            start_time=start_time
        )
    
    def _build_resolved_disambiguation_response(
        self,
        question: str,
        query_term: str,
        ambiguity_type: str,
        disambiguation_result: DisambiguationResult,
        pipeline_result,
        start_time: float,
        vault_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build response when disambiguation found a clear primary answer."""
        primary = disambiguation_result.primary_result
        alternatives = disambiguation_result.alternatives
        
        primary_name = primary.get("name", "Unknown")
        primary_role = primary.get("role", query_term)
        
        primary_org = self._get_vault_matching_org(primary, vault_context) or vault_context or ""
        
        if ambiguity_type == "role":
            answer = f"The {query_term} of {primary_org} is {primary_name}."
        else:
            answer = f"{primary_name} is the {primary_role}."
        
        if disambiguation_result.show_alternatives and alternatives:
            alt_lines = []
            for alt in alternatives:
                alt_name = alt.get("name", "Unknown")
                alt_role = alt.get("role", "")
                alt_orgs = alt.get("organizations", [])
                if not alt_orgs and alt.get("organization"):
                    alt_orgs = [alt.get("organization")]
                alt_org = alt_orgs[0] if alt_orgs else ""
                if alt_org:
                    alt_lines.append(f"- {alt_name} ({alt_role} of {alt_org})")
                else:
                    alt_lines.append(f"- {alt_name} ({alt_role})")
            
            if alt_lines:
                answer += "\n\nNote: Your documents also mention other " + query_term + "s:\n" + "\n".join(alt_lines)
        
        evidence = QAEvidence(
            entity_names=[primary_name],
            chunk_sources=[]
        )
        
        return build_response(
            answer=answer,
            confidence=0.9,
            qa_verdict={"status": "SUPPORTED", "reason": disambiguation_result.reasoning},
            evidence=evidence,
            iterations=0,
            time_ms=int((time.time() - start_time) * 1000),
            success=True,
            pipeline_result=pipeline_result,
            extra={
                "disambiguation": True,
                "resolved": True,
                "primary_match": primary,
                "alternatives": alternatives,
                "used_llm": disambiguation_result.used_llm
            }
        )
    
    def _build_clarification_response(
        self,
        query_term: str,
        ambiguity_type: str,
        all_matches: List[Dict[str, Any]],
        pipeline_result,
        start_time: float
    ) -> Dict[str, Any]:
        """Build response asking user to clarify when no clear primary match."""
        match_lines = []
        for match in all_matches:
            name = match.get("name", "Unknown")
            context = match.get("organization") or match.get("context") or match.get("department")
            role_or_type = match.get("role") or match.get("type") or match.get("category")
            
            if ambiguity_type == "role" and context:
                match_lines.append(f"- {name} ({role_or_type} of {context})")
            elif ambiguity_type == "role":
                match_lines.append(f"- {name} ({role_or_type})")
            elif context and role_or_type:
                match_lines.append(f"- {name} ({role_or_type} at {context})")
            elif context:
                match_lines.append(f"- {name} ({context})")
            elif role_or_type:
                match_lines.append(f"- {name} ({role_or_type})")
            else:
                match_lines.append(f"- {name}")
        
        matches_text = "\n".join(match_lines)
        
        type_descriptions = {
            "role": f"people with the {query_term} role",
            "entity": f"people named {query_term}",
            "department": f"departments matching {query_term}",
            "project": f"projects matching {query_term}",
            "location": f"locations matching {query_term}",
            "metric": f"items with {query_term}"
        }
        type_desc = type_descriptions.get(ambiguity_type, f"matches for {query_term}")
        
        answer = f"""I found multiple {type_desc}:

{matches_text}

Which one would you like to know more about? Please specify by name."""
        
        evidence = QAEvidence(
            entity_names=[m.get("name", "") for m in all_matches],
            chunk_sources=[]
        )
        
        return build_response(
            answer=answer,
            confidence=1.0,
            qa_verdict={"status": "DISAMBIGUATION_NEEDED", "reason": f"Multiple matches for {ambiguity_type} '{query_term}'"},
            evidence=evidence,
            iterations=0,
            time_ms=int((time.time() - start_time) * 1000),
            success=True,
            pipeline_result=pipeline_result,
            extra={"disambiguation": True, "ambiguity_type": ambiguity_type, "match_count": len(all_matches), "all_matches": all_matches}
        )
    
    def query(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        debug: bool = False,
        vault_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a query using tool-calling agent.
        
        Args:
            question: User's question
            conversation_history: Previous messages for context
            debug: If True, include detailed diagnostic info in response
            vault_context: Name of the current vault (for entity resolution)
            
        Returns:
            Dict with answer, tool_calls, evidence, pipeline_result, etc.
        """
        start_time = time.time()
        
        tier, complexity_signals = self.complexity_router.route(question)
        logger.info(f"[AGENT] Query complexity: tier={tier.value}, score={complexity_signals.complexity_score:.2f}")
        
        # Financial Query Handler: Check for pre-calculated metrics FIRST
        try:
            from .financial_query_handler import FinancialQueryHandler
            financial_handler = FinancialQueryHandler(self.session, self.tenant_id)
            financial_result = financial_handler.handle_query(question)
            
            if financial_result:
                logger.info(f"[AGENT] Financial query answered from pre-calculated metric: {financial_result.get('metric_name')}")
                evidence = QAEvidence(
                    entity_names=[financial_result.get('metric_name', '')],
                    chunk_sources=[]
                )
                return build_response(
                    answer=financial_result['answer'],
                    confidence=financial_result.get('confidence', 0.95),
                    qa_verdict={"status": "SUPPORTED", "reason": "Answered from pre-calculated financial metric"},
                    evidence=evidence,
                    iterations=0,
                    time_ms=int((time.time() - start_time) * 1000),
                    success=True,
                    pipeline_result=None,
                    extra={"source": "pre_calculated_financial", "entity_type": financial_result.get('entity_type')}
                )
        except Exception as e:
            logger.debug(f"[AGENT] Financial handler check (non-blocking): {e}")
        
        rlm_enabled = os.environ.get("RLM_ENABLED", "false").lower() == "true"
        rlm_timeout = int(os.environ.get("RLM_TIMEOUT_SECONDS", "30"))
        
        if tier == QueryTier.TIER2_RLM and rlm_enabled:
            logger.info("[AGENT] Routing to RLM for complex query")
            try:
                import concurrent.futures
                from ..rlm.schemas import RLMConfig
                
                config = RLMConfig(
                    max_iterations=5,
                    iteration_timeout_seconds=10,
                    total_timeout_seconds=rlm_timeout,
                    root_provider="openai",
                    root_model="gpt-4o-mini"
                )
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        execute_rlm_query,
                        tenant_id=self.tenant_id,
                        query=question,
                        db_session=self.session,
                        config=config
                    )
                    rlm_result = future.result(timeout=rlm_timeout)
                
                if rlm_result and rlm_result.answer_text and rlm_result.confidence >= 0.5:
                    logger.info(f"[AGENT] RLM returned answer with confidence={rlm_result.confidence:.2f}")
                    
                    evidence = QAEvidence(
                        entity_names=[e.name for e in rlm_result.entities_found] if rlm_result.entities_found else [],
                        chunk_sources=[]
                    )
                    
                    return build_response(
                        answer=rlm_result.answer_text,
                        confidence=rlm_result.confidence,
                        qa_verdict={"status": "SUPPORTED", "reason": "Answered via RLM iterative reasoning"},
                        evidence=evidence,
                        iterations=rlm_result.execution_trace.total_iterations if rlm_result.execution_trace else 0,
                        time_ms=int((time.time() - start_time) * 1000),
                        success=True,
                        pipeline_result=None,
                        extra={"mode": "RLM", "complexity_score": complexity_signals.complexity_score}
                    )
                else:
                    logger.info(f"[AGENT] RLM returned low confidence ({rlm_result.confidence if rlm_result else 'None'}), falling back to standard pipeline")
            except concurrent.futures.TimeoutError:
                logger.warning(f"[AGENT] RLM execution timed out after {rlm_timeout}s, falling back to standard pipeline")
            except Exception as e:
                logger.warning(f"[AGENT] RLM execution failed, falling back to standard pipeline: {e}")
        elif tier == QueryTier.TIER2_RLM:
            logger.info("[AGENT] Tier 2 query detected but RLM disabled (set RLM_ENABLED=true to enable)")
        
        # DISABLED: QueryInterpreter causing timeouts (29 errors in Orion test)
        # TODO: Re-enable after optimizing latency or adding caching
        intent: Optional[QueryIntent] = None
        # try:
        #     intent = self.query_interpreter.interpret(question)
        #     logger.info(f"[AGENT] Intent: entity='{intent.entity}', type='{intent.query_type}', target='{intent.target_type}'")
        #     
        #     if intent.query_type == "graph_traversal" and intent.entity:
        #         kg_result = self.directed_retriever.execute(intent)
        #         if kg_result.entity_found and kg_result.relationships:
        #             logger.info(f"[AGENT] KG has data: {len(kg_result.relationships)} relationships for '{intent.entity}'")
        #             return self._synthesize_from_kg(question, kg_result, intent, start_time)
        #         elif kg_result.entity_found:
        #             logger.info(f"[AGENT] KG entity found but no matching relationships, falling back to pipeline")
        #         else:
        #             logger.info(f"[AGENT] KG entity not found for '{intent.entity}', falling back to pipeline")
        #     
        #     elif intent.query_type == "property_lookup" and intent.entity:
        #         kg_result = self.directed_retriever.execute(intent)
        #         if kg_result.entity_found:
        #             logger.info(f"[AGENT] Property lookup for '{intent.entity}', falling through to pipeline with intent")
        # except Exception as e:
        #     logger.warning(f"[AGENT] Intent interpretation failed (continuing without): {e}")
        
        pipeline_result = None
        try:
            pipeline_result = self.query_pipeline.process(question, vault_context=vault_context)
            logger.info(f"[AGENT] Pipeline: strategy={pipeline_result.strategy_used}, has_data={pipeline_result.has_data}")
        except Exception as e:
            logger.warning(f"[AGENT] Pipeline pre-processing failed (continuing without): {e}")
        
        if pipeline_result and pipeline_result.needs_disambiguation and pipeline_result.ambiguity:
            logger.info(f"[AGENT] Ambiguity detected ({pipeline_result.ambiguity.ambiguity_type}) - using disambiguation reasoner")
            return self._build_disambiguation_response(question, pipeline_result, start_time, vault_context=vault_context)
        
        # Handle "I don't know" for scoped role resolution failures
        # When user asks "Who is the CEO of NextGen Battery Technologies?" and we can't find it,
        # return a definitive "not found" instead of falling through to wrong answers
        if pipeline_result and pipeline_result.strategy_used == "SCOPED_ROLE_NOT_FOUND":
            logger.info(f"[AGENT] Scoped role NOT FOUND - returning 'I don't know' response")
            
            # Extract the message from the entities (set by retrieval_router)
            not_found_message = "I couldn't find that information in the knowledge base."
            if pipeline_result.entities:
                for e in pipeline_result.entities:
                    if e.get('type') == 'NOT_FOUND' and e.get('message'):
                        not_found_message = e.get('message')
                        break
            
            duration = (time.time() - start_time) * 1000
            return build_response(
                question=question,
                answer=not_found_message,
                evidence={
                    "strategy": "SCOPED_ROLE_NOT_FOUND",
                    "data_found": False
                },
                confidence=0.15,  # Low confidence - we're admitting we don't know
                duration_ms=duration,
                extra={
                    "direct_answer": True,
                    "not_found_response": True,
                    "strategy_used": "SCOPED_ROLE_NOT_FOUND"
                }
            )
        
        if pipeline_result and self._can_answer_directly(pipeline_result):
            logger.info("[AGENT] Using DIRECT ANSWER path (skipping tool loop)")
            answer = self._synthesize_direct_answer(question, pipeline_result, intent)
            
            # Issue 1 Fix: Clean metadata garbage from answer
            from ..utils.qa_validation import clean_metadata_garbage
            answer = clean_metadata_garbage(answer)
            
            evidence = build_qa_evidence(retrieval_result=pipeline_result)
            confidence = calculate_confidence("SUPPORTED", evidence, answer)
            
            # QA Accuracy Fixes: Apply shared validation to direct answers
            from ..utils.qa_validation import validate_qa_response
            
            # Convert chunks to documents format for validation
            docs_for_validation = []
            if hasattr(pipeline_result, 'chunks') and pipeline_result.chunks:
                docs_for_validation = [
                    {'content': c.get('text', ''), 'document': c.get('document', '')}
                    for c in pipeline_result.chunks if isinstance(c, dict)
                ]
            
            qa_validation = validate_qa_response(
                query=question,
                answer=answer,
                documents=docs_for_validation
            )
            
            # Coherence Checking - modify response when confidence is LOW or MEDIUM
            coherence_result = None
            try:
                from ..validation.coherence_checker import CoherenceChecker, ConfidenceLevel
                coherence_checker = CoherenceChecker()
                source_chunks = [c.get('content', '') for c in docs_for_validation if isinstance(c, dict)]
                coherence_result = coherence_checker.validate(question, answer, source_chunks)
                coherence_checker.log_result(question, coherence_result)
            except Exception as e:
                logger.warning(f"[COHERENCE] Check failed (non-blocking): {e}")
            
            # Build extra dict with validation results
            extra_data = {"direct_answer": True}
            if qa_validation.has_warnings:
                extra_data["qa_validation_notes"] = qa_validation.validation_notes
                extra_data["caveats"] = qa_validation.validation_notes
            if qa_validation.precalculated_value:
                extra_data["precalculated_value_found"] = qa_validation.precalculated_value
            
            # Apply coherence-based response modification for LOW/MEDIUM confidence
            final_answer = answer
            if coherence_result and coherence_result.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM):
                # Build caveat from failed checks (issues contains CheckResult objects with passed=False)
                issues = [r.reason for r in coherence_result.issues if r.reason]
                caveat_parts = []
                
                if coherence_result.confidence_level == ConfidenceLevel.LOW:
                    caveat_parts.append(f"**Confidence: Low ({coherence_result.confidence_score:.0%})**")
                else:
                    caveat_parts.append(f"**Confidence: Medium ({coherence_result.confidence_score:.0%})**")
                
                if issues:
                    caveat_parts.append("**Why:** " + "; ".join(issues[:2]))  # Limit to 2 issues
                
                caveat_parts.append("**Please verify this information against source documents.**")
                
                caveat_text = "\n\n---\n" + "\n\n".join(caveat_parts)
                final_answer = answer + caveat_text
                
                extra_data["coherence_confidence"] = coherence_result.confidence_level.value
                extra_data["coherence_score"] = coherence_result.confidence_score
                extra_data["coherence_issues"] = issues
                logger.info(f"[COHERENCE] Response modified: {coherence_result.confidence_level.value.upper()} confidence, {len(issues)} issues")
            
            return build_response(
                answer=final_answer,
                confidence=confidence,
                qa_verdict={"status": "SUPPORTED", "reason": "Direct answer from pipeline data"},
                evidence=evidence,
                iterations=0,
                time_ms=int((time.time() - start_time) * 1000),
                success=True,
                pipeline_result=pipeline_result,
                extra=extra_data
            )
        
        system_prompt = AGENT_SYSTEM_PROMPT
        if vault_context:
            anchor_org = self._extract_anchor_org_name(vault_context)
            if anchor_org:
                system_prompt += f"\n\nCURRENT VAULT CONTEXT:\nThis knowledge base is about {anchor_org}. When queries refer to 'the company', 'company backlog', 'company revenue', or similar terms without specifying a company name, assume they refer to {anchor_org}. Prioritize information about {anchor_org} over information about their customers or partners."
        
        debug_info = {
            "tool_calls": [],
            "reasoning_trace": [],
            "context_loaded": {
                "system_prompt": system_prompt,
                "conversation_history": conversation_history[-6:] if conversation_history else [],
                "user_question": question,
                "pipeline_result": pipeline_result.to_dict() if pipeline_result else None
            },
            "raw_llm_responses": [],
            "messages_sent": []
        } if debug else None
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)
        
        user_message = question
        if pipeline_result and pipeline_result.has_data:
            context_injection = self._build_context_injection(pipeline_result)
            user_message = question + context_injection
        
        messages.append({"role": "user", "content": user_message})
        
        tool_calls_made = []
        tool_results = []
        
        for iteration in range(self.MAX_TOOL_CALLS + 1):
            logger.info(f"[AGENT] Iteration {iteration + 1}, messages: {len(messages)}")
            
            if debug_info:
                debug_info["messages_sent"].append({
                    "iteration": iteration + 1,
                    "messages": [self._sanitize_message(m) for m in messages]
                })
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto" if iteration < self.MAX_TOOL_CALLS else "none",
                    temperature=0.0,
                    max_tokens=800
                )
            except Exception as e:
                logger.error(f"[AGENT] OpenAI API error: {e}")
                result = {
                    "answer": f"Error calling AI service: {str(e)}",
                    "tool_calls": tool_calls_made,
                    "iterations": iteration + 1,
                    "time_ms": int((time.time() - start_time) * 1000),
                    "success": False
                }
                if debug_info:
                    result["debug"] = debug_info
                return result
            
            message = response.choices[0].message
            
            if debug_info:
                raw_response = {
                    "iteration": iteration + 1,
                    "role": message.role,
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        } for tc in (message.tool_calls or [])
                    ],
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    } if response.usage else None
                }
                debug_info["raw_llm_responses"].append(raw_response)
            
            if message.tool_calls:
                messages.append(message.model_dump())
                
                if debug_info:
                    debug_info["reasoning_trace"].append({
                        "iteration": iteration + 1,
                        "action": "tool_calls",
                        "thought": message.content,
                        "tools_called": [tc.function.name for tc in message.tool_calls]
                    })
                
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"[AGENT] Tool call: {tool_name}({arguments})")
                    
                    tool_start = time.time()
                    try:
                        result = self.tool_executor.execute(tool_name, arguments)
                    except Exception as e:
                        logger.error(f"[AGENT] Tool error: {e}")
                        result = {"error": str(e)}
                    tool_time = time.time() - tool_start
                    
                    tool_record = {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result,
                        "time_ms": int(tool_time * 1000)
                    }
                    tool_calls_made.append(tool_record)
                    tool_results.append(result)
                    
                    if debug_info:
                        debug_info["tool_calls"].append({
                            "iteration": iteration + 1,
                            "tool": tool_name,
                            "arguments": arguments,
                            "result": result,
                            "time_ms": int(tool_time * 1000)
                        })
                        debug_info["reasoning_trace"].append({
                            "iteration": iteration + 1,
                            "action": "observation",
                            "tool": tool_name,
                            "result_summary": self._summarize_result(result)
                        })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            else:
                analysis = self._analyze_retrieval_results(tool_calls_made)
                fallback_triggered = False
                
                logger.info(f"[RETRIEVAL] Pre-answer analysis: entities={analysis['entities_found']}, "
                           f"relationships={analysis['relationships_found']}, chunks={analysis['chunks_found']}, "
                           f"kg_tools={analysis['kg_tools_called']}, doc_tools={analysis['doc_tools_called']}")
                
                if self._needs_document_fallback(question, analysis):
                    fallback_triggered = True
                    logger.info(f"[RETRIEVAL] Executing document fallback for: {question[:50]}...")
                    
                    fallback_result = self._execute_document_fallback(question)
                    
                    if fallback_result.get('chunks'):
                        fallback_record = {
                            "tool": "search_documents",
                            "arguments": {"query": question, "limit": 5},
                            "result": fallback_result,
                            "time_ms": 0,
                            "fallback": True
                        }
                        tool_calls_made.append(fallback_record)
                        tool_results.append(fallback_result)
                        
                        analysis["chunks_found"] += len(fallback_result.get('chunks', []))
                        analysis["doc_tools_called"].append("search_documents (fallback)")
                        
                        fallback_tool_call_id = "fallback_search_docs"
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": fallback_tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": "search_documents",
                                    "arguments": json.dumps({"query": question, "limit": 5})
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": fallback_tool_call_id,
                            "content": json.dumps(fallback_result)
                        })
                        
                        logger.info(f"[RETRIEVAL] Re-running synthesis with {len(fallback_result.get('chunks', []))} fallback chunks")
                        
                        try:
                            synthesis_response = self.client.chat.completions.create(
                                model=self.model,
                                messages=messages,
                                tools=TOOL_DEFINITIONS,
                                tool_choice="none",
                                temperature=0.0,
                                max_tokens=800
                            )
                            answer = synthesis_response.choices[0].message.content or "I couldn't find an answer."
                        except Exception as e:
                            logger.error(f"[RETRIEVAL] Synthesis after fallback failed: {e}")
                            answer = message.content or "I couldn't find an answer."
                    else:
                        answer = message.content or "I couldn't find an answer."
                else:
                    answer = message.content or "I couldn't find an answer."
                
                logger.info(f"[RETRIEVAL] Final: entities={analysis['entities_found']}, "
                           f"relationships={analysis['relationships_found']}, chunks={analysis['chunks_found']}. "
                           f"Fallback: {fallback_triggered}")
                
                if debug_info:
                    debug_info["reasoning_trace"].append({
                        "iteration": iteration + 1,
                        "action": "final_answer",
                        "raw_answer": answer,
                        "fallback_triggered": fallback_triggered,
                        "retrieval_analysis": analysis
                    })
                
                # Issue 1 Fix: Clean metadata garbage from answer
                from ..utils.qa_validation import clean_metadata_garbage
                answer = clean_metadata_garbage(answer)
                
                answer = self._validate_numeric_claims(answer, tool_results)
                
                total_time = time.time() - start_time
                
                evidence = build_qa_evidence(
                    retrieval_result=pipeline_result,
                    tool_calls=tool_calls_made
                )
                
                qa_status = "SUPPORTED" if evidence.has_data else "INSUFFICIENT"
                confidence = calculate_confidence(qa_status, evidence, answer)
                
                # Coherence Checking (Shadow Mode) - log only, don't modify response
                try:
                    from ..validation.coherence_checker import CoherenceChecker
                    coherence_checker = CoherenceChecker()
                    source_chunks = []
                    for tr in tool_results:
                        if isinstance(tr, dict) and 'chunks' in tr:
                            for chunk in tr['chunks']:
                                if isinstance(chunk, dict):
                                    source_chunks.append(chunk.get('text', ''))
                    coherence_result = coherence_checker.validate(question, answer, source_chunks)
                    coherence_checker.log_result(question, coherence_result)
                except Exception as e:
                    logger.warning(f"[COHERENCE] Shadow check failed (non-blocking): {e}")
                
                result = build_response(
                    answer=answer,
                    confidence=confidence,
                    qa_verdict={"status": qa_status, "reason": f"Evidence: {evidence.entity_count} entities, {evidence.relationship_count} rels, {evidence.chunk_count} chunks"},
                    evidence=evidence,
                    tool_calls=tool_calls_made,
                    iterations=iteration + 1,
                    time_ms=int(total_time * 1000),
                    success=True,
                    pipeline_result=pipeline_result,
                    extra={
                        "retrieval_analysis": analysis,
                        "fallback_triggered": fallback_triggered
                    }
                )
                if debug_info:
                    result["debug"] = debug_info
                return result
        
        evidence = build_qa_evidence(
            retrieval_result=pipeline_result,
            tool_calls=tool_calls_made
        )
        result = build_response(
            answer="I reached the maximum number of tool calls. Please try a simpler question.",
            confidence=0.0,
            qa_verdict={"status": "INSUFFICIENT", "reason": "Max tool calls reached without finding answer"},
            evidence=evidence,
            tool_calls=tool_calls_made,
            iterations=self.MAX_TOOL_CALLS,
            time_ms=int((time.time() - start_time) * 1000),
            success=False,
            pipeline_result=pipeline_result
        )
        if debug_info:
            result["debug"] = debug_info
        return result
    
    def _validate_numeric_claims(self, answer: str, tool_results: List[Dict]) -> str:
        """Flag numeric claims without tool evidence."""
        numbers = re.findall(r'\b\d+\b', answer)
        
        has_agg_evidence = any(
            r.get("result_kind") or r.get("value") is not None
            for r in tool_results
        )
        
        if numbers and not has_agg_evidence:
            logger.warning(f"[AGENT] Numeric claims without aggregation evidence: {numbers}")
        
        return answer
    
    def _sanitize_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize message for debug output (truncate large content)."""
        result = dict(msg)
        if "content" in result and result["content"]:
            content = str(result["content"])
            if len(content) > 2000:
                result["content"] = content[:2000] + f"... [truncated, {len(content)} chars total]"
        return result
    
    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Create a brief summary of a tool result for the reasoning trace."""
        if "error" in result:
            return f"ERROR: {result['error'][:100]}"
        
        if "entities" in result:
            entities = result["entities"]
            resolved = [e for e in entities if e.get("resolved")]
            return f"Resolved {len(resolved)}/{len(entities)} entities"
        
        if "outgoing" in result or "incoming" in result:
            outgoing = result.get("outgoing", [])
            incoming = result.get("incoming", [])
            out_strs = [f"{t['type']}({t['count']})" for t in outgoing[:3]]
            in_strs = [f"{t['type']}({t['count']})" for t in incoming[:3]]
            return f"Outgoing: {', '.join(out_strs) or 'none'} | Incoming: {', '.join(in_strs) or 'none'}"
        
        if "relationship_types" in result:
            types = result["relationship_types"]
            type_strs = [f"{t['type']}({t['count']})" for t in types[:5]]
            return f"Found {len(types)} relationship types: {', '.join(type_strs)}"
        
        if "result_kind" in result:
            return f"{result['result_kind']}: {result.get('value', 'N/A')}"
        
        if "relationships" in result:
            rels = result["relationships"]
            return f"Found {len(rels)} relationships"
        
        if "chunks" in result:
            chunks = result["chunks"]
            return f"Found {len(chunks)} document chunks"
        
        return f"Result with keys: {list(result.keys())[:5]}"
    
    def _analyze_retrieval_results(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze what data was retrieved from tool calls."""
        analysis = {
            "entities_found": 0,
            "relationships_found": 0,
            "chunks_found": 0,
            "kg_tools_called": [],
            "doc_tools_called": [],
        }
        
        for tc in tool_calls:
            tool_name = tc.get('tool') or tc.get('name', '')
            result = tc.get('result', {})
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    result = {}
            
            if tool_name in ('resolve_entities', 'get_knowledge_bundle', 'discover_relationships'):
                analysis["kg_tools_called"].append(tool_name)
                
                entities = result.get('entities', [])
                if entities:
                    resolved = [e for e in entities if e.get("resolved")]
                    analysis["entities_found"] += len(resolved)
                
                analysis["relationships_found"] += len(result.get('relationships', []))
                analysis["relationships_found"] += len(result.get('incoming', []))
                analysis["relationships_found"] += len(result.get('outgoing', []))
                
                for r in result.get('results', []):
                    analysis["relationships_found"] += len(r.get('relationships', []))
            
            if tool_name in ('search_documents', 'search_chunks'):
                analysis["doc_tools_called"].append(tool_name)
                analysis["chunks_found"] += len(result.get('chunks', []))
        
        return analysis
    
    def _needs_document_fallback(self, query: str, analysis: Dict[str, Any]) -> bool:
        """
        Determine if we should fallback to document search.
        
        Fallback triggers when:
        - Documents weren't already searched
        - AND KG was queried (so we have some context)
        - AND no chunks have been found yet
        
        The goal is to ALWAYS supplement KG data with document search for factual
        queries, since KG relationships may not contain the specific facts requested.
        """
        if analysis["doc_tools_called"]:
            return False
        
        if not analysis["kg_tools_called"]:
            return False
        
        if analysis["chunks_found"] > 0:
            return False
        
        logger.info(f"[RETRIEVAL] KG queried but no document search yet. "
                    f"Entities: {analysis['entities_found']}, Relationships: {analysis['relationships_found']}. "
                    f"Triggering document fallback to supplement KG data.")
        return True
    
    def _execute_document_fallback(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute document search as fallback using ToolExecutor."""
        try:
            result = self.tool_executor.execute('search_documents', {'query': query, 'limit': limit})
            chunks_found = len(result.get('chunks', []))
            logger.info(f"[RETRIEVAL] Document fallback returned {chunks_found} chunks")
            return result
        except Exception as e:
            logger.error(f"[RETRIEVAL] Document fallback failed: {e}")
            return {"chunks": [], "error": str(e)}
