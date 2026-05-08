"""LLM client — Anthropic Claude Sonnet 4.6 with Postgres-backed cache.

NO Redis (per replit.md: PostgreSQL only). Cache lives in `llm_cache` table
(auto-created on first use). Cache key = sha256 of (model, system, user, schema_name).

`temperature=0` is non-negotiable. Determinism is the contract.

Provider-agnostic interface: subclass `LLMClient` to swap providers later.
Embeddings stay on OpenAI (`text-embedding-3-small`) per Anthropic gap.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional, Type, Dict, Callable
from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


DEFAULT_MODEL = os.environ.get("LLM_MODEL_OVERRIDE", "claude-sonnet-4-6")
BENCHMARK_PINNED_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "8192"))


class LLMError(RuntimeError):
    pass


def _ensure_cache_table(session: Session) -> None:
    """Create the llm_cache table if it doesn't exist. Idempotent."""
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS llm_cache (
            cache_key   TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            response    JSONB NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """))
    session.commit()


def _hash_prompt(model: str, system_prompt: str, user_prompt: str,
                 schema_name: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"||")
    h.update(system_prompt.encode("utf-8"))
    h.update(b"||")
    h.update(user_prompt.encode("utf-8"))
    h.update(b"||")
    h.update((schema_name or "").encode("utf-8"))
    return h.hexdigest()


class LLMClient:
    """Anthropic-backed client with Postgres cache and structured output.

    Args:
        session: SQLAlchemy session for the cache table.
        api_key: Anthropic API key. Required (loud failure on None).
        model: model identifier; defaults to env LLM_MODEL_OVERRIDE or sonnet 4.5.
        pin_model: when True (benchmark fixtures), ignore the env override.
    """

    def __init__(self, session: Session, api_key: Optional[str] = None,
                 model: Optional[str] = None, pin_model: bool = False):
        self.session = session
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY missing. The FactEvaluator engine refuses to "
                "fall back to a different provider — set the secret and restart."
            )
        self.model = BENCHMARK_PINNED_MODEL if pin_model else (model or DEFAULT_MODEL)
        _ensure_cache_table(session)
        # Lazy-import so unit tests that don't touch the network don't need it.
        try:
            import anthropic  # noqa
            self._anthropic_module = anthropic
        except ImportError as e:
            raise LLMError(f"anthropic SDK not installed: {e}") from e

    # ----------------------------------------------------------- caching
    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        row = self.session.execute(
            text("SELECT response FROM llm_cache WHERE cache_key = :k"),
            {"k": key},
        ).fetchone()
        if not row:
            return None
        return row[0]

    def _cache_put(self, key: str, response: Dict[str, Any]) -> None:
        self.session.execute(text("""
            INSERT INTO llm_cache (cache_key, model, response)
            VALUES (:k, :m, CAST(:r AS jsonb))
            ON CONFLICT (cache_key) DO NOTHING
        """), {"k": key, "m": self.model, "r": json.dumps(response)})
        self.session.commit()

    # ----------------------------------------------------------- main call
    async def call(self, system_prompt: str, user_prompt: str,
                   output_schema: Optional[Type[BaseModel]] = None,
                   cache: bool = True) -> Any:
        """Issue an LLM call. Returns dict if no schema, else schema instance."""
        from ..observability.trace import tracer
        schema_name = output_schema.__name__ if output_schema else None
        key = _hash_prompt(self.model, system_prompt, user_prompt, schema_name)

        if cache:
            cached = self._cache_get(key)
            if cached is not None:
                logger.debug(f"[LLMClient] cache HIT key={key[:12]}")
                tracer.bump("llm_cache_hit_count")
                return self._coerce(cached, output_schema)

        logger.debug(f"[LLMClient] cache MISS key={key[:12]} → API")
        tracer.bump("llm_call_count")
        client = self._anthropic_module.Anthropic(api_key=self.api_key)

        # Force JSON via tool_use when a schema is provided.
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if output_schema is not None:
            tool_schema = output_schema.model_json_schema()
            kwargs["tools"] = [{
                "name": "emit_" + output_schema.__name__.lower(),
                "description": f"Emit a {output_schema.__name__} payload.",
                "input_schema": tool_schema,
            }]
            kwargs["tool_choice"] = {
                "type": "tool",
                "name": "emit_" + output_schema.__name__.lower(),
            }

        try:
            resp = client.messages.create(**kwargs)
        except Exception as e:
            raise LLMError(f"Anthropic call failed: {e}") from e

        payload: Dict[str, Any]
        if output_schema is not None:
            tool_use = next(
                (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_use is None:
                raise LLMError(
                    f"Expected tool_use block for {output_schema.__name__}, got: "
                    f"{[getattr(b, 'type', '?') for b in resp.content]}"
                )
            payload = dict(tool_use.input)
        else:
            text_block = next(
                (b for b in resp.content if getattr(b, "type", None) == "text"),
                None,
            )
            payload = {"text": text_block.text if text_block else ""}

        if cache:
            self._cache_put(key, payload)
        return self._coerce(payload, output_schema)

    @staticmethod
    def _coerce(payload: Dict[str, Any], schema: Optional[Type[BaseModel]]) -> Any:
        if schema is None:
            return payload
        try:
            return schema.model_validate(payload)
        except ValidationError as e:
            raise LLMError(f"LLM payload failed schema {schema.__name__}: {e}") from e


class StubLLMClient(LLMClient):
    """Deterministic stub for unit tests. Routes prompts through a callable.

    Provide a `responder(system, user, schema_name) -> dict` callable. The stub
    bypasses Postgres cache and the Anthropic SDK entirely.
    """
    def __init__(self, responder: Callable[[str, str, Optional[str]], Dict[str, Any]],
                 model: str = "stub-model"):
        # Bypass parent __init__ entirely
        self.model = model
        self.session = None
        self.api_key = "stub"
        self._responder = responder

    async def call(self, system_prompt: str, user_prompt: str,
                   output_schema: Optional[Type[BaseModel]] = None,
                   cache: bool = True) -> Any:
        schema_name = output_schema.__name__ if output_schema else None
        payload = self._responder(system_prompt, user_prompt, schema_name)
        return self._coerce(payload, output_schema)
