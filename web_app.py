import os
import json
import atexit
from flask import Flask, render_template, request, jsonify
from src.context_foundry.core import ContextFoundry
from src.context_foundry.agents.scheduler import (
    GardenerScheduler, SchedulerConfig, start_scheduler, stop_scheduler, get_scheduler
)
from src.context_foundry.agents.gardener import GardenerConfig
from src.context_foundry.agents.identity_resolver import IdentityResolutionConfig

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "context-foundry-secret")

cf = None
scheduler = None

def get_context_foundry():
    global cf
    if cf is None:
        cf = ContextFoundry()
    return cf

def reset_context_foundry():
    """Reset the ContextFoundry instance to recover from errors."""
    global cf
    if cf is not None:
        cf.cleanup()
    cf = None

def init_scheduler():
    """Initialize the Gardener scheduler with 5-minute cycles."""
    global scheduler
    if scheduler is None:
        config = SchedulerConfig(
            cycle_interval_seconds=300,
            run_identity_resolution=True,
            gardener_config=GardenerConfig(
                decay_half_life_days=30.0,
                min_confidence_for_promotion=0.75,
                min_dwell_time_hours=24.0,
                archive_confidence_threshold=0.3,
            ),
            identity_config=IdentityResolutionConfig(
                auto_merge_threshold=0.95,
                review_threshold=0.70,
                never_auto_merge_types=["PERSON"],
            ),
        )
        scheduler = GardenerScheduler(config=config)
        scheduler.start()
        print("[WebApp] Gardener scheduler started (5-minute cycles)")
    return scheduler

def shutdown_scheduler():
    """Shutdown the scheduler on app exit."""
    global scheduler
    if scheduler:
        scheduler.stop()
        scheduler = None

atexit.register(shutdown_scheduler)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/api/query', methods=['POST'])
def query():
    data = request.get_json()
    query_text = data.get('query', '')
    
    if not query_text:
        return jsonify({'error': 'No query provided'}), 400
    
    try:
        foundry = get_context_foundry()
        result = foundry.query(query_text)
        
        response = {
            'success': True,
            'answer': result.get('answer', ''),
            'confidence': result.get('confidence', 0),
            'confidence_level': result.get('confidence_level', 'unknown'),
            'evidence_chain': result.get('evidence_chain', []),
            'uncertainty': result.get('uncertainty', {}),
            'rules_checked': result.get('rules_checked', []),
            'rules_passed': result.get('rules_passed', []),
            'validation': result.get('validation', {}),
            'query_log': {
                'query_id': result.get('query_log', {}).get('query_id', ''),
                'duration_seconds': result.get('query_log', {}).get('duration_seconds', 0)
            }
        }
        return jsonify(response)
    except Exception as e:
        reset_context_foundry()
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/stats')
def stats():
    try:
        foundry = get_context_foundry()
        statistics = foundry.get_statistics()
        return jsonify({'success': True, 'stats': statistics})
    except Exception as e:
        reset_context_foundry()
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/examples')
def examples():
    examples = [
        {
            'query': 'What services are affected if the Payments Database goes down?',
            'category': 'Impact Analysis',
            'icon': 'zap'
        },
        {
            'query': 'Who should I escalate to for a SEV1 on the Auth Service?',
            'category': 'Escalation',
            'icon': 'users'
        },
        {
            'query': 'What team owns the Payment Service?',
            'category': 'Ownership',
            'icon': 'building'
        },
        {
            'query': 'What does the Checkout Service depend on?',
            'category': 'Dependencies',
            'icon': 'git-branch'
        },
        {
            'query': 'What incidents have affected the Auth Service?',
            'category': 'Incident History',
            'icon': 'alert-triangle'
        },
        {
            'query': 'Who are the experts on payment processing?',
            'category': 'Expertise',
            'icon': 'award'
        }
    ]
    return jsonify({'success': True, 'examples': examples})

@app.route('/api/gardener/status')
def gardener_status():
    """Get Gardener scheduler status and stats."""
    global scheduler
    if scheduler is None:
        return jsonify({
            'success': True,
            'running': False,
            'message': 'Scheduler not initialized'
        })
    
    stats = scheduler.get_stats()
    last_result = scheduler.get_last_result()
    
    return jsonify({
        'success': True,
        'running': stats.get('running', False),
        'cycle_count': stats.get('cycle_count', 0),
        'interval_seconds': stats.get('interval_seconds', 300),
        'last_run': stats.get('last_run'),
        'cycles_successful': stats.get('cycles_successful', 0),
        'cycles_failed': stats.get('cycles_failed', 0),
        'total_entities_affected': stats.get('total_entities_affected', 0),
        'total_conflicts_detected': stats.get('total_conflicts_detected', 0),
        'total_merges_performed': stats.get('total_merges_performed', 0),
        'last_cycle': last_result.to_dict() if last_result else None,
    })

@app.route('/api/gardener/run', methods=['POST'])
def gardener_run_now():
    """Trigger an immediate Gardener cycle."""
    global scheduler
    if scheduler is None:
        scheduler = init_scheduler()
    
    try:
        result = scheduler.run_now()
        return jsonify({
            'success': True,
            'cycle_result': result.to_dict(),
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500

@app.route('/api/gardener/history')
def gardener_history():
    """Get recent Gardener cycle history."""
    global scheduler
    if scheduler is None:
        return jsonify({
            'success': True,
            'history': [],
        })
    
    limit = request.args.get('limit', 10, type=int)
    history = scheduler.get_history(limit=limit)
    
    return jsonify({
        'success': True,
        'history': [h.to_dict() for h in history],
    })

@app.route('/api/conflicts')
def get_conflicts():
    """Get conflict logs from database."""
    from src.context_foundry.models.schema import ConflictLog, get_session
    
    try:
        session = get_session()
        limit = request.args.get('limit', 50, type=int)
        unresolved_only = request.args.get('unresolved', 'false').lower() == 'true'
        
        query = session.query(ConflictLog).order_by(ConflictLog.detected_at.desc())
        
        if unresolved_only:
            query = query.filter(ConflictLog.resolution == None)
        
        conflicts = query.limit(limit).all()
        
        return jsonify({
            'success': True,
            'conflicts': [c.to_dict() for c in conflicts],
            'count': len(conflicts),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/conflicts/<conflict_id>/resolve', methods=['POST'])
def resolve_conflict(conflict_id):
    """Resolve a conflict manually."""
    from src.context_foundry.models.schema import ConflictLog, get_session
    from datetime import datetime
    
    try:
        session = get_session()
        data = request.get_json()
        
        conflict = session.query(ConflictLog).filter(
            ConflictLog.id == conflict_id
        ).first()
        
        if not conflict:
            return jsonify({'success': False, 'error': 'Conflict not found'}), 404
        
        conflict.resolution = data.get('resolution', 'manual_review')
        conflict.resolution_notes = data.get('notes', '')
        conflict.resolved_at = datetime.utcnow()
        conflict.resolved_by = data.get('resolved_by', 'human_reviewer')
        
        session.commit()
        
        return jsonify({
            'success': True,
            'conflict': conflict.to_dict(),
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/duplicates')
def get_duplicate_candidates():
    """Get duplicate candidates for review."""
    from src.context_foundry.models.schema import DuplicateCandidate, get_session
    
    try:
        session = get_session()
        limit = request.args.get('limit', 50, type=int)
        unreviewed_only = request.args.get('unreviewed', 'true').lower() == 'true'
        
        query = session.query(DuplicateCandidate).order_by(
            DuplicateCandidate.similarity_score.desc()
        )
        
        if unreviewed_only:
            query = query.filter(DuplicateCandidate.reviewed == False)
        
        candidates = query.limit(limit).all()
        
        return jsonify({
            'success': True,
            'duplicates': [c.to_dict() for c in candidates],
            'count': len(candidates),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/duplicates/<candidate_id>/review', methods=['POST'])
def review_duplicate(candidate_id):
    """Review a duplicate candidate."""
    from src.context_foundry.models.schema import DuplicateCandidate, get_session
    from datetime import datetime
    
    try:
        session = get_session()
        data = request.get_json()
        
        candidate = session.query(DuplicateCandidate).filter(
            DuplicateCandidate.id == candidate_id
        ).first()
        
        if not candidate:
            return jsonify({'success': False, 'error': 'Candidate not found'}), 404
        
        candidate.reviewed = True
        candidate.reviewed_at = datetime.utcnow()
        candidate.reviewed_by = data.get('reviewed_by', 'human_reviewer')
        
        action = data.get('action', 'dismiss')
        if action == 'merge':
            pass
        
        session.commit()
        
        return jsonify({
            'success': True,
            'candidate': candidate.to_dict(),
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/merge-audits')
def get_merge_audits():
    """Get merge audit trail."""
    from src.context_foundry.models.schema import MergeAudit, get_session
    
    try:
        session = get_session()
        limit = request.args.get('limit', 50, type=int)
        
        audits = session.query(MergeAudit).order_by(
            MergeAudit.merged_at.desc()
        ).limit(limit).all()
        
        return jsonify({
            'success': True,
            'audits': [a.to_dict() for a in audits],
            'count': len(audits),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

if __name__ == '__main__':
    init_scheduler()
    app.run(host='0.0.0.0', port=5000, debug=True)
