"""
Document uploader with file filtering logic.

Handles recursive file discovery with include/exclude rules:
- Include: files inside 'documents/' and 'excel_data/' folders
- Exclude: files at root level, README.md, .py files
"""

from pathlib import Path
from typing import List

from .config import load_config, UploadRules


def should_upload(file_path: Path, corpus_root: Path, rules: UploadRules = None, flat_mode: bool = False) -> bool:
    """
    Determine if a file should be uploaded.
    
    Two modes:
    1. Structured mode (flat_mode=False): Only files inside 'documents/' or 'excel_data/' folders
    2. Flat mode (flat_mode=True): Files at any level, with exclusions for test/metadata files
    
    ALWAYS EXCLUDE:
    - README.md anywhere
    - .py files anywhere  
    - .json files (metadata files)
    - Question bank files (question_bank*.md, qa_test_set*.md, qa_pairs*)
    - Ambiguity/consistency files (ambiguity_log*, consistency_validation*)
    """
    if rules is None:
        config = load_config()
        rules = config.upload_rules
    
    try:
        relative = file_path.relative_to(corpus_root)
    except ValueError:
        return False
    
    parts = relative.parts
    file_name_lower = file_path.name.lower()
    
    # Always exclude certain file types
    if file_path.suffix.lower() == '.py':
        return False
    
    if file_path.suffix.lower() == '.json':
        return False
    
    # Exclude specific files by name pattern
    exclude_patterns = [
        'readme', 'question_bank', 'qa_test_set', 'qa_pairs',
        'ambiguity_log', 'consistency_validation', 'data_consistency',
        'document_index'
    ]
    for pattern in exclude_patterns:
        if file_name_lower.startswith(pattern):
            return False
    
    # Exclude files in rules.exclude_files
    for exclude_file in rules.exclude_files:
        if file_name_lower == exclude_file.lower():
            return False
    
    # Check file extension
    if file_path.suffix.lower() not in rules.valid_extensions:
        return False
    
    if flat_mode:
        # In flat mode, accept files at any level (with the above exclusions)
        return True
    else:
        # Structured mode: must be inside an allowed subfolder
        if len(parts) < 2:
            return False
        
        top_folder = parts[0].lower()
        allowed_folders = [f.lower() for f in rules.include_folders]
        
        return top_folder in allowed_folders


def get_files_to_upload(corpus_root: Path, rules: UploadRules = None) -> List[Path]:
    """
    Recursively find all files to upload from corpus.
    
    Auto-detects mode:
    - If corpus has 'documents/' or 'excel_data/' subfolders, use structured mode
    - Otherwise, use flat mode (files at root level)
    
    Args:
        corpus_root: Path to corpus directory
        rules: Optional upload rules (loads from config if not provided)
        
    Returns:
        Sorted list of file paths to upload
    """
    if rules is None:
        config = load_config()
        rules = config.upload_rules
    
    corpus_root = Path(corpus_root)
    
    if not corpus_root.exists():
        raise ValueError(f"Corpus root does not exist: {corpus_root}")
    
    # Auto-detect mode: check if structured folders exist
    has_structured_folders = any(
        (corpus_root / folder).is_dir() 
        for folder in rules.include_folders
    )
    
    flat_mode = not has_structured_folders
    
    files = []
    for file_path in corpus_root.rglob('*'):
        if file_path.is_file() and should_upload(file_path, corpus_root, rules, flat_mode):
            files.append(file_path)
    
    return sorted(files)


def summarize_upload_plan(corpus_root: Path, rules: UploadRules = None) -> dict:
    """
    Generate a summary of files to be uploaded.
    
    Returns:
        Dict with file count, breakdown by folder and extension
    """
    files = get_files_to_upload(corpus_root, rules)
    
    by_folder = {}
    by_extension = {}
    
    for f in files:
        relative = f.relative_to(corpus_root)
        top_folder = relative.parts[0] if len(relative.parts) > 0 else "root"
        
        by_folder[top_folder] = by_folder.get(top_folder, 0) + 1
        by_extension[f.suffix.lower()] = by_extension.get(f.suffix.lower(), 0) + 1
    
    return {
        "total_files": len(files),
        "by_folder": by_folder,
        "by_extension": by_extension,
        "files": [str(f) for f in files]
    }
