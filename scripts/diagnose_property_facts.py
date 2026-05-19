#!/usr/bin/env python3
"""Diagnose property_facts coverage for key PROPERTY questions (Stage 3B).

For each target question, queries property_facts to show:
1. Does a matching fact exist?
2. What entity_name, attribute_name, attribute_value, lifecycle_state?
3. How many total facts exist for that entity?
4. How many total facts exist for that attribute?

Also prints overall table stats.

Usage:
    python scripts/diagnose_property_facts.py \
        --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.WARNING)

# Target questions: (q_number, query, expected_answer, entity_name, attribute_pattern)
TARGET_QUESTIONS = [
    (6, "What is the total revenue of Nexus Industries?", "$8.45 billion", "Nexus Industries", "revenue"),
    (7, "How many employees does Nexus Industries have?", "12,500", "Nexus Industries", "employee|headcount|staff"),
    (8, "What is the budget for Project Quantum Shield?", "$2.3 billion", "Quantum Shield", "budget"),
    (36, "What is the EBITDA margin for Nexus Industries?", "18.2%", "Nexus Industries", "ebitda"),
    (40, "What is the current order backlog?", "$12.4 billion", "Nexus Industries", "backlog"),
    (38, "What is the annual revenue for the Defense Systems division?", "$966 million", "Defense Systems", "revenue"),
    (45, "When was Nexus Industries founded?", "2003", "Nexus Industries", "found"),
    (48, "What is the capacity of the Austin manufacturing facility?", "425 kg/hr", "Austin", "capacity|production"),
    (58, "What is the contract value of the DOD partnership?", "$4.2 billion", "DOD", "contract|value"),
    (81, "What is the energy density of the solid-state battery?", "400 Wh/kg", "solid-state|battery", "energy_density|density"),
]


def main():
    parser = argparse.ArgumentParser(description="Diagnose property_facts coverage")
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    tid = args.tenant_id

    # --- Overall stats ---
    print("=" * 70)
    print("PROPERTY_FACTS TABLE DIAGNOSTICS")
    print("=" * 70)

    row = session.execute(text(
        "SELECT COUNT(*) AS cnt FROM property_facts WHERE tenant_id = :tid"
    ), {"tid": tid}).fetchone()
    print(f"\nTotal property_facts for tenant: {row.cnt}")

    rows = session.execute(text("""
        SELECT lifecycle_state, COUNT(*) AS cnt
        FROM property_facts WHERE tenant_id = :tid
        GROUP BY lifecycle_state ORDER BY cnt DESC
    """), {"tid": tid}).fetchall()
    print("\nBy lifecycle_state:")
    for r in rows:
        print(f"  {r.lifecycle_state:20s} {r.cnt:6d}")

    rows = session.execute(text("""
        SELECT entity_type, COUNT(*) AS cnt
        FROM property_facts WHERE tenant_id = :tid
        GROUP BY entity_type ORDER BY cnt DESC
    """), {"tid": tid}).fetchall()
    print("\nBy entity_type:")
    for r in rows:
        print(f"  {r.entity_type:30s} {r.cnt:6d}")

    rows = session.execute(text("""
        SELECT attribute_name, COUNT(*) AS cnt
        FROM property_facts WHERE tenant_id = :tid
        GROUP BY attribute_name ORDER BY cnt DESC
        LIMIT 30
    """), {"tid": tid}).fetchall()
    print("\nTop 30 attribute_names:")
    for r in rows:
        print(f"  {r.attribute_name:30s} {r.cnt:6d}")

    # --- Per-question diagnosis ---
    print("\n" + "=" * 70)
    print("PER-QUESTION DIAGNOSIS")
    print("=" * 70)

    for q_num, query, expected, entity_pattern, attr_pattern in TARGET_QUESTIONS:
        print(f"\n--- Q{q_num}: {query}")
        print(f"    Expected: {expected}")
        print(f"    Looking for entity~'{entity_pattern}' + attr~'{attr_pattern}'")

        # Search by entity name (ILIKE)
        entity_terms = entity_pattern.split("|")
        attr_terms = attr_pattern.split("|")

        # Find all facts for matching entities
        entity_clauses = " OR ".join([f"LOWER(entity_name) LIKE :e{i}" for i in range(len(entity_terms))])
        params = {"tid": tid}
        for i, term in enumerate(entity_terms):
            params[f"e{i}"] = f"%{term.lower()}%"

        rows = session.execute(text(f"""
            SELECT entity_name, entity_type, attribute_name, attribute_value,
                   numeric_value, unit, value_type, lifecycle_state, confidence,
                   period, fiscal_year
            FROM property_facts
            WHERE tenant_id = :tid AND ({entity_clauses})
            ORDER BY confidence DESC
            LIMIT 20
        """), params).fetchall()

        if rows:
            print(f"    Facts matching entity '{entity_pattern}': {len(rows)}")
            for r in rows:
                marker = ""
                # Check if this fact matches the attribute pattern
                for at in attr_terms:
                    if at.lower() in r.attribute_name.lower():
                        marker = " <-- ATTR MATCH"
                        # Check if value matches expected
                        if expected.lower().replace(",", "") in str(r.attribute_value).lower().replace(",", ""):
                            marker = " <-- CORRECT MATCH"
                        break
                print(f"      entity={r.entity_name:30s} attr={r.attribute_name:25s} val={str(r.attribute_value):25s} state={r.lifecycle_state} conf={r.confidence}{marker}")
        else:
            print(f"    NO FACTS found for entity '{entity_pattern}'")

        # Also search by attribute name to see if fact exists under a different entity
        attr_clauses = " OR ".join([f"LOWER(attribute_name) LIKE :a{i}" for i in range(len(attr_terms))])
        params2 = {"tid": tid}
        for i, term in enumerate(attr_terms):
            params2[f"a{i}"] = f"%{term.lower()}%"

        rows2 = session.execute(text(f"""
            SELECT entity_name, attribute_name, attribute_value, lifecycle_state, confidence
            FROM property_facts
            WHERE tenant_id = :tid AND ({attr_clauses})
            ORDER BY confidence DESC
            LIMIT 10
        """), params2).fetchall()

        if rows2:
            print(f"    All facts with attr~'{attr_pattern}' (any entity):")
            for r in rows2:
                val_match = ""
                if expected.lower().replace(",", "") in str(r.attribute_value).lower().replace(",", ""):
                    val_match = " <-- VALUE MATCH"
                print(f"      entity={r.entity_name:30s} attr={r.attribute_name:25s} val={str(r.attribute_value):25s} state={r.lifecycle_state}{val_match}")

    # --- Entity table check ---
    print("\n" + "=" * 70)
    print("ENTITY TABLE CHECK — do key entities exist?")
    print("=" * 70)

    key_entities = [
        "Nexus Industries", "Quantum Shield", "Defense Systems",
        "Austin", "BatteryTech", "DOD", "Falcon X",
    ]
    for name in key_entities:
        rows = session.execute(text("""
            SELECT e.id::text, e.name, e.entity_type, e.lifecycle_state,
                   COALESCE(
                       array_agg(DISTINCT ea.alias) FILTER (WHERE ea.alias IS NOT NULL),
                       ARRAY[]::text[]
                   ) AS aliases
            FROM entities e
            LEFT JOIN entity_aliases ea ON ea.entity_id = e.id AND ea.tenant_id = e.tenant_id
            WHERE e.tenant_id = :tid AND LOWER(e.name) LIKE :pat
            GROUP BY e.id, e.name, e.entity_type, e.lifecycle_state
            ORDER BY e.name ASC
            LIMIT 10
        """), {"tid": tid, "pat": f"%{name.lower()}%"}).fetchall()

        print(f"\n  '{name}':")
        if rows:
            for r in rows:
                aliases = list(r.aliases) if r.aliases else []
                print(f"    id={r.id[:12]}... name={r.name:40s} type={r.entity_type:20s} state={r.lifecycle_state}")
                if aliases:
                    print(f"      aliases: {aliases[:5]}")
        else:
            print(f"    NOT FOUND in entities table")

    # --- Chunk check: do chunks mention "Nexus Industries" with revenue? ---
    print("\n" + "=" * 70)
    print("CHUNK CHECK — chunks mentioning key terms")
    print("=" * 70)

    chunk_searches = [
        ("Nexus Industries + $8.45", "nexus industries", "8.45"),
        ("Nexus Industries + 12,500", "nexus industries", "12,500"),
        ("Quantum Shield + $2.3", "quantum shield", "2.3"),
        ("Nexus Industries + backlog", "nexus industries", "backlog"),
        ("Nexus Industries + EBITDA", "nexus industries", "ebitda"),
    ]
    for label, term1, term2 in chunk_searches:
        rows = session.execute(text("""
            SELECT dc.id::text AS chunk_id, LEFT(dc.text, 200) AS snippet
            FROM document_chunks dc
            WHERE dc.tenant_id = :tid
              AND dc.text ILIKE :t1
              AND dc.text ILIKE :t2
            LIMIT 3
        """), {"tid": tid, "t1": f"%{term1}%", "t2": f"%{term2}%"}).fetchall()

        print(f"\n  '{label}': {len(rows)} chunks found")
        for r in rows:
            print(f"    chunk={r.chunk_id[:12]}... snippet={r.snippet[:120]}...")

    session.close()
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
