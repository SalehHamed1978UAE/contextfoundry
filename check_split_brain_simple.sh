#!/bin/bash
# Quick split-brain check without needing to restart services

VAULT_ID="${1:-b158cd16-810a-484d-99a8-8de786602c35}"

echo "=================================="
echo "SPLIT-BRAIN CHECK"
echo "Vault: $VAULT_ID"
echo "=================================="
echo

python3 << EOF
import os
import psycopg2
from psycopg2.extras import RealDictCursor

vault_id = "$VAULT_ID"
database_url = os.environ.get('DATABASE_URL')

with psycopg2.connect(database_url) as conn:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check platform.documents
        cur.execute("SELECT COUNT(*) as count FROM platform.documents WHERE tenant_id = %s", (vault_id,))
        platform_count = cur.fetchone()['count']
        print(f"platform.documents: {platform_count} documents")

        # Check if public.documents exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'documents'
            )
        """)
        public_exists = cur.fetchone()['exists']

        if not public_exists:
            print("public.documents: TABLE DOES NOT EXIST ❌")
            print("\n🚨 SPLIT-BRAIN CONFIRMED: public.documents table missing!")
        else:
            cur.execute("SELECT COUNT(*) as count FROM public.documents WHERE tenant_id = %s", (vault_id,))
            public_count = cur.fetchone()['count']
            print(f"public.documents: {public_count} documents")

            if platform_count != public_count:
                print(f"\n🚨 SPLIT-BRAIN DETECTED: Count mismatch ({platform_count} vs {public_count})")
            else:
                print(f"\n✅ Counts match: {platform_count} documents")

        # Check entities
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE stage = 'staging') as staging,
                COUNT(*) FILTER (WHERE stage = 'trusted') as trusted
            FROM entities WHERE tenant_id = %s
        """, (vault_id,))
        ent = cur.fetchone()
        print(f"\nEntities: {ent['staging']} staging, {ent['trusted']} trusted")

        # Check relationships
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE stage = 'staging') as staging,
                COUNT(*) FILTER (WHERE stage = 'trusted') as trusted
            FROM relationships WHERE tenant_id = %s
        """, (vault_id,))
        rel = cur.fetchone()
        print(f"Relationships: {rel['staging']} staging, {rel['trusted']} trusted")

        if ent['trusted'] == 0 and ent['staging'] > 0:
            print("\n⚠️  WARNING: Entities in STAGING but NONE promoted to TRUSTED")
EOF

echo
echo "=================================="
