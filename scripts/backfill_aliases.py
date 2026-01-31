#!/usr/bin/env python
"""Backfill aliases from existing entity names like 'Full Name (ABBR)'."""
import re
import uuid
from sqlalchemy import text
from src.context_foundry.models.schema import get_session

def backfill_aliases_from_names(tenant_id: str = None):
    """Extract aliases from entity names like 'Full Name (ABBREVIATION)'."""
    session = get_session()
    
    if tenant_id:
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
    
    pattern = r'^(.+?)\s*\(([A-Z]{2,10})\)$'
    
    tenant_filter = ""
    params = {}
    if tenant_id:
        tenant_filter = "WHERE tenant_id = :tid"
        params["tid"] = tenant_id
    
    entities = session.execute(text(f"""
        SELECT id, name, tenant_id FROM entities
        WHERE name ~ '.*\\([A-Z]{{2,10}}\\)$'
        {f"AND tenant_id = :tid" if tenant_id else ""}
    """), params).fetchall()
    
    aliases_created = 0
    for entity in entities:
        match = re.match(pattern, entity.name)
        if match:
            acronym = match.group(2)
            
            existing = session.execute(text("""
                SELECT id FROM entity_aliases 
                WHERE entity_id = :eid AND alias = :alias
            """), {"eid": entity.id, "alias": acronym}).fetchone()
            
            if not existing:
                session.execute(text("""
                    INSERT INTO entity_aliases (id, entity_id, alias, alias_type, source, tenant_id)
                    VALUES (:id, :eid, :alias, 'acronym', 'backfill', :tid)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(uuid.uuid4()),
                    "eid": entity.id,
                    "alias": acronym,
                    "tid": entity.tenant_id
                })
                aliases_created += 1
                print(f"  Created alias: {acronym} -> {entity.name}")
    
    session.commit()
    
    if tenant_id:
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
    
    print(f"\nProcessed {len(entities)} entities with embedded acronyms")
    print(f"Created {aliases_created} new aliases")
    return aliases_created


if __name__ == "__main__":
    import sys
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else None
    backfill_aliases_from_names(tenant_id)
