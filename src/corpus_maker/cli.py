#!/usr/bin/env python3
"""
Corpus Maker CLI.

Usage:
    python -m src.corpus_maker upload \
        --vault-name "My Corpus" \
        --anchor-org "My Org" \
        --doc-folder "/path/to/docs:category" \
        --question-file "/path/to/questions.json"
        
    python -m src.corpus_maker list
    
    python -m src.corpus_maker validate \
        --doc-folder "/path/to/docs" \
        --question-file "/path/to/questions.json"
"""
import argparse
import json
import sys
import uuid
import logging
from pathlib import Path
from typing import List

from .uploader import upload_corpus, FolderMapping
from .validator import validate_documents, validate_questions, SUPPORTED_EXTENSIONS
from .registry import list_corpora, get_corpus_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_folder_mapping(value: str) -> FolderMapping:
    """
    Parse 'path:category' into FolderMapping.
    
    Examples:
        "/path/to/docs" -> FolderMapping(source_path="/path/to/docs", category="uncategorized")
        "/path/to/docs:strategy" -> FolderMapping(source_path="/path/to/docs", category="strategy")
    """
    if ':' in value and not value.startswith('/') or value.count(':') > 1:
        parts = value.rsplit(':', 1)
        path = parts[0]
        category = parts[1] if len(parts) > 1 else "uncategorized"
    else:
        path = value
        category = "uncategorized"
    
    return FolderMapping(source_path=Path(path), category=category)


def cmd_upload(args) -> int:
    """Handle upload command."""
    mappings = [parse_folder_mapping(f) for f in args.doc_folder]
    
    if args.vault_id:
        vault_id = args.vault_id
    else:
        vault_id = str(uuid.uuid4())
    
    result = upload_corpus(
        vault_id=vault_id,
        corpus_name=args.vault_name,
        anchor_org=args.anchor_org,
        folder_mappings=mappings,
        question_file=Path(args.question_file),
        sync_extract=not args.no_extract and args.sync_extract,
        skip_extraction=args.no_extract,
        user=args.user or "cli"
    )
    
    if result.success:
        print("\n" + "=" * 60)
        print("CORPUS UPLOADED SUCCESSFULLY")
        print("=" * 60)
        print(f"Vault ID:     {result.vault_id}")
        print(f"Corpus:       {result.corpus_name}")
        print(f"Documents:    {result.document_count}")
        print(f"Questions:    {result.question_count}")
        print(f"Manifest:     {result.manifest_path}")
        if result.extraction_status:
            print(f"Extraction:   {result.extraction_status}")
        print("=" * 60)
        print("\nTo run tests:")
        print(f'  python -m src.test_runner.runner --corpus "{result.corpus_name}"')
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("UPLOAD FAILED")
        print("=" * 60)
        for error in result.errors:
            print(f"  ERROR: {error}")
        print("=" * 60)
        return 1


def cmd_validate(args) -> int:
    """Handle validate command."""
    all_errors = []
    
    if args.doc_folder:
        for folder_spec in args.doc_folder:
            mapping = parse_folder_mapping(folder_spec)
            errors = validate_documents(mapping.source_path, SUPPORTED_EXTENSIONS)
            if errors:
                all_errors.extend(errors)
            else:
                print(f"Documents valid: {mapping.source_path}")
    
    if args.question_file:
        errors = validate_questions(Path(args.question_file))
        if errors:
            all_errors.extend(errors)
        else:
            print(f"Questions valid: {args.question_file}")
    
    if all_errors:
        print("\nValidation errors:")
        for error in all_errors:
            print(f"  ERROR: {error}")
        return 1
    
    print("\nAll validations passed!")
    return 0


def cmd_list(args) -> int:
    """Handle list command."""
    corpora = list_corpora()
    
    if not corpora:
        print("No corpora registered.")
        return 0
    
    print("\n" + "=" * 80)
    print("REGISTERED CORPORA")
    print("=" * 80)
    
    for name, config in corpora.items():
        print(f"\n{name}")
        print("-" * len(name))
        print(f"  Vault ID:      {config.get('vault_id', 'N/A')}")
        print(f"  Anchor Org:    {config.get('anchor_org', 'N/A')}")
        print(f"  Documents:     {config.get('document_count', 'N/A')}")
        print(f"  Questions:     {config.get('question_count', 'N/A')}")
        print(f"  Last Run:      {config.get('last_run', 'Never')}")
        print(f"  Last Accuracy: {config.get('last_accuracy', 'N/A')}")
    
    print("\n" + "=" * 80)
    return 0


def cmd_info(args) -> int:
    """Handle info command for single corpus."""
    config = get_corpus_config(args.corpus_name)
    
    if not config:
        print(f"Corpus '{args.corpus_name}' not found.")
        return 1
    
    print(json.dumps(config, indent=2))
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Corpus Maker - Upload and manage test corpora",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a corpus with single folder
  python -m src.corpus_maker upload \\
      --vault-name "ClaudeCode Nexus Industries" \\
      --anchor-org "Nexus Industries" \\
      --doc-folder "/path/to/All docs" \\
      --question-file "/path/to/questions.json"

  # Upload with categorized folders
  python -m src.corpus_maker upload \\
      --vault-name "Enterprise Corpus" \\
      --anchor-org "Acme Corp" \\
      --doc-folder "/path/strategy:strategy" \\
      --doc-folder "/path/financials:financials" \\
      --question-file "/path/questions.json"

  # List all registered corpora
  python -m src.corpus_maker list

  # Validate files before upload
  python -m src.corpus_maker validate \\
      --doc-folder "/path/to/docs" \\
      --question-file "/path/to/questions.json"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    upload_parser = subparsers.add_parser('upload', help='Upload a new corpus')
    upload_parser.add_argument('--vault-name', required=True,
                               help='Human-readable corpus/vault name')
    upload_parser.add_argument('--vault-id', 
                               help='Existing vault ID (creates new if not specified)')
    upload_parser.add_argument('--anchor-org', required=True,
                               help='Anchor organization for queries')
    upload_parser.add_argument('--doc-folder', action='append', required=True,
                               help='Document folder (format: /path:category or just /path)')
    upload_parser.add_argument('--question-file', required=True,
                               help='Path to questions JSON file')
    upload_parser.add_argument('--sync-extract', action='store_true', default=True,
                               help='Run extraction synchronously (default)')
    upload_parser.add_argument('--no-extract', action='store_true',
                               help='Skip extraction entirely')
    upload_parser.add_argument('--user', default='cli',
                               help='User identifier for audit log')
    
    validate_parser = subparsers.add_parser('validate', help='Validate files without uploading')
    validate_parser.add_argument('--doc-folder', action='append',
                                 help='Document folder to validate')
    validate_parser.add_argument('--question-file',
                                 help='Question file to validate')
    
    list_parser = subparsers.add_parser('list', help='List registered corpora')
    
    info_parser = subparsers.add_parser('info', help='Show details for a corpus')
    info_parser.add_argument('corpus_name', help='Name of the corpus')
    
    args = parser.parse_args()
    
    if args.command == 'upload':
        return cmd_upload(args)
    elif args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'list':
        return cmd_list(args)
    elif args.command == 'info':
        return cmd_info(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
