from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.sqlite import SqliteSaver 
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
import sqlite3
import requests

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

############# Tools ###########################
# tools
search_tool = DuckDuckGoSearchRun(region="us-en")

@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    A simple calculator tool that can perform basic arithmetic operations.
    Allowable operations are: add, subtract, multiply, divide.
    """

    if operation == "add":
        result = first_num + second_num
    elif operation == "subtract":
        result = first_num - second_num
    elif operation == "multiply":
        result = first_num * second_num
    elif operation == "divide":
        result = first_num / second_num
    else:
        return {"error": "Invalid operation. Please choose from add, subtract, multiply, divide."}

    return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}

@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """

    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={os.getenv('ALPHA_VANTAGE_API_KEY')}"
    r = requests.get(url)
    return r.json()

tools = [search_tool, calculator, get_stock_price]
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", api_key=api_key)
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]



def chat_node(state: ChatState) -> ChatState:
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}

def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    
    return list(all_threads)

conn = sqlite3.connect('chatbot.db', check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)
graph.add_node('chat_node', chat_node)
graph.add_node('tools', tool_node)
graph.add_edge(START, 'chat_node')
graph.add_conditional_edges('chat_node', tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)
