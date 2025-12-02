"""
Document Ingestion Pipeline for Context Foundry MVP2.
Handles PDF, DOCX, MD, and TXT files with sentence-aware chunking.
"""
from .document_loader import DocumentLoader
from .chunker import SentenceAwareChunker
from .ingestion_pipeline import IngestionPipeline

__all__ = ["DocumentLoader", "SentenceAwareChunker", "IngestionPipeline"]
