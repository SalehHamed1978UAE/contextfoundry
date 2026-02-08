#!/usr/bin/env python3
"""Find documents with supply-chain relationships for extraction validation."""

import os
from sqlalchemy import create_engine, text

def find_supply_chain_documents():
    """Query for documents with supply-chain language."""

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")

    engine = create_engine(database_url)
    conn = engine.connect()
    tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'

    # Find documents with Boeing mentions
    print("=== Documents mentioning Boeing ===")
    boeing_query = """
    SELECT DISTINCT document_name,
           LEFT(chunk_text, 300) as preview
    FROM chunks
    WHERE tenant_id = %s
    AND chunk_text ILIKE '%Boeing%'
    ORDER BY document_name
    LIMIT 10;
    """
    boeing_result = conn.execute(text(boeing_query), {'tenant_id': tenant_id})
    boeing_docs = boeing_result.fetchall()
    for doc in boeing_docs:
        print(f"\nDoc: {doc[0]}")
        print(f"Preview: {doc[1]}...")

    # Find documents with supplier/customer language
    print("\n\n=== Documents with supplier/customer language ===")
    supply_chain_query = """
    SELECT DISTINCT document_name,
           LEFT(chunk_text, 300) as preview
    FROM chunks
    WHERE tenant_id = :tenant_id
    AND (
      chunk_text ILIKE '%supplier%'
      OR chunk_text ILIKE '%customer%'
      OR chunk_text ILIKE '%procures from%'
      OR chunk_text ILIKE '%supplies to%'
      OR chunk_text ILIKE '%partnership with%'
    )
    ORDER BY document_name
    LIMIT 15;
    """
    supply_result = conn.execute(text(supply_chain_query), {'tenant_id': tenant_id})
    supply_docs = supply_result.fetchall()
    for doc in supply_docs:
        print(f"\nDoc: {doc[0]}")
        print(f"Preview: {doc[1]}...")

    # Find documents with well-known company names
    print("\n\n=== Documents with well-known companies ===")
    company_query = """
    SELECT DISTINCT document_name,
           LEFT(chunk_text, 300) as preview
    FROM chunks
    WHERE tenant_id = :tenant_id
    AND (
      chunk_text ILIKE '%Siemens%'
      OR chunk_text ILIKE '%Lockheed%'
      OR chunk_text ILIKE '%Northrop Grumman%'
      OR chunk_text ILIKE '%Raytheon%'
      OR chunk_text ILIKE '%General Electric%'
    )
    ORDER BY document_name
    LIMIT 10;
    """
    company_result = conn.execute(text(company_query), {'tenant_id': tenant_id})
    company_docs = company_result.fetchall()
    for doc in company_docs:
        print(f"\nDoc: {doc[0]}")
        print(f"Preview: {doc[1]}...")

    # Get all document names to see what we have
    print("\n\n=== All available documents ===")
    all_docs_query = """
    SELECT DISTINCT document_name
    FROM chunks
    WHERE tenant_id = :tenant_id
    ORDER BY document_name;
    """
    all_result = conn.execute(text(all_docs_query), {'tenant_id': tenant_id})
    all_docs = all_result.fetchall()
    for doc in all_docs:
        print(f"  - {doc[0]}")

    conn.close()

if __name__ == "__main__":
    find_supply_chain_documents()
