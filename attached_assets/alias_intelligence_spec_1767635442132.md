# Entity Alias Intelligence System

## Overview

Build systematic acronym and alias handling into Context Foundry so entity resolution works naturally without manual fixes.

---

## Components

### 1. Entity Aliases Table

```sql
-- Add to schema
CREATE TABLE entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    alias_type VARCHAR(50) NOT NULL DEFAULT 'acronym',
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'extraction',  -- 'extraction', 'llm', 'web', 'manual'
    tenant_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_alias_per_entity UNIQUE(entity_id, alias, tenant_id)
);

-- Index for fast lookup
CREATE INDEX idx_entity_aliases_lookup 
ON entity_aliases(tenant_id, LOWER(alias));

-- RLS policy
ALTER TABLE entity_aliases ENABLE ROW LEVEL SECURITY;

CREATE POLICY entity_aliases_tenant_isolation ON entity_aliases
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### 2. Extraction Enhancement

Update entity extraction prompt to capture aliases:

```python
EXTRACTION_PROMPT = """
Extract entities from the document. For each entity:
- name: The full, formal name
- type: Entity type (SERVICE, DATABASE, TEAM, etc.)
- aliases: List of abbreviations, acronyms, or alternate names

Examples:
- "Electronic Health Record (EHR)" → name: "Electronic Health Record", aliases: ["EHR"]
- "The API Gateway, also known as the edge proxy" → name: "API Gateway", aliases: ["edge proxy"]
- "AWS (Amazon Web Services)" → name: "Amazon Web Services", aliases: ["AWS"]

Return JSON:
{
  "entities": [
    {
      "name": "...",
      "type": "...",
      "aliases": ["...", "..."]
    }
  ]
}
"""
```

### 3. Graph Builder Update

When creating entities, also create alias records:

```python
def create_entity_with_aliases(
    self,
    name: str,
    entity_type: str,
    aliases: List[str],
    tenant_id: str,
    session
) -> Entity:
    """Create entity and its aliases."""
    
    # Create entity
    entity = Entity(
        id=str(uuid4()),
        name=name,
        entity_type=entity_type,
        tenant_id=tenant_id,
        lifecycle_state='STAGING',
        confidence=0.9
    )
    session.add(entity)
    session.flush()  # Get entity ID
    
    # Create aliases
    for alias in aliases:
        if alias and alias.lower() != name.lower():
            entity_alias = EntityAlias(
                entity_id=entity.id,
                alias=alias,
                alias_type=self._detect_alias_type(alias, name),
                source='extraction',
                tenant_id=tenant_id
            )
            session.add(entity_alias)
    
    return entity

def _detect_alias_type(self, alias: str, full_name: str) -> str:
    """Detect type of alias."""
    # All caps and short = acronym
    if alias.isupper() and len(alias) <= 10:
        return 'acronym'
    # Check if alias is initials of full name
    initials = ''.join(word[0] for word in full_name.split() if word[0].isupper())
    if alias.upper() == initials:
        return 'acronym'
    # Otherwise it's a synonym/alternate name
    return 'synonym'
```

### 4. Enhanced Entity Resolution

```python
class EntityResolver:
    """Resolve entity names with alias support."""
    
    def resolve(self, query_name: str, tenant_id: str) -> Optional[Entity]:
        """
        Resolve entity by name or alias.
        
        Resolution order:
        1. Exact match on entity name
        2. Case-insensitive match on entity name
        3. Exact match on alias
        4. Case-insensitive match on alias
        5. Fuzzy match on name
        6. LLM expansion (if enabled)
        """
        
        # 1. Exact match on name
        entity = self._exact_name_match(query_name, tenant_id)
        if entity:
            return entity
        
        # 2. Case-insensitive name match
        entity = self._case_insensitive_name_match(query_name, tenant_id)
        if entity:
            return entity
        
        # 3. Exact alias match
        entity = self._exact_alias_match(query_name, tenant_id)
        if entity:
            return entity
        
        # 4. Case-insensitive alias match
        entity = self._case_insensitive_alias_match(query_name, tenant_id)
        if entity:
            return entity
        
        # 5. Fuzzy match
        entity = self._fuzzy_match(query_name, tenant_id)
        if entity:
            return entity
        
        # 6. LLM expansion (last resort)
        entity = self._llm_expand_and_match(query_name, tenant_id)
        if entity:
            return entity
        
        return None
    
    def _exact_alias_match(self, alias: str, tenant_id: str) -> Optional[Entity]:
        """Find entity by exact alias match."""
        result = self.session.execute(text("""
            SELECT e.* FROM entities e
            JOIN entity_aliases a ON e.id = a.entity_id
            WHERE a.tenant_id = :tid
            AND a.alias = :alias
            AND e.lifecycle_state = 'TRUSTED'
            LIMIT 1
        """), {"tid": tenant_id, "alias": alias}).fetchone()
        
        if result:
            return self._row_to_entity(result)
        return None
    
    def _case_insensitive_alias_match(self, alias: str, tenant_id: str) -> Optional[Entity]:
        """Find entity by case-insensitive alias match."""
        result = self.session.execute(text("""
            SELECT e.* FROM entities e
            JOIN entity_aliases a ON e.id = a.entity_id
            WHERE a.tenant_id = :tid
            AND LOWER(a.alias) = LOWER(:alias)
            AND e.lifecycle_state = 'TRUSTED'
            LIMIT 1
        """), {"tid": tenant_id, "alias": alias}).fetchone()
        
        if result:
            return self._row_to_entity(result)
        return None
    
    def _llm_expand_and_match(self, query_name: str, tenant_id: str) -> Optional[Entity]:
        """
        Use LLM to expand acronym and try matching.
        
        Only called if all other methods fail.
        """
        # Get list of entity names in tenant for context
        entities = self.session.execute(text("""
            SELECT name FROM entities 
            WHERE tenant_id = :tid 
            AND lifecycle_state = 'TRUSTED'
            LIMIT 100
        """), {"tid": tenant_id}).fetchall()
        
        entity_names = [e.name for e in entities]
        
        # Ask LLM
        prompt = f"""
The user is looking for an entity called "{query_name}".

Here are the entities in the system:
{chr(10).join(f'- {name}' for name in entity_names)}

Which entity is the user most likely referring to? 
If "{query_name}" is an acronym, which entity name matches?

Return ONLY the exact entity name from the list, or "NONE" if no match.
"""
        
        response = self.llm.complete(prompt)
        matched_name = response.strip()
        
        if matched_name and matched_name != "NONE":
            # Try to find this entity
            entity = self._exact_name_match(matched_name, tenant_id)
            if entity:
                # Learn this alias for future
                self._save_learned_alias(entity.id, query_name, tenant_id)
                return entity
        
        return None
    
    def _save_learned_alias(self, entity_id: str, alias: str, tenant_id: str):
        """Save a newly learned alias."""
        try:
            self.session.execute(text("""
                INSERT INTO entity_aliases (entity_id, alias, alias_type, source, tenant_id)
                VALUES (:eid, :alias, 'acronym', 'llm', :tid)
                ON CONFLICT (entity_id, alias, tenant_id) DO NOTHING
            """), {"eid": entity_id, "alias": alias, "tid": tenant_id})
            self.session.commit()
        except Exception:
            self.session.rollback()
```

### 5. Web Search Fallback (Optional)

For truly unknown acronyms:

```python
def _web_search_acronym(self, acronym: str, domain_context: str) -> Optional[str]:
    """
    Search web for acronym meaning in context.
    
    Only used for unknown acronyms not in any entity or alias.
    """
    query = f"what does {acronym} stand for in {domain_context}"
    results = web_search(query)
    
    if results:
        # Ask LLM to extract the expansion
        prompt = f"""
Search results for "{acronym}":
{results[0].snippet}

What does "{acronym}" most likely stand for in the context of {domain_context}?
Return only the expanded form, nothing else.
"""
        expansion = self.llm.complete(prompt).strip()
        return expansion
    
    return None
```

---

## Migration for Existing Data

Extract aliases from existing entities:

```python
def backfill_aliases_from_names():
    """Extract aliases from entity names like 'Full Name (ABBR)'."""
    
    session = get_session()
    
    # Pattern: "Full Name (ABBREVIATION)"
    pattern = r'^(.+?)\s*\(([A-Z]{2,10})\)$'
    
    entities = session.execute(text("""
        SELECT id, name, tenant_id FROM entities
        WHERE name ~ '.*\\([A-Z]{2,10}\\)$'
    """)).fetchall()
    
    for entity in entities:
        match = re.match(pattern, entity.name)
        if match:
            full_name = match.group(1).strip()
            acronym = match.group(2)
            
            # Update entity name to just the full name
            session.execute(text("""
                UPDATE entities SET name = :name WHERE id = :id
            """), {"name": full_name, "id": entity.id})
            
            # Add acronym as alias
            session.execute(text("""
                INSERT INTO entity_aliases (entity_id, alias, alias_type, source, tenant_id)
                VALUES (:eid, :alias, 'acronym', 'migration', :tid)
                ON CONFLICT DO NOTHING
            """), {"eid": entity.id, "alias": acronym, "tid": entity.tenant_id})
    
    session.commit()
    print(f"Processed {len(entities)} entities with embedded acronyms")
```

---

## Testing

```python
def test_acronym_resolution():
    """Test that acronyms resolve correctly."""
    
    # Setup: Create entity with alias
    entity = create_entity_with_aliases(
        name="Electronic Health Record",
        entity_type="SERVICE",
        aliases=["EHR"],
        tenant_id=TEST_TENANT_ID
    )
    
    resolver = EntityResolver(session, TEST_TENANT_ID)
    
    # Test: Resolve by full name
    result = resolver.resolve("Electronic Health Record", TEST_TENANT_ID)
    assert result.id == entity.id
    
    # Test: Resolve by acronym
    result = resolver.resolve("EHR", TEST_TENANT_ID)
    assert result.id == entity.id
    
    # Test: Case insensitive
    result = resolver.resolve("ehr", TEST_TENANT_ID)
    assert result.id == entity.id


def test_llm_learns_alias():
    """Test that LLM-resolved aliases are saved."""
    
    # Setup: Entity without alias
    entity = create_entity(
        name="Application Programming Interface Gateway",
        entity_type="SERVICE"
    )
    
    resolver = EntityResolver(session, TEST_TENANT_ID)
    
    # First resolution: LLM figures it out
    result = resolver.resolve("API Gateway", TEST_TENANT_ID)
    assert result.id == entity.id
    
    # Verify alias was saved
    aliases = get_aliases(entity.id)
    assert "API Gateway" in aliases
    
    # Second resolution: Uses saved alias (faster)
    result = resolver.resolve("API Gateway", TEST_TENANT_ID)
    assert result.id == entity.id
```

---

## Summary

| Component | Purpose |
|-----------|---------|
| entity_aliases table | Store acronyms, abbreviations, synonyms |
| Extraction enhancement | Capture aliases during ingestion |
| Resolution enhancement | Check aliases before giving up |
| LLM fallback | Figure out unknown acronyms |
| Learning | Save resolved acronyms for future |

This makes the system **intelligent** instead of just pattern-matching.
