import streamlit as st
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
import warnings

# Import với error handling
try:
    import openai
except ImportError:
    st.error("❌ Lỗi: Không thể import OpenAI. Đang cài đặt...")
    st.code("pip install openai", language="bash")
    st.stop()

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

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

/* Session management */
.session-item {
    background: #f8f9fa;
    padding: 10px;
    border-radius: 8px;
    margin: 5px 0;
    border-left: 4px solid #667eea;
}
</style>
""", unsafe_allow_html=True)

# Optimized parameters for API calls
OPTIMIZED_PARAMS = {
    "model": "gpt-4o",
    "temperature": 0.1,
    "max_tokens": 4000,
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
# SESSION STATE MANAGEMENT
# ===============================

def init_session_state():
    """Initialize all session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = {}
    
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    
    if "client" not in st.session_state:
        st.session_state.client = None
    
    if "api_status" not in st.session_state:
        st.session_state.api_status = {"connected": False, "api_type": None}

def create_chat_session():
    """Create new chat session using session state"""
    session_id = str(uuid.uuid4())
    timestamp = datetime.now()
    
    # Create session data
    session_data = {
        "session_id": session_id,
        "title": f"Chat {timestamp.strftime('%H:%M %d/%m')}",
        "created_at": timestamp.isoformat(),
        "last_activity": timestamp.isoformat(),
        "messages": [],
        "api_type": "responses"
    }
    
    # Store in session state
    st.session_state.chat_sessions[session_id] = session_data
    
    return session_id

def save_message_to_session(session_id, role, content, metadata=None):
    """Save message to session state"""
    if session_id not in st.session_state.chat_sessions:
        return
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata
    }
    
    st.session_state.chat_sessions[session_id]["messages"].append(message)
    st.session_state.chat_sessions[session_id]["last_activity"] = datetime.now().isoformat()

def get_chat_sessions():
    """Get all chat sessions from session state"""
    sessions = []
    for session_id, session_data in st.session_state.chat_sessions.items():
        sessions.append({
            "session_id": session_id,
            "title": session_data["title"],
            "created_at": session_data["created_at"],
            "last_activity": session_data["last_activity"],
            "message_count": len(session_data["messages"]),
            "api_type": session_data.get("api_type", "responses")
        })
    
    # Sort by last activity
    sessions.sort(key=lambda x: x["last_activity"], reverse=True)
    return sessions

def load_chat_session(session_id):
    """Load specific chat session"""
    if session_id in st.session_state.chat_sessions:
        st.session_state.messages = st.session_state.chat_sessions[session_id]["messages"].copy()
        st.session_state.current_session_id = session_id
        return True
    return False

def delete_chat_session(session_id):
    """Delete chat session"""
    if session_id in st.session_state.chat_sessions:
        del st.session_state.chat_sessions[session_id]
        if st.session_state.current_session_id == session_id:
            st.session_state.current_session_id = None
            st.session_state.messages = []

# ===============================
# DISPLAY FUNCTIONS
# ===============================

def display_custom_chat(messages):
    """Display chat messages with custom styling"""
    if not messages:
        st.markdown("""
        <div class="welcome-message">
            <h3>💬 AI Agent Pháp Chế Khoáng Sản</h3>
            <p>Sử dụng <strong>OpenAI API với Response/Chat Completions</strong></p>
            <p>Đặt câu hỏi bên dưới để bắt đầu cuộc trò chuyện</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    chat_html = '<div class="chat-container">'
    
    for message in messages:
        timestamp = message.get("timestamp", "")
        time_str = ""
        
        if timestamp:
            try:
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                time_str = dt.strftime('%H:%M')
            except:
                time_str = ""
        
        # Escape HTML and format content
        content = message["content"].replace('<', '&lt;').replace('>', '&gt;')
        content = content.replace('**', '<strong>').replace('**', '</strong>')
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
            api_info = ""
            if message.get("metadata") and message["metadata"].get("api_used"):
                api_type = message["metadata"]["api_used"]
                if api_type == "responses":
                    api_info = " (Responses API)"
                elif api_type == "chat_completions":
                    api_info = " (Chat API)"
            
            chat_html += f'''
            <div class="ai-message">
                <div class="ai-bubble">
                    {content}
                </div>
            </div>
            {f'<div class="chat-info">⚖️ AI Agent{api_info} • {time_str}</div>' if time_str else f'<div class="chat-info">⚖️ AI Agent{api_info}</div>'}
            '''
    
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

# ===============================
# OPENAI API FUNCTIONS
# ===============================

def init_openai_client():
    """Initialize OpenAI client with proper error handling for Streamlit Cloud"""
    try:
        # Get API key from Streamlit secrets
        api_key = st.secrets.get("OPENAI_API_KEY")
        
        if not api_key:
            st.error("❌ **Chưa cấu hình OPENAI_API_KEY**")
            st.info("""
            📝 **Hướng dẫn setup Streamlit Cloud:**
            1. Vào **App settings** → **Secrets**
            2. Thêm:
            ```toml
            OPENAI_API_KEY = "sk-your-key-here"
            ```
            3. Save và deploy lại
            """)
            st.stop()
            
        # Validate API key format
        if not api_key.startswith('sk-'):
            st.error("❌ **API key không đúng định dạng**")
            st.info("API key phải bắt đầu bằng 'sk-'")
            st.stop()
        
        # Initialize client
        client = openai.OpenAI(api_key=api_key)
        
        # Test connection
        try:
            # Test với lightweight call
            test_response = client.models.list()
            st.session_state.api_status = {"connected": True, "api_type": "openai"}
            return client
        except Exception as e:
            st.error(f"❌ **Không thể kết nối OpenAI:** {str(e)}")
            st.info("💡 Kiểm tra API key và thử lại")
            st.session_state.api_status = {"connected": False, "api_type": None}
            st.stop()
            
    except Exception as e:
        st.error(f"❌ **Lỗi khởi tạo OpenAI client:** {str(e)}")
        st.session_state.api_status = {"connected": False, "api_type": None}
        st.stop()

def get_file_search_tools():
    """Get file search tools configuration"""
    tools = []
    
    # Get file IDs from secrets
    file_ids = st.secrets.get("FILE_IDS", "").split(",") if st.secrets.get("FILE_IDS") else []
    file_ids = [fid.strip() for fid in file_ids if fid.strip()]
    
    if file_ids:
        tools.append({
            "type": "file_search",
            "file_search": {
                "vector_store_ids": file_ids,
                "max_num_results": 20
            }
        })
    else:
        # Default file search without specific files
        tools.append({"type": "file_search"})
    
    return tools, len(file_ids)

def prepare_messages(question: str, conversation_history: List[Dict]) -> List[Dict]:
    """Prepare messages for OpenAI API"""
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

def get_ai_response(client, question: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Get AI response with Response API fallback to Chat Completions"""
    try:
        messages = prepare_messages(question, conversation_history)
        tools, file_count = get_file_search_tools()
        
        # Try Response API first (if available)
        try:
            response = client.responses.create(
                model=OPTIMIZED_PARAMS["model"],
                input=messages,
                tools=tools,
                temperature=OPTIMIZED_PARAMS["temperature"],
                max_tokens=OPTIMIZED_PARAMS["max_tokens"],
                store=True
            )
            
            # Extract response text
            if hasattr(response, 'output_text'):
                response_text = response.output_text
            elif hasattr(response, 'output') and response.output:
                if isinstance(response.output, list) and len(response.output) > 0:
                    last_output = response.output[-1]
                    if hasattr(last_output, 'content'):
                        if isinstance(last_output.content, list) and len(last_output.content) > 0:
                            response_text = last_output.content[0].text
                        else:
                            response_text = str(last_output.content)
                    else:
                        response_text = str(last_output)
                else:
                    response_text = str(response.output)
            else:
                response_text = "Không thể xử lý phản hồi từ Response API"
            
            return {
                "success": True,
                "response": response_text,
                "api_used": "responses",
                "file_count": file_count
            }
            
        except Exception as responses_error:
            # Fallback to Chat Completions API
            st.info("🔄 **Fallback**: Sử dụng Chat Completions API...")
            
            # Prepare tools for Chat Completions
            chat_tools = None
            if tools:
                chat_tools = tools
            
            response = client.chat.completions.create(
                model=OPTIMIZED_PARAMS["model"],
                messages=messages,
                temperature=OPTIMIZED_PARAMS["temperature"],
                max_tokens=OPTIMIZED_PARAMS["max_tokens"],
                tools=chat_tools,
                tool_choice="auto" if chat_tools else None
            )
            
            response_text = response.choices[0].message.content
            
            return {
                "success": True,
                "response": response_text,
                "api_used": "chat_completions",
                "file_count": file_count,
                "fallback_reason": str(responses_error)
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi API: {str(e)}",
            "api_used": "error"
        }

# ===============================
# MAIN APPLICATION
# ===============================

def main():
    # Initialize session state
    init_session_state()
    
    # Header
    st.title("⚖️ AI Agent Pháp Chế Khoáng Sản")
    st.markdown("*Tối ưu hóa cho **Streamlit Cloud** với OpenAI Response API + Chat Completions*")
    
    # API Status badge
    st.markdown("""
    <div class="new-api-badge">
        🚀 Streamlit Cloud Ready - OpenAI API Integration
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize client
    if not st.session_state.client:
        with st.spinner("🔌 Đang kết nối OpenAI API..."):
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
            st.session_state.messages = []
        
        # Display chat
        display_custom_chat(st.session_state.messages)
        
        # Chat input
        if prompt := st.chat_input("Đặt câu hỏi về pháp luật khoáng sản..."):
            handle_chat_input(prompt)
    
    with col2:
        # Control panel
        st.header("🔧 Quản Lý")
        
        # API Status
        st.subheader("📊 Trạng Thái")
        if st.session_state.api_status["connected"]:
            st.markdown('<div class="status-indicator status-success">✅ OpenAI Connected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-indicator status-error">❌ OpenAI Disconnected</div>', unsafe_allow_html=True)
        
        # Config info
        with st.expander("⚙️ Cấu Hình"):
            has_api_key = bool(st.secrets.get("OPENAI_API_KEY"))
            file_ids = st.secrets.get("FILE_IDS", "").split(",") if st.secrets.get("FILE_IDS") else []
            file_count = len([fid for fid in file_ids if fid.strip()])
            
            st.write("**OPENAI_API_KEY:**", "✅" if has_api_key else "❌")
            st.write("**FILE_IDS:**", f"✅ ({file_count} files)" if file_count > 0 else "❌ (Optional)")
            
            if not has_api_key:
                st.error("⚠️ Cần cấu hình OPENAI_API_KEY trong Secrets")
        
        st.divider()
        
        # Session Management
        st.subheader("💬 Chat Sessions")
        
        if st.button("🆕 Chat Mới", use_container_width=True):
            # Save current session
            if st.session_state.current_session_id and st.session_state.messages:
                for msg in st.session_state.messages:
                    save_message_to_session(
                        st.session_state.current_session_id, 
                        msg["role"], 
                        msg["content"],
                        msg.get("metadata")
                    )
            
            # Create new session
            new_session_id = create_chat_session()
            st.session_state.current_session_id = new_session_id
            st.session_state.messages = []
            st.success("✅ Đã tạo chat mới!")
            st.rerun()
        
        # Session list
        sessions = get_chat_sessions()
        
        if sessions:
            st.write("**📚 Lịch sử chat:**")
            for i, session in enumerate(sessions[:5]):  # Show last 5 sessions
                with st.container():
                    col_a, col_b = st.columns([4, 1])
                    
                    with col_a:
                        session_label = f"{session['title']} ({session['message_count']})"
                        if st.button(
                            session_label, 
                            key=f"load_{session['session_id']}", 
                            use_container_width=True
                        ):
                            # Save current session first
                            if st.session_state.current_session_id and st.session_state.messages:
                                for msg in st.session_state.messages:
                                    save_message_to_session(
                                        st.session_state.current_session_id, 
                                        msg["role"], 
                                        msg["content"],
                                        msg.get("metadata")
                                    )
                            
                            # Load selected session
                            if load_chat_session(session["session_id"]):
                                st.success(f"✅ Đã tải: {session['title']}")
                                st.rerun()
                    
                    with col_b:
                        if st.button("🗑️", key=f"del_{session['session_id']}"):
                            delete_chat_session(session["session_id"])
                            st.success("✅ Đã xóa!")
                            st.rerun()
        else:
            st.info("📝 Chưa có chat nào")
        
        st.divider()
        
        # Deploy Info
        st.subheader("🚀 Deploy Info")
        
        with st.expander("📋 Streamlit Cloud Setup"):
            st.markdown("""
            **✅ Required Secrets:**
            ```toml
            OPENAI_API_KEY = "sk-your-key-here"
            ```
            
            **📁 Optional Secrets:**
            ```toml
            FILE_IDS = "file-abc123,file-def456"
            ```
            
            **📦 Requirements.txt:**
            ```
            streamlit>=1.28.0
            openai>=1.12.0
            ```
            
            **⚡ Features:**
            - ✅ Session state storage (no database)
            - ✅ Response API with Chat fallback  
            - ✅ File search integration
            - ✅ Streamlit Cloud optimized
            """)
        
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
            **🐛 Common Issues:**
            
            1. **API Key Error:**
               - Check Secrets configuration
               - Verify key format (starts with 'sk-')
            
            2. **Response API Not Available:**
               - App auto-fallbacks to Chat Completions
               - No action needed
            
            3. **Session Lost:**
               - Sessions stored in browser memory
               - Will reset on page refresh
            
            4. **File Search Not Working:**
               - Add FILE_IDS to Secrets
               - Upload files via OpenAI API first
            """)

def handle_chat_input(prompt):
    """Handle chat input with proper error handling"""
    # Add user message
    user_message = {
        "role": "user", 
        "content": prompt, 
        "timestamp": datetime.now().isoformat()
    }
    st.session_state.messages.append(user_message)
    
    # Save to current session
    if st.session_state.current_session_id:
        save_message_to_session(
            st.session_state.current_session_id, 
            "user", 
            prompt
        )
    
    # Get AI response
    with st.spinner("🤔 AI đang phân tích..."):
        conversation_history = [msg for msg in st.session_state.messages[:-1]]
        
        result = get_ai_response(
            st.session_state.client,
            prompt,
            conversation_history
        )
        
        if result["success"]:
            response = result["response"]
            api_used = result["api_used"]
            
            # Show API status
            if api_used == "responses":
                st.success("✅ Response API")
            elif api_used == "chat_completions":
                st.info("ℹ️ Chat Completions API")
            
            # Add AI response
            ai_message = {
                "role": "assistant", 
                "content": response, 
                "timestamp": datetime.now().isoformat(),
                "metadata": {"api_used": api_used}
            }
            st.session_state.messages.append(ai_message)
            
            # Save to current session
            if st.session_state.current_session_id:
                save_message_to_session(
                    st.session_state.current_session_id, 
                    "assistant", 
                    response,
                    {"api_used": api_used}
                )
            
            st.rerun()
            
        else:
            error_msg = f"❌ {result['error']}"
            st.error(error_msg)
            
            # Add error message
            error_message = {
                "role": "assistant", 
                "content": error_msg, 
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.messages.append(error_message)

if __name__ == "__main__":
    main()