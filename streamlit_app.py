import streamlit as st
from openai import OpenAI
import requests
from datetime import datetime
from urllib.parse import quote
import os
import re

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
    """Khởi tạo session state"""
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
    """Lấy thống kê an toàn"""
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

def update_stats(input_tokens, output_tokens, model):
    """Cập nhật thống kê"""
    init_session_state()
    if model not in MODEL_PRICING:
        model = "gpt-4o-mini"
    pricing = MODEL_PRICING[model]
    cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
    st.session_state.token_stats["total_input_tokens"] += input_tokens
    st.session_state.token_stats["total_output_tokens"] += output_tokens
    st.session_state.token_stats["total_cost"] += cost
    st.session_state.token_stats["request_count"] += 1

def count_tokens(text):
    """Ước tính số token"""
    return len(str(text)) // 4

def get_system_prompt():
    """Lấy system prompt"""
    try:
        with open("01.system_trainning.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Bạn là chuyên gia pháp chế về khoáng sản tại Việt Nam. 
- Chỉ trả lời các vấn đề liên quan đến khoáng sản.
- Đưa ra thông tin chính xác, trích dẫn điều luật cụ thể.
- Giải thích rõ ràng, dễ hiểu.
- Ưu tiên nguồn chính thống: vbpl.vn, thuvienphapluat.vn, monre.gov.vn, chinhphu.vn.
- Từ chối lịch sự các câu hỏi không liên quan.
- Trích dẫn: Ghi rõ văn bản, điều, khoản; đề xuất kiểm tra vbpl.vn nếu không chắc chắn."""

def get_welcome_message():
    """Lấy tin nhắn chào"""
    try:
        with open("02.assistant.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """⚖️ Xin chào! Tôi là Trợ lý Pháp chế Khoáng sản Việt Nam.
Hỗ trợ: Luật Khoáng sản, thủ tục cấp phép, thuế phí, xử phạt vi phạm.
Hỏi tôi về khoáng sản nhé! 🤔 Kiểm tra thông tin tại vbpl.vn."""

def get_default_model():
    """Lấy model mặc định"""
    try:
        with open("module_chatgpt.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "gpt-4o-mini"

def is_mineral_related(message):
    """Kiểm tra câu hỏi liên quan khoáng sản"""
    mineral_keywords = [
        'khoáng sản', 'khai thác', 'thăm dò', 'đá', 'cát', 'sỏi',
        'than', 'quặng', 'kim loại', 'khoáng', 'luật khoáng sản',
        'giấy phép', 'cấp phép', 'thuế tài nguyên', 'phí thăm dò',
        'bộ tài nguyên', 'monre', 'tn&mt', 'mỏ', 'mining'
    ]
    return any(keyword in message.lower() for keyword in mineral_keywords)

def should_search_web(message):
    """Kiểm tra cần tìm kiếm web"""
    search_indicators = ['mới nhất', 'cập nhật', 'hiện hành', 'ban hành', 'nghị định', 'thông tư', 'luật', 'pháp luật', 'điều']
    return is_mineral_related(message) and any(indicator in message.lower() for indicator in search_indicators)

def validate_law_number(law_number, law_year):
    """Kiểm tra tính hợp lệ của số hiệu văn bản"""
    valid_laws = [
        {"number": "60/2010/QH12", "year": 2010, "title": "Luật Khoáng sản"},
        {"number": "54/2024/QH15", "year": 2024, "title": "Luật Địa chất và Khoáng sản"}
    ]
    for law in valid_laws:
        if law_number == law["number"] and law_year == law["year"]:
            return True
    return False

def simple_web_search(query, max_results=3):
    """Tìm kiếm web tối ưu, ưu tiên vbpl.vn"""
    try:
        trusted_domains = ["vbpl.vn", "thuvienphapluat.vn", "monre.gov.vn", "chinhphu.vn"]
        encoded_query = quote(f"{query} khoáng sản site:vbpl.vn")
        search_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': st.secrets.get("GOOGLE_API_KEY"),
            'cx': st.secrets.get("GOOGLE_CSE_ID"),
            'q': encoded_query,
            'num': max_results,
            'siteSearch': "site:vbpl.vn"
        }
        response = requests.get(search_url, params=params, timeout=10)
        results = []
        if response.status_code == 200:
            data = response.json()
            for item in data.get('items', [])[:max_results]:
                content = item.get('snippet', '')
                if len(content) > 50 and "vbpl.vn" in item.get('link', ''):
                    # Kiểm tra số hiệu văn bản trong tiêu đề hoặc nội dung
                    law_match = re.search(r'(\d+/\d{4}/QH\d+)', content)
                    if law_match:
                        law_number = law_match.group(1)
                        year = int(law_number.split('/')[1])
                        if not validate_law_number(law_number, year):
                            continue  # Bỏ qua nếu số hiệu không hợp lệ
                    results.append({
                        'title': item.get('title', '')[:100],
                        'content': content[:500],
                        'url': item.get('link', ''),
                        'source': 'vbpl.vn'
                    })
            return results
        return []
    except Exception as e:
        return []

def create_search_prompt(user_message, search_results):
    """Tạo prompt với kết quả tìm kiếm"""
    if not search_results:
        return f"{user_message}\n\nLưu ý: Không tìm thấy thông tin từ vbpl.vn. Vui lòng kiểm tra tại vbpl.vn hoặc thuvienphapluat.vn."
    
    search_info = "\n\n=== THÔNG TIN TÌM KIẾM ===\n"
    for i, result in enumerate(search_results, 1):
        search_info += f"\nNguồn {i} ({result['source']}):\nTiêu đề: {result['title']}\nNội dung: {result['content']}...\nURL: {result['url']}\n---\n"
    search_info += """HƯỚNG DẪN:
- Ưu tiên thông tin từ vbpl.vn, thuvienphapluat.vn, monre.gov.vn, chinhphu.vn.
- Trích dẫn văn bản, điều, khoản cụ thể nếu có.
- Khuyến nghị kiểm tra vbpl.vn để xác nhận.\n=== KẾT THÚC ===\n"""
    return search_info + f"Câu hỏi: {user_message}"

def main():
    init_session_state()
    st.markdown("""
    <style>
    .assistant-message { background: #f0f8ff; padding: 15px; border-radius: 15px; margin: 10px 0; max-width: 80%; border-left: 4px solid #4CAF50; }
    .assistant-message::before { content: "⚖️ Trợ lý Pháp chế: "; font-weight: bold; color: #2E7D32; }
    .user-message { background: #e3f2fd; padding: 15px; border-radius: 15px; margin: 10px 0 10px auto; max-width: 80%; text-align: right; border-right: 4px solid #2196F3; }
    .user-message::before { content: "👤 Bạn: "; font-weight: bold; color: #1976D2; }
    .stats-box { background: #f5f5f5; padding: 10px; border-radius: 8px; border: 1px solid #ddd; margin: 5px 0; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #2E7D32, #4CAF50); border-radius: 10px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">⚖️ Trợ lý Pháp chế Khoáng sản</h1>
        <p style="color: #E8F5E8; margin: 5px 0 0 0;">Chuyên gia tư vấn Quản lý Nhà nước về Khoáng sản</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt")
        web_search_enabled = st.toggle("🔍 Tìm kiếm pháp luật", value=True)
        model_options = ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        model_info = {
            "gpt-4o-mini": "💰 Rẻ nhất",
            "gpt-3.5-turbo": "⚖️ Cân bằng", 
            "gpt-4": "🧠 Thông minh",
            "gpt-4-turbo-preview": "🚀 Nhanh"
        }
        default_model = get_default_model()
        default_index = model_options.index(default_model) if default_model in model_options else 0
        selected_model = st.selectbox("🤖 Model AI:", model_options, index=default_index)
        st.caption(model_info[selected_model])
        temperature = st.slider("🌡️ Độ sáng tạo:", 0.0, 1.0, 0.3, 0.1)
        
        st.markdown("---")
        st.markdown("### 📊 Thống kê")
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
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset stats"):
                st.session_state.token_stats = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "session_start": datetime.now(),
                    "request_count": 0
                }
                st.rerun()
        with col2:
            if st.button("🗑️ Xóa chat"):
                st.session_state.messages = [
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "assistant", "content": get_welcome_message()}
                ]
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📚 Chuyên môn")
        st.markdown("• Luật Khoáng sản\n• Nghị định\n• Thông tư\n• Cấp phép\n• Thuế, phí\n• Xử phạt")
        st.success("✅ Phiên bản ổn định")

    if not st.secrets.get("OPENAI_API_KEY") or not st.secrets.get("GOOGLE_API_KEY") or not st.secrets.get("GOOGLE_CSE_ID"):
        st.error("❌ Chưa cấu hình API keys!")
        st.stop()
    
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            st.markdown(f'<div class="assistant-message">{message["content"]}</div>', unsafe_allow_html=True)
        elif message["role"] == "user":
            st.markdown(f'<div class="user-message">{message["content"]}</div>', unsafe_allow_html=True)
    
    if prompt := st.chat_input("Nhập câu hỏi về khoáng sản..."):
        if not is_mineral_related(prompt):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
            polite_refusal = """Xin lỗi, tôi chỉ tư vấn về khoáng sản. Hỏi về Luật Khoáng sản, cấp phép, thuế phí, hoặc xử phạt nhé! 😊"""
            st.session_state.messages.append({"role": "assistant", "content": polite_refusal})
            st.markdown(f'<div class="assistant-message">{polite_refusal}</div>', unsafe_allow_html=True)
            return
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        with st.spinner("🤔 Đang xử lý..."):
            search_results = []
            final_prompt = prompt
            if web_search_enabled and should_search_web(prompt):
                with st.status("🔍 Đang tìm kiếm..."):
                    search_results = simple_web_search(prompt)
                    if search_results:
                        st.success(f"✅ Tìm thấy {len(search_results)} kết quả từ vbpl.vn")
                        for i, result in enumerate(search_results, 1):
                            st.write(f"**{i}. {result['source']}:** {result['title'][:50]}...")
                        final_prompt = create_search_prompt(prompt, search_results)
                    else:
                        st.warning("⚠️ Không tìm thấy kết quả từ vbpl.vn")
            
            messages_for_api = [
                msg for msg in st.session_state.messages[:-1] 
                if msg["role"] != "system" or msg == st.session_state.messages[0]
            ]
            messages_for_api.append({"role": "user", "content": final_prompt})
            input_tokens = count_tokens("\n".join([msg["content"] for msg in messages_for_api]))
            
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
                        response_container.markdown(f'<div class="assistant-message">{response}▌</div>', unsafe_allow_html=True)
                
                response_container.markdown(f'<div class="assistant-message">{response}</div>', unsafe_allow_html=True)
                output_tokens = count_tokens(response)
                update_stats(input_tokens, output_tokens, selected_model)
                
                with st.expander("📊 Thống kê yêu cầu"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Input tokens", f"{input_tokens:,}")
                    with col2:
                        st.metric("Output tokens", f"{output_tokens:,}")
                    with col3:
                        pricing = MODEL_PRICING[selected_model]
                        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
                        st.metric("Chi phí", f"${cost:.4f}")
                
            except Exception as e:
                response = f"❌ Lỗi: {str(e)}"
                st.markdown(f'<div class="assistant-message">{response}</div>', unsafe_allow_html=True)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()