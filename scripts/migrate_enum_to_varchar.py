"""
Migration Script: Convert entity_type and relationship_type from ENUM to VARCHAR

This migration is CRITICAL for domain-agnostic schema support.
The hardcoded PostgreSQL ENUMs block new domains like Investment Portfolio
from being stored without code changes.

Migration steps:
1. Add temporary VARCHAR columns
2. Copy enum values to VARCHAR columns
3. Drop the ENUM columns
4. Rename VARCHAR columns to original names
5. Drop the ENUM types
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def run_migration():
    """Execute the ENUM to VARCHAR migration."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return False
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=" * 60)
        print("Starting ENUM to VARCHAR Migration")
        print("=" * 60)
        
        print("\n[Step 1/8] Adding temporary VARCHAR columns...")
        session.execute(text("""
            ALTER TABLE entities 
            ADD COLUMN IF NOT EXISTS entity_type_new VARCHAR(100);
        """))
        session.execute(text("""
            ALTER TABLE relationships 
            ADD COLUMN IF NOT EXISTS relationship_type_new VARCHAR(100);
        """))
        session.commit()
        print("  Added entity_type_new and relationship_type_new columns")
        
        print("\n[Step 2/8] Copying data from ENUM to VARCHAR...")
        session.execute(text("""
            UPDATE entities SET entity_type_new = entity_type::text 
            WHERE entity_type IS NOT NULL;
        """))
        session.execute(text("""
            UPDATE relationships SET relationship_type_new = relationship_type::text 
            WHERE relationship_type IS NOT NULL;
        """))
        session.commit()
        
        entity_count = session.execute(text("SELECT COUNT(*) FROM entities WHERE entity_type_new IS NOT NULL")).scalar()
        rel_count = session.execute(text("SELECT COUNT(*) FROM relationships WHERE relationship_type_new IS NOT NULL")).scalar()
        print(f"  Copied {entity_count} entity types and {rel_count} relationship types")
        
        print("\n[Step 3/8] Dropping ENUM columns...")
        session.execute(text("""
            ALTER TABLE entities DROP COLUMN entity_type;
        """))
        session.execute(text("""
            ALTER TABLE relationships DROP COLUMN relationship_type;
        """))
        session.commit()
        print("  Dropped entity_type and relationship_type ENUM columns")
        
        print("\n[Step 4/8] Renaming VARCHAR columns...")
        session.execute(text("""
            ALTER TABLE entities RENAME COLUMN entity_type_new TO entity_type;
        """))
        session.execute(text("""
            ALTER TABLE relationships RENAME COLUMN relationship_type_new TO relationship_type;
        """))
        session.commit()
        print("  Renamed columns to entity_type and relationship_type")
        
        print("\n[Step 5/8] Setting NOT NULL constraints...")
        session.execute(text("""
            ALTER TABLE entities ALTER COLUMN entity_type SET NOT NULL;
        """))
        session.execute(text("""
            ALTER TABLE relationships ALTER COLUMN relationship_type SET NOT NULL;
        """))
        session.commit()
        print("  Added NOT NULL constraints")
        
        print("\n[Step 6/8] Creating indexes...")
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_entities_entity_type ON entities(entity_type);
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_relationships_relationship_type ON relationships(relationship_type);
        """))
        session.commit()
        print("  Created indexes on type columns")
        
        print("\n[Step 7/8] Dropping old ENUM types...")
        session.execute(text("DROP TYPE IF EXISTS entitytype CASCADE;"))
        session.execute(text("DROP TYPE IF EXISTS relationshiptype CASCADE;"))
        session.commit()
        print("  Dropped entitytype and relationshiptype ENUM types")
        
        print("\n[Step 8/8] Verifying migration...")
        entity_types = session.execute(text("""
            SELECT DISTINCT entity_type FROM entities ORDER BY entity_type;
        """)).fetchall()
        rel_types = session.execute(text("""
            SELECT DISTINCT relationship_type FROM relationships ORDER BY relationship_type;
        """)).fetchall()
        
        print(f"  Entity types in database: {[r[0] for r in entity_types]}")
        print(f"  Relationship types in database: {[r[0] for r in rel_types]}")
        
        column_info = session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('entities', 'relationships')
            AND column_name IN ('entity_type', 'relationship_type')
            ORDER BY table_name;
        """)).fetchall()
        
        for col in column_info:
            print(f"  {col[0]}: {col[1]}")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("Entity types and relationship types are now VARCHAR.")
        print("Domain-agnostic schemas can now be used.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"\nERROR: Migration failed: {e}")
        print("Rolling back changes...")
        return False
    finally:
        session.close()


def verify_migration():
    """Verify the migration was successful."""
    database_url = os.environ.get('DATABASE_URL')
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        result = session.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns 
            WHERE table_name IN ('entities', 'relationships')
            AND column_name IN ('entity_type', 'relationship_type')
            ORDER BY table_name, column_name;
        """)).fetchall()
        
        print("\nColumn verification:")
        all_varchar = True
        for row in result:
            col_name, data_type, udt_name = row
            status = "OK" if data_type == "character varying" else "ENUM (needs migration)"
            if data_type != "character varying":
                all_varchar = False
            print(f"  {col_name}: {data_type} ({udt_name}) - {status}")
        
        return all_varchar
    finally:
        session.close()


if __name__ == "__main__":
    print("Checking current state...")
    needs_migration = not verify_migration()
    
    if needs_migration:
        print("\nMigration required. Starting migration...")
        success = run_migration()
        if success:
            print("\nFinal verification:")
            verify_migration()
    else:
        print("\nNo migration needed - columns are already VARCHAR.")
