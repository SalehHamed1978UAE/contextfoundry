"""
EpisodicMemoryAPI - Document chunk operations for RLM REPL.

Wraps document_chunks table to provide semantic search over content,
chunk retrieval, and provenance tracking.
"""

import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..schemas import (
    ChunkSummary,
    ChunkDetail,
    ChunkMatch,
    ProvenanceInfo,
)


class EpisodicMemoryAPI:
    """
    Exposes episodic memory (document chunks) to RLM REPL environment.
    
    All methods are tenant-scoped.
    """
    
    def __init__(self, tenant_id: str, session: Session):
        from uuid import UUID as PyUUID
        self._tenant_id_str = tenant_id
        self._tenant_id = PyUUID(tenant_id) if isinstance(tenant_id, str) and tenant_id else None
        self._session = session
        self._accessed_chunk_ids: List[str] = []
    
    def get_accessed_chunk_ids(self) -> List[str]:
        """Returns list of chunk IDs accessed during this session."""
        return list(set(self._accessed_chunk_ids))
    
    def clear_access_tracking(self):
        """Clear the accessed chunk tracking."""
        self._accessed_chunk_ids = []
    
    def search(
        self, 
        query: str, 
        k: int = 5,
        document_type: str = None
    ) -> List[ChunkMatch]:
        """
        Semantic search over document chunks.
        
        Falls back to text-based search if embeddings are not available.
        
        Args:
            query: Search query text
            k: Number of results (default 5)
            document_type: Filter by document type (pdf, docx, txt)
        
        Returns:
            List of ChunkMatch objects with similarity scores
        """
        from ...models.schema import Document, DocumentChunk
        
        doc_type_clause = "AND d.doc_type = :doc_type" if document_type else ""
        
        check_sql = text("""
            SELECT COUNT(*) FROM documents 
            WHERE tenant_id = :tenant_id AND embedding IS NOT NULL
            LIMIT 1
        """)
        has_embeddings = self._session.execute(check_sql, {"tenant_id": str(self._tenant_id)}).scalar() > 0
        
        if has_embeddings:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = response.data[0].embedding
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            sql = text(f"""
                SELECT 
                    dc.id as chunk_id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.text as content,
                    dc.chunk_metadata,
                    dc.created_at as chunk_created_at,
                    d.title as document_name,
                    d.doc_type as document_type,
                    d.created_at as upload_date,
                    1 - (d.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.tenant_id = :tenant_id
                AND d.embedding IS NOT NULL
                {doc_type_clause}
                ORDER BY d.embedding <=> '{embedding_str}'::vector
                LIMIT :limit
            """)
        else:
            query_lower = query.lower()
            query_words = query_lower.split()
            like_conditions = " OR ".join(
                f"LOWER(dc.text) LIKE '%{word}%'" for word in query_words if len(word) > 2
            )
            if not like_conditions:
                like_conditions = f"LOWER(dc.text) LIKE '%{query_lower}%'"
            
            sql = text(f"""
                SELECT 
                    dc.id as chunk_id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.text as content,
                    dc.chunk_metadata,
                    dc.created_at as chunk_created_at,
                    d.title as document_name,
                    d.doc_type as document_type,
                    d.created_at as upload_date,
                    CASE 
                        WHEN LOWER(dc.text) LIKE :query_contains THEN 0.8
                        ELSE 0.5
                    END as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.tenant_id = :tenant_id
                AND ({like_conditions})
                {doc_type_clause}
                ORDER BY similarity DESC
                LIMIT :limit
            """)
        
        params = {
            "tenant_id": str(self._tenant_id),
            "limit": k,
            "query_contains": f"%{query.lower()}%",
        }
        if document_type:
            params["doc_type"] = document_type.lower()
        
        rows = self._session.execute(sql, params).fetchall()
        
        results = []
        for row in rows:
            self._accessed_chunk_ids.append(str(row.chunk_id))
            
            content = row.content or ""
            token_count = len(content.split()) * 1.3
            
            page_numbers = None
            if row.chunk_metadata and 'page_numbers' in row.chunk_metadata:
                page_numbers = row.chunk_metadata.get('page_numbers')
            
            chunk_detail = ChunkDetail(
                id=str(row.chunk_id),
                document_id=str(row.document_id),
                chunk_index=row.chunk_index,
                content=content,
                token_count=int(token_count),
                created_at=row.chunk_created_at or datetime.utcnow(),
                document_name=row.document_name or "Unknown",
                document_type=row.document_type or "unknown",
                upload_date=row.upload_date or datetime.utcnow(),
                page_numbers=page_numbers
            )
            
            highlight = None
            query_terms = query.lower().split()
            for term in query_terms:
                if term in content.lower():
                    start = max(0, content.lower().find(term) - 50)
                    end = min(len(content), content.lower().find(term) + len(term) + 50)
                    snippet = content[start:end]
                    highlight = f"...{snippet}..."
                    break
            
            results.append(ChunkMatch(
                chunk=chunk_detail,
                similarity_score=row.similarity if row.similarity else 0.5,
                highlight=highlight
            ))
        
        return results
    
    def get_chunk(self, chunk_id: str) -> ChunkDetail:
        """
        Get full chunk content with provenance.
        
        Args:
            chunk_id: Chunk UUID
        
        Returns:
            ChunkDetail object
        """
        from ...models.schema import Document, DocumentChunk
        
        chunk = self._session.query(DocumentChunk).filter(
            DocumentChunk.id == chunk_id,
            DocumentChunk.tenant_id == self._tenant_id
        ).first()
        
        if not chunk:
            return ChunkDetail(
                id=chunk_id,
                document_id="unknown",
                chunk_index=0,
                content="Chunk not found",
                token_count=0,
                created_at=datetime.utcnow(),
                document_name="Unknown",
                document_type="unknown",
                upload_date=datetime.utcnow(),
                page_numbers=None
            )
        
        self._accessed_chunk_ids.append(str(chunk.id))
        
        doc = self._session.query(Document).filter(
            Document.id == chunk.document_id
        ).first()
        
        content = chunk.text or ""
        token_count = len(content.split()) * 1.3
        
        page_numbers = None
        if chunk.chunk_metadata and 'page_numbers' in chunk.chunk_metadata:
            page_numbers = chunk.chunk_metadata.get('page_numbers')
        
        return ChunkDetail(
            id=str(chunk.id),
            document_id=str(chunk.document_id),
            chunk_index=chunk.chunk_index,
            content=content,
            token_count=int(token_count),
            created_at=chunk.created_at or datetime.utcnow(),
            document_name=doc.title if doc else "Unknown",
            document_type=doc.doc_type if doc else "unknown",
            upload_date=doc.created_at if doc else datetime.utcnow(),
            page_numbers=page_numbers
        )
    
    def get_document_chunks(self, document_id: str) -> List[ChunkSummary]:
        """
        Get all chunks from a specific document.
        
        Args:
            document_id: Document UUID
        
        Returns:
            List of ChunkSummary objects ordered by chunk_index
        """
        from ...models.schema import DocumentChunk
        
        chunks = self._session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == self._tenant_id
        ).order_by(DocumentChunk.chunk_index).all()
        
        results = []
        for chunk in chunks:
            self._accessed_chunk_ids.append(str(chunk.id))
            
            content = chunk.text or ""
            token_count = len(content.split()) * 1.3
            preview = content[:200] if len(content) > 200 else content
            
            results.append(ChunkSummary(
                id=str(chunk.id),
                document_id=str(chunk.document_id),
                chunk_index=chunk.chunk_index,
                token_count=int(token_count),
                preview=preview,
                created_at=chunk.created_at or datetime.utcnow()
            ))
        
        return results
    
    def get_provenance(self, chunk_id: str) -> ProvenanceInfo:
        """
        Get source document and processing information.
        
        Args:
            chunk_id: Chunk UUID
        
        Returns:
            ProvenanceInfo object
        """
        from ...models.schema import Document, DocumentChunk
        
        chunk = self._session.query(DocumentChunk).filter(
            DocumentChunk.id == chunk_id,
            DocumentChunk.tenant_id == self._tenant_id
        ).first()
        
        if not chunk:
            return ProvenanceInfo(
                chunk_id=chunk_id,
                document_id="unknown",
                document_name="Unknown",
                document_type="unknown",
                upload_date=datetime.utcnow(),
                uploaded_by=None,
                page_numbers=None,
                section_title=None,
                processing_steps=[]
            )
        
        doc = self._session.query(Document).filter(
            Document.id == chunk.document_id
        ).first()
        
        page_numbers = None
        section_title = None
        if chunk.chunk_metadata:
            page_numbers = chunk.chunk_metadata.get('page_numbers')
            section_title = chunk.chunk_metadata.get('section_title')
        
        processing_steps = ["document_upload", "text_extraction", "chunking"]
        if doc and doc.embedding is not None:
            processing_steps.append("embedding")
        
        uploaded_by = None
        if doc and doc.doc_metadata:
            uploaded_by = doc.doc_metadata.get('uploaded_by')
        
        return ProvenanceInfo(
            chunk_id=str(chunk.id),
            document_id=str(chunk.document_id),
            document_name=doc.title if doc else "Unknown",
            document_type=doc.doc_type if doc else "unknown",
            upload_date=doc.created_at if doc else datetime.utcnow(),
            uploaded_by=uploaded_by,
            page_numbers=page_numbers,
            section_title=section_title,
            processing_steps=processing_steps
        )
    
    def search_by_document_type(
        self, 
        doc_type: str, 
        query: str, 
        k: int = 5
    ) -> List[ChunkMatch]:
        """
        Search within specific document types.
        
        Args:
            doc_type: Document type filter (pdf, docx, txt)
            query: Search query text
            k: Number of results (default 5)
        
        Returns:
            List of ChunkMatch objects
        """
        return self.search(query=query, k=k, document_type=doc_type)
