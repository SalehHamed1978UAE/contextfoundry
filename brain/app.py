import os
import sys
import logging
import atexit
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
            
            text_content = ""
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text_content = f.read()
            else:
                logger.warning(f"[ExtractionWorker] File not found: {file_path}")
                text_content = f"Document: {file_name}\n\nContent not available."
            
            start_time = datetime.utcnow()
            
            from src.context_foundry.extraction import ExtractionPipeline
            from src.context_foundry.extraction.staging_loader import StagingLoader
            from src.context_foundry.models.schema import tenant_session
            
            pipeline = ExtractionPipeline(model="gpt-4o-mini", temperature=0.0)
            
            extraction_result = pipeline.extract_from_text(
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
                    
                    staging_result = loader.load_all(
                        entities=extraction_result.entities,
                        relations=extraction_result.relations,
                        commit=True
                    )
                    
                    entities_count = staging_result.entities_created + staging_result.entities_updated
                    relations_count = staging_result.relations_created + staging_result.relations_updated
                    
                    logger.info(
                        f"[ExtractionWorker] Extraction complete: "
                        f"{entities_count} entities, {relations_count} relationships "
                        f"for tenant {tenant_id}"
                    )
                    
                except Exception as e:
                    logger.error(f"[ExtractionWorker] Staging error: {e}")
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
    init_scheduler()
    start_extraction_worker()
    port = int(os.environ.get('BRAIN_PORT', 3000))
    logger.info(f"[Brain] Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
