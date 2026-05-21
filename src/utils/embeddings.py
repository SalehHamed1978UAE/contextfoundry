"""
Embeddings utilities for Context Foundry

Supports both:
1. Local embeddings via sentence-transformers (BGE)
2. Ollama embeddings (nomic-embed-text)
"""

import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np

from src.config import settings


class EmbeddingService:
    """Manages document embeddings for episodic memory"""

    def __init__(self, use_ollama: bool = True):
        self.use_ollama = use_ollama
        self.model = None

        if not use_ollama:
            print(f"Loading local embedding model: {settings.embedding_model}")
            self.model = SentenceTransformer(settings.embedding_model)
            print("✓ Local embedding model loaded")

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if self.use_ollama:
            return await self._embed_with_ollama(text)
        else:
            return self._embed_with_local(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if self.use_ollama:
            # Ollama doesn't have great batch support, so we'll do sequential
            embeddings = []
            for text in texts:
                emb = await self._embed_with_ollama(text)
                embeddings.append(emb)
            return embeddings
        else:
            return self._embed_batch_local(texts)

    async def _embed_with_ollama(self, text: str) -> List[float]:
        """Generate embedding using Ollama API"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{settings.ollama_url}/api/embeddings",
                    json={
                        "model": settings.ollama_embedding_model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["embedding"]

            except httpx.HTTPError as e:
                print(f"Ollama embedding failed: {e}")
                # Fallback to local model
                if not self.model:
                    self.model = SentenceTransformer(settings.embedding_model)
                return self._embed_with_local(text)

    def _embed_with_local(self, text: str) -> List[float]:
        """Generate embedding using local sentence-transformers"""

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _embed_batch_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch using local model"""

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class DocumentEmbedder:
    """Processes documents and stores embeddings in database"""

    def __init__(self, db_manager, embedding_service: EmbeddingService):
        self.db = db_manager
        self.embedding_service = embedding_service

    async def embed_document(
        self,
        doc_id: str,
        doc_type: str,
        title: str,
        content: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> Dict[str, Any]:
        """
        Chunk and embed a document, storing in database

        Args:
            doc_id: Unique document identifier
            doc_type: Type of document (incident, runbook, etc.)
            title: Document title
            content: Full document content
            chunk_size: Characters per chunk
            chunk_overlap: Overlap between chunks

        Returns:
            Dictionary with embedding statistics
        """

        # Chunk the document
        chunks = self._chunk_text(content, chunk_size, chunk_overlap)

        # Generate embeddings
        embeddings = await self.embedding_service.embed_batch(chunks)

        # Store in database
        async with self.db.get_postgres_connection() as conn:
            inserted_count = 0

            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    # Convert embedding list to pgvector format (string representation)
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'

                    await conn.execute("""
                        INSERT INTO document_embeddings (
                            id,
                            document_id,
                            document_type,
                            document_title,
                            chunk_text,
                            chunk_index,
                            embedding
                        ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6::vector)
                    """,
                        doc_id,
                        doc_type,
                        title,
                        chunk,
                        idx,
                        embedding_str
                    )
                    inserted_count += 1

                except Exception as e:
                    print(f"Error inserting chunk {idx}: {e}")

        return {
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "embeddings_stored": inserted_count
        }

    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """
        Split text into overlapping chunks

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end
                last_period = chunk.rfind('. ')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)

                if break_point > chunk_size * 0.5:  # Only break if we're past halfway
                    chunk = chunk[:break_point + 1]
                    end = start + len(chunk)

            chunks.append(chunk.strip())

            # Move start position with overlap
            start = end - overlap

        return [c for c in chunks if c]  # Filter empty chunks

    async def embed_all_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Embed all documents from walking skeleton data

        Args:
            documents: List of document dictionaries

        Returns:
            Statistics about embedded documents
        """

        total_chunks = 0
        total_embeddings = 0

        for doc in documents:
            doc_id = doc["id"]
            doc_type = doc["type"]
            title = doc["title"]
            content = doc["content"]

            print(f"  Embedding: {title[:60]}...")

            result = await self.embed_document(
                doc_id,
                doc_type,
                title,
                content
            )

            total_chunks += result["chunks_created"]
            total_embeddings += result["embeddings_stored"]

        return {
            "documents_processed": len(documents),
            "total_chunks": total_chunks,
            "total_embeddings": total_embeddings
        }

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents using vector similarity search

        Args:
            query: Search query
            top_k: Number of results to return
            doc_type: Optional filter by document type

        Returns:
            List of similar document chunks with scores
        """

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Search in database using cosine similarity
        async with self.db.get_postgres_connection() as conn:
            # Convert query embedding to pgvector format
            query_embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

            if doc_type:
                results = await conn.fetch("""
                    SELECT
                        document_id,
                        document_type,
                        document_title,
                        chunk_text,
                        chunk_index,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM document_embeddings
                    WHERE document_type = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """, query_embedding_str, doc_type, top_k)
            else:
                results = await conn.fetch("""
                    SELECT
                        document_id,
                        document_type,
                        document_title,
                        chunk_text,
                        chunk_index,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM document_embeddings
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                """, query_embedding_str, top_k)

        initial_results = [
            {
                "document_id": row["document_id"],
                "document_type": row["document_type"],
                "title": row["document_title"],
                "text": row["chunk_text"],
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"])
            }
            for row in results
        ]

        # Context expansion: for the top 3 scoring documents, fetch ALL their chunks
        # so the LLM sees complete documents, not just fragments
        if initial_results:
            # Identify unique top documents (up to 3)
            seen_doc_ids = []
            for r in initial_results:
                if r["document_id"] not in seen_doc_ids:
                    seen_doc_ids.append(r["document_id"])
                if len(seen_doc_ids) >= 3:
                    break

            expanded_results = list(initial_results)

            async with self.db.get_postgres_connection() as conn:
                for doc_id in seen_doc_ids:
                    doc_sim = next(
                        (r["similarity"] for r in initial_results if r["document_id"] == doc_id),
                        0.5
                    )
                    existing_chunks = {
                        r["chunk_index"] for r in expanded_results
                        if r["document_id"] == doc_id
                    }

                    missing = await conn.fetch("""
                        SELECT document_id, document_type, document_title,
                               chunk_text, chunk_index
                        FROM document_embeddings
                        WHERE document_id = $1
                        ORDER BY chunk_index
                    """, doc_id)

                    for row in missing:
                        if row["chunk_index"] not in existing_chunks:
                            expanded_results.append({
                                "document_id": row["document_id"],
                                "document_type": row["document_type"],
                                "title": row["document_title"],
                                "text": row["chunk_text"],
                                "chunk_index": row["chunk_index"],
                                "similarity": doc_sim * 0.9
                            })

            # Sort: expanded documents in chunk order first, then rest by similarity
            expanded_doc_chunks = []
            for doc_id in seen_doc_ids:
                doc_chunks = sorted(
                    [r for r in expanded_results if r["document_id"] == doc_id],
                    key=lambda x: x["chunk_index"]
                )
                expanded_doc_chunks.extend(doc_chunks)

            other_chunks = sorted(
                [r for r in expanded_results if r["document_id"] not in seen_doc_ids],
                key=lambda x: -x["similarity"]
            )
            initial_results = expanded_doc_chunks + other_chunks

        # Hybrid search: supplement with keyword-matched documents
        keyword_results = await self._keyword_search(query, top_k=5)
        existing_doc_chunk_keys = {
            (r["document_id"], r["chunk_index"]) for r in initial_results
        }
        for kr in keyword_results:
            key = (kr["document_id"], kr["chunk_index"])
            if key not in existing_doc_chunk_keys:
                initial_results.append(kr)
                existing_doc_chunk_keys.add(key)

        return initial_results

    async def _keyword_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based search using PostgreSQL full-text or ILIKE.
        Supplements vector search for cases where exact terms matter.
        """
        # Extract significant keywords from query
        stop_words = {
            'what', 'which', 'who', 'where', 'when', 'how', 'is', 'are', 'does',
            'the', 'a', 'an', 'do', 'did', 'has', 'have', 'had', 'for', 'to',
            'from', 'on', 'with', 'by', 'in', 'of', 'at', 'be', 'was', 'were',
            'been', 'being', 'will', 'would', 'could', 'should', 'can', 'may',
            'this', 'that', 'these', 'those', 'it', 'its', 'their', 'and', 'or',
            'but', 'not', 'than', 'about', 'between', 'many', 'much', 'most',
            'name', 'total', 'expected', 'company', 'value'
        }

        words = query.lower().split()
        keywords = [w.strip('?.,!()"\'-') for w in words if w.lower().strip('?.,!()"\'-') not in stop_words and len(w.strip('?.,!()"\'-')) > 2]

        if not keywords:
            return []

        results = []
        async with self.db.get_postgres_connection() as conn:
            for keyword in keywords[:4]:  # Limit to top 4 keywords
                rows = await conn.fetch("""
                    SELECT document_id, document_type, document_title,
                           chunk_text, chunk_index
                    FROM document_embeddings
                    WHERE chunk_text ILIKE $1
                    ORDER BY chunk_index
                    LIMIT $2
                """, f'%{keyword}%', top_k)

                for row in rows:
                    results.append({
                        "document_id": row["document_id"],
                        "document_type": row["document_type"],
                        "title": row["document_title"],
                        "text": row["chunk_text"],
                        "chunk_index": row["chunk_index"],
                        "similarity": 0.6  # Keyword match baseline similarity
                    })

        # Deduplicate by (document_id, chunk_index)
        seen = set()
        unique = []
        for r in results:
            key = (r["document_id"], r["chunk_index"])
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:top_k * 2]
