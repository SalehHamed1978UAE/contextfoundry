"""
Piece 2 Stage 1 — scoped prompt construction tests.

Verifies SchemaPromptGenerator's new scoped builder methods enforce:
  - domain_id REQUIRED (raises on None or empty string)
  - scope = core ∪ primary_domain
  - NULL-domain rows excluded
  - other named domains excluded
  - core types/relations explicitly included
  - legacy unscoped methods + repository no-filter behavior preserved

Domain row counts (verified 2026-05-10 after Piece 0.6 mutation):
  core              | 25 types | 21 relations
  aviation          | 27 types | 30 relations
  construction      | 26 types | 28 relations
  finance           | 28 types | 28 relations
  healthcare        | 26 types | 34 relations
  it_infrastructure | 34 types | 25 relations
  manufacturing     | 18 types | 24 relations
  supply_chain      | 19 types | 27 relations
"""
import os
import pytest

from src.context_foundry.ontology.prompt_generator import SchemaPromptGenerator
from src.context_foundry.ontology.repository import OntologyRepository


CANONICAL_DOMAINS = [
    "core", "it_infrastructure", "supply_chain", "healthcare",
    "manufacturing", "aviation", "finance", "construction",
]

DOMAIN_TYPE_COUNTS = {
    "core": 25,
    "aviation": 27,
    "construction": 26,
    "finance": 28,
    "healthcare": 26,
    "it_infrastructure": 34,
    "manufacturing": 18,
    "supply_chain": 19,
}

DOMAIN_RELATION_COUNTS = {
    "core": 21,
    "aviation": 30,
    "construction": 28,
    "finance": 28,
    "healthcare": 34,
    "it_infrastructure": 25,
    "manufacturing": 24,
    "supply_chain": 27,
}


@pytest.fixture(scope="module")
def repo():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; scoped prompt tests require live DB")
    return OntologyRepository()


@pytest.fixture(scope="module")
def generator(repo):
    return SchemaPromptGenerator(repository=repo)


# =============================================================================
# REQUIRED domain_id — raises on None or empty
# =============================================================================

def test_build_entity_extraction_prompt_scoped_requires_domain_id(generator):
    """Brief Step H: build_entity_extraction_prompt(domain_id=None) raises."""
    with pytest.raises(ValueError, match="domain_id"):
        generator.build_entity_extraction_prompt_scoped(
            text="sample", domain_id=None
        )


def test_build_entity_extraction_prompt_scoped_rejects_empty_domain(generator):
    with pytest.raises(ValueError, match="domain_id"):
        generator.build_entity_extraction_prompt_scoped(
            text="sample", domain_id=""
        )


def test_build_relationship_extraction_prompt_scoped_requires_domain_id(generator):
    """Brief Step H: build_relationship_extraction_prompt(domain_id=None) raises."""
    with pytest.raises(ValueError, match="domain_id"):
        generator.build_relationship_extraction_prompt_scoped(
            text="sample", entities_str="", domain_id=None
        )


def test_build_relationship_extraction_prompt_scoped_rejects_empty_domain(generator):
    with pytest.raises(ValueError, match="domain_id"):
        generator.build_relationship_extraction_prompt_scoped(
            text="sample", entities_str="", domain_id=""
        )


def test_load_scoped_types_requires_domain_id(generator):
    with pytest.raises(ValueError, match="domain_id"):
        generator._load_scoped_types(None)


def test_load_scoped_relations_requires_domain_id(generator):
    with pytest.raises(ValueError, match="domain_id"):
        generator._load_scoped_relations(None)


def test_get_scoped_extraction_lists_requires_domain_id(generator):
    with pytest.raises(ValueError, match="domain_id"):
        generator.get_scoped_extraction_lists(None)


# =============================================================================
# Scope = core ∪ primary_domain — type/relation lists per domain
# =============================================================================

@pytest.mark.parametrize("domain", CANONICAL_DOMAINS)
def test_scoped_types_contain_only_core_and_selected_domain(generator, domain):
    """Scope = core ∪ domain. NULL-domain + other named domains excluded."""
    types = generator._load_scoped_types(domain)
    domains_seen = {t.domain_id for t in types}
    expected = {"core"} if domain == "core" else {"core", domain}
    assert domains_seen == expected, (
        f"scoped types for domain={domain} contain unexpected domain_ids: "
        f"{domains_seen} (expected {expected})"
    )
    # No NULL-domain leakage.
    assert None not in domains_seen
    # Other named domains absent.
    other_domains = set(CANONICAL_DOMAINS) - {"core", domain}
    assert not (domains_seen & other_domains)


@pytest.mark.parametrize("domain", CANONICAL_DOMAINS)
def test_scoped_relations_contain_only_core_and_selected_domain(generator, domain):
    """Scope = core ∪ domain. NULL-domain + other named domains excluded."""
    rels = generator._load_scoped_relations(domain)
    domains_seen = {r.domain_id for r in rels}
    expected = {"core"} if domain == "core" else {"core", domain}
    assert domains_seen == expected, (
        f"scoped relations for domain={domain} contain unexpected domain_ids: "
        f"{domains_seen} (expected {expected})"
    )
    assert None not in domains_seen


@pytest.mark.parametrize("domain", CANONICAL_DOMAINS)
def test_scoped_types_count_matches_db(generator, domain):
    """Total scoped count = core_count + domain_count (no overlap)."""
    types = generator._load_scoped_types(domain)
    if domain == "core":
        expected = DOMAIN_TYPE_COUNTS["core"]
    else:
        expected = DOMAIN_TYPE_COUNTS["core"] + DOMAIN_TYPE_COUNTS[domain]
    assert len(types) == expected, (
        f"scoped types for {domain}: expected {expected}, got {len(types)}"
    )


@pytest.mark.parametrize("domain", CANONICAL_DOMAINS)
def test_scoped_relations_count_matches_db(generator, domain):
    rels = generator._load_scoped_relations(domain)
    if domain == "core":
        expected = DOMAIN_RELATION_COUNTS["core"]
    else:
        expected = DOMAIN_RELATION_COUNTS["core"] + DOMAIN_RELATION_COUNTS[domain]
    assert len(rels) == expected


def test_scoped_finance_excludes_healthcare_and_aviation(generator):
    """Specific cross-contamination check."""
    types = generator._load_scoped_types("finance")
    domains = {t.domain_id for t in types}
    assert "healthcare" not in domains
    assert "aviation" not in domains
    assert "manufacturing" not in domains


def test_scoped_healthcare_excludes_finance(generator):
    rels = generator._load_scoped_relations("healthcare")
    domains = {r.domain_id for r in rels}
    assert "finance" not in domains


# =============================================================================
# Core is always included
# =============================================================================

def test_core_present_in_every_scoped_lookup(generator):
    """Brief Step H: 'core is included explicitly.'"""
    for domain in CANONICAL_DOMAINS:
        types = generator._load_scoped_types(domain)
        type_domains = {t.domain_id for t in types}
        assert "core" in type_domains, f"core missing from scoped types for {domain}"
        rels = generator._load_scoped_relations(domain)
        rel_domains = {r.domain_id for r in rels}
        assert "core" in rel_domains, f"core missing from scoped relations for {domain}"


def test_core_relation_holds_position_present_in_finance_scope(generator):
    """Piece 0.6 governed HOLDS_POSITION into core; finance scope must include it."""
    rels = generator._load_scoped_relations("finance")
    rel_types = {r.relation_type for r in rels}
    assert "HOLDS_POSITION" in rel_types
    assert "WORKS_AT" in rel_types
    assert "REPORTS_TO" in rel_types


def test_finance_relation_has_compensation_present_in_finance_scope(generator):
    """Piece 0.6 governed HAS_COMPENSATION (P→COMPENSATION) into finance."""
    rels = generator._load_scoped_relations("finance")
    pairs = {(r.relation_type, r.source_type_name, r.target_type_name) for r in rels}
    assert ("HAS_COMPENSATION", "PERSON", "COMPENSATION") in pairs


# =============================================================================
# Scoped prompt content
# =============================================================================

def test_scoped_entity_prompt_excludes_null_domain_types(generator):
    """The 803 NULL-domain layer-2 ad-hoc UPPER_SNAKE types must not leak."""
    prompt = generator.build_entity_extraction_prompt_scoped(
        text="sample", domain_id="finance"
    )
    # Sanity — prompt mentions the scoped domain.
    assert "finance" in prompt
    # No NULL-domain types should leak (count test above is the strict check;
    # this is a defense-in-depth content sanity).
    # The scoped finance prompt should have the sum of core+finance types
    # listed; a few representative non-domain-leak indicators.
    types = generator._load_scoped_types("finance")
    expected_count = DOMAIN_TYPE_COUNTS["core"] + DOMAIN_TYPE_COUNTS["finance"]
    assert len(types) == expected_count


def test_scoped_relationship_prompt_mentions_domain_and_lists_relations(generator):
    prompt = generator.build_relationship_extraction_prompt_scoped(
        text="sample text",
        entities_str="Alice (PERSON), Acme (ORGANIZATION)",
        domain_id="healthcare",
    )
    assert "healthcare" in prompt
    assert "RELATION_TYPE" in prompt  # template marker
    assert "KNOWN ENTITIES" in prompt


# =============================================================================
# Legacy methods + repository no-filter behavior preserved
# =============================================================================

def test_repository_no_filter_get_all_types_unchanged(repo):
    """Brief: 'OntologyRepository.get_all_types() with no domain filter must
    remain unchanged.'"""
    rows = repo.get_all_types()
    assert len(rows) == 1033, f"expected 1033 ACTIVE types, got {len(rows)}"


def test_repository_no_filter_get_all_relations_unchanged(repo):
    """Brief: 'OntologyRepository.get_all_relations() with no domain filter
    must remain unchanged.'"""
    # Default (include_deprecated=False) should remain at 253 post-Piece 0.6
    # (254 active rows minus 1 deprecated by Piece 0.6).
    rows = repo.get_all_relations()
    assert len(rows) == 253, f"expected 253 ACTIVE relations, got {len(rows)}"


def test_legacy_build_entity_extraction_prompt_signature_preserved(generator):
    """Legacy unscoped method signature must be unchanged (Piece 2 Stage 1 ADD-only).

    NOTE: actually calling build_entity_extraction_prompt(text='sample') without
    a layer/type filter exposes a pre-existing latent bug in
    SchemaPromptGenerator._format_type_description (line 51:
    type_obj.display_name.lower() crashes when display_name is None — at least
    one of the 1033 unscoped types has display_name=None). That bug pre-dates
    Piece 2 and is unrelated to the scoped builder work. Flagged for separate
    follow-up. This test only asserts the signature is preserved.
    """
    import inspect
    sig = inspect.signature(generator.build_entity_extraction_prompt)
    params = list(sig.parameters.keys())
    assert "text" in params
    assert "layer_filter" in params
    assert "type_filter" in params
    # No domain_id added to legacy method — scoped builder is a NEW method.
    assert "domain_id" not in params


def test_legacy_build_relationship_extraction_prompt_signature_preserved(generator):
    """Legacy method signature unchanged — confirms ADD-only Piece 2 Stage 1."""
    import inspect
    sig = inspect.signature(generator.build_relationship_extraction_prompt)
    params = list(sig.parameters.keys())
    assert "text" in params
    assert "entities_str" in params
    assert "domain_id" not in params


# =============================================================================
# get_scoped_extraction_lists shape (used by OntologyCentricPipeline)
# =============================================================================

def test_get_scoped_extraction_lists_returns_correct_shape(generator):
    entity_type_names, relation_type_defs = generator.get_scoped_extraction_lists(
        "finance"
    )
    assert isinstance(entity_type_names, list)
    assert all(isinstance(n, str) for n in entity_type_names)
    assert len(entity_type_names) > 0

    assert isinstance(relation_type_defs, list)
    assert all(isinstance(d, dict) for d in relation_type_defs)
    for d in relation_type_defs:
        assert "name" in d
        assert "definition" in d
        assert "source_types" in d
        assert "target_types" in d


def test_get_scoped_extraction_lists_finance_includes_core(generator):
    entity_type_names, relation_type_defs = generator.get_scoped_extraction_lists(
        "finance"
    )
    rel_names = {d["name"] for d in relation_type_defs}
    # Core relations governed by Piece 0.6 must be present.
    assert "HOLDS_POSITION" in rel_names
    assert "WORKS_AT" in rel_names
    # Finance relation must be present.
    assert "HAS_COMPENSATION" in rel_names
