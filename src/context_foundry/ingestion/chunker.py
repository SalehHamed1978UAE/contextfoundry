"""
Sentence-Aware Chunker for Context Foundry MVP2.
Chunks documents while preserving sentence boundaries.
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    chunk_id: str
    document_id: str
    content: str
    start_char: int
    end_char: int
    start_sentence: int
    end_sentence: int
    token_count: int
    metadata: Dict
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "start_sentence": self.start_sentence,
            "end_sentence": self.end_sentence,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


@dataclass
class Sentence:
    """Represents a sentence with position information."""
    index: int
    text: str
    start_char: int
    end_char: int
    
    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }


class SentenceAwareChunker:
    """
    Chunks documents while respecting sentence boundaries.
    Ensures chunks don't exceed max_tokens while keeping sentences intact.
    """
    
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\n')
    
    ABBREVIATIONS = {
        'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Sr.', 'Jr.', 'vs.', 'etc.',
        'i.e.', 'e.g.', 'Inc.', 'Ltd.', 'Corp.', 'Co.', 'No.', 'Vol.',
        'Rev.', 'Gen.', 'Col.', 'Lt.', 'Sgt.', 'Capt.', 'Maj.', 'Fig.',
    }
    
    def __init__(
        self,
        max_tokens: int = 512,
        overlap_sentences: int = 1,
        min_chunk_size: int = 50,
    ):
        """
        Initialize the chunker.
        
        Args:
            max_tokens: Maximum tokens per chunk (approximate, uses word count * 1.3)
            overlap_sentences: Number of sentences to overlap between chunks
            min_chunk_size: Minimum characters for a chunk
        """
        self.max_tokens = max_tokens
        self.overlap_sentences = overlap_sentences
        self.min_chunk_size = min_chunk_size
        self.token_ratio = 1.3
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text (words * 1.3 approximation)."""
        word_count = len(text.split())
        return int(word_count * self.token_ratio)
    
    def _split_into_sentences(self, text: str) -> List[Sentence]:
        """Split text into sentences while tracking positions."""
        sentences = []
        current_pos = 0
        sentence_idx = 0
        
        lines = text.split('\n')
        processed_text = text
        
        temp_text = text
        for abbr in self.ABBREVIATIONS:
            temp_text = temp_text.replace(abbr, abbr.replace('.', '<DOT>'))
        
        parts = re.split(r'(?<=[.!?])\s+', temp_text)
        
        for part in parts:
            part = part.replace('<DOT>', '.')
            part = part.strip()
            
            if not part:
                continue
            
            try:
                start_pos = text.find(part, current_pos)
                if start_pos == -1:
                    cleaned = re.sub(r'\s+', ' ', part)
                    for i in range(current_pos, len(text) - len(cleaned) + 1):
                        candidate = re.sub(r'\s+', ' ', text[i:i+len(part)+20])
                        if candidate.startswith(cleaned[:20]):
                            start_pos = i
                            break
                
                if start_pos == -1:
                    start_pos = current_pos
                
                end_pos = start_pos + len(part)
                
                sentences.append(Sentence(
                    index=sentence_idx,
                    text=part,
                    start_char=start_pos,
                    end_char=end_pos,
                ))
                
                sentence_idx += 1
                current_pos = end_pos
                
            except Exception:
                sentences.append(Sentence(
                    index=sentence_idx,
                    text=part,
                    start_char=current_pos,
                    end_char=current_pos + len(part),
                ))
                sentence_idx += 1
                current_pos += len(part) + 1
        
        return sentences
    
    def _create_chunk(
        self,
        document_id: str,
        sentences: List[Sentence],
        chunk_index: int,
    ) -> Chunk:
        """Create a chunk from a list of sentences."""
        content = ' '.join(s.text for s in sentences)
        
        return Chunk(
            chunk_id=f"{document_id}:chunk:{chunk_index}",
            document_id=document_id,
            content=content,
            start_char=sentences[0].start_char,
            end_char=sentences[-1].end_char,
            start_sentence=sentences[0].index,
            end_sentence=sentences[-1].index,
            token_count=self._estimate_tokens(content),
            metadata={
                "sentence_count": len(sentences),
                "char_count": len(content),
            }
        )
    
    def chunk(self, document_id: str, text: str) -> Tuple[List[Chunk], List[Sentence]]:
        """
        Chunk a document into sentence-aware chunks.
        
        Args:
            document_id: ID of the source document
            text: Document text to chunk
            
        Returns:
            Tuple of (chunks, sentences)
        """
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            return [], []
        
        chunks = []
        current_sentences = []
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence.text)
            
            if sentence_tokens > self.max_tokens:
                if current_sentences:
                    chunks.append(self._create_chunk(
                        document_id, current_sentences, chunk_index
                    ))
                    chunk_index += 1
                    current_sentences = []
                    current_tokens = 0
                
                chunks.append(self._create_chunk(
                    document_id, [sentence], chunk_index
                ))
                chunk_index += 1
                continue
            
            if current_tokens + sentence_tokens > self.max_tokens:
                if current_sentences:
                    chunks.append(self._create_chunk(
                        document_id, current_sentences, chunk_index
                    ))
                    chunk_index += 1
                    
                    if self.overlap_sentences > 0 and len(current_sentences) >= self.overlap_sentences:
                        overlap = current_sentences[-self.overlap_sentences:]
                        current_sentences = overlap.copy()
                        current_tokens = sum(
                            self._estimate_tokens(s.text) for s in current_sentences
                        )
                    else:
                        current_sentences = []
                        current_tokens = 0
            
            current_sentences.append(sentence)
            current_tokens += sentence_tokens
        
        if current_sentences:
            content = ' '.join(s.text for s in current_sentences)
            if len(content) >= self.min_chunk_size:
                chunks.append(self._create_chunk(
                    document_id, current_sentences, chunk_index
                ))
        
        return chunks, sentences
    
    def chunk_with_context(
        self,
        document_id: str,
        text: str,
        title: str = "",
    ) -> Tuple[List[Chunk], List[Sentence]]:
        """
        Chunk document and add document context to each chunk.
        
        Args:
            document_id: ID of the source document
            text: Document text to chunk
            title: Document title to prepend as context
            
        Returns:
            Tuple of (chunks, sentences)
        """
        chunks, sentences = self.chunk(document_id, text)
        
        if title:
            for chunk in chunks:
                chunk.metadata["document_title"] = title
        
        return chunks, sentences


class MarkdownChunker(SentenceAwareChunker):
    """
    Specialized chunker for Markdown documents.
    Respects headers and code blocks.
    """
    
    HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    
    def _split_by_headers(self, text: str) -> List[Tuple[str, str]]:
        """Split markdown by headers, returning (header, content) pairs."""
        sections = []
        current_header = ""
        current_content = []
        
        code_blocks = {}
        placeholder_idx = 0
        
        def replace_code(match):
            nonlocal placeholder_idx
            key = f"__CODE_BLOCK_{placeholder_idx}__"
            code_blocks[key] = match.group(0)
            placeholder_idx += 1
            return key
        
        processed_text = self.CODE_BLOCK_PATTERN.sub(replace_code, text)
        
        lines = processed_text.split('\n')
        
        for line in lines:
            header_match = self.HEADER_PATTERN.match(line)
            
            if header_match:
                if current_content or current_header:
                    content = '\n'.join(current_content)
                    for key, block in code_blocks.items():
                        content = content.replace(key, block)
                    sections.append((current_header, content))
                
                current_header = header_match.group(2)
                current_content = []
            else:
                current_content.append(line)
        
        if current_content or current_header:
            content = '\n'.join(current_content)
            for key, block in code_blocks.items():
                content = content.replace(key, block)
            sections.append((current_header, content))
        
        return sections
    
    def chunk(self, document_id: str, text: str) -> Tuple[List[Chunk], List[Sentence]]:
        """Chunk markdown document respecting headers."""
        sections = self._split_by_headers(text)
        
        all_chunks = []
        all_sentences = []
        chunk_offset = 0
        sentence_offset = 0
        
        for header, content in sections:
            if not content.strip():
                continue
            
            section_text = f"{header}\n{content}" if header else content
            chunks, sentences = super().chunk(f"{document_id}:{header or 'intro'}", section_text)
            
            for chunk in chunks:
                chunk.chunk_id = f"{document_id}:chunk:{chunk_offset}"
                chunk.document_id = document_id
                chunk.metadata["section_header"] = header
                chunk_offset += 1
                all_chunks.append(chunk)
            
            for sentence in sentences:
                sentence.index = sentence_offset
                sentence_offset += 1
                all_sentences.append(sentence)
        
        return all_chunks, all_sentences
