"""
Shared response helpers for consistent answer formatting.

All code paths (ToolAgent, web_app.py) should use these functions
to ensure consistent evidence gathering, confidence calculation,
and response formatting.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QAEvidence:
    """Unified evidence structure for QA verification and confidence calculation."""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)
    chunk_sources: List[str] = field(default_factory=list)
    chunk_excerpts: List[str] = field(default_factory=list)
    resolved_role: Optional[str] = None
    resolved_name: Optional[str] = None
    
    @property
    def entity_count(self) -> int:
        entity_ids = set()
        for e in self.entities:
            if isinstance(e, dict):
                eid = e.get('id') or e.get('name')
            else:
                eid = getattr(e, 'id', None) or getattr(e, 'name', None)
            if eid:
                entity_ids.add(eid)
        unique_names = set(n for n in self.entity_names if n not in entity_ids)
        return len(entity_ids) + len(unique_names)
    
    @property
    def relationship_count(self) -> int:
        return len(self.relationships)
    
    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
    
    @property
    def has_data(self) -> bool:
        return self.entity_count > 0 or self.relationship_count > 0 or self.chunk_count > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities_found": self.entity_count,
            "entity_names": list(set(self.entity_names))[:10],
            "relationships_found": self.relationship_count,
            "chunks_found": self.chunk_count,
            "chunk_sources": list(set(self.chunk_sources))[:5],
            "chunk_excerpts": self.chunk_excerpts[:3],
            "resolved_name": self.resolved_name,
            "has_data": self.has_data
        }


def build_qa_evidence(
    retrieval_result: Optional[Any] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None
) -> QAEvidence:
    """
    Build unified QAEvidence from pipeline retrieval result and/or tool calls.
    
    This is THE canonical way to gather evidence for QA verification.
    All code paths should use this function.
    
    Args:
        retrieval_result: Pipeline pre-retrieval data (RetrievalResult or dict)
        tool_calls: List of tool call records with 'tool', 'result' keys
        
    Returns:
        QAEvidence with combined data from all sources
    """
    evidence = QAEvidence()
    
    def get_field(obj, field_name, default=None):
        """Get field from object (attribute) or dict (key)."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)
    
    if retrieval_result:
        rr_entities = get_field(retrieval_result, 'entities') or []
        evidence.entities.extend(rr_entities)
        
        for e in rr_entities:
            name = e.get('name') if isinstance(e, dict) else getattr(e, 'name', None)
            if name:
                evidence.entity_names.append(name)
        
        rr_relationships = get_field(retrieval_result, 'relationships') or []
        evidence.relationships.extend(rr_relationships)
        
        rr_chunks = get_field(retrieval_result, 'chunks') or []
        evidence.chunks.extend(rr_chunks)
        
        for chunk in rr_chunks:
            if isinstance(chunk, dict):
                doc_name = chunk.get('document', chunk.get('source', 'Unknown'))
                evidence.chunk_sources.append(doc_name)
                text = chunk.get('text', '')[:400]
                if text:
                    evidence.chunk_excerpts.append(f"[{doc_name}]: {text}")
        
        rr_role = get_field(retrieval_result, 'role_resolution')
        if rr_role:
            is_resolved = get_field(rr_role, 'is_resolved', False)
            if is_resolved:
                evidence.resolved_role = get_field(rr_role, 'role')
                evidence.resolved_name = get_field(rr_role, 'resolved_name')
                if evidence.resolved_name:
                    evidence.entity_names.append(evidence.resolved_name)
    
    if tool_calls:
        for tc in tool_calls:
            tool_name = tc.get('tool') or tc.get('name', '')
            result = tc.get('result', {})
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}
            
            if tool_name in ('search_documents', 'search_chunks', 'summarize_chunks', 'retrieve_documents'):
                chunks = result.get('chunks', [])
                evidence.chunks.extend(chunks)
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        doc_name = chunk.get('document', chunk.get('source', 'Unknown'))
                        evidence.chunk_sources.append(doc_name)
                        text = chunk.get('text', '')[:400]
                        if text:
                            evidence.chunk_excerpts.append(f"[{doc_name}]: {text}")
            
            if tool_name == 'resolve_entities':
                for entity_wrapper in result.get('entities', []):
                    resolved = entity_wrapper.get('resolved')
                    if resolved:
                        evidence.entities.append(resolved)
                        name = resolved.get('name')
                        if name:
                            evidence.entity_names.append(name)
            
            if tool_name in ('get_knowledge_bundle', 'discover_relationships'):
                evidence.relationships.extend(result.get('relationships', []))
                evidence.relationships.extend(result.get('incoming', []))
                evidence.relationships.extend(result.get('outgoing', []))
    
    return evidence


def calculate_confidence(
    qa_verdict_status: str,
    evidence: QAEvidence,
    answer: str = ""
) -> float:
    """
    Calculate confidence score using a single consistent formula.
    
    This is THE canonical confidence calculation. All code paths should use this.
    
    Formula components:
    - Base: determined by QA verdict status
    - Bonuses: +0.1 for resolved entities, +0.05 per chunk (max 0.15)
    - Penalties: -0.2 for suspicious patterns
    
    Args:
        qa_verdict_status: QA verifier verdict (SUPPORTED, OFF_TOPIC, etc.)
        evidence: QAEvidence from build_qa_evidence()
        answer: The answer text (for pattern matching)
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    answer_lower = answer.lower() if answer else ""
    says_no_info = any(phrase in answer_lower for phrase in [
        "don't have", "no information", "cannot find", "not available",
        "no data", "unable to", "i don't know"
    ])
    
    if qa_verdict_status == "SUPPORTED":
        if evidence.resolved_name:
            base = 0.85
        elif evidence.chunk_count > 0 or evidence.relationship_count > 0:
            base = 0.70
        elif evidence.entity_count > 0:
            base = 0.65
        else:
            base = 0.60
        
        chunk_bonus = min(0.15, evidence.chunk_count * 0.05)
        entity_bonus = 0.05 if evidence.entity_count > 1 else 0.0
        
        confidence = min(1.0, base + chunk_bonus + entity_bonus)
        
    elif qa_verdict_status == "INSUFFICIENT":
        if evidence.has_data:
            confidence = 0.40
        else:
            confidence = 0.25
            
    elif qa_verdict_status == "OFF_TOPIC":
        confidence = 0.10
        
    elif qa_verdict_status == "UNSUPPORTED":
        confidence = 0.15
        
    elif qa_verdict_status == "SUSPICIOUS":
        confidence = 0.20
        
    elif qa_verdict_status == "REJECTED":
        confidence = 0.0
        
    else:
        if says_no_info and not evidence.has_data:
            confidence = 0.15
        elif says_no_info and evidence.has_data:
            confidence = 0.30
        elif evidence.has_data:
            confidence = 0.50
        else:
            confidence = 0.25
    
    return round(confidence, 2)


def build_response(
    answer: str,
    confidence: float,
    qa_verdict: Optional[Dict[str, Any]] = None,
    evidence: Optional[QAEvidence] = None,
    sources: Optional[List[str]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    iterations: int = 0,
    time_ms: int = 0,
    success: bool = True,
    pipeline_result: Optional[Any] = None,
    extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build consistent response dictionary for both CLI and Web.
    
    This is THE canonical response format. All code paths should use this.
    
    Args:
        answer: The answer text
        confidence: Confidence score (0.0-1.0)
        qa_verdict: QA verifier verdict dict with status and reason
        evidence: QAEvidence used for verification
        sources: List of source document names
        tool_calls: List of tool call records
        iterations: Number of agent iterations
        time_ms: Total time in milliseconds
        success: Whether the query succeeded
        pipeline_result: Pipeline pre-retrieval result (dict form)
        extra: Additional fields to include
        
    Returns:
        Consistent response dictionary
    """
    final_sources = sources or []
    if not final_sources and evidence:
        final_sources = list(set(evidence.chunk_sources))[:5]
    
    response = {
        "answer": answer,
        "confidence": confidence,
        "sources": final_sources,
        "tool_calls": tool_calls or [],
        "iterations": iterations,
        "time_ms": time_ms,
        "success": success
    }
    
    if qa_verdict:
        response["qa_verdict"] = qa_verdict
    
    if evidence:
        response["evidence"] = evidence.to_dict()
    
    if pipeline_result:
        if hasattr(pipeline_result, 'to_dict'):
            response["pipeline_result"] = pipeline_result.to_dict()
        elif isinstance(pipeline_result, dict):
            response["pipeline_result"] = pipeline_result
    
    if extra:
        response.update(extra)
    
    return response
