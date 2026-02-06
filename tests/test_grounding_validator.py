from context_foundry.grounding.validator import validate_path_contains_anchor


def test_grounding_filters_relationships():
    rels = [
        {"source_name": "GreenHydrogen", "target_name": "Honeywell"},
        {"source_name": "Aerospace", "target_name": "Boeing"},
    ]
    filtered = validate_path_contains_anchor(rels, "GreenHydrogen")
    assert len(filtered) == 1
    assert filtered[0]["target_name"] == "Honeywell"
