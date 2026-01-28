"""Test config registration for corpora."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

TEST_CONFIG_PATH = Path("src/test_config.json")


def register_corpus(
    corpus_name: str,
    vault_id: str,
    questions_file: str,
    anchor_org: str,
    document_count: int = 0,
    question_count: int = 100,
    root_path: Optional[str] = None
) -> bool:
    """
    Register a corpus in test_config.json.
    
    Args:
        corpus_name: Human-readable corpus name (used as key)
        vault_id: UUID of the vault
        questions_file: Filename of questions JSON
        anchor_org: Anchor organization for queries
        document_count: Number of documents in corpus
        question_count: Number of questions (default 100)
        root_path: Path to source documents folder
    
    Returns:
        True if registration successful
    """
    config = load_test_config()
    
    if 'corpora' not in config:
        config['corpora'] = {}
    
    corpus_entry = {
        'vault_id': vault_id,
        'questions_file': questions_file,
        'anchor_org': anchor_org,
        'document_count': document_count,
        'question_count': question_count,
        'registered_at': datetime.utcnow().isoformat() + "Z",
        'last_run': None,
        'last_accuracy': None
    }
    
    if root_path:
        corpus_entry['root_path'] = root_path
    
    config['corpora'][corpus_name] = corpus_entry
    
    save_test_config(config)
    logger.info(f"Registered corpus '{corpus_name}' with vault {vault_id}")
    
    return True


def unregister_corpus(corpus_name: str) -> bool:
    """Remove a corpus from test config."""
    config = load_test_config()
    
    if 'corpora' in config and corpus_name in config['corpora']:
        del config['corpora'][corpus_name]
        save_test_config(config)
        logger.info(f"Unregistered corpus '{corpus_name}'")
        return True
    
    return False


def get_corpus_config(corpus_name: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific corpus."""
    config = load_test_config()
    return config.get('corpora', {}).get(corpus_name)


def list_corpora() -> Dict[str, Dict[str, Any]]:
    """List all registered corpora."""
    config = load_test_config()
    return config.get('corpora', {})


def update_corpus_stats(
    corpus_name: str,
    accuracy: float,
    passed: int,
    total: int
) -> bool:
    """Update corpus with latest test results."""
    config = load_test_config()
    
    if 'corpora' not in config or corpus_name not in config['corpora']:
        logger.warning(f"Corpus '{corpus_name}' not found in config")
        return False
    
    config['corpora'][corpus_name]['last_run'] = datetime.utcnow().isoformat() + "Z"
    config['corpora'][corpus_name]['last_accuracy'] = accuracy
    config['corpora'][corpus_name]['last_passed'] = passed
    config['corpora'][corpus_name]['last_total'] = total
    
    save_test_config(config)
    return True


def load_test_config() -> Dict[str, Any]:
    """Load test configuration from file."""
    if not TEST_CONFIG_PATH.exists():
        return {'corpora': {}}
    
    try:
        with open(TEST_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading test config: {e}")
        return {'corpora': {}}


def save_test_config(config: Dict[str, Any]) -> None:
    """Save test configuration to file."""
    TEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with open(TEST_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def find_corpus_by_vault(vault_id: str) -> Optional[str]:
    """Find corpus name by vault ID."""
    config = load_test_config()
    
    for name, corpus in config.get('corpora', {}).items():
        if corpus.get('vault_id') == vault_id:
            return name
        vault_ids = corpus.get('vault_ids', [])
        if vault_id in vault_ids:
            return name
    
    return None


def update_corpus_root_path(corpus_name: str, root_path: str) -> bool:
    """
    Update the root_path for a corpus.
    
    Args:
        corpus_name: Name of the corpus
        root_path: Path to source documents folder
    
    Returns:
        True if update successful
    """
    config = load_test_config()
    
    if 'corpora' not in config or corpus_name not in config['corpora']:
        logger.warning(f"Corpus '{corpus_name}' not found in config")
        return False
    
    config['corpora'][corpus_name]['root_path'] = root_path
    save_test_config(config)
    logger.info(f"Updated root_path for corpus '{corpus_name}' to {root_path}")
    return True


def update_corpus_vault(corpus_name: str, vault_id: str) -> bool:
    """
    Add a vault ID to a corpus's list of associated vaults.
    Supports multiple vaults per corpus.
    
    Args:
        corpus_name: Name of the corpus
        vault_id: UUID of the new vault
    
    Returns:
        True if update successful
    """
    config = load_test_config()
    
    if 'corpora' not in config or corpus_name not in config['corpora']:
        logger.warning(f"Corpus '{corpus_name}' not found in config")
        return False
    
    corpus = config['corpora'][corpus_name]
    
    if 'vault_ids' not in corpus:
        corpus['vault_ids'] = []
        if corpus.get('vault_id'):
            corpus['vault_ids'].append(corpus['vault_id'])
    
    if vault_id not in corpus['vault_ids']:
        corpus['vault_ids'].append(vault_id)
    
    corpus['vault_id'] = vault_id
    corpus['last_vault_created'] = datetime.utcnow().isoformat() + "Z"
    
    save_test_config(config)
    logger.info(f"Added vault {vault_id} to corpus '{corpus_name}'")
    
    return True
