"""
Configuration management for test runner.
Loads/saves test_config.json with corpus definitions and state.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class CorpusConfig:
    """Configuration for a single test corpus."""
    root_path: str
    questions_file: str
    current_vault_id: Optional[str] = None
    last_run: Optional[str] = None
    last_accuracy: Optional[float] = None


@dataclass
class UploadRules:
    """Rules for document upload filtering."""
    include_folders: list = field(default_factory=lambda: ["documents", "excel_data"])
    valid_extensions: list = field(default_factory=lambda: [".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md"])
    exclude_files: list = field(default_factory=lambda: ["README.md"])


@dataclass
class ExtractionConfig:
    """Configuration for extraction waiting."""
    timeout_minutes: int = 15
    min_expected_chunks: int = 50
    poll_interval_seconds: int = 5


@dataclass
class TestConfig:
    """Main test configuration."""
    api_base_url: str = "http://localhost:5000"
    auth_token: Optional[str] = None
    corpora: Dict[str, CorpusConfig] = field(default_factory=dict)
    questions_dir: str = "test_questions/"
    results_dir: str = "test_results/"
    upload_rules: UploadRules = field(default_factory=UploadRules)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "api_base_url": self.api_base_url,
            "auth_token": self.auth_token,
            "corpora": {},
            "questions_dir": self.questions_dir,
            "results_dir": self.results_dir,
            "upload_rules": asdict(self.upload_rules),
            "extraction": asdict(self.extraction)
        }
        for name, corpus in self.corpora.items():
            result["corpora"][name] = asdict(corpus)
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TestConfig':
        """Create from dictionary."""
        config = cls()
        config.api_base_url = data.get("api_base_url", config.api_base_url)
        config.auth_token = data.get("auth_token") or os.environ.get("CF_API_TOKEN")
        config.questions_dir = data.get("questions_dir", config.questions_dir)
        config.results_dir = data.get("results_dir", config.results_dir)
        
        if "upload_rules" in data:
            config.upload_rules = UploadRules(**data["upload_rules"])
        
        if "extraction" in data:
            config.extraction = ExtractionConfig(**data["extraction"])
        
        if "corpora" in data:
            for name, corpus_data in data["corpora"].items():
                config.corpora[name] = CorpusConfig(**corpus_data)
        
        return config


def get_config_path() -> Path:
    """Get path to test_config.json."""
    return Path("src/test_config.json")


def load_config() -> TestConfig:
    """Load configuration from test_config.json."""
    config_path = get_config_path()
    
    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
        return TestConfig.from_dict(data)
    
    return create_default_config()


def save_config(config: TestConfig) -> None:
    """Save configuration to test_config.json."""
    config_path = get_config_path()
    
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)


def create_default_config() -> TestConfig:
    """Create default configuration with known corpora."""
    config = TestConfig()
    
    config.corpora = {
        "medsync_health": CorpusConfig(
            root_path="test_documents/medsync_health/",
            questions_file="question_bank_200.md"
        ),
        "manus_medsync": CorpusConfig(
            root_path="test_documents/manus_medsync/",
            questions_file="question_bank_200.md"
        ),
        "claudecode_medsync": CorpusConfig(
            root_path="test_documents/claudecode_medsync/",
            questions_file="qa_pairs.json"
        )
    }
    
    save_config(config)
    return config


def update_corpus_state(corpus_name: str, vault_id: Optional[str] = None, accuracy: Optional[float] = None) -> None:
    """Update corpus state after a test run."""
    config = load_config()
    
    if corpus_name not in config.corpora:
        raise ValueError(f"Unknown corpus: {corpus_name}")
    
    corpus = config.corpora[corpus_name]
    
    if vault_id is not None:
        corpus.current_vault_id = vault_id
    
    if accuracy is not None:
        corpus.last_accuracy = accuracy
    
    corpus.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_config(config)
