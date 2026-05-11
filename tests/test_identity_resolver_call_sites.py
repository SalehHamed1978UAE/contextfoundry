"""
Stage 1I Phase 1.5 — IdentityResolver call-site regression tests.

Static + targeted regression tests verifying every production call site to
``IdentityResolver(...)`` passes a ``tenant_id`` keyword (or stops/fail-closes
explicitly).

Why static AST instead of e2e: the production call sites live in Flask routes
(``web_app.py``) and a background scheduler (``scheduler.py``). Spinning up
real Flask + scheduler for one assertion per call site is high-cost and
brittle relative to the invariant being tested ("the call passes
tenant_id"). The brief (L125) explicitly authorizes a "focused
regression/static test" for this case.

This complements ``tests/test_identity_resolver_tenant_isolation.py`` which
covers the resolver internals.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_FILES = [
    REPO_ROOT / "src" / "context_foundry" / "agents" / "scheduler.py",
    REPO_ROOT / "web_app.py",
]
RESOLVER_FILE = REPO_ROOT / "src" / "context_foundry" / "agents" / "identity_resolver.py"


def _iter_identity_resolver_calls(tree: ast.AST) -> Iterator[ast.Call]:
    """Yield every ast.Call to a name 'IdentityResolver' in the module."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "IdentityResolver":
            yield node


def _has_tenant_id_kwarg(call: ast.Call) -> bool:
    return any(kw.arg == "tenant_id" for kw in call.keywords)


def _file_calls(path: Path) -> List[Tuple[int, ast.Call]]:
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    return [(c.lineno, c) for c in _iter_identity_resolver_calls(tree)]


# ---------------------------------------------------------------------------
# T01 — Production call sites all pass tenant_id (or no longer call resolver)
# ---------------------------------------------------------------------------


def test_p01_web_app_resolve_duplicates_passes_tenant_id():
    calls = _file_calls(REPO_ROOT / "web_app.py")
    assert calls, "Expected at least one IdentityResolver call site in web_app.py"
    for lineno, call in calls:
        assert _has_tenant_id_kwarg(call), (
            f"web_app.py:{lineno} IdentityResolver(...) call is missing required "
            f"tenant_id= kwarg. This regresses Stage 1I Phase 1.5 — every "
            f"production call site MUST pass tenant_id explicitly."
        )


def test_p02_web_app_call_sites_use_g_tenant_id():
    """
    The two web_app.py call sites must source tenant_id from `g.tenant_id`,
    not a hardcoded UUID, env var, or session entity. Defense against
    well-meaning regressions.
    """
    src = (REPO_ROOT / "web_app.py").read_text()
    tree = ast.parse(src)
    bad_lines: List[Tuple[int, str]] = []
    for call in _iter_identity_resolver_calls(tree):
        lineno = call.lineno
        kw = next((k for k in call.keywords if k.arg == "tenant_id"), None)
        if kw is None:
            continue
        # The expression must be `g.tenant_id` or a Name/Attribute that
        # resolves through Flask `g`. We accept ast.Attribute(value=Name('g'),
        # attr='tenant_id') as the canonical safe form.
        is_g_dot_tenant_id = (
            isinstance(kw.value, ast.Attribute)
            and kw.value.attr == "tenant_id"
            and isinstance(kw.value.value, ast.Name)
            and kw.value.value.id == "g"
        )
        if not is_g_dot_tenant_id:
            bad_lines.append(
                (lineno, ast.unparse(kw.value) if hasattr(ast, "unparse") else "<expr>")
            )
    assert not bad_lines, (
        f"web_app.py IdentityResolver tenant_id= must come from `g.tenant_id`. "
        f"Other sources risk hardcoding or entity-derived inference. "
        f"Offenders: {bad_lines}"
    )


def test_p03_scheduler_does_not_construct_identity_resolver():
    """
    Phase 1.5 stop-and-report decision: the scheduler call site is now wrapped
    in a NotImplementedError BEFORE any IdentityResolver(...) is constructed.
    Verify there is no live IdentityResolver(...) call in scheduler.py.
    Re-enabling requires the per-tenant-iteration design decision (see
    scheduler.py inline comment + brief).
    """
    calls = _file_calls(REPO_ROOT / "src" / "context_foundry" / "agents" / "scheduler.py")
    assert not calls, (
        f"scheduler.py must not construct IdentityResolver until per-tenant "
        f"iteration is added (Stage 1I Phase 1.5 stop-and-report). Found "
        f"calls at: {[lineno for lineno, _ in calls]}"
    )


def test_p04_scheduler_raises_named_error_on_run_identity_resolution():
    """
    Verify scheduler.py contains the named NotImplementedError path that
    fires when self.config.run_identity_resolution is True. Prevents silent
    revert to the broken behavior.
    """
    src = (REPO_ROOT / "src" / "context_foundry" / "agents" / "scheduler.py").read_text()
    assert "NotImplementedError(" in src, (
        "scheduler.py must raise NotImplementedError when "
        "run_identity_resolution is True (Phase 1.5 stop-and-report)."
    )
    assert "Scheduler-driven identity resolution is disabled" in src, (
        "scheduler.py NotImplementedError message must be the Phase 1.5 "
        "named message so misconfiguration is grep-able in logs."
    )


# ---------------------------------------------------------------------------
# T02 — Phase 1 guards remain intact (identity_resolver.py)
# ---------------------------------------------------------------------------


def test_p05_resolver_init_still_requires_tenant_id():
    """Phase 1 guard #1 must remain: __init__ raises ValueError on missing tenant_id."""
    from src.context_foundry.agents.identity_resolver import IdentityResolver
    with pytest.raises(ValueError, match="tenant_id"):
        IdentityResolver(session=None, tenant_id=None)
    with pytest.raises(ValueError, match="tenant_id"):
        IdentityResolver(session=None, tenant_id="")


def test_p06_resolver_signature_did_not_silently_default_tenant_id():
    """
    Defend against a future regression where someone "fixes" callers by
    adding `tenant_id: str = None` default to IdentityResolver.__init__.
    The signature MUST keep tenant_id as a required positional/keyword arg
    with NO default (the ValueError check is the safety net but signatures
    matter for IDE/type checkers).
    """
    import inspect
    from src.context_foundry.agents.identity_resolver import IdentityResolver
    sig = inspect.signature(IdentityResolver.__init__)
    tenant_id_param = sig.parameters.get("tenant_id")
    assert tenant_id_param is not None, (
        "IdentityResolver.__init__ must have a tenant_id parameter."
    )
    assert tenant_id_param.default is inspect.Parameter.empty, (
        "IdentityResolver.__init__ tenant_id MUST NOT have a default value. "
        "Tenant context must always be supplied explicitly by the caller "
        "(Stage 1I + 1.5)."
    )


# ---------------------------------------------------------------------------
# T03 — No global fallback / no hardcoded tenant in production call sites
# ---------------------------------------------------------------------------


def test_p07_no_hardcoded_tenant_uuid_near_call_sites():
    """
    Scan the lines surrounding every production IdentityResolver call site
    for hardcoded tenant UUIDs (a 32-hex-with-dashes pattern). A hardcoded
    tenant_id at a call site would defeat the Phase 1.5 fix.
    """
    import re
    uuid_re = re.compile(
        r"['\"][0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}['\"]"
    )
    for path in PRODUCTION_FILES:
        src_lines = path.read_text().splitlines()
        tree = ast.parse(path.read_text(), filename=str(path))
        for call in _iter_identity_resolver_calls(tree):
            lineno = call.lineno
            window = src_lines[max(0, lineno - 4):lineno + 1]
            for ln, text in zip(range(lineno - 3, lineno + 2), window):
                m = uuid_re.search(text)
                if m:
                    pytest.fail(
                        f"{path.name}:{ln} contains a hardcoded UUID near an "
                        f"IdentityResolver call site: {m.group(0)!r}. "
                        f"Phase 1.5 forbids hardcoded tenant; use g.tenant_id."
                    )


def test_p09_scheduler_config_defaults_identity_off():
    """
    Architect HIGH (2026-05-11): SchedulerConfig.run_identity_resolution
    MUST default to False until per-tenant iteration is implemented in
    _run_cycle. If left True, every scheduler cycle raises
    NotImplementedError and skips downstream gardener / extraction-monitor /
    auto-trigger / learning-flow tasks.
    """
    from src.context_foundry.agents.scheduler import SchedulerConfig
    cfg = SchedulerConfig()
    assert cfg.run_identity_resolution is False, (
        "SchedulerConfig.run_identity_resolution must default to False "
        "(Stage 1I Phase 1.5). Re-enabling requires per-tenant iteration "
        "in scheduler._run_cycle first."
    )


def test_p10_init_scheduler_disables_identity_resolution():
    """
    Defense in depth: even if SchedulerConfig default is changed in the
    future, web_app.init_scheduler() must explicitly set
    run_identity_resolution=False until per-tenant iteration is implemented.
    Static check on the source — importing web_app starts the Flask app.
    """
    src = (REPO_ROOT / "web_app.py").read_text()
    # Locate the init_scheduler block and verify it sets the flag to False.
    idx = src.find("def init_scheduler")
    assert idx != -1, "init_scheduler not found in web_app.py"
    block = src[idx:idx + 2000]
    assert "run_identity_resolution=False" in block, (
        "web_app.init_scheduler() must set run_identity_resolution=False "
        "(Stage 1I Phase 1.5 architect HIGH). Setting True will raise "
        "NotImplementedError every cycle."
    )
    assert "run_identity_resolution=True" not in block, (
        "web_app.init_scheduler() must NOT set run_identity_resolution=True "
        "until per-tenant iteration exists in scheduler._run_cycle."
    )


def test_p08_no_global_fallback_phrases_in_resolver_or_call_sites():
    """
    Scan resolver + production call-site files for phrases that would
    indicate a 'global fallback' regression (e.g., 'fallback tenant',
    'default tenant', 'or DEFAULT_TENANT'). Heuristic but cheap.
    """
    forbidden = (
        "fallback tenant",
        "default tenant",
        "DEFAULT_TENANT_ID",
        "or DEFAULT_TENANT",
        "if tenant_id is None: tenant_id =",
        "tenant_id = tenant_id or",
    )
    for path in [RESOLVER_FILE, *PRODUCTION_FILES]:
        src = path.read_text()
        for phrase in forbidden:
            assert phrase not in src, (
                f"{path.name} contains forbidden global-fallback phrase "
                f"{phrase!r}. Phase 1.5 invariant: no global fallback."
            )
