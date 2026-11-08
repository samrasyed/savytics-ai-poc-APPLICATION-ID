from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class LLMMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None

    # Tells whether the model stopped because it hit the output token limit.
    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class LLMProvider(Protocol):
    name: str
    model: str

    # Sends the chat messages to the model and returns its raw reply.
    def complete(self, messages: list[LLMMessage], *, json_mode: bool) -> ProviderResponse: ...
