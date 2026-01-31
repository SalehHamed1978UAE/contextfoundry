"""Folder and question normalization utilities."""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


STANDARD_CATEGORIES = [
    'strategy', 'projects', 'financials', 'compliance',
    'hr', 'technical', 'legal', 'uncategorized'
]

CATEGORY_ALIASES = {
    'all docs': 'uncategorized',
    'all documents': 'uncategorized',
    'documents': 'uncategorized',
    'files': 'uncategorized',
    'strategy documents': 'strategy',
    'strategic': 'strategy',
    'financial reports': 'financials',
    'financial': 'financials',
    'finance': 'financials',
    'project': 'projects',
    'compliance documents': 'compliance',
    'regulatory': 'compliance',
    'human resources': 'hr',
    'personnel': 'hr',
    'tech': 'technical',
    'technology': 'technical',
    'engineering': 'technical',
}


def normalize_folder_name(name: str) -> str:
    """
    Normalize folder name to filesystem-safe category.
    
    Rules:
    - Lowercase
    - Replace spaces and dashes with underscores
    - Strip leading/trailing whitespace
    - Map common aliases to standard categories
    
    Examples:
        normalize_folder_name("All Docs") -> "uncategorized"
        normalize_folder_name("Strategy Documents") -> "strategy"
        normalize_folder_name("My Custom Folder") -> "my_custom_folder"
    """
    name = name.strip().lower()
    
    if name in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[name]
    
    name = re.sub(r'[\s\-]+', '_', name)
    name = re.sub(r'[^a-z0-9_]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    
    return name or 'uncategorized'


def normalize_questions(source_path: Path, dest_path: Path) -> int:
    """
    Normalize questions file to canonical format.
    
    Handles various input formats:
    - Raw array of questions
    - Object with 'questions' key
    - Various field names (query/q/text -> question, answer/a -> expected)
    
    Returns:
        Number of questions in the normalized file
    """
    with open(source_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict) and 'questions' in data:
        questions = data['questions']
    else:
        questions = [data]
    
    normalized = []
    for i, q in enumerate(questions, 1):
        normalized_q = normalize_question(q, i)
        normalized.append(normalized_q)
    
    with open(dest_path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, indent=2)
    
    return len(normalized)


def normalize_question(q: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Normalize a single question to canonical format."""
    result = {}
    
    result['id'] = q.get('id', index)
    
    question_text = (
        q.get('question') or 
        q.get('query') or 
        q.get('q') or 
        q.get('text') or 
        ''
    )
    result['question'] = question_text.strip()
    
    expected_text = (
        q.get('expected') or 
        q.get('answer') or 
        q.get('expected_answer') or 
        q.get('a') or 
        ''
    )
    result['expected'] = expected_text.strip()
    
    if 'category' in q:
        result['category'] = q['category']
    
    if 'difficulty' in q:
        result['difficulty'] = q['difficulty']
    
    if 'tags' in q:
        result['tags'] = q['tags']
    
    return result


def slugify(name: str) -> str:
    """Convert name to filesystem-safe slug."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s_-]', '', slug)
    slug = re.sub(r'[\s-]+', '_', slug)
    slug = re.sub(r'_+', '_', slug)
    return slug.strip('_')
