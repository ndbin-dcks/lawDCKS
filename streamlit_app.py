import streamlit as st
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import sqlite3
import uuid

# Import với error handling
try:
    import openai
except ImportError:
    st.error("Lỗi: Không thể import OpenAI. Vui lòng kiểm tra requirements.txt")
    st.stop()

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

/* Typing Indicator */
.typing-indicator {
    display: flex;
    justify-content: flex-end;
    margin: 10px 0;
}

.typing-dots {
    background: #f0f0f0;
    padding: 15px 20px;
    border-radius: 20px 20px 5px 20px;
    max-width: 70px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.typing-dots span {
    height: 8px;
    width: 8px;
    background: #999;
    border-radius: 50%;
    display: inline-block;
    margin: 0 2px;
    animation: typing 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
    0%, 80%, 100% { 
        transform: scale(0.8);
        opacity: 0.5;
    }
    40% { 
        transform: scale(1);
        opacity: 1;
    }
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
    padding: 5px 10px;
    border-radius: 15px;
    font-size: 12px;
    font-weight: bold;
    text-align: center;
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

# Optimized parameters
OPTIMIZED_PARAMS = {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "temperature": 0.1,
    "max_tokens": 4000,
    "top_p": 0.95,
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
        assistant_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        title TEXT,
        thread_id TEXT
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

def create_chat_session(assistant_id=None):
    """Create new chat session"""
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO chat_sessions (session_id, assistant_id, title)
    VALUES (?, ?, ?)
    ''', (session_id, assistant_id, f"Chat {datetime.now().strftime('%H:%M %d/%m')}"))
    
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
    SELECT session_id, title, created_at, last_activity, assistant_id,
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
            "assistant_id": row[4],
            "message_count": row[5]
        })
    
    conn.close()
    return sessions

def update_session_thread_id(session_id, thread_id):
    """Update thread ID for session"""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE chat_sessions 
    SET thread_id = ? 
    WHERE session_id = ?
    ''', (thread_id, session_id))
    
    conn.commit()
    conn.close()

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
            <h3>💬 Chào mừng đến với AI Agent Pháp Chế Khoáng Sản!</h3>
            <p>Đặt câu hỏi bên dưới để bắt đầu cuộc trò chuyện với chuyên gia AI</p>
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
            {f'<div class="chat-info">⚖️ AI Agent • {time_str}</div>' if time_str else '<div class="chat-info">⚖️ AI Agent</div>'}
            '''
    
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

def show_typing_indicator():
    """Show typing indicator"""
    typing_html = '''
    <div class="typing-indicator">
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    </div>
    '''
    return st.markdown(typing_html, unsafe_allow_html=True)

# ===============================
# HELPER FUNCTIONS
# ===============================

@st.cache_resource  # ✅ FIXED: Use cache_resource for objects/connections
def init_openai_client():
    """Initialize OpenAI client with error handling"""
    try:
        # Thử lấy API key từ nhiều nguồn
        api_key = None
        
        # 1. Từ Streamlit secrets
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        
        # 2. Từ environment variables
        elif "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"]
        
        if not api_key:
            st.error("⚠️ Chưa cấu hình OPENAI_API_KEY")
            st.info("Vui lòng thêm API key vào Streamlit Advanced Settings")
            st.stop()
            
        # Validate API key format
        if not api_key.startswith('sk-'):
            st.error("⚠️ API key không đúng định dạng. Phải bắt đầu bằng 'sk-'")
            st.stop()
        
        # Try different initialization methods to handle version conflicts
        try:
            # Method 1: Standard initialization (latest version)
            client = openai.OpenAI(api_key=api_key)
        except TypeError as e:
            if "proxies" in str(e):
                # Method 2: Handle proxies parameter issue
                try:
                    import openai as openai_module
                    client = openai_module.OpenAI(
                        api_key=api_key,
                        timeout=30.0
                    )
                except Exception:
                    # Method 3: Fallback for older versions
                    openai.api_key = api_key
                    # Create a simple wrapper for compatibility
                    class OpenAIWrapper:
                        def __init__(self):
                            pass
                        @property
                        def beta(self):
                            return openai
                    client = OpenAIWrapper()
            else:
                raise e
        
        # Test connection
        try:
            if hasattr(client, 'models'):
                client.models.list()
            else:
                # Fallback test for older versions
                openai.Model.list()
            return client
        except Exception as e:
            st.error(f"⚠️ Không thể kết nối đến OpenAI: {str(e)}")
            st.info("💡 Kiểm tra API key và internet connection")
            st.stop()
            
    except Exception as e:
        st.error(f"⚠️ Lỗi khởi tạo OpenAI client: {str(e)}")
        st.stop()

def get_assistant_id_from_config():
    """Get Assistant ID from config sources"""
    # 1. Từ Streamlit secrets
    if hasattr(st, 'secrets') and "ASSISTANT_ID" in st.secrets:
        return st.secrets["ASSISTANT_ID"]
    
    # 2. Từ environment variables  
    elif "ASSISTANT_ID" in os.environ:
        return os.environ["ASSISTANT_ID"]
    
    return None

def auto_connect_assistant():
    """Tự động kết nối Assistant nếu có config sẵn"""
    assistant_id = get_assistant_id_from_config()
    
    if assistant_id and not st.session_state.assistant_id:
        try:
            # Verify assistant exists
            if hasattr(st.session_state.client, 'beta'):
                assistant = st.session_state.client.beta.assistants.retrieve(assistant_id)
            else:
                # Fallback for older versions
                assistant = openai.beta.assistants.retrieve(assistant_id)
            
            # Store in session state
            st.session_state.assistant_id = assistant_id
            st.session_state.assistant_info = {
                "name": assistant.name,
                "id": assistant_id,
                "created_at": assistant.created_at,
                "model": assistant.model,
                "auto_connected": True
            }
            
            return True
            
        except Exception as e:
            st.error(f"❌ Lỗi tự động kết nối Assistant {assistant_id}: {str(e)}")
            return False
    
    return False

def connect_existing_assistant(assistant_id):
    """Connect to existing assistant"""
    with st.spinner("🔄 Đang kết nối với Assistant..."):
        try:
            # Verify assistant exists and get info
            if hasattr(st.session_state.client, 'beta'):
                assistant = st.session_state.client.beta.assistants.retrieve(assistant_id)
            else:
                # Fallback for older versions
                assistant = openai.beta.assistants.retrieve(assistant_id)
            
            # Store in session state
            st.session_state.assistant_id = assistant_id
            st.session_state.assistant_info = {
                "name": assistant.name,
                "id": assistant_id,
                "created_at": assistant.created_at,
                "model": assistant.model,
                "auto_connected": False
            }
            
            st.success(f"✅ Kết nối thành công với Assistant: {assistant.name}")
            st.info(f"🆔 ID: `{assistant_id}`")
            st.info(f"🤖 Model: {assistant.model}")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Lỗi kết nối Assistant: {str(e)}")
            st.error("Kiểm tra lại Assistant ID hoặc quyền truy cập API")

def get_response_safe(client, assistant_id: str, question: str, thread_id: str = None) -> Dict[str, Any]:
    """Get assistant response with comprehensive error handling"""
    try:
        # Handle different client types
        if hasattr(client, 'beta'):
            beta_client = client.beta
        else:
            beta_client = openai.beta
        
        # Create or use existing thread
        if not thread_id:
            thread = beta_client.threads.create()
            thread_id = thread.id
        
        # Add message
        beta_client.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=question
        )
        
        # Create run with timeout handling
        run = beta_client.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            temperature=OPTIMIZED_PARAMS["temperature"],
            max_tokens=OPTIMIZED_PARAMS["max_tokens"]
        )
        
        # Wait for completion with timeout
        max_wait = 60  # seconds
        wait_time = 0
        
        while run.status in ['queued', 'in_progress'] and wait_time < max_wait:
            time.sleep(2)
            wait_time += 2
            run = beta_client.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        
        if wait_time >= max_wait:
            return {
                "success": False,
                "error": "Timeout: Quá thời gian chờ phản hồi",
                "thread_id": thread_id
            }
        
        if run.status == 'completed':
            messages = beta_client.threads.messages.list(thread_id=thread_id)
            response = messages.data[0].content[0].text.value
            return {
                "success": True,
                "response": response,
                "thread_id": thread_id
            }
        else:
            return {
                "success": False,
                "error": f"Lỗi xử lý: {run.status}",
                "thread_id": thread_id
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi hệ thống: {str(e)}",
            "thread_id": thread_id
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
    if "assistant_id" not in st.session_state:
        st.session_state.assistant_id = None
    if "client" not in st.session_state:
        st.session_state.client = None
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None

    # Header
    st.title("⚖️ AI Agent Pháp Chế Khoáng Sản")
    st.markdown("*Hệ thống AI hỗ trợ tra cứu và tư vấn pháp luật khoáng sản với độ chính xác cao*")
    
    # Feature highlight
    st.markdown("""
    <div class="feature-highlight">
        <h4>🎯 Tính Năng Chính</h4>
        <p>• 👤 <strong>User bên trái</strong>, ⚖️ <strong>AI bên phải</strong> - Giao diện chat trực quan</p>
        <p>• 💾 <strong>Lưu chat history</strong> tự động với SQLite database</p>
        <p>• 🚀 <strong>Auto-connect Assistant</strong> từ Advanced Settings</p>
        <p>• 📋 <strong>Phân tích pháp luật chính xác</strong> với system prompt tối ưu</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-initialize client and assistant
    if not st.session_state.client:
        st.session_state.client = init_openai_client()
    
    # Auto-connect assistant if configured
    if st.session_state.client and not st.session_state.assistant_id:
        if auto_connect_assistant():
            st.success("🚀 Đã tự động kết nối Assistant từ cấu hình!")
            
    # Main layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Main chat area
        if st.session_state.assistant_id:
            # Chat header
            st.header("💬 Tư Vấn Pháp Luật")
            
            # Create session if not exists
            if not st.session_state.current_session_id:
                session_id = create_chat_session(st.session_state.assistant_id)
                st.session_state.current_session_id = session_id
            
            # Load messages if empty but session exists
            if not st.session_state.messages and st.session_state.current_session_id:
                loaded_messages = load_chat_history(st.session_state.current_session_id)
                st.session_state.messages = loaded_messages
            
            # Display chat with custom styling
            display_custom_chat(st.session_state.messages)
            
            # Chat input
            if prompt := st.chat_input("Đặt câu hỏi về pháp luật khoáng sản..."):
                handle_chat_with_db(prompt)
        
        else:
            # No assistant connected
            st.header("💬 Tư Vấn Pháp Luật")
            st.info("👉 Vui lòng kết nối Assistant trong panel bên phải để bắt đầu chat")
            
            # Quick start guide
            with st.expander("🚀 Hướng Dẫn Nhanh - Chỉ 2 Bước"):
                st.markdown("""
                **Bước 1: Cấu hình Assistant ID**
                - Vào **Streamlit Advanced Settings**
                - Thêm: `ASSISTANT_ID = "asst_your_id_here"`
                - App sẽ tự động kết nối!
                
                **Bước 2: Chat ngay**
                - Không cần upload files
                - Không cần tạo Assistant mới
                - Chỉ cần chat và nhận tư vấn!
                
                **🎨 Giao diện đặc biệt:**
                - 👤 **Bạn**: Tin nhắn bên trái (xanh gradient)
                - ⚖️ **AI**: Tin nhắn bên phải (hồng gradient)
                - 💾 **History**: Tự động lưu mọi cuộc chat
                """)
            
            # Example questions
            st.subheader("🤔 Câu Hỏi Mẫu")
            example_questions = [
                "Quy trình cấp phép thăm dò khoáng sản như thế nào?",
                "Thuế tài nguyên khoáng sản được tính như thế nào?",
                "Điều kiện để được cấp giấy phép khai thác khoáng sản?",
                "Xử phạt vi phạm trong lĩnh vực khoáng sản có mức nào?",
                "Quyền và nghĩa vụ của tổ chức khai thác khoáng sản?"
            ]
            
            for i, question in enumerate(example_questions):
                if st.button(f"❓ {question}", key=f"example_{i}"):
                    st.info("Vui lòng kết nối Assistant trước để đặt câu hỏi này")
    
    with col2:
        # Control panel
        st.header("🔧 Quản Lý")
        
        # Connection status display
        st.subheader("📊 Trạng Thái")
        status_col1, status_col2 = st.columns(2)
        with status_col1:
            if st.session_state.client:
                st.markdown('<div class="status-indicator status-success">🔌 OpenAI ✅</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-indicator status-error">🔌 OpenAI ❌</div>', unsafe_allow_html=True)
                
        with status_col2:
            if st.session_state.assistant_id:
                st.markdown('<div class="status-indicator status-success">🤖 Assistant ✅</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-indicator status-warning">🤖 Assistant ⏳</div>', unsafe_allow_html=True)
        
        # Manual connection button
        if st.button("🔄 Refresh"):
            st.session_state.client = init_openai_client()
            auto_connect_assistant()
            st.rerun()
        
        # Config info
        with st.expander("⚙️ Cấu Hình"):
            has_api_key = bool(
                (hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets) or
                "OPENAI_API_KEY" in os.environ
            )
            has_assistant_id = bool(get_assistant_id_from_config())
            
            st.write("**OPENAI_API_KEY:**", "✅" if has_api_key else "❌")
            st.write("**ASSISTANT_ID:**", "✅" if has_assistant_id else "❌")
            
            if has_assistant_id:
                st.code(get_assistant_id_from_config())
        
        st.divider()
        
        # Chat Session Management
        st.subheader("💬 Chat Sessions")
        
        # Current session info
        if st.session_state.current_session_id:
            st.success(f"🎯 Session hiện tại")
            if st.button("🆕 Chat Mới"):
                # Save current session if has messages
                if st.session_state.messages:
                    for msg in st.session_state.messages:
                        save_message(st.session_state.current_session_id, msg["role"], msg["content"])
                
                # Create new session
                new_session_id = create_chat_session(st.session_state.assistant_id)
                st.session_state.current_session_id = new_session_id
                st.session_state.messages = []
                st.session_state.thread_id = None
                st.success("Đã tạo chat mới!")
                st.rerun()
        
        # Chat history
        with st.expander("📚 Lịch Sử", expanded=True):
            sessions = get_chat_sessions()
            
            if sessions:
                for session in sessions[:5]:  # Show last 5 sessions
                    session_title = session["title"]
                    message_count = session["message_count"]
                    
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
        
        # Assistant Management
        st.subheader("🤖 Assistant")
        
        # Show current assistant status
        if st.session_state.assistant_id:
            assistant_info = st.session_state.get("assistant_info", {})
            st.success(f"✅ {assistant_info.get('name', 'Unknown')}")
            
            if assistant_info.get('auto_connected'):
                st.info("🚀 Auto-connected")
            
            if st.button("❌ Disconnect"):
                st.session_state.assistant_id = None
                st.session_state.assistant_info = {}
                st.session_state.messages = []
                st.session_state.thread_id = None
                st.session_state.current_session_id = None
                st.success("Đã ngắt kết nối")
                st.rerun()
        
        else:
            # Manual connection options
            auto_assistant_id = get_assistant_id_from_config()
            
            if auto_assistant_id:
                st.info(f"🔧 ID: `{auto_assistant_id[:12]}...`")
                st.info("Sẽ auto-connect khi refresh")
            else:
                # Manual Assistant ID Input
                st.write("🎯 **Manual Connect**")
                manual_assistant_id = st.text_input(
                    "Assistant ID",
                    placeholder="asst_xxxxxxxxxx"
                )
                
                if st.button("🔗 Connect", type="primary"):
                    if not manual_assistant_id:
                        st.warning("Nhập Assistant ID")
                    elif not manual_assistant_id.startswith('asst_'):
                        st.error("ID phải bắt đầu 'asst_'")
                    else:
                        connect_existing_assistant(manual_assistant_id)
        
        # Parameters display
        with st.expander("📊 Tham Số"):
            st.json(OPTIMIZED_PARAMS)

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

def handle_chat_with_db(prompt):
    """Handle chat with database integration"""
    # Add user message to session and DB
    user_message = {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()}
    st.session_state.messages.append(user_message)
    save_message(st.session_state.current_session_id, "user", prompt)
    
    # Display user message immediately
    display_custom_chat(st.session_state.messages)
    
    # Show typing indicator
    typing_placeholder = st.empty()
    with typing_placeholder:
        show_typing_indicator()
    
    # Get AI response
    try:
        result = get_response_safe(
            st.session_state.client,
            st.session_state.assistant_id,
            prompt,
            st.session_state.thread_id
        )
        
        # Clear typing indicator
        typing_placeholder.empty()
        
        if result["success"]:
            response = result["response"]
            st.session_state.thread_id = result["thread_id"]
            
            # Update session thread_id in DB
            if st.session_state.current_session_id:
                update_session_thread_id(st.session_state.current_session_id, result["thread_id"])
            
            # Add AI response to session and DB
            ai_message = {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
            st.session_state.messages.append(ai_message)
            save_message(st.session_state.current_session_id, "assistant", response)
            
            # Refresh display
            st.rerun()
            
        else:
            typing_placeholder.empty()
            error_msg = f"❌ {result['error']}"
            st.error(error_msg)
            
            # Save error message too
            error_message = {"role": "assistant", "content": error_msg, "timestamp": datetime.now().isoformat()}
            st.session_state.messages.append(error_message)
            save_message(st.session_state.current_session_id, "assistant", error_msg)
            
    except Exception as e:
        typing_placeholder.empty()
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        st.error(error_msg)
        
        # Save error message
        error_message = {"role": "assistant", "content": error_msg, "timestamp": datetime.now().isoformat()}
        st.session_state.messages.append(error_message)
        save_message(st.session_state.current_session_id, "assistant", error_msg)

if __name__ == "__main__":
    main()