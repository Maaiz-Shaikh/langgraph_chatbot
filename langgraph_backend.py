from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver 
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", api_key=api_key)

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState) -> ChatState:
    messages = state['messages']
    response = llm.invoke(messages)
    return {'messages': [response]}

checkpointer = MemorySaver()

graph = StateGraph(ChatState)
graph.add_node('chat_node', chat_node)
graph.add_edge(START, 'chat_node')
graph.add_edge('chat_node', END)

chatbot = graph.compile(checkpointer=checkpointer)