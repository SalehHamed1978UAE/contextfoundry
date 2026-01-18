import os
import sys
import logging
import atexit
import threading
import time
import signal
import socket
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def is_port_available(port, retries=3, delay=1):
    """Check if a port is available for binding with retries."""
    for attempt in range(retries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', port))
                return True
            except OSError:
                if attempt < retries - 1:
                    time.sleep(delay)
    return False


def kill_port_process(port, max_attempts=3):
    """Kill any process using the specified port with retries."""
    import subprocess
    for attempt in range(max_attempts):
        try:
            subprocess.run(['fuser', '-k', f'{port}/tcp'], 
                          stderr=subprocess.DEVNULL, 
                          check=False)
            time.sleep(2)
            if is_port_available(port, retries=1):
                return True
            logging.info(f"[Brain] Port {port} still in use, attempt {attempt + 1}/{max_attempts}")
        except Exception:
            pass
    return False


def shutdown_handler(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    sig_name = signal.Signals(signum).name
    logging.info(f"[Brain] Received {sig_name}, shutting down gracefully...")
    shutdown_all()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

from flask import Flask
from brain.routes.internal import internal_bp
from src.decision_trace_layer.api import dtl_bp
from src.context_foundry.dtl.dtl_http import dtl_core_bp
from src.context_foundry.api.learning_api import learning_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    raise RuntimeError("SESSION_SECRET environment variable required")

app.register_blueprint(internal_bp)
app.register_blueprint(dtl_bp)
app.register_blueprint(dtl_core_bp)
app.register_blueprint(learning_bp)

scheduler = None
extraction_worker_thread = None
extraction_worker_running = False
extraction_worker_stats = {
    "last_run": None,
    "requests_processed": 0,
    "last_error": None,
    "is_running": False
}

VISION_CHARS_PER_PAGE_THRESHOLD = 800
VISION_GARBAGE_RATIO_THRESHOLD = 0.3
VISION_MAX_PAGES = 20
VISION_DPI = 150


def should_use_vision(text: str, page_count: int) -> bool:
    """
    Determine if we should fall back to Claude Vision for extraction.
    Returns True if text extraction is insufficient.
    """
    if page_count == 0:
        return False
    
    if not text or not text.strip():
        return True
    
    chars_per_page = len(text) / page_count
    
    if chars_per_page < VISION_CHARS_PER_PAGE_THRESHOLD:
        logger.info(f"[VisionCheck] Low text yield: {chars_per_page:.0f} chars/page < {VISION_CHARS_PER_PAGE_THRESHOLD} threshold")
        return True
    
    non_ascii_count = sum(1 for c in text if ord(c) > 127 or (ord(c) < 32 and c not in '\n\r\t'))
    garbage_ratio = non_ascii_count / len(text) if text else 0
    
    if garbage_ratio > VISION_GARBAGE_RATIO_THRESHOLD:
        logger.info(f"[VisionCheck] High garbage ratio: {garbage_ratio:.2%} > {VISION_GARBAGE_RATIO_THRESHOLD:.0%} threshold")
        return True
    
    return False


def render_pdf_pages(file_path: str, max_pages: int = VISION_MAX_PAGES, dpi: int = VISION_DPI) -> list:
    """
    Convert PDF pages to base64-encoded JPEG images for Vision processing.
    """
    import base64
    from io import BytesIO
    from pdf2image import convert_from_path
    
    poppler_path = "/nix/store/ibb9lajxj2jr8z0bmriqyc43648b7fql-poppler-utils-25.05.0/bin"
    
    try:
        images = convert_from_path(
            file_path,
            dpi=dpi,
            first_page=1,
            last_page=max_pages,
            poppler_path=poppler_path
        )
        
        base64_images = []
        for i, img in enumerate(images):
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            b64 = base64.standard_b64encode(buffer.getvalue()).decode('utf-8')
            base64_images.append(b64)
            logger.debug(f"[VisionRenderer] Rendered page {i+1}/{len(images)}")
        
        logger.info(f"[VisionRenderer] Rendered {len(base64_images)} pages as JPEG images")
        return base64_images
        
    except Exception as e:
        logger.error(f"[VisionRenderer] Failed to render PDF pages: {e}")
        return []


def extract_with_vision(images: list, entity_types: list) -> dict:
    """
    Extract entities directly from page images using Claude Vision.
    
    Args:
        images: List of base64-encoded JPEG images
        entity_types: List of entity type names to extract
        
    Returns:
        Dict with 'entities' list and 'document_summary'
    """
    import anthropic
    import json
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("[VisionExtractor] ANTHROPIC_API_KEY not set")
        return {"entities": [], "document_summary": "API key not configured"}
    
    client = anthropic.Anthropic(api_key=api_key)
    
    content = []
    
    for i, img_b64 in enumerate(images):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img_b64
            }
        })
        content.append({
            "type": "text",
            "text": f"[Page {i+1}]"
        })
    
    entity_type_str = ', '.join(entity_types)
    content.append({
        "type": "text",
        "text": f"""Analyze all pages above and extract entities. This is a knowledge extraction task.

Entity types to extract: {entity_type_str}

For each entity found, provide:
- name: The entity name exactly as it appears in the document
- type: One of the entity types listed above (use UPPERCASE)
- confidence: Your confidence in this extraction (0.0-1.0)
- context: Brief context where it appears (1 sentence)

IMPORTANT EXTRACTION RULES:
- Extract ALL relevant entities - do not limit yourself
- Capture EVERY concept, framework, methodology, metric, process, person, organization
- Include financial terms (NPV, IRR, EBITDA, etc.)
- Include risk categories (Technical Risk, Financial Risk, Operational Risk, etc.)
- Include strategic frameworks and pillars
- Include commercialization stages and phases
- Be thorough - this document contains valuable knowledge

Return JSON format only, no markdown:
{{
    "entities": [
        {{"name": "Entity Name", "type": "CONCEPT", "confidence": 0.9, "context": "Brief context"}},
        ...
    ],
    "document_summary": "Brief 2-3 sentence summary of document content"
}}"""
    })
    
    try:
        logger.info(f"[VisionExtractor] Sending {len(images)} pages to Claude Vision...")
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": content}]
        )
        
        response_text = response.content[0].text
        
        response_text = response_text.strip()
        if response_text.startswith("```"):
            import re
            response_text = re.sub(r"```json?\n?", "", response_text)
            response_text = re.sub(r"\n?```$", "", response_text)
        
        result = json.loads(response_text)
        
        entity_count = len(result.get("entities", []))
        logger.info(f"[VisionExtractor] Extracted {entity_count} entities from {len(images)} pages")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"[VisionExtractor] JSON parse error: {e}")
        logger.debug(f"[VisionExtractor] Raw response: {response_text[:500]}...")
        return {"entities": [], "document_summary": "Failed to parse response"}
    except Exception as e:
        logger.error(f"[VisionExtractor] Vision API error: {e}")
        return {"entities": [], "document_summary": str(e)}


def extract_text_from_file(file_path: str, file_name: str = None) -> tuple:
    """
    Extract text from various file types (PDF, DOCX, plain text).
    Returns: (text, method, page_count)
    method: 'text' | 'ocr' | 'vision_required'
    """
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"[TextExtractor] File not found: {file_path}")
        return "", "text", 0
    
    extension = ""
    if file_name:
        extension = os.path.splitext(file_name)[1].lower().lstrip('.')
    if not extension:
        extension = os.path.splitext(file_path)[1].lower().lstrip('.')
    
    logger.info(f"[TextExtractor] Extracting text from {file_name or file_path} (type: {extension})")
    
    if extension == 'pdf':
        text = ""
        page_count = 0
        method = "text"
        
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            page_count = len(reader.pages)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = "\n\n".join(text_parts)
            if text.strip() and not should_use_vision(text, page_count):
                logger.info(f"[TextExtractor] PDF parsed with pypdf: {page_count} pages, {len(text)} characters")
                return text, "text", page_count
        except Exception as e:
            logger.warning(f"[TextExtractor] pypdf failed: {e}")
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                text = "\n\n".join(text_parts)
                if text.strip() and not should_use_vision(text, page_count):
                    logger.info(f"[TextExtractor] PDF parsed with pdfplumber: {page_count} pages, {len(text)} characters")
                    return text, "text", page_count
        except Exception as e:
            logger.warning(f"[TextExtractor] pdfplumber failed: {e}")
        
        if not text.strip() or should_use_vision(text, page_count):
            logger.info(f"[TextExtractor] PDF has {page_count} pages but insufficient text. Attempting OCR...")
            try:
                from pdf2image import convert_from_path
                import pytesseract
                
                poppler_path = "/nix/store/ibb9lajxj2jr8z0bmriqyc43648b7fql-poppler-utils-25.05.0/bin"
                images = convert_from_path(file_path, dpi=200, poppler_path=poppler_path)
                ocr_parts = []
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image)
                    if page_text.strip():
                        ocr_parts.append(page_text.strip())
                    logger.debug(f"[TextExtractor] OCR page {i+1}/{len(images)}: {len(page_text)} chars")
                
                text = "\n\n".join(ocr_parts)
                method = "ocr"
                
                if text.strip() and not should_use_vision(text, page_count):
                    logger.info(f"[TextExtractor] PDF OCR successful: {len(images)} pages, {len(text)} characters")
                    return text, "ocr", page_count
                else:
                    chars_per_page = len(text) / page_count if page_count > 0 else 0
                    logger.info(f"[TextExtractor] OCR insufficient ({len(text)} chars, {chars_per_page:.0f}/page), Vision required")
                    return text, "vision_required", page_count
                    
            except ImportError as e:
                logger.warning(f"[TextExtractor] OCR dependencies not available: {e}")
            except Exception as e:
                logger.error(f"[TextExtractor] OCR failed: {e}")
        
        if should_use_vision(text, page_count):
            return text, "vision_required", page_count
        return text, method, page_count
    
    elif extension in ['doc', 'docx']:
        try:
            from docx import Document
            doc = Document(file_path)
            text_parts = []
            
            # 1. Document properties (often contains the title)
            try:
                if doc.core_properties.title:
                    text_parts.append(f"DOCUMENT TITLE: {doc.core_properties.title}")
                if doc.core_properties.subject:
                    text_parts.append(f"SUBJECT: {doc.core_properties.subject}")
            except Exception:
                pass
            
            # 2. Headers from all sections (put at start for visibility)
            for section in doc.sections:
                try:
                    if section.header:
                        for para in section.header.paragraphs:
                            header_text = para.text.strip()
                            if header_text:
                                text_parts.append(f"HEADER: {header_text}")
                except Exception:
                    pass
            
            # 3. All paragraphs (main body)
            for para in doc.paragraphs:
                para_text = para.text.strip()
                if para_text:
                    # Check if it's a heading (likely important entity)
                    if para.style and para.style.name and 'Heading' in para.style.name:
                        text_parts.append(f"SECTION: {para_text}")
                    else:
                        text_parts.append(para_text)
            
            # 4. All tables
            for table in doc.tables:
                table_rows = []
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        table_rows.append(" | ".join(row_cells))
                if table_rows:
                    text_parts.append("TABLE CONTENT:")
                    text_parts.extend(table_rows)
            
            # 5. Footers from all sections
            for section in doc.sections:
                try:
                    if section.footer:
                        for para in section.footer.paragraphs:
                            footer_text = para.text.strip()
                            if footer_text:
                                text_parts.append(f"FOOTER: {footer_text}")
                except Exception:
                    pass
            
            text = "\n".join(text_parts)
            logger.info(f"[TextExtractor] DOCX parsed (complete): {len(text)} characters")
            return text, "text", 0
        except Exception as e:
            logger.error(f"[TextExtractor] DOCX extraction error: {e}")
            return "", "text", 0
    
    else:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            logger.info(f"[TextExtractor] Plain text read: {len(text)} characters")
            return text, "text", 0
        except Exception as e:
            logger.error(f"[TextExtractor] Text read error: {e}")
            return "", "text", 0


ENABLE_PROGRESS_TRACKING = os.environ.get("ENABLE_PROGRESS_TRACKING", "false").lower() == "true"


def get_progress_tracker():
    """Get progress tracker if enabled, None otherwise."""
    if not ENABLE_PROGRESS_TRACKING:
        return None
    try:
        from src.context_foundry.pipeline.progress import ProgressTracker
        return ProgressTracker()
    except Exception as e:
        logger.warning(f"[ProgressTracker] Failed to initialize: {e}")
        return None


def process_extraction_queue():
    """
    Process pending extraction requests from the queue.
    Claims one request at a time, runs extraction, saves results.
    
    If ENABLE_PROGRESS_TRACKING=true, uses ProgressTracker for checkpointing.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("[ExtractionWorker] DATABASE_URL not set")
        return 0
    
    worker_id = f"brain-worker-{os.getpid()}"
    processed = 0
    tracker = get_progress_tracker()
    
    try:
        conn = psycopg2.connect(database_url)
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM platform.claim_extraction_request(%s)", (worker_id,))
            request = cur.fetchone()
            conn.commit()
            
            if not request or not request.get('id'):
                conn.close()
                return 0
            
            logger.info(f"[ExtractionWorker] Claimed request: {request.get('request_id')} for document {request.get('document_id')}")
        
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE platform.extraction_requests SET status = 'processing' WHERE id = %s",
                (request['id'],)
            )
            conn.commit()
            cur.close()
            
            file_path = request.get('file_path')
            file_name = request.get('file_name')
            tenant_id = str(request.get('tenant_id'))
            document_id = str(request.get('document_id'))
            request_id = str(request.get('request_id'))
            
            if tracker:
                from src.context_foundry.pipeline.progress import IngestionStep
                tracker.start(document_id, tenant_id)
                tracker.update(document_id, IngestionStep.READING, {"file_name": file_name})
            
            text_content, extraction_method, page_count = extract_text_from_file(file_path, file_name)
            
            if tracker:
                tracker.update(document_id, IngestionStep.CLASSIFYING, {"chars": len(text_content), "method": extraction_method})
            
            start_time = datetime.utcnow()
            
            from src.context_foundry.extraction import ExtractionPipeline
            from src.context_foundry.extraction.staging_loader import StagingLoader
            from src.context_foundry.extraction.entity_extractor import ExtractedEntity
            from src.context_foundry.models.schema import tenant_session
            from brain.classifier import CORE_FOUNDATION_TYPES
            
            use_ontology_centric = os.environ.get("USE_ONTOLOGY_CENTRIC_PIPELINE", "").lower() in ("true", "1", "yes")
            
            entities_count = 0
            relations_count = 0
            model_used = 'gpt-4o-mini'
            extraction_success = False
            extracted_entities = []
            
            if extraction_method == "vision_required":
                logger.info(f"[ExtractionWorker] Using Vision extraction for {file_name}")
                
                images = render_pdf_pages(file_path, max_pages=VISION_MAX_PAGES, dpi=VISION_DPI)
                
                if images:
                    entity_types = CORE_FOUNDATION_TYPES
                    vision_result = extract_with_vision(images, entity_types)
                    
                    for ve in vision_result.get("entities", []):
                        entity = ExtractedEntity(
                            id=f"vision-{ve.get('name', 'unknown').lower().replace(' ', '-')}",
                            entity_type=ve.get("type", "CONCEPT").upper(),
                            canonical_name=ve.get("name", "Unknown"),
                            properties={"context": ve.get("context", "")},
                            source_span=ve.get("name", ""),
                            source_document_id=document_id,
                            source_chunk_id=f"{document_id}:vision",
                            source_sentence_idx=0,
                            confidence=float(ve.get("confidence", 0.8)),
                        )
                        extracted_entities.append(entity)
                    
                    logger.info(f"[VisionExtractor] Created {len(extracted_entities)} ExtractedEntity objects")
                    extraction_method = "vision"
                    model_used = "claude-sonnet-4-20250514"
                    extraction_success = len(extracted_entities) > 0
                else:
                    logger.error(f"[ExtractionWorker] Failed to render PDF pages for Vision")
                    extraction_method = "vision_failed"
                    extraction_success = False
            else:
                if not text_content:
                    logger.warning(f"[ExtractionWorker] No text extracted from {file_name}")
                    text_content = f"Document: {file_name}\n\nContent could not be extracted."
                
                if tracker:
                    tracker.update(document_id, IngestionStep.CHUNKING)
                
                if use_ontology_centric:
                    from src.context_foundry.extraction.ontology_centric_pipeline import OntologyCentricPipeline
                    
                    logger.info(f"[ExtractionWorker] Using OntologyCentricPipeline for {file_name}")
                    
                    if tracker:
                        tracker.update(document_id, IngestionStep.EXTRACTING)
                    
                    with tenant_session(tenant_id) as session:
                        ontology_pipeline = OntologyCentricPipeline(
                            session=session,
                            tenant_id=tenant_id,
                            model="gpt-4o-mini",
                            enable_canonicalization=True,
                            auto_stage=True,
                        )
                        
                        ontology_result = ontology_pipeline.extract(
                            text=text_content,
                            document_id=document_id,
                            filename=file_name,
                        )
                        
                        extracted_entities = ontology_result.entities
                        extraction_success = ontology_result.success
                        extraction_method = f"ontology_centric_{ontology_result.document_type}"
                        
                        if ontology_result.staging_result:
                            entities_count = ontology_result.staging_result.entities_created + ontology_result.staging_result.entities_updated
                            relations_count = ontology_result.staging_result.relations_created + ontology_result.staging_result.relations_updated
                        else:
                            entities_count = len(ontology_result.entities)
                            relations_count = len(ontology_result.relations)
                        
                        logger.info(f"[ExtractionWorker] OntologyCentric: {entities_count} entities, "
                                   f"{relations_count} relations, type={ontology_result.document_type}")
                    
                    if tracker:
                        tracker.update(document_id, IngestionStep.RELATING, {"entities": len(extracted_entities)})
                    
                    extraction_result = type('ExtractionResult', (), {
                        'entities': extracted_entities,
                        'relations': ontology_result.relations,
                        'success': extraction_success
                    })()
                else:
                    pipeline = ExtractionPipeline(model="gpt-4o-mini", temperature=0.0)
                    
                    if tracker:
                        tracker.update(document_id, IngestionStep.EXTRACTING)
                    
                    extraction_result = pipeline.extract_with_fallback(
                        text=text_content,
                        document_id=document_id,
                        document_title=file_name or "Uploaded Document"
                    )
                    
                    extracted_entities = extraction_result.entities
                    extraction_success = extraction_result.success
                    
                    if tracker:
                        tracker.update(document_id, IngestionStep.RELATING, {"entities": len(extracted_entities)})
            
            if tracker:
                tracker.update(document_id, IngestionStep.STAGING)
            
            if not use_ontology_centric:
                with tenant_session(tenant_id) as session:
                    try:
                        loader = StagingLoader(
                            session=session,
                            enable_deduplication=True,
                            similarity_threshold=0.8,
                            tenant_id=tenant_id
                        )
                        
                        logger.info(f"[ExtractionWorker] Loading {len(extracted_entities)} entities to staging...")
                        
                        extracted_relations = extraction_result.relations if hasattr(extraction_result, 'relations') else []
                        
                        staging_result = loader.load_all(
                            entities=extracted_entities,
                            relations=extracted_relations,
                            commit=True
                        )
                        
                        entities_count = staging_result.entities_created + staging_result.entities_updated
                        relations_count = staging_result.relations_created + staging_result.relations_updated
                        
                        if staging_result.errors:
                            logger.warning(f"[ExtractionWorker] Staging errors: {staging_result.errors}")
                        
                        logger.info(
                            f"[ExtractionWorker] Extraction complete ({extraction_method}): "
                            f"{entities_count} entities ({staging_result.entities_created} created, {staging_result.entities_updated} updated, {staging_result.entities_skipped} skipped), "
                            f"{relations_count} relationships for tenant {tenant_id}"
                        )
                        
                        from src.context_foundry.models.schema import DocumentChunk
                        from src.context_foundry.memory.episodic import openai_embedding
                        import uuid as uuid_module
                        
                        existing_chunks = session.execute(
                            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :doc_id"),
                            {"doc_id": document_id}
                        ).scalar()
                        
                        if existing_chunks == 0 and text_content:
                            chunk_size = 2000
                            overlap = 400
                            chunks_created = 0
                            start_pos = 0
                            chunk_idx = 0
                            
                            while start_pos < len(text_content):
                                end_pos = min(start_pos + chunk_size, len(text_content))
                                chunk_text = text_content[start_pos:end_pos].strip()
                                
                                if chunk_text:
                                    chunk_embedding = None
                                    try:
                                        chunk_embedding = openai_embedding(chunk_text, dim=1536)
                                    except Exception as embed_e:
                                        logger.warning(f"[ExtractionWorker] Failed to generate embedding for chunk {chunk_idx}: {embed_e}")
                                    
                                    db_chunk = DocumentChunk(
                                        id=uuid_module.uuid4(),
                                        document_id=document_id,
                                        tenant_id=tenant_id,
                                        chunk_index=chunk_idx,
                                        text=chunk_text,
                                        char_start=start_pos,
                                        char_end=end_pos,
                                        chunk_metadata={"source": "extraction_worker"},
                                        embedding=chunk_embedding
                                    )
                                    session.add(db_chunk)
                                    chunks_created += 1
                                    chunk_idx += 1
                                
                                start_pos = end_pos - overlap
                                if start_pos >= len(text_content):
                                    break
                            
                            session.commit()
                            logger.info(f"[ExtractionWorker] Created {chunks_created} document chunks with embeddings")
                        
                    except Exception as e:
                        logger.error(f"[ExtractionWorker] Staging error: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        session.rollback()
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            try:
                conn.close()
            except:
                pass
            
            result_conn = psycopg2.connect(database_url)
            result_cur = result_conn.cursor()
            
            import json as json_lib
            extraction_metrics = json_lib.dumps({
                "chars_extracted": len(text_content) if text_content else 0,
                "chars_per_page": len(text_content) / page_count if page_count > 0 and text_content else 0,
                "page_count": page_count,
                "entities_extracted": entities_count,
                "vision_fallback": extraction_method == "vision"
            })
            
            try:
                result_cur.execute("""
                    INSERT INTO platform.extraction_results
                    (request_id, document_id, tenant_id, status,
                     entities_extracted, relationships_extracted,
                     input_tokens, output_tokens, total_tokens,
                     started_at, completed_at, duration_ms,
                     extraction_version, model_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    request_id,
                    document_id,
                    tenant_id,
                    'success' if extraction_success else 'failed',
                    entities_count,
                    relations_count,
                    500,
                    300,
                    800,
                    start_time.isoformat() + 'Z',
                    end_time.isoformat() + 'Z',
                    duration_ms,
                    '1.0.0',
                    model_used
                ))
                
                result_cur.execute("""
                    UPDATE platform.extraction_requests
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = %s
                """, (request['id'],))
                
                result_cur.execute("""
                    UPDATE platform.documents
                    SET status = 'extracted', updated_at = NOW(),
                        extraction_method = %s, extraction_metrics = %s
                    WHERE id = %s
                """, (extraction_method, extraction_metrics, request['document_id'],))
                
                result_conn.commit()
                logger.info(f"[ExtractionWorker] Successfully persisted extraction results for {request['document_id']}")
                
                if tracker:
                    tracker.complete(document_id)
                
            except Exception as db_error:
                logger.error(f"[ExtractionWorker] Failed to persist results: {db_error}")
                result_conn.rollback()
                if tracker:
                    tracker.fail(document_id, str(db_error))
            finally:
                result_cur.close()
                result_conn.close()
            
            processed = 1
            extraction_worker_stats["requests_processed"] += 1
            
        except Exception as e:
            logger.error(f"[ExtractionWorker] Processing error: {e}")
            extraction_worker_stats["last_error"] = str(e)
            
            try:
                fail_conn = psycopg2.connect(database_url)
                fail_cur = fail_conn.cursor()
                fail_cur.execute("""
                    UPDATE platform.extraction_requests
                    SET status = 'failed'
                    WHERE id = %s
                """, (request['id'],))
                fail_conn.commit()
                fail_cur.close()
                fail_conn.close()
            except Exception as fail_error:
                logger.error(f"[ExtractionWorker] Failed to mark request as failed: {fail_error}")
        
        try:
            conn.close()
        except:
            pass
        
    except Exception as e:
        logger.error(f"[ExtractionWorker] Database error: {e}")
        extraction_worker_stats["last_error"] = str(e)
    
    return processed


def extraction_worker_loop():
    """
    Background thread that polls the extraction queue every 30 seconds.
    """
    global extraction_worker_running
    
    logger.info("[ExtractionWorker] Starting extraction worker (5-second interval)")
    extraction_worker_stats["is_running"] = True
    
    while extraction_worker_running:
        try:
            extraction_worker_stats["last_run"] = datetime.utcnow().isoformat()
            processed = process_extraction_queue()
            
            if processed > 0:
                time.sleep(1)
            else:
                for _ in range(5):
                    if not extraction_worker_running:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"[ExtractionWorker] Loop error: {e}")
            extraction_worker_stats["last_error"] = str(e)
            time.sleep(10)
    
    extraction_worker_stats["is_running"] = False
    logger.info("[ExtractionWorker] Extraction worker stopped")


def start_extraction_worker():
    """Start the extraction worker background thread."""
    global extraction_worker_thread, extraction_worker_running
    
    if extraction_worker_thread and extraction_worker_thread.is_alive():
        return
    
    extraction_worker_running = True
    extraction_worker_thread = threading.Thread(target=extraction_worker_loop, daemon=True)
    extraction_worker_thread.start()
    logger.info("[Brain] Extraction worker started (5-second cycles)")


def stop_extraction_worker():
    """Stop the extraction worker background thread."""
    global extraction_worker_running
    extraction_worker_running = False


def get_extraction_worker_status():
    """Get the current status of the extraction worker."""
    global extraction_worker_thread, extraction_worker_running
    
    is_actually_running = (
        extraction_worker_thread is not None 
        and extraction_worker_thread.is_alive()
    )
    
    return {
        "is_running": is_actually_running,
        "last_run": extraction_worker_stats.get("last_run"),
        "requests_processed": extraction_worker_stats.get("requests_processed", 0),
        "last_error": extraction_worker_stats.get("last_error")
    }


def seed_aggregation_definitions(tenant_id: str = None):
    """Seed aggregation definitions for the aggregation framework."""
    try:
        from src.context_foundry.aggregation.seed_definitions import seed_all_definitions
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        import uuid
        
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.warning("[Brain] DATABASE_URL not set, skipping aggregation definitions seeding")
            return
        
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        
        # Use provided tenant_id or default system tenant
        tid = uuid.UUID(tenant_id) if tenant_id else uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        with Session() as session:
            # Set tenant context for RLS
            session.execute(text(f"SET app.current_tenant = '{tid}'"))
            
            stats = seed_all_definitions(session, tid)
            session.commit()
            
            logger.info(f"[Brain] Aggregation definitions seeded: {stats}")
            
    except ImportError:
        logger.debug("[Brain] Aggregation module not available, skipping seeding")
    except Exception as e:
        logger.warning(f"[Brain] Failed to seed aggregation definitions: {e}")


def init_scheduler():
    global scheduler
    if scheduler is None:
        from src.context_foundry.agents.scheduler import GardenerScheduler, SchedulerConfig
        from src.context_foundry.agents.gardener import GardenerConfig
        from src.context_foundry.agents.identity_resolver import IdentityResolutionConfig
        
        config = SchedulerConfig(
            cycle_interval_seconds=30,
            run_identity_resolution=True,
            gardener_config=GardenerConfig(
                min_confidence_for_promotion=0.75,
                min_dwell_time_hours=1.0,
                archive_confidence_threshold=0.4,
            ),
            identity_config=IdentityResolutionConfig(
                auto_merge_threshold=0.95,
                review_threshold=0.70,
                never_auto_merge_types=["PERSON"],
            ),
        )
        scheduler = GardenerScheduler(config=config)
        scheduler.start()
        logger.info("[Brain] Gardener scheduler started (5-minute cycles)")
    return scheduler


def shutdown_scheduler():
    global scheduler
    if scheduler:
        scheduler.stop()
        scheduler = None


def shutdown_all():
    """Shutdown all background processes."""
    stop_extraction_worker()
    shutdown_scheduler()


atexit.register(shutdown_all)


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == '__main__':
    port = int(os.environ.get('BRAIN_PORT', 3000))
    
    # Check if port is available (skip if started via start.sh)
    if not os.environ.get('SKIP_PORT_CHECK'):
        if not is_port_available(port):
            logger.warning(f"[Brain] Port {port} in use, attempting to kill existing process...")
            if kill_port_process(port):
                logger.info(f"[Brain] Successfully freed port {port}")
            else:
                logger.error(f"[Brain] Failed to free port {port}, exiting")
                sys.exit(1)
    else:
        logger.info(f"[Brain] Port check skipped (started via start.sh)")
    
    # Clean up orphaned entities from deleted tenants on startup
    try:
        from src.context_foundry.utils.vault_operations import cleanup_orphaned_entities
        cleanup_result = cleanup_orphaned_entities()
        if cleanup_result.get('total_cleaned', 0) > 0:
            logger.info(f"[Brain] Orphan cleanup: {cleanup_result}")
    except Exception as e:
        logger.warning(f"[Brain] Orphan cleanup failed (non-fatal): {e}")
    
    init_scheduler()
    start_extraction_worker()
    seed_aggregation_definitions(tenant_id='7627d577-e07c-484f-893a-ed2f464d28b9')  # Seed aggregation framework definitions
    logger.info(f"[Brain] Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
