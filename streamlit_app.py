import streamlit as st
import openai
import logging
from typing import Optional, List, Dict, Any

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Thông tin cấu hình
VECTOR_STORE_ID = "vs_68695626c77881918a6b72f1b9bdd4c9"  # Thay bằng ID vector store của bạn
MODEL = "gpt-4o"

# Khởi tạo client OpenAI
@st.cache_resource
def init_client():
    return openai.OpenAI(api_key=st.secrets["openai"]["api_key"])

def check_api_key(client) -> bool:
    """Kiểm tra tính hợp lệ của API key"""
    try:
        client.models.list()
        logger.info("API key is valid")
        return True
    except Exception as e:
        logger.error(f"API key error: {str(e)}")
        st.error(f"API key error: {str(e)}")
        return False

def check_vector_store(client, vector_store_id: str) -> bool:
    """Kiểm tra trạng thái vector store"""
    try:
        store = client.vector_stores.retrieve(vector_store_id)
        logger.info(f"Vector Store ID: {vector_store_id}")
        logger.info(f"Status: {store.status}")
        logger.info(f"File Count: {store.file_counts.total}")
        if store.file_counts.total > 0:
            files = client.vector_stores.files.list(vector_store_id)
            logger.info("Files in Vector Store:")
            for file in files.data:
                logger.info(f"- File ID: {file.id} (Status: {file.status})")
        return store.status == "completed"
    except Exception as e:
        logger.error(f"Vector Store Error: {str(e)}")
        st.error(f"Vector Store Error: {str(e)}")
        return False

def get_ai_response(client, question: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Lấy phản hồi từ Responses API với File Search"""
    try:
        messages = [{"role": "system", "content": "Bạn là AI chuyên về pháp luật khoáng sản Việt Nam."}] + conversation_history + [{"role": "user", "content": question}]
        tools = [{"type": "file_search", "vector_store_ids": [VECTOR_STORE_ID]}]
        response = client.responses.create(
            model=MODEL,
            input=messages,
            tools=tools,
            store=True
        )
        response_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
        logger.info("Responses API call successful")
        return {
            "success": True,
            "response": response_text,
            "api_used": "responses",
            "has_file_search": True
        }
    except Exception as e:
        logger.error(f"Responses API Error: {str(e)}")
        return {
            "success": False,
            "error": f"Responses API Error: {str(e)}",
            "api_used": "error"
        }

def main():
    st.title("Tra Cứu Văn Bản Pháp Luật Khoáng Sản")
    
    # Khởi tạo session state
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    
    # Khởi tạo client
    client = init_client()
    if not check_api_key(client):
        st.stop()

    if not check_vector_store(client, VECTOR_STORE_ID):
        st.error("Vector Store không hợp lệ hoặc không sẵn sàng.")
        st.stop()

    # Nhập câu hỏi
    question = st.text_input("Nhập câu hỏi về pháp luật khoáng sản:", "Điều 2 Luật Khoáng sản 2010 nói gì?")
    if st.button("Gửi câu hỏi"):
        if question:
            result = get_ai_response(client, question, st.session_state.conversation_history)
            if result["success"]:
                st.session_state.conversation_history.append({"role": "user", "content": question})
                st.session_state.conversation_history.append({"role": "assistant", "content": result["response"]})
                st.success("Phản hồi:")
                st.write(result["response"])
            else:
                st.error(result["error"])

    # Hiển thị lịch sử trò chuyện
    st.subheader("Lịch sử trò chuyện")
    for message in st.session_state.conversation_history:
        role = "Bạn" if message["role"] == "user" else "AI"
        st.write(f"{role}: {message['content']}")

if __name__ == "__main__":
    main()