"""
Document Ingestion Pipeline for Context Foundry MVP2.
Coordinates document loading, chunking, and storage.
"""
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .document_loader import DocumentLoader, LoadedDocument
from .chunker import SentenceAwareChunker, MarkdownChunker, Chunk, Sentence


@dataclass
class IngestionResult:
    """Result of ingesting a document."""
    document_id: str
    title: str
    source_path: str
    chunk_count: int
    sentence_count: int
    total_tokens: int
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "source_path": self.source_path,
            "chunk_count": self.chunk_count,
            "sentence_count": self.sentence_count,
            "total_tokens": self.total_tokens,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class IngestionStats:
    """Statistics for an ingestion run."""
    documents_processed: int = 0
    documents_succeeded: int = 0
    documents_failed: int = 0
    total_chunks: int = 0
    total_sentences: int = 0
    total_tokens: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "documents_processed": self.documents_processed,
            "documents_succeeded": self.documents_succeeded,
            "documents_failed": self.documents_failed,
            "total_chunks": self.total_chunks,
            "total_sentences": self.total_sentences,
            "total_tokens": self.total_tokens,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            ),
        }


@dataclass
class IngestedDocument:
    """A fully ingested document with chunks and sentences."""
    document: LoadedDocument
    chunks: List[Chunk]
    sentences: List[Sentence]
    
    def to_dict(self) -> Dict:
        return {
            "document": self.document.to_dict(),
            "chunks": [c.to_dict() for c in self.chunks],
            "sentences": [s.to_dict() for s in self.sentences],
        }


class IngestionPipeline:
    """
    Document ingestion pipeline that coordinates loading, chunking, and processing.
    
    Features:
    - Supports PDF, DOCX, MD, TXT files
    - Sentence-aware chunking with configurable max tokens
    - Overlap between chunks for context preservation
    - Callbacks for progress tracking
    """
    
    def __init__(
        self,
        max_tokens: int = 512,
        overlap_sentences: int = 1,
        min_chunk_size: int = 50,
        on_document_processed: Optional[Callable[[IngestionResult], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize the ingestion pipeline.
        
        Args:
            max_tokens: Maximum tokens per chunk
            overlap_sentences: Number of sentences to overlap between chunks
            min_chunk_size: Minimum characters for a chunk
            on_document_processed: Callback called after each document is processed
            on_progress: Callback called with (current, total) for progress updates
        """
        self.loader = DocumentLoader()
        self.text_chunker = SentenceAwareChunker(
            max_tokens=max_tokens,
            overlap_sentences=overlap_sentences,
            min_chunk_size=min_chunk_size,
        )
        self.markdown_chunker = MarkdownChunker(
            max_tokens=max_tokens,
            overlap_sentences=overlap_sentences,
            min_chunk_size=min_chunk_size,
        )
        self.on_document_processed = on_document_processed
        self.on_progress = on_progress
    
    def _get_chunker(self, file_type: str) -> SentenceAwareChunker:
        """Get appropriate chunker for file type."""
        if file_type == "markdown":
            return self.markdown_chunker
        return self.text_chunker
    
    def ingest_document(self, path: str) -> IngestedDocument:
        """
        Ingest a single document.
        
        Args:
            path: Path to the document
            
        Returns:
            IngestedDocument with document, chunks, and sentences
        """
        document = self.loader.load(path)
        chunker = self._get_chunker(document.file_type)
        chunks, sentences = chunker.chunk_with_context(
            document.id,
            document.content,
            document.title,
        )
        
        return IngestedDocument(
            document=document,
            chunks=chunks,
            sentences=sentences,
        )
    
    def ingest_string(
        self,
        content: str,
        title: str,
        source: str = "inline",
        file_type: str = "text",
    ) -> IngestedDocument:
        """
        Ingest a document from a string.
        
        Args:
            content: Document content
            title: Document title
            source: Source identifier
            file_type: File type (text, markdown, etc.)
            
        Returns:
            IngestedDocument with document, chunks, and sentences
        """
        document = self.loader.load_from_string(content, title, source, file_type)
        chunker = self._get_chunker(file_type)
        chunks, sentences = chunker.chunk_with_context(
            document.id,
            document.content,
            document.title,
        )
        
        return IngestedDocument(
            document=document,
            chunks=chunks,
            sentences=sentences,
        )
    
    def ingest_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> tuple[List[IngestedDocument], IngestionStats]:
        """
        Ingest all documents from a directory.
        
        Args:
            directory: Path to the directory
            recursive: Whether to search subdirectories
            extensions: List of file extensions to include (None for all supported)
            
        Returns:
            Tuple of (list of IngestedDocuments, IngestionStats)
        """
        stats = IngestionStats(started_at=datetime.now())
        results = []
        
        documents = self.loader.load_directory(directory, recursive, extensions)
        total = len(documents)
        
        for i, document in enumerate(documents):
            stats.documents_processed += 1
            
            try:
                chunker = self._get_chunker(document.file_type)
                chunks, sentences = chunker.chunk_with_context(
                    document.id,
                    document.content,
                    document.title,
                )
                
                ingested = IngestedDocument(
                    document=document,
                    chunks=chunks,
                    sentences=sentences,
                )
                results.append(ingested)
                
                total_tokens = sum(c.token_count for c in chunks)
                
                result = IngestionResult(
                    document_id=document.id,
                    title=document.title,
                    source_path=document.source_path,
                    chunk_count=len(chunks),
                    sentence_count=len(sentences),
                    total_tokens=total_tokens,
                    success=True,
                )
                
                stats.documents_succeeded += 1
                stats.total_chunks += len(chunks)
                stats.total_sentences += len(sentences)
                stats.total_tokens += total_tokens
                
                if self.on_document_processed:
                    self.on_document_processed(result)
                
            except Exception as e:
                error_msg = f"{document.source_path}: {str(e)}"
                stats.documents_failed += 1
                stats.errors.append(error_msg)
                
                result = IngestionResult(
                    document_id=document.id,
                    title=document.title,
                    source_path=document.source_path,
                    chunk_count=0,
                    sentence_count=0,
                    total_tokens=0,
                    success=False,
                    error=str(e),
                )
                
                if self.on_document_processed:
                    self.on_document_processed(result)
            
            if self.on_progress:
                self.on_progress(i + 1, total)
        
        stats.completed_at = datetime.now()
        return results, stats
    
    def ingest_batch(
        self,
        paths: List[str],
    ) -> tuple[List[IngestedDocument], IngestionStats]:
        """
        Ingest a batch of documents by path.
        
        Args:
            paths: List of document paths
            
        Returns:
            Tuple of (list of IngestedDocuments, IngestionStats)
        """
        stats = IngestionStats(started_at=datetime.now())
        results = []
        total = len(paths)
        
        for i, path in enumerate(paths):
            stats.documents_processed += 1
            
            try:
                ingested = self.ingest_document(path)
                results.append(ingested)
                
                total_tokens = sum(c.token_count for c in ingested.chunks)
                
                result = IngestionResult(
                    document_id=ingested.document.id,
                    title=ingested.document.title,
                    source_path=path,
                    chunk_count=len(ingested.chunks),
                    sentence_count=len(ingested.sentences),
                    total_tokens=total_tokens,
                    success=True,
                )
                
                stats.documents_succeeded += 1
                stats.total_chunks += len(ingested.chunks)
                stats.total_sentences += len(ingested.sentences)
                stats.total_tokens += total_tokens
                
                if self.on_document_processed:
                    self.on_document_processed(result)
                
            except Exception as e:
                error_msg = f"{path}: {str(e)}"
                stats.documents_failed += 1
                stats.errors.append(error_msg)
                
                result = IngestionResult(
                    document_id="",
                    title=Path(path).stem,
                    source_path=path,
                    chunk_count=0,
                    sentence_count=0,
                    total_tokens=0,
                    success=False,
                    error=str(e),
                )
                
                if self.on_document_processed:
                    self.on_document_processed(result)
            
            if self.on_progress:
                self.on_progress(i + 1, total)
        
        stats.completed_at = datetime.now()
        return results, stats
