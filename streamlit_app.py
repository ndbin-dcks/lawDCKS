import streamlit as st
import openai
import time

st.set_page_config(page_title="AI Pháp chế Khoáng sản", page_icon="⚖️")

# Nhập API Key bảo mật (mỗi lần chạy hoặc dùng st.secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else st.text_input("Nhập OpenAI API Key:", type="password")

ASSISTANT_ID = st.secrets["ASSISTANT_ID"] if "ASSISTANT_ID" in st.secrets else st.text_input("Nhập Assistant ID:", type="password")

st.title("⚖️ AI Pháp chế Khoáng sản - Q&A Legal Agent")

st.markdown(
    """
    🟢 *Hỏi đáp luật khoáng sản, trả lời có trích dẫn Điều, Khoản và đúng nguồn pháp luật.*  
    **Dữ liệu trả lời dựa trên các văn bản pháp luật bạn đã upload vào Assistant (OpenAI Platform).**  
    """
)

if openai.api_key and ASSISTANT_ID:
    # Lưu session chat
    if "thread_id" not in st.session_state:
        thread = openai.beta.threads.create()
        st.session_state["thread_id"] = thread.id

    # Form nhập câu hỏi
    with st.form(key="qa_form", clear_on_submit=True):
        user_question = st.text_area("Nhập câu hỏi pháp luật:", placeholder="Ví dụ: Khi nào bị thu hồi giấy phép khai thác khoáng sản?")
        submitted = st.form_submit_button("Hỏi AI")

    if submitted and user_question.strip():
        with st.spinner("Đang gửi câu hỏi, vui lòng đợi..."):
            # Gửi câu hỏi lên Assistant API (tạo message mới trong thread)
            openai.beta.threads.messages.create(
                thread_id=st.session_state["thread_id"],
                role="user",
                content=user_question
            )
            # Gọi assistant để tạo câu trả lời
            run = openai.beta.threads.runs.create(
                thread_id=st.session_state["thread_id"],
                assistant_id=ASSISTANT_ID
            )
            # Đợi assistant trả lời
            status = "in_progress"
            with st.spinner("AI pháp chế đang xử lý..."):
                while status not in ["completed", "failed", "cancelled"]:
                    run_status = openai.beta.threads.runs.retrieve(thread_id=st.session_state["thread_id"], run_id=run.id)
                    status = run_status.status
                    time.sleep(1)
            # Lấy message trả lời cuối cùng
            messages = openai.beta.threads.messages.list(thread_id=st.session_state["thread_id"])
            answer = messages.data[0].content[0].text.value if messages.data else "Không có trả lời từ AI."
            st.markdown(f"#### **Trả lời:**\n\n{answer}")

            # Hiển thị nguồn trích dẫn (nếu có)
            if messages.data and messages.data[0].content[0].text.annotations:
                st.info("**Nguồn trích dẫn:**")
                for ann in messages.data[0].content[0].text.annotations:
                    st.markdown(f"- {ann.file_citation.display_name} (Trang: {ann.file_citation.page_number})")
else:
    st.warning("Vui lòng nhập OpenAI API Key và Assistant ID để sử dụng hệ thống.")

st.caption("© 2025 - Hệ thống AI pháp chế khoáng sản. Thiết kế bởi bạn và ChatGPT.")
