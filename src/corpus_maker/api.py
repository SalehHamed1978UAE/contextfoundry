"""REST API endpoints for Corpus Maker."""
import json
import logging
import tempfile
import uuid
import zipfile
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template
from typing import Dict, Any, List

from .uploader import upload_corpus, FolderMapping
from .validator import validate_documents, validate_questions, SUPPORTED_EXTENSIONS
from .registry import list_corpora, get_corpus_config, unregister_corpus
from .manifest import load_manifest

logger = logging.getLogger(__name__)

corpus_bp = Blueprint('corpus', __name__, url_prefix='/api/corpus')


@corpus_bp.route('/ui', methods=['GET'])
def corpus_maker_ui():
    """Serve the Corpus Maker UI."""
    import time
    return render_template('corpus_maker.html', cache_bust=int(time.time()))


@corpus_bp.route('/list', methods=['GET'])
def api_list_corpora():
    """List all registered corpora."""
    try:
        corpora_dict = list_corpora()
        corpora_list = []
        for name, data in corpora_dict.items():
            accuracy = data.get('last_accuracy')
            if isinstance(accuracy, str):
                try:
                    accuracy = float(accuracy.rstrip('%'))
                except (ValueError, AttributeError):
                    accuracy = None
            
            corpora_list.append({
                'name': name,
                'vault_id': data.get('vault_id'),
                'vault_ids': data.get('vault_ids', [data.get('vault_id')] if data.get('vault_id') else []),
                'anchor_org': data.get('anchor_org'),
                'document_count': data.get('document_count'),
                'question_count': data.get('question_count'),
                'last_run': data.get('last_run'),
                'last_accuracy': accuracy,
                'registered_at': data.get('registered_at')
            })
        return jsonify({
            'success': True,
            'corpora': corpora_list,
            'count': len(corpora_list)
        })
    except Exception as e:
        logger.exception("Error listing corpora")
        return jsonify({'success': False, 'error': str(e)}), 500


@corpus_bp.route('/<corpus_name>', methods=['GET'])
def api_get_corpus(corpus_name: str):
    """Get configuration for a specific corpus."""
    try:
        config = get_corpus_config(corpus_name)
        if not config:
            return jsonify({
                'success': False,
                'error': f"Corpus '{corpus_name}' not found"
            }), 404
        
        return jsonify({
            'success': True,
            'corpus': config
        })
    except Exception as e:
        logger.exception(f"Error getting corpus {corpus_name}")
        return jsonify({'success': False, 'error': str(e)}), 500


@corpus_bp.route('/<corpus_name>', methods=['DELETE'])
def api_delete_corpus(corpus_name: str):
    """Unregister a corpus."""
    try:
        result = unregister_corpus(corpus_name)
        if result:
            return jsonify({
                'success': True,
                'message': f"Corpus '{corpus_name}' unregistered"
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Corpus '{corpus_name}' not found"
            }), 404
    except Exception as e:
        logger.exception(f"Error deleting corpus {corpus_name}")
        return jsonify({'success': False, 'error': str(e)}), 500


@corpus_bp.route('/validate', methods=['POST'])
def api_validate():
    """
    Validate documents and questions before upload.
    
    Request body:
    {
        "doc_folders": ["/path/to/docs"],
        "question_file": "/path/to/questions.json"
    }
    
    Or with uploaded files via multipart/form-data.
    """
    try:
        all_errors = []
        
        if request.is_json:
            data = request.get_json()
            
            doc_folders = data.get('doc_folders', [])
            for folder in doc_folders:
                errors = validate_documents(Path(folder), SUPPORTED_EXTENSIONS)
                all_errors.extend(errors)
            
            question_file = data.get('question_file')
            if question_file:
                errors = validate_questions(Path(question_file))
                all_errors.extend(errors)
        
        else:
            question_count = 0
            doc_count = 0
            
            if 'questions' in request.files:
                q_file = request.files['questions']
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
                    q_file.save(f.name)
                    temp_path = Path(f.name)
                
                errors = validate_questions(temp_path)
                all_errors.extend(errors)
                
                if not errors:
                    try:
                        with open(temp_path) as qf:
                            qdata = json.load(qf)
                            question_count = len(qdata.get('questions', qdata) if isinstance(qdata, dict) else qdata)
                    except:
                        pass
                
                temp_path.unlink()
            
            doc_files = request.files.getlist('documents')
            if doc_files:
                for doc_file in doc_files:
                    if doc_file.filename:
                        ext = Path(doc_file.filename).suffix.lower()
                        if ext not in SUPPORTED_EXTENSIONS:
                            all_errors.append(f"Unsupported file type: {doc_file.filename}")
                        else:
                            doc_count += 1
            
            if all_errors:
                return jsonify({
                    'success': False,
                    'valid': False,
                    'errors': all_errors
                })
            
            return jsonify({
                'success': True,
                'valid': True,
                'errors': [],
                'question_count': question_count,
                'document_count': doc_count
            })
        
        if all_errors:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': all_errors
            })
        
        return jsonify({
            'success': True,
            'valid': True,
            'errors': []
        })
        
    except Exception as e:
        logger.exception("Validation error")
        return jsonify({'success': False, 'error': str(e)}), 500


@corpus_bp.route('/upload', methods=['POST'])
def api_upload():
    """
    Upload a new corpus.
    
    Supports multipart/form-data with:
    - vault_name: Corpus name (required)
    - anchor_org: Anchor organization (required)
    - folder_mappings: JSON array of {source, category} (optional)
    - question_file: Questions JSON file (required)
    - documents: ZIP file of documents (required)
    - sync_extract: Boolean (default true)
    
    Or JSON body for server-side paths:
    {
        "vault_name": "My Corpus",
        "anchor_org": "My Org",
        "folder_mappings": [{"source": "/path", "category": "strategy"}],
        "question_file": "/path/to/questions.json",
        "sync_extract": true
    }
    """
    try:
        if request.is_json:
            return _handle_json_upload(request.get_json())
        else:
            return _handle_multipart_upload()
    except Exception as e:
        logger.exception("Upload error")
        return jsonify({'success': False, 'error': str(e)}), 500


def _handle_json_upload(data: Dict[str, Any]):
    """Handle upload with server-side file paths."""
    vault_name = data.get('vault_name')
    anchor_org = data.get('anchor_org')
    
    if not vault_name or not anchor_org:
        return jsonify({
            'success': False,
            'error': "vault_name and anchor_org are required"
        }), 400
    
    folder_mappings = []
    for mapping in data.get('folder_mappings', []):
        folder_mappings.append(FolderMapping(
            source_path=Path(mapping['source']),
            category=mapping.get('category', 'uncategorized')
        ))
    
    question_file = data.get('question_file')
    if not question_file:
        return jsonify({
            'success': False,
            'error': "question_file is required"
        }), 400
    
    vault_id = data.get('vault_id') or str(uuid.uuid4())
    sync_extract = data.get('sync_extract', True)
    
    result = upload_corpus(
        vault_id=vault_id,
        corpus_name=vault_name,
        anchor_org=anchor_org,
        folder_mappings=folder_mappings,
        question_file=Path(question_file),
        sync_extract=sync_extract,
        user=data.get('user', 'api')
    )
    
    return _upload_result_response(result)


def _handle_multipart_upload():
    """Handle upload with file uploads."""
    vault_name = request.form.get('name') or request.form.get('vault_name')
    anchor_org = request.form.get('anchor_org') or vault_name
    
    if not vault_name:
        return jsonify({
            'success': False,
            'error': "name (corpus name) is required"
        }), 400
    
    questions_file = request.files.get('questions') or request.files.get('question_file')
    if not questions_file:
        return jsonify({
            'success': False,
            'error': "questions file is required"
        }), 400
    
    doc_files = request.files.getlist('documents')
    doc_zip = request.files.get('documents_zip')
    
    if not doc_files and not doc_zip:
        return jsonify({
            'success': False,
            'error': "documents are required (individual files or zip)"
        }), 400
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        q_path = temp_path / 'questions.json'
        questions_file.save(str(q_path))
        
        docs_path = temp_path / 'documents'
        docs_path.mkdir()
        
        category_map = {}
        category_map_json = request.form.get('category_map', '{}')
        try:
            category_map = json.loads(category_map_json)
        except json.JSONDecodeError:
            pass
        
        path_map = {}
        path_map_json = request.form.get('path_map', '{}')
        try:
            path_map = json.loads(path_map_json)
        except json.JSONDecodeError:
            pass
        
        if doc_zip:
            zip_path = temp_path / 'documents.zip'
            doc_zip.save(str(zip_path))
            with zipfile.ZipFile(zip_path, 'r') as z:
                for member in z.namelist():
                    member_path = docs_path / member
                    try:
                        member_path.resolve().relative_to(docs_path.resolve())
                    except ValueError:
                        logger.warning(f"Skipping potentially unsafe path in ZIP: {member}")
                        continue
                    z.extract(member, docs_path)
        elif doc_files:
            categories_used = set()
            for doc_file in doc_files:
                if doc_file.filename:
                    relative_path = path_map.get(doc_file.filename, doc_file.filename)
                    category = category_map.get(relative_path, category_map.get(doc_file.filename, 'uncategorized'))
                    categories_used.add(category)
                    cat_dir = docs_path / category
                    cat_dir.mkdir(exist_ok=True)
                    doc_file.save(str(cat_dir / doc_file.filename))
        
        folder_mappings = []
        for subdir in docs_path.iterdir():
            if subdir.is_dir():
                folder_mappings.append(FolderMapping(
                    source_path=subdir,
                    category=subdir.name
                ))
        
        if not folder_mappings:
            folder_mappings.append(FolderMapping(
                source_path=docs_path,
                category='uncategorized'
            ))
        
        vault_id_str = request.form.get('vault_id') or str(uuid.uuid4())
        sync_extract = request.form.get('sync_extract', 'true').lower() == 'true'

        result = upload_corpus(
            vault_id=vault_id_str,
            corpus_name=vault_name,
            anchor_org=anchor_org or vault_name,
            folder_mappings=folder_mappings,
            question_file=q_path,
            sync_extract=sync_extract,
            user=request.form.get('user', 'api')
        )
        
        return _upload_result_response(result)


def _upload_result_response(result):
    """Convert UploadResult to JSON response."""
    if result.success:
        return jsonify({
            'success': True,
            'vault_id': result.vault_id,
            'corpus_name': result.corpus_name,
            'document_count': result.document_count,
            'question_count': result.question_count,
            'manifest_path': str(result.manifest_path) if result.manifest_path else None,
            'extraction_status': result.extraction_status
        })
    else:
        return jsonify({
            'success': False,
            'errors': result.errors
        }), 400


@corpus_bp.route('/<corpus_name>/manifest', methods=['GET'])
def api_get_manifest(corpus_name: str):
    """Get manifest for a corpus."""
    try:
        from .normalizer import slugify
        
        config = get_corpus_config(corpus_name)
        if not config:
            return jsonify({
                'success': False,
                'error': f"Corpus '{corpus_name}' not found"
            }), 404
        
        slug = slugify(corpus_name)
        manifest_path = Path(f"test_questions/{slug}_manifest.json")
        
        manifest = load_manifest(manifest_path)
        if not manifest:
            return jsonify({
                'success': False,
                'error': "Manifest not found"
            }), 404
        
        return jsonify({
            'success': True,
            'manifest': manifest
        })
    except Exception as e:
        logger.exception(f"Error getting manifest for {corpus_name}")
        return jsonify({'success': False, 'error': str(e)}), 500


@corpus_bp.route('/create-vault', methods=['POST'])
def api_create_vault():
    """
    Create a new vault from a registered corpus.
    
    Request body:
    {
        "corpus_name": "My Corpus",
        "vault_name": "My Test Vault",
        "auto_extract": true
    }
    """
    from flask import session
    from uuid import UUID as UUIDType
    
    data = request.json
    corpus_name = data.get('corpus_name')
    vault_name = data.get('vault_name')
    auto_extract = data.get('auto_extract', True)
    
    if not corpus_name or not vault_name:
        return jsonify({'success': False, 'error': 'Missing corpus_name or vault_name'}), 400
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    try:
        config = get_corpus_config(corpus_name)
        if not config:
            return jsonify({'success': False, 'error': f'Corpus not found: {corpus_name}'}), 404
        
        from platform_foundation.src.tenant_service import TenantService
        from platform_foundation.src.document_service import DocumentService
        
        ts = TenantService()
        
        new_tenant = ts.create_vault_for_user(
            user_id=UUIDType(user_id),
            name=vault_name
        )
        vault_id = str(new_tenant.get('id', new_tenant.get('tenant_id', '')))
        
        if not vault_id:
            return jsonify({'success': False, 'error': 'Failed to create vault - no ID returned'}), 500
        
        from .normalizer import slugify
        slug = slugify(corpus_name)
        manifest_path = Path(f"test_questions/{slug}_manifest.json")
        manifest = load_manifest(manifest_path)
        
        uploaded_count = 0
        doc_service = DocumentService()
        
        mime_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
        }
        
        excluded_files = {'questions.json', 'manifest.json', 'readme.md', 'readme.txt'}
        excluded_extensions = {'.json', '.log'}
        excluded_folders = {'all docs', 'all_docs', 'duplicates'}
        
        def upload_file(file_path: Path) -> bool:
            """Upload a single file, returns True on success."""
            try:
                if file_path.name.lower() in excluded_files:
                    return False
                if file_path.suffix.lower() in excluded_extensions:
                    return False
                if file_path.name.startswith('.'):
                    return False
                if any(part.lower() in excluded_folders for part in file_path.parts):
                    return False
                    
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                ext = file_path.suffix.lower()
                mime_type = mime_types.get(ext, 'application/octet-stream')
                
                from uuid import UUID as UUIDType

                doc_service.upload_document(
                    tenant_id=UUIDType(vault_id) if isinstance(vault_id, str) else vault_id,
                    filename=file_path.name,
                    mime_type=mime_type,
                    file_content=content,
                    auto_extract=auto_extract
                )
                return True
            except Exception as doc_err:
                logger.error(f"Failed to upload {file_path}: {doc_err}", exc_info=True)
                return False
        
        if manifest and manifest.get('documents'):
            for doc_info in manifest['documents']:
                file_path = Path(doc_info.get('path', ''))
                if file_path.exists() and file_path.is_file():
                    if upload_file(file_path):
                        uploaded_count += 1
        else:
            config = get_corpus_config(corpus_name)
            root_path = config.get('root_path') if config else None
            
            if root_path:
                root_dir = Path(root_path)
                if root_dir.exists():
                    for file_path in root_dir.rglob('*'):
                        if file_path.is_file():
                            if upload_file(file_path):
                                uploaded_count += 1
                    logger.info(f"Uploaded {uploaded_count} documents from root_path: {root_path}")
        
        from .registry import update_corpus_vault
        update_corpus_vault(corpus_name, vault_id)
        
        return jsonify({
            'success': True,
            'vault_id': vault_id,
            'vault_name': vault_name,
            'documents_uploaded': uploaded_count,
            'auto_extract': auto_extract
        })
            
    except Exception as e:
        logger.exception(f"Failed to create vault: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def register_corpus_routes(app):
    """Register corpus routes with Flask app."""
    app.register_blueprint(corpus_bp)
