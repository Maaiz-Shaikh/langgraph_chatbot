from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
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
    conversation_id: str
    title_generated: bool



def chat_node(state: ChatState) -> ChatState:
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}

def title_generation_node(state: ChatState) -> ChatState:
    """
    Generate title on first user message if not already generated.
    This node runs before the chat node to ensure title is generated early.
    """
    messages = state['messages']
    conversation_id = state.get('conversation_id', '')
    title_generated = state.get('title_generated', False)
    
    # Only generate if we haven't generated yet and we have a conversation_id
    if not title_generated and conversation_id and len(messages) > 0:
        # Find first human message
        first_user_message = None
        for msg in messages:
            if isinstance(msg, HumanMessage):
                first_user_message = msg.content
                break
        
        # Generate title if we found a user message and conversation doesn't already have one
        if first_user_message and not conversation_has_title(conversation_id):
            title = generate_conversation_title(first_user_message)
            update_conversation_title(conversation_id, title)
            
            return {
                'messages': state['messages'],
                'conversation_id': conversation_id,
                'title_generated': True
            }
    
    return state

def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    
    return list(all_threads)

conn = sqlite3.connect('chatbot.db', check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

# ***************************** Conversations Database *****************************
def init_conversation_db():
    """Initialize conversations table if not exists."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

def create_conversation(conversation_id):
    """Create a new conversation with null title."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (conversation_id, title)
            VALUES (?, NULL)
        ''', (conversation_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

def update_conversation_title(conversation_id, title):
    """Update conversation title."""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE conversation_id = ?
    ''', (title, conversation_id))
    conn.commit()

def get_conversation(conversation_id):
    """Get conversation metadata."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT conversation_id, title, created_at, updated_at
        FROM conversations
        WHERE conversation_id = ?
    ''', (conversation_id,))
    return cursor.fetchone()

def get_all_conversations():
    """Get all conversations sorted by most recent."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT conversation_id, title, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
    ''')
    return cursor.fetchall()

def conversation_has_title(conversation_id):
    """Check if conversation already has a title."""
    conv = get_conversation(conversation_id)
    return conv is not None and conv[1] is not None

# ***************************** Title Generation Service *****************************
def generate_conversation_title(user_message: str) -> str:
    """
    Generate a concise conversation title from the first user message.
    
    Args:
        user_message: The first user message
        
    Returns:
        Generated title (3-8 words) or fallback title
    """
    if not user_message or len(user_message.strip()) == 0:
        return "New Resume Chat"
    
    system_prompt = """You are a title generation assistant for a resume review chatbot.
Generate a concise, descriptive conversation title based on the user's message.

Rules:
- Maximum 6 words
- Do not use quotation marks
- Do not include punctuation unless necessary (hyphens OK)
- Return only the title, nothing else
- Make it descriptive and easy to scan in a sidebar
- Focus on the key topic or role mentioned

Examples:
- "Google SWE Resume Review" (from "Review my resume for Google SWE roles")
- "ATS Optimization Help" (from "Help me improve ATS score")
- "Flutter Developer Analysis" (from "Analyze my Flutter developer resume")"""
    
    try:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ])
        
        title = response.content.strip()
        
        if not title or title == "":
            return "New Resume Chat"
        
        # Validate title length - keep max 8 words
        words = title.split()
        if len(words) > 8:
            title = " ".join(words[:6])
        
        return title
    
    except Exception as e:
        print(f"Error generating title: {e}")
        return "New Resume Chat"

# Initialize database
init_conversation_db()

graph = StateGraph(ChatState)
graph.add_node('title_generation', title_generation_node)
graph.add_node('chat_node', chat_node)
graph.add_node('tools', tool_node)
graph.add_edge(START, 'title_generation')
graph.add_edge('title_generation', 'chat_node')
graph.add_conditional_edges('chat_node', tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)
