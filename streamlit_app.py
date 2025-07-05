import streamlit as st
import openai
import time
import json
import os
from datetime import datetime
import tempfile
import PyPDF2
import docx
from typing import List, Dict, Any

# ===============================
# CONFIGURATION & SETUP
# ===============================

# Page config
st.set_page_config(
    page_title="AI Agent Pháp Chế Khoáng Sản",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tối ưu tham số cho độ chính xác cao
OPTIMIZED_PARAMS = {
    "chunk_size": 1000,  # Chunk nhỏ hơn để tránh mất thông tin quan trọng
    "chunk_overlap": 200,  # Overlap cao để đảm bảo tính liên tục
    "temperature": 0.1,  # Rất thấp để đảm bảo độ chính xác
    "max_tokens": 4000,  # Đủ dài cho câu trả lời chi tiết
    "top_p": 0.95,  # Tập trung vào câu trả lời có độ tin cậy cao
}

# System prompt được tối ưu cho pháp luật khoáng sản
SYSTEM_PROMPT = """
Bạn là AI Agent chuyên về pháp luật khoáng sản Việt Nam với độ chính xác cao nhất. 

NGUYÊN TẮC HOẠT ĐỘNG:
1. **Độ chính xác tuyệt đối**: Chỉ trả lời dựa trên văn bản pháp luật có trong tài liệu
2. **Xử lý thay đổi pháp luật**: Luôn kiểm tra và cảnh báo về:
   - Văn bản đã bị sửa đổi, bổ sung
   - Văn bản đã bị thay thế hoàn toàn
   - Văn bản đã hết hiệu lực
   - Quy định có thể bị mâu thuẫn giữa các văn bản

3. **Cấu trúc trả lời bắt buộc**:
   ```
   📋 **THÔNG TIN PHÁP LÝ**
   - Căn cứ pháp lý: [Tên văn bản, điều khoản cụ thể]
   - Trạng thái hiệu lực: [Còn hiệu lực/Đã sửa đổi/Đã hết hiệu lực]
   - Ngày ban hành/sửa đổi: [DD/MM/YYYY]

   💡 **NỘI DUNG GIẢI ĐÁP**
   [Trả lời chi tiết, chính xác]

   ⚠️ **CẢNH BÁO QUAN TRỌNG**
   [Nếu có vấn đề về hiệu lực, thay đổi, hoặc mâu thuẫn]

   🔍 **GỢI Ý KIỂM TRA THÊM**
   [Văn bản liên quan cần xem xét]
   ```

4. **Xử lý các trường hợp đặc biệt**:
   - Nếu câu hỏi về quy định đã thay đổi: Nêu rõ quy định cũ và mới
   - Nếu có mâu thuẫn giữa văn bản: Chỉ ra và giải thích thứ tự ưu tiên
   - Nếu không có thông tin: Thẳng thắn nói "Không có thông tin trong tài liệu"
   - Nếu thông tin không đầy đủ: Nêu rõ hạn chế và đề xuất tìm hiểu thêm

5. **Đặc biệt chú ý về khoáng sản**:
   - Phân biệt rõ khoáng sản làm vật liệu xây dựng thông thường vs khoáng sản quý hiếm
   - Quy trình cấp phép thăm dò, khai thác
   - Nghĩa vụ tài chính (thuế, phí, lệ phí)
   - Bảo vệ môi trường trong khai thác khoáng sản
   - Xử lý vi phạm và chế tài

6. **Ngôn ngữ và văn phong**:
   - Sử dụng thuật ngữ pháp lý chính xác
   - Giải thích rõ ràng, dễ hiểu
   - Tránh diễn giải hoặc suy đoán
   - Luôn dẫn chiếu cụ thể điều, khoản, điểm

TUYỆT ĐỐI KHÔNG ĐƯỢC:
- Đưa ra lời khuyên pháp lý mà không có căn cứ
- Diễn giải rộng hoặc suy đoán nội dung
- Bỏ qua việc cảnh báo về thay đổi pháp luật
- Trả lời khi không chắc chắn về thông tin
"""

# ===============================
# HELPER FUNCTIONS
# ===============================

def init_openai_client():
    """Initialize OpenAI client with API key"""
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("⚠️ Chưa cấu hình OPENAI_API_KEY. Vui lòng thêm vào Streamlit secrets.")
        st.stop()
    return openai.OpenAI(api_key=api_key)

def extract_text_from_pdf(file) -> str:
    """Extract text from PDF file"""
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Lỗi đọc file PDF: {str(e)}")
        return ""

def extract_text_from_docx(file) -> str:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Lỗi đọc file DOCX: {str(e)}")
        return ""

def preprocess_legal_text(text: str) -> str:
    """
    Tối ưu hóa nội dung văn bản pháp luật trước khi upload
    """
    # Loại bỏ ký tự đặc biệt và khoảng trắng thừa
    import re
    
    # Chuẩn hóa ký tự tiếng Việt
    text = text.replace('\ufeff', '')  # Loại bỏ BOM
    text = re.sub(r'\s+', ' ', text)   # Chuẩn hóa khoảng trắng
    
    # Cải thiện cấu trúc cho AI hiểu
    # Đánh dấu rõ các phần quan trọng
    text = re.sub(r'(Điều \d+[a-z]*\.)', r'\n\n**\1**\n', text)
    text = re.sub(r'(Khoản \d+\.)', r'\n**\1**', text)
    text = re.sub(r'(Điểm [a-z]+\))', r'\n**\1**', text)
    
    # Đánh dấu thông tin về hiệu lực
    effectiveness_patterns = [
        r'(có hiệu lực|hiệu lực)',
        r'(sửa đổi|bổ sung)',
        r'(thay thế|hết hiệu lực)',
        r'(ngày.*ban hành)',
        r'(ngày.*có hiệu lực)'
    ]
    
    for pattern in effectiveness_patterns:
        text = re.sub(pattern, r'⚠️ **\1**', text, flags=re.IGNORECASE)
    
    return text.strip()

def create_assistant(client, name: str) -> str:
    """Create OpenAI Assistant with optimized parameters"""
    
    assistant = client.beta.assistants.create(
        name=name,
        instructions=SYSTEM_PROMPT,
        model="gpt-4-turbo-preview",  # Model mới nhất với context window lớn
        tools=[{"type": "file_search"}],
        temperature=OPTIMIZED_PARAMS["temperature"],
        top_p=OPTIMIZED_PARAMS["top_p"],
        tool_resources={
            "file_search": {
                "max_num_results": 20,  # Tăng số kết quả tìm kiếm
            }
        }
    )
    
    return assistant.id

def upload_file_to_assistant(client, assistant_id: str, file_content: str, filename: str) -> str:
    """Upload file content to assistant"""
    
    # Tối ưu hóa nội dung trước khi upload
    optimized_content = preprocess_legal_text(file_content)
    
    # Tạo file tạm thời
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
        tmp_file.write(optimized_content)
        tmp_file_path = tmp_file.name
    
    try:
        # Upload file
        with open(tmp_file_path, 'rb') as f:
            file_obj = client.files.create(file=f, purpose='assistants')
        
        # Attach file to assistant
        client.beta.assistants.update(
            assistant_id=assistant_id,
            tool_resources={
                "file_search": {
                    "vector_store_ids": [],
                    "max_num_results": 20
                }
            },
            file_ids=[file_obj.id]
        )
        
        return file_obj.id
        
    finally:
        # Dọn dẹp file tạm
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

def get_assistant_response(client, assistant_id: str, question: str, thread_id: str = None) -> Dict[str, Any]:
    """Get response from assistant"""
    
    # Create thread if not exists
    if not thread_id:
        thread = client.beta.threads.create()
        thread_id = thread.id
    
    # Add message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=question
    )
    
    # Run assistant
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        temperature=OPTIMIZED_PARAMS["temperature"],
        max_tokens=OPTIMIZED_PARAMS["max_tokens"]
    )
    
    # Wait for completion
    while run.status in ['queued', 'in_progress']:
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
    
    if run.status == 'completed':
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = messages.data[0].content[0].text.value
        return {
            "success": True,
            "response": response,
            "thread_id": thread_id
        }
    else:
        return {
            "success": False,
            "error": f"Run failed with status: {run.status}",
            "thread_id": thread_id
        }

# ===============================
# STREAMLIT UI
# ===============================

def main():
    # Header
    st.title("⚖️ AI Agent Pháp Chế Khoáng Sản")
    st.markdown("*Hệ thống AI hỗ trợ tra cứu và tư vấn pháp luật khoáng sản với độ chính xác cao*")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("🔧 Cấu Hình Hệ Thống")
        
        # Display optimized parameters
        with st.expander("📊 Tham Số Tối Ưu"):
            st.json(OPTIMIZED_PARAMS)
        
        st.header("📁 Quản Lý Tài Liệu")
        
        # File upload
        uploaded_files = st.file_uploader(
            "Upload văn bản pháp luật (PDF, DOCX, TXT)",
            type=['pdf', 'docx', 'txt'],
            accept_multiple_files=True,
            help="Hỗ trợ nhiều định dạng file văn bản pháp luật"
        )
        
        # Assistant management
        assistant_name = st.text_input(
            "Tên Assistant", 
            value=f"AI-PapChế-KhoángSản-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        if st.button("🚀 Tạo Assistant Mới", type="primary"):
            if uploaded_files:
                create_new_assistant(uploaded_files, assistant_name)
            else:
                st.warning("Vui lòng upload ít nhất một file văn bản pháp luật")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 Tư Vấn Pháp Luật")
        
        # Chat interface
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Đặt câu hỏi về pháp luật khoáng sản..."):
            if "assistant_id" not in st.session_state:
                st.warning("⚠️ Vui lòng tạo Assistant trước khi đặt câu hỏi")
            else:
                handle_chat_message(prompt)
    
    with col2:
        st.header("ℹ️ Hướng Dẫn Sử Dụng")
        
        with st.expander("🎯 Mục Đích Sử Dụng"):
            st.markdown("""
            - Tra cứu quy định pháp luật về khoáng sản
            - Tư vấn thủ tục hành chính
            - Kiểm tra tính hiệu lực của văn bản
            - Giải thích các điều khoản phức tạp
            """)
        
        with st.expander("⚡ Tính Năng Đặc Biệt"):
            st.markdown("""
            - **Phát hiện thay đổi pháp luật**: Cảnh báo khi quy định đã sửa đổi
            - **Độ chính xác cao**: Temperature = 0.1 đảm bảo câu trả lời chính xác
            - **Chunk tối ưu**: 1000 tokens với overlap 200 để không bỏ sót thông tin
            - **Kiểm tra mâu thuẫn**: Phát hiện các quy định có thể xung đột
            """)
        
        with st.expander("🔍 Mẹo Tối Ưu File"):
            st.markdown("""
            **Chuẩn bị file tốt nhất:**
            - Định dạng PDF hoặc DOCX chất lượng cao
            - Văn bản đã được OCR tốt (nếu scan)
            - Loại bỏ header/footer không cần thiết
            - Đảm bảo cấu trúc Điều-Khoản-Điểm rõ ràng
            
            **Hệ thống sẽ tự động:**
            - Chuẩn hóa định dạng văn bản
            - Đánh dấu các phần quan trọng
            - Tối ưu cho AI hiểu tốt hơn
            """)

def create_new_assistant(uploaded_files, assistant_name):
    """Create new assistant with uploaded files"""
    
    with st.spinner("🔄 Đang tạo Assistant và xử lý tài liệu..."):
        try:
            client = init_openai_client()
            
            # Create assistant
            assistant_id = create_assistant(client, assistant_name)
            st.session_state.assistant_id = assistant_id
            
            # Process and upload files
            file_ids = []
            for uploaded_file in uploaded_files:
                # Extract text based on file type
                if uploaded_file.type == "application/pdf":
                    text = extract_text_from_pdf(uploaded_file)
                elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    text = extract_text_from_docx(uploaded_file)
                else:  # txt
                    text = str(uploaded_file.read(), "utf-8")
                
                if text:
                    file_id = upload_file_to_assistant(client, assistant_id, text, uploaded_file.name)
                    file_ids.append(file_id)
            
            st.session_state.client = client
            st.session_state.thread_id = None
            st.session_state.file_ids = file_ids
            
            st.success(f"✅ Đã tạo thành công Assistant: {assistant_name}")
            st.success(f"📄 Đã upload {len(file_ids)} tài liệu")
            st.info(f"🆔 Assistant ID: `{assistant_id}`")
            
        except Exception as e:
            st.error(f"❌ Lỗi tạo Assistant: {str(e)}")

def handle_chat_message(prompt):
    """Handle chat message and get AI response"""
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("🤔 Đang phân tích và tra cứu pháp luật..."):
            try:
                result = get_assistant_response(
                    st.session_state.client,
                    st.session_state.assistant_id,
                    prompt,
                    st.session_state.get("thread_id")
                )
                
                if result["success"]:
                    response = result["response"]
                    st.session_state.thread_id = result["thread_id"]
                    
                    # Display response with enhanced formatting
                    st.markdown(response)
                    
                    # Add to chat history
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                else:
                    error_msg = f"❌ Lỗi: {result['error']}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
            except Exception as e:
                error_msg = f"❌ Lỗi hệ thống: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

if __name__ == "__main__":
    main()