"""
Status file management for the test runner.
Shared module to avoid circular imports.
"""

import json
from datetime import datetime
from pathlib import Path

STATUS_FILE_PATH = Path('data/test-runner/status.json')


def update_status(stage: str = '', stage_status: str = '', qa_progress: dict = None, current_question: dict = None, overall_status: str = '', **kwargs):
    """Update the status file with current progress.
    
    Args:
        stage: The stage name (delete, create, upload, extract, qa)
        stage_status: Status for this stage (pending, running, complete, skipped)
        qa_progress: Q&A progress dict with total, answered, passed, failed, accuracy_percent
        current_question: Current question dict with id, text
        overall_status: Top-level test status (starting, running, finished, failed, stopped)
        **kwargs: Additional stage-specific data (vault_id, file_count, entities, etc.)
    """
    STATUS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    status = {}
    if STATUS_FILE_PATH.exists():
        try:
            with open(STATUS_FILE_PATH) as f:
                status = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    if 'stages' not in status:
        status['stages'] = {
            'delete': {'status': 'pending'},
            'create': {'status': 'pending'},
            'upload': {'status': 'pending'},
            'extract': {'status': 'pending'},
            'qa': {'status': 'pending'}
        }
    
    if stage in status['stages'] and stage_status:
        status['stages'][stage]['status'] = stage_status
        for key, value in kwargs.items():
            status['stages'][stage][key] = value
    
    # Set overall test status if provided
    if overall_status:
        status['status'] = overall_status
    
    if qa_progress is not None:
        status['qa_progress'] = qa_progress
    
    if current_question is not None:
        status['current_question'] = current_question
    
    status['updated_at'] = datetime.now().isoformat()
    
    with open(STATUS_FILE_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)
