import streamlit as st
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import sqlite3
import uuid
import warnings

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
    "max_tokens": 4000,
    "store": True,  # Enable state management
    "stream": False,  # Can be set to True for streaming
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
        api_type TEXT DEFAULT 'responses',
        response_id TEXT
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
# OPENAI RESPONSES API FUNCTIONS
# ===============================

@st.cache_resource
def init_openai_client():
    """Initialize OpenAI client for Responses API"""
    try:
        # Get API key
        api_key = None
        
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
        elif "OPENAI_API_KEY" in os.environ:
            api_key = os.environ["OPENAI_API_KEY"]
        
        if not api_key:
            st.error("⚠️ Chưa cấu hình OPENAI_API_KEY")
            st.info("💡 Vui lòng thêm API key vào Streamlit Advanced Settings")
            st.stop()
            
        # Validate API key format
        if not api_key.startswith('sk-'):
            st.error("⚠️ API key không đúng định dạng. Phải bắt đầu bằng 'sk-'")
            st.stop()
        
        # Initialize client
        client = openai.OpenAI(api_key=api_key)
        
        # Test connection với chat completions API (vì responses có thể chưa available)
        try:
            # Test với chat completions trước
            test_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return client
        except Exception as e:
            st.error(f"⚠️ Không thể kết nối đến OpenAI: {str(e)}")
            st.info("💡 Kiểm tra API key và internet connection")
            st.stop()
            
    except Exception as e:
        st.error(f"⚠️ Lỗi khởi tạo OpenAI client: {str(e)}")
        st.stop()

def get_file_search_tools():
    """Get file search tools configuration cho Responses API"""
    # Check if we have files configured
    file_ids = get_file_ids_from_config()
    
    tools = []
    
    # File search tool
    if file_ids:
        tools.append({
            "type": "file_search",
            "file_search": {
                "vector_store_ids": file_ids,
                "max_num_results": 20
            }
        })
    else:
        # Default file search
        tools.append({"type": "file_search"})
    
    # Web search tool (nếu có)
    # tools.append({"type": "web_search"})
    
    return tools

def get_file_ids_from_config():
    """Get file IDs from config sources"""
    # You can configure file IDs in Advanced Settings
    if hasattr(st, 'secrets') and "FILE_IDS" in st.secrets:
        return st.secrets["FILE_IDS"].split(",")
    elif "FILE_IDS" in os.environ:
        return os.environ["FILE_IDS"].split(",")
    
    return []

def prepare_input_messages(question: str, conversation_history: List[Dict]) -> List[Dict]:
    """Chuẩn bị input messages cho Responses API"""
    input_messages = []
    
    # Add system message vào đầu
    input_messages.append({
        "role": "system", 
        "content": SYSTEM_PROMPT
    })
    
    # Add conversation history
    for msg in conversation_history:
        input_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current question
    input_messages.append({
        "role": "user",
        "content": question
    })
    
    return input_messages

def get_response_with_responses_api(client, question: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Get response using new Responses API"""
    try:
        # Prepare input - Response API sử dụng format khác
        input_messages = prepare_input_messages(question, conversation_history)
        
        # Get tools
        tools = get_file_search_tools()
        
        # Gọi Responses API với cú pháp mới
        try:
            # Thử với Responses API trước
            response = client.responses.create(
                model=OPTIMIZED_PARAMS["model"],
                input=input_messages,  # Responses API dùng 'input' thay vì 'messages'
                tools=tools,
                temperature=OPTIMIZED_PARAMS["temperature"],
                max_tokens=OPTIMIZED_PARAMS["max_tokens"],
                store=OPTIMIZED_PARAMS["store"],
                stream=OPTIMIZED_PARAMS["stream"]
            )
            
            # Extract response text từ Responses API
            if hasattr(response, 'output_text'):
                response_text = response.output_text
            elif hasattr(response, 'output') and response.output:
                # Có thể response.output là array của các message objects
                if isinstance(response.output, list) and len(response.output) > 0:
                    last_output = response.output[-1]
                    if hasattr(last_output, 'content'):
                        if isinstance(last_output.content, list):
                            response_text = last_output.content[0].text if last_output.content else "No response"
                        else:
                            response_text = last_output.content
                    else:
                        response_text = str(last_output)
                else:
                    response_text = str(response.output)
            else:
                response_text = str(response)
            
            return {
                "success": True,
                "response": response_text,
                "response_id": getattr(response, 'id', None),
                "api_used": "responses"
            }
            
        except Exception as responses_error:
            # Fallback về Chat Completions API nếu Responses API chưa available
            st.warning(f"⚠️ Responses API chưa khả dụng: {str(responses_error)}")
            st.info("🔄 Đang fallback về Chat Completions API...")
            
            # Convert input messages về format cho Chat Completions
            chat_messages = input_messages
            
            response = client.chat.completions.create(
                model=OPTIMIZED_PARAMS["model"],
                messages=chat_messages,
                temperature=OPTIMIZED_PARAMS["temperature"],
                max_tokens=OPTIMIZED_PARAMS["max_tokens"],
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )
            
            response_text = response.choices[0].message.content
            
            return {
                "success": True,
                "response": response_text,
                "response_id": getattr(response, 'id', None),
                "api_used": "chat_completions"
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi API: {str(e)}",
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
    st.markdown("*Sử dụng **OpenAI Responses API mới nhất (2025)** với fallback sang Chat Completions*")
    
    # API Status badge
    st.markdown("""
    <div class="new-api-badge">
        🚀 NEW: OpenAI Responses API (March 2025) - Faster & More Flexible!
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-initialize client
    if not st.session_state.client:
        st.session_state.client = init_openai_client()
            
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
        
        # Chat input
        if prompt := st.chat_input("Đặt câu hỏi về pháp luật khoáng sản..."):
            handle_chat_with_responses_api(prompt)
    
    with col2:
        # Control panel
        st.header("🔧 Quản Lý")
        
        # API Status
        st.subheader("📊 API Status")
        if st.session_state.client:
            st.markdown('<div class="status-indicator status-success">🚀 OpenAI Client ✅</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-indicator status-error">🚀 OpenAI Client ❌</div>', unsafe_allow_html=True)
        
        # Config info
        with st.expander("⚙️ Cấu Hình"):
            has_api_key = bool(
                (hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets) or
                "OPENAI_API_KEY" in os.environ
            )
            has_files = bool(get_file_ids_from_config())
            
            st.write("**OPENAI_API_KEY:**", "✅" if has_api_key else "❌")
            st.write("**FILE_IDS:**", "✅" if has_files else "❌ (Optional)")
            
            if has_files:
                st.code(f"Files: {len(get_file_ids_from_config())} files")
            else:
                st.info("💡 Để sử dụng file search, thêm FILE_IDS vào Advanced Settings")
        
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
        
        # API Information
        st.subheader("📖 API Info")
        
        with st.expander("🚀 Responses API Features"):
            st.markdown("""
            **✅ Advantages:**
            - ⚡ Faster response times
            - 🔍 Better file search integration  
            - 💾 Stateful conversations
            - 🌐 Built-in web search (preview)
            - 🧹 Simplified syntax
            - 🤖 Computer use capabilities
            
            **📋 Current Configuration:**
            - Model: `gpt-4o` (latest)
            - Context: 128k tokens
            - Tools: file_search
            - Temperature: 0.1 (high accuracy)
            - Store: True (state management)
            """)
        
        with st.expander("🔧 Setup Guide"):
            st.markdown("""
            **Required:**
            - `OPENAI_API_KEY` in Advanced Settings
            
            **Optional:**
            - `FILE_IDS` for file search (comma-separated)
            
            **Example FILE_IDS:**
            ```
            file-abc123,file-def456,file-ghi789
            ```
            
            **Upload files via API:**
            ```python
            file = client.files.create(
                file=open("law.pdf", "rb"), 
                purpose='assistants'  # hoặc 'fine-tune'
            )
            print(file.id)  # Use this in FILE_IDS
            ```
            
            **Note:** App sẽ tự động fallback về Chat Completions nếu Responses API chưa available.
            """)
        
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

def handle_chat_with_responses_api(prompt):
    """Handle chat with new Responses API"""
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
            api_used = result.get("api_used", "unknown")
            
            # Show which API was used
            if api_used == "chat_completions":
                st.info("ℹ️ Sử dụng Chat Completions API (fallback)")
            elif api_used == "responses":
                st.success("✅ Sử dụng Responses API")
            
            # Add AI response to session and DB
            ai_message = {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
            st.session_state.messages.append(ai_message)
            save_message(st.session_state.current_session_id, "assistant", response, {"api_used": api_used})
            
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