"""Validation for documents and questions."""
import json
from pathlib import Path
from typing import List, Set, Dict, Any, Tuple


SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', '.md'}

EXCLUDED_FILES = {
    'readme.md', 'readme.txt', 'license.md', 'license.txt',
    'changelog.md', '.ds_store', 'thumbs.db', '.gitignore'
}


def validate_documents(source_path: Path, extensions: Set[str] = None) -> List[str]:
    """
    Validate document folder.
    
    Args:
        source_path: Path to source folder
        extensions: Set of allowed extensions (defaults to SUPPORTED_EXTENSIONS)
    
    Returns:
        List of error messages (empty if valid)
    """
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS
    
    errors = []
    
    if not source_path.exists():
        errors.append(f"Source folder not found: {source_path}")
        return errors
    
    if not source_path.is_dir():
        errors.append(f"Source is not a folder: {source_path}")
        return errors
    
    valid_files = list_valid_documents(source_path, extensions)
    
    if not valid_files:
        errors.append(f"No supported documents found in {source_path}")
        errors.append(f"Supported formats: {', '.join(sorted(extensions))}")
    
    return errors


def list_valid_documents(source_path: Path, extensions: Set[str] = None) -> List[Path]:
    """List all valid documents in source folder."""
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS
    
    valid_files = []
    
    for file in source_path.rglob("*"):
        if not file.is_file():
            continue
        
        if file.name.startswith('.'):
            continue
        
        if file.name.lower() in EXCLUDED_FILES:
            continue
        
        if file.suffix.lower() in extensions:
            valid_files.append(file)
    
    return valid_files


def validate_questions(question_path: Path, require_100: bool = True) -> List[str]:
    """
    Validate questions file.
    
    Args:
        question_path: Path to questions JSON file
        require_100: If True, require exactly 100 questions
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    if not question_path.exists():
        errors.append(f"Question file not found: {question_path}")
        return errors
    
    try:
        with open(question_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in question file: {e}")
        return errors
    except Exception as e:
        errors.append(f"Error reading question file: {e}")
        return errors
    
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict) and 'questions' in data:
        questions = data['questions']
    else:
        errors.append("Question file must be a JSON array or object with 'questions' key")
        return errors
    
    if require_100 and len(questions) != 100:
        errors.append(f"Expected 100 questions, found {len(questions)}")
    
    if len(questions) == 0:
        errors.append("Question file contains no questions")
        return errors
    
    question_errors = validate_question_schema(questions)
    errors.extend(question_errors)
    
    return errors


def validate_question_schema(questions: List[Dict[str, Any]]) -> List[str]:
    """Validate schema of each question."""
    errors = []
    
    question_fields = {'question', 'query', 'q', 'text'}
    expected_fields = {'expected', 'answer', 'expected_answer', 'a'}
    
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            errors.append(f"Question {i} is not an object")
            continue
        
        has_question = bool(question_fields & set(q.keys()))
        has_expected = bool(expected_fields & set(q.keys()))
        
        if not has_question:
            errors.append(f"Question {i} missing question field (expected one of: {', '.join(question_fields)})")
        
        if not has_expected:
            errors.append(f"Question {i} missing expected answer field (expected one of: {', '.join(expected_fields)})")
    
    return errors


def validate_corpus_config(config: Dict[str, Any]) -> List[str]:
    """Validate corpus configuration."""
    errors = []
    
    required = ['vault_name', 'anchor_org']
    for field in required:
        if not config.get(field):
            errors.append(f"Missing required field: {field}")
    
    if not config.get('folder_mappings') and not config.get('doc_folder'):
        errors.append("At least one document folder mapping required")
    
    if not config.get('question_file'):
        errors.append("Question file path required")
    
    return errors
