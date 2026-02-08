#!/usr/bin/env python3
"""Clear extraction cache for a specific vault to force re-extraction."""

import argparse
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_foundry.config import get_database_url
from sqlalchemy import create_engine, text


def clear_vault_extraction(vault_id: str):
    """Clear extraction jobs and reset document status for a vault."""
    engine = create_engine(get_database_url())

    with engine.connect() as conn:
        # Delete extraction jobs
        result = conn.execute(
            text("""
                DELETE FROM extraction_jobs
                WHERE document_id IN (
                    SELECT id FROM documents WHERE tenant_id = :vault_id
                )
            """),
            {"vault_id": vault_id}
        )
        print(f"Deleted {result.rowcount} extraction jobs")

        # Reset document status
        result = conn.execute(
            text("""
                UPDATE documents
                SET status = 'queued'
                WHERE tenant_id = :vault_id
            """),
            {"vault_id": vault_id}
        )
        print(f"Reset {result.rowcount} documents to 'queued' status")

        conn.commit()
        print(f"✓ Extraction cache cleared for vault {vault_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear extraction cache for a vault")
    parser.add_argument("--vault-id", required=True, help="Vault/tenant ID")
    args = parser.parse_args()

    clear_vault_extraction(args.vault_id)
