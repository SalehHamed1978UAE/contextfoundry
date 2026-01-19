import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

DEFAULT_CONFIG = {
    "api_base_url": "http://localhost:5000/api",
    "corpora": {
        "ClaudeCode Medsync": {
            "root_path": "test_documents/ClaudeCode Medsync/",
            "questions_file": "medsync_235q.json",
            "current_vault_id": None,
            "last_run": None,
            "last_accuracy": None
        },
        "Manus Healthtec": {
            "root_path": "test_documents/Manus Healthtec/",
            "questions_file": "medsync_235q.json",
            "current_vault_id": None,
            "last_run": None,
            "last_accuracy": None
        },
        "Manus Medsync": {
            "root_path": "test_documents/Manus Medsync/",
            "questions_file": "medsync_235q.json",
            "current_vault_id": None,
            "last_run": None,
            "last_accuracy": None
        }
    },
    "questions_dir": "test_questions/",
    "results_dir": "test_results/",
    "upload_rules": {
        "include_folders": ["documents", "excel_data"],
        "valid_extensions": [".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md"],
        "exclude_files": ["README.md", "readme.md"]
    },
    "extraction": {
        "timeout_minutes": 20,
        "min_expected_chunks": 50,
        "poll_interval_seconds": 10
    }
}

class TestConfig:
    def __init__(self, config_path: str = "src/test_config.json"):
        self.config_path = Path(config_path)
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()
    
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_corpus(self, name: str) -> Optional[Dict]:
        return self.data.get('corpora', {}).get(name)
    
    def update_corpus(self, name: str, **kwargs):
        if name in self.data.get('corpora', {}):
            self.data['corpora'][name].update(kwargs)
            self.save()
    
    def list_corpora(self) -> Dict[str, Dict]:
        return self.data.get('corpora', {})
    
    @property
    def api_base_url(self) -> str:
        return self.data.get('api_base_url', 'http://localhost:5000/api')
    
    @property
    def questions_dir(self) -> Path:
        return Path(self.data.get('questions_dir', 'test_questions/'))
    
    @property
    def results_dir(self) -> Path:
        return Path(self.data.get('results_dir', 'test_results/'))
    
    @property
    def upload_rules(self) -> Dict:
        return self.data.get('upload_rules', DEFAULT_CONFIG['upload_rules'])
    
    @property
    def extraction_config(self) -> Dict:
        return self.data.get('extraction', DEFAULT_CONFIG['extraction'])
