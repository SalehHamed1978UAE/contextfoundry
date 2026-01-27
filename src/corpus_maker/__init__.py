"""
Corpus Maker - Vault-aware corpus upload with normalization and validation.

A tool for normalizing any input structure into a canonical format for
knowledge graph Q&A testing.
"""
from .uploader import upload_corpus, FolderMapping, UploadResult
from .validator import validate_documents, validate_questions
from .normalizer import normalize_folder_name, normalize_questions
from .manifest import generate_manifest, compute_sha256
from .registry import register_corpus

__all__ = [
    'upload_corpus',
    'FolderMapping',
    'UploadResult',
    'validate_documents',
    'validate_questions',
    'normalize_folder_name',
    'normalize_questions',
    'generate_manifest',
    'compute_sha256',
    'register_corpus',
]
