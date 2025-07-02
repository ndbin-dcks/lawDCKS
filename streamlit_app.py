import streamlit as st
from openai import OpenAI
import requests
import json
from datetime import datetime
import re
from urllib.parse import quote
import time
import os
import traceback

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
            {"role": "system", "content": get_strict_system_prompt()},
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
        
        if model not in MODEL_PRICING:
            model = "gpt-4o-mini"
        
        pricing = MODEL_PRICING[model]
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        
        st.session_state.token_stats["total_input_tokens"] += input_tokens
        st.session_state.token_stats["total_output_tokens"] += output_tokens
        st.session_state.token_stats["total_cost"] += cost
        st.session_state.token_stats["request_count"] += 1
        
    except Exception as e:
        st.error(f"Lỗi cập nhật stats: {e}")

def count_tokens(text):
    """Ước tính số token đơn giản"""
    return len(str(text)) // 4

def get_strict_system_prompt():
    """System prompt nghiêm ngặt ngăn hallucination"""
    try:
        with open("01.system_trainning.txt", "r", encoding="utf-8") as file:
            base_prompt = file.read()
            # Thêm strict instructions vào cuối
            return base_prompt + """

🚫 HƯỚNG DẪN NGHIÊM NGẶT BỔ SUNG:

TUYỆT ĐỐI KHÔNG ĐƯỢC:
1. Bịa đặt số luật, số điều, số khoản nếu không có trong thông tin tìm kiếm
2. Trích dẫn cụ thể các điều khoản pháp luật mà không có nguồn xác thực
3. Đưa ra thông tin chi tiết về nội dung luật nếu không chắc chắn 100%
4. Sử dụng kiến thức cũ về pháp luật mà không có xác nhận từ nguồn hiện tại

CHỈ ĐƯỢC:
1. Trích dẫn thông tin CÓ TRONG kết quả tìm kiếm được cung cấp
2. Đưa ra các nguyên tắc chung về pháp luật khoáng sản
3. Hướng dẫn người hỏi tham khảo nguồn chính thống
4. Nói rõ khi thông tin không đầy đủ hoặc cần kiểm tra thêm

LUÔN ưu tiên an toàn thông tin hơn việc đưa ra câu trả lời chi tiết."""
            
    except FileNotFoundError:
        return """Bạn là chuyên gia pháp chế về quản lý nhà nước trong lĩnh vực khoáng sản tại Việt Nam.

⚖️ NGUYÊN TẮC LÀM VIỆC NGHIÊM NGẶT:

🚫 TUYỆT ĐỐI KHÔNG ĐƯỢC:
1. Bịa đặt số luật, số điều, số khoản nếu không có trong thông tin tìm kiếm
2. Trích dẫn cụ thể các điều khoản pháp luật mà không có nguồn xác thực
3. Đưa ra thông tin chi tiết về nội dung luật nếu không chắc chắn 100%
4. Sử dụng kiến thức cũ về pháp luật mà không có xác nhận từ nguồn hiện tại

✅ CHỈ ĐƯỢC:
1. Trích dẫn thông tin CÓ TRONG kết quả tìm kiếm được cung cấp
2. Đưa ra các nguyên tắc chung về pháp luật khoáng sản
3. Hướng dẫn người hỏi tham khảo nguồn chính thống
4. Nói rõ khi thông tin không đầy đủ hoặc cần kiểm tra thêm

🎯 CÁCH TRẢ LỜI AN TOÀN:
- Khi có thông tin từ search: "Dựa theo thông tin tìm kiếm từ [nguồn]..."
- Khi không chắc chắn: "Thông tin này cần được kiểm tra tại thuvienphapluat.vn"
- Khi thông tin không đủ: "Tôi không có đủ thông tin chính xác để trả lời chi tiết"

QUAN TRỌNG: An toàn thông tin pháp luật quan trọng hơn việc đưa ra câu trả lời chi tiết."""

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
   • Nghị định, Thông tư của Bộ Tài nguyên và Môi trường

✅ **Thủ tục hành chính:**
   • Cấp Giấy phép thăm dò, khai thác khoáng sản
   • Gia hạn, sửa đổi, bổ sung giấy phép
   • Thủ tục đóng cửa mỏ

🎯 **Lưu ý quan trọng:** 
Tôi chỉ tư vấn về lĩnh vực **Khoáng sản**. Để có thông tin chính xác nhất, bạn nên tham khảo trực tiếp tại **thuvienphapluat.vn**.

**Bạn có thắc mắc gì về pháp luật Khoáng sản không?** 🤔"""

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
        'mỏ', 'mỏ đá', 'mỏ cát', 'mỏ than', 'quarry', 'mining',
        'thu hồi giấy phép'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mineral_keywords)

def should_search_web(message):
    """Kiểm tra có cần tìm kiếm web không"""
    search_indicators = [
        'mới nhất', 'cập nhật', 'hiện hành', 'ban hành', 'sửa đổi',
        'bổ sung', 'thay thế', 'có hiệu lực', 'quy định mới',
        'nghị định', 'thông tư', 'luật', 'pháp luật', 'điều',
        'khi nào', 'trường hợp nào', 'điều kiện', 'thu hồi'
    ]
    
    message_lower = message.lower()
    return (is_mineral_related(message) and 
            any(indicator in message_lower for indicator in search_indicators))

# =================== SEARCH FUNCTIONS ===================

def is_high_quality_legal_content(title, content, url=""):
    """Kiểm tra nội dung có phải văn bản pháp luật chất lượng cao không"""
    
    # 1. Kiểm tra nguồn uy tín
    trusted_domains = ['thuvienphapluat.vn', 'monre.gov.vn', 'moj.gov.vn', 'chinhphu.vn']
    is_trusted_source = any(domain in url.lower() for domain in trusted_domains)
    
    # 2. Kiểm tra cấu trúc văn bản pháp luật
    legal_structure_patterns = [
        r'(?:luật|nghị định|thông tư|quyết định)\s+(?:số\s*)?\d+',
        r'điều\s+\d+',
        r'khoản\s+\d+',
        r'chương\s+[ivx\d]+',
        r'mục\s+\d+'
    ]
    
    text = (title + ' ' + content).lower()
    has_legal_structure = sum(1 for pattern in legal_structure_patterns 
                            if re.search(pattern, text)) >= 2
    
    # 3. Kiểm tra từ khóa khoáng sản cụ thể
    mineral_legal_terms = [
        'luật khoáng sản', 'khai thác khoáng sản', 'thăm dò khoáng sản',
        'giấy phép khai thác', 'giấy phép thăm dò', 'thuế tài nguyên',
        'bộ tài nguyên', 'sở tài nguyên', 'thu hồi giấy phép'
    ]
    
    has_mineral_terms = any(term in text for term in mineral_legal_terms)
    
    # 4. Loại bỏ nội dung spam/không phù hợp
    spam_indicators = ['quảng cáo', 'bán hàng', 'tuyển dụng', '404', 'error']
    has_spam = any(spam in text for spam in spam_indicators)
    
    # 5. Kiểm tra độ dài nội dung
    has_sufficient_content = len(content.strip()) > 100
    
    # Tính điểm tổng
    score = 0
    if is_trusted_source: score += 3
    if has_legal_structure: score += 2  
    if has_mineral_terms: score += 2
    if has_sufficient_content: score += 1
    if has_spam: score -= 3
    
    return score >= 4

def calculate_improved_confidence(query, title, content, url=""):
    """Tính confidence score cải tiến với nhiều yếu tố"""
    
    confidence = 0.0
    query_lower = query.lower()
    text_lower = (title + ' ' + content).lower()
    
    # 1. Exact phrase matching (25%)
    if query_lower in text_lower:
        confidence += 0.25
    
    # 2. Word overlap (20%)
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    if len(query_words) > 0:
        overlap_ratio = len(query_words.intersection(text_words)) / len(query_words)
        confidence += overlap_ratio * 0.20
    
    # 3. Legal document indicators (20%)
    legal_patterns = [
        (r'luật\s+khoáng sản', 0.15),
        (r'luật\s+(?:số\s*)?\d+.*khoáng sản', 0.12),
        (r'nghị định\s+(?:số\s*)?\d+.*khoáng sản', 0.10),
        (r'thông tư\s+(?:số\s*)?\d+.*khoáng sản', 0.08),
        (r'điều\s+\d+', 0.05),
        (r'khoản\s+\d+', 0.03)
    ]
    
    for pattern, weight in legal_patterns:
        if re.search(pattern, text_lower):
            confidence += weight
            break  # Chỉ tính pattern có trọng số cao nhất
    
    # 4. Source reliability (20%)
    source_scores = {
        'thuvienphapluat.vn': 0.20,
        'monre.gov.vn': 0.18,
        'chinhphu.vn': 0.15,
        'moj.gov.vn': 0.12,
        'gov.vn': 0.08
    }
    
    for domain, score in source_scores.items():
        if domain in url.lower():
            confidence += score
            break
    
    # 5. Title relevance bonus (10%)
    title_words = set(title.lower().split())
    title_overlap = len(query_words.intersection(title_words)) / len(query_words) if query_words else 0
    confidence += title_overlap * 0.10
    
    # 6. Content quality (5%)
    if len(content) > 200:
        confidence += 0.05
    elif len(content) > 100:
        confidence += 0.025
    
    # Penalties
    if any(spam in text_lower for spam in ['404', 'error', 'không tìm thấy']):
        confidence *= 0.3
    
    return min(confidence, 1.0)

def extract_document_type(title):
    """Trích xuất loại văn bản từ tiêu đề"""
    title_lower = title.lower()
    
    if re.search(r'luật\s+(?:số\s*)?\d+', title_lower):
        return 'Luật'
    elif re.search(r'nghị định\s+(?:số\s*)?\d+', title_lower):
        return 'Nghị định'
    elif re.search(r'thông tư\s+(?:số\s*)?\d+', title_lower):
        return 'Thông tư'
    elif re.search(r'quyết định\s+(?:số\s*)?\d+', title_lower):
        return 'Quyết định'
    else:
        return 'Văn bản'

def remove_duplicate_results(results):
    """Loại bỏ kết quả trùng lặp"""
    unique_results = []
    seen_urls = set()
    seen_titles = set()
    
    for result in results:
        url = result.get('url', '')
        title = result.get('title', '').lower().strip()
        
        # Skip if URL or title already seen
        if url in seen_urls or title in seen_titles:
            continue
            
        # Skip if title too similar to existing ones
        is_duplicate = False
        for seen_title in seen_titles:
            if calculate_string_similarity(title, seen_title) > 0.8:
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_urls.add(url)
            seen_titles.add(title)
            unique_results.append(result)
    
    return unique_results

def calculate_string_similarity(str1, str2):
    """Tính similarity giữa 2 string"""
    if not str1 or not str2:
        return 0.0
    
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0

def advanced_web_search_improved(query, max_results=5):
    """Improved web search với better accuracy"""
    results = []
    
    try:
        # Search strategy 1: Direct thuvienphapluat.vn focus
        search_queries = [
            f'site:thuvienphapluat.vn "{query}" luật khoáng sản',
            f'site:thuvienphapluat.vn khoáng sản "{query}"',
            f'site:monre.gov.vn "{query}" khoáng sản',
            f'"luật khoáng sản" "{query}" site:thuvienphapluat.vn'
        ]
        
        for search_query in search_queries:
            if len(results) >= max_results:
                break
                
            try:
                params = {
                    'q': search_query,
                    'format': 'json',
                    'no_html': '1',
                    'skip_disambig': '1'
                }
                
                response = requests.get("https://api.duckduckgo.com/", 
                                      params=params, timeout=8)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Process Abstract với validation
                    if data.get('Abstract') and len(data['Abstract']) > 50:
                        title = data.get('AbstractText', 'Thông tin pháp luật')
                        content = data.get('Abstract')
                        url = data.get('AbstractURL', '')
                        
                        if is_high_quality_legal_content(title, content, url):
                            confidence = calculate_improved_confidence(query, title, content, url)
                            
                            results.append({
                                'title': title,
                                'content': content,
                                'url': url,
                                'source': 'Thư viện Pháp luật' if 'thuvienphapluat' in url else 'Cơ quan nhà nước',
                                'priority': True,
                                'confidence': confidence,
                                'document_type': extract_document_type(title)
                            })
                    
                    # Process RelatedTopics với strict filtering
                    for topic in data.get('RelatedTopics', []):
                        if len(results) >= max_results:
                            break
                            
                        if isinstance(topic, dict) and topic.get('Text'):
                            title = topic.get('Text', '')[:100]
                            content = topic.get('Text', '')
                            url = topic.get('FirstURL', '')
                            
                            if (is_high_quality_legal_content(title, content, url) and
                                len(content) > 100):
                                
                                confidence = calculate_improved_confidence(query, title, content, url)
                                
                                results.append({
                                    'title': title + '...',
                                    'content': content,
                                    'url': url,
                                    'source': 'Thư viện Pháp luật' if 'thuvienphapluat' in url else 'Tìm kiếm web',
                                    'priority': 'thuvienphapluat' in url,
                                    'confidence': confidence,
                                    'document_type': extract_document_type(title)
                                })
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                continue
    
    except Exception as e:
        st.warning(f"⚠️ Tìm kiếm web gặp lỗi: {e}")
    
    # Remove duplicates và sort by confidence
    unique_results = remove_duplicate_results(results)
    
    # Sort by priority and confidence
    unique_results.sort(
        key=lambda x: (x.get('priority', False), x.get('confidence', 0)), 
        reverse=True
    )
    
    return unique_results[:max_results]

def create_search_summary(search_results):
    """Tạo summary ngắn gọn về search results"""
    summary = ""
    for i, result in enumerate(search_results[:3], 1):
        confidence = result.get('confidence', 0)
        summary += f"{i}. {result['title'][:50]}... (Confidence: {confidence:.2f})\n"
    return summary

def create_safe_enhanced_search_prompt(user_message, search_results):
    """Tạo prompt an toàn ngăn AI hallucination"""
    
    if not search_results:
        return f"""
{user_message}

QUAN TRỌNG: KHÔNG tìm thấy thông tin chính xác từ các nguồn pháp luật chính thống.

HƯỚNG DẪN TRẢ LỜI:
1. TUYỆT ĐỐI KHÔNG được bịa đặt số luật, số điều, số khoản
2. TUYỆT ĐỐI KHÔNG được trích dẫn cụ thể nếu không có trong kết quả search
3. CHỈ được nói về các nguyên tắc chung và khuyến nghị tham khảo nguồn chính thống

Hãy trả lời: "Tôi không tìm thấy thông tin chính xác về vấn đề này từ các nguồn pháp luật chính thống. Để có thông tin chính xác nhất về [vấn đề cụ thể], bạn vui lòng:

1. Tham khảo trực tiếp tại thuvienphapluat.vn
2. Liên hệ Sở Tài nguyên và Môi trường địa phương  
3. Tham khảo văn bản Luật Khoáng sản hiện hành và các nghị định hướng dẫn

Tôi không thể đưa ra thông tin cụ thể về điều khoản pháp luật mà không có nguồn xác thực."
"""
    
    # Kiểm tra chất lượng search results
    high_quality_results = [r for r in search_results if r.get('confidence', 0) > 0.8]
    trusted_results = [r for r in search_results if r.get('priority', False)]
    
    if not high_quality_results and not trusted_results:
        return f"""
{user_message}

CẢNH BÁO: Kết quả tìm kiếm có độ tin cậy thấp.

HƯỚNG DẪN TRẢ LỜI AN TOÀN:
1. KHÔNG được trích dẫn cụ thể số luật, số điều nếu không chắc chắn 100%
2. CHỈ được nói về các nguyên tắc chung
3. PHẢI khuyến nghị kiểm tra tại nguồn chính thống

Kết quả tìm kiếm (ĐỘ TIN CẬY THẤP):
{create_search_summary(search_results)}

Hãy trả lời thận trọng và luôn disclaimer về độ tin cậy thấp.
"""
    
    # Chỉ dùng results có confidence cao
    validated_results = [r for r in search_results if r.get('confidence', 0) > 0.7]
    
    search_info = "\n\n=== THÔNG TIN PHÁP LUẬT ĐÃ KIỂM ĐỊNH ===\n"
    
    for i, result in enumerate(validated_results, 1):
        confidence = result.get('confidence', 0)
        doc_type = result.get('document_type', 'Văn bản')
        
        search_info += f"\nNguồn {i} - {doc_type} [Tin cậy: {confidence:.2f}]:\n"
        search_info += f"Tiêu đề: {result['title']}\n"
        search_info += f"Nội dung: {result['content'][:800]}\n"
        search_info += f"URL: {result.get('url', '')}\n"
        search_info += "---\n"
    
    search_info += f"""
HƯỚNG DẪN TRẢ LỜI NGHIÊM NGẶT:
1. CHỈ được trích dẫn thông tin CÓ TRONG kết quả tìm kiếm trên
2. TUYỆT ĐỐI KHÔNG được bịa đặt số điều, số khoản, tên luật
3. Nếu thông tin không đầy đủ, phải ghi rõ "Thông tin không đầy đủ, cần tham khảo thêm"
4. PHẢI có disclaimer: "Thông tin tham khảo, vui lòng kiểm tra tại thuvienphapluat.vn"
5. Nếu có doubt gì, ưu tiên nói "Không thể xác định chính xác"

=== KẾT THÚC THÔNG TIN ===

Câu hỏi: {user_message}
"""
    
    return search_info

# =================== MAIN APPLICATION ===================

def main():
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
        <p style="color: #E8F5E8; margin: 5px 0 0 0; font-size: 12px;">🛡️ Safe Mode • Debug Enabled • Anti-Hallucination</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt hệ thống")
        
        # Web search toggle
        web_search_enabled = st.toggle("🔍 Tìm kiếm pháp luật online (Debug Mode)", value=True)
        
        # Debug mode toggle
        debug_mode = st.toggle("🐛 Debug Mode (Hiển thị search details)", value=True)
        
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
        
        selected_model = st.selectbox("🤖 Chọn model AI:", model_options, index=default_index)
        st.caption(model_info[selected_model])
        
        # Temperature
        temperature = st.slider("🌡️ Độ sáng tạo:", 0.0, 1.0, 0.3, 0.1)
        
        st.markdown("---")
        
        # Stats
        st.markdown("### 📊 Thống kê sử dụng")
        
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
                        {"role": "system", "content": get_strict_system_prompt()},
                        {"role": "assistant", "content": get_welcome_message()}
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi xóa chat: {e}")
        
        st.markdown("---")
        st.markdown("### 🛡️ Safe Mode Features")
        st.success("✅ Anti-hallucination prompts")
        st.success("✅ Source verification")
        st.success("✅ Confidence scoring")
        st.success("✅ Debug search results")
        st.info("💡 Ngăn AI bịa đặt thông tin pháp luật")
    
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
            
            polite_refusal = """Xin lỗi, tôi là trợ lý chuyên về **pháp luật khoáng sản** tại Việt Nam.

Tôi chỉ có thể tư vấn về các vấn đề liên quan đến:
- 🏔️ Luật Khoáng sản và các văn bản hướng dẫn
- ⚖️ Thủ tục cấp phép thăm dò, khai thác khoáng sản
- 💰 Thuế, phí liên quan đến khoáng sản
- 🌱 Bảo vệ môi trường trong hoạt động khoáng sản
- ⚠️ Xử phạt vi phạm hành chính

Bạn có thể hỏi tôi về những vấn đề này không? Tôi sẵn sàng hỗ trợ bạn! 😊"""
            
            st.session_state.messages.append({"role": "assistant", "content": polite_refusal})
            st.markdown(f'<div class="assistant-message">{polite_refusal}</div>', 
                       unsafe_allow_html=True)
            return
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        # Process response
        with st.spinner("🤔 Đang phân tích câu hỏi pháp luật..."):
            search_results = []
            final_prompt = prompt
            
            # DEBUG/Improved web search if enabled
            if web_search_enabled and should_search_web(prompt):
                with st.status("🔍 Đang tìm kiếm văn bản pháp luật với thuật toán cải tiến...", expanded=debug_mode) as status:
                    
                    if debug_mode:
                        # DEBUG: Hiển thị search process
                        st.write("🔍 **DEBUG: Search Process**")
                        st.write(f"📝 Query: {prompt}")
                        st.write(f"🎯 Is mineral related: {is_mineral_related(prompt)}")
                        st.write(f"🔎 Should search web: {should_search_web(prompt)}")
                    
                    # Perform search với debug info
                    search_results = []
                    try:
                        if debug_mode:
                            st.write("⏳ Đang gọi search function...")
                        search_results = advanced_web_search_improved(prompt)
                        if debug_mode:
                            st.write(f"✅ Search completed. Found {len(search_results)} results")
                    except Exception as e:
                        st.error(f"❌ Search failed: {str(e)}")
                        if debug_mode:
                            st.code(traceback.format_exc())
                    
                    # DEBUG: Hiển thị RAW search results
                    if search_results and debug_mode:
                        st.markdown("### 🔍 **RAW SEARCH RESULTS:**")
                        
                        for i, result in enumerate(search_results, 1):
                            with st.expander(f"Result {i}: {result.get('title', 'No title')[:50]}...", expanded=False):
                                st.json({
                                    "title": result.get('title', ''),
                                    "content": result.get('content', '')[:500] + "..." if len(result.get('content', '')) > 500 else result.get('content', ''),
                                    "url": result.get('url', ''),
                                    "source": result.get('source', ''),
                                    "priority": result.get('priority', False),
                                    "confidence": result.get('confidence', 0),
                                    "document_type": result.get('document_type', 'Unknown')
                                })
                        
                        # Thống kê search results
                        priority_count = sum(1 for r in search_results if r.get('priority'))
                        high_confidence_count = sum(1 for r in search_results if r.get('confidence', 0) > 0.7)
                        very_high_confidence_count = sum(1 for r in search_results if r.get('confidence', 0) > 0.85)
                        avg_confidence = sum(r.get('confidence', 0) for r in search_results) / len(search_results)
                        
                        st.markdown("### 📊 **SEARCH STATISTICS:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Results", len(search_results))
                        with col2:
                            st.metric("Priority Sources ⭐", priority_count)
                        with col3:
                            st.metric("High Confidence (>0.7)", high_confidence_count)
                        with col4:
                            st.metric("Avg Confidence", f"{avg_confidence:.2f}")
                        
                        # Quality assessment
                        if very_high_confidence_count > 0:
                            st.success(f"🎯 **EXCELLENT**: {very_high_confidence_count} very high confidence results")
                        elif high_confidence_count > 0:
                            st.success(f"✅ **GOOD**: {high_confidence_count} high confidence results")
                        elif priority_count > 0:
                            st.warning(f"⚠️ **MEDIUM**: {priority_count} priority sources but low confidence")
                        else:
                            st.error("❌ **POOR**: No high-quality results found")
                    
                    if search_results:
                        # Create safe prompt
                        final_prompt = create_safe_enhanced_search_prompt(prompt, search_results)
                        
                        # DEBUG: Hiển thị final prompt
                        if debug_mode:
                            with st.expander("🤖 **FINAL PROMPT TO AI** (Click to expand)", expanded=False):
                                st.code(final_prompt[:2000] + "..." if len(final_prompt) > 2000 else final_prompt)
                        
                        # Show summary for non-debug mode
                        if not debug_mode:
                            priority_count = sum(1 for r in search_results if r.get('priority'))
                            high_confidence_count = sum(1 for r in search_results if r.get('confidence', 0) > 0.7)
                            very_high_confidence_count = sum(1 for r in search_results if r.get('confidence', 0) > 0.85)
                            
                            if very_high_confidence_count > 0:
                                st.success(f"🎯 Tìm thấy {len(search_results)} kết quả ({very_high_confidence_count} rất tin cậy)")
                            elif high_confidence_count > 0:
                                st.success(f"✅ Tìm thấy {len(search_results)} kết quả ({high_confidence_count} tin cậy cao)")
                            else:
                                st.warning(f"⚠️ Tìm thấy {len(search_results)} kết quả (độ tin cậy thấp)")
                        
                        status.update(label="✅ Search completed with safe mode", state="complete", expanded=False)
                        
                    else:
                        if debug_mode:
                            st.error("❌ **NO SEARCH RESULTS FOUND**")
                            st.markdown("### 🔍 **Possible reasons:**")
                            st.markdown("- API calls failed")
                            st.markdown("- No relevant content found") 
                            st.markdown("- Content filtering too strict")
                            st.markdown("- Network/timeout issues")
                            
                            # Test basic connectivity
                            st.markdown("### 🧪 **Connectivity Test:**")
                            try:
                                test_response = requests.get("https://api.duckduckgo.com/", timeout=5)
                                st.success(f"✅ DuckDuckGo API reachable (Status: {test_response.status_code})")
                            except Exception as e:
                                st.error(f"❌ DuckDuckGo API unreachable: {e}")
                        
                        # Fallback safe response
                        final_prompt = f"""
{prompt}

CRITICAL: Search function failed completely. No results found.
HƯỚNG DẪN TRẢ LỜI AN TOÀN:
1. TUYỆT ĐỐI KHÔNG được bịa đặt thông tin pháp luật
2. Chỉ được nói về nguyên tắc chung
3. PHẢI khuyến nghị tham khảo nguồn chính thống

Hãy trả lời: "Tôi gặp lỗi khi tìm kiếm thông tin pháp luật về vấn đề này. Để có thông tin chính xác nhất, bạn vui lòng:

1. Truy cập trực tiếp thuvienphapluat.vn
2. Tìm kiếm với từ khóa liên quan đến câu hỏi
3. Liên hệ Sở Tài nguyên và Môi trường địa phương
4. Tham khảo Luật Khoáng sản hiện hành

Xin lỗi vì sự bất tiện này."
"""
                        
                        status.update(label="❌ Search failed - using safe fallback", state="error", expanded=False)
            
            else:
                if debug_mode:
                    st.info("🔍 **Search disabled** or query not eligible for web search")
                final_prompt = f"""
{prompt}

QUAN TRỌNG: Không có tìm kiếm web được thực hiện.
HƯỚNG DẪN TRẢ LỜI AN TOÀN:
1. TUYỆT ĐỐI KHÔNG được bịa đặt số luật, số điều, số khoản
2. Chỉ được nói về các nguyên tắc chung về pháp luật khoáng sản
3. PHẢI khuyến nghị tham khảo nguồn chính thống để có thông tin chính xác
"""
            
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
                with st.expander("📊 Thống kê request này"):
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
                error_msg = f"❌ Lỗi hệ thống: {str(e)}"
                st.markdown(f'<div class="assistant-message">{error_msg}</div>', 
                           unsafe_allow_html=True)
                response = error_msg
        
        # Add response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()