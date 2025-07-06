import streamlit as st
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import sqlite3
import uuid
import warnings
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import với error handling
try:
    from openai import OpenAI
except ImportError:
    st.error("Lỗi: Không thể import OpenAI. Vui lòng kiểm tra requirements.txt")
    st.stop()

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ===============================
# CONFIGURATION & SETUP  
# ===============================

# Page config - SIMPLE
st.set_page_config(
    page_title="AI Agent Pháp Chế Khoáng Sản",
    page_icon="⚖️",
    layout="wide"
)

# ==> DEBUG CODE - ENHANCED <===
if st.sidebar.checkbox("🔍 Debug Mode"):
    st.sidebar.write("**Debug Information:**")
    if hasattr(st, 'secrets'):
        st.sidebar.write("Available secrets keys:", list(st.secrets.keys()))

    # Test API Key
    if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
        st.sidebar.write(f"✅ API key found: {api_key[:15]}...")
        st.sidebar.write(f"API key length: {len(api_key)}")
        
        # Test OpenAI client
        try:
            client = OpenAI(api_key=api_key)
            st.sidebar.write("✅ OpenAI client created successfully")
            
            # Test simple API call
            test_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            st.sidebar.write("✅ Basic API call successful!")
            
            # Test Responses API with file search
            if st.sidebar.button("🧪 Test Responses API"):
                try:
                    vector_store_ids = get_vector_store_ids()
                    
                    params = {
                        "model": "gpt-4o",
                        "input": [
                            {"role": "system", "content": "Bạn là AI chuyên về pháp luật khoáng sản Việt Nam."},
                            {"role": "user", "content": "Điều 2 Luật Khoáng sản 2010 quy định gì?"}
                        ],
                        "store": True
                    }
                    
                    if vector_store_ids:
                        params["tools"] = [{"type": "file_search", "vector_store_ids": vector_store_ids}]
                        st.sidebar.write(f"🔍 Using vector stores: {vector_store_ids}")
                    
                    response = client.responses.create(**params)
                    response_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
                    
                    st.sidebar.write("✅ Responses API test successful!")
                    st.sidebar.write(f"📄 Response preview: {response_text[:100]}...")
                    
                except Exception as e:
                    st.sidebar.write(f"❌ Responses API Error: {e}")
            
        except Exception as e:
            st.sidebar.write(f"❌ Error: {e}")
            
    else:
        st.sidebar.write("❌ OPENAI_API_KEY not found in secrets")
    
    # Test Vector Store IDs
    if hasattr(st, 'secrets') and "VECTOR_STORE_IDS" in st.secrets:
        vs_ids = st.secrets["VECTOR_STORE_IDS"]
        st.sidebar.write(f"✅ VECTOR_STORE_IDS found: {vs_ids}")
        
        # Parse vector store IDs
        if isinstance(vs_ids, str):
            parsed_ids = [id.strip() for id in vs_ids.split(",") if id.strip()]
            st.sidebar.write(f"📋 Parsed IDs: {parsed_ids}")
        else:
            st.sidebar.write(f"📋 Raw value: {vs_ids}")
            
    else:
        st.sidebar.write("❌ VECTOR_STORE_IDS not found in secrets")
        
    st.sidebar.write("---")
# ==> END DEBUG CODE <===

# Simple CSS - PROFESSIONAL STYLE
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Professional chat styling */
    .assistant {
        padding: 15px;
        border-radius: 8px;
        max-width: 75%;
        background: #f8f9fa;
        border-left: 4px solid #2c3e50;
        text-align: left;
        margin: 10px 0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
    }
    
    .user {
        padding: 15px;
        border-radius: 8px;
        max-width: 75%;
        background: #e8f4fd;
        border-left: 4px solid #3498db;
        text-align: right;
        margin-left: auto;
        margin: 10px 0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
    }
    
    .assistant::before { 
        content: "⚖️ AI Agent: "; 
        font-weight: bold; 
        color: #2c3e50;
    }
    
    .user::before { 
        content: "👤 Bạn: "; 
        font-weight: bold; 
        color: #3498db;
        float: left;
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        padding: 20px 0;
        border-bottom: 2px solid #ecf0f1;
        margin-bottom: 30px;
    }
    
    .main-title {
        color: #2c3e50;
        font-size: 28px;
        font-weight: 600;
        margin-bottom: 10px;
    }
    
    .main-subtitle {
        color: #7f8c8d;
        font-size: 16px;
        font-style: italic;
    }
    
    /* Status indicators */
    .status-box {
        padding: 10px 15px;
        border-radius: 6px;
        margin: 10px 0;
        font-size: 14px;
    }
    
    .status-success {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-error {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    
    .status-info {
        background: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
    }
</style>
""", unsafe_allow_html=True)

# ===============================
# CONTENT FUNCTIONS
# ===============================

def rfile(name_file):
    """Read content from text file"""
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return f"[File {name_file} not found]"
    except Exception as e:
        return f"[Error reading {name_file}: {e}]"

# ===============================
# SYSTEM CONFIGURATION
# ===============================

# System prompt for legal AI
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

TUYỆT ĐỐI KHÔNG ĐƯỢC:
- Đưa ra lời khuyên pháp lý mà không có căn cứ
- Diễn giải rộng hoặc suy đoán nội dung
- Bỏ qua việc cảnh báo về thay đổi pháp luật
- Trả lời khi không chắc chắn về thông tin
"""

# Welcome message
ASSISTANT_WELCOME = """Xin chào! Tôi là AI Agent chuyên tư vấn pháp luật khoáng sản Việt Nam.

Tôi có thể hỗ trợ bạn:
• Tra cứu điều khoản pháp luật khoáng sản
• Giải thích quy định về thăm dò, khai thác khoáng sản
• Hướng dẫn các thủ tục hành chính
• Phân tích văn bản pháp luật liên quan

Vui lòng đặt câu hỏi cụ thể để được hỗ trợ tốt nhất."""

# ===============================
# DATABASE FUNCTIONS (Simplified)
# ===============================

def init_database():
    """Initialize SQLite database for chat history"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def save_message(role, content):
    """Save message to database"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO chat_messages (role, content)
    VALUES (?, ?)
    ''', (role, content))
    
    conn.commit()
    conn.close()

# ===============================
# OPENAI CLIENT SETUP
# ===============================

def init_openai_client():
    """Initialize OpenAI client"""
    try:
        # Get API key
        api_key = None
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"].strip()
        elif "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"].strip()
        
        if not api_key:
            st.error("⚠️ Chưa cấu hình OPENAI_API_KEY")
            st.info("💡 Vui lòng thêm API key vào Streamlit Advanced Settings")
            st.stop()
        
        # Create client
        client = OpenAI(api_key=api_key)
        
        # Test connection
        try:
            client.models.list()
            logger.info("OpenAI client initialized successfully")
            return client
        except Exception as e:
            st.error(f"⚠️ Không thể kết nối đến OpenAI: {str(e)}")
            st.stop()
            
    except Exception as e:
        st.error(f"⚠️ Lỗi khởi tạo OpenAI client: {str(e)}")
        st.stop()

# ===============================
# VECTOR STORE CONFIGURATION
# ===============================

def get_vector_store_ids():
    """Get vector store IDs from configuration"""
    vector_store_ids = []
    
    # From Streamlit secrets
    if hasattr(st, 'secrets') and "VECTOR_STORE_IDS" in st.secrets:
        ids = st.secrets["VECTOR_STORE_IDS"]
        if isinstance(ids, str):
            vector_store_ids = [id.strip() for id in ids.split(",") if id.strip()]
        elif isinstance(ids, list):
            vector_store_ids = ids
    
    # From environment variables  
    elif "VECTOR_STORE_IDS" in os.environ:
        ids = os.environ["VECTOR_STORE_IDS"]
        vector_store_ids = [id.strip() for id in ids.split(",") if id.strip()]
    
    return vector_store_ids

def get_ai_response(client, question: str, conversation_history: List[Dict]) -> str:
    """Get AI response using Responses API - FIXED FORMAT"""
    try:
        # Prepare messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current question
        messages.append({"role": "user", "content": question})
        
        # Get vector store IDs
        vector_store_ids = get_vector_store_ids()
        
        # Prepare API parameters - EXACTLY LIKE WORKING SCRIPT
        params = {
            "model": "gpt-4o",
            "input": messages,
            "temperature": 0.1,
            "store": True
        }
        
        # Add file search if vector stores available - FIXED FORMAT
        if vector_store_ids:
            # EXACTLY like working script: [{"type": "file_search", "vector_store_ids": [VECTOR_STORE_ID]}]
            params["tools"] = [{"type": "file_search", "vector_store_ids": vector_store_ids}]
            logger.info(f"Using vector stores: {vector_store_ids}")
        else:
            logger.warning("No vector stores configured")
        
        # Log API call like working script
        logger.debug(f"Calling Responses API with params: {params}")
        
        # Make API call
        response = client.responses.create(**params)
        
        # Log response like working script  
        logger.debug(f"Response: {response.model_dump_json(indent=2) if hasattr(response, 'model_dump_json') else str(response)}")
        
        # Extract response text - EXACTLY like working script
        response_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
        
        logger.info("Responses API call successful")
        return response_text
        
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return f"❌ Lỗi khi gọi API: {str(e)}"

# ===============================
# MAIN APPLICATION
# ===============================

def main():
    # Initialize database
    init_database()
    
    # Initialize OpenAI client
    if "client" not in st.session_state:
        st.session_state.client = init_openai_client()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <div class="main-title">⚖️ AI Agent Pháp Chế Khoáng Sản</div>
        <div class="main-subtitle">Tư vấn pháp luật khoáng sản Việt Nam với độ chính xác cao</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Status indicators
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.markdown("**📊 Trạng thái hệ thống:**")
        
        # API Status
        if st.session_state.client:
            st.markdown('<div class="status-box status-success">✅ OpenAI API: Kết nối</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-box status-error">❌ OpenAI API: Lỗi</div>', unsafe_allow_html=True)
        
        # Vector Store Status
        vector_store_ids = get_vector_store_ids()
        if vector_store_ids:
            st.markdown(f'<div class="status-box status-success">✅ File Search: {len(vector_store_ids)} stores</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-box status-info">ℹ️ File Search: Chưa cấu hình</div>', unsafe_allow_html=True)
        
        # Configuration panel
        with st.expander("⚙️ Cấu hình"):
            st.write("**OPENAI_API_KEY:**")
            if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
                api_key = st.secrets["OPENAI_API_KEY"]
                st.success(f"✅ Configured: {api_key[:15]}...")
            else:
                st.error("❌ Not configured")
                
            st.write("**VECTOR_STORE_IDS:**")
            vector_store_ids = get_vector_store_ids()
            if vector_store_ids:
                st.success(f"✅ Configured: {len(vector_store_ids)} stores")
                for i, vs_id in enumerate(vector_store_ids):
                    st.code(f"{i+1}. {vs_id}")
            else:
                st.error("❌ Not configured")
                st.info("""
                **Cách cấu hình:**
                1. Click ⚙️ (Settings) → Advanced settings
                2. Thêm (KHÔNG dùng [secrets]):
                ```
                OPENAI_API_KEY = "sk-proj-your-api-key"
                VECTOR_STORE_IDS = "vs_68695626c77881918a6b72f1b9bdd4c9"
                ```
                3. Save → Restart app
                """)
            
            if st.button("🔄 Reset Chat"):
                st.session_state.messages = []
                st.rerun()
    
    with col1:
        st.markdown("**💬 Cuộc trò chuyện:**")
        
        # Initialize messages
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": ASSISTANT_WELCOME}
            ]
        
        # Display chat history
        for message in st.session_state.messages:
            if message["role"] == "assistant":
                st.markdown(f'<div class="assistant">{message["content"]}</div>', unsafe_allow_html=True)
            elif message["role"] == "user":
                st.markdown(f'<div class="user">{message["content"]}</div>', unsafe_allow_html=True)
        
        # Chat input
        if prompt := st.chat_input("Nhập câu hỏi về pháp luật khoáng sản..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.markdown(f'<div class="user">{prompt}</div>', unsafe_allow_html=True)
            save_message("user", prompt)
            
            # Show processing
            with st.spinner("🤔 Đang phân tích và tra cứu pháp luật..."):
                # Get conversation history (exclude system and current message)
                conversation_history = [msg for msg in st.session_state.messages[:-1] if msg["role"] != "system"]
                
                # Get AI response
                response = get_ai_response(st.session_state.client, prompt, conversation_history)
                
                # Display response
                st.markdown(f'<div class="assistant">{response}</div>', unsafe_allow_html=True)
                
                # Add to session and save
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_message("assistant", response)
                
                # Force refresh to show new message
                st.rerun()

if __name__ == "__main__":
    main()