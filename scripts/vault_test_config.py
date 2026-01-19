#!/usr/bin/env python3
"""
Vault Test Configuration

Defines all test vaults with their document folders and question banks.
Vault names MUST match folder names exactly (no suffixes like "Clean").
"""

VAULT_CONFIGS = {
    "Manus Healthtec": {
        "name": "Manus Healthtec",
        "doc_dir": "test documents/Manus Healthtec",
        "question_bank": "test documents/Manus Healthtec/question_bank_200.md",
        "results_prefix": "manus_healthtec",
        "description": "MedSync Health - healthcare SaaS company"
    },
    "ClaudeCode Medsync": {
        "name": "ClaudeCode Medsync",
        "doc_dir": "test documents/ClaudeCode Medsync",
        "question_bank": "test documents/ClaudeCode Medsync/question_bank_200.md",
        "results_prefix": "claudecode_medsync",
        "description": "ClaudeCode version of MedSync Health"
    },
    "Manus Medsync": {
        "name": "Manus Medsync",
        "doc_dir": "test documents/Manus Medsync",
        "question_bank": "test documents/Manus Medsync/question_bank_200.md",
        "results_prefix": "manus_medsync",
        "description": "Manus version of MedSync Health"
    },
    "TechVentures": {
        "name": "TechVentures",
        "doc_dir": "test documents/TechVentures",
        "question_bank": None,
        "results_prefix": "techventures",
        "description": "Tech VC firm test vault"
    },
    "Launchpad Ventures": {
        "name": "Launchpad Ventures",
        "doc_dir": "test documents/Launchpad Ventures",
        "question_bank": None,
        "results_prefix": "launchpad_ventures",
        "description": "Accelerator test vault"
    },
    "Hospital": {
        "name": "Riverside Medical Center",
        "doc_dir": "test documents/Hospital",
        "question_bank": None,
        "results_prefix": "hospital",
        "description": "Hospital test vault"
    },
    "Law Firm": {
        "name": "Morrison & Sterling",
        "doc_dir": "test documents/Law Firm",
        "question_bank": None,
        "results_prefix": "law_firm",
        "description": "Law firm test vault"
    },
    "Titan Manufacturing": {
        "name": "Titan Manufacturing",
        "doc_dir": "test documents/Titan Manufacturing",
        "question_bank": None,
        "results_prefix": "titan_manufacturing",
        "description": "Manufacturing test vault"
    },
}

def get_vault_config(vault_key: str) -> dict:
    """Get vault configuration by key."""
    if vault_key not in VAULT_CONFIGS:
        available = list(VAULT_CONFIGS.keys())
        raise ValueError(f"Unknown vault: {vault_key}. Available: {available}")
    return VAULT_CONFIGS[vault_key]

def list_vaults():
    """List all available vaults."""
    print("\nAvailable Vaults:")
    print("-" * 60)
    for key, config in VAULT_CONFIGS.items():
        has_qb = "Yes" if config.get("question_bank") else "No"
        print(f"  {key}")
        print(f"    Name: {config['name']}")
        print(f"    Question Bank: {has_qb}")
        print(f"    Description: {config['description']}")
        print()

if __name__ == "__main__":
    list_vaults()
