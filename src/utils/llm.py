"""
LLM utilities for Context Foundry

Supports Ollama (local) and OpenAI-compatible APIs
"""

import httpx
import json
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


class LLMClient:
    """Unified LLM client - routes to Ollama or OpenAI based on config"""

    def __init__(self):
        self.provider = settings.llm_provider

        if self.provider == "openai":
            self._client = OpenAIClient()
        else:
            self._client = OllamaClient()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        return await self._client.chat(messages, temperature)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        return await self._client.generate(
            prompt, system=system, temperature=temperature,
            format=format, max_tokens=max_tokens
        )

    async def health_check(self) -> bool:
        return await self._client.health_check()


class OpenAIClient:
    """Client for OpenAI-compatible APIs"""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url
        self.timeout = settings.llm_timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, temperature, max_tokens=max_tokens,
                               json_mode=format == "json")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                choice = result["choices"][0]
                return {
                    "text": choice["message"]["content"],
                    "role": choice["message"]["role"],
                    "model": result.get("model"),
                    "total_duration": None,
                    "usage": result.get("usage")
                }

            except httpx.TimeoutException as e:
                print(f"OpenAI Timeout: {e}")
                return {"error": str(e), "text": "", "fallback": True}

            except httpx.HTTPStatusError as e:
                print(f"OpenAI HTTP Error: {e.response.status_code} - {e.response.text[:200]}")
                return {"error": str(e), "text": "", "fallback": True}

            except Exception as e:
                print(f"OpenAI Error: {e}")
                return {"error": str(e), "text": "", "fallback": True}

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                return response.status_code == 200
        except:
            return False


class OllamaClient:
    """Client for Ollama API"""

    def __init__(self):
        self.base_url = settings.ollama_url
        self.model = settings.ollama_model
        self.timeout = settings.llm_timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=60.0, read=self.timeout, write=30.0, pool=30.0)) as client:
            options = {
                    "temperature": temperature
                }
            if max_tokens:
                options["num_predict"] = max_tokens

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": options
            }

            if system:
                payload["system"] = system

            if format:
                payload["format"] = format

            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "text": result.get("response", ""),
                    "model": result.get("model"),
                    "total_duration": result.get("total_duration"),
                    "prompt_eval_count": result.get("prompt_eval_count"),
                    "eval_count": result.get("eval_count")
                }

            except httpx.TimeoutException as e:
                print(f"LLM Timeout: {e}")
                return {
                    "error": f"LLM timeout: {str(e)}",
                    "text": "",
                    "fallback": True
                }

            except httpx.HTTPError as e:
                print(f"LLM HTTP Error: {e}")
                return {
                    "error": f"LLM HTTP error: {str(e)}",
                    "text": "",
                    "fallback": True
                }

            except Exception as e:
                print(f"LLM Unexpected Error: {e}")
                return {
                    "error": f"LLM error: {str(e)}",
                    "text": "",
                    "fallback": True
                }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> Dict[str, Any]:

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=60.0, read=self.timeout, write=30.0, pool=30.0)) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }

            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                message = result.get("message", {})

                return {
                    "text": message.get("content", ""),
                    "role": message.get("role"),
                    "model": result.get("model"),
                    "total_duration": result.get("total_duration")
                }

            except (httpx.TimeoutException, httpx.HTTPError) as e:
                return {
                    "error": str(e),
                    "text": "",
                    "fallback": True
                }

    async def health_check(self) -> bool:
        """Check if Ollama is accessible"""

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
