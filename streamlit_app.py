import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import quote, urljoin
import time

def improved_legal_search(query, max_results=5):
    """
    Tìm kiếm pháp luật cải tiến với multiple methods và validation
    """
    results = []
    
    # Method 1: Truy cập trực tiếp thuvienphapluat.vn
    results.extend(search_thuvienphapluat_direct(query, max_results//2))
    
    # Method 2: Search trên cổng thông tin Bộ TN&MT
    results.extend(search_monre_portal(query, max_results//2))
    
    # Method 3: Backup với Google Custom Search (nếu cần)
    if len(results) < 2:
        results.extend(search_with_backup_method(query, max_results-len(results)))
    
    # Validate và improve confidence scoring
    validated_results = validate_and_score_results(query, results)
    
    return validated_results[:max_results]

def search_thuvienphapluat_direct(query, max_results=3):
    """
    Tìm kiếm trực tiếp trên thuvienphapluat.vn
    """
    results = []
    
    try:
        # Tạo search URL cho thư viện pháp luật
        search_url = "https://thuvienphapluat.vn/tim-van-ban"
        
        # Cải thiện query terms cho khoáng sản
        mineral_terms = ["khoáng sản", "thăm dò", "khai thác", "Luật Khoáng sản"]
        enhanced_query = f"{query} {' OR '.join(mineral_terms)}"
        
        params = {
            'keyword': enhanced_query,
            'trich_yeu': enhanced_query,
            'type': 1,  # Văn bản pháp luật
            'status': 8  # Còn hiệu lực
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://thuvienphapluat.vn/'
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse kết quả search
            search_items = soup.find_all('div', class_=['search-item', 'document-item'])
            
            for item in search_items[:max_results]:
                try:
                    title_elem = item.find(['h3', 'h4', 'a'], class_=['title', 'doc-title'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get('href') or title_elem.find('a', href=True)
                        
                        # Lấy thêm content
                        content_elem = item.find(['p', 'div'], class_=['summary', 'excerpt', 'content'])
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        # Validate là văn bản khoáng sản
                        if is_mineral_related_document(title, content):
                            confidence = calculate_enhanced_confidence(query, title, content)
                            
                            results.append({
                                'title': title,
                                'content': content,
                                'url': urljoin('https://thuvienphapluat.vn', link) if link else '',
                                'source': 'Thư viện Pháp luật VN',
                                'priority': True,
                                'confidence': confidence,
                                'document_type': extract_document_type(title)
                            })
                
                except Exception as e:
                    continue
                    
        time.sleep(0.5)  # Rate limiting
        
    except Exception as e:
        print(f"Error in direct search: {e}")
    
    return results

def search_monre_portal(query, max_results=2):
    """
    Tìm kiếm trên cổng thông tin Bộ TN&MT
    """
    results = []
    
    try:
        # Search trên portal của Bộ TN&MT
        search_urls = [
            "https://monre.gov.vn/Pages/tim-kiem.aspx",
            "https://monre.gov.vn/vn/Pages/search.aspx"
        ]
        
        for search_url in search_urls:
            try:
                params = {
                    'keyword': f"{query} khoáng sản",
                    'k': f"{query} khoáng sản"
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://monre.gov.vn/'
                }
                
                response = requests.get(search_url, params=params, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Parse kết quả từ portal
                    items = soup.find_all(['div', 'article'], class_=['result-item', 'news-item', 'search-result'])
                    
                    for item in items[:max_results]:
                        try:
                            title = item.find(['h3', 'h4', 'a']).get_text(strip=True)
                            content = item.find(['p', 'div'], class_=['summary', 'excerpt']).get_text(strip=True)
                            link = item.find('a', href=True)['href']
                            
                            if is_mineral_related_document(title, content):
                                confidence = calculate_enhanced_confidence(query, title, content)
                                
                                results.append({
                                    'title': title,
                                    'content': content,
                                    'url': urljoin('https://monre.gov.vn', link),
                                    'source': 'Bộ TN&MT',
                                    'priority': True,
                                    'confidence': confidence,
                                    'document_type': extract_document_type(title)
                                })
                        except:
                            continue
                            
                time.sleep(0.5)
                break  # Nếu thành công, không cần try URL khác
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"Error in MONRE search: {e}")
    
    return results

def search_with_backup_method(query, max_results=2):
    """
    Phương pháp backup sử dụng Google Custom Search hoặc API khác
    """
    results = []
    
    try:
        # Sử dụng Google Custom Search (cần API key)
        # Hoặc search với Bing/Yahoo
        
        search_queries = [
            f"site:thuvienphapluat.vn \"{query}\" khoáng sản",
            f"site:monre.gov.vn \"{query}\" khoáng sản",
            f"\"{query}\" luật khoáng sản Việt Nam filetype:pdf"
        ]
        
        for search_query in search_queries:
            # Implement backup search method here
            # Có thể dùng requests đến search engines khác
            pass
            
    except Exception as e:
        print(f"Error in backup search: {e}")
    
    return results

def is_mineral_related_document(title, content):
    """
    Kiểm tra xem văn bản có liên quan đến khoáng sản không
    """
    mineral_indicators = [
        'khoáng sản', 'thăm dò', 'khai thác', 'mỏ', 'đá', 'cát', 'sỏi',
        'than', 'quặng', 'kim loại', 'phi kim loại', 'tài nguyên khoáng sản',
        'luật khoáng sản', 'nghị định.*khoáng sản', 'thông tư.*khoáng sản',
        'giấy phép.*khai thác', 'giấy phép.*thăm dò'
    ]
    
    text = (title + ' ' + content).lower()
    
    return any(re.search(indicator, text) for indicator in mineral_indicators)

def extract_document_type(title):
    """
    Trích xuất loại văn bản từ tiêu đề
    """
    if re.search(r'luật\s+\d+', title.lower()):
        return 'Luật'
    elif re.search(r'nghị định\s+\d+', title.lower()):
        return 'Nghị định'
    elif re.search(r'thông tư\s+\d+', title.lower()):
        return 'Thông tư'
    elif re.search(r'quyết định\s+\d+', title.lower()):
        return 'Quyết định'
    else:
        return 'Văn bản'

def calculate_enhanced_confidence(query, title, content):
    """
    Tính confidence score cải tiến
    """
    confidence = 0.0
    
    # 1. Exact phrase matching (weight: 0.3)
    query_lower = query.lower()
    text_lower = (title + ' ' + content).lower()
    
    if query_lower in text_lower:
        confidence += 0.3
    
    # 2. Word overlap (weight: 0.2)
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    overlap = len(query_words.intersection(text_words))
    if len(query_words) > 0:
        confidence += (overlap / len(query_words)) * 0.2
    
    # 3. Legal document indicators (weight: 0.2)
    legal_patterns = [
        r'điều\s+\d+',
        r'khoản\s+\d+', 
        r'luật\s+\d+',
        r'nghị định\s+\d+',
        r'thông tư\s+\d+'
    ]
    
    for pattern in legal_patterns:
        if re.search(pattern, text_lower):
            confidence += 0.04  # 0.2 / 5 patterns
    
    # 4. Mineral-specific terms (weight: 0.15)
    mineral_terms = ['khoáng sản', 'thăm dò', 'khai thác', 'mỏ']
    mineral_count = sum(1 for term in mineral_terms if term in text_lower)
    confidence += (mineral_count / len(mineral_terms)) * 0.15
    
    # 5. Title relevance bonus (weight: 0.15)
    if any(word in title.lower() for word in query_lower.split()):
        confidence += 0.15
    
    # 6. Source reliability bonus
    source_bonus = 0.1  # Thêm bonus cho nguồn tin cậy
    confidence += source_bonus
    
    return min(confidence, 1.0)

def validate_and_score_results(query, results):
    """
    Validate kết quả và cập nhật confidence score
    """
    validated_results = []
    
    for result in results:
        # Kiểm tra tính hợp lệ của kết quả
        if validate_legal_document(result):
            # Recalculate confidence với validation
            result['confidence'] = calculate_enhanced_confidence(
                query, result['title'], result['content']
            )
            
            # Thêm validation flags
            result['validated'] = True
            result['validation_score'] = calculate_validation_score(result)
            
            validated_results.append(result)
    
    # Sắp xếp theo confidence và validation score
    validated_results.sort(
        key=lambda x: (x.get('priority', False), x.get('confidence', 0), x.get('validation_score', 0)), 
        reverse=True
    )
    
    return validated_results

def validate_legal_document(result):
    """
    Validate tính hợp lệ của văn bản pháp luật
    """
    title = result['title']
    content = result['content']
    
    # Kiểm tra các criteria validation
    validations = [
        # 1. Có chứa từ khóa pháp luật
        bool(re.search(r'(luật|nghị định|thông tư|quyết định)\s+\d+', title.lower())),
        
        # 2. Có chứa thông tin về khoáng sản
        is_mineral_related_document(title, content),
        
        # 3. Có cấu trúc văn bản pháp luật
        bool(re.search(r'điều\s+\d+|khoản\s+\d+', content.lower())),
        
        # 4. Không phải spam hoặc irrelevant content
        len(content) > 50 and not content.startswith('404') and 'error' not in content.lower()
    ]
    
    # Cần ít nhất 2/4 criteria đạt
    return sum(validations) >= 2

def calculate_validation_score(result):
    """
    Tính điểm validation cho kết quả
    """
    score = 0.0
    
    # Source reliability
    if 'thuvienphapluat' in result.get('url', ''):
        score += 0.4
    elif 'gov.vn' in result.get('url', ''):
        score += 0.3
    
    # Document type
    doc_type = result.get('document_type', '')
    if doc_type in ['Luật', 'Nghị định']:
        score += 0.3
    elif doc_type in ['Thông tư', 'Quyết định']:
        score += 0.2
    
    # Content quality
    content_length = len(result.get('content', ''))
    if content_length > 200:
        score += 0.2
    elif content_length > 100:
        score += 0.1
    
    # URL validity
    if result.get('url') and result['url'].startswith('http'):
        score += 0.1
    
    return min(score, 1.0)

# Example usage
if __name__ == "__main__":
    # Test the improved search
    results = improved_legal_search("thuế tài nguyên khoáng sản")
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Source: {result['source']}")
        print(f"   Validated: {result.get('validated', False)}")
        print(f"   URL: {result['url']}")
        print()