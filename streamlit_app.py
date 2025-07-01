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
    page_title="🏔️ Trợ lý Pháp chế Khoáng sản Việt Nam",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Pricing cho các models OpenAI (USD per 1K tokens)
MODEL_PRICING = {
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03}
}

class TokenCounter:
    """Lớp đếm token và tính chi phí"""
    
    def __init__(self):
        self.reset_stats()
    
    def reset_stats(self):
        """Reset thống kê về 0"""
        if "token_stats" not in st.session_state:
            st.session_state.token_stats = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "session_start": datetime.now(),
                "request_count": 0
            }
    
    def count_tokens(self, text, model="gpt-3.5-turbo"):
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
            model = "gpt-3.5-turbo"  # Default fallback
        
        pricing = MODEL_PRICING[model]
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
    
    def update_stats(self, input_tokens, output_tokens, model):
        """Cập nhật thống kê"""
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        
        st.session_state.token_stats["total_input_tokens"] += input_tokens
        st.session_state.token_stats["total_output_tokens"] += output_tokens
        st.session_state.token_stats["total_cost"] += cost
        st.session_state.token_stats["request_count"] += 1
    
    def get_stats_display(self):
        """Lấy thống kê để hiển thị"""
        stats = st.session_state.token_stats
        total_tokens = stats["total_input_tokens"] + stats["total_output_tokens"]
        
        return {
            "total_tokens": total_tokens,
            "input_tokens": stats["total_input_tokens"],
            "output_tokens": stats["total_output_tokens"],
            "total_cost_usd": stats["total_cost"],
            "total_cost_vnd": stats["total_cost"] * 24000,  # Estimate VND rate
            "requests": stats["request_count"],
            "session_duration": datetime.now() - stats["session_start"]
        }

# Khởi tạo token counter
@st.cache_resource
def get_token_counter():
    return TokenCounter()

token_counter = get_token_counter()

# Hàm đọc nội dung từ file văn bản với fallback cho chuyên ngành khoáng sản
def rfile(name_file):
    try:
        with open(name_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        # Fallback content chuyên biệt cho khoáng sản
        fallback_content = {
            "00.xinchao.txt": "⚖️ Trợ lý Pháp chế Khoáng sản Việt Nam",
            "01.system_trainning.txt": """Bạn là chuyên gia pháp chế về quản lý nhà nước trong lĩnh vực khoáng sản tại Việt Nam. Bạn có kiến thức sâu rộng về:

🏔️ LĨNH VỰC CHUYÊN MÔN:
- Luật Khoáng sản 2017 và các văn bản hướng dẫn thi hành
- Nghị định về quản lý hoạt động khoáng sản
- Thông tư của Bộ Tài nguyên và Môi trường
- Quy định về thăm dò, khai thác khoáng sản
- Cấp phép hoạt động khoáng sản
- Thuế, phí liên quan đến khoáng sản
- Bảo vệ môi trường trong hoạt động khoáng sản
- Xử phạt vi phạm hành chính trong lĩnh vực khoáng sản

⚖️ NGUYÊN TẮC LÀM VIỆC:
1. Chỉ tập trung vào các vấn đề liên quan đến khoáng sản ở Việt Nam
2. Đưa ra thông tin chính xác, dẫn chiếu cụ thể điều khoản pháp luật
3. Giải thích rõ ràng, dễ hiểu cho cả chuyên gia và người dân
4. Khi tìm kiếm web, ưu tiên nguồn chính thống: portal.gov.vn, monre.gov.vn, thuvienphapluat.vn
5. Từ chối trả lời các câu hỏi không liên quan đến khoáng sản

🎯 CÁCH TRÍCH DẪN:
- Luôn ghi rõ tên văn bản pháp luật, điều, khoản cụ thể
- Ví dụ: "Theo Điều 15 Luật Khoáng sản 2017..."
- Khi có thông tin web: "Dựa theo thông tin từ [nguồn chính thống]..."

QUAN TRỌNG: Chỉ trả lời các câu hỏi về khoáng sản. Nếu câu hỏi không liên quan, hãy lịch sự chuyển hướng về lĩnh vực chuyên môn.""",
            
            "02.assistant.txt": """Xin chào! ⚖️ 

Tôi là Trợ lý Pháp chế chuyên về **Quản lý Nhà nước trong lĩnh vực Khoáng sản tại Việt Nam**.

🏔️ **Tôi có thể hỗ trợ bạn về:**

✅ **Pháp luật Khoáng sản:**
   • Luật Khoáng sản 2017 và văn bản hướng dẫn
   • Nghị định, Thông tư của Bộ TN&MT
   • Quy định về thăm dò, khai thác

✅ **Thủ tục hành chính:**
   • Cấp giấy phép thăm dò, khai thác
   • Hồ sơ, quy trình xin phép
   • Thời hạn, điều kiện cấp phép

✅ **Thuế, phí Khoáng sản:**
   • Thuế tài nguyên
   • Phí thăm dò, khai thác
   • Tiền cấp quyền khai thác

✅ **Xử phạt vi phạm:**
   • Nghị định xử phạt vi phạm hành chính
   • Mức phạt, biện pháp khắc phục

✅ **Bảo vệ môi trường:**
   • Đánh giá tác động môi trường
   • Phục hồi môi trường sau khai thác

**🎯 Lưu ý:** Tôi chỉ tư vấn về lĩnh vực Khoáng sản. Đối với các vấn đề khác, bạn vui lòng tham khảo chuyên gia phù hợp.

**Bạn có thắc mắc gì về pháp luật Khoáng sản không?** 🤔""",
            
            "module_chatgpt.txt": "gpt-3.5-turbo"
        }
        return fallback_content.get(name_file, f"Nội dung mặc định cho {name_file}")

# Lớp tìm kiếm pháp luật nâng cao
class AdvancedLegalSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Patterns để detect cấu trúc pháp luật
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
            # Phân tích query để xác định loại tìm kiếm
            search_type = self._analyze_query(query)
            
            results = []
            
            if search_type == 'specific_article':
                # Tìm kiếm điều khoản cụ thể
                results = self._search_specific_article(query, max_results)
            elif search_type == 'law_content':
                # Tìm kiếm nội dung pháp luật tổng quát
                results = self._search_law_content(query, max_results)
            else:
                # Tìm kiếm chung
                results = self._search_general_legal(query, max_results)
            
            # Nếu không tìm thấy, thử fallback search
            if not results:
                results = self._fallback_search(query, max_results)
            
            return results[:max_results]
            
        except Exception as e:
            st.error(f"Lỗi tìm kiếm pháp luật: {str(e)}")
            return self._get_error_result(query)
    
    def _analyze_query(self, query):
        """Phân tích query để xác định loại tìm kiếm"""
        query_lower = query.lower()
        
        # Kiểm tra tìm kiếm điều khoản cụ thể
        if re.search(r'điều\s+\d+', query_lower):
            return 'specific_article'
        
        # Kiểm tra tìm kiếm nội dung luật
        if any(keyword in query_lower for keyword in ['luật', 'nghị định', 'thông tư']):
            return 'law_content'
        
        return 'general'
    
    def _search_specific_article(self, query, max_results):
        """Tìm kiếm điều khoản cụ thể trong pháp luật"""
        results = []
        
        try:
            # Trích xuất thông tin từ query
            article_match = re.search(r'điều\s+(\d+)', query.lower())
            law_match = re.search(r'luật\s+([^0-9]*?)(?:\s*năm\s*(\d{4})|\s*số\s*([0-9/A-Z]+))?', query.lower())
            
            if article_match:
                article_num = article_match.group(1)
                
                if law_match:
                    law_name = law_match.group(1).strip()
                    year = law_match.group(2) if law_match.group(2) else None
                    law_number = law_match.group(3) if law_match.group(3) else None
                    
                    # Tìm kiếm trên thuvienphapluat.vn
                    results.extend(self._search_thuvienphapluat(
                        f"điều {article_num} {law_name}", max_results
                    ))
                    
                    # Tìm kiếm trên nguồn khác
                    results.extend(self._search_legal_portals(
                        f"điều {article_num} luật {law_name}", max_results - len(results)
                    ))
        
        except Exception as e:
            pass
        
        return results
    
    def _search_thuvienphapluat(self, query, max_results):
        """Tìm kiếm trên thuvienphapluat.vn với độ chính xác cao"""
        results = []
        
        try:
            # Tối ưu query cho thuvienphapluat.vn
            optimized_query = f"site:thuvienphapluat.vn {query}"
            
            # Sử dụng DuckDuckGo để search
            params = {
                'q': optimized_query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = self.session.get("https://api.duckduckgo.com/", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Abstract answer
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
                
                # Related topics
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
        
        except Exception as e:
            pass
        
        return results
    
    def _search_legal_portals(self, query, max_results):
        """Tìm kiếm trên các portal pháp luật khác"""
        results = []
        
        portals = [
            ('portal.gov.vn', 'Cổng thông tin điện tử Chính phủ'),
            ('monre.gov.vn', 'Bộ Tài nguyên và Môi trường'),
            ('moj.gov.vn', 'Bộ Tư pháp')
        ]
        
        for domain, source_name in portals:
            try:
                portal_results = self._search_domain(query, domain, source_name, max_results // len(portals))
                results.extend(portal_results)
                
                if len(results) >= max_results:
                    break
                    
            except:
                continue
        
        return results
    
    def _search_domain(self, query, domain, source_name, max_results):
        """Tìm kiếm trên domain cụ thể"""
        results = []
        
        try:
            # DuckDuckGo search với site filter
            params = {
                'q': f"site:{domain} {query}",
                'format': 'json',
                'no_html': '1'
            }
            
            response = self.session.get("https://api.duckduckgo.com/", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Abstract answer
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
                
                # Related topics
                for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                    if isinstance(topic, dict) and topic.get('Text'):
                        confidence = self._calculate_confidence(query, topic.get('Text', ''), topic.get('Text', ''))
                        results.append({
                            'title': topic.get('Text', '')[:80] + '...',
                            'content': topic.get('Text', ''),
                            'url': topic.get('FirstURL', ''),
                            'source': source_name,
                            'priority': True,
                            'confidence': confidence
                        })
        
        except Exception as e:
            pass
        
        return results
    
    def _search_law_content(self, query, max_results):
        """Tìm kiếm nội dung pháp luật tổng quát"""
        results = []
        
        # Tìm kiếm với keywords được tối ưu
        optimized_query = self._optimize_legal_query(query)
        
        # Tìm trên thuvienphapluat.vn
        results.extend(self._search_thuvienphapluat(optimized_query, max_results))
        
        # Tìm trên các portal khác
        if len(results) < max_results:
            results.extend(self._search_legal_portals(optimized_query, max_results - len(results)))
        
        return results
    
    def _search_general_legal(self, query, max_results):
        """Tìm kiếm pháp luật chung"""
        enhanced_query = f"{query} khoáng sản Việt Nam pháp luật"
        
        results = []
        
        # DuckDuckGo search cơ bản
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
        
        except Exception as e:
            pass
        
        return results
    
    def _fallback_search(self, query, max_results):
        """Tìm kiếm dự phòng"""
        return [{
            'title': 'Không tìm thấy thông tin cụ thể',
            'content': f'Không thể tìm thấy thông tin chính xác cho "{query}". Tôi sẽ trả lời dựa trên kiến thức pháp luật có sẵn và khuyến nghị bạn tham khảo trực tiếp tại thuvienphapluat.vn hoặc liên hệ cơ quan có thẩm quyền.',
            'url': 'https://thuvienphapluat.vn',
            'source': 'Hệ thống',
            'priority': False,
            'confidence': 0.1
        }]
    
    def _get_error_result(self, query):
        """Kết quả khi có lỗi"""
        return [{
            'title': 'Lỗi tìm kiếm pháp luật',
            'content': f'Đã xảy ra lỗi khi tìm kiếm thông tin cho "{query}". Vui lòng thử lại sau hoặc tham khảo trực tiếp tại các nguồn chính thống.',
            'url': '',
            'source': 'Hệ thống',
            'priority': False,
            'confidence': 0.0
        }]
    
    def _is_legal_content(self, title, content):
        """Kiểm tra xem có phải nội dung pháp luật không"""
        legal_indicators = [
            'luật', 'nghị định', 'thông tư', 'quyết định', 'điều',
            'khoản', 'điểm', 'chương', 'mục', 'bộ luật'
        ]
        
        text = (title + ' ' + content).lower()
        return any(indicator in text for indicator in legal_indicators)
    
    def _calculate_confidence(self, query, title, content):
        """Tính độ tin cậy của kết quả"""
        confidence = 0.3  # Base confidence
        
        query_words = set(query.lower().split())
        content_words = set((title + ' ' + content).lower().split())
        
        # Intersection of words
        common_words = query_words.intersection(content_words)
        if len(query_words) > 0:
            word_match_ratio = len(common_words) / len(query_words)
            confidence += word_match_ratio * 0.4
        
        # Legal structure indicators
        if re.search(r'điều\s+\d+', content.lower()):
            confidence += 0.2
        
        if re.search(r'khoản\s+\d+', content.lower()):
            confidence += 0.1
        
        if any(domain in content.lower() for domain in ['thuvienphapluat', 'gov.vn']):
            confidence += 0.2
        
        # Specific legal document indicators
        if re.search(r'luật\s+khoáng sản', content.lower()):
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _optimize_legal_query(self, query):
        """Tối ưu query cho tìm kiếm pháp luật"""
        # Thêm các từ khóa pháp luật liên quan
        legal_terms = ['văn bản', 'quy định', 'hướng dẫn', 'pháp luật']
        
        # Nếu query chưa có từ khóa pháp luật, thêm vào
        query_lower = query.lower()
        if not any(term in query_lower for term in legal_terms):
            query += ' quy định pháp luật'
        
        return query

# Khởi tạo advanced legal searcher
@st.cache_resource
def get_advanced_legal_searcher():
    return AdvancedLegalSearcher()

advanced_legal_searcher = get_advanced_legal_searcher()

def is_mineral_related(message):
    """Kiểm tra câu hỏi có liên quan đến khoáng sản không"""
    mineral_keywords = [
        # Từ khóa chính
        'khoáng sản', 'khai thác', 'thăm dò', 'đá', 'cát', 'sỏi',
        'than', 'quặng', 'kim loại', 'phi kim loại', 'khoáng',
        
        # Pháp luật
        'luật khoáng sản', 'giấy phép', 'cấp phép', 'thuế tài nguyên',
        'phí thăm dò', 'tiền cấp quyền', 'vi phạm hành chính',
        
        # Cơ quan
        'bộ tài nguyên', 'sở tài nguyên', 'monre', 'tn&mt',
        
        # Hoạt động
        'mỏ', 'mỏ đá', 'mỏ cát', 'mỏ than', 'quarry', 'mining'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mineral_keywords)

def should_search_legal_web(message):
    """Kiểm tra có cần tìm kiếm pháp luật trên web"""
    search_indicators = [
        'mới nhất', 'cập nhật', 'hiện hành', 'ban hành', 'sửa đổi',
        'bổ sung', 'thay thế', 'có hiệu lực', 'quy định mới',
        'nghị định', 'thông tư', 'luật', 'pháp luật'
    ]
    
    message_lower = message.lower()
    return (is_mineral_related(message) and 
            any(indicator in message_lower for indicator in search_indicators))

def create_enhanced_legal_prompt(user_message, search_results):
    """Tạo prompt nâng cao với kết quả tìm kiếm được sắp xếp theo độ tin cậy"""
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
    
    high_confidence_found = False
    
    for i, result in enumerate(sorted_results, 1):
        if result.get('content'):
            priority_mark = "⭐ " if result.get('priority') else ""
            confidence = result.get('confidence', 0)
            confidence_mark = f"[Tin cậy: {confidence:.1f}]" if confidence > 0 else ""
            
            if confidence > 0.7:
                high_confidence_found = True
            
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
3. PHẢI trích dẫn cụ thể: "Theo Điều X khoản Y Luật/Nghị định số Z..."
4. Nếu độ tin cậy thấp: "Thông tin tham khảo từ [nguồn], cần xác minh thêm"
5. Luôn khuyến nghị: "Để có thông tin chính xác nhất, vui lòng tham khảo tại thuvienphapluat.vn"
6. Nếu là điều khoản cụ thể nhưng không tìm thấy: "Không tìm thấy nội dung chính xác của điều này. Khuyến nghị tìm kiếm trực tiếp trên thuvienphapluat.vn"

=== KẾT THÚC THÔNG TIN PHÁP LUẬT ===

"""
    
    return legal_info + f"Câu hỏi: {user_message}"

# Main UI
def main():
    # Custom CSS cho giao diện bot trái, user phải
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
        
        .cost-highlight {
            color: #d32f2f;
            font-weight: bold;
        }
        
        .token-highlight {
            color: #1976d2;
            font-weight: bold;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Header
    st.markdown(
        """
        <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #2E7D32, #4CAF50); border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">⚖️ Trợ lý Pháp chế Khoáng sản</h1>
            <p style="color: #E8F5E8; margin: 5px 0 0 0;">Chuyên gia tư vấn Quản lý Nhà nước về Khoáng sản tại Việt Nam</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Sidebar với thống kê chi tiết
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt hệ thống")
        
        # Toggle web search cho pháp luật
        legal_search_enabled = st.toggle("🔍 Tìm kiếm pháp luật online", value=True)
        
        # Model selection
        model_options = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        selected_model = st.selectbox("🤖 Chọn model AI:", model_options, index=0)
        
        # Temperature setting
        temperature = st.slider("🌡️ Độ sáng tạo (Temperature):", 0.0, 1.0, 0.3, 0.1,
                               help="0.0 = Chính xác, 1.0 = Sáng tạo")
        
        st.markdown("---")
        
        # Thống kê token và chi phí
        st.markdown("### 📊 Thống kê sử dụng")
        
        stats = token_counter.get_stats_display()
        
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
        
        # Reset button
        if st.button("🔄 Reset thống kê", use_container_width=True):
            token_counter.reset_stats()
            st.rerun()
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
            st.session_state.messages = [
                {"role": "system", "content": rfile("01.system_trainning.txt")},
                {"role": "assistant", "content": rfile("02.assistant.txt")}
            ]
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📚 Lĩnh vực chuyên môn")
        st.markdown("• Luật Khoáng sản 2017")
        st.markdown("• Nghị định hướng dẫn")
        st.markdown("• Thông tư Bộ TN&MT")
        st.markdown("• Thủ tục cấp phép")
        st.markdown("• Thuế, phí khoáng sản")
        st.markdown("• Xử phạt vi phạm")
        st.markdown("• Bảo vệ môi trường")
    
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
    
    # Display chat history với style tùy chỉnh
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            st.markdown(f'<div class="assistant-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)
        elif message["role"] == "user":
            st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                       unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Nhập câu hỏi về pháp luật khoáng sản..."):
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
            # Check if legal web search is needed
            search_results = []
            final_prompt = prompt
            
            if legal_search_enabled and should_search_legal_web(prompt):
                with st.status("🔍 Đang tìm kiếm văn bản pháp luật chính xác...", expanded=False) as status:
                    search_results = advanced_legal_searcher.search(prompt, max_results=3)
                    
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
            
            # Đếm input tokens
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
                
                # Đếm output tokens và cập nhật stats
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

if __name__ == "__main__":
    main()