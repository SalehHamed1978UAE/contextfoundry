from context_foundry.grounding.doc_fallback import extract_named_entities, build_fallback_queries


def test_extract_named_entities():
    query = "Who is the CEO of Nexus Industries?"
    entities = extract_named_entities(query)
    assert "Nexus Industries" in entities


def test_build_fallback_queries_single():
    query = "Who is the CEO of Nexus Industries?"
    queries = build_fallback_queries(query)
    assert queries == ["CEO Nexus Industries"]


def test_build_fallback_queries_multi():
    query = "What are the contract values for Boeing, Airbus, and DoD?"
    queries = build_fallback_queries(query)
    assert len(queries) >= 2
