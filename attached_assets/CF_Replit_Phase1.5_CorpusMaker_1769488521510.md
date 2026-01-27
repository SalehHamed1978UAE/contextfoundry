# Context Foundry: Phase 1.5 - Corpus Maker

## Problem

Each LLM generates corpora with different structures:
- Folder names vary: "All docs", "documents", "files"
- Question files vary: "questions.json", "nexus_100q.json"
- Requires manual config editing every time
- No audit trail of what was uploaded when

## Solution

A vault-aware Corpus Maker with UI, API, and CLI parity that normalizes any input structure into a canonical format.

---

# Part 1: Architecture

## Canonical Folder Structure

```
<vault_root>/
  documents/
    strategy/          # User-defined categories
    projects/
    financials/
    compliance/
    uncategorized/     # Default if no category assigned
  question_sets/
    <corpus_name>_100q.json
  manifest.json        # Checksums and file listing
```

## Data Flow

```
User Input (any structure)
    │
    ▼
┌─────────────────────────────────────┐
│  Corpus Maker UI / CLI / API        │
│  - Vault selection                  │
│  - Folder → category mapping        │
│  - Question file upload             │
│  - Metadata capture                 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Normalization Layer                │
│  - Rename folders to categories     │
│  - Validate question schema         │
│  - Generate manifest with checksums │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Vault Storage                      │
│  - Write to canonical structure     │
│  - Store metadata on tenant record  │
│  - Trigger sync extraction          │
│  - Register in test config          │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Audit Log                          │
│  - Who, when, what, status          │
└─────────────────────────────────────┘
```

---

# Part 2: Requirements

## 2.1 Vault-Aware Upload UI

**Features:**
- Vault selector (existing or create new)
- Display default folder structure
- "Add Folder" button to map local folders
- "Upload Questions" with schema validation
- Summary panel showing final structure before upload
- Block "Finalize" until all validations pass

**Mockup:**
```
┌─────────────────────────────────────────────────────────┐
│  CORPUS MAKER                                           │
├─────────────────────────────────────────────────────────┤
│  Vault: [Select or Create ▼]                            │
│  Corpus Name: [________________________]                │
│  Anchor Org:  [________________________]                │
├─────────────────────────────────────────────────────────┤
│  DOCUMENT FOLDERS                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Source: /Users/x/corpus/All docs                │   │
│  │ → Category: [strategy ▼]                        │   │
│  │ Files: 45 (.pdf, .docx)                         │   │
│  └─────────────────────────────────────────────────┘   │
│  [+ Add Another Folder]                                 │
├─────────────────────────────────────────────────────────┤
│  QUESTION SET                                           │
│  File: questions.json ✓ Valid (100 questions)           │
├─────────────────────────────────────────────────────────┤
│  PREVIEW                                                │
│  documents/                                             │
│    strategy/ (45 files)                                 │
│  question_sets/                                         │
│    nexus_industries_100q.json                           │
├─────────────────────────────────────────────────────────┤
│  [Cancel]                              [Finalize Upload]│
└─────────────────────────────────────────────────────────┘
```

## 2.2 Folder Normalization Rules

| User Input | Normalized Output |
|------------|-------------------|
| "All docs" | `documents/uncategorized/` |
| "Strategy Documents" | `documents/strategy/` |
| "Financial Reports" | `documents/financials/` |
| User-defined "my_category" | `documents/my_category/` |

**Standard categories** (suggested, not enforced):
- `strategy`, `projects`, `financials`, `compliance`, `hr`, `technical`, `legal`

**Rules:**
- Folder names lowercase, underscores for spaces
- Nested source folders flattened into single category
- Hidden files (`.DS_Store`, etc.) excluded
- README files excluded

## 2.3 Metadata Capture

**Required fields:**
- Corpus name
- Anchor organization
- Question set file path

**Stored on tenant record:**
```json
{
  "tenant_id": "abc-123",
  "metadata": {
    "corpus_name": "ClaudeCode Nexus Industries",
    "anchor_organization": "Nexus Industries",
    "question_file": "nexus_industries_100q.json",
    "document_count": 100,
    "question_count": 100,
    "created_at": "2026-01-27T12:00:00Z",
    "created_by": "user@example.com"
  }
}
```

## 2.4 Validation

**Pre-upload checks:**

| Check | Requirement | Error Message |
|-------|-------------|---------------|
| Documents exist | ≥1 file in mapped folders | "No documents found in source folders" |
| Supported formats | .pdf, .docx, .xlsx, .csv, .txt, .md | "Unsupported file type: .xyz" |
| Question file exists | File readable | "Question file not found" |
| Question schema | Valid JSON array | "Invalid JSON in question file" |
| Question count | Exactly 100 entries | "Expected 100 questions, found N" |
| Question fields | Each has `id`, `question`, `expected` | "Question N missing required field: X" |

**Question schema:**
```json
[
  {
    "id": 1,
    "question": "Who is the CEO of Nexus Industries?",
    "expected": "Dr. Victoria Chen",
    "category": "role",        // optional
    "difficulty": "easy"       // optional
  }
]
```

## 2.5 Automation Hooks

After successful upload:

1. **Trigger sync extraction** for all documents
2. **Register question set** in `test_config.json`
3. **Update corpus registry** (list of available corpora)
4. **Return status** with vault ID and extraction results

## 2.6 CLI / API Parity

Both interfaces use identical normalization and validation logic.

**CLI:**
```bash
python -m src.corpus_maker upload \
    --vault-name "ClaudeCode Nexus Industries" \
    --anchor-org "Nexus Industries" \
    --doc-folder "/local/path/All docs:strategy" \
    --doc-folder "/local/path/Reports:financials" \
    --question-file "/local/path/questions.json" \
    --sync-extract
```

**API:**
```
POST /api/corpus/upload
Content-Type: multipart/form-data

{
  "vault_name": "ClaudeCode Nexus Industries",
  "anchor_org": "Nexus Industries",
  "folder_mappings": [
    {"source": "All docs", "category": "strategy"},
    {"source": "Reports", "category": "financials"}
  ],
  "question_file": <file>,
  "documents": <zip>,
  "sync_extract": true
}
```

## 2.7 Versioning & Checksums

**Manifest file** (`manifest.json`):
```json
{
  "corpus_name": "ClaudeCode Nexus Industries",
  "created_at": "2026-01-27T12:00:00Z",
  "created_by": "user@example.com",
  "documents": [
    {
      "source_path": "/local/All docs/strategy_memo.pdf",
      "dest_path": "documents/strategy/strategy_memo.pdf",
      "sha256": "abc123...",
      "size_bytes": 102400
    }
  ],
  "question_set": {
    "source_path": "/local/questions.json",
    "dest_path": "question_sets/nexus_industries_100q.json",
    "sha256": "def456...",
    "question_count": 100
  },
  "total_documents": 100,
  "total_size_bytes": 15728640
}
```

**Use cases:**
- Verify corpus hasn't changed unexpectedly
- Enable deterministic rebuilds
- Diff between corpus versions

## 2.8 Audit Log

**Log entry:**
```json
{
  "timestamp": "2026-01-27T12:00:00Z",
  "action": "corpus_upload",
  "user": "user@example.com",
  "vault_id": "abc-123",
  "corpus_name": "ClaudeCode Nexus Industries",
  "document_count": 100,
  "question_count": 100,
  "extraction_status": "completed",
  "duration_seconds": 120
}
```

**Stored in:** `platform.audit_log` table or dedicated log service

---

# Part 3: Implementation

## 3.1 File Structure

```
src/corpus_maker/
    __init__.py
    cli.py              # CLI entry point
    api.py              # API endpoint handlers
    uploader.py         # Core upload logic
    normalizer.py       # Folder/file normalization
    validator.py        # Schema and content validation
    manifest.py         # Checksum and manifest generation
    registry.py         # Test config registration
```

## 3.2 Core: `uploader.py`

```python
"""Core corpus upload logic shared by CLI and API."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from .normalizer import normalize_folder_name, normalize_questions
from .validator import validate_documents, validate_questions
from .manifest import generate_manifest
from .registry import register_corpus


@dataclass
class FolderMapping:
    source_path: Path
    category: str


@dataclass
class UploadResult:
    success: bool
    vault_id: str
    corpus_name: str
    document_count: int
    question_count: int
    manifest_path: Path
    errors: List[str]
    extraction_status: Optional[str] = None


SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', '.md'}


def upload_corpus(
    vault_id: str,
    corpus_name: str,
    anchor_org: str,
    folder_mappings: List[FolderMapping],
    question_file: Path,
    sync_extract: bool = True,
    user: str = "system"
) -> UploadResult:
    """
    Upload and normalize a corpus to a vault.

    Args:
        vault_id: Target vault ID
        corpus_name: Human-readable corpus name
        anchor_org: Anchor organization for queries
        folder_mappings: List of source folder → category mappings
        question_file: Path to questions JSON
        sync_extract: If True, run extraction synchronously
        user: User performing upload (for audit)

    Returns:
        UploadResult with status and details
    """
    errors = []
    slug = slugify(corpus_name)

    # Get vault root path
    vault_root = get_vault_root(vault_id)
    docs_dir = vault_root / "documents"
    questions_dir = vault_root / "question_sets"

    # Create directories
    docs_dir.mkdir(parents=True, exist_ok=True)
    questions_dir.mkdir(parents=True, exist_ok=True)

    # 1. Validate inputs
    for mapping in folder_mappings:
        doc_errors = validate_documents(mapping.source_path, SUPPORTED_EXTENSIONS)
        errors.extend(doc_errors)

    question_errors = validate_questions(question_file)
    errors.extend(question_errors)

    if errors:
        return UploadResult(
            success=False,
            vault_id=vault_id,
            corpus_name=corpus_name,
            document_count=0,
            question_count=0,
            manifest_path=None,
            errors=errors
        )

    # 2. Copy and normalize documents
    all_documents = []
    for mapping in folder_mappings:
        category = normalize_folder_name(mapping.category)
        category_dir = docs_dir / category
        category_dir.mkdir(exist_ok=True)

        documents = copy_documents(
            source=mapping.source_path,
            dest=category_dir,
            extensions=SUPPORTED_EXTENSIONS
        )
        all_documents.extend(documents)

    # 3. Normalize and copy questions
    questions_dest = questions_dir / f"{slug}_100q.json"
    question_count = normalize_questions(question_file, questions_dest)

    # 4. Generate manifest
    manifest = generate_manifest(
        corpus_name=corpus_name,
        documents=all_documents,
        question_file=questions_dest,
        user=user
    )
    manifest_path = vault_root / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # 5. Update tenant metadata
    update_tenant_metadata(
        vault_id=vault_id,
        metadata={
            "corpus_name": corpus_name,
            "anchor_organization": anchor_org,
            "question_file": f"{slug}_100q.json",
            "document_count": len(all_documents),
            "question_count": question_count,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": user
        }
    )

    # 6. Register in test config
    register_corpus(
        corpus_name=corpus_name,
        vault_id=vault_id,
        questions_file=f"{slug}_100q.json",
        anchor_org=anchor_org
    )

    # 7. Trigger extraction
    extraction_status = None
    if sync_extract:
        extraction_status = trigger_extraction(vault_id, sync=True)

    # 8. Audit log
    log_audit(
        action="corpus_upload",
        user=user,
        vault_id=vault_id,
        corpus_name=corpus_name,
        document_count=len(all_documents),
        question_count=question_count,
        extraction_status=extraction_status
    )

    return UploadResult(
        success=True,
        vault_id=vault_id,
        corpus_name=corpus_name,
        document_count=len(all_documents),
        question_count=question_count,
        manifest_path=manifest_path,
        errors=[],
        extraction_status=extraction_status
    )


def copy_documents(source: Path, dest: Path, extensions: set) -> List[dict]:
    """Copy documents from source to dest, return list with metadata."""
    documents = []

    for file in source.rglob("*"):
        if file.suffix.lower() not in extensions:
            continue
        if file.name.startswith('.'):
            continue
        if file.name.lower() in ('readme.md', 'readme.txt'):
            continue

        dest_file = dest / file.name

        # Handle duplicates
        counter = 1
        while dest_file.exists():
            stem = file.stem
            dest_file = dest / f"{stem}_{counter}{file.suffix}"
            counter += 1

        shutil.copy2(file, dest_file)

        documents.append({
            "source_path": str(file),
            "dest_path": str(dest_file),
            "sha256": compute_sha256(dest_file),
            "size_bytes": dest_file.stat().st_size
        })

    return documents


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def slugify(name: str) -> str:
    """Convert name to filesystem-safe slug."""
    return name.lower().replace(' ', '_').replace('-', '_')


def get_vault_root(vault_id: str) -> Path:
    """Get filesystem root for vault."""
    # Implementation depends on storage backend
    return Path(f"/data/vaults/{vault_id}")


def update_tenant_metadata(vault_id: str, metadata: dict):
    """Update tenant record with corpus metadata."""
    # Implementation: UPDATE tenants SET metadata = ... WHERE id = vault_id
    pass


def trigger_extraction(vault_id: str, sync: bool = True) -> str:
    """Trigger extraction for all documents in vault."""
    from platform_foundation.src.document_service import DocumentService

    ds = DocumentService()
    docs = ds.list_documents(vault_id)

    for doc in docs:
        ds.trigger_extraction(doc['id'], sync_extract=sync)

    return "completed" if sync else "queued"


def log_audit(action: str, user: str, **kwargs):
    """Log action to audit table."""
    # Implementation: INSERT INTO platform.audit_log ...
    pass
```

## 3.3 Validator: `validator.py`

```python
"""Validation for documents and questions."""
import json
from pathlib import Path
from typing import List, Set


def validate_documents(source_path: Path, extensions: Set[str]) -> List[str]:
    """Validate document folder. Returns list of errors."""
    errors = []

    if not source_path.exists():
        errors.append(f"Source folder not found: {source_path}")
        return errors

    if not source_path.is_dir():
        errors.append(f"Source is not a folder: {source_path}")
        return errors

    # Check for at least one valid document
    valid_files = []
    for file in source_path.rglob("*"):
        if file.is_file() and file.suffix.lower() in extensions:
            valid_files.append(file)

    if not valid_files:
        errors.append(f"No supported documents found in {source_path}")

    # Check for unsupported files (warning only)
    for file in source_path.rglob("*"):
        if file.is_file() and file.suffix.lower() not in extensions:
            if not file.name.startswith('.') and file.name.lower() not in ('readme.md', 'readme.txt'):
                pass  # Could add warning

    return errors


def validate_questions(question_path: Path) -> List[str]:
    """Validate questions file. Returns list of errors."""
    errors = []

    if not question_path.exists():
        errors.append(f"Question file not found: {question_path}")
        return errors

    # Load JSON
    try:
        with open(question_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in question file: {e}")
        return errors

    # Extract questions list
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict) and 'questions' in data:
        questions = data['questions']
    else:
        errors.append("Question file must be a JSON array or object with 'questions' key")
        return errors

    # Check count
    if len(questions) != 100:
        errors.append(f"Expected 100 questions, found {len(questions)}")

    # Check each question
    required_fields = {'question', 'expected'}
    alt_fields = {
        'question': ['query', 'q', 'text'],
        'expected': ['answer', 'expected_answer', 'a']
    }

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            errors.append(f"Question {i+1} is not an object")
            continue

        for field in required_fields:
            if field not in q:
                # Check alternatives
                found = False
                for alt in alt_fields.get(field, []):
                    if alt in q:
                        found = True
                        break
                if not found:
                    errors.append(f"Question {i+1} missing required field: {field}")

    return errors
```

## 3.4 CLI: `cli.py`

```python
#!/usr/bin/env python3
"""
Corpus Maker CLI.

Usage:
    python -m src.corpus_maker upload \
        --vault-name "My Corpus" \
        --anchor-org "My Org" \
        --doc-folder "/path/to/docs:category" \
        --question-file "/path/to/questions.json"
"""
import argparse
import sys
from pathlib import Path

from .uploader import upload_corpus, FolderMapping


def parse_folder_mapping(value: str) -> FolderMapping:
    """Parse 'path:category' into FolderMapping."""
    if ':' in value:
        path, category = value.rsplit(':', 1)
    else:
        path = value
        category = "uncategorized"

    return FolderMapping(source_path=Path(path), category=category)


def cmd_upload(args):
    """Handle upload command."""
    # Parse folder mappings
    mappings = [parse_folder_mapping(f) for f in args.doc_folder]

    # Get or create vault
    if args.vault_id:
        vault_id = args.vault_id
    else:
        vault_id = create_vault(args.vault_name)

    # Upload
    result = upload_corpus(
        vault_id=vault_id,
        corpus_name=args.vault_name,
        anchor_org=args.anchor_org,
        folder_mappings=mappings,
        question_file=Path(args.question_file),
        sync_extract=args.sync_extract,
        user=args.user or "cli"
    )

    # Output
    if result.success:
        print("\n" + "=" * 50)
        print("CORPUS UPLOADED SUCCESSFULLY")
        print("=" * 50)
        print(f"Vault ID:    {result.vault_id}")
        print(f"Corpus:      {result.corpus_name}")
        print(f"Documents:   {result.document_count}")
        print(f"Questions:   {result.question_count}")
        print(f"Manifest:    {result.manifest_path}")
        print(f"Extraction:  {result.extraction_status}")
        print("=" * 50)
    else:
        print("\nERRORS:")
        for error in result.errors:
            print(f"  - {error}")
        sys.exit(1)


def create_vault(name: str) -> str:
    """Create a new vault."""
    from src.test_runner.vault_manager import VaultManager
    from src.test_runner.config import TestConfig

    config = TestConfig()
    vm = VaultManager(config.api_base_url)
    vm.authenticate_dev()
    return vm.ensure_clean_vault(name)


def main():
    parser = argparse.ArgumentParser(description="Corpus Maker")
    subparsers = parser.add_subparsers(dest='command')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a corpus')
    upload_parser.add_argument('--vault-name', required=True, help='Corpus/vault name')
    upload_parser.add_argument('--vault-id', help='Existing vault ID (optional)')
    upload_parser.add_argument('--anchor-org', required=True, help='Anchor organization')
    upload_parser.add_argument('--doc-folder', action='append', required=True,
                               help='Document folder (format: path:category)')
    upload_parser.add_argument('--question-file', required=True, help='Questions JSON file')
    upload_parser.add_argument('--sync-extract', action='store_true', default=True,
                               help='Run extraction synchronously')
    upload_parser.add_argument('--no-extract', action='store_true',
                               help='Skip extraction')
    upload_parser.add_argument('--user', help='User performing upload')
    upload_parser.set_defaults(func=cmd_upload)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.no_extract:
        args.sync_extract = False

    args.func(args)


if __name__ == '__main__':
    main()
```

## 3.5 API: `api.py`

```python
"""API endpoint for corpus upload."""
from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
import tempfile
import zipfile
from pathlib import Path

from .uploader import upload_corpus, FolderMapping
from .validator import validate_questions

corpus_bp = Blueprint('corpus', __name__, url_prefix='/api/corpus')


@corpus_bp.route('/upload', methods=['POST'])
def upload():
    """
    Upload a corpus.

    Expects multipart form:
        - vault_name: str
        - anchor_org: str
        - folder_mappings: JSON array of {source, category}
        - question_file: file
        - documents: zip file
        - sync_extract: bool (optional, default true)
    """
    # Parse form data
    vault_name = request.form.get('vault_name')
    anchor_org = request.form.get('anchor_org')
    folder_mappings_json = request.form.get('folder_mappings', '[]')
    sync_extract = request.form.get('sync_extract', 'true').lower() == 'true'

    if not vault_name or not anchor_org:
        return jsonify({"error": "vault_name and anchor_org required"}), 400

    # Handle file uploads
    if 'question_file' not in request.files:
        return jsonify({"error": "question_file required"}), 400

    if 'documents' not in request.files:
        return jsonify({"error": "documents zip required"}), 400

    question_file = request.files['question_file']
    documents_zip = request.files['documents']

    # Save to temp location
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Save question file
        question_path = tmpdir / secure_filename(question_file.filename)
        question_file.save(question_path)

        # Extract documents zip
        docs_path = tmpdir / "documents"
        docs_path.mkdir()
        zip_path = tmpdir / "documents.zip"
        documents_zip.save(zip_path)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(docs_path)

        # Parse folder mappings
        import json
        mappings_data = json.loads(folder_mappings_json)
        mappings = []
        for m in mappings_data:
            source = docs_path / m.get('source', '')
            if source.exists():
                mappings.append(FolderMapping(
                    source_path=source,
                    category=m.get('category', 'uncategorized')
                ))

        # If no mappings, use root
        if not mappings:
            mappings = [FolderMapping(source_path=docs_path, category='uncategorized')]

        # Create vault
        vault_id = create_vault(vault_name)

        # Upload
        result = upload_corpus(
            vault_id=vault_id,
            corpus_name=vault_name,
            anchor_org=anchor_org,
            folder_mappings=mappings,
            question_file=question_path,
            sync_extract=sync_extract,
            user=g.get('user', 'api')
        )

    if result.success:
        return jsonify({
            "success": True,
            "vault_id": result.vault_id,
            "corpus_name": result.corpus_name,
            "document_count": result.document_count,
            "question_count": result.question_count,
            "extraction_status": result.extraction_status
        })
    else:
        return jsonify({
            "success": False,
            "errors": result.errors
        }), 400


def create_vault(name: str) -> str:
    """Create a new vault."""
    from src.test_runner.vault_manager import VaultManager
    from src.test_runner.config import TestConfig

    config = TestConfig()
    vm = VaultManager(config.api_base_url)
    vm.authenticate_dev()
    return vm.ensure_clean_vault(name)
```

## 3.6 Registry: `registry.py`

```python
"""Register corpus in test configuration."""
import json
from pathlib import Path

CONFIG_FILE = Path("src/test_config.json")


def register_corpus(
    corpus_name: str,
    vault_id: str,
    questions_file: str,
    anchor_org: str
):
    """Register corpus in test_config.json."""

    # Load existing config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {"corpora": {}}

    # Add/update corpus entry
    config.setdefault('corpora', {})
    config['corpora'][corpus_name] = {
        "root_path": f"/data/vaults/{vault_id}",
        "questions_file": questions_file,
        "anchor_organization": anchor_org,
        "current_vault_id": vault_id,
        "last_run": None,
        "last_accuracy": None
    }

    # Write back
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
```

## 3.7 Manifest: `manifest.py`

```python
"""Generate manifest with checksums."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List


def generate_manifest(
    corpus_name: str,
    documents: List[dict],
    question_file: Path,
    user: str
) -> dict:
    """Generate manifest.json content."""

    # Compute question file hash
    question_hash = compute_sha256(question_file)
    with open(question_file, 'r') as f:
        question_count = len(json.load(f))

    return {
        "corpus_name": corpus_name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "created_by": user,
        "documents": documents,
        "question_set": {
            "dest_path": str(question_file),
            "sha256": question_hash,
            "question_count": question_count
        },
        "total_documents": len(documents),
        "total_size_bytes": sum(d.get('size_bytes', 0) for d in documents)
    }


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

---

# Part 4: Front-End Implementation

## 4.1 React Component Structure

```
src/components/corpus_maker/
    CorpusMakerPage.tsx       # Main page
    VaultSelector.tsx          # Vault dropdown + create
    FolderMapper.tsx           # Drag-drop folder mapping
    QuestionUploader.tsx       # Question file upload + validation
    PreviewPanel.tsx           # Final structure preview
    ProgressIndicator.tsx      # Upload/extraction progress
```

## 4.2 Key UI States

1. **Initial** - Empty form, vault selector
2. **Mapping** - User adding folders, assigning categories
3. **Validating** - Checking files and questions
4. **Ready** - All validations pass, "Finalize" enabled
5. **Uploading** - Progress bar, file upload
6. **Extracting** - Extraction progress
7. **Complete** - Success summary with vault ID

---

# Part 5: Testing

## 5.1 Unit Tests

```python
"""tests/unit/test_corpus_maker.py"""
import pytest
import json
from pathlib import Path


class TestValidator:
    def test_validates_question_count(self, tmp_path):
        from src.corpus_maker.validator import validate_questions

        # Create file with 50 questions (should fail)
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"question": f"Q{i}?", "expected": f"A{i}"} for i in range(50)
        ]))

        errors = validate_questions(q_file)
        assert any("100 questions" in e for e in errors)

    def test_validates_required_fields(self, tmp_path):
        from src.corpus_maker.validator import validate_questions

        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"question": "Q1?"}  # Missing expected
        ] * 100))

        errors = validate_questions(q_file)
        assert any("expected" in e for e in errors)


class TestNormalizer:
    def test_normalizes_folder_names(self):
        from src.corpus_maker.normalizer import normalize_folder_name

        assert normalize_folder_name("All Docs") == "all_docs"
        assert normalize_folder_name("Strategy-Documents") == "strategy_documents"
        assert normalize_folder_name("  spaces  ") == "spaces"


class TestManifest:
    def test_generates_checksums(self, tmp_path):
        from src.corpus_maker.manifest import compute_sha256

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        hash1 = compute_sha256(test_file)
        hash2 = compute_sha256(test_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
```

## 5.2 Integration Test

```python
"""tests/integration/test_corpus_upload.py"""
import pytest
from pathlib import Path


class TestCorpusUpload:
    def test_end_to_end_upload(self, tmp_path):
        """Full upload flow with temp files."""
        from src.corpus_maker.uploader import upload_corpus, FolderMapping

        # Create test documents
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test1.pdf").write_bytes(b"%PDF-1.4 test")
        (docs_dir / "test2.docx").write_bytes(b"PK test")

        # Create test questions
        q_file = tmp_path / "questions.json"
        q_file.write_text(json.dumps([
            {"id": i, "question": f"Q{i}?", "expected": f"A{i}"}
            for i in range(1, 101)
        ]))

        # Upload (without extraction for test speed)
        result = upload_corpus(
            vault_id="test-vault-123",
            corpus_name="Test Corpus",
            anchor_org="Test Org",
            folder_mappings=[FolderMapping(docs_dir, "test_category")],
            question_file=q_file,
            sync_extract=False
        )

        assert result.success
        assert result.document_count == 2
        assert result.question_count == 100
```

---

# Part 6: Usage Examples

## Add corpus via CLI

```bash
# Single folder, default category
python -m src.corpus_maker upload \
    --vault-name "ClaudeCode Nexus Industries" \
    --anchor-org "Nexus Industries" \
    --doc-folder "/Users/x/corpus/All docs" \
    --question-file "/Users/x/corpus/questions.json"

# Multiple folders with categories
python -m src.corpus_maker upload \
    --vault-name "Enterprise Corpus" \
    --anchor-org "Acme Corp" \
    --doc-folder "/path/strategy:strategy" \
    --doc-folder "/path/financials:financials" \
    --doc-folder "/path/other:uncategorized" \
    --question-file "/path/questions.json"

# Skip extraction (just organize files)
python -m src.corpus_maker upload \
    --vault-name "Quick Test" \
    --anchor-org "Test" \
    --doc-folder "/path/docs" \
    --question-file "/path/q.json" \
    --no-extract
```

## After upload, run tests

```bash
# Corpus is auto-registered, just run:
python -m src.test_runner.runner --corpus "ClaudeCode Nexus Industries"
```

---

# Summary

| Component | Purpose |
|-----------|---------|
| `uploader.py` | Core logic: copy, normalize, manifest, extract |
| `validator.py` | Pre-upload validation |
| `normalizer.py` | Folder/question normalization |
| `manifest.py` | Checksums and versioning |
| `registry.py` | Test config registration |
| `cli.py` | Command-line interface |
| `api.py` | REST API endpoint |
| UI components | React front-end |

**Result**: One command (or UI flow) to add any corpus, regardless of source structure, with full audit trail and automatic test registration.
