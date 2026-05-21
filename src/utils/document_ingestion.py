"""
Document Ingestion Pipeline

Handles PDF, DOCX, Markdown, and plain text files.
Performs sentence-aware chunking while preserving sentence boundaries.

Key features:
- Sentence boundary detection
- Chunk size management (512 tokens default)
- Overlap between chunks for context
- Sentence provenance tracking
"""

import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Sentence:
    """Represents a single sentence with its metadata"""
    text: str
    start_pos: int  # Character position in document
    end_pos: int
    sentence_index: int  # 0-based index in document


@dataclass
class DocumentChunk:
    """Represents a chunk of text with sentence boundaries preserved"""
    chunk_id: str
    text: str
    sentences: List[Sentence]
    chunk_index: int
    metadata: Dict[str, Any]


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents and creating sentence-aware chunks"""

    def __init__(
        self,
        chunk_size: int = 512,  # tokens
        chunk_overlap: int = 50,  # tokens
        min_sentence_length: int = 10  # characters
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_sentence_length = min_sentence_length

    def ingest_document(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a document from file path

        Args:
            file_path: Path to document file
            document_type: Type of document (incident, runbook, etc.)
            metadata: Additional metadata

        Returns:
            Dictionary with document text, chunks, and metadata
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        # Determine file type and extract text
        extension = path.suffix.lower()

        if extension == ".txt":
            text = self._read_text_file(path)
        elif extension == ".md":
            text = self._read_markdown_file(path)
        elif extension == ".pdf":
            text = self._read_pdf_file(path)
        elif extension in [".docx", ".doc"]:
            text = self._read_docx_file(path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        # Process document
        return self.process_text(
            text=text,
            document_id=str(uuid.uuid4()),
            document_type=document_type or "document",
            title=path.stem,
            metadata=metadata or {}
        )

    def process_text(
        self,
        text: str,
        document_id: str,
        document_type: str,
        title: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process raw text into sentence-aware chunks

        Args:
            text: Raw document text
            document_id: Unique document identifier
            document_type: Type of document
            title: Document title
            metadata: Additional metadata

        Returns:
            Dictionary with document info and chunks
        """

        # Step 1: Split into sentences
        sentences = self._split_into_sentences(text)

        print(f"  → Split into {len(sentences)} sentences")

        # Step 2: Create chunks with sentence boundaries
        chunks = self._create_chunks(sentences)

        print(f"  → Created {len(chunks)} chunks")

        return {
            "document_id": document_id,
            "document_type": document_type,
            "title": title,
            "text": text,
            "sentence_count": len(sentences),
            "chunk_count": len(chunks),
            "chunks": chunks,
            "metadata": {
                **metadata,
                "ingested_at": datetime.utcnow().isoformat(),
                "file_size_chars": len(text)
            }
        }

    def _read_text_file(self, path: Path) -> str:
        """Read plain text file"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _read_markdown_file(self, path: Path) -> str:
        """Read markdown file (treat as plain text for now)"""
        return self._read_text_file(path)

    def _read_pdf_file(self, path: Path) -> str:
        """Read PDF file using PyPDF2"""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 required for PDF support: pip install PyPDF2")

        text = []
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text())

        return "\n\n".join(text)

    def _read_docx_file(self, path: Path) -> str:
        """Read DOCX file using python-docx"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx required for DOCX support: pip install python-docx")

        doc = Document(path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)

    def _split_into_sentences(self, text: str) -> List[Sentence]:
        """
        Split text into sentences with position tracking

        Uses simple sentence boundary detection:
        - Period, exclamation, question mark followed by space and capital letter
        - Or followed by newline/end of string
        - Tracks character positions
        """

        # Simple sentence boundary pattern
        # Matches: . ! ? followed by (space + capital) or newline or end
        sentence_pattern = r'([.!?]+)(\s+(?=[A-Z])|[\n]+|$)'

        # Split text, keeping delimiters
        parts = re.split(sentence_pattern, text)

        sentences = []
        current_pos = 0
        sentence_index = 0

        # Combine text with its delimiter
        i = 0
        while i < len(parts):
            if not parts[i].strip():
                i += 1
                continue

            sentence_text = parts[i]

            # Add punctuation if it exists
            if i + 1 < len(parts) and parts[i + 1]:
                sentence_text += parts[i + 1]

            # Add whitespace if it exists
            if i + 2 < len(parts) and parts[i + 2]:
                sentence_text += parts[i + 2]

            i += 3

            # Clean up the sentence
            sentence_text = sentence_text.strip()

            # Skip empty or too-short sentences
            if len(sentence_text) < self.min_sentence_length:
                current_pos += len(sentence_text)
                continue

            sentences.append(Sentence(
                text=sentence_text,
                start_pos=current_pos,
                end_pos=current_pos + len(sentence_text),
                sentence_index=sentence_index
            ))

            current_pos += len(sentence_text) + 1  # +1 for space
            sentence_index += 1

        return sentences

    def _create_chunks(self, sentences: List[Sentence]) -> List[DocumentChunk]:
        """
        Create chunks from sentences, preserving sentence boundaries

        Strategy:
        - Add complete sentences to chunk until approaching size limit
        - Never split a sentence across chunks
        - Include overlap with previous chunk for context
        """

        if not sentences:
            return []

        chunks = []
        current_sentences = []
        current_token_count = 0
        chunk_index = 0

        for sentence in sentences:
            # Rough token estimation: ~4 chars per token
            sentence_tokens = len(sentence.text) // 4

            # Check if adding this sentence would exceed chunk size
            if current_token_count + sentence_tokens > self.chunk_size and current_sentences:
                # Create chunk with current sentences
                chunk = self._create_chunk(current_sentences, chunk_index)
                chunks.append(chunk)
                chunk_index += 1

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_sentences)
                current_sentences = overlap_sentences
                current_token_count = sum(len(s.text) // 4 for s in overlap_sentences)

            # Add sentence to current chunk
            current_sentences.append(sentence)
            current_token_count += sentence_tokens

        # Add final chunk if it has sentences
        if current_sentences:
            chunk = self._create_chunk(current_sentences, chunk_index)
            chunks.append(chunk)

        return chunks

    def _get_overlap_sentences(self, sentences: List[Sentence]) -> List[Sentence]:
        """Get last N sentences for overlap with next chunk"""

        overlap_tokens = 0
        overlap_sentences = []

        # Work backwards from end
        for sentence in reversed(sentences):
            sentence_tokens = len(sentence.text) // 4

            if overlap_tokens + sentence_tokens > self.chunk_overlap:
                break

            overlap_sentences.insert(0, sentence)
            overlap_tokens += sentence_tokens

        return overlap_sentences

    def _create_chunk(
        self,
        sentences: List[Sentence],
        chunk_index: int
    ) -> DocumentChunk:
        """Create a document chunk from sentences"""

        chunk_text = " ".join(s.text for s in sentences)

        return DocumentChunk(
            chunk_id=str(uuid.uuid4()),
            text=chunk_text,
            sentences=sentences,
            chunk_index=chunk_index,
            metadata={
                "sentence_count": len(sentences),
                "first_sentence_index": sentences[0].sentence_index if sentences else 0,
                "last_sentence_index": sentences[-1].sentence_index if sentences else 0,
                "char_count": len(chunk_text),
                "token_estimate": len(chunk_text) // 4
            }
        )


def ingest_runbook_for_testing(file_path: str) -> Dict[str, Any]:
    """
    Convenience function for ingesting a runbook for testing

    Args:
        file_path: Path to runbook file

    Returns:
        Ingested document with chunks
    """

    pipeline = DocumentIngestionPipeline(
        chunk_size=512,
        chunk_overlap=50
    )

    print(f"\n{'='*60}")
    print(f"INGESTING DOCUMENT: {Path(file_path).name}")
    print(f"{'='*60}")

    result = pipeline.ingest_document(
        file_path=file_path,
        document_type="runbook",
        metadata={"source": "test_ingestion"}
    )

    print(f"\nDocument Summary:")
    print(f"  Title: {result['title']}")
    print(f"  Type: {result['document_type']}")
    print(f"  Sentences: {result['sentence_count']}")
    print(f"  Chunks: {result['chunk_count']}")
    print(f"  Total Characters: {result['metadata']['file_size_chars']}")

    print(f"\nChunk Details:")
    for i, chunk in enumerate(result['chunks']):
        print(f"  Chunk {i}:")
        print(f"    Sentences: {chunk.metadata['sentence_count']}")
        print(f"    Tokens: ~{chunk.metadata['token_estimate']}")
        print(f"    Preview: {chunk.text[:100]}...")

    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    # Test with a sample text
    sample_text = """
    This is a runbook for troubleshooting database connection issues.
    The payment-api service depends on the payments-db database.
    When connection pool exhaustion occurs, you should check current connections.
    Run this query: SELECT count(*) FROM pg_stat_activity.
    If the count exceeds max_connections, you need to increase the limit.
    Contact the platform-team for assistance.
    They can be reached via the #platform Slack channel.
    """

    pipeline = DocumentIngestionPipeline()
    result = pipeline.process_text(
        text=sample_text,
        document_id="test-001",
        document_type="runbook",
        title="Test Runbook",
        metadata={}
    )

    print(f"Processed {result['chunk_count']} chunks from {result['sentence_count']} sentences")
