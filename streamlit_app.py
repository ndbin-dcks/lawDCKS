import streamlit as st
import openai
import time
import os
from datetime import datetime
from typing import List, Dict, Any
import sqlite3
import uuid
import warnings
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
import config  # Import file cấu hình

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    st.error("Lỗi: Không thể import OpenAI. Vui lòng kiểm tra requirements.txt")
    st.stop()

warnings.filterwarnings("ignore", category=DeprecationWarning)

st.set_page_config(page_title="AI Agent Pháp Chế Khoáng Sản", page_icon="⚖️", layout="wide")

if st.sidebar.checkbox("🔍 Debug Mode"):
    st.sidebar.write("**Debug Information:**")
    if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
        st.sidebar.write(f"✅ API key found: {api_key[:15]}...")
        try:
            client = OpenAI(api_key=api_key)
            st.sidebar.write("✅ OpenAI client created successfully")
        except Exception as e:
            st.sidebar.write(f"❌ Error: {e}")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .assistant {padding: 15px; border-radius: 8px; max-width: 75%; background: #f8f9fa; border-left: 4px solid #2c3e50; text-align: left; margin: 10px 0;}
    .user {padding: 15px; border-radius: 8px; max-width: 75%; background: #e8f4fd; border-left: 4px solid #3498db; text-align: right; margin-left: auto; margin: 10px 0;}
    .assistant::before {content: "⚖️ AI Agent: "; font-weight: bold; color: #2c3e50;}
    .user::before {content: "👤 Bạn: "; font-weight: bold; color: #3498db; float: left;}
    .main-header {text-align: center; padding: 20px 0; border-bottom: 2px solid #ecf0f1; margin-bottom: 30px;}
    .main-title {color: #2c3e50; font-size: 28px; font-weight: 600; margin-bottom: 10px;}
    .status-box {padding: 10px 15px; border-radius: 6px; margin: 10px 0; font-size: 14px;}
    .status-success {background: #d4edda; color: #155724; border: 1px solid #c3e6cb;}
    .status-error {background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;}
</style>
""", unsafe_allow_html=True)

# Sử dụng prompt từ config
SYSTEM_PROMPT = config.SYSTEM_PROMPT
ASSISTANT_WELCOME = config.ASSISTANT_WELCOME

def init_database():
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

def save_message(role, content):
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO chat_messages (role, content) VALUES (?, ?)', (role, content))
    conn.commit()
    conn.close()

def init_openai_client():
    try:
        api_key = st.secrets["OPENAI_API_KEY"].strip() if "OPENAI_API_KEY" in st.secrets else os.environ.get("OPENAI_API_KEY")
        if not api_key:
            st.error("⚠️ Chưa cấu hình OPENAI_API_KEY")
            st.stop()
        client = OpenAI(api_key=api_key)
        client.models.list()
        return client
    except Exception as e:
        st.error(f"⚠️ Lỗi khởi tạo OpenAI: {str(e)}")
        st.stop()

def get_vector_store_ids():
    vector_store_ids = []
    if "VECTOR_STORE_IDS" in st.secrets:
        ids = st.secrets["VECTOR_STORE_IDS"]
        vector_store_ids = [id.strip() for id in ids.split(",") if id.strip()] if isinstance(ids, str) else ids
    elif "VECTOR_STORE_ID" in st.secrets:
        vector_store_ids = [st.secrets["VECTOR_STORE_ID"].strip()]
    return vector_store_ids

def get_ai_response(client, question: str, conversation_history: List[Dict]) -> str:
    for attempt in range(3):
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history + [{"role": "user", "content": question}]
            vector_store_ids = get_vector_store_ids()
            params = {
                "model": "gpt-4o",
                "input": messages,
                "temperature": 0.1,
                "max_completion_tokens": 1000,
                "store": True
            }
            if vector_store_ids:
                params["tools"] = [{"type": "file_search", "vector_store_ids": vector_store_ids}]
            response = client.responses.create(**params)
            response_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
            return response_text
        except Exception as e:
            if attempt == 2:
                return f"❌ Lỗi sau 3 lần thử: {str(e)}"
            time.sleep(2)

def upload_files_to_vector_store(client):
    uploaded_files = st.file_uploader("Tải lên VBPL (*.docx)", type="docx", accept_multiple_files=True)
    if uploaded_files:
        for file in uploaded_files:
            response = client.files.create(file=file, purpose="assistants")
            client.vector_stores.files.create(vector_store_id=get_vector_store_ids()[0], file_id=response.id)
            st.success(f"Đã tải {file.name} lên vector store")

def export_chat():
    if st.button("Xuất lịch sử chat (PDF)"):
        pdf = SimpleDocTemplate("chat_history.pdf", pagesize=letter)
        story = [Paragraph(f"{'AI' if msg['role'] == 'assistant' else 'Bạn'}: {msg['content']}", style=None) for msg in st.session_state.messages]
        pdf.build(story)
        st.success("Đã xuất file chat_history.pdf")

def main():
    init_database()
    if "client" not in st.session_state:
        st.session_state.client = init_openai_client()

    st.markdown("""
    <div class="main-header">
        <div class="main-title">⚖️ AI Agent Pháp Chế Khoáng Sản</div>
        <div class="main-subtitle">Tư vấn pháp luật khoáng sản Việt Nam</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown("**📊 Trạng thái hệ thống:**")
        if st.session_state.client:
            st.markdown('<div class="status-box status-success">✅ OpenAI API: Kết nối</div>', unsafe_allow_html=True)
        vector_store_ids = get_vector_store_ids()
        if vector_store_ids:
            st.markdown(f'<div class="status-box status-success">✅ File Search: {len(vector_store_ids)} stores</div>', unsafe_allow_html=True)
        with st.expander("⚙️ Cấu hình"):
            if vector_store_ids:
                st.success(f"✅ Vector Store IDs: {vector_store_ids}")
            upload_files_to_vector_store(st.session_state.client)
            export_chat()

    with col1:
        st.markdown("**💬 Cuộc trò chuyện:**")
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": ASSISTANT_WELCOME}]
        for message in st.session_state.messages:
            st.markdown(f'<div class="{'assistant' if message["role"] == 'assistant' else 'user'}">{message["content"]}</div>', unsafe_allow_html=True)
        if prompt := st.chat_input("Nhập câu hỏi về pháp luật khoáng sản..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.markdown(f'<div class="user">{prompt}</div>', unsafe_allow_html=True)
            save_message("user", prompt)
            with st.spinner("🤔 Đang phân tích..."):
                response = get_ai_response(st.session_state.client, prompt, [msg for msg in st.session_state.messages[:-1] if msg["role"] != "system"])
                st.markdown(f'<div class="assistant">{response}</div>', unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_message("assistant", response)
                st.rerun()

if __name__ == "__main__":
    main()