import os
import sys
import json
import atexit
import logging
import signal
import socket
import time
from datetime import timedelta
from uuid import UUID
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g

logger = logging.getLogger(__name__)


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
            print(f"[Platform] Port {port} still in use, attempt {attempt + 1}/{max_attempts}")
        except Exception:
            pass
    return False


def shutdown_handler(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    sig_name = signal.Signals(signum).name
    print(f"[Platform] Received {sig_name}, shutting down gracefully...")
    stop_scheduler()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
from src.context_foundry.core import ContextFoundry
from src.context_foundry.agents.scheduler import (
    GardenerScheduler, SchedulerConfig, start_scheduler, stop_scheduler, get_scheduler
)
from src.context_foundry.agents.gardener import GardenerConfig
from src.context_foundry.agents.identity_resolver import IdentityResolutionConfig
from src.context_foundry.agents.tool_agent import ToolAgent
from src.context_foundry.agents.conversation_store import ConversationStore

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    raise RuntimeError("SESSION_SECRET environment variable required")
app.permanent_session_lifetime = timedelta(days=7)

if os.environ.get("GOOGLE_OAUTH_CLIENT_ID"):
    from google_auth import google_auth
    app.register_blueprint(google_auth)

from src.context_foundry.api.external import external_api
app.register_blueprint(external_api)

from src.context_foundry.ontology_routes import ontology_bp
app.register_blueprint(ontology_bp)

from src.context_foundry.api.extraction_api import extraction_api
app.register_blueprint(extraction_api)

def validate_api_key():
    """
    Validate API key from Authorization header.
    Returns (tenant_id, key_data) on success, (None, error_response) on failure.
    """
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header:
        return None, None
    
    if not auth_header.startswith('Bearer '):
        return None, (jsonify({'error': 'Invalid authorization header format. Use: Bearer <api_key>'}), 401)
    
    api_key = auth_header[7:]
    
    if not api_key.startswith('cf_live_') and not api_key.startswith('cf_test_'):
        return None, (jsonify({'error': 'Invalid API key format'}), 401)
    
    try:
        from platform_foundation.src.auth_service import AuthService
        auth_service = AuthService(os.environ.get('DATABASE_URL'))
        key_data = auth_service.validate_api_key(api_key)
        
        if not key_data:
            return None, (jsonify({'error': 'Invalid or expired API key'}), 401)
        
        return key_data.get('tenant_id'), key_data
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        return None, (jsonify({'error': 'Authentication service error'}), 500)

@app.after_request
def add_headers(response):
    """Add dark theme headers and cache control."""
    # CRITICAL: Declare dark theme at HTTP level - sent BEFORE any HTML renders
    # This prevents the browser's default white background
    response.headers['Color-Scheme'] = 'dark'
    response.headers['Prefer-Color-Scheme'] = 'dark'
    
    # Cache control for static files
    if 'static' in request.path:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

cf = None
scheduler = None
evaluation_result = None
comparison_pairs = {}  # Store individual comparison pairs by pair_id
preference_metrics = {'cf_wins': 0, 'graphrag_wins': 0, 'ties': 0, 'reviewed': set()}


def _compute_metrics_from_db(session):
    """Compute evaluation metrics from database (works across workers)."""
    from src.context_foundry.models.schema import EvaluationVote
    
    votes = session.query(EvaluationVote).filter(
        EvaluationVote.human_preference.isnot(None)
    ).all()
    
    cf_wins = 0
    graphrag_wins = 0
    ties = 0
    
    for vote in votes:
        if vote.human_preference == 'tie':
            ties += 1
        elif vote.human_preference == 'A':
            if vote.a_is_context_foundry:
                cf_wins += 1
            else:
                graphrag_wins += 1
        elif vote.human_preference == 'B':
            if not vote.a_is_context_foundry:
                cf_wins += 1
            else:
                graphrag_wins += 1
    
    return {
        'cf_wins': cf_wins,
        'graphrag_wins': graphrag_wins,
        'ties': ties,
        'reviewed': len(votes),
    }


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
        print("[WebApp] Gardener scheduler started (5-minute cycles)")
    return scheduler

def shutdown_scheduler():
    """Shutdown the scheduler on app exit."""
    global scheduler
    if scheduler:
        scheduler.stop()
        scheduler = None

atexit.register(shutdown_scheduler)

auth_service = None

def get_auth_service():
    """Get or create the AuthService instance."""
    global auth_service
    if auth_service is None:
        from platform_foundation.src.auth_service import AuthService
        auth_service = AuthService()
    return auth_service

@app.before_request
def set_tenant_context():
    """
    Set tenant context for RLS on authenticated requests.
    Stores tenant_id/role in Flask g for use by request handlers.
    Handlers that need tenant isolation should use g.tenant_id directly.
    """
    from flask import g
    g.tenant_id = None
    g.user_id = None
    g.user_role = None
    
    # First check session-based auth (Google OAuth)
    if session.get('user_id') and session.get('tenant_id'):
        g.tenant_id = session.get('tenant_id')
        g.user_id = session.get('user_id')
        g.user_role = session.get('role', 'user')
        return
    
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        auth = get_auth_service()
        payload = auth.validate_token(token)
        if payload:
            g.tenant_id = payload.get('tenant_id')
            g.user_id = payload.get('sub')
            g.user_role = payload.get('role')
    
    elif auth_header.startswith('ApiKey ') or auth_header.startswith('cf_'):
        api_key = auth_header.replace('ApiKey ', '') if auth_header.startswith('ApiKey ') else auth_header
        auth = get_auth_service()
        key_data = auth.validate_api_key(api_key)
        if key_data:
            g.tenant_id = key_data.get('tenant_id')
            g.user_role = 'api_key'


def set_tenant_on_session(session, tenant_id: str, role: str = None):
    """
    Set tenant context on a specific database session for RLS.
    Call this at the start of any handler that needs tenant isolation.
    
    Args:
        session: SQLAlchemy session to configure
        tenant_id: UUID string of tenant
        role: Optional user role
    """
    from sqlalchemy import text
    if tenant_id:
        session.execute(text("SELECT platform.set_current_tenant(:tid)"), {'tid': tenant_id})
        if role:
            session.execute(text("SELECT platform.set_current_user_role(:role)"), {'role': role})

@app.route('/auth/magic-link', methods=['POST'])
def request_magic_link():
    """Request a magic link for passwordless authentication."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    auth = get_auth_service()
    result = auth.create_magic_link(
        email=email,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    if result.success:
        return jsonify({
            'success': True,
            'message': 'Magic link sent to your email',
            'expires_at': result.expires_at.isoformat() if result.expires_at else None,
            '_dev_link': result.link
        })
    else:
        return jsonify({'error': result.error}), 400

@app.route('/auth/verify')
def verify_magic_link():
    """Verify a magic link token and authenticate user."""
    token = request.args.get('token')
    
    if not token:
        return jsonify({'error': 'Token required'}), 400
    
    auth = get_auth_service()
    result = auth.verify_magic_link(token)
    
    if result.success:
        response_data = {
            'success': True,
            'user': {
                'id': result.user.id,
                'email': result.user.email,
                'name': result.user.name,
                'role': result.user.role,
                'tenant_id': result.user.tenant_id
            },
            'access_token': result.access_token,
            'refresh_token': result.refresh_token,
            'expires_at': result.expires_at.isoformat() if result.expires_at else None
        }
        return jsonify(response_data)
    else:
        return jsonify({'error': result.error}), 401

@app.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh an access token using a refresh token."""
    data = request.get_json() or {}
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400
    
    auth = get_auth_service()
    result = auth.refresh_access_token(refresh_token)
    
    if result.success:
        return jsonify({
            'success': True,
            'access_token': result.access_token,
            'expires_at': result.expires_at.isoformat() if result.expires_at else None
        })
    else:
        return jsonify({'error': result.error}), 401

@app.route('/auth/me')
def get_current_user():
    """Get the current authenticated user."""
    from flask import g
    
    if not g.get('user_id'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    auth = get_auth_service()
    user = auth._get_user_by_id(g.user_id)
    
    if user:
        return jsonify({
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'tenant_id': user.tenant_id
            }
        })
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/api/dev/auth', methods=['POST'])
def dev_auth():
    """Development-only auth endpoint for stress testing.
    Creates or gets a test user/tenant for automated testing.
    """
    import os
    import uuid
    if os.environ.get('REPLIT_DEPLOYMENT') == '1':
        return jsonify({'error': 'Not available in production'}), 403
    
    data = request.get_json() or {}
    email = data.get('email', 'stress-test@context-foundry.local')
    override_tenant_id = data.get('tenant_id')  # Allow override for testing specific vaults
    
    auth = get_auth_service()
    result = auth.create_magic_link(
        email=email,
        ip_address=request.remote_addr,
        user_agent='StressTest/1.0'
    )
    
    if not result.success:
        return jsonify({'error': result.error}), 400
    
    import re
    token_match = re.search(r'token=([^&]+)', result.link)
    if not token_match:
        return jsonify({'error': 'Failed to extract token'}), 500
    
    verify_result = auth.verify_magic_link(token_match.group(1))
    if not verify_result.success:
        return jsonify({'error': verify_result.error}), 400
    
    user_id = verify_result.user.id
    tenant_id = verify_result.user.tenant_id
    
    # Allow tenant_id override from request (for testing specific vaults)
    if override_tenant_id:
        tenant_id = override_tenant_id
    elif not tenant_id:
        # Only create tenant if no override and user has no tenant
        from src.context_foundry.models.schema import get_session
        db_session = get_session()
        try:
            new_tenant_id = str(uuid.uuid4())
            tenant_name = f"Stress Test Tenant ({email.split('@')[0]})"
            tenant_slug = f"stress-test-{email.split('@')[0].replace('.', '-')}-{new_tenant_id[:8]}"
            
            from sqlalchemy import text
            db_session.execute(text("""
                INSERT INTO platform.tenants (id, name, slug, type, status, settings, created_at)
                VALUES (:id, :name, :slug, 'demo', 'active', '{}', NOW())
                ON CONFLICT (id) DO NOTHING
            """), {'id': new_tenant_id, 'name': tenant_name, 'slug': tenant_slug})
            
            db_session.commit()
            tenant_id = new_tenant_id
        finally:
            db_session.close()
    
    session['user_id'] = user_id
    session['user_name'] = verify_result.user.name or email.split('@')[0]
    session['tenant_id'] = tenant_id
    session['role'] = verify_result.user.role or 'user'
    session.permanent = True
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'tenant_id': tenant_id,
        'access_token': verify_result.access_token
    })

@app.route('/api/keys', methods=['GET', 'POST'])
def api_keys():
    """List or create API keys for the current tenant."""
    from flask import g
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Tenant context required'}), 401
    
    auth = get_auth_service()
    
    if request.method == 'GET':
        keys = auth.list_api_keys(g.tenant_id)
        return jsonify({'keys': keys})
    
    elif request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name', 'API Key')
        scopes = data.get('scopes', ['read'])
        rate_limit = data.get('rate_limit', 60)
        expires_in_days = data.get('expires_in_days')
        
        result = auth.create_api_key(
            tenant_id=g.tenant_id,
            name=name,
            scopes=scopes,
            created_by=g.get('user_id'),
            rate_limit=rate_limit,
            expires_in_days=expires_in_days
        )
        
        if result.success:
            return jsonify({
                'success': True,
                'key_id': result.key_id,
                'api_key': result.api_key,
                'key_prefix': result.key_prefix,
                'message': 'Save this key now - it cannot be retrieved later'
            }), 201
        else:
            return jsonify({'error': result.error}), 400

@app.route('/api/keys/<key_id>', methods=['DELETE'])
def revoke_api_key(key_id):
    """Revoke an API key."""
    from flask import g
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Tenant context required'}), 401
    
    auth = get_auth_service()
    success = auth.revoke_api_key(key_id, g.tenant_id)
    
    if success:
        return jsonify({'success': True, 'message': 'API key revoked'})
    else:
        return jsonify({'error': 'API key not found or already revoked'}), 404


doc_service = None

def get_document_service():
    """Lazy-load DocumentService singleton."""
    global doc_service
    if doc_service is None:
        from platform_foundation.src.document_service import DocumentService
        doc_service = DocumentService()
    return doc_service


@app.route('/documents', methods=['POST'])
def upload_document():
    """Upload a new document for extraction."""
    from flask import g
    from uuid import UUID
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        tenant_id = UUID(g.tenant_id)
        user_id = UUID(g.user_id) if g.get('user_id') else None
        
        folder_id = request.form.get('folder_id')
        auto_extract = request.form.get('auto_extract', 'true').lower() == 'true'
        priority = request.form.get('priority', 'normal')
        
        doc_svc = get_document_service()
        document = doc_svc.upload_document(
            tenant_id=tenant_id,
            filename=file.filename,
            mime_type=file.content_type or 'application/octet-stream',
            file_content=file.read(),
            folder_id=UUID(folder_id) if folder_id else None,
            created_by=user_id,
            auto_extract=auto_extract,
            priority=priority
        )
        
        response = {
            'id': str(document['id']),
            'name': document['name'],
            'status': document['status'],
            'mime_type': document['mime_type'],
            'size_bytes': document['size_bytes'],
            'created_at': document['created_at'].isoformat() if document.get('created_at') else None
        }
        
        if 'extraction_request_id' in document:
            response['extraction_request_id'] = document['extraction_request_id']
        
        return jsonify(response), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({'error': 'Upload failed'}), 500


@app.route('/documents', methods=['GET'])
def list_documents():
    """List documents for the current tenant."""
    from flask import g
    from uuid import UUID
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = UUID(g.tenant_id)
        folder_id = request.args.get('folder_id')
        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        doc_svc = get_document_service()
        documents = doc_svc.list_documents(
            tenant_id=tenant_id,
            folder_id=UUID(folder_id) if folder_id else None,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'documents': [
                {
                    'id': str(d['id']),
                    'name': d['name'],
                    'status': d['status'],
                    'mime_type': d['mime_type'],
                    'size_bytes': d['size_bytes'],
                    'created_at': d['created_at'].isoformat() if d.get('created_at') else None,
                    'updated_at': d['updated_at'].isoformat() if d.get('updated_at') else None
                }
                for d in documents
            ],
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        return jsonify({'error': 'Failed to list documents'}), 500


@app.route('/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get document details and extraction status."""
    from flask import g
    from uuid import UUID
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = UUID(g.tenant_id)
        doc_id = UUID(document_id)
        
        doc_svc = get_document_service()
        document = doc_svc.get_document(doc_id, tenant_id)
        
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        response = {
            'id': str(document['id']),
            'name': document['name'],
            'original_filename': document['original_filename'],
            'status': document['status'],
            'mime_type': document['mime_type'],
            'size_bytes': document['size_bytes'],
            'current_version': document['current_version'],
            'created_at': document['created_at'].isoformat() if document.get('created_at') else None,
            'updated_at': document['updated_at'].isoformat() if document.get('updated_at') else None
        }
        
        return jsonify(response)
        
    except ValueError:
        return jsonify({'error': 'Invalid document ID'}), 400
    except Exception as e:
        logger.error(f"Get document failed: {e}")
        return jsonify({'error': 'Failed to get document'}), 500


@app.route('/documents/<document_id>/extraction', methods=['POST'])
def requeue_extraction(document_id):
    """Re-queue a document for extraction."""
    from flask import g
    from uuid import UUID
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = UUID(g.tenant_id)
        doc_id = UUID(document_id)
        
        data = request.get_json() or {}
        priority = data.get('priority', 'normal')
        ontology_hints = data.get('ontology_hints')
        extraction_mode = data.get('extraction_mode', 'full')
        
        doc_svc = get_document_service()
        extraction_request = doc_svc.queue_for_extraction(
            document_id=doc_id,
            tenant_id=tenant_id,
            priority=priority,
            ontology_hints=ontology_hints,
            extraction_mode=extraction_mode
        )
        
        return jsonify({
            'request_id': extraction_request['request_id'],
            'status': extraction_request['status'],
            'message': 'Document queued for extraction'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Queue extraction failed: {e}")
        return jsonify({'error': 'Failed to queue extraction'}), 500


@app.route('/documents/<document_id>/status', methods=['GET'])
def get_document_extraction_status(document_id):
    """Get extraction status for a document."""
    from flask import g
    from uuid import UUID
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = UUID(g.tenant_id)
        doc_id = UUID(document_id)
        
        doc_svc = get_document_service()
        document = doc_svc.get_document(doc_id, tenant_id)
        
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        response = {
            'document_id': str(document['id']),
            'document_status': document['status']
        }
        
        return jsonify(response)
        
    except ValueError:
        return jsonify({'error': 'Invalid document ID'}), 400
    except Exception as e:
        logger.error(f"Get status failed: {e}")
        return jsonify({'error': 'Failed to get status'}), 500


@app.route('/')
def landing():
    """Landing page - shows sign in or redirects to dashboard if authenticated."""
    if session.get('user_id') and session.get('tenant_id'):
        return redirect(url_for('vault_list'))
    return render_template('landing.html')

# ============ Vault Routes ============

@app.route('/app')
def vault_list():
    """Vault list - shows all vaults the user has access to."""
    if not session.get('user_id'):
        return redirect(url_for('landing'))
    import time
    return render_template('vault_list.html',
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/new')
def vault_new():
    """Create new vault page."""
    if not session.get('user_id'):
        return redirect(url_for('landing'))
    import time
    return render_template('vault_new.html',
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/<vault_id>')
def vault_view(vault_id):
    """Vault view - file tree and chat interface."""
    if not session.get('user_id'):
        return redirect(url_for('landing'))
    
    try:
        vault_uuid = UUID(vault_id)
        user_uuid = UUID(session['user_id'])
    except (ValueError, TypeError):
        return "Invalid vault ID", 400
    
    from platform_foundation.src.tenant_service import TenantService
    tenant_svc = TenantService()
    if not tenant_svc.user_has_vault_access(user_uuid, vault_uuid):
        return "Access denied", 403
    
    session['tenant_id'] = vault_id
    g.tenant_id = vault_id
    g.user_role = session.get('role', 'user')
    import time
    return render_template('vault_view.html',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/<vault_id>/settings')
def vault_settings(vault_id):
    """Vault settings - API keys and configuration."""
    if not session.get('user_id'):
        return redirect(url_for('landing'))
    
    try:
        vault_uuid = UUID(vault_id)
        user_uuid = UUID(session['user_id'])
    except (ValueError, TypeError):
        return "Invalid vault ID", 400
    
    from platform_foundation.src.tenant_service import TenantService
    tenant_svc = TenantService()
    if not tenant_svc.user_has_vault_access(user_uuid, vault_uuid):
        return "Access denied", 403
    
    session['tenant_id'] = vault_id
    g.tenant_id = vault_id
    g.user_role = session.get('role', 'user')
    import time
    return render_template('vault_settings.html',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

# ============ Vault API ============

@app.route('/api/vaults', methods=['GET'])
def api_list_vaults():
    """List all vaults the user has access to."""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from platform_foundation.src.tenant_service import TenantService
        tenant_svc = TenantService()
        vaults = tenant_svc.list_user_vaults(UUID(session['user_id']))
        
        result = []
        for v in vaults:
            result.append({
                'id': str(v['id']),
                'name': v['name'],
                'slug': v['slug'],
                'document_count': v.get('document_count', 0),
                'created_at': v['created_at'].isoformat() if v.get('created_at') else None,
                'updated_at': v['updated_at'].isoformat() if v.get('updated_at') else None
            })
        
        return jsonify({'success': True, 'vaults': result})
    except Exception as e:
        logger.error(f"Failed to list vaults: {e}")
        return jsonify({'error': 'Failed to list vaults'}), 500

@app.route('/api/vaults', methods=['POST'])
def api_create_vault():
    """Create a new vault."""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Vault name is required'}), 400
        if len(name) < 2:
            return jsonify({'error': 'Vault name must be at least 2 characters'}), 400
        if len(name) > 100:
            return jsonify({'error': 'Vault name must be less than 100 characters'}), 400
        
        from platform_foundation.src.tenant_service import TenantService
        tenant_svc = TenantService()
        vault = tenant_svc.create_vault_for_user(UUID(session['user_id']), name)
        
        session['tenant_id'] = str(vault['id'])
        
        return jsonify({
            'success': True,
            'vault': {
                'id': str(vault['id']),
                'name': vault['name'],
                'slug': vault['slug']
            }
        })
    except Exception as e:
        logger.error(f"Failed to create vault: {e}")
        return jsonify({'error': 'Failed to create vault'}), 500

@app.route('/api/vaults/<vault_id>', methods=['GET'])
def api_get_vault(vault_id):
    """Get vault details."""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        try:
            vault_uuid = UUID(vault_id)
            user_uuid = UUID(session['user_id'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid vault ID'}), 400
        
        from platform_foundation.src.tenant_service import TenantService
        tenant_svc = TenantService()
        
        if not tenant_svc.user_has_vault_access(user_uuid, vault_uuid):
            return jsonify({'error': 'Access denied'}), 403
        
        vault = tenant_svc.get_tenant(vault_uuid)
        
        if not vault:
            return jsonify({'error': 'Vault not found'}), 404
        
        stats = tenant_svc.get_vault_stats(vault_uuid)
        
        return jsonify({
            'success': True,
            'vault': {
                'id': str(vault['id']),
                'name': vault['name'],
                'slug': vault['slug'],
                'total_documents': stats.get('total_documents', 0),
                'completed_documents': stats.get('completed_documents', 0),
                'last_activity': stats['last_activity'].isoformat() if stats.get('last_activity') else None
            }
        })
    except Exception as e:
        logger.error(f"Failed to get vault: {e}")
        return jsonify({'error': 'Failed to get vault'}), 500

@app.route('/api/vaults/<vault_id>', methods=['DELETE'])
def api_delete_vault(vault_id):
    """Delete a vault and all associated data. Requires owner role and confirmation."""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        try:
            vault_uuid = UUID(vault_id)
            user_uuid = UUID(session['user_id'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid vault ID'}), 400
        
        data = request.get_json() or {}
        confirmation_name = data.get('confirmation_name', '').strip()
        confirm_delete = data.get('confirm_delete', False)
        
        from platform_foundation.src.tenant_service import TenantService
        tenant_svc = TenantService()
        
        if not tenant_svc.user_is_vault_owner(user_uuid, vault_uuid):
            return jsonify({'error': 'Only the vault owner can delete this vault'}), 403
        
        vault = tenant_svc.get_tenant(vault_uuid)
        if not vault:
            return jsonify({'error': 'Vault not found'}), 404
        
        if not confirm_delete:
            return jsonify({'error': 'Deletion not confirmed'}), 400
        
        if confirmation_name != vault['name']:
            return jsonify({'error': 'Vault name does not match'}), 400
        
        deleted = delete_vault_and_artifacts(vault_uuid)
        
        if session.get('tenant_id') == vault_id:
            session.pop('tenant_id', None)
        
        logger.info(f"Vault {vault_id} deleted by owner {user_uuid}. Artifacts deleted: {deleted}")
        
        return jsonify({
            'success': True,
            'message': 'Vault deleted successfully',
            'deleted': deleted
        })
    except Exception as e:
        logger.error(f"Failed to delete vault {vault_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete vault'}), 500

from src.context_foundry.utils.vault_operations import delete_vault_and_artifacts

# ============ Legacy App Routes (within vault context) ============

def require_vault_access(vault_id):
    """Check vault access and return redirect/error if not authorized."""
    if not session.get('user_id'):
        return redirect(url_for('landing'))
    try:
        vault_uuid = UUID(vault_id)
        user_uuid = UUID(session['user_id'])
    except (ValueError, TypeError):
        return "Invalid vault ID", 400
    from platform_foundation.src.tenant_service import TenantService
    tenant_svc = TenantService()
    if not tenant_svc.user_has_vault_access(user_uuid, vault_uuid):
        return "Access denied", 403
    session['tenant_id'] = vault_id
    g.tenant_id = vault_id
    g.user_role = session.get('role', 'user')
    return None

@app.route('/app/<vault_id>/dashboard')
def index(vault_id):
    """Knowledge dashboard - main knowledge exploration interface."""
    auth_check = require_vault_access(vault_id)
    if auth_check:
        return auth_check
    import time
    return render_template('index.html', 
                         active_section='knowledge',
                         active_page='dashboard',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/<vault_id>/memory-graph')
def app_memory_graph(vault_id):
    """Knowledge - Memory Graph page."""
    auth_check = require_vault_access(vault_id)
    if auth_check:
        return auth_check
    import time
    return render_template('index.html',
                         active_section='knowledge', 
                         active_page='memory-graph',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/<vault_id>/command-center')
def app_command_center(vault_id):
    """Knowledge - Command Center page."""
    auth_check = require_vault_access(vault_id)
    if auth_check:
        return auth_check
    import time
    return render_template('index.html',
                         active_section='knowledge',
                         active_page='command-center',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

@app.route('/app/<vault_id>/evaluation')
def app_evaluation(vault_id):
    """Knowledge - A/B Evaluation page."""
    auth_check = require_vault_access(vault_id)
    if auth_check:
        return auth_check
    import time
    return render_template('index.html',
                         active_section='knowledge',
                         active_page='evaluation',
                         vault_id=vault_id,
                         user_name=session.get('user_name', 'User'),
                         cache_bust=int(time.time()))

def get_dashboard_context(active_page='upload'):
    """Helper to get dashboard context with tenant info."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    tenant_name = session.get('user_name', 'My') + "'s Space"
    
    try:
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT name FROM platform.tenants WHERE id = %s", (session['tenant_id'],))
                tenant = cur.fetchone()
                if tenant:
                    tenant_name = tenant['name']
    except Exception as e:
        logger.warning(f"Could not fetch tenant name: {e}")
    
    return {
        'tenant_id': session['tenant_id'],
        'tenant_name': tenant_name,
        'user_name': session.get('user_name', 'User'),
        'user_email': session.get('user_email', ''),
        'active_section': 'sources',
        'active_page': active_page
    }

@app.route('/dashboard')
@app.route('/dashboard/documents')
def user_dashboard():
    """Sources - Documents page (combined upload + status)."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return redirect(url_for('landing'))
    return render_template('user_dashboard.html', **get_dashboard_context('documents'))

@app.route('/dashboard/upload')
@app.route('/dashboard/status')
def redirect_old_routes():
    """Redirect old upload/status routes to documents."""
    return redirect(url_for('user_dashboard'))

@app.route('/dashboard/connectors')
def dashboard_connectors_page():
    """Sources - Connectors page."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return redirect(url_for('landing'))
    return render_template('user_dashboard.html', **get_dashboard_context('connectors'))


@app.route('/dashboard/api-keys')
def dashboard_api_keys_page():
    """Sources - API Keys page."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return redirect(url_for('landing'))
    return render_template('user_dashboard.html', **get_dashboard_context('api-keys'))

@app.route('/logout')
def logout():
    """Clear session and redirect to landing."""
    session.clear()
    return redirect(url_for('landing'))

@app.route('/dashboard/search', methods=['POST'])
def dashboard_search():
    """Search knowledge graph for authenticated user."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    try:
        from uuid import UUID
        foundry = get_context_foundry()
        tenant_id = UUID(session['tenant_id'])
        
        result = foundry.query_context(
            query=query,
            tenant_id=tenant_id,
            include_context=True
        )
        
        return jsonify({
            'success': True,
            'answer': result.get('answer', ''),
            'confidence': result.get('confidence', 0),
            'sources': result.get('sources', [])
        })
        
    except Exception as e:
        logger.error(f"Dashboard search failed: {e}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500

@app.route('/api/corpus-stats', methods=['GET'])
def api_corpus_stats():
    """API: Get corpus statistics for the current tenant."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    tenant_id = session.get('tenant_id')
    
    try:
        import psycopg2
        database_url = os.environ.get("DATABASE_URL")
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = %s",
                    (tenant_id,)
                )
                doc_count = cur.fetchone()[0]
                
                cur.execute(
                    "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = %s AND status IN ('queued', 'processing')",
                    (tenant_id,)
                )
                processing_count = cur.fetchone()[0]
                
                cur.execute(
                    "SELECT COUNT(*) FROM public.entities WHERE tenant_id = %s",
                    (tenant_id,)
                )
                entity_count = cur.fetchone()[0]
                
                cur.execute(
                    "SELECT COUNT(*) FROM public.relationships WHERE tenant_id = %s",
                    (tenant_id,)
                )
                relationship_count = cur.fetchone()[0]
        
        return jsonify({
            'success': True,
            'documents': doc_count,
            'entities': entity_count,
            'relationships': relationship_count,
            'processing': processing_count
        })
        
    except Exception as e:
        print(f"[CorpusStats] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents/upload/multi', methods=['POST'])
def api_documents_upload_multi():
    """API: Upload multiple documents - wrapper for dashboard upload."""
    return dashboard_upload_multi()

@app.route('/api/folders', methods=['GET'])
def api_list_folders():
    """List all folders for the current tenant."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, path, parent_path, created_at
                    FROM platform.folders
                    WHERE tenant_id = %s
                    ORDER BY path
                """, (session['tenant_id'],))
                folders = cur.fetchall()
        
        return jsonify({
            'success': True,
            'folders': [{
                'id': str(f['id']),
                'name': f['name'],
                'path': f['path'],
                'parent_path': f['parent_path']
            } for f in folders]
        })
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders', methods=['POST'])
def api_create_folder():
    """Create a new folder."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        data = request.get_json()
        name = data.get('name', '').strip()
        parent_path = data.get('parent_path', '/').strip()
        
        if not name:
            return jsonify({'error': 'Folder name is required'}), 400
        
        if not parent_path.startswith('/'):
            parent_path = '/' + parent_path
        if not parent_path.endswith('/'):
            parent_path = parent_path + '/'
        
        folder_path = parent_path + name + '/'
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.folders (tenant_id, name, path, parent_path)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, path) DO NOTHING
                    RETURNING id, name, path, parent_path
                """, (session['tenant_id'], name, folder_path, parent_path))
                folder = cur.fetchone()
                conn.commit()
                
                if not folder:
                    return jsonify({'error': 'Folder already exists'}), 409
        
        return jsonify({
            'success': True,
            'folder': {
                'id': str(folder['id']),
                'name': folder['name'],
                'path': folder['path'],
                'parent_path': folder['parent_path']
            }
        })
    except Exception as e:
        logger.error(f"Failed to create folder: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<doc_id>/move', methods=['POST'])
def api_move_document(doc_id):
    """Move a document to a different folder."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        
        data = request.get_json()
        folder_path = data.get('folder_path', '/').strip()
        
        if not folder_path.startswith('/'):
            folder_path = '/' + folder_path
        if not folder_path.endswith('/') and folder_path != '/':
            folder_path = folder_path + '/'
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.documents
                    SET folder_path = %s, updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                """, (folder_path, doc_id, session['tenant_id']))
                conn.commit()
                
                if cur.rowcount == 0:
                    return jsonify({'error': 'Document not found'}), 404
        
        return jsonify({'success': True, 'folder_path': folder_path})
    except Exception as e:
        logger.error(f"Failed to move document: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/tree', methods=['GET'])
def api_documents_tree():
    """Get documents organized by folder structure."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, path, parent_path
                    FROM platform.folders
                    WHERE tenant_id = %s
                    ORDER BY path
                """, (session['tenant_id'],))
                folders = cur.fetchall()
                
                cur.execute("""
                    SELECT d.id, d.original_filename, d.folder_path, d.status, d.mime_type,
                           COALESCE(er.status, d.status) as extraction_status
                    FROM platform.documents d
                    LEFT JOIN LATERAL (
                        SELECT status FROM platform.extraction_requests 
                        WHERE document_id = d.id 
                        ORDER BY created_at DESC LIMIT 1
                    ) er ON true
                    WHERE d.tenant_id = %s
                    ORDER BY d.folder_path, d.original_filename
                """, (session['tenant_id'],))
                documents = cur.fetchall()
        
        return jsonify({
            'success': True,
            'folders': [{
                'id': str(f['id']),
                'name': f['name'],
                'path': f['path'],
                'parent_path': f['parent_path']
            } for f in folders],
            'documents': [{
                'id': str(d['id']),
                'name': d['original_filename'],
                'folder_path': d['folder_path'] or '/',
                'status': d['extraction_status'],
                'mime_type': d['mime_type']
            } for d in documents]
        })
    except Exception as e:
        logger.error(f"Failed to get document tree: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents', methods=['GET'])
def api_documents():
    """API: List documents for authenticated user with pagination, search, and filtering."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        sort_by = request.args.get('sort', 'created_at')
        sort_dir = request.args.get('dir', 'desc')
        
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        valid_sorts = {'created_at', 'original_filename', 'status'}
        if sort_by not in valid_sorts:
            sort_by = 'created_at'
        sort_dir = 'DESC' if sort_dir.lower() == 'desc' else 'ASC'
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                where_clauses = ["tenant_id = %s"]
                params = [session['tenant_id']]
                
                if search:
                    where_clauses.append("original_filename ILIKE %s")
                    params.append(f"%{search}%")
                
                if status_filter:
                    where_clauses.append("status = %s")
                    params.append(status_filter)
                
                where_sql = " AND ".join(where_clauses)
                
                cur.execute(f"SELECT COUNT(*) as total FROM platform.documents WHERE {where_sql}", params)
                total = cur.fetchone()['total']
                
                cur.execute(f"""
                    SELECT d.id, d.original_filename, d.mime_type, d.status, d.created_at,
                           d.published, COALESCE(e.entity_count, 0) as entity_count
                    FROM platform.documents d
                    LEFT JOIN (
                        SELECT source_document_id, COUNT(*) as entity_count
                        FROM public.entities
                        WHERE tenant_id = %s
                        GROUP BY source_document_id
                    ) e ON d.id::text = e.source_document_id::text
                    WHERE {where_sql}
                    ORDER BY {sort_by} {sort_dir}
                    LIMIT %s OFFSET %s
                """, [session['tenant_id']] + params + [per_page, offset])
                docs = cur.fetchall()
                
                cur.execute("""
                    SELECT COUNT(*) as count FROM platform.documents
                    WHERE tenant_id = %s AND status IN ('queued', 'processing')
                """, (session['tenant_id'],))
                processing_count = cur.fetchone()['count']
        
        return jsonify({
            'success': True,
            'documents': [{
                'id': str(doc['id']),
                'name': doc['original_filename'],
                'mime_type': doc['mime_type'],
                'status': doc['status'] or 'pending',
                'published': doc['published'] or False,
                'created_at': doc['created_at'].isoformat() if doc['created_at'] else None,
                'entity_count': doc['entity_count']
            } for doc in docs],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            },
            'processing_count': processing_count
        })
        
    except Exception as e:
        logger.error(f"Dashboard documents failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to load documents'}), 500

@app.route('/api/documents/<doc_id>/details', methods=['GET'])
def api_document_details(doc_id):
    """API: Get document details including all extracted entities."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, original_filename, status, mime_type, created_at,
                           extraction_method, extraction_metrics, published
                    FROM platform.documents 
                    WHERE id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                doc = cur.fetchone()
                
                if not doc:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                cur.execute("""
                    SELECT entity_type, name, confidence
                    FROM public.entities
                    WHERE source_document_id = %s AND tenant_id = %s
                    ORDER BY entity_type, confidence DESC, name
                """, [doc_id, tenant_id])
                entities = cur.fetchall()
        
        grouped = {}
        for e in entities:
            etype = e['entity_type']
            if etype not in grouped:
                grouped[etype] = []
            grouped[etype].append({
                'name': e['name'],
                'confidence': float(e['confidence']) if e['confidence'] else 0.9
            })
        
        file_type = 'unknown'
        if doc['original_filename']:
            ext = doc['original_filename'].split('.')[-1].lower()
            file_type = ext if ext in ['pdf', 'doc', 'docx', 'txt', 'md', 'json', 'csv', 'xls', 'xlsx', 'ppt', 'pptx', 'html', 'xml'] else 'file'
        
        return jsonify({
            'success': True,
            'id': str(doc['id']),
            'name': doc['original_filename'],
            'status': doc['status'],
            'file_type': file_type,
            'created_at': doc['created_at'].isoformat() if doc['created_at'] else None,
            'extraction_method': doc['extraction_method'] or 'text',
            'extraction_metrics': doc['extraction_metrics'] or {},
            'published': doc['published'] or False,
            'entity_count': len(entities),
            'entities_by_type': grouped
        })
        
    except Exception as e:
        logger.error(f"Document details failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to load document details'}), 500

@app.route('/api/documents/<doc_id>/publish', methods=['POST'])
def publish_document(doc_id):
    """Approve document - entities become trusted."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    user_email = session.get('user_email', 'user')
    
    try:
        import psycopg2
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.documents 
                    SET published = TRUE, published_at = NOW(), published_by = %s
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                """, [user_email, doc_id, tenant_id])
                
                if cur.fetchone() is None:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                cur.execute("""
                    UPDATE public.entities 
                    SET status = 'trusted'
                    WHERE source_document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                conn.commit()
        
        logger.info(f"Document {doc_id} published by {user_email}")
        return jsonify({'success': True, 'published': True})
        
    except Exception as e:
        logger.error(f"Publish failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to publish document'}), 500

@app.route('/api/documents/<doc_id>/unpublish', methods=['POST'])
def unpublish_document(doc_id):
    """Retract document - entities back to staging."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.documents 
                    SET published = FALSE, published_at = NULL
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                """, [doc_id, tenant_id])
                
                if cur.fetchone() is None:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                cur.execute("""
                    UPDATE public.entities 
                    SET status = 'staging'
                    WHERE source_document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                conn.commit()
        
        logger.info(f"Document {doc_id} unpublished")
        return jsonify({'success': True, 'published': False})
        
    except Exception as e:
        logger.error(f"Unpublish failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to unpublish document'}), 500

@app.route('/api/documents/<doc_id>/reject', methods=['POST'])
def reject_document(doc_id):
    """Reject document - delete entities, mark as rejected."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM public.relationships 
                    WHERE tenant_id = %s AND (
                        source_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                        OR target_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                    )
                """, [tenant_id, doc_id, doc_id])
                
                cur.execute("""
                    DELETE FROM public.entities 
                    WHERE source_document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                cur.execute("""
                    UPDATE platform.documents 
                    SET status = 'rejected', published = FALSE
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                """, [doc_id, tenant_id])
                
                if cur.fetchone() is None:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                conn.commit()
        
        logger.info(f"Document {doc_id} rejected")
        return jsonify({'success': True, 'status': 'rejected'})
        
    except Exception as e:
        logger.error(f"Reject failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to reject document'}), 500

@app.route('/api/documents/<doc_id>/re-extract', methods=['POST'])
def re_extract_document(doc_id):
    """Re-extract document - delete entities, re-queue for extraction."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, original_filename, mime_type
                    FROM platform.documents 
                    WHERE id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                doc = cur.fetchone()
                
                if not doc:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                cur.execute("""
                    DELETE FROM public.relationships 
                    WHERE tenant_id = %s AND (
                        source_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                        OR target_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                    )
                """, [tenant_id, doc_id, doc_id])
                
                cur.execute("""
                    DELETE FROM public.entities 
                    WHERE source_document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                cur.execute("""
                    UPDATE platform.documents 
                    SET status = 'queued', published = FALSE, 
                        extraction_method = NULL, extraction_metrics = NULL
                    WHERE id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                cur.execute("""
                    INSERT INTO platform.extraction_requests 
                    (id, request_id, document_id, tenant_id, file_path, file_name, 
                     mime_type, file_size_bytes, extraction_mode, priority, status, 
                     retry_count, max_retries, created_at, submitted_at)
                    VALUES (
                        gen_random_uuid(), gen_random_uuid(), %s, %s,
                        './storage/tenants/' || %s || '/documents/' || %s || '/v1/content',
                        %s, %s, 0, 'full', 'high', 'pending', 0, 3, NOW(), NOW()
                    )
                """, [doc_id, tenant_id, tenant_id, doc_id, 
                      doc['original_filename'], doc['mime_type'] or 'application/pdf'])
                
                conn.commit()
        
        logger.info(f"Document {doc_id} queued for re-extraction")
        return jsonify({'success': True, 'status': 'queued'})
        
    except Exception as e:
        logger.error(f"Re-extract failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to re-extract document'}), 500


@app.route('/api/documents/backfill-chunks', methods=['POST'])
def backfill_document_chunks():
    """Backfill document chunks for existing documents that don't have chunks.
    
    This enables RAG fallback for documents uploaded before chunk storage was added.
    Creates chunks from platform.documents content and entity source_sentences.
    """
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        import uuid as uuid_module
        from psycopg2.extras import RealDictCursor
        database_url = os.environ.get("DATABASE_URL")
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT pd.id as platform_doc_id, 
                           pd.original_filename,
                           d.id as public_doc_id
                    FROM platform.documents pd
                    LEFT JOIN public.documents d ON d.source_document_id = pd.id::text 
                                                  AND d.tenant_id = pd.tenant_id
                    WHERE pd.tenant_id = %s
                      AND pd.status = 'extracted'
                      AND pd.id NOT IN (
                          SELECT DISTINCT dc.document_id 
                          FROM public.document_chunks dc 
                          WHERE dc.tenant_id = %s::uuid
                      )
                """, [tenant_id, tenant_id])
                
                docs_to_backfill = cur.fetchall()
                
                if not docs_to_backfill:
                    return jsonify({
                        'success': True, 
                        'message': 'No documents need chunk backfill',
                        'documents_processed': 0
                    })
                
                chunks_created = 0
                docs_processed = 0
                
                for doc in docs_to_backfill:
                    platform_doc_id = str(doc['platform_doc_id'])
                    public_doc_id = doc['public_doc_id']
                    
                    cur.execute("""
                        SELECT array_agg(DISTINCT source_sentence) as sentences
                        FROM public.entities 
                        WHERE tenant_id = %s::uuid
                          AND source_document_id = %s
                          AND source_sentence IS NOT NULL
                          AND LENGTH(source_sentence) > 10
                    """, [tenant_id, platform_doc_id])
                    
                    result = cur.fetchone()
                    sentences = result['sentences'] if result and result['sentences'] else []
                    
                    if not sentences:
                        continue
                    
                    if not public_doc_id:
                        public_doc_id = uuid_module.uuid4()
                        cur.execute("""
                            INSERT INTO public.documents 
                            (id, tenant_id, title, doc_type, content, source_document_id, created_at)
                            VALUES (%s, %s::uuid, %s, 'DOCUMENT', %s, %s, NOW())
                        """, [
                            str(public_doc_id),
                            tenant_id,
                            doc['original_filename'] or 'Backfilled Document',
                            ' '.join(sentences)[:5000],
                            platform_doc_id
                        ])
                    
                    full_text = " ".join(sentences)
                    chunk_size = 1500
                    chunks = []
                    
                    for i in range(0, len(full_text), chunk_size):
                        chunk_text = full_text[i:i+chunk_size]
                        if len(chunk_text.strip()) > 50:
                            chunks.append(chunk_text)
                    
                    for idx, chunk_text in enumerate(chunks):
                        chunk_id = str(uuid_module.uuid4())
                        cur.execute("""
                            INSERT INTO public.document_chunks 
                            (id, document_id, tenant_id, chunk_index, text, char_start, char_end, chunk_metadata)
                            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s::json)
                            ON CONFLICT (document_id, chunk_index) DO NOTHING
                        """, [
                            chunk_id,
                            str(public_doc_id),
                            tenant_id,
                            idx,
                            chunk_text,
                            idx * chunk_size,
                            min((idx + 1) * chunk_size, len(full_text)),
                            '{"source": "backfill"}'
                        ])
                        chunks_created += 1
                    
                    docs_processed += 1
                
                conn.commit()
        
        logger.info(f"Backfill complete: {docs_processed} documents, {chunks_created} chunks")
        return jsonify({
            'success': True,
            'documents_processed': docs_processed,
            'chunks_created': chunks_created
        })
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Hard delete document and all associated data."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    tenant_id = session['tenant_id']
    
    try:
        import psycopg2
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM public.relationships 
                    WHERE tenant_id = %s AND (
                        source_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                        OR target_id IN (SELECT id FROM public.entities WHERE source_document_id = %s)
                    )
                """, [tenant_id, doc_id, doc_id])
                
                cur.execute("""
                    DELETE FROM public.entities 
                    WHERE source_document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                cur.execute("""
                    DELETE FROM platform.extraction_requests 
                    WHERE document_id = %s AND tenant_id = %s
                """, [doc_id, tenant_id])
                
                cur.execute("""
                    DELETE FROM platform.documents 
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                """, [doc_id, tenant_id])
                
                if cur.fetchone() is None:
                    return jsonify({'success': False, 'error': 'Document not found'}), 404
                
                conn.commit()
        
        logger.info(f"Document {doc_id} permanently deleted")
        return jsonify({'success': True, 'deleted': True})
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete document'}), 500

@app.route('/test-upload', methods=['POST'])
def test_upload():
    try:
        print("=== TEST UPLOAD HIT ===")
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        f = request.files['file']
        print(f"File: {f.filename}, Size: {f.content_length}")
        return jsonify({'success': True, 'filename': f.filename})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard/upload', methods=['POST'])
def dashboard_upload():
    """Upload a document for authenticated user."""
    print("=== SINGLE UPLOAD STARTED ===")
    print(f"Session: user_id={session.get('user_id')}, tenant_id={session.get('tenant_id')}")
    if not session.get('user_id') or not session.get('tenant_id'):
        print("=== UPLOAD FAILED: No auth ===")
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    if 'file' not in request.files:
        print("=== UPLOAD FAILED: No file in request ===")
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    print(f"File received: {file.filename}")
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    try:
        from uuid import UUID, uuid4
        import psycopg2
        
        tenant_id = UUID(session['tenant_id'])
        user_id = UUID(session['user_id'])
        
        doc_id = uuid4()
        version = 1
        storage_dir = f"./storage/tenants/{tenant_id}/documents/{doc_id}/v{version}"
        os.makedirs(storage_dir, exist_ok=True)
        storage_path = f"{storage_dir}/content"
        
        file.save(storage_path)
        file_size = os.path.getsize(storage_path)
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.documents (
                        id, tenant_id, name, original_filename, mime_type, 
                        storage_path, size_bytes, current_version, status, created_by, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s, NOW(), NOW())
                """, (str(doc_id), str(tenant_id), file.filename, file.filename, 
                      file.content_type or 'application/octet-stream',
                      storage_path, file_size, version, str(user_id)))
                
                cur.execute("""
                    INSERT INTO platform.usage_events (
                        tenant_id, user_id, event_type, document_id, tokens_consumed, metadata, created_at
                    ) VALUES (%s, %s, 'upload', %s, %s, %s, NOW())
                """, (str(tenant_id), str(user_id), str(doc_id), file_size,
                      json.dumps({'filename': file.filename})))
                
                cur.execute("""
                    INSERT INTO platform.extraction_requests (
                        id, request_id, document_id, tenant_id, file_path, file_name, 
                        mime_type, file_size_bytes, extraction_mode, priority, status,
                        submitted_at, retry_count, max_retries, created_at
                    ) VALUES (gen_random_uuid(), gen_random_uuid(), %s, %s, %s, %s, %s, %s, 
                              'full', 'normal', 'pending', NOW(), 0, 3, NOW())
                """, (str(doc_id), str(tenant_id), storage_path, file.filename,
                      file.content_type or 'application/octet-stream', file_size))
                
                conn.commit()
        
        return jsonify({
            'success': True,
            'document_id': str(doc_id),
            'filename': file.filename
        })
        
    except Exception as e:
        print(f"=== SINGLE UPLOAD FAILED: {e} ===")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/upload/multi', methods=['POST'])
def dashboard_upload_multi():
    """Upload multiple files at once."""
    import traceback
    print("=== MULTI UPLOAD STARTED ===")
    print(f"Step 0: Session check - user_id={session.get('user_id')}, tenant_id={session.get('tenant_id')}")
    
    # Detect if this is an AJAX request (expects JSON response)
    is_ajax = 'application/json' in request.headers.get('Accept', '') or \
              request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    print(f"Step 0: is_ajax={is_ajax}")
    
    if not session.get('user_id') or not session.get('tenant_id'):
        print("=== MULTI UPLOAD FAILED: No auth ===")
        if not is_ajax:
            return redirect('/dashboard?error=auth')
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        print("Step 1: Getting files from request")
        files = request.files.getlist('files')
        print(f"Step 1: Got {len(files) if files else 0} files")
        if not files or len(files) == 0:
            return jsonify({'success': False, 'error': 'No files provided'}), 400
        
        from uuid import UUID, uuid4
        import psycopg2
        import hashlib
        
        print("Step 2: Parsing tenant_id and user_id from session")
        tenant_id = UUID(session['tenant_id'])
        user_id = UUID(session['user_id'])
        print(f"Step 2: tenant_id={tenant_id}, user_id={user_id}")
        
        JUNK_PATTERNS = ['.DS_Store', 'Thumbs.db', 'desktop.ini', '.gitignore', '__pycache__']
        ALLOWED_EXTENSIONS = ['.txt', '.md', '.json', '.csv', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.html', '.xml']
        MAX_FILE_SIZE = 50 * 1024 * 1024
        
        results = []
        database_url = os.environ.get("DATABASE_URL")
        print(f"Step 3: Connecting to database (URL exists: {bool(database_url)})")
        
        with psycopg2.connect(database_url) as conn:
            print("Step 3: Database connected")
            with conn.cursor() as cur:
                for idx, file in enumerate(files):
                    print(f"Step 4: Processing file {idx+1}: {file.filename}")
                    if not file.filename:
                        continue
                    
                    filename = file.filename
                    if any(junk in filename for junk in JUNK_PATTERNS):
                        results.append({'filename': filename, 'status': 'skipped', 'reason': 'Junk file'})
                        continue
                    
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        results.append({'filename': filename, 'status': 'skipped', 'reason': f'Unsupported type: {ext}'})
                        continue
                    
                    doc_id = uuid4()
                    version = 1
                    storage_dir = f"./storage/tenants/{tenant_id}/documents/{doc_id}/v{version}"
                    print(f"Step 5: Creating storage dir: {storage_dir}")
                    os.makedirs(storage_dir, exist_ok=True)
                    storage_path = f"{storage_dir}/content"
                    
                    print(f"Step 6: Saving file to {storage_path}")
                    file.save(storage_path)
                    file_size = os.path.getsize(storage_path)
                    print(f"Step 6: File saved, size={file_size}")
                    
                    if file_size > MAX_FILE_SIZE:
                        os.remove(storage_path)
                        results.append({'filename': filename, 'status': 'skipped', 'reason': 'File too large (>50MB)'})
                        continue
                    
                    print("Step 7: Computing content hash")
                    with open(storage_path, 'rb') as f:
                        content_hash = hashlib.sha256(f.read()).hexdigest()
                    print(f"Step 7: Hash={content_hash[:16]}...")
                    
                    print("Step 8: Checking for duplicates")
                    cur.execute("""
                        SELECT id FROM platform.documents 
                        WHERE tenant_id = %s AND content_hash = %s LIMIT 1
                    """, (str(tenant_id), content_hash))
                    if cur.fetchone():
                        os.remove(storage_path)
                        results.append({'filename': filename, 'status': 'duplicate', 'reason': 'Content already exists'})
                        print("Step 8: Duplicate found, skipping")
                        continue
                    print("Step 8: No duplicate")
                    
                    print("Step 9: Inserting into platform.documents")
                    cur.execute("""
                        INSERT INTO platform.documents (
                            id, tenant_id, name, original_filename, mime_type, 
                            storage_path, size_bytes, current_version, status, content_hash, created_by, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s, %s, NOW(), NOW())
                    """, (str(doc_id), str(tenant_id), filename, filename, 
                          file.content_type or 'application/octet-stream',
                          storage_path, file_size, version, content_hash, str(user_id)))
                    print("Step 9: Document inserted")
                    
                    print("Step 10: Inserting usage event")
                    cur.execute("""
                        INSERT INTO platform.usage_events (
                            tenant_id, user_id, event_type, document_id, tokens_consumed, metadata, created_at
                        ) VALUES (%s, %s, 'upload', %s, %s, %s, NOW())
                    """, (str(tenant_id), str(user_id), str(doc_id), file_size,
                          json.dumps({'filename': filename, 'source': 'multi_upload'})))
                    print("Step 10: Usage event inserted")
                    
                    print("Step 10b: Inserting extraction request")
                    cur.execute("""
                        INSERT INTO platform.extraction_requests (
                            id, request_id, document_id, tenant_id, file_path, file_name,
                            mime_type, file_size_bytes, extraction_mode, priority, status,
                            submitted_at, retry_count, max_retries, created_at
                        ) VALUES (gen_random_uuid(), gen_random_uuid(), %s, %s, %s, %s, %s, %s,
                                  'full', 'normal', 'pending', NOW(), 0, 3, NOW())
                    """, (str(doc_id), str(tenant_id), storage_path, filename,
                          file.content_type or 'application/octet-stream', file_size))
                    print("Step 10b: Extraction request inserted")
                    
                    results.append({'filename': filename, 'status': 'queued', 'document_id': str(doc_id)})
                
                print("Step 11: Committing transaction")
                conn.commit()
                print("Step 11: Committed")
        
        queued = sum(1 for r in results if r['status'] == 'queued')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        duplicates = sum(1 for r in results if r['status'] == 'duplicate')
        
        print(f"=== MULTI UPLOAD SUCCESS: queued={queued}, skipped={skipped}, duplicates={duplicates} ===")
        
        if not is_ajax:
            return redirect(f'/dashboard?uploaded={queued}&skipped={skipped}&duplicates={duplicates}')
        
        return jsonify({
            'success': True,
            'summary': {'queued': queued, 'skipped': skipped, 'duplicates': duplicates},
            'results': results
        })
        
    except Exception as e:
        print(f"=== MULTI UPLOAD EXCEPTION: {e} ===")
        traceback.print_exc()
        if not is_ajax:
            return redirect(f'/dashboard?error={str(e)[:50]}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/upload/zip', methods=['POST'])
def dashboard_upload_zip():
    """Upload a ZIP file and extract its contents."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': 'Please upload a ZIP file'}), 400
    
    try:
        from uuid import UUID, uuid4
        import psycopg2
        import hashlib
        import zipfile
        import tempfile
        
        tenant_id = UUID(session['tenant_id'])
        user_id = UUID(session['user_id'])
        
        JUNK_PATTERNS = ['.DS_Store', 'Thumbs.db', 'desktop.ini', '.gitignore', '__pycache__', '__MACOSX']
        ALLOWED_EXTENSIONS = ['.txt', '.md', '.json', '.csv', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.html', '.xml']
        MAX_FILE_SIZE = 50 * 1024 * 1024
        MAX_ZIP_SIZE = 200 * 1024 * 1024
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            file.save(tmp.name)
            zip_path = tmp.name
        
        if os.path.getsize(zip_path) > MAX_ZIP_SIZE:
            os.remove(zip_path)
            return jsonify({'success': False, 'error': 'ZIP file too large (>200MB)'}), 400
        
        results = []
        database_url = os.environ.get("DATABASE_URL")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                with psycopg2.connect(database_url) as conn:
                    with conn.cursor() as cur:
                        for zip_info in zf.infolist():
                            if zip_info.is_dir():
                                continue
                            
                            filename = os.path.basename(zip_info.filename)
                            if not filename:
                                continue
                            
                            if any(junk in zip_info.filename for junk in JUNK_PATTERNS):
                                results.append({'filename': filename, 'status': 'skipped', 'reason': 'Junk file'})
                                continue
                            
                            ext = os.path.splitext(filename)[1].lower()
                            if ext not in ALLOWED_EXTENSIONS:
                                results.append({'filename': filename, 'status': 'skipped', 'reason': f'Unsupported type: {ext}'})
                                continue
                            
                            if zip_info.file_size > MAX_FILE_SIZE:
                                results.append({'filename': filename, 'status': 'skipped', 'reason': 'File too large'})
                                continue
                            
                            content = zf.read(zip_info.filename)
                            content_hash = hashlib.sha256(content).hexdigest()
                            
                            cur.execute("""
                                SELECT id FROM platform.documents 
                                WHERE tenant_id = %s AND content_hash = %s LIMIT 1
                            """, (str(tenant_id), content_hash))
                            if cur.fetchone():
                                results.append({'filename': filename, 'status': 'duplicate', 'reason': 'Content already exists'})
                                continue
                            
                            doc_id = uuid4()
                            version = 1
                            storage_dir = f"./storage/tenants/{tenant_id}/documents/{doc_id}/v{version}"
                            os.makedirs(storage_dir, exist_ok=True)
                            storage_path = f"{storage_dir}/content"
                            
                            with open(storage_path, 'wb') as out_file:
                                out_file.write(content)
                            
                            mime_type, _ = mimetypes.guess_type(filename)
                            
                            cur.execute("""
                                INSERT INTO platform.documents (
                                    id, tenant_id, name, original_filename, mime_type, 
                                    storage_path, size_bytes, current_version, status, content_hash, created_by, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s, %s, NOW(), NOW())
                            """, (str(doc_id), str(tenant_id), filename, filename, 
                                  mime_type or 'application/octet-stream',
                                  storage_path, len(content), version, content_hash, str(user_id)))
                            
                            cur.execute("""
                                INSERT INTO platform.usage_events (
                                    tenant_id, user_id, event_type, document_id, tokens_consumed, metadata, created_at
                                ) VALUES (%s, %s, 'upload', %s, %s, %s, NOW())
                            """, (str(tenant_id), str(user_id), str(doc_id), len(content),
                                  json.dumps({'filename': filename, 'source': 'zip_upload', 'zip_name': file.filename})))
                            
                            cur.execute("""
                                INSERT INTO platform.extraction_requests (
                                    id, request_id, document_id, tenant_id, file_path, file_name,
                                    mime_type, file_size_bytes, extraction_mode, priority, status,
                                    submitted_at, retry_count, max_retries, created_at
                                ) VALUES (gen_random_uuid(), gen_random_uuid(), %s, %s, %s, %s, %s, %s,
                                          'full', 'normal', 'pending', NOW(), 0, 3, NOW())
                            """, (str(doc_id), str(tenant_id), storage_path, filename,
                                  mime_type or 'application/octet-stream', len(content)))
                            
                            results.append({'filename': filename, 'status': 'queued', 'document_id': str(doc_id)})
                        
                        conn.commit()
        finally:
            os.remove(zip_path)
        
        queued = sum(1 for r in results if r['status'] == 'queued')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        duplicates = sum(1 for r in results if r['status'] == 'duplicate')
        
        return jsonify({
            'success': True,
            'summary': {'queued': queued, 'skipped': skipped, 'duplicates': duplicates, 'total': len(results)},
            'results': results
        })
        
    except zipfile.BadZipFile:
        return jsonify({'success': False, 'error': 'Invalid or corrupted ZIP file'}), 400
    except Exception as e:
        logger.error(f"ZIP upload failed: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500

@app.route('/dashboard/api-keys', methods=['GET'])
def dashboard_list_api_keys():
    """List API keys for authenticated user."""
    print("=== API KEYS LIST CALLED ===")
    print(f"Session: user_id={session.get('user_id')}, tenant_id={session.get('tenant_id')}")
    if not session.get('user_id') or not session.get('tenant_id'):
        print("=== API KEYS LIST FAILED: No auth ===")
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, key_prefix, scopes, created_at
                    FROM platform.api_keys
                    WHERE tenant_id = %s AND revoked_at IS NULL
                    ORDER BY created_at DESC
                """, (session['tenant_id'],))
                keys = cur.fetchall()
        
        return jsonify({
            'success': True,
            'keys': [{
                'id': str(key['id']),
                'name': key['name'],
                'key_prefix': key['key_prefix'],
                'scopes': key['scopes'],
                'created_at': key['created_at'].isoformat() if key['created_at'] else None
            } for key in keys]
        })
        
    except Exception as e:
        print(f"Dashboard list API keys failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Failed to load API keys'}), 500

@app.route('/dashboard/api-keys', methods=['POST'])
def dashboard_create_api_key():
    """Create a new API key for authenticated user."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import secrets
        import bcrypt
        from uuid import UUID, uuid4
        import psycopg2
        
        data = request.get_json() or {}
        key_name = data.get('name', 'Dashboard Key')
        scopes = data.get('scopes', ['read'])
        
        tenant_id = UUID(session['tenant_id'])
        user_id = UUID(session['user_id'])
        
        key_id = uuid4()
        raw_secret = secrets.token_urlsafe(32)
        key_prefix = f"cf_live_{secrets.token_hex(4)}"
        full_key = f"{key_prefix}_{raw_secret}"
        
        key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.api_keys (
                        id, tenant_id, created_by, name, key_prefix, 
                        key_hash, scopes, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (str(key_id), str(tenant_id), str(user_id), key_name,
                      key_prefix, key_hash, scopes))
                conn.commit()
        
        return jsonify({
            'success': True,
            'key_id': str(key_id),
            'api_key': full_key
        })
        
    except Exception as e:
        print(f"Dashboard create API key failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Failed to create API key'}), 500

@app.route('/dashboard/api-keys/<key_id>', methods=['DELETE'])
def dashboard_revoke_api_key(key_id):
    """Revoke an API key."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.api_keys
                    SET status = 'revoked'
                    WHERE id = %s AND tenant_id = %s
                """, (key_id, session['tenant_id']))
                conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Dashboard revoke API key failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to revoke API key'}), 500

@app.route('/dashboard/connectors', methods=['GET'])
def dashboard_list_connectors():
    """List source connectors for authenticated user."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, type, name, status, last_sync_at, 
                           documents_discovered, documents_processed, created_at
                    FROM platform.source_connectors
                    WHERE tenant_id = %s
                    ORDER BY created_at DESC
                """, (session['tenant_id'],))
                connectors = cur.fetchall()
        
        return jsonify({
            'success': True,
            'connectors': [{
                'id': str(c['id']),
                'type': c['type'],
                'name': c['name'],
                'status': c['status'],
                'last_sync_at': c['last_sync_at'].isoformat() if c['last_sync_at'] else None,
                'documents_discovered': c['documents_discovered'],
                'documents_processed': c['documents_processed'],
                'created_at': c['created_at'].isoformat() if c['created_at'] else None
            } for c in connectors]
        })
        
    except Exception as e:
        logger.error(f"Dashboard list connectors failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to load connectors'}), 500

@app.route('/dashboard/connectors', methods=['POST'])
def dashboard_create_connector():
    """Create a new source connector."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        from uuid import UUID, uuid4
        import psycopg2
        from platform_foundation.src.utils.encryption import get_encryption
        
        data = request.get_json() or {}
        connector_type = data.get('type')
        connector_name = data.get('name', 'Unnamed Connector')
        config = data.get('config', {})
        
        if connector_type not in ['s3', 'gdrive']:
            return jsonify({'success': False, 'error': 'Unsupported connector type'}), 400
        
        tenant_id = UUID(session['tenant_id'])
        connector_id = uuid4()
        
        encryption = get_encryption()
        encrypted_config = encryption.encrypt_config(config)
        
        if connector_type == 's3':
            from platform_foundation.src.connectors.s3_connector import S3Connector, S3Config
            s3_config = S3Config(
                access_key_id=config.get('access_key_id', ''),
                secret_access_key=config.get('secret_access_key', ''),
                bucket_name=config.get('bucket_name', ''),
                prefix=config.get('prefix', ''),
                region=config.get('region', 'us-east-1')
            )
            connector = S3Connector(s3_config)
            test_result = connector.test_connection()
            
            if not test_result.get('success'):
                return jsonify({'success': False, 'error': test_result.get('error', 'Connection failed')}), 400
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.source_connectors (
                        id, tenant_id, type, name, config, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, 'active', NOW())
                """, (str(connector_id), str(tenant_id), connector_type, 
                      connector_name, psycopg2.Binary(encrypted_config)))
                conn.commit()
        
        return jsonify({
            'success': True,
            'connector_id': str(connector_id),
            'name': connector_name,
            'type': connector_type
        })
        
    except Exception as e:
        logger.error(f"Dashboard create connector failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to create connector'}), 500

@app.route('/dashboard/connectors/<connector_id>/sync', methods=['POST'])
def dashboard_sync_connector(connector_id):
    """Trigger a sync for a connector."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        from uuid import UUID, uuid4
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import hashlib
        from platform_foundation.src.utils.encryption import get_encryption
        
        tenant_id = UUID(session['tenant_id'])
        user_id = UUID(session['user_id'])
        
        database_url = os.environ.get("DATABASE_URL")
        
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, type, name, config FROM platform.source_connectors
                    WHERE id = %s AND tenant_id = %s
                """, (connector_id, str(tenant_id)))
                connector = cur.fetchone()
                
                if not connector:
                    return jsonify({'success': False, 'error': 'Connector not found'}), 404
                
                job_id = uuid4()
                cur.execute("""
                    INSERT INTO platform.sync_jobs (id, connector_id, tenant_id, status, started_at)
                    VALUES (%s, %s, %s, 'running', NOW())
                """, (str(job_id), connector_id, str(tenant_id)))
                conn.commit()
                
                encryption = get_encryption()
                config = encryption.decrypt_config(bytes(connector['config']))
                
                if connector['type'] == 's3':
                    from platform_foundation.src.connectors.s3_connector import S3Connector, S3Config
                    s3_config = S3Config(
                        access_key_id=config.get('access_key_id', ''),
                        secret_access_key=config.get('secret_access_key', ''),
                        bucket_name=config.get('bucket_name', ''),
                        prefix=config.get('prefix', ''),
                        region=config.get('region', 'us-east-1')
                    )
                    source = S3Connector(s3_config)
                else:
                    cur.execute("""
                        UPDATE platform.sync_jobs SET status = 'failed', 
                        error_message = 'Unsupported connector type', completed_at = NOW()
                        WHERE id = %s
                    """, (str(job_id),))
                    conn.commit()
                    return jsonify({'success': False, 'error': 'Unsupported connector type'}), 400
                
                results = {'queued': 0, 'skipped': 0, 'duplicates': 0, 'failed': 0}
                files_list = list(source.discover_files(max_files=1000))
                
                cur.execute("""
                    UPDATE platform.sync_jobs SET files_total = %s WHERE id = %s
                """, (len(files_list), str(job_id)))
                conn.commit()
                
                for file_info in files_list:
                    try:
                        cur.execute("""
                            SELECT id FROM platform.documents 
                            WHERE tenant_id = %s AND source_connector_id = %s AND external_id = %s
                        """, (str(tenant_id), connector_id, file_info['external_id']))
                        
                        if cur.fetchone():
                            results['duplicates'] += 1
                            continue
                        
                        content = source.get_file_content(file_info['key'])
                        content_hash = hashlib.sha256(content).hexdigest()
                        
                        cur.execute("""
                            SELECT id FROM platform.documents 
                            WHERE tenant_id = %s AND content_hash = %s
                        """, (str(tenant_id), content_hash))
                        
                        if cur.fetchone():
                            results['duplicates'] += 1
                            continue
                        
                        doc_id = uuid4()
                        version = 1
                        storage_dir = f"./storage/tenants/{tenant_id}/documents/{doc_id}/v{version}"
                        os.makedirs(storage_dir, exist_ok=True)
                        storage_path = f"{storage_dir}/content"
                        
                        with open(storage_path, 'wb') as f:
                            f.write(content)
                        
                        cur.execute("""
                            INSERT INTO platform.documents (
                                id, tenant_id, name, original_filename, mime_type, storage_path,
                                size_bytes, current_version, status, source_connector_id,
                                external_id, content_hash, created_by, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', %s, %s, %s, %s, NOW(), NOW())
                        """, (str(doc_id), str(tenant_id), file_info['name'], file_info['name'], file_info['mime_type'],
                              storage_path, file_info['size'], version, connector_id,
                              file_info['external_id'], content_hash, str(user_id)))
                        
                        cur.execute("""
                            INSERT INTO platform.usage_events (
                                tenant_id, user_id, event_type, document_id, tokens_consumed, metadata, created_at
                            ) VALUES (%s, %s, 'upload', %s, %s, %s, NOW())
                        """, (str(tenant_id), str(user_id), str(doc_id), file_info['size'],
                              json.dumps({'filename': file_info['name'], 'source': 's3', 'connector_id': connector_id})))
                        
                        cur.execute("""
                            INSERT INTO platform.extraction_requests (
                                id, request_id, document_id, tenant_id, file_path, file_name,
                                mime_type, file_size_bytes, extraction_mode, priority, status,
                                submitted_at, retry_count, max_retries, created_at
                            ) VALUES (gen_random_uuid(), gen_random_uuid(), %s, %s, %s, %s, %s, %s,
                                      'full', 'normal', 'pending', NOW(), 0, 3, NOW())
                        """, (str(doc_id), str(tenant_id), storage_path, file_info['name'],
                              file_info['mime_type'], file_info['size']))
                        
                        results['queued'] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to sync file {file_info.get('name')}: {e}")
                        results['failed'] += 1
                
                cur.execute("""
                    UPDATE platform.sync_jobs 
                    SET status = 'completed', files_processed = %s, files_failed = %s,
                        files_skipped = %s, completed_at = NOW()
                    WHERE id = %s
                """, (results['queued'], results['failed'], 
                      results['skipped'] + results['duplicates'], str(job_id)))
                
                cur.execute("""
                    UPDATE platform.source_connectors
                    SET last_sync_at = NOW(), 
                        documents_discovered = documents_discovered + %s,
                        documents_processed = documents_processed + %s
                    WHERE id = %s
                """, (len(files_list), results['queued'], connector_id))
                
                conn.commit()
        
        return jsonify({
            'success': True,
            'job_id': str(job_id),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Dashboard sync connector failed: {e}")
        return jsonify({'success': False, 'error': 'Sync failed'}), 500

@app.route('/dashboard/connectors/<connector_id>', methods=['DELETE'])
def dashboard_delete_connector(connector_id):
    """Delete a source connector."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM platform.source_connectors
                    WHERE id = %s AND tenant_id = %s
                """, (connector_id, session['tenant_id']))
                conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Dashboard delete connector failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete connector'}), 500

@app.route('/dashboard/sync-jobs', methods=['GET'])
def dashboard_list_sync_jobs():
    """List recent sync jobs."""
    if not session.get('user_id') or not session.get('tenant_id'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.environ.get("DATABASE_URL")
        with psycopg2.connect(database_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT sj.id, sj.connector_id, sc.name as connector_name, sc.type as connector_type,
                           sj.status, sj.files_total, sj.files_processed, sj.files_failed,
                           sj.files_skipped, sj.started_at, sj.completed_at, sj.error_message
                    FROM platform.sync_jobs sj
                    LEFT JOIN platform.source_connectors sc ON sj.connector_id = sc.id
                    WHERE sj.tenant_id = %s
                    ORDER BY sj.started_at DESC
                    LIMIT 20
                """, (session['tenant_id'],))
                jobs = cur.fetchall()
        
        return jsonify({
            'success': True,
            'jobs': [{
                'id': str(j['id']),
                'connector_id': str(j['connector_id']) if j['connector_id'] else None,
                'connector_name': j['connector_name'],
                'connector_type': j['connector_type'],
                'status': j['status'],
                'files_total': j['files_total'],
                'files_processed': j['files_processed'],
                'files_failed': j['files_failed'],
                'files_skipped': j['files_skipped'],
                'started_at': j['started_at'].isoformat() if j['started_at'] else None,
                'completed_at': j['completed_at'].isoformat() if j['completed_at'] else None,
                'error_message': j['error_message']
            } for j in jobs]
        })
        
    except Exception as e:
        logger.error(f"Dashboard list sync jobs failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to load sync jobs'}), 500

@app.route('/evaluation')
def evaluation():
    # Redirect to SPA
    from flask import redirect
    return redirect('/app?page=evaluation')

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/internal/v1/health')
def internal_health():
    """
    Brain internal health endpoint for Platform Foundation.
    Returns component-level health status.
    """
    from src.context_foundry.models.schema import get_session
    import time
    
    start_time = time.time()
    components = {}
    overall_healthy = True
    
    try:
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        components['database'] = {'status': 'healthy', 'latency_ms': int((time.time() - start_time) * 1000)}
        session.close()
    except Exception as e:
        components['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    try:
        foundry = get_context_foundry()
        components['core'] = {'status': 'healthy' if foundry else 'unhealthy'}
        if not foundry:
            overall_healthy = False
    except Exception as e:
        components['core'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    components['extraction_worker'] = {'status': 'available'}
    components['query_endpoint'] = {'status': 'healthy'}
    
    return jsonify({
        'status': 'healthy' if overall_healthy else 'degraded',
        'version': '1.0.0',
        'components': components,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }), 200 if overall_healthy else 503

@app.route('/internal/v1/query', methods=['POST'])
def internal_query():
    """
    Brain internal query endpoint for Platform Foundation.
    Returns QueryResponse contract format.
    """
    import time
    from packages.interface_types.src import QueryRequest, QueryResponse, QueryType, QueryErrorCode
    from packages.interface_types.src.query import QueryError, TokensConsumed
    
    start_time = time.time()
    data = request.get_json() or {}
    
    try:
        query_request = QueryRequest(**data)
    except Exception as e:
        return jsonify({
            'success': False,
            'results': [],
            'total_count': 0,
            'tokens_consumed': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
            'duration_ms': int((time.time() - start_time) * 1000),
            'error': {'code': 'INVALID_QUERY', 'message': str(e)}
        }), 400
    
    try:
        # Create tenant-specific ContextFoundry instance
        from src.context_foundry.core import ContextFoundry
        foundry = ContextFoundry(tenant_id=query_request.tenant_id)
        
        if query_request.query_type == QueryType.SEMANTIC_SEARCH:
            result = foundry.query(query_request.query_text or "")
            
            # Handle aggregation queries specially
            if result.get('is_aggregation'):
                agg = result.get('aggregation', {})
                results = [{
                    'answer': result.get('answer', ''),
                    'is_aggregation': True,
                    'result_kind': agg.get('result_kind', 'UNKNOWN'),
                    'value': agg.get('value'),
                    'unit': agg.get('unit'),
                    'bounds': agg.get('bounds'),
                    'confidence': result.get('confidence', 0),
                    'assumptions': agg.get('assumptions', [])
                }]
                input_tokens = 50
                output_tokens = 30
            else:
                entities = result.get('context_bundle', {}).get('blast_radius_entities', [])
                results = [
                    {
                        'entity_id': e.get('id', ''),
                        'entity_type': e.get('type', ''),
                        'content': e,
                        'similarity_score': 0.8,
                        'source_document_id': e.get('source_document_id')
                    }
                    for e in entities[:query_request.max_results or 10]
                ]
                
                input_tokens = 100
                output_tokens = 50
            
        elif query_request.query_type == QueryType.VERIFY_STATEMENT:
            result = foundry.query(query_request.statement or "")
            
            verified = result.get('confidence', 0) > 0.7
            results = [{
                'verified': verified,
                'confidence': result.get('confidence', 0),
                'supporting_entities': [],
                'contradicting_entities': [],
                'explanation': result.get('answer', '')
            }]
            
            input_tokens = 150
            output_tokens = 100
            
        elif query_request.query_type == QueryType.GET_SCHEMA:
            from src.context_foundry.models.schema import get_session, OntologyType
            session = get_session()
            types = session.query(OntologyType).filter(
                OntologyType.state == 'ACTIVE'
            ).limit(50).all()
            
            results = [
                {
                    'entity_type': t.name,
                    'properties': [],
                    'relationships': []
                }
                for t in types
            ]
            session.close()
            
            input_tokens = 50
            output_tokens = 30
            
        else:
            results = []
            input_tokens = 20
            output_tokens = 10
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        response = {
            'success': True,
            'results': results,
            'total_count': len(results),
            'tokens_consumed': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens
            },
            'duration_ms': duration_ms
        }
        
        return jsonify(response)
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            'success': False,
            'results': [],
            'total_count': 0,
            'tokens_consumed': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
            'duration_ms': duration_ms,
            'error': {'code': 'INTERNAL_ERROR', 'message': str(e)}
        }), 500


mcp_server = None

def get_mcp_server():
    """Lazy-load MCPServer singleton."""
    global mcp_server
    if mcp_server is None:
        from platform_foundation.src.mcp_server import MCPServer
        mcp_server = MCPServer()
    return mcp_server


@app.route('/mcp/v1/tools/<tool_name>', methods=['POST'])
def mcp_tool_call(tool_name):
    """
    MCP tool call endpoint.
    
    Requires API key authentication via Authorization header:
    - Authorization: ApiKey cf_live_xxxxx
    - Authorization: cf_live_xxxxx
    """
    api_key = None
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('ApiKey '):
        api_key = auth_header[7:]
    elif auth_header.startswith('cf_'):
        api_key = auth_header
    
    if not api_key:
        return jsonify({
            'success': False,
            'error': {'code': 'MISSING_API_KEY', 'message': 'API key required in Authorization header'}
        }), 401
    
    arguments = request.get_json() or {}
    
    mcp = get_mcp_server()
    result = mcp.handle_tool_call(api_key, tool_name, arguments)
    
    status_code = 200
    if not result.get('success'):
        error_code = result.get('error', {}).get('code', '')
        if error_code in ['MISSING_API_KEY', 'INVALID_API_KEY', 'INVALID_API_KEY_FORMAT']:
            status_code = 401
        elif error_code == 'INSUFFICIENT_SCOPE':
            status_code = 403
        elif error_code in ['DAILY_QUOTA_EXCEEDED', 'MONTHLY_QUOTA_EXCEEDED']:
            status_code = 429
        elif error_code in ['NOT_FOUND', 'UNKNOWN_TOOL']:
            status_code = 404
        else:
            status_code = 400
    
    return jsonify(result), status_code


@app.route('/mcp/v1/resources', methods=['GET'])
def mcp_resource():
    """
    MCP resource request endpoint.
    
    Query params:
    - uri: Resource URI (e.g., context://schema/default, context://usage)
    """
    api_key = None
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('ApiKey '):
        api_key = auth_header[7:]
    elif auth_header.startswith('cf_'):
        api_key = auth_header
    
    if not api_key:
        return jsonify({
            'success': False,
            'error': {'code': 'MISSING_API_KEY', 'message': 'API key required'}
        }), 401
    
    resource_uri = request.args.get('uri', '')
    if not resource_uri:
        return jsonify({
            'success': False,
            'error': {'code': 'MISSING_URI', 'message': 'Resource URI required'}
        }), 400
    
    mcp = get_mcp_server()
    result = mcp.handle_resource_request(api_key, resource_uri)
    
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@app.route('/mcp/v1/tools', methods=['GET'])
def mcp_list_tools():
    """List available MCP tools."""
    tools = [
        {
            "name": "query_context",
            "description": "Query the knowledge graph for relevant context using semantic search",
            "parameters": {
                "query": {"type": "string", "description": "Natural language query", "required": True},
                "entity_types": {"type": "array", "description": "Filter by entity types"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
                "include_relationships": {"type": "boolean", "description": "Include relationships (default true)"}
            },
            "required_scope": "read"
        },
        {
            "name": "verify_statement",
            "description": "Verify a statement against the knowledge base",
            "parameters": {
                "statement": {"type": "string", "description": "Statement to verify", "required": True},
                "confidence_threshold": {"type": "number", "description": "Min confidence (default 0.7)"}
            },
            "required_scope": "read"
        },
        {
            "name": "ingest_document",
            "description": "Upload and queue a document for extraction",
            "parameters": {
                "filename": {"type": "string", "description": "Document filename", "required": True},
                "content": {"type": "string", "description": "Document content", "required": True},
                "mime_type": {"type": "string", "description": "MIME type (default text/plain)"},
                "priority": {"type": "string", "description": "Extraction priority (low, normal, high)"}
            },
            "required_scope": "write"
        },
        {
            "name": "get_document_status",
            "description": "Get document extraction status",
            "parameters": {
                "document_id": {"type": "string", "description": "Document UUID", "required": True}
            },
            "required_scope": "read"
        },
        {
            "name": "list_entity_types",
            "description": "List available entity types from ontology",
            "parameters": {},
            "required_scope": "read"
        }
    ]
    
    return jsonify({
        "tools": tools,
        "version": "1.0"
    })


@app.route('/mcp/v1/resources/list', methods=['GET'])
def mcp_list_resources():
    """List available MCP resources."""
    resources = [
        {
            "uri": "context://schema/{domain}",
            "description": "Get ontology schema for a domain",
            "parameters": {
                "domain": {"type": "string", "description": "Domain name (optional)"}
            }
        },
        {
            "uri": "context://usage",
            "description": "Get current quota usage for the tenant",
            "parameters": {}
        }
    ]
    
    return jsonify({
        "resources": resources,
        "version": "1.0"
    })


@app.route('/CommandCenter')
def command_center_redirect():
    """Redirect to SPA Command Center page."""
    from flask import redirect
    return redirect('/?page=command')

@app.route('/api/query', methods=['POST'])
def query():
    tenant_id, auth_result = validate_api_key()
    if auth_result and isinstance(auth_result, tuple):
        return auth_result
    
    if not tenant_id:
        return jsonify({'error': 'API key required. Use Authorization: Bearer <api_key>'}), 401
    
    data = request.get_json()
    query_text = data.get('query', '')
    as_of_date = data.get('as_of_date')  # Optional: ISO format date string for temporal queries
    
    if not query_text:
        return jsonify({'error': 'No query provided'}), 400
    
    try:
        foundry = get_context_foundry()
        result = foundry.query(query_text, as_of_date=as_of_date)
        
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
            'as_of_date': as_of_date,  # Echo back the temporal filter if used
            'query_log': {
                'query_id': result.get('query_log', {}).get('query_id', ''),
                'duration_seconds': result.get('query_log', {}).get('duration_seconds', 0)
            }
        }
        
        # Include traversal results for impact queries
        context_bundle = result.get('context_bundle', {})
        
        # Legacy: blast radius entities for backward compatibility
        if context_bundle.get('blast_radius_entities'):
            response['blast_radius_entities'] = context_bundle['blast_radius_entities']
            response['blast_radius_complete'] = context_bundle.get('blast_radius_complete', True)
        
        # NEW: Structured traversal result with frontier detection
        if context_bundle.get('traversal_result'):
            traversal = context_bundle['traversal_result']
            response['confirmed'] = traversal.get('confirmed', {})
            response['frontier'] = traversal.get('frontier', [])
            response['gaps_identified'] = traversal.get('gaps_identified', [])
        elif context_bundle.get('frontier'):
            # Fallback if traversal_result not present but frontier is
            response['frontier'] = context_bundle['frontier']
            response['gaps_identified'] = context_bundle.get('gaps_identified', [])
        
        # NEW: Speculative inferences (AI-inferred relationships) - always include
        speculative_inferences = context_bundle.get('speculative_inferences', [])
        response['speculative_inferences'] = speculative_inferences
        
        # Build tiered results summary for UI - always include for consistent frontend
        confirmed_entities = context_bundle.get('blast_radius_entities', [])
        frontier_nodes = context_bundle.get('frontier', [])
        
        tiered_results = {
            'confirmed': {
                'entities': confirmed_entities,
                'count': len(confirmed_entities)
            },
            'inferred': {
                'relationships': speculative_inferences,
                'count': len(speculative_inferences)
            },
            'boundaries': {
                'frontier_nodes': frontier_nodes,
                'count': len(frontier_nodes)
            }
        }
        response['tiered_results'] = tiered_results
        
        # Include aggregation data if present
        if result.get('is_aggregation'):
            response['is_aggregation'] = True
            response['aggregation_result'] = result.get('aggregation_result', {})
            response['counted_entities'] = result.get('counted_entities', [])
        
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

def _resolve_pronouns(query_text: str, history: list) -> str:
    """Resolve pronouns (he, she, they, it) using context from chat history.
    
    Looks for entities mentioned in previous assistant responses and replaces
    pronouns with the entity names for clearer queries.
    """
    if not history:
        return query_text
    
    import re
    
    pronouns = {
        'he': ['PERSON'],
        'him': ['PERSON'],
        'his': ['PERSON'],
        'she': ['PERSON'],
        'her': ['PERSON'],
        'they': ['PERSON', 'ORGANIZATION'],
        'them': ['PERSON', 'ORGANIZATION'],
        'their': ['PERSON', 'ORGANIZATION'],
        'it': ['ORGANIZATION', 'PROJECT', 'DOCUMENT'],
        'its': ['ORGANIZATION', 'PROJECT', 'DOCUMENT'],
    }
    
    query_lower = query_text.lower()
    has_pronoun = any(re.search(rf'\b{p}\b', query_lower) for p in pronouns.keys())
    
    if not has_pronoun:
        return query_text
    
    last_entities = []
    last_person = None
    last_org = None
    
    for msg in reversed(history):
        if msg.get('role') == 'assistant':
            entities = msg.get('entities', [])
            if entities:
                for ent in entities:
                    if isinstance(ent, dict):
                        ent_type = ent.get('type', '').upper()
                        ent_name = ent.get('name', '')
                    else:
                        ent_type = 'UNKNOWN'
                        ent_name = str(ent)
                    
                    if ent_type == 'PERSON' and not last_person:
                        last_person = ent_name
                    elif ent_type in ['ORGANIZATION', 'ORG', 'COMPANY'] and not last_org:
                        last_org = ent_name
                
                if last_person or last_org:
                    break
            
            content = msg.get('content', '')
            if not last_person:
                person_match = re.search(r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', content)
                if person_match:
                    last_person = person_match.group(1)
            
            if last_person:
                break
    
    resolved = query_text
    if last_person:
        for pronoun in ['he', 'him', 'his', 'she', 'her']:
            pattern = rf'\b{pronoun}\b'
            if re.search(pattern, resolved, re.IGNORECASE):
                resolved = re.sub(pattern, last_person, resolved, count=1, flags=re.IGNORECASE)
                break
    
    if last_org:
        for pronoun in ['it', 'its', 'they', 'them', 'their']:
            pattern = rf'\b{pronoun}\b'
            if re.search(pattern, resolved, re.IGNORECASE):
                resolved = re.sub(pattern, last_org, resolved, count=1, flags=re.IGNORECASE)
                break
    
    return resolved


@app.route('/api/vault/chat', methods=['POST'])
def vault_chat():
    """Session-based chat endpoint for vault view (no API key required).
    
    Uses HYBRID retrieval: Always searches both knowledge graph AND document chunks,
    combining structured relationships with document text for comprehensive answers.
    This ensures CF is at least as good as basic RAG, plus better for graph queries.
    """
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    # Get vault_id from request (authoritative) or fall back to session
    request_vault_id = data.get('vault_id')
    session_tenant_id = g.tenant_id or session.get('tenant_id')
    
    # Determine effective tenant_id with mismatch detection
    if request_vault_id:
        tenant_id = request_vault_id
        if session_tenant_id and request_vault_id != session_tenant_id:
            logger.warning(f"[VAULT_QUERY] TENANT MISMATCH DETECTED!")
            logger.warning(f"[VAULT_QUERY]   Request vault_id: {request_vault_id}")
            logger.warning(f"[VAULT_QUERY]   Session tenant_id: {session_tenant_id}")
            logger.warning(f"[VAULT_QUERY]   Using request vault_id as authoritative source")
            # Update session to match the vault being queried
            session['tenant_id'] = request_vault_id
            g.tenant_id = request_vault_id
    else:
        tenant_id = session_tenant_id
        logger.debug(f"[VAULT_QUERY] No vault_id in request, using session tenant: {tenant_id}")
    
    if not tenant_id:
        return jsonify({'error': 'No vault context'}), 400
    
    logger.info(f"[VAULT_QUERY] Effective tenant_id: {tenant_id}")
    
    query_text = data.get('query', '').strip()
    chat_history = data.get('history', [])
    
    if not query_text:
        return jsonify({'error': 'No query provided'}), 400
    
    resolved_query = _resolve_pronouns(query_text, chat_history)
    logger.info(f"[vault_chat] Original: {query_text!r} -> Resolved: {resolved_query!r}")
    
    # Tool agent mode (enabled by default, opt-out with ?agent=false)
    use_tool_agent = request.args.get('agent', 'true').lower() != 'false'
    debug_mode = request.args.get('debug', 'false').lower() == 'true'
    session_id = data.get('session_id')
    
    if use_tool_agent:
        try:
            from sqlalchemy import text
            from src.context_foundry.models.schema import set_tenant_context, get_session as get_db_session
            db_session = get_db_session()
            set_tenant_context(db_session, tenant_id)
            
            # Get vault name for context injection
            vault_context = None
            try:
                vault_row = db_session.execute(
                    text("SELECT name FROM platform.tenants WHERE id = :tid"),
                    {'tid': tenant_id}
                ).fetchone()
                if vault_row:
                    vault_context = vault_row[0]
                    logger.info(f"[TOOL_AGENT] Vault context: {vault_context}")
            except Exception as e:
                logger.warning(f"[TOOL_AGENT] Could not get vault name: {e}")
            
            # Initialize conversation store
            effective_session_id = session_id or 'default'
            logger.info(f"[TOOL_AGENT] session_id={effective_session_id}, query={query_text!r}, debug={debug_mode}")
            conv_store = ConversationStore(db_session, tenant_id, effective_session_id)
            
            # Resolve pronouns from conversation history
            resolved_query = conv_store.resolve_pronouns(query_text)
            logger.info(f"[TOOL_AGENT] Pronoun resolved: {query_text!r} -> {resolved_query!r}")
            
            # Get conversation history
            history = conv_store.get_history()
            logger.info(f"[TOOL_AGENT] Loaded {len(history)} messages from conversation history")
            for i, msg in enumerate(history[-4:]):
                logger.info(f"[TOOL_AGENT]   History[{i}]: {msg['role']}: {msg['content'][:100]}...")
            
            # Run tool agent with debug mode and vault context
            agent = ToolAgent(db_session, tenant_id)
            agent_result = agent.query(resolved_query, conversation_history=history, debug=debug_mode, vault_context=vault_context)
            
            # Store messages
            conv_store.add_message("user", query_text)
            
            # Use confidence and evidence from ToolAgent (computed via shared helpers)
            computed_confidence = agent_result.get('confidence', 0.5)
            evidence = agent_result.get('evidence', {})
            
            # Extract mentioned entities from evidence
            mentioned_entities = evidence.get('entity_names', []) if evidence else []
            source_documents = evidence.get('chunk_sources', []) if evidence else []
            
            # Also extract from sources field as fallback
            if not source_documents and agent_result.get('sources'):
                source_documents = agent_result['sources']
            
            logger.info(f"[CONFIDENCE] Using agent-computed confidence: {computed_confidence}")
            logger.info(f"[CONFIDENCE] Evidence: {evidence}")
            
            # === QA VERIFIER: Semantic check before returning answer ===
            # This may adjust the answer if verdict is poor
            qa_verdict_dict = agent_result.get('qa_verdict')
            
            if not qa_verdict_dict:
                try:
                    from src.context_foundry.agents.qa_verifier import AnswerVerifierAgent
                    from src.context_foundry.utils.response_helpers import build_qa_evidence, calculate_confidence
                    
                    verifier = AnswerVerifierAgent()
                    qa_verdict = verifier.verify_from_retrieval_result(
                        question=resolved_query,
                        answer=agent_result.get('answer', ''),
                        retrieval_result=agent_result.get('pipeline_result'),
                        tool_calls=agent_result.get('tool_calls', [])
                    )
                    
                    logger.info(f"[QA_VERIFIER] Verdict: {qa_verdict.status} - {qa_verdict.reason}")
                    
                    qa_verdict_dict = qa_verdict.to_dict()
                    agent_result['qa_verdict'] = qa_verdict_dict
                    
                    # Recalculate confidence using shared helper based on QA verdict
                    qa_evidence = build_qa_evidence(
                        retrieval_result=agent_result.get('pipeline_result'),
                        tool_calls=agent_result.get('tool_calls', [])
                    )
                    computed_confidence = calculate_confidence(
                        qa_verdict.status, qa_evidence, agent_result.get('answer', '')
                    )
                    
                    # Block answers that don't address the question
                    if qa_verdict.status in ('OFF_TOPIC', 'INSUFFICIENT', 'UNSUPPORTED', 'SUSPICIOUS'):
                        if qa_verdict.status == 'OFF_TOPIC':
                            agent_result['answer'] = "I found related information but it doesn't directly answer your question. Could you rephrase?"
                        elif qa_verdict.status == 'INSUFFICIENT':
                            agent_result['answer'] = f"I have partial information but cannot fully answer this. {qa_verdict.reason}"
                        elif qa_verdict.status == 'SUSPICIOUS':
                            agent_result['answer'] = "I couldn't find reliable data. Could you try rephrasing your question?"
                        else:  # UNSUPPORTED
                            agent_result['answer'] = "I don't have verified information to answer this question."
                        logger.info(f"[QA_VERIFIER] Answer replaced due to {qa_verdict.status} verdict")
                        
                except Exception as e:
                    logger.warning(f"[QA_VERIFIER] Verification failed, proceeding with original answer: {e}")
            # === END QA VERIFIER ===
            
            conv_store.add_message("assistant", agent_result['answer'], entities=mentioned_entities)
            
            db_session.close()
            
            logger.info(f"[TOOL_AGENT] Answer: {agent_result['answer'][:200]}...")
            logger.info(f"[TOOL_AGENT] Confidence: {computed_confidence}, Sources: {source_documents}")
            
            response_data = {
                'success': True,
                'answer': agent_result['answer'],
                'confidence': computed_confidence,
                'confidence_level': 'high' if computed_confidence >= 0.7 else ('medium' if computed_confidence >= 0.4 else 'low'),
                'tool_calls': agent_result.get('tool_calls', []),
                'iterations': agent_result.get('iterations', 0),
                'time_ms': agent_result.get('time_ms', 0),
                'mode': 'tool_agent',
                'mentioned_entities': mentioned_entities,
                'chunk_sources': [{'document': doc} for doc in source_documents]
            }
            
            # Include QA validation notes (caveats) if present
            if agent_result.get('qa_validation_notes'):
                response_data['qa_validation_notes'] = agent_result['qa_validation_notes']
            if agent_result.get('caveats'):
                response_data['caveats'] = agent_result['caveats']
            if agent_result.get('precalculated_value_found'):
                response_data['precalculated_value_found'] = agent_result['precalculated_value_found']
            
            # Include debug info if requested
            if debug_mode and 'debug' in agent_result:
                response_data['debug'] = agent_result['debug']
            
            return jsonify(response_data)
        except Exception as e:
            logger.error(f"Tool agent failed, falling back: {e}")
            # Fall through to existing logic
    
    try:
        from src.context_foundry.models.schema import set_tenant_context, get_session as get_db_session
        from src.context_foundry.core import ContextFoundry
        
        db_session = get_db_session()
        set_tenant_context(db_session, tenant_id)
        
        foundry = ContextFoundry(tenant_id=tenant_id, session=db_session)
        graph_result = foundry.query(resolved_query)
        
        # AGGREGATION RESULT: Return deterministic count directly (no LLM hybridization)
        if graph_result.get('is_aggregation'):
            db_session.close()
            agg = graph_result.get('aggregation_result', {})
            
            # Build entities list for frontend pronoun tracking
            mentioned_entities = []
            primary_entity = graph_result.get('primary_entity')
            if primary_entity:
                mentioned_entities.append(primary_entity)
            
            # Add counted entities (organizations, etc.)
            counted = graph_result.get('counted_entities', [])
            for ent in counted[:5]:
                mentioned_entities.append({
                    'id': ent.get('id'),
                    'name': ent.get('name'),
                    'type': ent.get('entity_type', 'ORGANIZATION')
                })
            
            return jsonify({
                'success': True,
                'answer': graph_result.get('answer', ''),
                'confidence': graph_result.get('confidence', 0.75),
                'confidence_level': graph_result.get('confidence_level', 'medium'),
                'evidence_chain': graph_result.get('evidence_chain', []),
                'retrieval_method': 'aggregation',
                'is_aggregation': True,
                'aggregation': {
                    'result_kind': agg.get('result_kind'),
                    'value': agg.get('value'),
                    'unit': agg.get('unit'),
                    'bounds': agg.get('bounds'),
                    'assumptions': agg.get('assumptions', [])
                },
                'counted_entities': counted,
                'mentioned_entities': mentioned_entities,
                'chunks_used': 0
            })
        
        graph_confidence = graph_result.get('confidence', 0)
        graph_answer = graph_result.get('answer', '')
        graph_evidence = graph_result.get('evidence_chain', [])
        
        chunk_result = _get_relevant_chunks(resolved_query, tenant_id, db_session)
        
        if chunk_result['chunks']:
            hybrid_answer = _generate_hybrid_answer(
                resolved_query, 
                graph_result, 
                chunk_result, 
                tenant_id,
                db_session
            )
            
            entity_citations = _get_entity_chunk_citations(resolved_query, tenant_id, db_session)
            
            combined_confidence = max(graph_confidence, chunk_result.get('relevance_score', 0.3))
            if graph_confidence > 0 and chunk_result['chunks']:
                combined_confidence = min(1.0, graph_confidence + 0.1)
            
            db_session.close()
            
            return jsonify({
                'success': True,
                'answer': hybrid_answer,
                'confidence': combined_confidence,
                'confidence_level': _confidence_level(combined_confidence),
                'evidence_chain': graph_evidence,
                'retrieval_method': 'hybrid',
                'graph_confidence': graph_confidence,
                'chunks_used': len(chunk_result['chunks']),
                'chunk_sources': chunk_result.get('sources', []),
                'entity_citations': entity_citations
            })
        
        db_session.close()
        
        return jsonify({
            'success': True,
            'answer': graph_answer,
            'confidence': graph_confidence,
            'confidence_level': graph_result.get('confidence_level', 'unknown'),
            'evidence_chain': graph_evidence,
            'retrieval_method': 'graph_only',
            'chunks_used': 0
        })
    except Exception as e:
        logger.error(f"Chat query failed: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


def _confidence_level(confidence: float) -> str:
    """Convert numeric confidence to categorical level."""
    if confidence >= 0.8:
        return 'high'
    elif confidence >= 0.5:
        return 'medium'
    else:
        return 'low'


def _get_relevant_chunks(query_text: str, tenant_id: str, db_session) -> dict:
    """Search document chunks for relevant text.
    
    Uses keyword ranking: chunks matching more query words rank higher.
    Filters out stop words to focus on meaningful terms.
    Requires at least 1 non-stop keyword to match.
    
    Returns dict with 'chunks' list and 'sources' list.
    """
    from sqlalchemy import text
    import re
    
    try:
        query_lower = query_text.lower()
        query_lower = re.sub(r'[^\w\s]', '', query_lower)
        stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'what', 'where', 'when', 'who', 'how', 'why', 'was', 'were', 'are', 'has', 'have', 'does', 'do', 'did', 'from', 'that', 'this', 'can', 'will', 'would', 'could', 'should', 'been', 'being', 'had', 'having', 'they', 'them', 'their', 'you', 'your', 'its', 'just', 'also', 'than', 'into', 'about', 'some', 'other', 'such', 'only', 'over', 'very', 'any', 'all', 'most', 'then', 'more', 'own'}
        query_words = [w for w in query_lower.split() if len(w) > 2 and w not in stop_words]
        
        if not query_words:
            query_words = [w for w in query_lower.split() if len(w) > 2][:3]
        
        if not query_words:
            return {'chunks': [], 'sources': [], 'relevance_score': 0}
        
        like_conditions = " OR ".join(
            f"LOWER(dc.text) LIKE '%' || :word{i} || '%'" for i in range(len(query_words))
        )
        
        match_count_expr = " + ".join(
            f"CASE WHEN LOWER(dc.text) LIKE '%' || :word{i} || '%' THEN 1 ELSE 0 END" for i in range(len(query_words))
        )
        
        full_phrase = ' '.join(query_words)
        phrase_underscore = '_'.join(query_words)
        
        all_words_in_title = " AND ".join(f"LOWER(d.name) LIKE '%' || :word{i} || '%'" for i in range(len(query_words)))
        
        sql = text(f"""
            SELECT 
                dc.id as chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.text,
                d.name as document_title,
                d.mime_type as doc_type,
                ({match_count_expr}) as match_count,
                CASE WHEN LOWER(dc.text) LIKE '%' || :full_phrase || '%' THEN 10 ELSE 0 END as phrase_bonus,
                CASE 
                    WHEN LOWER(d.name) LIKE '%' || :full_phrase || '%' THEN 20
                    WHEN LOWER(d.name) LIKE '%' || :phrase_underscore || '%' THEN 20
                    WHEN ({all_words_in_title}) THEN 15
                    ELSE 0 
                END as title_bonus
            FROM document_chunks dc
            JOIN platform.documents d ON dc.document_id = d.id
            WHERE dc.tenant_id = :tenant_id
            AND ({like_conditions})
            ORDER BY title_bonus DESC, phrase_bonus DESC, match_count DESC, dc.chunk_index
            LIMIT 8
        """)
        
        params = {'tenant_id': tenant_id, 'full_phrase': full_phrase, 'phrase_underscore': phrase_underscore}
        for i, word in enumerate(query_words):
            params[f'word{i}'] = word
        
        rows = db_session.execute(sql, params).fetchall()
        
        if not rows:
            return {'chunks': [], 'sources': [], 'relevance_score': 0}
        
        chunks = []
        sources = []
        total_match_count = 0
        max_possible_matches = len(query_words)
        
        for row in rows:
            chunk_text = row.text[:1200] if len(row.text) > 1200 else row.text
            total_match_count += row.match_count
            chunks.append({
                'text': chunk_text,
                'document': row.document_title,
                'chunk_index': row.chunk_index,
                'match_count': row.match_count
            })
            if row.document_title not in [s['document'] for s in sources]:
                sources.append({
                    'document': row.document_title,
                    'doc_type': row.doc_type
                })
        
        avg_match_ratio = total_match_count / (len(rows) * max_possible_matches) if rows and max_possible_matches > 0 else 0
        relevance_score = min(0.7, 0.2 + (avg_match_ratio * 0.4) + (min(len(rows), 5) * 0.05))
        
        return {
            'chunks': chunks,
            'sources': sources,
            'relevance_score': relevance_score,
            'query_words': query_words
        }
        
    except Exception as e:
        logger.warning(f"Chunk search failed: {e}")
        return {'chunks': [], 'sources': [], 'relevance_score': 0}


def _get_entity_chunk_citations(query_text: str, tenant_id: str, db_session) -> list:
    """Fetch entities matching query with their source chunk citations.
    
    Returns entities with provenance: which chunk/document they came from.
    Normalizes query terms: lowercase, strips punctuation, filters stop words.
    """
    from sqlalchemy import text as sql_text
    import re
    
    try:
        query_lower = query_text.lower()
        query_lower = re.sub(r'[^\w\s]', '', query_lower)
        stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'what', 'where', 'when', 'who', 'how', 'why', 'was', 'were', 'are', 'has', 'have', 'does', 'do', 'did', 'from', 'that', 'this', 'can', 'will'}
        query_words = [w for w in query_lower.split() if len(w) > 2 and w not in stop_words]
        if not query_words:
            return []
        
        like_conditions = " OR ".join(
            f"LOWER(e.name) LIKE '%' || :word{i} || '%'" for i in range(len(query_words))
        )
        
        sql = sql_text(f"""
            SELECT e.name, e.entity_type, e.source_chunk_id::text, d.name as doc_name,
                   dc.chunk_index, LEFT(dc.text, 200) as chunk_preview
            FROM entities e
            LEFT JOIN platform.documents d ON e.source_document_id = d.id::text
            LEFT JOIN document_chunks dc ON e.source_chunk_id = dc.id
            WHERE e.tenant_id = :tenant_id
            AND e.source_chunk_id IS NOT NULL
            AND ({like_conditions})
            ORDER BY e.name
            LIMIT 10
        """)
        
        params = {'tenant_id': tenant_id}
        for i, word in enumerate(query_words):
            params[f'word{i}'] = word
        
        rows = db_session.execute(sql, params).fetchall()
        
        return [{
            'entity': row[0],
            'type': row[1],
            'chunk_id': row[2][:8] if row[2] else None,
            'document': row[3],
            'chunk_index': row[4],
            'chunk_preview': row[5]
        } for row in rows]
    except Exception as e:
        logger.warning(f"Entity-chunk citation fetch failed: {e}")
        return []


def _generate_hybrid_answer(query_text: str, graph_result: dict, chunk_result: dict, tenant_id: str, db_session=None) -> str:
    """Generate answer using both graph data and document chunks.
    
    LLM sees structured graph data AND relevant document text.
    For job/position queries, fetches ALL relationships from database.
    Caps chunk context to prevent token overflow.
    Includes entity-chunk citations for provenance.
    """
    import os
    import re
    from openai import OpenAI
    from sqlalchemy import text as sql_text
    
    try:
        graph_answer = graph_result.get('answer', '')
        graph_evidence = graph_result.get('evidence_chain', [])
        graph_confidence = graph_result.get('confidence', 0)
        
        graph_context = ""
        
        query_lower = query_text.lower()
        is_job_query = any(w in query_lower for w in ['job', 'jobs', 'work', 'worked', 'position', 'positions', 'role', 'roles', 'career', 'employment', 'employed'])
        
        if is_job_query and db_session:
            # Skip common question words when looking for person names
            skip_words = {'what', 'how', 'who', 'where', 'when', 'which', 'why', 'the', 'a', 'an', 'is', 'are', 'was', 'were', 'did', 'does', 'do', 'has', 'have', 'had'}
            person_matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query_text)
            person_name = None
            for match in person_matches:
                if match.lower() not in skip_words:
                    person_name = match
                    break
            
            if not person_name:
                words = [w for w in query_text.split() if len(w) > 2 and w.lower() not in {'what', 'jobs', 'has', 'done', 'did', 'does', 'the', 'all', 'roles', 'positions'}]
                person_name = words[0] if words else None
            
            if person_name:
                job_sql = sql_text("""
                    SELECT r.relationship_type, e2.name as target
                    FROM relationships r
                    JOIN entities e1 ON r.source_id = e1.id
                    JOIN entities e2 ON r.target_id = e2.id
                    WHERE r.tenant_id = :tenant_id
                    AND LOWER(e1.name) LIKE :person_pattern
                    AND r.relationship_type IN ('HOLDS_POSITION', 'HELD_POSITION', 'HOLD_POSITION', 'WORKED_AT', 'EMPLOYED_BY', 'EMPLOYED_AT')
                    ORDER BY r.relationship_type, e2.name
                """)
                job_rows = db_session.execute(job_sql, {
                    'tenant_id': tenant_id, 
                    'person_pattern': f'%{person_name.lower()}%'
                }).fetchall()
                
                if job_rows:
                    positions = [r.target for r in job_rows if r.relationship_type in ('HOLDS_POSITION', 'HELD_POSITION', 'HOLD_POSITION')]
                    companies = [r.target for r in job_rows if r.relationship_type in ('WORKED_AT', 'EMPLOYED_BY', 'EMPLOYED_AT')]
                    
                    lines = []
                    if positions:
                        lines.append(f"Positions held: {', '.join(positions)}")
                    if companies:
                        lines.append(f"Companies worked at: {', '.join(companies)}")
                    graph_context = "\n".join(lines)
                    graph_confidence = max(graph_confidence, 0.5)
        
        if not graph_context and graph_confidence >= 0.15 and graph_evidence:
            evidence_lines = []
            for ev in graph_evidence[:10]:
                if isinstance(ev, dict):
                    evidence_lines.append(f"- {ev.get('source', '')} {ev.get('relation', '')} {ev.get('target', '')}")
                else:
                    evidence_lines.append(f"- {ev}")
            graph_context = "\n".join(evidence_lines)
        
        entity_citations = []
        if db_session:
            entity_citations = _get_entity_chunk_citations(query_text, tenant_id, db_session)
        
        entity_context = ""
        if entity_citations:
            entity_lines = []
            for ec in entity_citations[:6]:
                line = f"- {ec['entity']} ({ec['type']}) from '{ec['document']}' chunk {ec['chunk_index']}"
                entity_lines.append(line)
            entity_context = "\n".join(entity_lines)
        
        chunks = chunk_result.get('chunks', [])[:4]
        chunk_context = ""
        total_chars = 0
        max_chunk_chars = 4000
        for chunk in chunks:
            chunk_text = chunk.get('text', '')[:800]
            if total_chars + len(chunk_text) > max_chunk_chars:
                break
            chunk_context += f"[Source: {chunk['document']}]\n{chunk_text}\n\n---\n\n"
            total_chars += len(chunk_text)
        
        chunk_relevance = chunk_result.get('relevance_score', 0)
        
        client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
        
        system_prompt = """You are a helpful assistant that answers questions using both structured knowledge graph data AND document text excerpts.

RULES:
- ONLY use information from the provided sources (graph data and documents)
- If graph has structured relationships, cite them as "[Graph: relationship]"
- If documents have relevant text, cite them as "[Source: document name]"
- If BOTH sources have info, combine them for a complete answer
- If neither source has the answer, say "I don't have enough information to answer this."
- For enumeration questions (roles, jobs, positions, companies), list ALL items from the graph data - do NOT summarize or group them
- Use bullet points for lists of items"""

        no_graph = "No relevant graph relationships found."
        no_chunks = "No relevant document excerpts found."
        no_entities = ""
        
        entity_section = ""
        if entity_context:
            entity_section = f"""
EXTRACTED ENTITIES (with source provenance):
{entity_context}
"""
        
        user_prompt = f"""Answer this question using the sources below.

QUESTION: {query_text}

KNOWLEDGE GRAPH DATA (structured relationships, confidence: {graph_confidence:.2f}):
{graph_context if graph_context else no_graph}
{entity_section}
DOCUMENT EXCERPTS (text search, relevance: {chunk_relevance:.2f}):
{chunk_context.strip() if chunk_context.strip() else no_chunks}

Provide a concise, accurate answer with citations."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=600
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.warning(f"Hybrid answer generation failed: {e}")
        return graph_result.get('answer', 'Unable to generate answer.')


def _try_rag_fallback(query_text: str, tenant_id: str, db_session) -> dict:
    """
    RAG fallback: Semantic search over document chunks and answer from text.
    
    Returns a result dict with answer, confidence, etc. or None if no relevant chunks found.
    """
    import os
    from openai import OpenAI
    from sqlalchemy import text
    
    try:
        query_lower = query_text.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        
        if not query_words:
            return None
        
        like_conditions = " OR ".join(
            f"LOWER(dc.text) LIKE '%' || :word{i} || '%'" for i in range(len(query_words))
        )
        
        sql = text(f"""
            SELECT 
                dc.id as chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.text,
                dc.chunk_metadata,
                d.title as document_title,
                d.doc_type
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.tenant_id = :tenant_id
            AND ({like_conditions})
            ORDER BY dc.chunk_index
            LIMIT 10
        """)
        
        params = {'tenant_id': tenant_id}
        for i, word in enumerate(query_words):
            params[f'word{i}'] = word
        
        rows = db_session.execute(sql, params).fetchall()
        
        if not rows:
            return None
        
        chunks_text = []
        sources = []
        for row in rows:
            chunk_text = row.text[:1500] if len(row.text) > 1500 else row.text
            chunks_text.append(f"[{row.document_title}]: {chunk_text}")
            sources.append({
                'document': row.document_title,
                'chunk_index': row.chunk_index
            })
        
        context = "\n\n---\n\n".join(chunks_text)
        
        client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful assistant that answers questions based on provided document excerpts.
                    
RULES:
- ONLY use information from the provided documents
- If the documents don't contain the answer, say so
- Quote relevant parts when possible
- Be concise but complete"""
                },
                {
                    "role": "user",
                    "content": f"""Based on these document excerpts, answer the question.

DOCUMENTS:
{context}

QUESTION: {query_text}

Provide a helpful answer based on the documents above."""
                }
            ],
            temperature=0.0,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        
        confidence = min(0.7, 0.4 + (len(rows) * 0.05))
        
        return {
            'success': True,
            'answer': answer,
            'confidence': confidence,
            'confidence_level': 'medium' if confidence >= 0.5 else 'low',
            'evidence_chain': sources[:5],
            'rag_chunks_used': len(rows)
        }
        
    except Exception as e:
        logger.warning(f"RAG fallback failed: {e}")
        return None


@app.route('/api/v1/health')
def api_health():
    """Health check endpoint for system status monitoring."""
    from datetime import datetime, timezone
    from sqlalchemy import text
    from src.context_foundry.models.schema import get_session
    
    session = get_session()
    try:
        # Check database connectivity
        session.execute(text("SELECT 1"))
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    finally:
        session.close()
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/command-center/data')
def command_center_data():
    """API endpoint for AJAX refresh of Command Center dashboard."""
    from datetime import datetime, timedelta
    from sqlalchemy import text
    from src.context_foundry.models.schema import get_session, Entity, Relationship, Document, Rule, LifecycleState, GardenerLog
    from flask import session as flask_session
    
    db_session = get_session()
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_10min = now - timedelta(minutes=10)
    
    # Set RLS tenant context for multi-tenant isolation
    tenant_id = flask_session.get('tenant_id')
    if tenant_id:
        db_session.execute(text("SELECT platform.set_current_tenant(:tid)"), {'tid': str(tenant_id)})
    
    try:
        # Perception quadrant
        docs_total = db_session.query(Document).count()
        entities_total = db_session.query(Entity).count()
        rels_total = db_session.query(Relationship).count()
        
        perception = {
            'documents_total': docs_total,
            'documents_24h': db_session.query(Document).filter(Document.created_at >= last_24h).count(),
            'entities_extracted': entities_total,
            'entities_24h': db_session.query(Entity).filter(Entity.created_at >= last_24h).count(),
            'relationships_extracted': rels_total,
            'relationships_24h': db_session.query(Relationship).filter(Relationship.created_at >= last_24h).count(),
            'extractors': [
                {'name': 'EntityExtractor', 'status': 'IDLE', 'last_run': 'On demand'},
                {'name': 'RelationExtractor', 'status': 'IDLE', 'last_run': 'On demand'},
                {'name': 'ConstrainedExtractor', 'status': 'IDLE', 'last_run': 'On demand'},
            ],
        }
        
        # Memory quadrant
        try:
            rules_count = db_session.query(Rule).filter(Rule.is_active == True).count()
        except:
            db_session.rollback()
            rules_count = 0
            
        try:
            avg_conf = db_session.execute(text("SELECT COALESCE(AVG(confidence), 0) FROM entities WHERE lifecycle_state = 'TRUSTED'")).scalar() or 0
        except:
            db_session.rollback()
            avg_conf = 0
            
        try:
            orphan_entities = db_session.execute(text("""
                SELECT COUNT(*) FROM entities e
                WHERE NOT EXISTS (SELECT 1 FROM relationships r WHERE r.source_id = e.id OR r.target_id = e.id)
            """)).scalar() or 0
        except:
            db_session.rollback()
            orphan_entities = 0
            
        try:
            pending_conflicts = db_session.execute(text("SELECT COUNT(*) FROM conflicts WHERE status = 'PENDING'")).scalar() or 0
        except:
            db_session.rollback()
            pending_conflicts = 0
        
        memory = {
            'entities_staging': db_session.query(Entity).filter(Entity.lifecycle_state == LifecycleState.STAGING).count(),
            'entities_trusted': db_session.query(Entity).filter(Entity.lifecycle_state == LifecycleState.TRUSTED).count(),
            'entities_archived': db_session.query(Entity).filter(Entity.lifecycle_state == LifecycleState.ARCHIVED).count(),
            'total_nodes': entities_total,
            'total_edges': rels_total,
            'documents_indexed': docs_total,
            'embeddings_count': docs_total,
            'rules_count': rules_count,
            'avg_confidence': float(avg_conf),
            'orphan_entities': orphan_entities,
            'pending_conflicts': pending_conflicts,
        }
        
        # Agents quadrant
        gardener_last = db_session.query(GardenerLog).order_by(GardenerLog.created_at.desc()).first()
        gardener_status = 'IDLE'
        gardener_last_action = 'Never'
        if gardener_last:
            if gardener_last.created_at >= last_10min:
                gardener_status = 'ACTIVE'
            gardener_last_action = gardener_last.created_at.strftime('%H:%M:%S')
        
        try:
            orphan_pending = db_session.execute(text("SELECT COUNT(*) FROM context.orphan_patterns WHERE status = 'ACTIVE'")).scalar() or 0
            approval_pending = db_session.execute(text("SELECT COUNT(*) FROM ontology.approval_requests WHERE status = 'PENDING'")).scalar() or 0
        except:
            db_session.rollback()
            orphan_pending = 0
            approval_pending = 0
        
        agent_list = [
            {'name': 'GraphBuilder', 'phase': 'Ingest', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'EntityExtractor', 'phase': 'Perceive', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'RelationExtractor', 'phase': 'Perceive', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'GardenerAgent', 'phase': 'Memory', 'status': gardener_status, 'last_run_time': gardener_last_action},
            {'name': 'IdentityResolver', 'phase': 'Memory', 'status': 'SCHEDULED', 'last_run_time': gardener_last_action},
            {'name': 'RetrievalAgent', 'phase': 'Reason', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'ReasoningAgent', 'phase': 'Reason', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'BundleBuilder', 'phase': 'Express', 'status': 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'OrphanDetector', 'phase': 'Learn', 'status': 'ACTIVE' if orphan_pending > 0 else 'IDLE', 'last_run_time': 'N/A'},
            {'name': 'ApprovalManager', 'phase': 'Learn', 'status': 'ACTIVE' if approval_pending > 0 else 'IDLE', 'last_run_time': 'N/A'},
        ]
        
        gardener_stats = {
            'last_cycle': gardener_last_action,
            'promoted': db_session.execute(text("SELECT COUNT(*) FROM gardener_logs WHERE action_type = 'PROMOTE' AND created_at >= :since"), {'since': last_24h}).scalar() or 0,
            'demoted': db_session.execute(text("SELECT COUNT(*) FROM gardener_logs WHERE action_type IN ('DEMOTE', 'ARCHIVE') AND created_at >= :since"), {'since': last_24h}).scalar() or 0,
            'conflicts': db_session.execute(text("SELECT COUNT(*) FROM gardener_logs WHERE action_type = 'RESOLVE_CONFLICT' AND created_at >= :since"), {'since': last_24h}).scalar() or 0,
        }
        
        # Context quadrant
        try:
            type_counts = db_session.execute(text("SELECT status, COUNT(*) FROM ontology.types GROUP BY status")).fetchall()
            type_status_map = {row[0]: row[1] for row in type_counts}
        except:
            db_session.rollback()
            type_status_map = {}
            
        try:
            orphans_detected = db_session.execute(text("SELECT COUNT(*) FROM context.orphan_patterns")).scalar() or 0
            orphans_surfaced = db_session.execute(text("SELECT COUNT(*) FROM context.orphan_patterns WHERE frequency >= 10")).scalar() or 0
            types_promoted = db_session.execute(text("SELECT COUNT(*) FROM context.orphan_patterns WHERE status = 'RESOLVED'")).scalar() or 0
        except:
            db_session.rollback()
            orphans_detected = orphans_surfaced = types_promoted = 0
            
        # Approval queue
        approval_queue = []
        try:
            pending_requests = db_session.execute(text("""
                SELECT ar.id, t.type_name, ar.assigned_level, ar.sla_deadline, ar.created_at
                FROM ontology.approval_requests ar
                JOIN ontology.types t ON ar.target_id = t.id
                WHERE ar.status = 'PENDING'
                ORDER BY ar.sla_deadline ASC
                LIMIT 5
            """)).fetchall()
            
            for req in pending_requests:
                deadline, created = req[3], req[4]
                if deadline and created:
                    remaining = deadline - now
                    hours_left = remaining.total_seconds() / 3600
                    if hours_left < 0:
                        sla_remaining, sla_class = 'OVERDUE', 'sla-red'
                    elif hours_left < 24:
                        sla_remaining, sla_class = f'{int(hours_left)}h left', 'sla-yellow' if hours_left < 12 else 'sla-green'
                    else:
                        sla_remaining, sla_class = f'{int(hours_left/24)}d left', 'sla-green'
                else:
                    sla_remaining, sla_class = 'No deadline', 'sla-green'
                approval_queue.append({'type_name': req[1], 'level': f'L{req[2]}', 'sla_remaining': sla_remaining, 'sla_class': sla_class})
        except:
            db_session.rollback()
        
        context = {
            'orphans_detected': orphans_detected,
            'orphans_surfaced': orphans_surfaced,
            'types_promoted': types_promoted,
            'types_active': type_status_map.get('ACTIVE', 0),
            'types_proposed': type_status_map.get('PROPOSED', 0),
            'types_approved': type_status_map.get('APPROVED', 0),
            'types_deprecated': type_status_map.get('DEPRECATED', 0),
            'pending_approvals': len(approval_queue),
            'approval_queue': approval_queue,
        }
        
        # Message bus footer
        try:
            recent_events = db_session.execute(text("""
                SELECT event_type, source_agent, created_at
                FROM shared.message_queue
                ORDER BY created_at DESC
                LIMIT 10
            """)).fetchall()
            event_list = [{'type': ev[0], 'source': ev[1], 'time': ev[2].strftime('%H:%M:%S') if ev[2] else ''} for ev in recent_events]
        except:
            db_session.rollback()
            event_list = []
            
        try:
            dead_letter = db_session.execute(text("SELECT COUNT(*) FROM shared.dead_letter_queue")).scalar() or 0
        except:
            db_session.rollback()
            dead_letter = 0
        
        try:
            events_per_min = db_session.execute(text("SELECT COUNT(*) FROM shared.message_queue WHERE created_at >= :since"), {'since': now - timedelta(minutes=1)}).scalar() or 0
        except:
            db_session.rollback()
            events_per_min = 0
            
        try:
            total_events = db_session.execute(text("SELECT COUNT(*) FROM shared.message_queue")).scalar() or 0
        except:
            db_session.rollback()
            total_events = 0
        
        message_bus = {
            'dead_letter': dead_letter,
            'events_per_minute': events_per_min,
            'total_events': total_events,
            'recent_events': event_list,
        }
        
        return jsonify({
            'success': True,
            'last_updated': now.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'perception': perception,
            'memory': memory,
            'agents': {'agent_list': agent_list, 'gardener': gardener_stats},
            'context': context,
            'message_bus': message_bus,
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db_session.close()


@app.route('/api/knowledge/date-range')
def knowledge_date_range():
    """Get the temporal range of knowledge for timeline slider."""
    from src.context_foundry.models.schema import get_session, Entity
    from sqlalchemy import func, text
    from datetime import datetime, timezone
    
    session = get_session()
    set_tenant_on_session(session, g.tenant_id)
    try:
        result = session.execute(
            text("""
                SELECT 
                    MIN(valid_from) as earliest,
                    MAX(valid_from) as latest
                FROM public.entities
            """)
        ).fetchone()
        
        now = datetime.now(timezone.utc)
        earliest = result[0] if result and result[0] else now.replace(tzinfo=None)
        latest = result[1] if result and result[1] else now.replace(tzinfo=None)
        
        # Format dates consistently - naive datetimes get 'Z' appended
        def format_iso(dt):
            if dt is None:
                return None
            if dt.tzinfo is not None:
                return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
            return dt.isoformat() + 'Z'
        
        return jsonify({
            'success': True,
            'earliest': format_iso(earliest),
            'latest': format_iso(latest),
            'today': format_iso(now)
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/graph/visualization')
def graph_visualization():
    """Get graph data for dynamic visualization.
    
    Query parameters:
    - lifecycle_state: STAGING, TRUSTED, ARCHIVED, or 'all' (default: 'all')
    - entity_type: Filter by entity type (e.g., SERVICE, TEAM, PERSON)
    - limit: Maximum number of entities to return (default: 100)
    - as_of_date: ISO date string for temporal filtering (optional)
    """
    from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
    from datetime import datetime
    from sqlalchemy import or_
    
    # CRITICAL: Ensure tenant context is set for RLS isolation
    tenant_id = g.tenant_id or session.get('tenant_id')
    if not tenant_id:
        logger.warning("[GRAPH_VIZ] No tenant context - returning 401")
        return jsonify({'success': False, 'error': 'No vault context - please select a vault first', 'nodes': [], 'edges': []}), 401
    
    lifecycle_filter = request.args.get('lifecycle_state', 'all')
    entity_type_filter = request.args.get('entity_type', None)
    limit = int(request.args.get('limit', 100))
    as_of_date_str = request.args.get('as_of_date', None)
    
    as_of_date = None
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d')
            except ValueError:
                pass
    
    db_session = get_session()
    set_tenant_on_session(db_session, tenant_id)
    logger.info(f"[GRAPH_VIZ] tenant_id={tenant_id}, lifecycle={lifecycle_filter}, limit={limit}")
    try:
        entity_query = db_session.query(Entity)
        
        if as_of_date:
            entity_query = entity_query.filter(
                Entity.valid_from <= as_of_date,
                or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
            )
        else:
            entity_query = entity_query.filter(Entity.valid_to.is_(None))
        
        if lifecycle_filter != 'all':
            try:
                state = LifecycleState(lifecycle_filter)
                entity_query = entity_query.filter(Entity.lifecycle_state == state)
            except ValueError:
                pass
        
        if entity_type_filter:
            entity_query = entity_query.filter(Entity.entity_type == entity_type_filter)
        
        entities = entity_query.order_by(Entity.confidence.desc()).limit(limit).all()
        entity_ids = {e.id for e in entities}
        
        rel_query = db_session.query(Relationship).filter(
            Relationship.source_id.in_(entity_ids),
            Relationship.target_id.in_(entity_ids)
        )
        
        if as_of_date:
            rel_query = rel_query.filter(
                Relationship.valid_from <= as_of_date,
                or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
            )
        else:
            rel_query = rel_query.filter(Relationship.valid_to.is_(None))
        
        if lifecycle_filter != 'all':
            try:
                state = LifecycleState(lifecycle_filter)
                rel_query = rel_query.filter(Relationship.lifecycle_state == state)
            except ValueError:
                pass
        
        relationships = rel_query.all()
        
        nodes = []
        for e in entities:
            node_data = {
                'id': str(e.id),
                'name': e.name,
                'type': e.entity_type,
                'lifecycle_state': e.lifecycle_state.value if e.lifecycle_state else 'STAGING',
                'confidence': e.confidence or 0.5,
                'validation_status': e.validation_status.value if e.validation_status else 'PENDING',
                'valid_from': e.valid_from.isoformat() if e.valid_from else None,
                'valid_to': e.valid_to.isoformat() if e.valid_to else None,
                'is_superseded': e.superseded_by is not None
            }
            nodes.append(node_data)
        
        edges = []
        for r in relationships:
            edges.append({
                'id': str(r.id),
                'source': str(r.source_id),
                'target': str(r.target_id),
                'type': r.relationship_type,
                'lifecycle_state': r.lifecycle_state.value if r.lifecycle_state else 'STAGING',
                'confidence': r.confidence or 0.5
            })
        
        state_counts = {}
        for state in LifecycleState:
            count_query = db_session.query(Entity).filter(Entity.lifecycle_state == state)
            if as_of_date:
                count_query = count_query.filter(
                    Entity.valid_from <= as_of_date,
                    or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
                )
            else:
                count_query = count_query.filter(Entity.valid_to.is_(None))
            state_counts[state.value] = count_query.count()
        
        logger.info(f"[GRAPH_VIZ] Returning {len(nodes)} nodes, {len(edges)} edges for tenant {tenant_id}")
        return jsonify({
            'success': True,
            'nodes': nodes,
            'edges': edges,
            'as_of_date': as_of_date_str,
            'is_historical': as_of_date is not None,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'lifecycle_counts': state_counts
            }
        })
    except Exception as e:
        logger.error(f"[GRAPH_VIZ] Error: {e}")
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        db_session.close()

@app.route('/api/graph/search')
def graph_search():
    """Search for entities and return matching node with 1-hop neighbors.
    
    Query parameters:
    - q: Search query (entity name, partial match)
    - lifecycle_state: Filter by lifecycle state (default: 'all')
    - limit: Max results for search (default: 10)
    - as_of_date: ISO date string for temporal filtering (optional)
    """
    from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
    from sqlalchemy import or_, func
    from datetime import datetime
    
    # Ensure tenant context is set
    tenant_id = g.tenant_id or session.get('tenant_id')
    if not tenant_id:
        return jsonify({'success': False, 'error': 'No vault context - please select a vault first', 'results': []}), 401
    
    query = request.args.get('q', '').strip()
    lifecycle_filter = request.args.get('lifecycle_state', 'all')
    limit = int(request.args.get('limit', 10))
    as_of_date_str = request.args.get('as_of_date', None)
    
    as_of_date = None
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d')
            except ValueError:
                pass
    
    if not query:
        return jsonify({'success': True, 'results': [], 'message': 'Enter a search term'})
    
    db_session = get_session()
    set_tenant_on_session(db_session, tenant_id)
    logger.info(f"[GRAPH_SEARCH] tenant_id={tenant_id}, query='{query}'")
    try:
        entity_query = db_session.query(Entity).filter(
            func.lower(Entity.name).contains(query.lower())
        )
        
        if as_of_date:
            entity_query = entity_query.filter(
                Entity.valid_from <= as_of_date,
                or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
            )
        else:
            entity_query = entity_query.filter(Entity.valid_to.is_(None))
        
        if lifecycle_filter != 'all':
            try:
                state = LifecycleState(lifecycle_filter)
                entity_query = entity_query.filter(Entity.lifecycle_state == state)
            except ValueError:
                pass
        
        matches = entity_query.order_by(Entity.confidence.desc()).limit(limit).all()
        
        results = []
        for e in matches:
            results.append({
                'id': str(e.id),
                'name': e.name,
                'type': e.entity_type,
                'lifecycle_state': e.lifecycle_state.value if e.lifecycle_state else 'STAGING',
                'confidence': e.confidence or 0.5
            })
        
        logger.info(f"[GRAPH_SEARCH] Found {len(results)} results for '{query}'")
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        logger.error(f"[GRAPH_SEARCH] Error: {e}")
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        db_session.close()

@app.route('/api/graph/expand/<entity_id>')
def graph_expand(entity_id):
    """Get an entity and its 1-hop neighbors (for progressive disclosure).
    
    Returns the entity, all directly connected entities, and their relationships.
    Includes frontier detection: neighbors with no further edges are marked as frontiers.
    Respects lifecycle_state filter for all entities and relationships.
    Supports as_of_date for temporal filtering.
    
    Optional: include_speculative=true to get rule-based and similarity inferences
    for frontier nodes (Phase 2 speculative layer).
    """
    from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
    from src.context_foundry.config.domain_schema import FrontierReason, FrontierNode, generate_frontier_message
    from sqlalchemy import or_
    from datetime import datetime
    import uuid
    
    # CRITICAL: Ensure tenant context is set for RLS isolation
    tenant_id = g.tenant_id or session.get('tenant_id')
    if not tenant_id:
        logger.warning("[GRAPH_EXPAND] No tenant context - returning 401")
        return jsonify({'success': False, 'error': 'No vault context - please select a vault first'}), 401
    
    lifecycle_filter = request.args.get('lifecycle_state', 'all')
    as_of_date_str = request.args.get('as_of_date', None)
    include_speculative = request.args.get('include_speculative', 'false').lower() == 'true'
    
    as_of_date = None
    if as_of_date_str:
        try:
            as_of_date = datetime.fromisoformat(as_of_date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d')
            except ValueError:
                pass
    
    db_session = get_session()
    set_tenant_on_session(db_session, tenant_id)
    logger.info(f"[GRAPH_EXPAND] tenant_id={tenant_id}, entity_id={entity_id}")
    try:
        try:
            entity_uuid = uuid.UUID(entity_id)
        except ValueError:
            return jsonify({'error': 'Invalid entity ID', 'success': False}), 400
        
        center_query = db_session.query(Entity).filter(Entity.id == entity_uuid)
        
        if as_of_date:
            center_query = center_query.filter(
                Entity.valid_from <= as_of_date,
                or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
            )
        else:
            center_query = center_query.filter(Entity.valid_to.is_(None))
        
        if lifecycle_filter != 'all':
            try:
                state = LifecycleState(lifecycle_filter)
                center_query = center_query.filter(Entity.lifecycle_state == state)
            except ValueError:
                pass
        
        center_entity = center_query.first()
        if not center_entity:
            entity_exists = db_session.query(Entity).filter(Entity.id == entity_uuid).first()
            if entity_exists:
                message = f'Entity exists but is not visible'
                if as_of_date:
                    message += f' as of {as_of_date_str}'
                if lifecycle_filter != 'all':
                    message += f' in {lifecycle_filter} state'
                return jsonify({
                    'success': True,
                    'center_id': entity_id,
                    'nodes': [],
                    'edges': [],
                    'stats': {'total_nodes': 0, 'total_edges': 0, 'neighbors': 0},
                    'message': message
                })
            return jsonify({'error': 'Entity not found', 'success': False}), 404
        
        outgoing_query = db_session.query(Relationship).filter(
            Relationship.source_id == entity_uuid
        )
        incoming_query = db_session.query(Relationship).filter(
            Relationship.target_id == entity_uuid
        )
        
        if as_of_date:
            outgoing_query = outgoing_query.filter(
                Relationship.valid_from <= as_of_date,
                or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
            )
            incoming_query = incoming_query.filter(
                Relationship.valid_from <= as_of_date,
                or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
            )
        else:
            outgoing_query = outgoing_query.filter(Relationship.valid_to.is_(None))
            incoming_query = incoming_query.filter(Relationship.valid_to.is_(None))
        
        if lifecycle_filter != 'all':
            try:
                state = LifecycleState(lifecycle_filter)
                outgoing_query = outgoing_query.filter(Relationship.lifecycle_state == state)
                incoming_query = incoming_query.filter(Relationship.lifecycle_state == state)
            except ValueError:
                pass
        
        outgoing_rels = outgoing_query.all()
        incoming_rels = incoming_query.all()
        
        neighbor_ids = set()
        for r in outgoing_rels:
            neighbor_ids.add(r.target_id)
        for r in incoming_rels:
            neighbor_ids.add(r.source_id)
        
        neighbors = []
        if neighbor_ids:
            neighbor_query = db_session.query(Entity).filter(Entity.id.in_(neighbor_ids))
            if as_of_date:
                neighbor_query = neighbor_query.filter(
                    Entity.valid_from <= as_of_date,
                    or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
                )
            else:
                neighbor_query = neighbor_query.filter(Entity.valid_to.is_(None))
            if lifecycle_filter != 'all':
                try:
                    state = LifecycleState(lifecycle_filter)
                    neighbor_query = neighbor_query.filter(Entity.lifecycle_state == state)
                except ValueError:
                    pass
            neighbors = neighbor_query.all()
        
        all_entities = [center_entity] + neighbors
        all_relationships = outgoing_rels + incoming_rels
        
        frontier = []
        center_id_uuid = uuid.UUID(entity_id)
        
        for neighbor in neighbors:
            neighbor_outgoing = db_session.query(Relationship).filter(
                Relationship.source_id == neighbor.id,
                Relationship.target_id != center_id_uuid
            )
            neighbor_incoming = db_session.query(Relationship).filter(
                Relationship.target_id == neighbor.id,
                Relationship.source_id != center_id_uuid
            )
            
            if as_of_date:
                neighbor_outgoing = neighbor_outgoing.filter(
                    Relationship.valid_from <= as_of_date,
                    or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
                )
                neighbor_incoming = neighbor_incoming.filter(
                    Relationship.valid_from <= as_of_date,
                    or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
                )
            else:
                neighbor_outgoing = neighbor_outgoing.filter(Relationship.valid_to.is_(None))
                neighbor_incoming = neighbor_incoming.filter(Relationship.valid_to.is_(None))
            
            if lifecycle_filter != 'all':
                try:
                    state = LifecycleState(lifecycle_filter)
                    neighbor_outgoing = neighbor_outgoing.filter(Relationship.lifecycle_state == state)
                    neighbor_incoming = neighbor_incoming.filter(Relationship.lifecycle_state == state)
                except ValueError:
                    pass
            
            has_further_edges = neighbor_outgoing.first() is not None or neighbor_incoming.first() is not None
            
            if not has_further_edges:
                message = generate_frontier_message(
                    FrontierReason.NO_RELATIONSHIPS,
                    "explore",
                    neighbor.name,
                    neighbor.entity_type
                )
                frontier.append({
                    'entity_id': str(neighbor.id),
                    'entity_name': neighbor.name,
                    'entity_type': neighbor.entity_type,
                    'reason': FrontierReason.NO_RELATIONSHIPS.value,
                    'message': message,
                    'depth': 1
                })
        
        nodes = []
        for e in all_entities:
            props = e.properties or {}
            nodes.append({
                'id': str(e.id),
                'name': e.name,
                'type': e.entity_type,
                'lifecycle_state': e.lifecycle_state.value if e.lifecycle_state else 'STAGING',
                'confidence': e.confidence or 0.5,
                'validation_status': e.validation_status.value if e.validation_status else 'PENDING',
                'is_center': str(e.id) == entity_id,
                'properties': props,
                'description': e.description,
                'source_document_id': e.source_document_id,
                'created_at': e.created_at.isoformat() if e.created_at else None,
                'promoted_at': e.promoted_at.isoformat() if e.promoted_at else None,
                'valid_from': e.valid_from.isoformat() if e.valid_from else None,
                'valid_to': e.valid_to.isoformat() if e.valid_to else None
            })
        
        edges = []
        valid_node_ids = {str(e.id) for e in all_entities}
        for r in all_relationships:
            if str(r.source_id) in valid_node_ids and str(r.target_id) in valid_node_ids:
                edges.append({
                    'id': str(r.id),
                    'source': str(r.source_id),
                    'target': str(r.target_id),
                    'type': r.relationship_type,
                    'lifecycle_state': r.lifecycle_state.value if r.lifecycle_state else 'STAGING',
                    'confidence': r.confidence or 0.5,
                    'source_sentence': r.source_sentence
                })
        
        speculative = {'inferred': [], 'similar': []}
        if include_speculative:
            try:
                from src.context_foundry.memory.inference import InferenceEngine
                
                inference_engine = InferenceEngine(session, tenant_id=g.tenant_id)
                visited_ids = {str(e.id) for e in all_entities}
                
                all_inferred = []
                all_similar = []
                
                if frontier:
                    frontier_nodes = [
                        FrontierNode(
                            entity_id=f['entity_id'],
                            entity_name=f['entity_name'],
                            entity_type=f['entity_type'],
                            reason=FrontierReason(f['reason']),
                            message=f['message'],
                            depth=f.get('depth', 1)
                        )
                        for f in frontier
                    ]
                    
                    speculative_result = inference_engine.get_speculative_results(
                        frontier_nodes=frontier_nodes,
                        visited_entities=visited_ids,
                        include_similar=True
                    )
                    all_inferred.extend(speculative_result.inferred)
                    all_similar.extend(speculative_result.similar)
                
                neighbor_ids = [str(n.id) for n in neighbors]
                shared_dep_inferred = inference_engine.find_shared_dependencies(
                    neighbor_ids=neighbor_ids,
                    center_id=entity_id,
                    visited_entities=visited_ids
                )
                all_inferred.extend(shared_dep_inferred)
                
                transitive_inferred = inference_engine.find_transitive_chains(
                    center_id=entity_id,
                    neighbor_ids=neighbor_ids,
                    visited_entities=visited_ids
                )
                all_inferred.extend(transitive_inferred)
                
                if not neighbors:
                    co_occurrence_inferred = inference_engine.find_co_occurrences_for_entity(
                        entity_id=entity_id,
                        visited_entities=visited_ids
                    )
                    all_inferred.extend(co_occurrence_inferred)
                
                seen_pairs = set()
                unique_inferred = []
                for inf in all_inferred:
                    pair = (inf.source_entity_id, inf.target_entity_id, inf.inferred_relationship_type)
                    reverse_pair = (inf.target_entity_id, inf.source_entity_id, inf.inferred_relationship_type)
                    if pair not in seen_pairs and reverse_pair not in seen_pairs:
                        seen_pairs.add(pair)
                        unique_inferred.append(inf)
                
                speculative = {
                    'inferred': [inf.to_dict() for inf in unique_inferred],
                    'similar': [sim.to_dict() for sim in all_similar]
                }
            except Exception as spec_error:
                import traceback
                traceback.print_exc()
                speculative = {'inferred': [], 'similar': [], 'error': str(spec_error)}
        
        return jsonify({
            'success': True,
            'center_id': entity_id,
            'nodes': nodes,
            'edges': edges,
            'frontier': frontier,
            'speculative': speculative,
            'as_of_date': as_of_date_str,
            'is_historical': as_of_date is not None,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'neighbors': len(neighbors),
                'frontier_nodes': len(frontier),
                'speculative_inferred': len(speculative.get('inferred', [])),
                'speculative_similar': len(speculative.get('similar', []))
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"[GRAPH_EXPAND] Error: {e}")
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        db_session.close()

@app.route('/api/graph/entity/<entity_id>')
def graph_entity_details(entity_id):
    """Get full details for a single entity (for side panel)."""
    from src.context_foundry.models.schema import get_session, Entity, Relationship
    import uuid
    
    # CRITICAL: Ensure tenant context is set for RLS isolation
    tenant_id = g.tenant_id or session.get('tenant_id')
    if not tenant_id:
        logger.warning("[GRAPH_ENTITY] No tenant context - returning 401")
        return jsonify({'success': False, 'error': 'No vault context - please select a vault first'}), 401
    
    db_session = get_session()
    set_tenant_on_session(db_session, tenant_id)
    logger.info(f"[GRAPH_ENTITY] tenant_id={tenant_id}, entity_id={entity_id}")
    try:
        try:
            entity_uuid = uuid.UUID(entity_id)
        except ValueError:
            return jsonify({'error': 'Invalid entity ID', 'success': False}), 400
        
        entity = db_session.query(Entity).filter(Entity.id == entity_uuid).first()
        if not entity:
            return jsonify({'error': 'Entity not found', 'success': False}), 404
        
        outgoing = db_session.query(Relationship).filter(
            Relationship.source_id == entity_uuid
        ).all()
        incoming = db_session.query(Relationship).filter(
            Relationship.target_id == entity_uuid
        ).all()
        
        outgoing_list = []
        for r in outgoing:
            target = db_session.query(Entity).filter(Entity.id == r.target_id).first()
            outgoing_list.append({
                'relationship_type': r.relationship_type,
                'target_id': str(r.target_id),
                'target_name': target.name if target else 'Unknown',
                'target_type': target.entity_type if target else 'Unknown',
                'confidence': r.confidence or 0.5
            })
        
        incoming_list = []
        for r in incoming:
            source = db_session.query(Entity).filter(Entity.id == r.source_id).first()
            incoming_list.append({
                'relationship_type': r.relationship_type,
                'source_id': str(r.source_id),
                'source_name': source.name if source else 'Unknown',
                'source_type': source.entity_type if source else 'Unknown',
                'confidence': r.confidence or 0.5
            })
        
        return jsonify({
            'success': True,
            'entity': {
                'id': str(entity.id),
                'name': entity.name,
                'type': entity.entity_type,
                'lifecycle_state': entity.lifecycle_state.value if entity.lifecycle_state else 'STAGING',
                'validation_status': entity.validation_status.value if entity.validation_status else 'PENDING',
                'confidence': entity.confidence or 0.5,
                'description': entity.description,
                'properties': entity.properties or {},
                'source_document_id': entity.source_document_id,
                'source_sentence': entity.source_sentence,
                'created_at': entity.created_at.isoformat() if entity.created_at else None,
                'promoted_at': entity.promoted_at.isoformat() if entity.promoted_at else None,
                'archived_at': entity.archived_at.isoformat() if entity.archived_at else None
            },
            'outgoing_relationships': outgoing_list,
            'incoming_relationships': incoming_list
        })
    except Exception as e:
        logger.error(f"[GRAPH_ENTITY] Error: {e}")
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        db_session.close()

@app.route('/api/entities/<entity_id>/history')
def entity_history(entity_id):
    """Get temporal history for an entity - all versions over time.
    
    Returns a list of entity versions ordered by valid_from (newest first),
    showing how the entity evolved over time through merges, updates, etc.
    """
    from src.context_foundry.models.schema import get_session, Entity
    import uuid as uuid_module
    
    session = get_session()
    set_tenant_on_session(session, g.tenant_id)
    try:
        try:
            entity_uuid = uuid_module.UUID(entity_id)
        except ValueError:
            return jsonify({'error': 'Invalid entity ID', 'success': False}), 400
        
        current = session.query(Entity).filter(Entity.id == entity_uuid).first()
        if not current:
            return jsonify({'error': 'Entity not found', 'success': False}), 404
        
        history = []
        
        history.append({
            'id': str(current.id),
            'name': current.name,
            'entity_type': current.entity_type,
            'confidence': current.confidence or 0.5,
            'lifecycle_state': current.lifecycle_state.value if current.lifecycle_state else 'STAGING',
            'valid_from': current.valid_from.isoformat() if current.valid_from else None,
            'valid_to': current.valid_to.isoformat() if current.valid_to else None,
            'is_current': current.valid_to is None,
            'change_reason': current.change_reason,
            'superseded_by': str(current.superseded_by) if current.superseded_by else None,
            'properties': current.properties or {},
            'source_document_id': current.source_document_id,
            'created_at': current.created_at.isoformat() if current.created_at else None
        })
        
        predecessors = session.query(Entity).filter(
            Entity.superseded_by == entity_uuid
        ).order_by(Entity.valid_from.desc()).all()
        
        for pred in predecessors:
            history.append({
                'id': str(pred.id),
                'name': pred.name,
                'entity_type': pred.entity_type,
                'confidence': pred.confidence or 0.5,
                'lifecycle_state': pred.lifecycle_state.value if pred.lifecycle_state else 'ARCHIVED',
                'valid_from': pred.valid_from.isoformat() if pred.valid_from else None,
                'valid_to': pred.valid_to.isoformat() if pred.valid_to else None,
                'is_current': False,
                'change_reason': pred.change_reason,
                'superseded_by': str(pred.superseded_by) if pred.superseded_by else None,
                'properties': pred.properties or {},
                'source_document_id': pred.source_document_id,
                'created_at': pred.created_at.isoformat() if pred.created_at else None
            })
        
        history.sort(key=lambda x: x['valid_from'] or '', reverse=True)
        
        return jsonify({
            'success': True,
            'entity_id': entity_id,
            'current_name': current.name,
            'history_count': len(history),
            'history': history
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500
    finally:
        session.close()

@app.route('/api/examples')
def examples():
    """Load example queries from active domain schema."""
    from src.context_foundry.config.domain_schema import get_schema_loader
    
    schema_loader = get_schema_loader()
    schema = schema_loader.schema
    
    example_queries = schema.example_queries
    
    if example_queries:
        formatted_examples = [
            {
                'query': query,
                'category': schema.domain,
                'icon': 'search'
            }
            for query in example_queries
        ]
    else:
        formatted_examples = [
            {
                'query': f"Tell me about entities in the {schema.domain} domain",
                'category': schema.domain,
                'icon': 'search'
            }
        ]
    
    return jsonify({'success': True, 'examples': formatted_examples, 'domain': schema.domain})

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


@app.route('/api/resolve-duplicates', methods=['POST'])
def resolve_duplicates():
    """
    Run identity resolution on all STAGING entities.
    
    Detects duplicate entities and either auto-merges or flags for review.
    
    Returns:
        { duplicates_found, auto_merged, flagged_for_review, errors }
    """
    from src.context_foundry.agents.identity_resolver import IdentityResolver
    from src.context_foundry.models.schema import get_session
    
    try:
        session = get_session()
        
        resolver = IdentityResolver(session)
        result = resolver.run(commit=True)
        
        return jsonify({
            'success': True,
            'entities_scanned': result.entities_scanned,
            'duplicates_found': result.candidates_found,
            'auto_merged': result.auto_merged,
            'flagged_for_review': result.flagged_for_review,
            'relationships_transferred': result.relationships_transferred,
            'errors': result.errors,
            'started_at': result.started_at.isoformat() if result.started_at else None,
            'completed_at': result.completed_at.isoformat() if result.completed_at else None,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        
        tenant_id = g.get('tenant_id')
        if not tenant_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        evaluator = BlindEvaluator(tenant_id=tenant_id)
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
    from src.context_foundry.models.schema import EvaluationVote, get_session
    
    global comparison_pairs
    
    # Demo tenant with test data (API Gateway, Auth Service, etc.)
    DEMO_TENANT_ID = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"
    
    try:
        data = request.get_json()
        query_id = data.get('query_id')
        use_demo_tenant = data.get('use_demo_tenant', True)  # Default to demo tenant for evaluation
        
        if not query_id:
            return jsonify({'success': False, 'error': 'query_id required'}), 400
        
        tenant_id = g.get('tenant_id')
        if not tenant_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Use demo tenant for evaluation if requested (default) to ensure test data is available
        eval_tenant_id = DEMO_TENANT_ID if use_demo_tenant else tenant_id
        
        evaluator = BlindEvaluator(tenant_id=eval_tenant_id)
        pair = evaluator.run_single_query(query_id)
        
        if not pair:
            return jsonify({'success': False, 'error': 'Query not found'}), 404
        
        comparison_pairs[pair.pair_id] = pair
        
        blind_a, blind_b = pair.get_blind_responses()
        
        session = get_session()
        try:
            existing = session.query(EvaluationVote).filter_by(pair_id=pair.pair_id).first()
            if not existing:
                vote_record = EvaluationVote(
                    pair_id=pair.pair_id,
                    query_id=query_id,
                    query_text=pair.query.query_text,
                    a_is_context_foundry=pair.a_is_context_foundry,
                    response_a=blind_a.get('answer', ''),
                    response_b=blind_b.get('answer', ''),
                    latency_a_ms=blind_a.get('latency_ms', 0),
                    latency_b_ms=blind_b.get('latency_ms', 0),
                )
                session.add(vote_record)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
        
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
        
        tenant_id = g.get('tenant_id')
        if not tenant_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        graphrag = GraphRAGBaseline(tenant_id=tenant_id)
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
    from src.context_foundry.models.schema import EvaluationVote, get_session
    from datetime import datetime
    
    global evaluation_result, comparison_pairs, preference_metrics
    
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
        
        session = get_session()
        try:
            vote_record = session.query(EvaluationVote).filter_by(pair_id=pair_id).first()
            
            if vote_record:
                if vote_record.human_preference:
                    metrics = _compute_metrics_from_db(session)
                    return jsonify({
                        'success': True,
                        'message': 'Already reviewed',
                        'metrics': metrics,
                    })
                
                vote_record.human_preference = preference
                vote_record.reviewed_by = reviewer
                vote_record.notes = notes
                vote_record.voted_at = datetime.utcnow()
                session.commit()
                
                metrics = _compute_metrics_from_db(session)
                return jsonify({
                    'success': True,
                    'metrics': metrics,
                })
        except Exception as db_err:
            session.rollback()
            print(f"DB error: {db_err}")
        finally:
            session.close()
        
        pair = comparison_pairs.get(pair_id)
        
        if pair:
            # Check if already reviewed - prevent duplicate votes
            if pair_id in preference_metrics['reviewed']:
                return jsonify({
                    'success': True,
                    'message': 'Already reviewed',
                    'metrics': {
                        'cf_wins': preference_metrics['cf_wins'],
                        'graphrag_wins': preference_metrics['graphrag_wins'],
                        'ties': preference_metrics['ties'],
                        'reviewed': len(preference_metrics['reviewed']),
                    },
                })
            
            # Record preference on the stored pair
            pair.human_preference = preference
            pair.reviewed_by = reviewer
            pair.human_notes = notes
            
            # Add to reviewed set FIRST to prevent race conditions
            preference_metrics['reviewed'].add(pair_id)
            
            # Determine actual winner based on which system was A/B
            if preference == 'tie':
                preference_metrics['ties'] += 1
            elif preference == 'A':
                # A was chosen - check if A is context_foundry
                if pair.a_is_context_foundry:
                    preference_metrics['cf_wins'] += 1
                else:
                    preference_metrics['graphrag_wins'] += 1
            else:  # preference == 'B'
                # B was chosen - check if B is context_foundry (opposite of A)
                if not pair.a_is_context_foundry:
                    preference_metrics['cf_wins'] += 1
                else:
                    preference_metrics['graphrag_wins'] += 1
            
            return jsonify({
                'success': True,
                'metrics': {
                    'cf_wins': preference_metrics['cf_wins'],
                    'graphrag_wins': preference_metrics['graphrag_wins'],
                    'ties': preference_metrics['ties'],
                    'reviewed': len(preference_metrics['reviewed']),
                },
            })
        
        # Fall back to batch evaluation result if available
        if evaluation_result is not None:
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
        
        return jsonify({'success': False, 'error': 'Pair not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluation/metrics')
def get_evaluation_metrics():
    """Get current evaluation metrics."""
    from src.context_foundry.evaluation.evaluator import BlindEvaluator
    from src.context_foundry.models.schema import get_session
    
    global evaluation_result, preference_metrics
    
    try:
        session = get_session()
        try:
            metrics = _compute_metrics_from_db(session)
            if metrics['reviewed'] > 0:
                return jsonify({
                    'success': True,
                    'metrics': metrics,
                })
        finally:
            session.close()
        
        if len(preference_metrics['reviewed']) > 0:
            return jsonify({
                'success': True,
                'metrics': {
                    'cf_wins': preference_metrics['cf_wins'],
                    'graphrag_wins': preference_metrics['graphrag_wins'],
                    'ties': preference_metrics['ties'],
                    'reviewed': len(preference_metrics['reviewed']),
                },
            })
        
        if evaluation_result is None:
            return jsonify({
                'success': True,
                'message': 'No evaluation running',
                'metrics': {'cf_wins': 0, 'graphrag_wins': 0, 'ties': 0, 'reviewed': 0},
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
    
    global evaluation_result, comparison_pairs, preference_metrics
    
    try:
        # Check stored comparisons first
        reviewed_pairs = [p for p in comparison_pairs.values() if p.human_preference]
        
        if reviewed_pairs:
            # Calculate win rate
            total_decided = preference_metrics['cf_wins'] + preference_metrics['graphrag_wins']
            cf_win_rate = preference_metrics['cf_wins'] / total_decided if total_decided > 0 else 0
            
            return jsonify({
                'success': True,
                'reviewed': len(reviewed_pairs),
                'pairs': [p.to_dict(reveal_source=True) for p in reviewed_pairs],
                'metrics': {
                    'cf_wins': preference_metrics['cf_wins'],
                    'graphrag_wins': preference_metrics['graphrag_wins'],
                    'ties': preference_metrics['ties'],
                    'cf_win_rate': cf_win_rate,
                },
            })
        
        # Fall back to batch evaluation result
        if evaluation_result is None:
            return jsonify({'success': False, 'error': 'No pairs have been reviewed yet'}), 400
        
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


@app.route('/api/ingest', methods=['POST'])
def ingest_document():
    """
    Ingest a document and extract entities/relationships to STAGING.
    Auto-runs validation after ingestion to check for conflicts and rule violations.
    Auto-runs identity resolution to detect and handle duplicate entities.
    
    Body: 
        { "document_path": "..." } - Path to document file
        OR
        { "text": "...", "title": "...", "doc_type": "..." } - Raw text content
        
        Optional:
        { "schema_config_path": "config/examples/investment_portfolio.yaml" } - Use alternate schema
        { "skip_validation": true } - Skip auto-validation after ingestion
        { "skip_identity_resolution": true } - Skip identity resolution after validation
        
    Returns:
        { "entities_extracted": N, "relationships_extracted": M, "staged": true, "validation": {...}, "identity_resolution": {...}, "schema_info": {...} }
    """
    from src.context_foundry.agents.graph_builder import GraphBuilderAgent, ExtractionResult
    from src.context_foundry.agents.staging_validator import StagingValidatorAgent
    from src.context_foundry.agents.identity_resolver import IdentityResolver
    from src.context_foundry.models.schema import get_session
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON body provided'}), 400
        
        doc_path = data.get('document_path')
        text = data.get('text')
        title = data.get('title')
        doc_type = data.get('doc_type', 'DOCUMENT')
        schema_config_path = data.get('schema_config_path')
        skip_validation = data.get('skip_validation', False)
        skip_identity_resolution = data.get('skip_identity_resolution', False)
        
        if not doc_path and not text:
            return jsonify({
                'success': False, 
                'error': 'Either document_path or text must be provided'
            }), 400
        
        agent = GraphBuilderAgent(schema_config_path=schema_config_path)
        validation_result = None
        identity_result = None
        
        try:
            result = agent.ingest_document(
                doc_path=doc_path,
                text=text,
                title=title,
                doc_type=doc_type
            )
            
            if not skip_validation and result.staged and (result.entities_staged > 0 or result.relationships_staged > 0):
                validator = StagingValidatorAgent(schema_config_path=schema_config_path)
                try:
                    val_result = validator.validate_all_staging()
                    validation_result = {
                        'is_valid': val_result.is_valid,
                        'entities_checked': val_result.entities_checked,
                        'relationships_checked': val_result.relationships_checked,
                        'errors_count': len(val_result.get_errors()),
                        'warnings_count': len(val_result.get_warnings()),
                        'conflicts_detected': val_result.conflicts_detected,
                        'review_items_created': val_result.review_items_created,
                        'issues': [
                            {
                                'severity': issue.severity.value,
                                'rule_name': issue.rule_name,
                                'message': issue.message,
                                'entity_id': issue.entity_id,
                                'relationship_id': issue.relationship_id,
                            }
                            for issue in val_result.issues[:20]
                        ]
                    }
                finally:
                    validator.close()
            
            if not skip_identity_resolution and result.staged and (result.entities_staged > 0):
                session = get_session()
                try:
                    resolver = IdentityResolver(session)
                    id_result = resolver.run(commit=True)
                    identity_result = {
                        'entities_scanned': id_result.entities_scanned,
                        'duplicates_found': id_result.candidates_found,
                        'auto_merged': id_result.auto_merged,
                        'flagged_for_review': id_result.flagged_for_review,
                        'relationships_transferred': id_result.relationships_transferred,
                        'errors': id_result.errors,
                    }
                finally:
                    session.close()
            
            return jsonify({
                'success': True,
                'document_id': result.document_id,
                'entities_extracted': result.entities_extracted,
                'relationships_extracted': result.relationships_extracted,
                'entities_staged': result.entities_staged,
                'relationships_staged': result.relationships_staged,
                'chunks_processed': result.chunks_processed,
                'staged': result.staged,
                'errors': result.errors if result.errors else [],
                'validation': validation_result,
                'identity_resolution': identity_result,
                'schema_info': agent.get_schema_info(),
            })
        finally:
            agent.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback for a query response (Learning Loop)."""
    from src.context_foundry.models.schema import FeedbackRecord, get_session
    
    try:
        data = request.get_json()
        
        query_text = data.get('query_text', '')
        response_text = data.get('response_text', '')
        confidence = data.get('confidence', 0)
        judgment = data.get('judgment', '')
        error_type = data.get('error_type')
        query_log_id = data.get('query_log_id')
        
        if not query_text or not response_text or not judgment:
            return jsonify({'success': False, 'error': 'query_text, response_text, and judgment required'}), 400
        
        if judgment not in ['correct', 'incorrect', 'partial']:
            return jsonify({'success': False, 'error': 'judgment must be correct, incorrect, or partial'}), 400
        
        session = get_session()
        try:
            feedback = FeedbackRecord(
                query_log_id=query_log_id if query_log_id else None,
                query_text=query_text,
                response_text=response_text,
                confidence=confidence,
                judgment=judgment,
                error_type=error_type,
                processed=False,
            )
            session.add(feedback)
            session.commit()
            
            return jsonify({
                'success': True,
                'feedback_id': str(feedback.id),
                'message': 'Feedback recorded successfully',
            })
        except Exception as db_err:
            session.rollback()
            return jsonify({'success': False, 'error': str(db_err)}), 500
        finally:
            session.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback/stats')
def feedback_stats():
    """Get feedback statistics for the Learning Loop dashboard."""
    from src.context_foundry.models.schema import FeedbackRecord, get_session
    from sqlalchemy import func
    
    try:
        session = get_session()
        try:
            total = session.query(func.count(FeedbackRecord.id)).scalar() or 0
            unprocessed = session.query(func.count(FeedbackRecord.id)).filter(
                FeedbackRecord.processed == False
            ).scalar() or 0
            
            correct = session.query(func.count(FeedbackRecord.id)).filter(
                FeedbackRecord.judgment == 'correct'
            ).scalar() or 0
            incorrect = session.query(func.count(FeedbackRecord.id)).filter(
                FeedbackRecord.judgment == 'incorrect'
            ).scalar() or 0
            partial = session.query(func.count(FeedbackRecord.id)).filter(
                FeedbackRecord.judgment == 'partial'
            ).scalar() or 0
            
            error_types = session.query(
                FeedbackRecord.error_type,
                func.count(FeedbackRecord.id).label('count')
            ).filter(
                FeedbackRecord.error_type.isnot(None)
            ).group_by(FeedbackRecord.error_type).all()
            
            return jsonify({
                'success': True,
                'stats': {
                    'total': total,
                    'unprocessed': unprocessed,
                    'processed': total - unprocessed,
                    'by_judgment': {
                        'correct': correct,
                        'incorrect': incorrect,
                        'partial': partial,
                    },
                    'by_error_type': {et: count for et, count in error_types if et},
                },
            })
        finally:
            session.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback/recent')
def recent_feedback():
    """Get recent feedback records."""
    from src.context_foundry.models.schema import FeedbackRecord, get_session
    
    try:
        session = get_session()
        try:
            limit = request.args.get('limit', 20, type=int)
            unprocessed_only = request.args.get('unprocessed', 'false').lower() == 'true'
            
            query = session.query(FeedbackRecord).order_by(FeedbackRecord.created_at.desc())
            
            if unprocessed_only:
                query = query.filter(FeedbackRecord.processed == False)
            
            records = query.limit(limit).all()
            
            return jsonify({
                'success': True,
                'feedback': [r.to_dict() for r in records],
                'count': len(records),
            })
        finally:
            session.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schema')
def get_schema():
    """Get current domain schema configuration."""
    from src.context_foundry.config.domain_schema import get_schema_loader
    
    try:
        loader = get_schema_loader()
        schema = loader.schema
        
        return jsonify({
            'success': True,
            'schema': {
                'domain': schema.domain,
                'schema_version': schema.schema_version,
                'description': schema.description,
                'entity_types': [
                    {
                        'name': et.name,
                        'description': et.description,
                        'required_fields': et.required_fields,
                        'optional_fields': et.optional_fields,
                    }
                    for et in schema.entity_types.values()
                ],
                'relationship_types': [
                    {
                        'name': rt.name,
                        'description': rt.description,
                        'source_types': rt.source_types,
                        'target_types': rt.target_types,
                        'cardinality': rt.cardinality.value,
                    }
                    for rt in schema.relationship_types.values()
                ],
                'validation_rules': [
                    {
                        'name': r.name,
                        'description': r.description,
                        'applies_to': r.applies_to,
                    }
                    for r in schema.validation_rules
                ],
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schema/reload', methods=['POST'])
def reload_schema():
    """Reload domain schema from config file."""
    from src.context_foundry.config.domain_schema import get_schema_loader
    
    try:
        data = request.get_json() or {}
        config_path = data.get('config_path')
        
        loader = get_schema_loader(config_path=config_path, force_reload=True)
        
        return jsonify({
            'success': True,
            'message': f'Schema reloaded for domain: {loader.schema.domain}',
            'domain': loader.schema.domain,
            'entity_types': list(loader.schema.entity_types.keys()),
            'relationship_types': list(loader.schema.relationship_types.keys()),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/validate', methods=['POST'])
def validate_staging():
    """Validate all STAGING entities and relationships against schema rules."""
    from src.context_foundry.agents.staging_validator import StagingValidatorAgent
    
    try:
        data = request.get_json() or {}
        schema_config_path = data.get('schema_config_path')
        
        validator = StagingValidatorAgent(schema_config_path=schema_config_path)
        result = validator.validate_all_staging()
        
        issues_list = [
            {
                'severity': issue.severity.value,
                'rule_name': issue.rule_name,
                'message': issue.message,
                'entity_id': issue.entity_id,
                'relationship_id': issue.relationship_id,
                'conflicting_fact_id': issue.conflicting_fact_id,
                'suggested_action': issue.suggested_action,
            }
            for issue in result.issues
        ]
        
        validator.close()
        
        return jsonify({
            'success': True,
            'validation': {
                'is_valid': result.is_valid,
                'entities_checked': result.entities_checked,
                'relationships_checked': result.relationships_checked,
                'issues': issues_list,
                'errors_count': len(result.get_errors()),
                'warnings_count': len(result.get_warnings()),
                'conflicts_detected': result.conflicts_detected,
                'review_items_created': result.review_items_created,
            },
            'schema_info': validator.get_schema_info(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/review-queue')
def get_review_queue():
    """Get items in the review queue."""
    from src.context_foundry.agents.staging_validator import StagingValidatorAgent
    
    try:
        limit = request.args.get('limit', 50, type=int)
        
        validator = StagingValidatorAgent()
        items = validator.get_pending_review_items(limit=limit)
        conflicts = validator.get_pending_conflicts(limit=limit)
        
        validator.close()
        
        return jsonify({
            'success': True,
            'review_items': items,
            'pending_conflicts': conflicts,
            'review_count': len(items),
            'conflict_count': len(conflicts),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Context Bundle API v1 - Pillar 4: Deliver structured, trustworthy truth to AI
# =============================================================================

@app.route('/api/v1/context', methods=['POST'])
def context_bundle_api():
    """
    Context Bundle API - The formal delivery mechanism for structured, trustworthy context.
    
    This is Pillar 4 of the Context Foundry vision: "Deliver structured, trustworthy truth to AI."
    
    Request body:
    {
        "query": "What services are affected if Payment Database goes down?",
        "focal_entity": "Payment Database",  // optional
        "max_hops": 2,
        "include_episodic": true,
        "include_symbolic": true,
        "include_speculative": true,
        "min_confidence": 0.5,
        "max_entities": 50,
        "max_documents": 10
    }
    
    Response:
    {
        "success": true,
        "bundle": { ... APIContextBundle ... },
        "meta": { ... RetrievalMeta ... }
    }
    """
    from pydantic import ValidationError
    from src.context_foundry.api.context_bundle import ContextBundleRequest, ContextBundleResponse
    from src.context_foundry.api.bundle_builder import BundleBuilder
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON body provided',
                'bundle': None,
                'meta': None
            }), 400
        
        try:
            req = ContextBundleRequest(**data)
        except ValidationError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid request: {str(e)}',
                'bundle': None,
                'meta': None
            }), 400
        
        builder = BundleBuilder()
        bundle = builder.build(req)
        
        response = ContextBundleResponse(
            success=True,
            bundle=bundle,
            error=None,
            meta=bundle.retrieval_meta
        )
        
        return jsonify(response.model_dump(mode='json'))
        
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[Context Bundle API Error] {error_detail}")
        
        return jsonify({
            'success': False,
            'error': str(e),
            'bundle': None,
            'meta': None
        }), 500


@app.route('/api/v1/context/schema')
def context_bundle_schema():
    """
    Returns the OpenAPI schema for the Context Bundle API.
    
    This provides documentation for AI applications consuming Context Foundry.
    """
    from src.context_foundry.api.context_bundle import (
        ContextBundleRequest,
        ContextBundleResponse,
        APIContextBundle,
    )
    
    schema = {
        'openapi': '3.0.0',
        'info': {
            'title': 'Context Foundry - Context Bundle API',
            'description': 'Pillar 4: Deliver structured, trustworthy truth to AI applications.',
            'version': '1.0.0'
        },
        'paths': {
            '/api/v1/context': {
                'post': {
                    'summary': 'Get Context Bundle',
                    'description': 'Retrieves a context bundle for a natural language query. The bundle contains focal entities, related entities, relationships, source documents, applicable rules, speculative inferences, and explicit knowledge boundaries.',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': ContextBundleRequest.model_json_schema(),
                                'example': {
                                    'query': 'What services are affected if Payment Database goes down?',
                                    'focal_entity': 'Payment Database',
                                    'max_hops': 2,
                                    'include_episodic': True,
                                    'include_symbolic': True
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'Successful response with context bundle',
                            'content': {
                                'application/json': {
                                    'schema': ContextBundleResponse.model_json_schema(),
                                    'example': {
                                        'success': True,
                                        'bundle': {
                                            'version': '1.0.0',
                                            'query': 'What services are affected if Payment Database goes down?',
                                            'focal_entities': [
                                                {
                                                    'id': 'uuid-1',
                                                    'name': 'Payment Database',
                                                    'entity_type': 'DATABASE',
                                                    'confidence': 0.95,
                                                    'lifecycle_state': 'TRUSTED'
                                                }
                                            ],
                                            'related_entities': [
                                                {
                                                    'id': 'uuid-2',
                                                    'name': 'Payment Service',
                                                    'entity_type': 'SERVICE',
                                                    'confidence': 0.92,
                                                    'lifecycle_state': 'TRUSTED',
                                                    'hop_distance': 1,
                                                    'path_confidence': 0.92
                                                }
                                            ],
                                            'knowledge_gaps': [
                                                'No visibility into downstream consumers of External API Gateway'
                                            ],
                                            'overall_confidence': 0.87
                                        },
                                        'meta': {
                                            'semantic_query_time_ms': 45.2,
                                            'episodic_query_time_ms': 12.8,
                                            'symbolic_query_time_ms': 3.4,
                                            'total_time_ms': 61.4,
                                            'entities_considered': 25,
                                            'entities_included': 12
                                        }
                                    }
                                }
                            }
                        },
                        '400': {
                            'description': 'Invalid request'
                        },
                        '500': {
                            'description': 'Server error'
                        }
                    }
                }
            }
        },
        'components': {
            'schemas': {
                'ContextBundleRequest': ContextBundleRequest.model_json_schema(),
                'ContextBundleResponse': ContextBundleResponse.model_json_schema(),
                'APIContextBundle': APIContextBundle.model_json_schema(),
            }
        }
    }
    
    return jsonify(schema)


@app.route('/api/v1/inference/runs', methods=['POST'])
def start_inference_run():
    """Start a new relationship inference run."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = PyUUID(g.tenant_id)
        data = request.get_json() or {}
        
        batch_size = min(data.get('batch_size', 100), 500)
        entity_filter = data.get('entity_filter')
        domain = data.get('domain', 'IT')
        
        agent = RelationshipInferenceAgent(domain=domain)
        run = agent.run_inference(
            tenant_id=tenant_id,
            batch_size=batch_size,
            entity_filter=entity_filter
        )
        
        return jsonify({
            'run_id': str(run.id),
            'status': run.status.value,
            'entities_processed': run.entities_processed,
            'relationships_proposed': run.relationships_proposed,
            'relationships_approved': run.relationships_approved,
            'estimated_cost_usd': round(run.estimated_cost_usd, 4)
        }), 201
        
    except Exception as e:
        logger.error(f"Inference run failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/runs/<run_id>', methods=['GET'])
def get_inference_run(run_id):
    """Get inference run status."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.models.schema import InferenceRun, get_session
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        session = get_session()
        run = session.query(InferenceRun).filter(
            InferenceRun.id == PyUUID(run_id),
            InferenceRun.tenant_id == PyUUID(g.tenant_id)
        ).first()
        
        if not run:
            return jsonify({'error': 'Run not found'}), 404
        
        return jsonify(run.to_dict())
        
    except Exception as e:
        logger.error(f"Get inference run failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/review', methods=['GET'])
def get_inference_review_queue():
    """Get pending relationship proposals for review."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = PyUUID(g.tenant_id)
        run_id = request.args.get('run_id')
        limit = min(int(request.args.get('limit', 50)), 100)
        
        agent = RelationshipInferenceAgent()
        proposals = agent.get_pending_proposals(
            tenant_id=tenant_id,
            run_id=PyUUID(run_id) if run_id else None,
            limit=limit
        )
        
        return jsonify({
            'proposals': [p.to_dict() for p in proposals],
            'total_pending': len(proposals)
        })
        
    except Exception as e:
        logger.error(f"Get review queue failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/review/<proposal_id>', methods=['POST'])
def review_proposal(proposal_id):
    """Approve or reject a relationship proposal."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json() or {}
        action = data.get('action')
        reviewed_by = data.get('reviewed_by', g.get('user_id', 'anonymous'))
        
        if action not in ['approve', 'reject']:
            return jsonify({'error': 'Invalid action. Use "approve" or "reject"'}), 400
        
        agent = RelationshipInferenceAgent()
        
        if action == 'approve':
            relationship_id = agent.approve_proposal(PyUUID(proposal_id), reviewed_by)
            if relationship_id:
                return jsonify({
                    'proposal_id': proposal_id,
                    'status': 'APPROVED',
                    'relationship_id': str(relationship_id)
                })
            else:
                return jsonify({'error': 'Proposal not found or already processed'}), 404
        else:
            reason = data.get('rejection_reason', 'No reason provided')
            success = agent.reject_proposal(PyUUID(proposal_id), reviewed_by, reason)
            if success:
                return jsonify({
                    'proposal_id': proposal_id,
                    'status': 'REJECTED'
                })
            else:
                return jsonify({'error': 'Proposal not found'}), 404
        
    except Exception as e:
        logger.error(f"Review proposal failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/bulk-approve', methods=['POST'])
def bulk_approve_proposals():
    """Bulk approve proposals meeting confidence threshold."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = PyUUID(g.tenant_id)
        data = request.get_json() or {}
        
        min_confidence = data.get('min_confidence', 0.90)
        require_lexical = data.get('require_lexical_evidence', True)
        reviewed_by = data.get('reviewed_by', g.get('user_id', 'system'))
        run_id = data.get('run_id')
        
        agent = RelationshipInferenceAgent()
        approved_ids = agent.bulk_approve(
            tenant_id=tenant_id,
            min_confidence=min_confidence,
            require_lexical=require_lexical,
            approved_by=reviewed_by,
            run_id=PyUUID(run_id) if run_id else None
        )
        
        return jsonify({
            'approved_count': len(approved_ids),
            'relationship_ids': [str(rid) for rid in approved_ids]
        })
        
    except Exception as e:
        logger.error(f"Bulk approve failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/runs/<run_id>/rollback', methods=['POST'])
def rollback_inference_run(run_id):
    """Rollback an inference run, deleting created relationships."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'No reason provided')
        delete_proposals = data.get('delete_proposals', True)
        executed_by = data.get('executed_by', g.get('user_id', 'anonymous'))
        
        agent = RelationshipInferenceAgent()
        result = agent.rollback_run(
            run_id=PyUUID(run_id),
            reason=reason,
            executed_by=executed_by,
            delete_proposals=delete_proposals
        )
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/inference/metrics', methods=['GET'])
def get_inference_metrics():
    """Get relationship density and inference metrics."""
    from flask import g
    from uuid import UUID as PyUUID
    from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent
    
    if not g.get('tenant_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        tenant_id = PyUUID(g.tenant_id)
        agent = RelationshipInferenceAgent()
        metrics = agent.get_metrics(tenant_id)
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Get metrics failed: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = 5000
    
    # Check if port is available (skip if started via start.sh)
    if not os.environ.get('SKIP_PORT_CHECK'):
        if not is_port_available(port):
            print(f"[Platform] Port {port} in use, attempting to kill existing process...")
            if kill_port_process(port):
                print(f"[Platform] Successfully freed port {port}")
            else:
                print(f"[Platform] Failed to free port {port}, exiting")
                sys.exit(1)
    else:
        print(f"[Platform] Port check skipped (started via start.sh)")
    
    init_scheduler()
    print(f"[Platform] Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
