"""A rule-driven stand-in for the chat model so the graphs can be tested without an API key.

`fn(messages) -> AIMessage` decides each reply; bind_tools() is a no-op because the fake
simply emits tool_calls itself.
"""
import itertools
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_ids = itertools.count(1)


def call(name: str, **args) -> dict:
    return {"name": name, "args": args, "id": f"call_{next(_ids)}", "type": "tool_call"}


def ai(text: str = "", *calls: dict) -> AIMessage:
    return AIMessage(content=text, tool_calls=list(calls))


def system_of(messages: list[BaseMessage]) -> str:
    return str(messages[0].content) if messages else ""


class RuleLLM(BaseChatModel):
    fn: Any

    @property
    def _llm_type(self) -> str:
        return "rule-llm"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self.fn(messages))])
