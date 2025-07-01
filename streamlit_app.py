import streamlit as st
from openai import OpenAI
import requests
import json
from datetime import datetime
import re
from urllib.parse import quote
import time
import os

# Cấu hình trang
st.set_page_config(
    page_title="⚖️ Trợ lý Pháp chế Khoáng sản Việt Nam",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Model pricing (USD per 1K tokens)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03}
}

def init_session_state():
    """Khởi tạo session state an toàn"""
    if "token_stats" not in st.session_state:
        st.session_state.token_stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "session_start": datetime.now(),
            "request_count": 0
        }
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "assistant", "content": get_welcome_message()}
        ]

def safe_get_stats():
    """Lấy stats một cách an toàn"""
    try:
        init_session_state()
        stats = st.session_state.token_stats
        total_tokens = stats["total_input_tokens"] + stats["total_output_tokens"]
        
        return {
            "total_tokens": total_tokens,
            "input_tokens": stats["total_input_tokens"],
            "output_tokens": stats["total_output_tokens"],
            "total_cost_usd": stats["total_cost"],
            "total_cost_vnd": stats["total_cost"] * 24000,
            "requests": stats["request_count"],
            "session_duration": datetime.now() - stats["session_start"]
        }
    except Exception as e:
        # Return default stats if error
        return {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "total_cost_vnd": 0.0,
            "requests": 0,
            "session_duration": datetime.now() - datetime.now()
        }

def update_stats(input_tokens, output_tokens, model):
    """Cập nhật stats an toàn"""
    try:
        init_session_state()
        
        # Calculate cost
        if model not in MODEL_PRICING:
            model = "gpt-4o-mini"
        
        pricing = MODEL_PRICING[model]
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        
        # Update stats
        st.session_state.token_stats["total_input_tokens"] += input_tokens
        st.session_state.token_stats["total_output_tokens"] += output_tokens
        st.session_state.token_stats["total_cost"] += cost
        st.session_state.token_stats["request_count"] += 1
        
    except Exception as e:
        st.error(f"Lỗi cập nhật stats: {e}")

def count_tokens(text):
    """Ước tính số token đơn giản"""
    return len(str(text)) // 4

def get_system_prompt():
    """Lấy system prompt"""
    try:
        with open("01.system_trainning.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Bạn là chuyên gia pháp chế về quản lý nhà nước trong lĩnh vực khoáng sản tại Việt Nam.

⚖️ NGUYÊN TẮC LÀM VIỆC:
1. CHỈ tập trung vào các vấn đề liên quan đến khoáng sản ở Việt Nam
2. Đưa ra thông tin chính xác, dẫn chiếu cụ thể điều khoản pháp luật khi có
3. Giải thích rõ ràng, dễ hiểu
4. Khi có thông tin web, ưu tiên nguồn chính thống: thuvienphapluat.vn, monre.gov.vn
5. Từ chối lịch sự các câu hỏi không liên quan đến khoáng sản

🎯 CÁCH TRÍCH DẪN:
- Luôn ghi rõ tên văn bản pháp luật, điều, khoản cụ thể nếu có
- Khi có thông tin web: "Dựa theo thông tin từ [nguồn chính thống]..."
- Khi không chắc chắn: "Thông tin tham khảo, vui lòng kiểm tra tại thuvienphapluat.vn"

QUAN TRỌNG: Chỉ trả lời các câu hỏi về khoáng sản. Nếu câu hỏi không liên quan, hãy lịch sự chuyển hướng về lĩnh vực chuyên môn."""

def get_welcome_message():
    """Lấy tin nhắn chào mừng"""
    try:
        with open("02.assistant.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Xin chào! ⚖️ 

Tôi là **Trợ lý Pháp chế chuyên về Quản lý Nhà nước trong lĩnh vực Khoáng sản tại Việt Nam**.

🏔️ **Tôi có thể hỗ trợ bạn về:**

✅ **Pháp luật Khoáng sản:**
   • Luật Khoáng sản và các văn bản hướng dẫn
   • Nghị định, Thông tư của Bộ TN&MT

✅ **Thủ tục hành chính:**
   • Cấp Giấy phép thăm dò, khai thác khoáng sản
   • Gia hạn, sửa đổi giấy phép

✅ **Thuế và phí:**
   • Thuế tài nguyên
   • Tiền cấp quyền khai thác
   • Phí thăm dò

✅ **Xử phạt vi phạm:**
   • Các hành vi vi phạm và mức phạt
   • Biện pháp khắc phục

🎯 **Lưu ý:** Tôi chỉ tư vấn về lĩnh vực **Khoáng sản**.

**Bạn có câu hỏi gì về pháp luật Khoáng sản?** 🤔

**Để có thông tin chính xác nhất, hãy tham khảo tại thuvienphapluat.vn**"""

def get_default_model():
    """Lấy model mặc định"""
    try:
        with open("module_chatgpt.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "gpt-4o-mini"

def is_mineral_related(message):
    """Kiểm tra câu hỏi có liên quan đến khoáng sản không"""
    mineral_keywords = [
        'khoáng sản', 'khai thác', 'thăm dò', 'đá', 'cát', 'sỏi',
        'than', 'quặng', 'kim loại', 'khoáng', 'luật khoáng sản',
        'giấy phép', 'cấp phép', 'thuế tài nguyên', 'phí thăm dò',
        'bộ tài nguyên', 'monre', 'tn&mt', 'mỏ', 'mining'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mineral_keywords)

def should_search_web(message):
    """Kiểm tra có cần tìm kiếm web không"""
    search_indicators = [
        'mới nhất', 'cập nhật', 'hiện hành', 'ban hành',
        'nghị định', 'thông tư', 'luật', 'pháp luật', 'điều'
    ]
    
    message_lower = message.lower()
    return (is_mineral_related(message) and 
            any(indicator in message_lower for indicator in search_indicators))

def simple_web_search(query, max_results=3):
    """Tìm kiếm web đơn giản"""
    try:
        # Tìm kiếm trên thuvienphapluat.vn
        params = {
            'q': f"site:thuvienphapluat.vn {query} khoáng sản",
            'format': 'json',
            'no_html': '1'
        }
        
        response = requests.get("https://api.duckduckgo.com/", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            if data.get('Abstract'):
                results.append({
                    'title': data.get('AbstractText', 'Thông tin pháp luật')[:100],
                    'content': data.get('Abstract'),
                    'url': data.get('AbstractURL', ''),
                    'source': 'Thư viện Pháp luật'
                })
            
            for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '')[:80] + '...',
                        'content': topic.get('Text', ''),
                        'url': topic.get('FirstURL', ''),
                        'source': 'Thư viện Pháp luật'
                    })
            
            return results
    
    except Exception as e:
        pass
    
    return []

def create_search_prompt(user_message, search_results):
    """Tạo prompt với kết quả tìm kiếm"""
    if not search_results:
        return f"""
{user_message}

QUAN TRỌNG: Không tìm thấy thông tin từ nguồn pháp luật chính thống.
Hãy trả lời dựa trên kiến thức có sẵn và ghi rõ:
- Đây là thông tin tham khảo
- Khuyến nghị kiểm tra tại thuvienphapluat.vn
"""
    
    search_info = "\n\n=== THÔNG TIN PHÁP LUẬT TÌM KIẾM ===\n"
    for i, result in enumerate(search_results, 1):
        search_info += f"\nNguồn {i} ({result['source']}):\n"
        search_info += f"Tiêu đề: {result['title']}\n"
        search_info += f"Nội dung: {result['content'][:500]}...\n"
        if result.get('url'):
            search_info += f"URL: {result['url']}\n"
        search_info += "---\n"
    
    search_info += """
HƯỚNG DẪN:
- Ưu tiên thông tin từ Thư viện Pháp luật
- Trích dẫn cụ thể nếu có điều khoản
- Luôn khuyến nghị kiểm tra tại thuvienphapluat.vn
=== KẾT THÚC THÔNG TIN ===

"""
    
    return search_info + f"Câu hỏi: {user_message}"

def main():
    # Khởi tạo session state
    init_session_state()
    
    # CSS
    st.markdown("""
    <style>
    .assistant-message {
        background: #f0f8ff;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        max-width: 80%;
        border-left: 4px solid #4CAF50;
    }
    .assistant-message::before { 
        content: "⚖️ Trợ lý Pháp chế: "; 
        font-weight: bold; 
        color: #2E7D32;
    }
    
    .user-message {
        background: #e3f2fd;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0 10px auto;
        max-width: 80%;
        text-align: right;
        border-right: 4px solid #2196F3;
    }
    .user-message::before { 
        content: "👤 Bạn: "; 
        font-weight: bold; 
        color: #1976D2;
    }
    
    .stats-box {
        background: #f5f5f5;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin: 5px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #2E7D32, #4CAF50); border-radius: 10px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">⚖️ Trợ lý Pháp chế Khoáng sản</h1>
        <p style="color: #E8F5E8; margin: 5px 0 0 0;">Chuyên gia tư vấn Quản lý Nhà nước về Khoáng sản tại Việt Nam</p>
        <p style="color: #E8F5E8; margin: 5px 0 0 0; font-size: 12px;">🆕 Phiên bản ổn định • GPT-4o-mini • Chính xác pháp luật</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt")
        
        # Web search toggle
        web_search_enabled = st.toggle("🔍 Tìm kiếm pháp luật online", value=True)
        
        # Model selection
        model_options = ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        model_info = {
            "gpt-4o-mini": "💰 Rẻ nhất ($0.15/$0.6 per 1K tokens)",
            "gpt-3.5-turbo": "⚖️ Cân bằng ($1.5/$2 per 1K tokens)", 
            "gpt-4": "🧠 Thông minh ($30/$60 per 1K tokens)",
            "gpt-4-turbo-preview": "🚀 Nhanh ($10/$30 per 1K tokens)"
        }
        
        default_model = get_default_model()
        default_index = model_options.index(default_model) if default_model in model_options else 0
        
        selected_model = st.selectbox("🤖 Model AI:", model_options, index=default_index)
        st.caption(model_info[selected_model])
        
        # Temperature
        temperature = st.slider("🌡️ Độ sáng tạo:", 0.0, 1.0, 0.3, 0.1)
        
        st.markdown("---")
        
        # Stats
        st.markdown("### 📊 Thống kê")
        
        try:
            stats = safe_get_stats()
            
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("🎯 Tổng Token", f"{stats['total_tokens']:,}")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📥 Input", f"{stats['input_tokens']:,}")
            with col2:
                st.metric("📤 Output", f"{stats['output_tokens']:,}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("💰 Chi phí (USD)", f"${stats['total_cost_usd']:.4f}")
            st.metric("💸 Chi phí (VND)", f"{stats['total_cost_vnd']:,.0f}đ")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("📞 Số lượt hỏi", stats['requests'])
            duration = str(stats['session_duration']).split('.')[0]
            st.metric("⏱️ Thời gian", duration)
            st.markdown('</div>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Lỗi hiển thị stats: {e}")
        
        # Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset stats", use_container_width=True):
                try:
                    st.session_state.token_stats = {
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_cost": 0.0,
                        "session_start": datetime.now(),
                        "request_count": 0
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi reset: {e}")
        
        with col2:
            if st.button("🗑️ Xóa chat", use_container_width=True):
                try:
                    st.session_state.messages = [
                        {"role": "system", "content": get_system_prompt()},
                        {"role": "assistant", "content": get_welcome_message()}
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi xóa chat: {e}")
        
        st.markdown("---")
        st.markdown("### 📚 Chuyên môn")
        st.markdown("• Luật Khoáng sản")
        st.markdown("• Nghị định hướng dẫn")
        st.markdown("• Thông tư Bộ TN&MT")
        st.markdown("• Thủ tục cấp phép")
        st.markdown("• Thuế, phí")
        st.markdown("• Xử phạt vi phạm")
        
        st.markdown("---")
        st.success("✅ Phiên bản ổn định")
        st.info("💡 Real-time legal search")
    
    # Check API key
    if not st.secrets.get("OPENAI_API_KEY"):
        st.error("❌ Chưa cấu hình OPENAI_API_KEY!")
        st.stop()
    
    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception as e:
        st.error(f"❌ Lỗi OpenAI: {str(e)}")
        st.stop()
    
    # Display chat history
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            st.markdown(f'<div class="assistant-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)
        elif message["role"] == "user":
            st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Nhập câu hỏi về pháp luật khoáng sản..."):
        
        # Check if mineral related
        if not is_mineral_related(prompt):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
            
            polite_refusal = """Xin lỗi, tôi chỉ tư vấn về **pháp luật khoáng sản** tại Việt Nam.

Tôi có thể hỗ trợ bạn về:
- 🏔️ Luật Khoáng sản và văn bản hướng dẫn
- ⚖️ Thủ tục cấp phép thăm dò, khai thác
- 💰 Thuế, phí liên quan khoáng sản
- ⚠️ Xử phạt vi phạm hành chính

Bạn có câu hỏi về khoáng sản không? 😊"""
            
            st.session_state.messages.append({"role": "assistant", "content": polite_refusal})
            st.markdown(f'<div class="assistant-message">{polite_refusal}</div>', 
                       unsafe_allow_html=True)
            return
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        # Process response
        with st.spinner("🤔 Đang xử lý..."):
            search_results = []
            final_prompt = prompt
            
            # Web search if enabled
            if web_search_enabled and should_search_web(prompt):
                with st.status("🔍 Đang tìm kiếm pháp luật...", expanded=False) as status:
                    search_results = simple_web_search(prompt)
                    
                    if search_results:
                        st.success(f"✅ Tìm thấy {len(search_results)} kết quả")
                        for i, result in enumerate(search_results, 1):
                            st.write(f"**{i}. {result['source']}:** {result['title'][:50]}...")
                        
                        final_prompt = create_search_prompt(prompt, search_results)
                        status.update(label="✅ Hoàn tất tìm kiếm", state="complete")
                    else:
                        status.update(label="⚠️ Không tìm thấy", state="complete")
            
            # Count input tokens
            messages_for_api = [
                msg for msg in st.session_state.messages[:-1] 
                if msg["role"] != "system" or msg == st.session_state.messages[0]
            ]
            messages_for_api.append({"role": "user", "content": final_prompt})
            
            input_text = "\n".join([msg["content"] for msg in messages_for_api])
            input_tokens = count_tokens(input_text)
            
            # Generate response
            try:
                response = ""
                
                stream = client.chat.completions.create(
                    model=selected_model,
                    messages=messages_for_api,
                    stream=True,
                    temperature=temperature,
                    max_tokens=2000
                )
                
                response_container = st.empty()
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        response += chunk.choices[0].delta.content
                        response_container.markdown(
                            f'<div class="assistant-message">{response}▌</div>', 
                            unsafe_allow_html=True
                        )
                
                # Final response
                response_container.markdown(
                    f'<div class="assistant-message">{response}</div>', 
                    unsafe_allow_html=True
                )
                
                # Update stats
                output_tokens = count_tokens(response)
                update_stats(input_tokens, output_tokens, selected_model)
                
                # Show request stats
                with st.expander("📊 Request stats"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Input tokens", f"{input_tokens:,}")
                    with col2:
                        st.metric("Output tokens", f"{output_tokens:,}")
                    with col3:
                        if selected_model in MODEL_PRICING:
                            pricing = MODEL_PRICING[selected_model]
                            cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
                            st.metric("Chi phí", f"${cost:.4f}")
                
            except Exception as e:
                error_msg = f"❌ Lỗi: {str(e)}"
                st.markdown(f'<div class="assistant-message">{error_msg}</div>', 
                           unsafe_allow_html=True)
                response = error_msg
        
        # Add response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()