import os
import sys
import logging
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from brain.routes.internal import internal_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "brain-service-secret")

app.register_blueprint(internal_bp)

scheduler = None


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


atexit.register(shutdown_scheduler)


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == '__main__':
    init_scheduler()
    port = int(os.environ.get('BRAIN_PORT', 3000))
    logger.info(f"[Brain] Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
