"""
Test Runner API Blueprint

Provides REST API endpoints for the Test Runner Dashboard:
- Question Sets management (upload, list, get, delete)
- Test Control (start, status, stop)
- History & Results
- Corpus folders listing
"""

import json
import os
import subprocess
import signal
from datetime import datetime
from pathlib import Path
from uuid import UUID

from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

test_runner_api = Blueprint('test_runner_api', __name__, url_prefix='/api/test-runner')

STATUS_FILE_PATH = Path('data/test-runner/status.json')
CORPUS_FOLDERS_PATH = Path('test documents')


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def read_status_file():
    """Read the current test status from status file."""
    if not STATUS_FILE_PATH.exists():
        return None
    try:
        with open(STATUS_FILE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_status_file(status: dict):
    """Write status to status file."""
    STATUS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)


def clear_status_file():
    """Clear the status file."""
    if STATUS_FILE_PATH.exists():
        STATUS_FILE_PATH.unlink()


@test_runner_api.route('/question-sets/upload', methods=['POST'])
def upload_question_set():
    """Upload a question set from JSON or JSONL file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith(('.json', '.jsonl')):
        return jsonify({'error': 'File must be .json or .jsonl'}), 400
    
    name = request.form.get('name') or Path(file.filename).stem
    
    try:
        content = file.read().decode('utf-8')
        
        if file.filename.endswith('.jsonl'):
            questions = []
            for line in content.strip().split('\n'):
                if line.strip():
                    questions.append(json.loads(line))
        else:
            data = json.loads(content)
            if isinstance(data, list):
                questions = data
            elif 'questions' in data:
                questions = data['questions']
            else:
                questions = [data]
        
        question_count = len(questions)
        
        session = get_db_session()
        try:
            result = session.execute(text("""
                INSERT INTO question_sets (name, question_count, questions, uploaded_by)
                VALUES (:name, :count, :questions, :uploaded_by)
                RETURNING id
            """), {
                'name': name,
                'count': question_count,
                'questions': json.dumps(questions),
                'uploaded_by': 'api'
            })
            question_set_id = result.fetchone()[0]
            session.commit()
            
            return jsonify({
                'id': str(question_set_id),
                'name': name,
                'question_count': question_count,
                'message': f'Uploaded {question_count} questions successfully'
            }), 201
        finally:
            session.close()
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@test_runner_api.route('/question-sets', methods=['GET'])
def list_question_sets():
    """List all question sets."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT id, name, question_count, uploaded_at, uploaded_by
            FROM question_sets
            ORDER BY uploaded_at DESC
        """))
        
        question_sets = []
        for row in result:
            question_sets.append({
                'id': str(row[0]),
                'name': row[1],
                'question_count': row[2],
                'uploaded_at': row[3].isoformat() if row[3] else None,
                'uploaded_by': row[4]
            })
        
        return jsonify({'question_sets': question_sets})
    finally:
        session.close()


@test_runner_api.route('/question-sets/<uuid:question_set_id>', methods=['GET'])
def get_question_set(question_set_id: UUID):
    """Get a question set with its questions."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT id, name, question_count, questions, uploaded_at, uploaded_by
            FROM question_sets
            WHERE id = :id
        """), {'id': str(question_set_id)})
        
        row = result.fetchone()
        if not row:
            return jsonify({'error': 'Question set not found'}), 404
        
        return jsonify({
            'id': str(row[0]),
            'name': row[1],
            'question_count': row[2],
            'questions': row[3],
            'uploaded_at': row[4].isoformat() if row[4] else None,
            'uploaded_by': row[5]
        })
    finally:
        session.close()


@test_runner_api.route('/question-sets/<uuid:question_set_id>', methods=['DELETE'])
def delete_question_set(question_set_id: UUID):
    """Delete a question set."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            DELETE FROM question_sets WHERE id = :id RETURNING id
        """), {'id': str(question_set_id)})
        
        if not result.fetchone():
            return jsonify({'error': 'Question set not found'}), 404
        
        session.commit()
        return jsonify({'message': 'Question set deleted successfully'})
    finally:
        session.close()


@test_runner_api.route('/start', methods=['POST'])
def start_test():
    """Start a new test run."""
    current_status = read_status_file()
    if current_status and current_status.get('status') == 'running':
        return jsonify({
            'error': 'A test is already running',
            'current_test': current_status
        }), 409
    
    data = request.get_json() or {}
    corpus = data.get('corpus')
    question_set_id = data.get('question_set_id')
    fresh = data.get('fresh', False)
    
    if not corpus:
        return jsonify({'error': 'corpus is required'}), 400
    
    cmd = ['python', '-m', 'src.test_runner.runner', '--corpus', corpus]
    
    if question_set_id:
        cmd.extend(['--question-set-id', question_set_id])
    
    if fresh:
        cmd.append('--fresh')
    
    initial_status = {
        'status': 'starting',
        'corpus': corpus,
        'question_set_id': question_set_id,
        'fresh': fresh,
        'started_at': datetime.now().isoformat(),
        'pid': None,
        'stage': 'init',
        'progress': {
            'total': 0,
            'completed': 0,
            'passed': 0,
            'failed': 0
        }
    }
    write_status_file(initial_status)
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        initial_status['status'] = 'running'
        initial_status['pid'] = process.pid
        write_status_file(initial_status)
        
        return jsonify({
            'message': 'Test started',
            'pid': process.pid,
            'corpus': corpus,
            'command': ' '.join(cmd)
        }), 202
    except Exception as e:
        initial_status['status'] = 'failed'
        initial_status['error'] = str(e)
        write_status_file(initial_status)
        return jsonify({'error': f'Failed to start test: {str(e)}'}), 500


@test_runner_api.route('/status', methods=['GET'])
def get_test_status():
    """Get current test status."""
    status = read_status_file()
    if not status:
        return jsonify({
            'status': 'idle',
            'message': 'No test is currently running'
        })
    
    if status.get('pid'):
        try:
            os.kill(status['pid'], 0)
        except OSError:
            if status.get('status') == 'running':
                status['status'] = 'finished'
                write_status_file(status)
    
    return jsonify(status)


@test_runner_api.route('/stop', methods=['POST'])
def stop_test():
    """Stop the currently running test."""
    status = read_status_file()
    if not status or status.get('status') != 'running':
        return jsonify({'error': 'No test is currently running'}), 400
    
    pid = status.get('pid')
    if not pid:
        return jsonify({'error': 'No process ID found'}), 400
    
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        
        status['status'] = 'stopped'
        status['stopped_at'] = datetime.now().isoformat()
        write_status_file(status)
        
        return jsonify({
            'message': 'Test stopped',
            'pid': pid
        })
    except ProcessLookupError:
        status['status'] = 'finished'
        write_status_file(status)
        return jsonify({'message': 'Process already finished'})
    except Exception as e:
        return jsonify({'error': f'Failed to stop test: {str(e)}'}), 500


@test_runner_api.route('/history', methods=['GET'])
def get_test_history():
    """Get test run history."""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT 
                id, vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, started_at, completed_at,
                questions_total, questions_answered, questions_passed, questions_failed,
                error_message
            FROM test_runs
            ORDER BY started_at DESC
            LIMIT :limit OFFSET :offset
        """), {'limit': limit, 'offset': offset})
        
        runs = []
        for row in result:
            runs.append({
                'id': str(row[0]),
                'vault_id': str(row[1]) if row[1] else None,
                'vault_name': row[2],
                'question_set_id': str(row[3]) if row[3] else None,
                'question_set_name': row[4],
                'mode': row[5],
                'corpus_folder': row[6],
                'status': row[7],
                'stage': row[8],
                'started_at': row[9].isoformat() if row[9] else None,
                'completed_at': row[10].isoformat() if row[10] else None,
                'questions_total': row[11],
                'questions_answered': row[12],
                'questions_passed': row[13],
                'questions_failed': row[14],
                'error_message': row[15]
            })
        
        count_result = session.execute(text("SELECT COUNT(*) FROM test_runs"))
        total = count_result.fetchone()[0]
        
        return jsonify({
            'runs': runs,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        session.close()


@test_runner_api.route('/results/<uuid:test_id>', methods=['GET'])
def get_test_results(test_id: UUID):
    """Get detailed results for a specific test run."""
    session = get_db_session()
    try:
        run_result = session.execute(text("""
            SELECT 
                id, vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, started_at, completed_at,
                questions_total, questions_answered, questions_passed, questions_failed,
                checkpoint, error_message
            FROM test_runs
            WHERE id = :id
        """), {'id': str(test_id)})
        
        run_row = run_result.fetchone()
        if not run_row:
            return jsonify({'error': 'Test run not found'}), 404
        
        results_result = session.execute(text("""
            SELECT 
                id, question_id, question_text, expected_answer, actual_answer,
                category, passed, failure_reason, duration_ms, answered_at
            FROM test_results
            WHERE test_run_id = :test_id
            ORDER BY answered_at
        """), {'test_id': str(test_id)})
        
        results = []
        for row in results_result:
            results.append({
                'id': str(row[0]),
                'question_id': row[1],
                'question_text': row[2],
                'expected_answer': row[3],
                'actual_answer': row[4],
                'category': row[5],
                'passed': row[6],
                'failure_reason': row[7],
                'duration_ms': row[8],
                'answered_at': row[9].isoformat() if row[9] else None
            })
        
        return jsonify({
            'run': {
                'id': str(run_row[0]),
                'vault_id': str(run_row[1]) if run_row[1] else None,
                'vault_name': run_row[2],
                'question_set_id': str(run_row[3]) if run_row[3] else None,
                'question_set_name': run_row[4],
                'mode': run_row[5],
                'corpus_folder': run_row[6],
                'status': run_row[7],
                'stage': run_row[8],
                'started_at': run_row[9].isoformat() if run_row[9] else None,
                'completed_at': run_row[10].isoformat() if run_row[10] else None,
                'questions_total': run_row[11],
                'questions_answered': run_row[12],
                'questions_passed': run_row[13],
                'questions_failed': run_row[14],
                'checkpoint': run_row[15],
                'error_message': run_row[16]
            },
            'results': results
        })
    finally:
        session.close()


@test_runner_api.route('/corpus-folders', methods=['GET'])
def list_corpus_folders():
    """List available corpus folders from test documents directory."""
    folders = []
    
    if CORPUS_FOLDERS_PATH.exists():
        for item in sorted(CORPUS_FOLDERS_PATH.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                doc_count = 0
                doc_folder = item / 'documents'
                if doc_folder.exists():
                    doc_count = sum(1 for f in doc_folder.rglob('*') if f.is_file())
                
                folders.append({
                    'name': item.name,
                    'path': str(item),
                    'document_count': doc_count
                })
    
    return jsonify({'corpus_folders': folders})
