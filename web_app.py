import os
import json
from flask import Flask, render_template, request, jsonify
from src.context_foundry.core import ContextFoundry

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "context-foundry-secret")

cf = None

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
