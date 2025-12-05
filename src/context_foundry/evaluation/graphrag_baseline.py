"""
GraphRAG Baseline for Context Foundry Evaluation.

A simpler graph-based RAG approach for comparison:
- Uses knowledge graph for entity/relationship retrieval
- Uses vector search for document context
- NO symbolic rules layer
- NO confidence scoring on individual facts
- Simple prompt-based reasoning

This baseline represents a typical GraphRAG implementation
without the tri-memory cognitive architecture.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import uuid
import os

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models.schema import (
    Entity, Relationship, Document, LifecycleState,
    get_session
)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


@dataclass
class GraphRAGContext:
    """Context retrieved by GraphRAG baseline."""
    entities: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    documents: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "entities": self.entities,
            "relationships": self.relationships,
            "documents": self.documents,
            "total_items": len(self.entities) + len(self.relationships) + len(self.documents),
        }


@dataclass
class GraphRAGResponse:
    """Response from GraphRAG baseline."""
    query: str
    answer: str
    context: GraphRAGContext
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "context": self.context.to_dict(),
            "latency_ms": self.latency_ms,
        }


class GraphRAGBaseline:
    """
    GraphRAG Baseline Implementation.
    
    Differences from Context Foundry:
    1. No lifecycle states - uses all entities equally
    2. No confidence scoring - treats all facts as equally reliable
    3. No symbolic rules - no validation layer
    4. Simple keyword matching instead of semantic analysis
    5. No provenance tracking on response generation
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        self._client = None
    
    def _get_openai_client(self):
        """Lazy load OpenAI client using Replit AI Integrations."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
                base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
            )
        return self._client
    
    def query(self, query_text: str) -> GraphRAGResponse:
        """
        Process a query using simple GraphRAG approach.
        
        Steps:
        1. Extract keywords from query
        2. Find matching entities by name
        3. Get relationships for those entities
        4. Find similar documents
        5. Generate response with LLM
        """
        start_time = datetime.utcnow()
        
        context = self._retrieve_context(query_text)
        
        answer = self._generate_response(query_text, context)
        
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return GraphRAGResponse(
            query=query_text,
            answer=answer,
            context=context,
            latency_ms=latency,
        )
    
    def _retrieve_context(self, query_text: str) -> GraphRAGContext:
        """Retrieve context using simple keyword matching."""
        context = GraphRAGContext()
        
        keywords = self._extract_keywords(query_text)
        
        for keyword in keywords:
            entities = self.session.query(Entity).filter(
                Entity.name.ilike(f"%{keyword}%")
            ).limit(10).all()
            
            for entity in entities:
                context.entities.append({
                    "name": entity.name,
                    "type": entity.entity_type,
                    "description": entity.description,
                    "properties": entity.properties,
                })
                
                for rel in entity.outgoing_relationships:
                    context.relationships.append({
                        "source": entity.name,
                        "type": rel.relationship_type,
                        "target": rel.target_entity.name if rel.target_entity else "Unknown",
                        "properties": rel.properties,
                    })
                
                for rel in entity.incoming_relationships:
                    context.relationships.append({
                        "source": rel.source_entity.name if rel.source_entity else "Unknown",
                        "type": rel.relationship_type,
                        "target": entity.name,
                        "properties": rel.properties,
                    })
        
        context.relationships = self._deduplicate_relationships(context.relationships)
        
        documents = self.session.query(Document).filter(
            or_(*[Document.content.ilike(f"%{kw}%") for kw in keywords])
        ).limit(5).all()
        
        for doc in documents:
            context.documents.append({
                "title": doc.title,
                "content": doc.content[:500] if doc.content else "",
                "doc_type": doc.doc_type,
            })
        
        return context
    
    def _extract_keywords(self, query_text: str) -> List[str]:
        """Extract keywords from query using simple heuristics."""
        stopwords = {
            "what", "which", "who", "when", "where", "how", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "do", "does",
            "did", "will", "would", "could", "should", "may", "might", "must",
            "shall", "can", "need", "the", "a", "an", "and", "or", "but", "if",
            "then", "else", "for", "of", "to", "from", "by", "on", "in", "at",
            "with", "about", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "again", "further", "once",
            "here", "there", "all", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "also", "now", "down", "goes", "go",
            "affected", "paged", "should", "escalate", "owns", "depends",
        }
        
        words = query_text.lower().replace("?", "").replace(",", "").split()
        
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        if "database" in query_text.lower():
            keywords.append("database")
        if "service" in query_text.lower():
            keywords.append("service")
        if "team" in query_text.lower():
            keywords.append("team")
        
        return list(set(keywords))
    
    def _deduplicate_relationships(self, relationships: List[Dict]) -> List[Dict]:
        """Remove duplicate relationships."""
        seen = set()
        unique = []
        for rel in relationships:
            key = (rel["source"], rel["type"], rel["target"])
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        return unique
    
    def _generate_response(self, query_text: str, context: GraphRAGContext) -> str:
        """Generate response using LLM with simple prompt."""
        client = self._get_openai_client()
        
        context_str = self._format_context(context)
        
        prompt = f"""You are a helpful assistant answering questions about an IT operations knowledge base.

Context from knowledge graph:
{context_str}

Question: {query_text}

Answer the question based on the context provided. If the context doesn't contain enough information, say so."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def _format_context(self, context: GraphRAGContext) -> str:
        """Format context for LLM prompt."""
        lines = []
        
        if context.entities:
            lines.append("ENTITIES:")
            for e in context.entities[:15]:
                desc = e.get("description", "")[:100] if e.get("description") else ""
                lines.append(f"  - {e['name']} ({e['type']}): {desc}")
        
        if context.relationships:
            lines.append("\nRELATIONSHIPS:")
            for r in context.relationships[:20]:
                lines.append(f"  - {r['source']} --[{r['type']}]--> {r['target']}")
        
        if context.documents:
            lines.append("\nDOCUMENTS:")
            for d in context.documents[:3]:
                lines.append(f"  - {d['title']}: {d['content'][:200]}...")
        
        return "\n".join(lines) if lines else "No relevant context found."
    
    def cleanup(self):
        """Clean up session."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
