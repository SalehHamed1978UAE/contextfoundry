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
        try:
            cf.reset_session()
        except Exception:
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

evaluation_result = None

@app.route('/api/evaluation/query-set')
def get_query_set():
    """Get the 100-query evaluation set."""
    from src.context_foundry.evaluation.query_set import QuerySet
    
    try:
        qs = QuerySet()
        category = request.args.get('category')
        difficulty = request.args.get('difficulty')
        
        queries = qs.get_all_queries()
        
        if category:
            from src.context_foundry.evaluation.query_set import QueryCategory
            cat_enum = QueryCategory(category)
            queries = [q for q in queries if q.category == cat_enum]
        
        if difficulty:
            from src.context_foundry.evaluation.query_set import DifficultyLevel
            diff_enum = DifficultyLevel(difficulty)
            queries = [q for q in queries if q.difficulty == diff_enum]
        
        return jsonify({
            'success': True,
            'queries': [q.to_dict() for q in queries],
            'count': len(queries),
            'statistics': qs.get_statistics(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/run', methods=['POST'])
def run_evaluation():
    """Run blind evaluation on selected queries."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    from src.context_foundry.evaluation.query_set import QueryCategory
    
    global evaluation_result
    
    try:
        data = request.get_json() or {}
        query_ids = data.get('query_ids')
        categories = data.get('categories')
        sample_size = data.get('sample_size')
        reveal_source = data.get('reveal_source', False)
        
        if categories:
            categories = [QueryCategory(c) for c in categories]
        
        evaluator = BlindEvaluator()
        evaluation_result = evaluator.run_evaluation(
            query_ids=query_ids,
            categories=categories,
            sample_size=sample_size,
        )
        
        return jsonify({
            'success': True,
            'evaluation_id': evaluation_result.evaluation_id,
            'total_queries': evaluation_result.total_queries,
            'completed_queries': evaluation_result.completed_queries,
            'pairs': [p.to_dict(reveal_source=reveal_source) for p in evaluation_result.pairs],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/compare', methods=['POST'])
def compare_single_query():
    """Run a single query through both systems for comparison."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    
    try:
        data = request.get_json()
        query_id = data.get('query_id')
        
        if not query_id:
            return jsonify({'success': False, 'error': 'query_id required'}), 400
        
        evaluator = BlindEvaluator()
        pair = evaluator.run_single_query(query_id)
        
        if not pair:
            return jsonify({'success': False, 'error': 'Query not found'}), 404
        
        blind_a, blind_b = pair.get_blind_responses()
        
        return jsonify({
            'success': True,
            'pair_id': pair.pair_id,
            'query': pair.query.to_dict(),
            'response_a': blind_a,
            'response_b': blind_b,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/graphrag', methods=['POST'])
def query_graphrag():
    """Run a query through GraphRAG baseline only."""
    from src.context_foundry.evaluation.graphrag_baseline import GraphRAGBaseline
    
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        
        if not query_text:
            return jsonify({'success': False, 'error': 'query required'}), 400
        
        graphrag = GraphRAGBaseline()
        result = graphrag.query(query_text)
        
        return jsonify({
            'success': True,
            'answer': result.answer,
            'context': result.context.to_dict(),
            'latency_ms': result.latency_ms,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/preference', methods=['POST'])
def record_preference():
    """Record human preference for a blind comparison."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    
    global evaluation_result
    
    try:
        data = request.get_json()
        pair_id = data.get('pair_id')
        preference = data.get('preference')
        notes = data.get('notes', '')
        reviewer = data.get('reviewer', 'anonymous')
        
        if not pair_id or not preference:
            return jsonify({'success': False, 'error': 'pair_id and preference required'}), 400
        
        if preference not in ['A', 'B', 'tie']:
            return jsonify({'success': False, 'error': 'preference must be A, B, or tie'}), 400
        
        if evaluation_result is None:
            return jsonify({'success': False, 'error': 'No evaluation running'}), 400
        
        evaluator = BlindEvaluator()
        success = evaluator.record_preference(
            pair_id=pair_id,
            preference=preference,
            notes=notes,
            reviewer=reviewer,
            result=evaluation_result,
        )
        
        if success:
            metrics = evaluator.calculate_metrics(evaluation_result)
            return jsonify({
                'success': True,
                'metrics': metrics.to_dict(),
            })
        else:
            return jsonify({'success': False, 'error': 'Pair not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/metrics')
def get_evaluation_metrics():
    """Get current evaluation metrics."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    
    global evaluation_result
    
    try:
        if evaluation_result is None:
            return jsonify({
                'success': True,
                'message': 'No evaluation running',
                'metrics': None,
            })
        
        evaluator = BlindEvaluator()
        metrics = evaluator.calculate_metrics(evaluation_result)
        
        return jsonify({
            'success': True,
            'evaluation_id': evaluation_result.evaluation_id,
            'total_queries': evaluation_result.total_queries,
            'completed_queries': evaluation_result.completed_queries,
            'reviewed': sum(1 for p in evaluation_result.pairs if p.human_preference),
            'metrics': metrics.to_dict(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/reveal', methods=['POST'])
def reveal_evaluation_source():
    """Reveal which system produced each response (only after review is complete)."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    
    global evaluation_result
    
    try:
        if evaluation_result is None:
            return jsonify({'success': False, 'error': 'No evaluation running'}), 400
        
        reviewed_count = sum(1 for p in evaluation_result.pairs if p.human_preference)
        if reviewed_count == 0:
            return jsonify({
                'success': False, 
                'error': 'No pairs have been reviewed yet. Complete review before revealing sources.'
            }), 400
        
        evaluator = BlindEvaluator()
        metrics = evaluator.calculate_metrics(evaluation_result)
        
        return jsonify({
            'success': True,
            'evaluation_id': evaluation_result.evaluation_id,
            'total_queries': evaluation_result.total_queries,
            'reviewed': reviewed_count,
            'pairs': [p.to_dict(reveal_source=True) for p in evaluation_result.pairs if p.human_preference],
            'metrics': metrics.to_dict(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    init_scheduler()
    app.run(host='0.0.0.0', port=5000, debug=True)
