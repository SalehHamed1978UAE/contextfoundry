"""LLM client tests — cache hit/miss path with the StubLLMClient."""
import asyncio
from pydantic import BaseModel
from src.context_foundry.inference.llm.client import StubLLMClient


class _Out(BaseModel):
    answer: str


def test_stub_returns_schema_validated_payload():
    calls = {"n": 0}
    def responder(sys, user, schema):
        calls["n"] += 1
        return {"answer": "42"}
    stub = StubLLMClient(responder)
    out = asyncio.run(stub.call("sys", "user", output_schema=_Out))
    assert out.answer == "42"
    assert calls["n"] == 1


def test_stub_passes_schema_name_to_responder():
    seen = {}
    def responder(sys, user, schema):
        seen["schema"] = schema
        return {"answer": "ok"}
    stub = StubLLMClient(responder)
    asyncio.run(stub.call("s", "u", output_schema=_Out))
    assert seen["schema"] == "_Out"
