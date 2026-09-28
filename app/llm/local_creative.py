import json
from collections.abc import AsyncIterator

import httpx

from app.config import get_settings


CREATIVE_INSTRUCTIONS = """
You are JARVIS Creative, the user's private local model for fiction and free-form conversation.

Behavior:
- Follow the user's language and tone naturally.
- For fiction, prioritize immersive prose, continuity, vivid character voice, and a satisfying narrative flow.
- Respect formatting preferences such as continuous prose, fewer line breaks, first-person narration, or dialogue-heavy writing.
- For casual conversation, be relaxed and conversational rather than sounding like a task assistant.
- You do not have access to JARVIS device actions or external tools in this mode. Do not claim that you executed calls, calendar changes, navigation, or other device actions.
- Use profile or memory context only when it is supplied in the conversation context.
""".strip()


class LocalCreativeClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": CREATIVE_INSTRUCTIONS},
            *messages,
        ]

    def _payload(self, messages: list[dict[str, str]], *, stream: bool) -> dict:
        return {
            "model": self.settings.ollama_model,
            "messages": self._messages(messages),
            "stream": stream,
            "options": {"temperature": self.settings.ollama_temperature},
        }

    async def chat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.settings.ollama_base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
                response = await client.post(url, json=self._payload(messages, stream=False))
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.settings.ollama_base_url}"
            ) from exc
        if response.is_error:
            raise RuntimeError(
                f"Ollama request failed ({response.status_code}): {response.text[:300]}"
            )
        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return str(content)

    async def stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        url = f"{self.settings.ollama_base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
                async with client.stream(
                    "POST", url, json=self._payload(messages, stream=True)
                ) as response:
                    if response.is_error:
                        await response.aread()
                        raise RuntimeError(
                            f"Ollama request failed ({response.status_code}): "
                            f"{response.text[:300]}"
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        delta = data.get("message", {}).get("content", "")
                        if delta:
                            yield str(delta)
                        if data.get("done"):
                            break
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.settings.ollama_base_url}"
            ) from exc
