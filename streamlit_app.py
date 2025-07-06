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

# Configure logging like working script
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import với error handling
try:
    import openai
except ImportError:
    st.error("Lỗi: Không thể import OpenAI. Vui lòng kiểm tra requirements.txt")
    st.stop()

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ===============================
# CONFIGURATION & SETUP  
# ===============================

# Page config
try:
    st.set_page_config(
        page_title="AI Agent Pháp Chế Khoáng Sản",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
except Exception as e:
    st.error(f"Lỗi cấu hình trang: {e}")

# Custom CSS cho giao diện chat đẹp
st.markdown("""
<style>
/* Hide Streamlit default elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Chat Container */
.chat-container {
    max-width: 100%;
    margin: 0 auto;
    padding: 20px 0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* User Message (Left) */
.user-message {
    display: flex;
    justify-content: flex-start;
    margin: 15px 0;
    animation: slideInLeft 0.3s ease-out;
}

.user-bubble {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 15px 20px;
    border-radius: 20px 20px 20px 5px;
    max-width: 70%;
    word-wrap: break-word;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    position: relative;
    line-height: 1.4;
}

.user-bubble::before {
    content: "👤";
    position: absolute;
    left: -35px;
    top: 5px;
    font-size: 24px;
}

/* AI Message (Right) */
.ai-message {
    display: flex;
    justify-content: flex-end;
    margin: 15px 0;
    animation: slideInRight 0.3s ease-out;
}

.ai-bubble {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 15px 20px;
    border-radius: 20px 20px 5px 20px;
    max-width: 70%;
    word-wrap: break-word;
    box-shadow: 0 4px 12px rgba(240, 147, 251, 0.3);
    position: relative;
    line-height: 1.4;
}

.ai-bubble::after {
    content: "⚖️";
    position: absolute;
    right: -35px;
    top: 5px;
    font-size: 24px;
}

/* Animations */
@keyframes slideInLeft {
    from {
        opacity: 0;
        transform: translateX(-50px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes slideInRight {
    from {
        opacity: 0;
        transform: translateX(50px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

/* Chat Info */
.chat-info {
    text-align: center;
    color: #666;
    font-size: 12px;
    margin: 5px 0;
}

/* New API Badge */
.new-api-badge {
    background: linear-gradient(45deg, #00c851, #007e33);
    color: white;
    padding: 8px 15px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: bold;
    margin: 15px 0;
    text-align: center;
    display: inline-block;
}

/* Welcome Message */
.welcome-message {
    text-align: center;
    padding: 40px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 20px;
    color: white;
    margin: 20px 0;
}

/* Button Styling */
.stButton > button {
    border-radius: 20px;
    border: none;
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white;
    transition: all 0.3s ease;
    font-weight: 500;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(102, 126, 234, 0.3);
}

/* Status indicators */
.status-indicator {
    padding: 8px 12px;
    border-radius: 15px;
    font-size: 12px;
    font-weight: bold;
    text-align: center;
    margin: 5px 0;
}

.status-success {
    background: #d4edda;
    color: #155724;
}

.status-warning {
    background: #fff3cd;
    color: #856404;
}

.status-error {
    background: #f8d7da;
    color: #721c24;
}

/* Feature highlight */
.feature-highlight {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 20px;
    border-radius: 15px;
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# Optimized parameters for Responses API  
OPTIMIZED_PARAMS = {
    "model": "gpt-4o",  # Latest model
    "temperature": 0.1,
    "store": True,  # Enable state management
}

# Enhanced system prompt
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

# ===============================
# DATABASE FUNCTIONS
# ===============================

def init_database():
    """Initialize SQLite database for chat history"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        title TEXT,
        api_type TEXT DEFAULT 'responses'
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT,
        FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id)
    )
    ''')
    
    # Create indexes for performance
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_session_last_activity 
    ON chat_sessions(last_activity)
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_messages_session_time 
    ON chat_messages(session_id, timestamp)
    ''')
    
    conn.commit()
    conn.close()

def create_chat_session():
    """Create new chat session"""
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO chat_sessions (session_id, title, api_type)
    VALUES (?, ?, ?)
    ''', (session_id, f"Chat {datetime.now().strftime('%H:%M %d/%m')}", "responses"))
    
    conn.commit()
    conn.close()
    
    return session_id

def save_message(session_id, role, content, metadata=None):
    """Save message to database"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO chat_messages (session_id, role, content, metadata)
    VALUES (?, ?, ?, ?)
    ''', (session_id, role, content, json.dumps(metadata) if metadata else None))
    
    # Update last activity
    cursor.execute('''
    UPDATE chat_sessions 
    SET last_activity = CURRENT_TIMESTAMP 
    WHERE session_id = ?
    ''', (session_id,))
    
    conn.commit()
    conn.close()

def load_chat_history(session_id):
    """Load chat history from database"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT role, content, timestamp, metadata
    FROM chat_messages 
    WHERE session_id = ?
    ORDER BY timestamp ASC
    ''', (session_id,))
    
    messages = []
    for row in cursor.fetchall():
        role, content, timestamp, metadata = row
        messages.append({
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": json.loads(metadata) if metadata else None
        })
    
    conn.close()
    return messages

def get_chat_sessions():
    """Get all chat sessions"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT session_id, title, created_at, last_activity, api_type,
           (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count
    FROM chat_sessions cs
    ORDER BY last_activity DESC
    ''')
    
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "session_id": row[0],
            "title": row[1],
            "created_at": row[2],
            "last_activity": row[3],
            "api_type": row[4],
            "message_count": row[5]
        })
    
    conn.close()
    return sessions

def delete_chat_session(session_id):
    """Delete chat session and all messages"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
    cursor.execute('DELETE FROM chat_sessions WHERE session_id = ?', (session_id,))
    
    conn.commit()
    conn.close()

# ===============================
# CUSTOM CHAT DISPLAY FUNCTIONS
# ===============================

def display_custom_chat(messages):
    """Display chat messages with custom styling"""
    if not messages:
        st.markdown("""
        <div class="welcome-message">
            <h3>💬 AI Agent Pháp Chế Khoáng Sản</h3>
            <p>Sử dụng <strong>OpenAI Responses API mới nhất (2025)</strong></p>
            <p>Đặt câu hỏi bên dưới để bắt đầu cuộc trò chuyện</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    chat_html = '<div class="chat-container">'
    
    for i, message in enumerate(messages):
        timestamp = message.get("timestamp", "")
        if timestamp:
            # Parse timestamp if it's a string
            if isinstance(timestamp, str):
                try:
                    if 'T' in timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = timestamp.split(' ')[1][:5] if ' ' in timestamp else ""
            else:
                time_str = ""
        else:
            time_str = ""
        
        # Escape HTML in content
        content = message["content"].replace('<', '&lt;').replace('>', '&gt;')
        # Convert markdown bold to HTML
        content = content.replace('**', '<strong>').replace('**', '</strong>')
        # Convert newlines to <br>
        content = content.replace('\n', '<br>')
        
        if message["role"] == "user":
            chat_html += f'''
            <div class="user-message">
                <div class="user-bubble">
                    {content}
                </div>
            </div>
            {f'<div class="chat-info">👤 Bạn • {time_str}</div>' if time_str else '<div class="chat-info">👤 Bạn</div>'}
            '''
        else:  # assistant
            chat_html += f'''
            <div class="ai-message">
                <div class="ai-bubble">
                    {content}
                </div>
            </div>
            {f'<div class="chat-info">⚖️ AI Agent (Responses API) • {time_str}</div>' if time_str else '<div class="chat-info">⚖️ AI Agent (Responses API)</div>'}
            '''
    
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

# ===============================
# OPENAI RESPONSES API FUNCTIONS (FIXED)
# ===============================

def test_api_key_standalone():
    """Test API key without caching"""
    try:
        # Get API key directly
        api_key = None
        source = ""
        
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"].strip()
            source = "Streamlit Secrets"
        elif "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"].strip()
            source = "Environment Variable"
        
        if not api_key:
            return {"success": False, "error": "No API key found", "source": "None"}
        
        # Test client creation
        client = openai.OpenAI(api_key=api_key)
        
        # Test API call
        models = client.models.list()
        
        return {
            "success": True, 
            "source": source,
            "api_key_format": f"{api_key[:15]}...{api_key[-10:]}",
            "api_key_length": len(api_key),
            "models_count": len(models.data)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "source": source}

@st.cache_resource
def init_openai_client():
    """Initialize OpenAI client for Responses API"""
    try:
        # Get API key - WITH BETTER DEBUGGING
        api_key = None
        source = ""
        
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
            source = "Streamlit Secrets"
        elif "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"]
            source = "Environment Variable"
        
        if not api_key:
            st.error("⚠️ Chưa cấu hình OPENAI_API_KEY")
            st.info("💡 Vui lòng thêm API key vào Streamlit Advanced Settings hoặc Environment Variables")
            st.stop()
        
        # CLEAN API KEY - Remove any whitespace/newlines
        api_key = api_key.strip()
        
        # Debug info (safely)
        logger.info(f"API Key source: {source}")
        logger.info(f"API Key format: {api_key[:15]}...{api_key[-10:]} (length: {len(api_key)})")
        
        # Validate API key format
        if not (api_key.startswith('sk-') or api_key.startswith('sk-proj-')):
            st.error(f"⚠️ API key không đúng định dạng. Phải bắt đầu bằng 'sk-' hoặc 'sk-proj-', nhưng tìm thấy: {api_key[:10]}...")
            st.stop()
        
        # Initialize client
        client = openai.OpenAI(api_key=api_key)
        
        # Test connection like working script
        try:
            models_response = client.models.list()
            logger.info("API key is valid")
            st.success(f"✅ API key valid (from {source})")
            return client
        except Exception as e:
            logger.error(f"API key error: {str(e)}")
            st.error(f"⚠️ Lỗi kết nối OpenAI: {str(e)}")
            st.error(f"🔍 Debug: Key source={source}, length={len(api_key)}, starts_with={api_key[:10]}...")
            st.info("💡 Kiểm tra API key và billing account")
            st.stop()
            
    except Exception as e:
        logger.error(f"OpenAI client initialization error: {str(e)}")
        st.error(f"⚠️ Lỗi khởi tạo OpenAI client: {str(e)}")
        st.stop()

def get_vector_store_ids():
    """Get vector store IDs from config sources - FIXED"""
    # Try different config sources
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
    
    # Legacy support for FILE_IDS
    elif hasattr(st, 'secrets') and "FILE_IDS" in st.secrets:
        st.warning("⚠️ FILE_IDS is deprecated. Please use VECTOR_STORE_IDS instead.")
        ids = st.secrets["FILE_IDS"] 
        vector_store_ids = [id.strip() for id in ids.split(",") if id.strip()]
    elif "FILE_IDS" in os.environ:
        st.warning("⚠️ FILE_IDS is deprecated. Please use VECTOR_STORE_IDS instead.")
        ids = os.environ["FILE_IDS"]
        vector_store_ids = [id.strip() for id in ids.split(",") if id.strip()]
    
    return vector_store_ids

def check_vector_store(client, vector_store_id: str) -> bool:
    """Check vector store status - LIKE WORKING SCRIPT"""
    try:
        store = client.vector_stores.retrieve(vector_store_id)
        st.success(f"✅ Vector Store: {vector_store_id[:20]}...")
        st.info(f"📊 Status: {store.status}")
        st.info(f"📁 Files: {store.file_counts.total}")
        
        if store.file_counts.total > 0:
            files = client.vector_stores.files.list(vector_store_id)
            st.write("**Files in Vector Store:**")
            for i, file in enumerate(files.data[:3]):  # Show first 3
                st.code(f"{i+1}. {file.id} (Status: {file.status})")
            if len(files.data) > 3:
                st.code(f"... and {len(files.data) - 3} more files")
        
        return store.status == "completed"
    except Exception as e:
        st.error(f"❌ Vector Store Error: {str(e)}")
        return False

def prepare_messages(question: str, conversation_history: List[Dict]) -> List[Dict]:
    """Prepare messages for Responses API"""
    messages = []
    
    # Add system message
    messages.append({
        "role": "system", 
        "content": SYSTEM_PROMPT
    })
    
    # Add conversation history
    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current question
    messages.append({
        "role": "user",
        "content": question
    })
    
    return messages

def get_response_with_responses_api(client, question: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Get response using new Responses API - FIXED"""
    try:
        # Prepare input messages
        messages = prepare_messages(question, conversation_history)
        
        # Get vector store IDs
        vector_store_ids = get_vector_store_ids()
        
        # Prepare parameters - SIMPLIFIED
        params = {
            "model": OPTIMIZED_PARAMS["model"],
            "input": messages,
            "temperature": OPTIMIZED_PARAMS["temperature"],
            "store": OPTIMIZED_PARAMS["store"]
        }
        
        # Add tools if vector stores available - FIXED FORMAT
        if vector_store_ids:
            params["tools"] = [{"type": "file_search", "vector_store_ids": vector_store_ids}]
            st.info(f"🔍 Using {len(vector_store_ids)} vector stores for file search")
            logger.info(f"Using vector stores: {vector_store_ids}")
        else:
            st.warning("⚠️ No vector stores configured. File search disabled.")
            logger.warning("No vector stores configured")
        
        # Log API call like working script
        logger.debug(f"Calling Responses API with params: {params}")
        
        # Make API call - SIMPLIFIED
        response = client.responses.create(**params)
        
        # Log response like working script  
        logger.debug(f"Response: {response.model_dump_json(indent=2) if hasattr(response, 'model_dump_json') else str(response)}")
        
        # Extract response text - SIMPLIFIED LIKE WORKING SCRIPT
        response_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
        
        logger.info("Responses API call successful")
        
        return {
            "success": True,
            "response": response_text,
            "response_id": getattr(response, 'id', None),
            "api_used": "responses",
            "has_file_search": bool(vector_store_ids)
        }
        
    except Exception as e:
        error_msg = f"Responses API Error: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "response_id": None,
            "api_used": "error"
        }

# ===============================
# MAIN APPLICATION
# ===============================

def main():
    # Initialize database
    init_database()
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "client" not in st.session_state:
        st.session_state.client = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None

    # Header
    st.title("⚖️ AI Agent Pháp Chế Khoáng Sản")
    st.markdown("*Sử dụng **OpenAI Responses API mới nhất (2025)** - Thay thế Assistants API*")
    
    # API Status badge
    st.markdown("""
    <div class="new-api-badge">
        🚀 NEW: OpenAI Responses API (March 2025) - Faster & More Flexible!
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-initialize client with better error handling
    if not st.session_state.client:
        with st.spinner("🔄 Initializing OpenAI client..."):
            try:
                st.session_state.client = init_openai_client()
            except Exception as e:
                st.error(f"❌ Failed to initialize client")
                st.error(f"**Error:** {e}")
                
                # Quick fix suggestions
                st.warning("""
                **🔧 Quick Fixes:**
                1. **Check API Key:** Go to Debug panel below → Test API Connection
                2. **Verify Format:** API key should start with `sk-` or `sk-proj-`
                3. **Check Billing:** Ensure OpenAI account has active billing
                4. **Try New Key:** Create new API key at https://platform.openai.com/api-keys
                """)
                
                # Still allow access to debug panel
                st.info("💡 You can still use the Debug panel below to test your API key")
                pass  # Don't stop, let user access debug panel
            
    # Main layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Main chat area
        st.header("💬 Tư Vấn Pháp Luật")
        
        # Create session if not exists
        if not st.session_state.current_session_id:
            session_id = create_chat_session()
            st.session_state.current_session_id = session_id
        
        # Load messages if empty but session exists
        if not st.session_state.messages and st.session_state.current_session_id:
            loaded_messages = load_chat_history(st.session_state.current_session_id)
            st.session_state.messages = loaded_messages
        
        # Display chat with custom styling
        display_custom_chat(st.session_state.messages)
        
        # Chat input - Only if client is available
        if st.session_state.client:
            if prompt := st.chat_input("Đặt câu hỏi về pháp luật khoáng sản..."):
                handle_chat_with_responses_api(prompt)
        else:
            st.chat_input("⚠️ Cần cấu hình API key trước khi chat (xem bên phải)", disabled=True)
    
    with col2:
        # Control panel
        st.header("🔧 Quản Lý")
        
        # API Status
        st.subheader("📊 API Status")
        if st.session_state.client:
            st.markdown('<div class="status-indicator status-success">🚀 Responses API ✅</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-indicator status-error">🚀 Responses API ❌</div>', unsafe_allow_html=True)
        
        # Config info - UPDATED
        with st.expander("⚙️ Cấu Hình"):
            has_api_key = bool(
                (hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets) or
                "OPENAI_API_KEY" in os.environ
            )
            vector_store_ids = get_vector_store_ids()
            has_vector_stores = bool(vector_store_ids)
            
            st.write("**OPENAI_API_KEY:**", "✅" if has_api_key else "❌")
            st.write("**VECTOR_STORE_IDS:**", "✅" if has_vector_stores else "❌ (Optional)")
            
            if has_vector_stores:
                st.code(f"Vector Stores: {len(vector_store_ids)} stores")
                for i, vs_id in enumerate(vector_store_ids[:3]):  # Show first 3
                    st.code(f"  {i+1}. {vs_id}")
                if len(vector_store_ids) > 3:
                    st.code(f"  ... and {len(vector_store_ids) - 3} more")
                
                # ADD: Check vector store status
                if st.button("🔍 Check Vector Stores"):
                    for vs_id in vector_store_ids:
                        with st.expander(f"Vector Store: {vs_id[:20]}..."):
                            check_vector_store(st.session_state.client, vs_id)
            else:
                st.info("💡 Để sử dụng file search, thêm VECTOR_STORE_IDS vào Advanced Settings")
        
        st.divider()
        
        # Chat Session Management
        st.subheader("💬 Chat Sessions")
        
        # Current session info
        if st.session_state.current_session_id:
            st.success(f"🎯 Session hiện tại")
            if st.button("🆕 Chat Mới"):
                # Save current session
                if st.session_state.messages:
                    for msg in st.session_state.messages:
                        save_message(st.session_state.current_session_id, msg["role"], msg["content"])
                
                # Create new session
                new_session_id = create_chat_session()
                st.session_state.current_session_id = new_session_id
                st.session_state.messages = []
                st.success("Đã tạo chat mới!")
                st.rerun()
        
        # Chat history
        with st.expander("📚 Lịch Sử", expanded=True):
            sessions = get_chat_sessions()
            
            if sessions:
                for session in sessions[:5]:  # Show last 5 sessions
                    session_title = session["title"]
                    message_count = session["message_count"]
                    api_type = session.get("api_type", "responses")
                    
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        if st.button(f"💬 {session_title} ({message_count})", key=f"load_{session['session_id']}"):
                            load_chat_session(session["session_id"])
                    with col_b:
                        if st.button("🗑️", key=f"del_{session['session_id']}"):
                            delete_chat_session(session["session_id"])
                            st.success("Đã xóa!")
                            st.rerun()
            else:
                st.info("Chưa có chat nào")
        
        st.divider()
        
        # API Information - UPDATED
        st.subheader("📖 API Info")
        
        with st.expander("🚀 Responses API Features"):
            st.markdown("""
            **✅ Advantages:**
            - ⚡ Faster response times
            - 🔍 Better file search integration  
            - 💾 Stateful conversations
            - 🌐 Built-in web search (preview)
            - 🧹 Simplified syntax
            
            **📋 Current Model:**
            - Model: `gpt-4o` (latest)
            - Context: 128k tokens
            - Tools: file_search via vector stores
            - Temperature: 0.1 (high accuracy)
            - Store: True (stateful)
            """)
        
        with st.expander("🔧 Setup Guide - UPDATED"):
            st.markdown("""
            **Required:**
            - `OPENAI_API_KEY` in Advanced Settings
            
            **Optional:**
            - `VECTOR_STORE_IDS` for file search (comma-separated)
            
            **Example VECTOR_STORE_IDS:**
            ```
            vs_68695626c77881918a6b72f1b9bdd4c9,vs_abc123def456
            ```
            
            **Create Vector Store:**
            1. Go to OpenAI Platform
            2. Upload your legal documents (.docx, .pdf, .txt)
            3. Create vector store and get ID (starts with 'vs_')
            4. Add vector store ID to VECTOR_STORE_IDS
            """)
        
        with st.expander("📊 Tham Số"):
            st.json(OPTIMIZED_PARAMS)
        
        # Debug info - ADDED
        with st.expander("🐞 Debug Info"):
            if st.button("📋 Show Current Config"):
                api_source = "None"
                if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
                    api_source = "Streamlit Secrets"
                elif "OPENAI_API_KEY" in os.environ:
                    api_source = "Environment Variable"
                
                st.code(f"""
API Key Source: {api_source}
API Key Configured: {bool((hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets) or 'OPENAI_API_KEY' in os.environ)}
Vector Store IDs: {get_vector_store_ids()}
Model: {OPTIMIZED_PARAMS['model']}
Temperature: {OPTIMIZED_PARAMS['temperature']}
Store: {OPTIMIZED_PARAMS['store']}
""")
            
            if st.button("🔄 Clear API Client Cache"):
                init_openai_client.clear()
                st.session_state.client = None
                st.success("✅ Cache cleared! Reload page to reinitialize.")
            
            if st.button("🔍 Test API Connection"):
                with st.spinner("Testing API connection..."):
                    result = test_api_key_standalone()
                    
                    if result["success"]:
                        st.success("✅ API Connection OK")
                        st.info(f"Source: {result['source']}")
                        st.info(f"API Key: {result['api_key_format']} (length: {result['api_key_length']})")
                        st.info(f"Available models: {result['models_count']} models")
                    else:
                        st.error(f"❌ API Connection Failed: {result['error']}")
                        st.info(f"Source: {result['source']}")
                        
                        if "invalid_api_key" in result['error']:
                            st.warning("""
                            💡 **API Key Issues:**
                            - Check if key is complete (no truncation)
                            - Verify billing account is active
                            - Try creating a new API key
                            - Make sure key has gpt-4o access
                            """)
                        
                if st.session_state.client:
                    try:
                        # Additional test for current client
                        models = st.session_state.client.models.list()
                        gpt4o_available = any(model.id == "gpt-4o" for model in models.data)
                        if gpt4o_available:
                            st.success("✅ Current client: gpt-4o model available")
                        else:
                            st.warning("⚠️ Current client: gpt-4o model not found")
                    except:
                        st.warning("⚠️ Current client has issues")
                else:
                    st.info("ℹ️ No active client (will auto-initialize on app start)")

def load_chat_session(session_id):
    """Load specific chat session"""
    # Save current session first
    if st.session_state.current_session_id and st.session_state.messages:
        for msg in st.session_state.messages:
            save_message(st.session_state.current_session_id, msg["role"], msg["content"])
    
    # Load new session
    st.session_state.current_session_id = session_id
    st.session_state.messages = load_chat_history(session_id)
    st.success(f"Đã tải chat!")
    st.rerun()

def handle_chat_with_responses_api(prompt):
    """Handle chat with new Responses API - UPDATED"""
    # Add user message to session and DB
    user_message = {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()}
    st.session_state.messages.append(user_message)
    save_message(st.session_state.current_session_id, "user", prompt)
    
    # Display user message immediately
    display_custom_chat(st.session_state.messages)
    
    # Show progress
    with st.spinner("🤔 AI đang phân tích với Responses API..."):
        # Get conversation history (exclude current message for API call)
        conversation_history = [msg for msg in st.session_state.messages[:-1]]
        
        # Get AI response using Responses API
        result = get_response_with_responses_api(
            st.session_state.client,
            prompt,
            conversation_history
        )
        
        if result["success"]:
            response = result["response"]
            
            # Add AI response to session and DB
            ai_message = {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
            st.session_state.messages.append(ai_message)
            save_message(st.session_state.current_session_id, "assistant", response)
            
            # Show success info
            api_info = f"✅ {result['api_used'].upper()}"
            if result.get('has_file_search'):
                api_info += " + File Search"
            st.success(api_info)
            
            # Refresh display
            st.rerun()
            
        else:
            error_msg = f"❌ {result['error']}"
            st.error(error_msg)
            
            # Save error message too
            error_message = {"role": "assistant", "content": error_msg, "timestamp": datetime.now().isoformat()}
            st.session_state.messages.append(error_message)
            save_message(st.session_state.current_session_id, "assistant", error_msg)

if __name__ == "__main__":
    main()