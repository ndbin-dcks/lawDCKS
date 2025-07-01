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
    page_title="AI Assistant với Web Search",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hàm đọc nội dung từ file văn bản với error handling
def rfile(name_file):
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        # Fallback content nếu file không tồn tại
        fallback_content = {
            "00.xinchao.txt": "🤖 Trợ lý AI thông minh",
            "01.system_trainning.txt": "Bạn là một trợ lý AI hữu ích, thông minh và thân thiện. Hãy trả lời câu hỏi một cách chính xác và hữu ích.",
            "02.assistant.txt": "Xin chào! Tôi là trợ lý AI của bạn. Tôi có thể giúp bạn tìm kiếm thông tin, trả lời câu hỏi và hỗ trợ nhiều công việc khác. Bạn cần tôi giúp gì?",
            "module_chatgpt.txt": "gpt-3.5-turbo"
        }
        return fallback_content.get(name_file, f"Nội dung mặc định cho {name_file}")

# Lớp xử lý tìm kiếm web tối ưu cho Streamlit Cloud
class CloudWebSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def search(self, query, max_results=3):
        """Tìm kiếm web với error handling mạnh mẽ"""
        try:
            # Thử DuckDuckGo instant answer trước
            results = self._search_duckduckgo_instant(query, max_results)
            
            if not results:
                # Fallback sang Wikipedia search
                results = self._search_wikipedia(query, max_results)
            
            return results[:max_results]
            
        except Exception as e:
            st.error(f"Lỗi tìm kiếm: {str(e)}")
            return self._get_fallback_result(query)
    
    def _search_duckduckgo_instant(self, query, max_results):
        """Tìm kiếm với DuckDuckGo instant answer"""
        try:
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = self.session.get(
                "https://api.duckduckgo.com/", 
                params=params, 
                timeout=10
            )
            
            if response.status_code != 200:
                return []
                
            data = response.json()
            results = []
            
            # Abstract answer
            if data.get('Abstract') and len(data['Abstract']) > 50:
                results.append({
                    'title': data.get('AbstractText', 'Thông tin tổng quan')[:100],
                    'content': data.get('Abstract'),
                    'url': data.get('AbstractURL', ''),
                    'source': data.get('AbstractSource', 'DuckDuckGo')
                })
            
            # Related topics
            for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '')[:80] + '...',
                        'content': topic.get('Text', ''),
                        'url': topic.get('FirstURL', ''),
                        'source': 'DuckDuckGo'
                    })
            
            return results
            
        except Exception as e:
            return []
    
    def _search_wikipedia(self, query, max_results):
        """Tìm kiếm Wikipedia tiếng Việt"""
        try:
            # Wikipedia API search
            search_params = {
                'action': 'query',
                'list': 'search',
                'srsearch': query,
                'format': 'json',
                'srlimit': max_results
            }
            
            search_response = self.session.get(
                'https://vi.wikipedia.org/api/rest_v1/page/summary/' + quote(query),
                timeout=10
            )
            
            results = []
            
            if search_response.status_code == 200:
                data = search_response.json()
                if data.get('extract'):
                    results.append({
                        'title': data.get('title', 'Wikipedia'),
                        'content': data.get('extract', ''),
                        'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                        'source': 'Wikipedia'
                    })
            
            return results
            
        except Exception as e:
            return []
    
    def _get_fallback_result(self, query):
        """Kết quả dự phòng khi tìm kiếm thất bại"""
        return [{
            'title': 'Không thể tìm kiếm web',
            'content': f'Xin lỗi, hiện tại không thể tìm kiếm thông tin cho: "{query}". Tôi sẽ trả lời dựa trên kiến thức có sẵn.',
            'url': '',
            'source': 'Hệ thống'
        }]

# Khởi tạo web searcher
@st.cache_resource
def get_web_searcher():
    return CloudWebSearcher()

web_searcher = get_web_searcher()

# Hàm phân tích xem có cần tìm kiếm web không
def should_search_web(message):
    """Kiểm tra xem câu hỏi có cần tìm kiếm web không"""
    search_indicators = [
        # Tiếng Việt
        'tìm kiếm', 'tin tức', 'thông tin mới', 'cập nhật', 'hiện tại', 
        'gần đây', 'mới nhất', 'thời tiết', 'giá', 'tỷ giá', 'hôm nay',
        'what is', 'who is', 'where is', 'when did', 'how much',
        # Tiếng Anh
        'search', 'news', 'latest', 'current', 'recent', 'today',
        'weather', 'price', 'stock', 'rate'
    ]
    
    message_lower = message.lower()
    return any(indicator in message_lower for indicator in search_indicators)

# Hàm tạo prompt với kết quả tìm kiếm
def create_enhanced_prompt(user_message, search_results):
    """Tạo prompt kết hợp thông tin tìm kiếm"""
    if not search_results or not any(r.get('content') for r in search_results):
        return user_message
    
    search_info = "\n\n=== THÔNG TIN TÌM KIẾM WEB ===\n"
    for i, result in enumerate(search_results, 1):
        if result.get('content'):
            search_info += f"\nNguồn {i} ({result['source']}):\n"
            search_info += f"Tiêu đề: {result['title']}\n"
            search_info += f"Nội dung: {result['content'][:500]}...\n"
            if result.get('url'):
                search_info += f"URL: {result['url']}\n"
            search_info += "---\n"
    
    search_info += "\nHướng dẫn: Sử dụng thông tin trên để trả lời câu hỏi của người dùng. "
    search_info += "Hãy trích dẫn nguồn rõ ràng bằng cách viết 'Theo [Tên nguồn]' hoặc 'Dựa theo [Tên nguồn]'.\n"
    search_info += "=== KẾT THÚC THÔNG TIN TÌM KIẾM ===\n\n"
    
    return search_info + f"Câu hỏi của người dùng: {user_message}"

# Main UI
def main():
    # Header
    st.markdown(
        """
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #1f77b4;">🤖 AI Assistant với Web Search</h1>
            <p style="color: #666;">Trợ lý AI thông minh với khả năng tìm kiếm web và trích dẫn nguồn</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt")
        
        # Toggle web search
        web_search_enabled = st.toggle("🔍 Tìm kiếm web", value=True)
        
        # Model selection
        model_options = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        selected_model = st.selectbox("🤖 Chọn model AI:", model_options, index=0)
        
        # Temperature setting
        temperature = st.slider("🌡️ Creativity (Temperature):", 0.0, 1.0, 0.7, 0.1)
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
            st.session_state.messages = [
                {"role": "system", "content": rfile("01.system_trainning.txt")},
                {"role": "assistant", "content": rfile("02.assistant.txt")}
            ]
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 💡 Mẹo sử dụng")
        st.markdown("• Hỏi về tin tức, thời tiết, giá cả để kích hoạt tìm kiếm web")
        st.markdown("• Bot sẽ tự động trích dẫn nguồn khi tìm thấy thông tin")
        st.markdown("• Có thể tắt tìm kiếm web nếu chỉ muốn chat thông thường")
    
    # Check API key
    if not st.secrets.get("OPENAI_API_KEY"):
        st.error("❌ Chưa cấu hình OPENAI_API_KEY trong secrets!")
        st.stop()
    
    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception as e:
        st.error(f"❌ Lỗi khởi tạo OpenAI client: {str(e)}")
        st.stop()
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": rfile("01.system_trainning.txt")},
            {"role": "assistant", "content": rfile("02.assistant.txt")}
        ]
    
    # Display chat history
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"])
        elif message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        
        # Process response
        with st.chat_message("assistant", avatar="🤖"):
            response_placeholder = st.empty()
            
            # Check if web search is needed
            search_results = []
            final_prompt = prompt
            
            if web_search_enabled and should_search_web(prompt):
                with st.status("🔍 Đang tìm kiếm thông tin trên web...", expanded=False) as status:
                    search_results = web_searcher.search(prompt, max_results=3)
                    
                    if search_results and any(r.get('content') for r in search_results):
                        st.success(f"✅ Tìm thấy {len(search_results)} kết quả")
                        for i, result in enumerate(search_results, 1):
                            if result.get('content'):
                                st.write(f"**{i}. {result['source']}:** {result['title'][:50]}...")
                        
                        final_prompt = create_enhanced_prompt(prompt, search_results)
                        status.update(label="✅ Hoàn tất tìm kiếm", state="complete", expanded=False)
                    else:
                        status.update(label="⚠️ Không tìm thấy kết quả", state="complete", expanded=False)
            
            # Generate AI response
            try:
                messages_for_api = [
                    msg for msg in st.session_state.messages[:-1] 
                    if msg["role"] != "system" or msg == st.session_state.messages[0]
                ]
                messages_for_api.append({"role": "user", "content": final_prompt})
                
                response = ""
                stream = client.chat.completions.create(
                    model=selected_model,
                    messages=messages_for_api,
                    stream=True,
                    temperature=temperature,
                    max_tokens=2000
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        response += chunk.choices[0].delta.content
                        response_placeholder.markdown(response + "▌")
                
                response_placeholder.markdown(response)
                
            except Exception as e:
                error_msg = f"❌ Lỗi: {str(e)}"
                response_placeholder.markdown(error_msg)
                response = error_msg
        
        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()