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
    for attempt in range(max_attempts):
        try:
            os.system(f'fuser -k {port}/tcp 2>/dev/null')
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "brain-service-secret")

app.register_blueprint(internal_bp)

scheduler = None
extraction_worker_thread = None
extraction_worker_running = False
extraction_worker_stats = {
    "last_run": None,
    "requests_processed": 0,
    "last_error": None,
    "is_running": False
}


def extract_text_from_file(file_path: str, file_name: str = None) -> str:
    """Extract text from various file types (PDF, DOCX, plain text)."""
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"[TextExtractor] File not found: {file_path}")
        return ""
    
    extension = ""
    if file_name:
        extension = os.path.splitext(file_name)[1].lower().lstrip('.')
    if not extension:
        extension = os.path.splitext(file_path)[1].lower().lstrip('.')
    
    logger.info(f"[TextExtractor] Extracting text from {file_name or file_path} (type: {extension})")
    
    if extension == 'pdf':
        text = ""
        page_count = 0
        
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
            if text.strip():
                logger.info(f"[TextExtractor] PDF parsed with pypdf: {page_count} pages, {len(text)} characters")
                return text
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
                if text.strip():
                    logger.info(f"[TextExtractor] PDF parsed with pdfplumber: {page_count} pages, {len(text)} characters")
                    return text
        except Exception as e:
            logger.warning(f"[TextExtractor] pdfplumber failed: {e}")
        
        if not text.strip():
            logger.info(f"[TextExtractor] PDF has {page_count} pages but no extractable text. Attempting OCR...")
            try:
                from pdf2image import convert_from_path
                import pytesseract
                
                images = convert_from_path(file_path, dpi=200)
                ocr_parts = []
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image)
                    if page_text.strip():
                        ocr_parts.append(page_text.strip())
                    logger.debug(f"[TextExtractor] OCR page {i+1}/{len(images)}: {len(page_text)} chars")
                
                text = "\n\n".join(ocr_parts)
                if text.strip():
                    logger.info(f"[TextExtractor] PDF OCR successful: {len(images)} pages, {len(text)} characters")
                else:
                    logger.warning(f"[TextExtractor] OCR produced no text from {len(images)} pages")
            except ImportError as e:
                logger.warning(f"[TextExtractor] OCR dependencies not available: {e}")
            except Exception as e:
                logger.error(f"[TextExtractor] OCR failed: {e}")
        return text
    
    elif extension in ['doc', 'docx']:
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            logger.info(f"[TextExtractor] DOCX parsed: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"[TextExtractor] DOCX extraction error: {e}")
            return ""
    
    else:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            logger.info(f"[TextExtractor] Plain text read: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"[TextExtractor] Text read error: {e}")
            return ""


def process_extraction_queue():
    """
    Process pending extraction requests from the queue.
    Claims one request at a time, runs extraction, saves results.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("[ExtractionWorker] DATABASE_URL not set")
        return 0
    
    worker_id = f"brain-worker-{os.getpid()}"
    processed = 0
    
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
            
            text_content = extract_text_from_file(file_path, file_name)
            
            if not text_content:
                logger.warning(f"[ExtractionWorker] No text extracted from {file_name}")
                text_content = f"Document: {file_name}\n\nContent could not be extracted."
            
            start_time = datetime.utcnow()
            
            from src.context_foundry.extraction import ExtractionPipeline
            from src.context_foundry.extraction.staging_loader import StagingLoader
            from src.context_foundry.models.schema import tenant_session
            
            pipeline = ExtractionPipeline(model="gpt-4o-mini", temperature=0.0)
            
            extraction_result = pipeline.extract_with_fallback(
                text=text_content,
                document_id=document_id,
                document_title=file_name or "Uploaded Document"
            )
            
            entities_count = 0
            relations_count = 0
            
            with tenant_session(tenant_id) as session:
                try:
                    loader = StagingLoader(
                        session=session,
                        enable_deduplication=True,
                        similarity_threshold=0.8,
                        tenant_id=tenant_id
                    )
                    
                    logger.info(f"[ExtractionWorker] Loading {len(extraction_result.entities)} entities to staging...")
                    
                    staging_result = loader.load_all(
                        entities=extraction_result.entities,
                        relations=extraction_result.relations,
                        commit=True
                    )
                    
                    entities_count = staging_result.entities_created + staging_result.entities_updated
                    relations_count = staging_result.relations_created + staging_result.relations_updated
                    
                    if staging_result.errors:
                        logger.warning(f"[ExtractionWorker] Staging errors: {staging_result.errors}")
                    
                    logger.info(
                        f"[ExtractionWorker] Extraction complete: "
                        f"{entities_count} entities ({staging_result.entities_created} created, {staging_result.entities_updated} updated, {staging_result.entities_skipped} skipped), "
                        f"{relations_count} relationships for tenant {tenant_id}"
                    )
                    
                except Exception as e:
                    logger.error(f"[ExtractionWorker] Staging error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    session.rollback()
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            cur = conn.cursor()
            cur.execute("""
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
                'success' if extraction_result.success else 'failed',
                entities_count,
                relations_count,
                500,
                300,
                800,
                start_time.isoformat() + 'Z',
                end_time.isoformat() + 'Z',
                duration_ms,
                '1.0.0',
                'gpt-4o-mini'
            ))
            
            cur.execute("""
                UPDATE platform.extraction_requests
                SET status = 'completed', completed_at = NOW()
                WHERE id = %s
            """, (request['id'],))
            
            cur.execute("""
                UPDATE platform.documents
                SET status = 'extracted', updated_at = NOW()
                WHERE id = %s
            """, (request['document_id'],))
            
            conn.commit()
            cur.close()
            
            processed = 1
            extraction_worker_stats["requests_processed"] += 1
            
        except Exception as e:
            logger.error(f"[ExtractionWorker] Processing error: {e}")
            extraction_worker_stats["last_error"] = str(e)
            
            cur = conn.cursor()
            cur.execute("""
                UPDATE platform.extraction_requests
                SET status = 'failed'
                WHERE id = %s
            """, (request['id'],))
            conn.commit()
            cur.close()
        
        conn.close()
        
    except Exception as e:
        logger.error(f"[ExtractionWorker] Database error: {e}")
        extraction_worker_stats["last_error"] = str(e)
    
    return processed


def extraction_worker_loop():
    """
    Background thread that polls the extraction queue every 30 seconds.
    """
    global extraction_worker_running
    
    logger.info("[ExtractionWorker] Starting extraction worker (30-second interval)")
    extraction_worker_stats["is_running"] = True
    
    while extraction_worker_running:
        try:
            extraction_worker_stats["last_run"] = datetime.utcnow().isoformat()
            processed = process_extraction_queue()
            
            if processed > 0:
                time.sleep(1)
            else:
                for _ in range(30):
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
    logger.info("[Brain] Extraction worker started (30-second cycles)")


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


def init_scheduler():
    global scheduler
    if scheduler is None:
        from src.context_foundry.agents.scheduler import GardenerScheduler, SchedulerConfig
        from src.context_foundry.agents.gardener import GardenerConfig
        from src.context_foundry.agents.identity_resolver import IdentityResolutionConfig
        
        config = SchedulerConfig(
            cycle_interval_seconds=300,
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
    
    init_scheduler()
    start_extraction_worker()
    logger.info(f"[Brain] Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
