from openai import OpenAI
import streamlit as st
import time
from datetime import datetime

st.set_page_config(page_title="AI Pháp chế Khoáng sản", page_icon="⚖️", layout="wide")

def get_secret_or_input(secret_key, label, password=True):
    if secret_key in st.secrets:
        return st.secrets[secret_key]
    else:
        return st.text_input(label, type="password" if password else "default")

OPENAI_API_KEY = get_secret_or_input("OPENAI_API_KEY", "Nhập OpenAI API Key:")
ASSISTANT_ID = get_secret_or_input("ASSISTANT_ID", "Nhập Assistant ID:", password=False)

st.title("⚖️ AI Pháp chế Khoáng sản")

if OPENAI_API_KEY and ASSISTANT_ID:
    client = OpenAI(api_key=OPENAI_API_KEY)

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "thread_id" not in st.session_state:
        thread = client.threads.create()
        st.session_state["thread_id"] = thread.id

    st.markdown('<div style="height:400px;overflow-y:auto;border:1px solid #ddd;padding:8px 0;background:#f9f9f9">', unsafe_allow_html=True)
    for item in st.session_state["chat_history"]:
        who, content, timestamp = item["role"], item["content"], item["time"]
        if who == "user":
            st.markdown(
                f"""<div style="display:flex;align-items:flex-start;">
                    <div style="background:#e5eaff;padding:12px 18px;border-radius:18px 18px 18px 4px;max-width:70%;margin-bottom:4px;">
                        <b>Bạn</b> <span style="color:#888;font-size:11px;">{timestamp}</span><br>{content}
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                f"""<div style="display:flex;justify-content:flex-end;">
                    <div style="background:#fffbe0;padding:12px 18px;border-radius:18px 18px 4px 18px;max-width:70%;margin-bottom:4px;">
                        <b>AI</b> <span style="color:#888;font-size:11px;">{timestamp}</span><br>{content}
                    </div>
                </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.form(key="qa_form", clear_on_submit=True):
        user_input = st.text_area("Nhập câu hỏi pháp luật:", placeholder="Khi nào bị thu hồi giấy phép khai thác khoáng sản?", height=80)
        submitted = st.form_submit_button("Gửi")

    if submitted and user_input.strip():
        st.session_state["chat_history"].append({
            "role": "user",
            "content": user_input,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        with st.spinner("AI pháp chế đang xử lý..."):
            client.threads.messages.create(
                thread_id=st.session_state["thread_id"],
                role="user",
                content=user_input
            )
            run = client.threads.runs.create(
                thread_id=st.session_state["thread_id"],
                assistant_id=ASSISTANT_ID
            )
            while True:
                run_status = client.threads.runs.retrieve(
                    thread_id=st.session_state["thread_id"],
                    run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled"]:
                    st.error("Có lỗi khi xử lý câu hỏi.")
                    break
                time.sleep(1)
            messages = client.threads.messages.list(thread_id=st.session_state["thread_id"])
            ai_answer = messages.data[-1].content[0].text.value if messages.data else "Không có trả lời từ AI."
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": ai_answer,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        st.rerun()

else:
    st.warning("Vui lòng nhập OpenAI API Key và Assistant ID để sử dụng hệ thống.")

st.caption("© 2025 - Hệ thống AI pháp chế khoáng sản.")
