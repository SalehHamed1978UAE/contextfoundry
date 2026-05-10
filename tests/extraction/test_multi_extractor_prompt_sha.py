"""
Piece 2 Stage 1 — Step G lock test.

Asserts that MultiModelExtractor's EXTRACTION_SYSTEM_PROMPT module-level
constant is byte-identical to the value verified in Pieces 1 and 1.5 and
re-confirmed in Step A of the Piece 2 Stage 1 preflight.

Per brief lines 207-216 + Step B sign-off Decision 3 + Decision 4
(docs/inbox/piece_2_stage1_step_b_signoff_2026-05-10.md):
    - Prompt MUST remain unchanged in Stage 1.
    - Symbol is module-level: src.context_foundry.extraction.multi_extractor.EXTRACTION_SYSTEM_PROMPT
      (NOT MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT).
    - SHA-256 target: 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963

Any modification to the prompt requires Stage 2 sign-off.
"""
import hashlib

from src.context_foundry.extraction import multi_extractor


PROMPT_SHA_TARGET = (
    "5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963"
)


def test_extraction_system_prompt_is_module_level_constant():
    """Confirms the symbol exists at module level (not on the class)."""
    assert hasattr(multi_extractor, "EXTRACTION_SYSTEM_PROMPT"), (
        "EXTRACTION_SYSTEM_PROMPT must be a module-level constant in "
        "src.context_foundry.extraction.multi_extractor"
    )
    assert isinstance(multi_extractor.EXTRACTION_SYSTEM_PROMPT, str)
    assert len(multi_extractor.EXTRACTION_SYSTEM_PROMPT) > 0


def test_extraction_system_prompt_sha_unchanged():
    """Lock test — fails if the MultiModelExtractor system prompt changes."""
    actual_sha = hashlib.sha256(
        multi_extractor.EXTRACTION_SYSTEM_PROMPT.encode("utf-8")
    ).hexdigest()
    assert actual_sha == PROMPT_SHA_TARGET, (
        f"MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT was modified.\n"
        f"  expected: {PROMPT_SHA_TARGET}\n"
        f"  actual:   {actual_sha}\n"
        f"This is forbidden in Piece 2 Stage 1. Any change to the prompt "
        f"requires Stage 2 sign-off. See docs/inbox/"
        f"piece_2_stage1_implementation_2026-05-10.md lines 207-216 and "
        f"docs/inbox/piece_2_stage1_step_b_signoff_2026-05-10.md Decision 3."
    )


def test_multi_extractor_class_does_not_define_prompt_attribute():
    """Sanity — the prompt is NOT a class attribute on MultiModelExtractor.

    This test exists to catch any future refactor that moves the constant
    onto the class without updating the lock test. If someone genuinely
    wants the prompt as a class attribute, this test must be updated AND
    Step G of the Piece 2 Stage 1 brief revisited.
    """
    cls = multi_extractor.MultiModelExtractor
    assert not hasattr(cls, "EXTRACTION_SYSTEM_PROMPT") or (
        getattr(cls, "EXTRACTION_SYSTEM_PROMPT", None)
        is multi_extractor.EXTRACTION_SYSTEM_PROMPT
    ), (
        "If MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT exists, it must "
        "be the same object as the module-level constant."
    )
