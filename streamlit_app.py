import streamlit as st
import openai
import sqlite3
import time
from datetime import datetime

# Cấu hình app
st.set_page_config(page_title="AI Pháp chế Khoáng sản", page_icon="⚖️", layout="wide")

# --- Lấy API Key và Assistant ID từ secrets hoặc nhập tay ---
def get_secret_or_input(secret_key, label, password=True):
    if secret_key in st.secrets:
        return st.secrets[secret_key]
    else:
        return st.text_input(label, type="password" if password else "default")

openai.api_key = get_secret_or_input("OPENAI_API_KEY", "Nhập OpenAI API Key:")
ASSISTANT_ID = get_secret_or_input("ASSISTANT_ID", "Nhập Assistant ID:", password=False)

# --- Hàm SQLite ---
def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    return conn

def save_chat(thread_id, role, content):
    conn = init_db()
    c = conn.cursor()
    c.execute("INSERT INTO chat (thread_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
              (thread_id, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_chat(thread_id):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp FROM chat WHERE thread_id = ? ORDER BY id ASC", (thread_id,))
    rows = c.fetchall()
    conn.close()
    return rows

st.title("⚖️ AI Pháp chế Khoáng sản - Q&A Legal Agent")

# --- Kiểm tra điều kiện đủ để tạo thread ---
thread_id = None
if openai.api_key and ASSISTANT_ID:
    if "thread_id" not in st.session_state:
        try:
            thread = openai.beta.threads.create()
            st.session_state["thread_id"] = thread.id
        except Exception as e:
            st.error(f"Lỗi khi tạo thread với Assistants API: {e}")
    thread_id = st.session_state.get("thread_id")
else:
    st.warning("Vui lòng nhập OpenAI API Key và Assistant ID để sử dụng hệ thống.")

# --- Giao diện chat ---
if thread_id:
    chat_history = load_chat(thread_id)
    st.markdown('<div style="height:400px;overflow-y:scroll;border:1px solid #ddd;padding:8px 0 8px 0;background:#f9f9f9">', unsafe_allow_html=True)
    for role, content, timestamp in chat_history:
        if role == "user":
            st.markdown(
                f"""
                <div style="display:flex;align-items:flex-start;">
                    <div style="background:#e5eaff;padding:12px 18px;border-radius:18px 18px 18px 4px;max-width:70%;margin-bottom:4px;">
                        <b>Bạn</b> <span style="color:#888;font-size:11px;">{timestamp}</span><br>{content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div style="display:flex;justify-content:flex-end;">
                    <div style="background:#fffbe0;padding:12px 18px;border-radius:18px 18px 4px 18px;max-width:70%;margin-bottom:4px;">
                        <b>AI</b> <span style="color:#888;font-size:11px;">{timestamp}</span><br>{content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- Nhập câu hỏi ---
    with st.form(key="qa_form", clear_on_submit=True):
        user_input = st.text_area(
            "Nhập câu hỏi pháp luật:",
            placeholder="Khi nào bị thu hồi giấy phép khai thác khoáng sản?",
            height=80  # >=68 pixels
        )
        submitted = st.form_submit_button("Gửi")

    if submitted and user_input.strip():
        # Lưu và hiển thị user chat
        save_chat(thread_id, "user", user_input)
        st.experimental_rerun()

        # Gửi lên Assistant API
        try:
            openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_input
            )
            run = openai.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
                temperature=0.1,
                max_tokens=800
            )
            status = "in_progress"
            with st.spinner("AI pháp chế đang xử lý..."):
                while status not in ["completed", "failed", "cancelled"]:
                    run_status = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                    status = run_status.status
                    time.sleep(1.2)
            # Lấy câu trả lời AI
            messages = openai.beta.threads.messages.list(thread_id=thread_id)
            ai_answer = messages.data[0].content[0].text.value if messages.data else "Không có trả lời từ AI."
            save_chat(thread_id, "assistant", ai_answer)
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Lỗi khi gửi câu hỏi tới Assistant: {e}")
else:
    st.info("Vui lòng nhập đầy đủ API Key và Assistant ID ở trên để bắt đầu.")

st.caption("© 2025 - Hệ thống AI pháp chế khoáng sản. Thiết kế bởi bạn và ChatGPT.")
