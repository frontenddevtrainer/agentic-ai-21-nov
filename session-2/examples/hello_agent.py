from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_openrouter import ChatOpenRouter
from langchain_groq import ChatGroq
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

# Use docstring """""" to define the usage and purpose of the tools.
@tool
def add(a:int, b: int) -> int:
    """Add two numbers."""
    return a + b

@tool
def multiple(a:int, b: int) -> int:
    """multiple two numbers."""
    return a * b

@tool 
def income_tax (income: int, slab: int) -> int:
    "income param is total income before tax, slab this is % of tax charged"
    # rest api /post incometax
    return 


model = ChatOpenRouter(model="anthropic/claude-haiku-5.5", max_tokens=1000)
# model = ChatGroq(model="anthropic/claude-haiku-5.5", max_tokens=1000)
agent= create_agent(model, checkpointer=InMemorySaver())


def ask(text, config):
    result = agent.invoke({"messages": [("user", text)]}, config)
    return result["messages"][-1].content

config = { "configurable" : { "thread_id"  : "rhkwjrjwehkrhhjfghdjfgs748234"} }
config2 = { "configurable" : { "thread_id"  : "hjkhfjdfggsdjfg3424gh4j"} }

print(ask("Your name is now Alex", config))
print(ask("You are based in Delhi", config))
print(ask("What is your name and city you are based in.", config))
print("----------------------------------------------")
print(ask("Your name is now Amit", config2))
print(ask("You are based in London", config2))
print(ask("What is your name and city you are based in.", config2))


# result = agent.invoke({ "messages" : [( "user", "what is the capital of India." )] })
# result1 = agent.invoke({ "messages" : [( "user", "Your name is now Alex" )] })
# result2 = agent.invoke({ "messages" : [( "user", "You are based in Delhi" )] })
# result3 = agent.invoke({ "messages" : [( "user", "What is your name and city you are based in." )] })