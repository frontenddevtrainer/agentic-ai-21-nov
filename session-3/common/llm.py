import os

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()


def get_llm(temperature: float = 0.0):
    """One place to change the model for every demo."""
    return ChatOpenRouter(
        model=os.environ.get("MODEL_NAME", "anthropic/claude-haiku-5.5"),
        temperature=temperature,
        max_tokens=2048,
    )

def get_best_llm(temperature: float = 0.0):
    """One place to change the model for every demo."""
    return ChatOpenRouter(
        model=os.environ.get("MODEL_NAME", "anthropic/claude-opus-5.5"),
        temperature=temperature,
        max_tokens=2048,
    )