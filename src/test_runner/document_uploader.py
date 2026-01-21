from pathlib import Path
from typing import List, Dict

def should_upload(file_path: Path, corpus_root: Path, rules: Dict) -> bool:
    """
    Determine if a file should be uploaded.
    
    INCLUDE:
    - Files inside specified folders (e.g., 'documents/', 'excel_data/')
    - Root-level files with allowed extensions (e.g., company_profile.md)
    
    EXCLUDE:
    - Files in exclude_files list (e.g., README.md, qa_pairs.md)
    - .py files anywhere
    """
    relative = file_path.relative_to(corpus_root)
    parts = relative.parts
    
    exclude_files = [f.lower() for f in rules.get('exclude_files', ['README.md'])]
    if file_path.name.lower() in exclude_files:
        return False
    
    valid_extensions = rules.get('valid_extensions', ['.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', '.md'])
    if file_path.suffix.lower() not in valid_extensions:
        return False
    
    if len(parts) == 1:
        root_extensions = [e.lower() for e in rules.get('include_root_extensions', [])]
        return file_path.suffix.lower() in root_extensions
    
    top_folder = parts[0].lower()
    allowed_folders = [f.lower() for f in rules.get('include_folders', ['documents', 'excel_data'])]
    
    return top_folder in allowed_folders


def get_files_to_upload(corpus_root: Path, rules: Dict) -> List[Path]:
    """Recursively find all files to upload from corpus."""
    files = []
    for file_path in corpus_root.rglob('*'):
        if file_path.is_file() and should_upload(file_path, corpus_root, rules):
            files.append(file_path)
    
    return sorted(files)
