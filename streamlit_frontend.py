import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage

config = {'configurable': {'thread_id': 'thread_1'}}

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []


for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.text(message["content"])

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

