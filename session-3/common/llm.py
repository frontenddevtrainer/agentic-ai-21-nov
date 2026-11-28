import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()


def get_llm(temperature: float = 0.0):
    """One place to change the model for every demo."""
    return ChatAnthropic(
        model=os.environ.get("MODEL_NAME", "claude-sonnet-5-5"),
        temperature=temperature,
        max_tokens=2048,
    )
