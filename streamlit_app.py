import streamlit as st
from openai import OpenAI
import requests
import json
from datetime import datetime
import re
from urllib.parse import quote, urljoin
import time
import os
import tiktoken
from bs4 import BeautifulSoup

# Cấu hình trang
st.set_page_config(
    page_title="⚖️ Trợ lý Pháp chế Khoáng sản Việt Nam",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Pricing cho các models OpenAI (USD per 1K tokens)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03}
}

class SessionStateManager:
    """Quản lý session state an toàn"""
    
    @staticmethod
    def init_token_stats():
        """Khởi tạo token statistics"""
        if "token_stats" not in st.session_state:
            st.session_state.token_stats = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "session_start": datetime.now(),
                "request_count": 0
            }
    
    @staticmethod
    def init_messages():
        """Khởi tạo chat messages"""
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "system", "content": get_system_prompt()},
                {"role": "assistant", "content": get_welcome_message()}
            ]
    
    @staticmethod
    def reset_token_stats():
        """Reset token statistics"""
        st.session_state.token_stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "session_start": datetime.now(),
            "request_count": 0
        }
    
    @staticmethod
    def reset_chat():
        """Reset chat history"""
        st.session_state.messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "assistant", "content": get_welcome_message()}
        ]

class TokenCounter:
    """Lớp đếm token và tính chi phí"""
    
    def __init__(self):
        SessionStateManager.init_token_stats()
    
    def count_tokens(self, text, model="gpt-4o-mini"):
        """Đếm số token trong text"""
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(str(text)))
        except:
            # Fallback estimation: ~4 characters per token
            return len(str(text)) // 4
    
    def calculate_cost(self, input_tokens, output_tokens, model):
        """Tính chi phí dựa trên số token"""
        if model not in MODEL_PRICING:
            model = "gpt-4o-mini"  # Default fallback
        
        pricing = MODEL_PRICING[model]
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
    
    def update_stats(self, input_tokens, output_tokens, model):
        """Cập nhật thống kê"""
        SessionStateManager.init_token_stats()
        
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        
        st.session_state.token_stats["total_input_tokens"] += input_tokens
        st.session_state.token_stats["total_output_tokens"] += output_tokens
        st.session_state.token_stats["total_cost"] += cost
        st.session_state.token_stats["request_count"] += 1
    
    def get_stats(self):
        """Lấy thống kê hiện tại"""
        SessionStateManager.init_token_stats()
        
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

class LegalSearchEngine:
    """Hệ thống tìm kiếm pháp luật nâng cao"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.legal_patterns = {
            'dieu': r'Điều\s+(\d+)',
            'khoan': r'khoản\s+(\d+)',
            'diem': r'điểm\s+([a-z])',
            'luat': r'Luật\s+([^0-9]*?)\s*(?:số\s*)?(\d+/\d+/[A-Z]+\d*)?',
            'nghi_dinh': r'Nghị định\s*(?:số\s*)?(\d+/\d+/[A-Z\-]+)',
            'thong_tu': r'Thông tư\s*(?:số\s*)?(\d+/\d+/[A-Z\-]+)'
        }
    
    def search(self, query, max_results=3):
        """Tìm kiếm pháp luật với độ chính xác cao"""
        try:
            search_type = self._analyze_query(query)
            
            if search_type == 'specific_article':
                results = self._search_specific_article(query, max_results)
            elif search_type == 'law_content':
                results = self._search_law_content(query, max_results)
            else:
                results = self._search_general_legal(query, max_results)
            
            if not results:
                results = self._get_fallback_result(query)
            
            return results[:max_results]
            
        except Exception as e:
            return self._get_error_result(query, str(e))
    
    def _analyze_query(self, query):
        """Phân tích loại query"""
        query_lower = query.lower()
        
        if re.search(r'điều\s+\d+', query_lower):
            return 'specific_article'
        elif any(keyword in query_lower for keyword in ['luật', 'nghị định', 'thông tư']):
            return 'law_content'
        else:
            return 'general'
    
    def _search_specific_article(self, query, max_results):
        """Tìm kiếm điều khoản cụ thể"""
        results = []
        
        try:
            article_match = re.search(r'điều\s+(\d+)', query.lower())
            law_match = re.search(r'luật\s+([^0-9]*?)(?:\s*năm\s*(\d{4})|\s*số\s*([0-9/A-Z]+))?', query.lower())
            
            if article_match and law_match:
                article_num = article_match.group(1)
                law_name = law_match.group(1).strip()
                
                search_query = f"điều {article_num} {law_name} khoáng sản"
                results = self._search_thuvienphapluat(search_query, max_results)
                
                if not results:
                    results = self._search_legal_portals(search_query, max_results)
        
        except Exception:
            pass
        
        return results
    
    def _search_thuvienphapluat(self, query, max_results):
        """Tìm kiếm trên thuvienphapluat.vn"""
        results = []
        
        try:
            params = {
                'q': f"site:thuvienphapluat.vn {query}",
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = self.session.get("https://api.duckduckgo.com/", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('Abstract') and len(data['Abstract']) > 100:
                    confidence = self._calculate_confidence(query, data.get('AbstractText', ''), data.get('Abstract'))
                    results.append({
                        'title': data.get('AbstractText', 'Thông tin pháp luật')[:100],
                        'content': data.get('Abstract'),
                        'url': data.get('AbstractURL', ''),
                        'source': 'Thư viện Pháp luật',
                        'priority': True,
                        'confidence': confidence
                    })
                
                for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                    if isinstance(topic, dict) and topic.get('Text'):
                        confidence = self._calculate_confidence(query, topic.get('Text', ''), topic.get('Text', ''))
                        results.append({
                            'title': topic.get('Text', '')[:80] + '...',
                            'content': topic.get('Text', ''),
                            'url': topic.get('FirstURL', ''),
                            'source': 'Thư viện Pháp luật',
                            'priority': True,
                            'confidence': confidence
                        })
        
        except Exception:
            pass
        
        return results
    
    def _search_legal_portals(self, query, max_results):
        """Tìm kiếm trên các portal chính phủ"""
        results = []
        
        portals = [
            ('portal.gov.vn', 'Cổng thông tin Chính phủ'),
            ('monre.gov.vn', 'Bộ Tài nguyên và Môi trường'),
            ('moj.gov.vn', 'Bộ Tư pháp')
        ]
        
        for domain, source_name in portals:
            try:
                params = {
                    'q': f"site:{domain} {query}",
                    'format': 'json',
                    'no_html': '1'
                }
                
                response = self.session.get("https://api.duckduckgo.com/", params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('Abstract'):
                        confidence = self._calculate_confidence(query, data.get('AbstractText', ''), data.get('Abstract'))
                        results.append({
                            'title': data.get('AbstractText', 'Thông tin pháp luật')[:100],
                            'content': data.get('Abstract'),
                            'url': data.get('AbstractURL', ''),
                            'source': source_name,
                            'priority': True,
                            'confidence': confidence
                        })
                    
                    if len(results) >= max_results:
                        break
                        
            except Exception:
                continue
        
        return results
    
    def _search_law_content(self, query, max_results):
        """Tìm kiếm nội dung pháp luật tổng quát"""
        optimized_query = f"{query} khoáng sản Việt Nam pháp luật"
        results = self._search_thuvienphapluat(optimized_query, max_results)
        
        if len(results) < max_results:
            results.extend(self._search_legal_portals(optimized_query, max_results - len(results)))
        
        return results
    
    def _search_general_legal(self, query, max_results):
        """Tìm kiếm chung"""
        enhanced_query = f"{query} khoáng sản Việt Nam pháp luật"
        results = []
        
        try:
            params = {
                'q': enhanced_query,
                'format': 'json',
                'no_html': '1'
            }
            
            response = self.session.get("https://api.duckduckgo.com/", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('Abstract'):
                    confidence = self._calculate_confidence(query, data.get('AbstractText', ''), data.get('Abstract'))
                    results.append({
                        'title': data.get('AbstractText', 'Thông tin pháp luật'),
                        'content': data.get('Abstract'),
                        'url': data.get('AbstractURL', ''),
                        'source': 'DuckDuckGo',
                        'priority': False,
                        'confidence': confidence
                    })
                
                for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                    if isinstance(topic, dict) and topic.get('Text'):
                        confidence = self._calculate_confidence(query, topic.get('Text', ''), topic.get('Text', ''))
                        results.append({
                            'title': topic.get('Text', '')[:80] + '...',
                            'content': topic.get('Text', ''),
                            'url': topic.get('FirstURL', ''),
                            'source': 'DuckDuckGo',
                            'priority': False,
                            'confidence': confidence
                        })
        
        except Exception:
            pass
        
        return results
    
    def _calculate_confidence(self, query, title, content):
        """Tính độ tin cậy"""
        confidence = 0.3
        
        query_words = set(query.lower().split())
        content_words = set((title + ' ' + content).lower().split())
        
        common_words = query_words.intersection(content_words)
        if len(query_words) > 0:
            word_match_ratio = len(common_words) / len(query_words)
            confidence += word_match_ratio * 0.4
        
        if re.search(r'điều\s+\d+', content.lower()):
            confidence += 0.2
        
        if re.search(r'khoản\s+\d+', content.lower()):
            confidence += 0.1
        
        if any(domain in content.lower() for domain in ['thuvienphapluat', 'gov.vn']):
            confidence += 0.2
        
        if re.search(r'luật\s+khoáng sản', content.lower()):
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _get_fallback_result(self, query):
        """Kết quả dự phòng"""
        return [{
            'title': 'Không tìm thấy thông tin cụ thể',
            'content': f'Không thể tìm thấy thông tin chính xác cho "{query}". Tôi sẽ trả lời dựa trên kiến thức pháp luật có sẵn và khuyến nghị bạn tham khảo trực tiếp tại thuvienphapluat.vn',
            'url': 'https://thuvienphapluat.vn',
            'source': 'Hệ thống',
            'priority': False,
            'confidence': 0.1
        }]
    
    def _get_error_result(self, query, error):
        """Kết quả khi có lỗi"""
        return [{
            'title': 'Lỗi tìm kiếm pháp luật',
            'content': f'Đã xảy ra lỗi khi tìm kiếm: {error}. Vui lòng thử lại sau hoặc tham khảo trực tiếp tại thuvienphapluat.vn',
            'url': 'https://thuvienphapluat.vn',
            'source': 'Hệ thống',
            'priority': False,
            'confidence': 0.0
        }]

def get_system_prompt():
    """Lấy system prompt - KHÔNG có thông tin pháp luật cụ thể"""
    try:
        with open("01.system_trainning.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Bạn là chuyên gia pháp chế về quản lý nhà nước trong lĩnh vực khoáng sản tại Việt Nam.

⚖️ NGUYÊN TẮC LÀM VIỆC:
1. CHỈ tập trung vào các vấn đề liên quan đến khoáng sản ở Việt Nam
2. Đưa ra thông tin chính xác, dẫn chiếu cụ thể điều khoản pháp luật khi có
3. Giải thích rõ ràng, dễ hiểu cho cả chuyên gia và người dân
4. Khi có thông tin web, ưu tiên nguồn chính thống: thuvienphapluat.vn, monre.gov.vn, portal.gov.vn
5. Từ chối một cách lịch sự các câu hỏi không liên quan đến khoáng sản

🎯 CÁCH TRÍCH DẪN:
- Luôn ghi rõ tên văn bản pháp luật, điều, khoản cụ thể nếu có
- Ví dụ: "Theo Điều X khoản Y [Tên luật/nghị định]..."
- Khi có thông tin web: "Dựa theo thông tin từ [nguồn chính thống]..."
- Khi không chắc chắn: "Thông tin tham khảo, vui lòng kiểm tra tại thuvienphapluat.vn"

📋 CÁC CHỦ ĐỀ CHÍNH:
1. Quyền khai thác khoáng sản và thủ tục cấp phép
2. Nghĩa vụ của tổ chức, cá nhân khai thác khoáng sản
3. Thuế tài nguyên và các khoản thu khác
4. Bảo vệ môi trường trong hoạt động khoáng sản
5. Xử phạt vi phạm hành chính
6. Thanh tra, kiểm tra hoạt động khoáng sản

QUAN TRỌNG: Chỉ trả lời các câu hỏi về khoáng sản. Nếu câu hỏi không liên quan, hãy lịch sự chuyển hướng về lĩnh vực chuyên môn và đưa ra ví dụ câu hỏi phù hợp."""

def get_welcome_message():
    """Lấy tin nhắn chào mừng - KHÔNG có thông tin pháp luật cụ thể"""
    try:
        with open("02.assistant.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Xin chào! ⚖️ 

Tôi là **Trợ lý Pháp chế chuyên về Quản lý Nhà nước trong lĩnh vực Khoáng sản tại Việt Nam**.

🏔️ **Tôi có thể hỗ trợ bạn về:**

✅ **Pháp luật Khoáng sản:**
   • Luật Khoáng sản và Luật Địa chất và Khoáng sản
   • Các nghị định hướng dẫn thi hành
   • Thông tư của Bộ Tài nguyên và Môi trường

✅ **Thủ tục hành chính:**
   • Cấp Giấy phép thăm dò khoáng sản
   • Cấp Giấy phép khai thác khoáng sản
   • Gia hạn, sửa đổi, bổ sung giấy phép
   • Thủ tục đóng cửa mỏ

✅ **Thuế và các khoản thu:**
   • Thuế tài nguyên
   • Tiền cấp quyền khai thác khoáng sản
   • Phí thăm dò khoáng sản

✅ **Xử phạt vi phạm hành chính:**
   • Các hành vi vi phạm và mức phạt
   • Biện pháp khắc phục hậu quả
   • Thẩm quyền xử phạt

✅ **Bảo vệ môi trường:**
   • Đánh giá tác động môi trường
   • Kế hoạch bảo vệ môi trường
   • Phục hồi môi trường sau khai thác

🎯 **Lưu ý quan trọng:** 
Tôi chỉ tư vấn về lĩnh vực **Khoáng sản**. Đối với các vấn đề khác, bạn vui lòng tham khảo chuyên gia phù hợp.

**Bạn có thắc mắc gì về pháp luật Khoáng sản không?** 🤔

*Ví dụ câu hỏi:*
- "Thủ tục xin phép khai thác đá như thế nào?"
- "Mức thuế tài nguyên hiện tại?"
- "Vi phạm khai thác khoáng sản bị phạt như thế nào?"
- "Điều kiện cấp Giấy phép thăm dò?"

**Lưu ý:** Để có thông tin chính xác nhất, bạn nên tham khảo trực tiếp tại thuvienphapluat.vn"""

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
        'than', 'quặng', 'kim loại', 'phi kim loại', 'khoáng',
        'luật khoáng sản', 'giấy phép', 'cấp phép', 'thuế tài nguyên',
        'phí thăm dò', 'tiền cấp quyền', 'vi phạm hành chính',
        'bộ tài nguyên', 'sở tài nguyên', 'monre', 'tn&mt',
        'mỏ', 'mỏ đá', 'mỏ cát', 'mỏ than', 'quarry', 'mining'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mineral_keywords)

def should_search_legal_web(message):
    """Kiểm tra có cần tìm kiếm pháp luật trên web"""
    search_indicators = [
        'mới nhất', 'cập nhật', 'hiện hành', 'ban hành', 'sửa đổi',
        'bổ sung', 'thay thế', 'có hiệu lực', 'quy định mới',
        'nghị định', 'thông tư', 'luật', 'pháp luật', 'điều'
    ]
    
    message_lower = message.lower()
    return (is_mineral_related(message) and 
            any(indicator in message_lower for indicator in search_indicators))

def create_enhanced_legal_prompt(user_message, search_results):
    """Tạo prompt với thông tin pháp luật tìm kiếm"""
    if not search_results or not any(r.get('content') for r in search_results):
        return f"""
{user_message}

QUAN TRỌNG: Không tìm thấy thông tin chính xác từ các nguồn pháp luật chính thống. 
Hãy trả lời dựa trên kiến thức có sẵn và LƯU Ý:
1. Ghi rõ đây là thông tin tham khảo, chưa được xác minh từ nguồn chính thống
2. Khuyến nghị người hỏi tham khảo trực tiếp tại thuvienphapluat.vn
3. Nếu là điều khoản cụ thể, đề xuất tìm kiếm trực tiếp trên website chính thống
4. Đưa ra link trực tiếp: https://thuvienphapluat.vn
"""
    
    # Sắp xếp kết quả theo độ tin cậy và priority
    sorted_results = sorted(search_results, 
                          key=lambda x: (x.get('priority', False), x.get('confidence', 0)), 
                          reverse=True)
    
    legal_info = "\n\n=== THÔNG TIN PHÁP LUẬT TÌM KIẾM ===\n"
    high_confidence_found = any(r.get('confidence', 0) > 0.7 for r in sorted_results)
    
    for i, result in enumerate(sorted_results, 1):
        if result.get('content'):
            priority_mark = "⭐ " if result.get('priority') else ""
            confidence = result.get('confidence', 0)
            confidence_mark = f"[Tin cậy: {confidence:.1f}]"
            
            legal_info += f"\n{priority_mark}Nguồn {i} ({result['source']}) {confidence_mark}:\n"
            legal_info += f"Tiêu đề: {result['title']}\n"
            legal_info += f"Nội dung: {result['content'][:600]}...\n"
            
            if result.get('url'):
                legal_info += f"URL: {result['url']}\n"
            legal_info += "---\n"
    
    confidence_instruction = ""
    if high_confidence_found:
        confidence_instruction = "CÓ NGUỒN TIN CẬY CAO - Hãy ưu tiên các nguồn có độ tin cậy > 0.7"
    else:
        confidence_instruction = "KHÔNG CÓ NGUỒN TIN CẬY CAO - Hãy thận trọng khi trích dẫn và ghi rõ cần xác minh"
    
    legal_info += f"""
{confidence_instruction}

HƯỚNG DẪN TRÍCH DẪN CHÍNH XÁC:
1. Ưu tiên nguồn có ⭐ (nguồn chính thống)
2. Ưu tiên kết quả có độ tin cậy cao (> 0.7)
3. PHẢI trích dẫn cụ thể nếu có: "Theo Điều X khoản Y [Tên luật/nghị định]..."
4. Nếu độ tin cậy thấp: "Thông tin tham khảo từ [nguồn], cần xác minh thêm"
5. Luôn khuyến nghị: "Để có thông tin chính xác nhất, vui lòng tham khảo tại thuvienphapluat.vn"

=== KẾT THÚC THÔNG TIN PHÁP LUẬT ===

"""
    
    return legal_info + f"Câu hỏi: {user_message}"

def render_ui_styles():
    """Render CSS styles"""
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True
    )

def render_header():
    """Render header"""
    st.markdown(
        """
        <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #2E7D32, #4CAF50); border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">⚖️ Trợ lý Pháp chế Khoáng sản</h1>
            <p style="color: #E8F5E8; margin: 5px 0 0 0;">Chuyên gia tư vấn Quản lý Nhà nước về Khoáng sản tại Việt Nam</p>
            <p style="color: #E8F5E8; margin: 5px 0 0 0; font-size: 12px;">🆕 Clean Code • GPT-4o-mini • Confidence Scoring • Chính xác pháp luật</p>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_sidebar(token_counter, legal_searcher):
    """Render sidebar"""
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt hệ thống")
        
        # Toggle web search
        legal_search_enabled = st.toggle("🔍 Tìm kiếm pháp luật online", value=True)
        
        # Model selection
        model_options = ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        model_info = {
            "gpt-4o-mini": "💰 Rẻ nhất ($0.15/$0.6 per 1K tokens) 🆕",
            "gpt-3.5-turbo": "⚖️ Cân bằng ($1.5/$2 per 1K tokens)", 
            "gpt-4": "🧠 Thông minh ($30/$60 per 1K tokens)",
            "gpt-4-turbo-preview": "🚀 Nhanh ($10/$30 per 1K tokens)"
        }
        
        default_model = get_default_model()
        default_index = model_options.index(default_model) if default_model in model_options else 0
        
        selected_model = st.selectbox("🤖 Chọn model AI:", model_options, index=default_index)
        st.caption(model_info[selected_model])
        
        # Temperature setting
        temperature = st.slider("🌡️ Độ sáng tạo:", 0.0, 1.0, 0.3, 0.1)
        
        st.markdown("---")
        
        # Stats display
        st.markdown("### 📊 Thống kê sử dụng")
        
        try:
            stats = token_counter.get_stats()
            
            # Token stats
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("🎯 Tổng Token", f"{stats['total_tokens']:,}")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📥 Input", f"{stats['input_tokens']:,}")
            with col2:
                st.metric("📤 Output", f"{stats['output_tokens']:,}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Cost stats
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("💰 Chi phí (USD)", f"${stats['total_cost_usd']:.4f}")
            st.metric("💸 Chi phí (VND)", f"{stats['total_cost_vnd']:,.0f}đ")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Session stats
            st.markdown('<div class="stats-box">', unsafe_allow_html=True)
            st.metric("📞 Số lượt hỏi", stats['requests'])
            duration = str(stats['session_duration']).split('.')[0]
            st.metric("⏱️ Thời gian", duration)
            st.markdown('</div>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Lỗi hiển thị stats: {e}")
        
        # Control buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset stats", use_container_width=True):
                SessionStateManager.reset_token_stats()
                st.rerun()
        
        with col2:
            if st.button("🗑️ Xóa chat", use_container_width=True):
                SessionStateManager.reset_chat()
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📚 Lĩnh vực chuyên môn")
        st.markdown("• Luật Khoáng sản và Luật Địa chất Khoáng sản")
        st.markdown("• Nghị định hướng dẫn thi hành")
        st.markdown("• Thông tư Bộ TN&MT")
        st.markdown("• Thủ tục cấp phép")
        st.markdown("• Thuế, phí khoáng sản")
        st.markdown("• Xử phạt vi phạm")
        st.markdown("• Bảo vệ môi trường")
        
        st.markdown("---")
        st.markdown("### 🎯 Đảm bảo chính xác")
        st.success("✅ Không có thông tin pháp luật cứng trong code")
        st.success("✅ Tìm kiếm nguồn chính thống")
        st.success("✅ Confidence scoring")
        st.info("💡 Tất cả thông tin pháp luật đều được tìm kiếm real-time")
    
    return legal_search_enabled, selected_model, temperature

def render_chat_history():
    """Render chat history"""
    SessionStateManager.init_messages()
    
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            st.markdown(f'<div class="assistant-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)
        elif message["role"] == "user":
            st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)

def process_user_input(prompt, legal_search_enabled, selected_model, temperature, 
                      token_counter, legal_searcher, client):
    """Xử lý input từ user"""
    
    # Kiểm tra câu hỏi có liên quan đến khoáng sản không
    if not is_mineral_related(prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        # Phản hồi từ chối lịch sự
        polite_refusal = """Xin lỗi, tôi là trợ lý chuyên về **pháp luật khoáng sản** tại Việt Nam. 

Tôi chỉ có thể tư vấn về các vấn đề liên quan đến:
- 🏔️ Luật Khoáng sản và văn bản hướng dẫn
- ⚖️ Thủ tục cấp phép thăm dò, khai thác
- 💰 Thuế, phí liên quan đến khoáng sản  
- 🌱 Bảo vệ môi trường trong hoạt động khoáng sản
- ⚠️ Xử phạt vi phạm hành chính

Bạn có thể hỏi tôi về những vấn đề này không? Ví dụ:
- "Thủ tục xin phép khai thác đá như thế nào?"
- "Mức thuế tài nguyên hiện tại ra sao?"
- "Vi phạm trong khai thác khoáng sản bị phạt như thế nào?"

Tôi sẵn sàng hỗ trợ bạn! 😊"""
        
        st.session_state.messages.append({"role": "assistant", "content": polite_refusal})
        st.markdown(f'<div class="assistant-message">{polite_refusal}</div>', 
                   unsafe_allow_html=True)
        return
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
    
    # Process response
    with st.spinner("🤔 Đang phân tích câu hỏi pháp luật..."):
        # Search for legal information
        search_results = []
        final_prompt = prompt
        
        if legal_search_enabled and should_search_legal_web(prompt):
            with st.status("🔍 Đang tìm kiếm văn bản pháp luật chính xác...", expanded=False) as status:
                search_results = legal_searcher.search(prompt, max_results=3)
                
                if search_results and any(r.get('content') for r in search_results):
                    # Đếm nguồn ưu tiên và độ tin cậy cao
                    priority_count = sum(1 for r in search_results if r.get('priority'))
                    high_confidence_count = sum(1 for r in search_results if r.get('confidence', 0) > 0.7)
                    
                    if high_confidence_count > 0:
                        st.success(f"✅ Tìm thấy {len(search_results)} kết quả ({priority_count} nguồn ưu tiên, {high_confidence_count} tin cậy cao)")
                    else:
                        st.warning(f"⚠️ Tìm thấy {len(search_results)} kết quả ({priority_count} nguồn ưu tiên) - Độ tin cậy chưa cao")
                    
                    # Hiển thị kết quả với confidence scores
                    for i, result in enumerate(search_results, 1):
                        if result.get('content'):
                            priority_mark = "⭐ " if result.get('priority') else ""
                            confidence = result.get('confidence', 0)
                            confidence_color = "🟢" if confidence > 0.7 else "🟡" if confidence > 0.4 else "🔴"
                            
                            st.write(f"**{priority_mark}{i}. {result['source']}** {confidence_color} [{confidence:.2f}]: {result['title'][:50]}...")
                    
                    final_prompt = create_enhanced_legal_prompt(prompt, search_results)
                    status.update(label="✅ Hoàn tất tìm kiếm pháp luật chính xác", state="complete", expanded=False)
                else:
                    st.warning("⚠️ Không tìm thấy văn bản pháp luật liên quan - Sẽ trả lời từ kiến thức có sẵn")
                    status.update(label="⚠️ Không tìm thấy văn bản liên quan", state="complete", expanded=False)
        
        # Count input tokens
        messages_for_api = [
            msg for msg in st.session_state.messages[:-1] 
            if msg["role"] != "system" or msg == st.session_state.messages[0]
        ]
        messages_for_api.append({"role": "user", "content": final_prompt})
        
        input_text = "\n".join([msg["content"] for msg in messages_for_api])
        input_tokens = token_counter.count_tokens(input_text, selected_model)
        
        # Generate AI response
        try:
            response = ""
            
            stream = client.chat.completions.create(
                model=selected_model,
                messages=messages_for_api,
                stream=True,
                temperature=temperature,
                max_tokens=2000
            )
            
            # Container cho response
            response_container = st.empty()
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    response += chunk.choices[0].delta.content
                    # Update response hiển thị với style
                    response_container.markdown(
                        f'<div class="assistant-message">{response}▌</div>', 
                        unsafe_allow_html=True
                    )
            
            # Final response
            response_container.markdown(
                f'<div class="assistant-message">{response}</div>', 
                unsafe_allow_html=True
            )
            
            # Count output tokens và update stats
            output_tokens = token_counter.count_tokens(response, selected_model)
            token_counter.update_stats(input_tokens, output_tokens, selected_model)
            
            # Hiển thị stats của request này
            with st.expander("📊 Thống kê request này"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Input tokens", f"{input_tokens:,}")
                with col2:
                    st.metric("Output tokens", f"{output_tokens:,}")
                with col3:
                    cost = token_counter.calculate_cost(input_tokens, output_tokens, selected_model)
                    st.metric("Chi phí", f"${cost:.4f}")
            
        except Exception as e:
            error_msg = f"❌ Lỗi hệ thống: {str(e)}"
            st.markdown(f'<div class="assistant-message">{error_msg}</div>', 
                       unsafe_allow_html=True)
            response = error_msg
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})

def main():
    """Hàm chính"""
    
    # Khởi tạo session state
    SessionStateManager.init_token_stats()
    SessionStateManager.init_messages()
    
    # Khởi tạo các components
    token_counter = TokenCounter()
    legal_searcher = LegalSearchEngine()
    
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
    
    # Render UI
    render_ui_styles()
    render_header()
    
    # Render sidebar và lấy settings
    legal_search_enabled, selected_model, temperature = render_sidebar(token_counter, legal_searcher)
    
    # Render chat history
    render_chat_history()
    
    # Chat input
    if prompt := st.chat_input("Nhập câu hỏi về pháp luật khoáng sản..."):
        process_user_input(prompt, legal_search_enabled, selected_model, temperature, 
                          token_counter, legal_searcher, client)

if __name__ == "__main__":
    main()