import streamlit as st
from langgraph_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage, AIMessage
import uuid



# ************************************* Utility Functions ********************************
def generate_thread_id():
    thread_id = str(uuid.uuid4())
    return thread_id

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    add_thread(thread_id)
    st.session_state["message_history"] = []

def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)

def load_conversation(thread_id):
    return chatbot.get_state(config={"configurable": {"thread_id": thread_id}}).values.get("messages", [])

# ************************************* Session Setup ************************************
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads()

add_thread(st.session_state["thread_id"])

# ************************************** Sidebar UI **************************************
st.sidebar.title("LangGraph Chatbot")
if st.sidebar.button("New Chat"):
    reset_chat()
st.sidebar.header("Chat History")
for thread_id in st.session_state["chat_threads"][::-1]:
    if st.sidebar.button(thread_id):
        st.session_state["thread_id"] = thread_id
        messages = load_conversation(thread_id)
        temp_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                temp_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                temp_messages.append({"role": "assistant", "content": message.content[0]["text"] if len(message.content) > 0 else ""})
        st.session_state["message_history"] = temp_messages

# ************************************** Main UI *****************************************
config = {
    'configurable': {'thread_id': st.session_state["thread_id"]},
    'metadata': {'thread_id': st.session_state["thread_id"]},
    'run_name': 'chat_turn'
    }

for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Type here...")

if user_input:
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    with st.chat_message("assistant"):
        ai_response = st.write_stream(
            chat_message.content[0]["text"] if len(chat_message.content) > 0 else ""
            for chat_message, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=config,
                stream_mode='messages',
            )
        )
        st.session_state["message_history"].append({"role": "assistant", "content": ai_response})

