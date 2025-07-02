import streamlit as st
from openai import OpenAI
import sqlite3
import json
from datetime import datetime
import re
import time
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Cấu hình trang
st.set_page_config(
    page_title="⚖️ Trợ lý Pháp chế Khoáng sản Việt Nam",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== CONFIGURATIONS ===================

MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03}
}

@dataclass
class VBPLConfig:
    """Cấu hình cho VBPL integration"""
    vbpl_db_path: str = "vbpl.db"
    model: str = "gpt-4o-mini"
    max_tokens: int = 1500
    temperature: float = 0.1
    max_search_results: int = 5
    domain_focus: str = "khoáng sản"
    prioritize_active_docs: bool = True

# =================== VBPL DATABASE INTEGRATION ===================

class VBPLDatabase:
    """Database manager cho VBPL với Streamlit integration"""
    
    def __init__(self, config: VBPLConfig):
        self.config = config
        self.conn = None
        self.available = False
        self._init_connection()
    
    def _init_connection(self):
        """Initialize database connection"""
        try:
            if not os.path.exists(self.config.vbpl_db_path):
                st.sidebar.warning(f"⚠️ Database file không tồn tại: {self.config.vbpl_db_path}")
                return False
            
            self.conn = sqlite3.connect(self.config.vbpl_db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.available = True
            
            # Analyze database structure
            self._analyze_database()
            return True
            
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi kết nối database: {e}")
            return False
    
    def _analyze_database(self):
        """Phân tích cấu trúc database và hiển thị stats"""
        try:
            cursor = self.conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            st.sidebar.success(f"✅ VBPL Database Online")
            st.sidebar.caption(f"📊 {len(tables)} tables detected")
            
            # Check for expected tables
            expected_tables = ['documents', 'vbpl_content']
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                st.sidebar.warning(f"⚠️ Missing tables: {missing_tables}")
            
            # Analyze document distribution if documents table exists
            if 'documents' in tables:
                cursor.execute("SELECT state, COUNT(*) FROM documents GROUP BY state ORDER BY COUNT(*) DESC")
                status_dist = cursor.fetchall()
                
                with st.sidebar.expander("📊 Database Statistics", expanded=False):
                    total_docs = sum(count for _, count in status_dist)
                    st.metric("Total Documents", f"{total_docs:,}")
                    
                    for status, count in status_dist[:5]:  # Top 5 statuses
                        percentage = (count / total_docs) * 100
                        st.metric(status, f"{count:,} ({percentage:.1f}%)")
            
            # Check vbpl_content table
            if 'vbpl_content' in tables:
                cursor.execute("SELECT COUNT(*) FROM vbpl_content")
                content_count = cursor.fetchone()[0]
                st.sidebar.metric("Legal Content Items", f"{content_count:,}")
                
                # Check domain coverage
                cursor.execute("""
                    SELECT COUNT(*) FROM vbpl_content 
                    WHERE LOWER(element_content) LIKE '%khoáng sản%' 
                    OR LOWER(document_name) LIKE '%khoáng sản%'
                """)
                mineral_count = cursor.fetchone()[0]
                
                if content_count > 0:
                    mineral_percentage = (mineral_count / content_count) * 100
                    st.sidebar.metric("Khoáng sản Content", f"{mineral_count:,} ({mineral_percentage:.1f}%)")
            
        except Exception as e:
            st.sidebar.error(f"❌ Database analysis failed: {e}")
    
    def is_available(self) -> bool:
        """Check if database is available and connected"""
        return self.available and self.conn is not None
    
    def search_domain_specific(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search database với domain-specific filtering cho khoáng sản"""
        if not self.is_available():
            return []
        
        try:
            cursor = self.conn.cursor()
            keywords = self._extract_smart_keywords(query)
            
            if not keywords:
                st.warning("⚠️ Không thể trích xuất từ khóa từ câu hỏi")
                return []
            
            # Display search info
            st.write(f"🔍 **Searching for**: {', '.join(keywords[:3])}")
            
            # Build search query với domain filtering
            search_conditions = []
            params = []
            
            # 1. Domain filtering - KHOÁNG SẢN
            domain_keywords = ['khoáng sản', 'tài nguyên', 'thăm dò', 'khai thác', 'mỏ', 'địa chất']
            domain_condition = " OR ".join([f"LOWER(element_content) LIKE ?" for _ in domain_keywords])
            domain_condition += " OR " + " OR ".join([f"LOWER(document_name) LIKE ?" for _ in domain_keywords])
            
            search_conditions.append(f"({domain_condition})")
            params.extend([f"%{kw}%" for kw in domain_keywords])
            params.extend([f"%{kw}%" for kw in domain_keywords])
            
            # 2. Query-specific keywords
            query_condition = " OR ".join([f"LOWER(element_content) LIKE ?" for _ in keywords])
            query_condition += " OR " + " OR ".join([f"LOWER(element_name) LIKE ?" for _ in keywords])
            
            search_conditions.append(f"({query_condition})")
            params.extend([f"%{kw}%" for kw in keywords])
            params.extend([f"%{kw}%" for kw in keywords])
            
            # 3. Build final query với prioritization
            state_priority = """
                CASE 
                    WHEN LOWER(document_state) LIKE '%còn hiệu lực%' THEN 3
                    WHEN LOWER(document_state) LIKE '%có hiệu lực%' THEN 3  
                    WHEN LOWER(document_state) LIKE '%hết hiệu lực%' THEN 1
                    ELSE 2 
                END
            """
            
            # Element type priority
            element_priority = """
                CASE 
                    WHEN element_type = 'vbpl_section' THEN 3
                    WHEN element_type = 'vbpl_clause' THEN 2
                    WHEN element_type = 'vbpl_point' THEN 1
                    ELSE 0
                END
            """
            
            sql = f"""
            SELECT 
                element_id,
                element_type,
                element_number,
                element_name,
                element_content,
                document_number,
                document_name,
                document_state,
                {state_priority} as status_priority,
                {element_priority} as element_priority,
                LENGTH(element_content) as content_length
            FROM vbpl_content 
            WHERE {' AND '.join(search_conditions)}
            AND element_content IS NOT NULL 
            AND LENGTH(TRIM(element_content)) > 50
            ORDER BY 
                status_priority DESC,
                element_priority DESC,
                content_length DESC,
                element_id
            LIMIT ?
            """
            
            params.append(max_results)
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            st.write(f"📊 **Raw database results**: {len(results)}")
            
            # Process results
            processed_results = []
            for row in results:
                relevance_score = self._calculate_relevance(query, dict(row))
                
                processed_results.append({
                    'element_id': row['element_id'],
                    'element_type': row['element_type'],
                    'element_number': row['element_number'] or '',
                    'element_name': row['element_name'] or '',
                    'element_content': row['element_content'] or '',
                    'document_number': row['document_number'],
                    'document_name': row['document_name'],
                    'document_state': row['document_state'],
                    'is_active': self._is_document_active(row['document_state']),
                    'relevance_score': relevance_score,
                    'status_priority': row['status_priority'],
                    'element_priority': row['element_priority']
                })
            
            # Sort by combined score
            processed_results.sort(
                key=lambda x: (x['is_active'], x['relevance_score'], x['element_priority']), 
                reverse=True
            )
            
            return processed_results
            
        except Exception as e:
            st.error(f"❌ Database search failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            return []
    
    def _extract_smart_keywords(self, query: str) -> List[str]:
        """Extract smart keywords từ query với Vietnamese support"""
        # Vietnamese stop words
        stop_words = {
            'là', 'của', 'và', 'có', 'được', 'theo', 'trong', 'về', 'khi', 'nào', 'gì', 'như', 'thế',
            'với', 'để', 'cho', 'từ', 'tại', 'trên', 'dưới', 'này', 'đó', 'những', 'các', 'một',
            'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín', 'mười'
        }
        
        # Normalize và tokenize
        query_normalized = re.sub(r'[^\w\s]', ' ', query.lower())
        words = [w.strip() for w in query_normalized.split() if w.strip()]
        
        # Filter keywords
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        
        # Add important bigrams for better matching
        bigrams = []
        for i in range(len(words) - 1):
            if (words[i] not in stop_words and words[i+1] not in stop_words 
                and len(words[i]) > 2 and len(words[i+1]) > 2):
                bigrams.append(f"{words[i]} {words[i+1]}")
        
        # Combine và prioritize
        all_keywords = keywords[:4] + bigrams[:2]  # Limit để avoid quá complex
        
        return all_keywords
    
    def _calculate_relevance(self, query: str, content: Dict) -> float:
        """Calculate relevance score cho search result"""
        score = 0.0
        query_lower = query.lower()
        
        # Text fields với weights khác nhau
        text_fields = [
            (content.get('element_content', ''), 0.4),  # Content cao nhất
            (content.get('element_name', ''), 0.25),    # Tên element
            (content.get('document_name', ''), 0.15),   # Tên document  
            (content.get('element_number', ''), 0.1),   # Số điều/khoản
            (content.get('document_number', ''), 0.1)   # Số văn bản
        ]
        
        # Calculate text matching score
        for text, weight in text_fields:
            if text:
                text_lower = text.lower()
                
                # Exact phrase match
                if query_lower in text_lower:
                    score += weight
                
                # Word overlap
                query_words = set(query_lower.split())
                text_words = set(text_lower.split())
                overlap = len(query_words.intersection(text_words))
                if len(query_words) > 0:
                    overlap_ratio = overlap / len(query_words)
                    score += (overlap_ratio * weight * 0.5)
        
        # Bonus for active documents
        if self._is_document_active(content.get('document_state', '')):
            score += 0.15
        
        # Bonus for important element types
        element_type = content.get('element_type', '')
        if element_type == 'vbpl_section':
            score += 0.1
        elif element_type == 'vbpl_clause':
            score += 0.05
        
        # Content length bonus (longer = more detailed)
        content_length = len(content.get('element_content', ''))
        if content_length > 500:
            score += 0.05
        elif content_length > 200:
            score += 0.02
        
        return min(score, 1.0)
    
    def _is_document_active(self, state: str) -> bool:
        """Check if document is currently active"""
        if not state:
            return False
        
        state_lower = state.lower()
        active_indicators = ['còn hiệu lực', 'có hiệu lực', 'hiện hành']
        return any(indicator in state_lower for indicator in active_indicators)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.available = False

class VBPLOpenAIProcessor:
    """OpenAI processor cho VBPL content với professional prompting"""
    
    def __init__(self, openai_client: OpenAI, config: VBPLConfig, db_manager: VBPLDatabase):
        self.client = openai_client
        self.config = config
        self.db_manager = db_manager
    
    def process_legal_query(self, query: str) -> Dict[str, Any]:
        """Process legal query với VBPL database"""
        
        # Step 1: Search database
        with st.status("🔍 Đang tìm kiếm trong cơ sở dữ liệu pháp luật VBPL...", expanded=True) as status:
            
            search_results = self.db_manager.search_domain_specific(query, self.config.max_search_results)
            
            if search_results:
                active_count = sum(1 for r in search_results if r['is_active'])
                inactive_count = len(search_results) - active_count
                
                st.success(f"✅ Tìm thấy {len(search_results)} kết quả chính xác")
                st.info(f"📊 {active_count} văn bản còn hiệu lực, {inactive_count} văn bản hết hiệu lực")
                
                # Display preview of results
                for i, result in enumerate(search_results, 1):
                    status_icon = "✅" if result['is_active'] else "⚠️"
                    st.write(f"**{i}. {status_icon} {result['element_number']}**")
                    if result['element_name']:
                        st.write(f"   📋 {result['element_name'][:80]}...")
                    st.write(f"   📄 {result['document_number']} ({result['document_state']})")
                    st.write(f"   🎯 Score: {result['relevance_score']:.2f}")
                
                status.update(label="✅ Tìm kiếm VBPL hoàn tất", state="complete")
            else:
                st.warning("⚠️ Không tìm thấy kết quả phù hợp trong database VBPL")
                status.update(label="⚠️ Không tìm thấy kết quả", state="complete")
        
        # Step 2: Generate response
        if search_results:
            return self._generate_response_with_sources(query, search_results)
        else:
            return self._generate_fallback_response(query)
    
    def _generate_response_with_sources(self, query: str, search_results: List[Dict]) -> Dict[str, Any]:
        """Generate response với database sources"""
        
        # Create context từ search results
        context = self._create_structured_context(search_results)
        
        # Show context preview
        with st.expander("📄 Context được gửi đến AI (Click để xem)", expanded=False):
            st.code(context[:1500] + "..." if len(context) > 1500 else context)
        
        # Call OpenAI
        try:
            response = self._call_openai_with_vbpl_context(query, context, search_results)
            
            return {
                'response': response,
                'sources': search_results,
                'active_sources': sum(1 for r in search_results if r['is_active']),
                'inactive_sources': sum(1 for r in search_results if not r['is_active']),
                'total_sources': len(search_results),
                'method': 'vbpl_database',
                'success': True
            }
            
        except Exception as e:
            st.error(f"❌ Lỗi OpenAI API: {e}")
            return {
                'response': f"Tôi đã tìm thấy {len(search_results)} quy định liên quan trong cơ sở dữ liệu, nhưng gặp lỗi khi xử lý thông tin. Vui lòng tham khảo trực tiếp các quy định sau hoặc liên hệ cơ quan có thẩm quyền.",
                'sources': search_results,
                'method': 'vbpl_database_error',
                'success': False
            }
    
    def _generate_fallback_response(self, query: str) -> Dict[str, Any]:
        """Generate fallback response khi không có database results"""
        
        fallback_response = """Tôi không tìm thấy thông tin cụ thể về vấn đề này trong cơ sở dữ liệu pháp luật hiện có. 

🔍 **Để có thông tin chính xác nhất, bạn vui lòng:**

1. **Tham khảo trực tiếp** tại thuvienphapluat.vn
2. **Liên hệ** Sở Tài nguyên và Môi trường địa phương  
3. **Tham khảo** Luật Khoáng sản hiện hành và các nghị định hướng dẫn
4. **Liên hệ** hotline tư vấn pháp luật của Bộ Tư pháp

💡 **Gợi ý**: Thử diễn đạt câu hỏi khác hoặc sử dụng từ khóa cụ thể hơn về lĩnh vực khoáng sản."""

        return {
            'response': fallback_response,
            'sources': [],
            'method': 'vbpl_database_empty',
            'success': False
        }
    
    def _create_structured_context(self, results: List[Dict]) -> str:
        """Create structured context từ VBPL database results"""
        
        context = "=== THÔNG TIN TỪ CƠ SỞ DỮ LIỆU PHÁP LUẬT VBPL ===\n\n"
        
        # Group by document status
        active_results = [r for r in results if r['is_active']]
        inactive_results = [r for r in results if not r['is_active']]
        
        if active_results:
            context += "📋 **QUY ĐỊNH CÒN HIỆU LỰC (Ưu tiên sử dụng):**\n\n"
            for i, result in enumerate(active_results, 1):
                context += self._format_result_for_context(result, i, "✅")
        
        if inactive_results:
            context += "\n📋 **QUY ĐỊNH HẾT HIỆU LỰC (Chỉ tham khảo):**\n\n"
            for i, result in enumerate(inactive_results, 1):
                context += self._format_result_for_context(result, i, "⚠️")
        
        return context
    
    def _format_result_for_context(self, result: Dict, index: int, status_icon: str) -> str:
        """Format single result cho context"""
        
        entry = f"Nguồn {index} {status_icon}:\n"
        entry += f"• **Văn bản**: {result['document_number']} - {result['document_name']}\n"
        entry += f"• **Trạng thái**: {result['document_state']}\n"
        entry += f"• **Điều khoản**: {result['element_number']}"
        
        if result['element_name']:
            entry += f" - {result['element_name']}\n"
        else:
            entry += "\n"
        
        # Clean và format content
        content = result['element_content'].strip()
        if len(content) > 800:
            content = content[:800] + "..."
        
        entry += f"• **Nội dung**: {content}\n"
        entry += f"• **Độ liên quan**: {result['relevance_score']:.2f}\n"
        entry += "---\n\n"
        
        return entry
    
    def _call_openai_with_vbpl_context(self, query: str, context: str, sources: List[Dict]) -> str:
        """Call OpenAI với VBPL context và professional prompting"""
        
        # Count sources
        active_sources = sum(1 for s in sources if s['is_active'])
        inactive_sources = len(sources) - active_sources
        
        # Professional system prompt cho khoáng sản
        system_prompt = """Bạn là chuyên gia pháp luật KHOÁNG SẢN Việt Nam với chuyên môn sâu về quy định pháp luật.

🎯 **NHIỆM VỤ CHÍNH**:
- Trả lời DỰA TRÊN quy định pháp luật khoáng sản từ cơ sở dữ liệu VBPL
- Ưu tiên tuyệt đối QUY ĐỊNH CÒN HIỆU LỰC (✅) hơn quy định hết hiệu lực (⚠️)
- Trích dẫn CHÍNH XÁC điều, khoản, điểm từ văn bản pháp luật
- Giải thích THỰC TIỄN và dễ hiểu cho doanh nghiệp/cá nhân

🚫 **NGHIÊM CẤM**:
- Suy luận hoặc diễn giải khi không có thông tin trực tiếp
- Sử dụng quy định HẾT HIỆU LỰC khi đã có quy định CÒN HIỆU LỰC
- Trích dẫn điều luật không trực tiếp liên quan đến câu hỏi
- Bịa đặt thông tin không có trong cơ sở dữ liệu

📋 **FORMAT CHUẨN**:
**🔍 Trả lời**: [Câu trả lời trực tiếp và rõ ràng]

**⚖️ Căn cứ pháp lý**: 
[Trích dẫn cụ thể với trạng thái hiệu lực]

**💡 Lưu ý thực tiễn**: [Nếu cần thiết]

**📌 Khuyến nghị**: [Hướng dẫn thực hiện hoặc tham khảo thêm]

🎯 **DOMAIN**: CHỈ về KHOÁNG SẢN - không áp dụng cho lĩnh vực khác."""

        user_prompt = f"""❓ **Câu hỏi**: {query}

📊 **Nguồn từ Database VBPL**: {active_sources} quy định còn hiệu lực + {inactive_sources} quy định hết hiệu lực

{context}

🎯 **Yêu cầu**: Trả lời dựa trên cơ sở dữ liệu VBPL trên, TUYỆT ĐỐI ưu tiên quy định CÒN HIỆU LỰC."""

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {e}")

# =================== STREAMLIT CORE FUNCTIONS ===================

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

def get_system_prompt():
    """Get system prompt từ file hoặc default"""
    try:
        with open("01.system_trainning.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Bạn là chuyên gia pháp chế về quản lý nhà nước trong lĩnh vực khoáng sản tại Việt Nam, được hỗ trợ bởi cơ sở dữ liệu pháp luật VBPL chuyên nghiệp."""

def get_welcome_message():
    """Get welcome message"""
    try:
        with open("02.assistant.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """Xin chào! ⚖️ 

Tôi là **Trợ lý Pháp chế chuyên về Khoáng sản** được hỗ trợ bởi **cơ sở dữ liệu pháp luật VBPL**.

🗄️ **Tôi có thể tìm kiếm chính xác trong hệ thống pháp luật về:**
- Luật Khoáng sản và các văn bản hướng dẫn
- Thủ tục cấp phép thăm dò, khai thác
- Thuế, phí liên quan đến khoáng sản  
- Xử phạt vi phạm hành chính
- Bảo vệ môi trường trong hoạt động khoáng sản

💡 **Hãy đặt câu hỏi cụ thể để tôi tìm kiếm chính xác trong database!**"""

def get_default_model():
    """Get default model"""
    try:
        with open("module_chatgpt.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return "gpt-4o-mini"

def is_mineral_related(message):
    """Check if message is mineral-related"""
    mineral_keywords = [
        'khoáng sản', 'khai thác', 'thăm dò', 'đá', 'cát', 'sỏi',
        'than', 'quặng', 'kim loại', 'phi kim loại', 'khoáng',
        'luật khoáng sản', 'giấy phép', 'cấp phép', 'thuế tài nguyên',
        'phí thăm dò', 'tiền cấp quyền', 'vi phạm hành chính',
        'bộ tài nguyên', 'sở tài nguyên', 'monre', 'tn&mt',
        'mỏ', 'mỏ đá', 'mỏ cát', 'mỏ than', 'quarry', 'mining',
        'thu hồi giấy phép', 'gia hạn', 'đóng cửa mỏ'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mineral_keywords)

def count_tokens(text):
    """Estimate token count"""
    return len(str(text)) // 4

def update_stats(input_tokens, output_tokens, model):
    """Update token statistics"""
    try:
        if model not in MODEL_PRICING:
            model = "gpt-4o-mini"
        
        pricing = MODEL_PRICING[model]
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        
        st.session_state.token_stats["total_input_tokens"] += input_tokens
        st.session_state.token_stats["total_output_tokens"] += output_tokens
        st.session_state.token_stats["total_cost"] += cost
        st.session_state.token_stats["request_count"] += 1
        
    except Exception as e:
        st.error(f"Error updating stats: {e}")

# =================== VBPL SYSTEM INITIALIZATION ===================

def init_vbpl_system():
    """Initialize VBPL system"""
    if 'vbpl_system' not in st.session_state:
        config = VBPLConfig()
        db_manager = VBPLDatabase(config)
        
        if db_manager.is_available():
            try:
                client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                openai_processor = VBPLOpenAIProcessor(client, config, db_manager)
                
                st.session_state.vbpl_system = {
                    'config': config,
                    'db_manager': db_manager,
                    'openai_processor': openai_processor,
                    'available': True
                }
                
            except Exception as e:
                st.sidebar.error(f"❌ VBPL system initialization failed: {e}")
                st.session_state.vbpl_system = {'available': False}
        else:
            st.session_state.vbpl_system = {'available': False}

def is_vbpl_available() -> bool:
    """Check if VBPL system is available"""
    return st.session_state.get('vbpl_system', {}).get('available', False)

def process_with_vbpl(query: str) -> Dict[str, Any]:
    """Process query với VBPL system"""
    if not is_vbpl_available():
        return {'method': 'vbpl_unavailable', 'success': False}
    
    processor = st.session_state.vbpl_system['openai_processor']
    return processor.process_legal_query(query)

def show_vbpl_results_details(result: Dict[str, Any]):
    """Show detailed VBPL results"""
    if not result.get('sources'):
        return
    
    st.markdown("### 📊 **Chi tiết kết quả từ Database VBPL**")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tổng kết quả", result['total_sources'])
    with col2:
        st.metric("Còn hiệu lực", result['active_sources'])
    with col3:
        st.metric("Hết hiệu lực", result['inactive_sources'])
    
    # Detailed results
    for i, source in enumerate(result['sources'], 1):
        with st.expander(
            f"{i}. {'✅' if source['is_active'] else '⚠️'} {source['element_number']}: {source['element_name'][:60]}...", 
            expanded=False
        ):
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**📄 Văn bản**: {source['document_number']}")
                st.write(f"**📋 Tên văn bản**: {source['document_name']}")
                st.write(f"**⚖️ Trạng thái**: {source['document_state']}")
                st.write(f"**📍 Điều khoản**: {source['element_number']}")
                if source['element_name']:
                    st.write(f"**🏷️ Tên điều khoản**: {source['element_name']}")
            
            with col2:
                st.metric("Relevance Score", f"{source['relevance_score']:.2f}")
                st.metric("Element Type", source['element_type'])
                st.metric("Priority", "High" if source['is_active'] else "Low")
            
            st.markdown("**📝 Nội dung đầy đủ:**")
            st.write(source['element_content'])

# =================== MAIN APPLICATION ===================

def main():
    # Initialize systems
    init_session_state()
    init_vbpl_system()
    
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
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #2E7D32, #4CAF50); border-radius: 10px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">⚖️ Trợ lý Pháp chế Khoáng sản</h1>
        <p style="color: #E8F5E8; margin: 5px 0 0 0;">Hỗ trợ bởi Cơ sở dữ liệu Pháp luật VBPL</p>
        <p style="color: #E8F5E8; margin: 5px 0 0 0; font-size: 12px;">🗄️ Database-Powered • Accurate Legal Content • Real-time Search</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Cài đặt hệ thống")
        
        # VBPL status
        if is_vbpl_available():
            vbpl_enabled = st.toggle("🗄️ Sử dụng VBPL Database", value=True)
            st.success("✅ VBPL Database Online")
        else:
            vbpl_enabled = False
            st.toggle("🗄️ Sử dụng VBPL Database", value=False, disabled=True)
            st.error("❌ VBPL Database Offline")
            st.info("💡 Cần file vbpl.db để sử dụng")
        
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
        temperature = st.slider("🌡️ Độ sáng tạo:", 0.0, 1.0, 0.1, 0.1)
        
        st.markdown("---")
        
        # Statistics
        st.markdown("### 📊 Thống kê sử dụng")
        try:
            stats = st.session_state.token_stats
            total_tokens = stats["total_input_tokens"] + stats["total_output_tokens"]
            
            st.metric("🎯 Tổng Token", f"{total_tokens:,}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📥 Input", f"{stats['total_input_tokens']:,}")
            with col2:
                st.metric("📤 Output", f"{stats['total_output_tokens']:,}")
            
            st.metric("💰 Chi phí (USD)", f"${stats['total_cost']:.4f}")
            st.metric("💸 Chi phí (VND)", f"{stats['total_cost'] * 24000:,.0f}đ")
            st.metric("📞 Số lượt hỏi", stats['request_count'])
            
        except Exception as e:
            st.error(f"Error displaying stats: {e}")
        
        # Reset buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset stats", use_container_width=True):
                st.session_state.token_stats = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                    "session_start": datetime.now(),
                    "request_count": 0
                }
                st.rerun()
        
        with col2:
            if st.button("🗑️ Xóa chat", use_container_width=True):
                st.session_state.messages = [
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "assistant", "content": get_welcome_message()}
                ]
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 🗄️ VBPL Features")
        if is_vbpl_available():
            st.success("✅ Structured legal database")
            st.success("✅ Domain-specific filtering")
            st.success("✅ Document status prioritization")
            st.success("✅ Professional AI prompting")
            st.info("💡 Tìm kiếm chính xác trong database pháp luật")
        else:
            st.info("💡 VBPL database cung cấp:")
            st.write("• Tìm kiếm structured content")
            st.write("• Ưu tiên văn bản còn hiệu lực")
            st.write("• Trích dẫn chính xác điều khoản")
            st.write("• Filtering domain khoáng sản")
    
    # Check OpenAI API
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

Hãy đặt câu hỏi về lĩnh vực khoáng sản để tôi có thể hỗ trợ bạn tốt nhất! 😊"""
            
            st.session_state.messages.append({"role": "assistant", "content": polite_refusal})
            st.markdown(f'<div class="assistant-message">{polite_refusal}</div>', 
                       unsafe_allow_html=True)
            return
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        # Process with VBPL if available
        if vbpl_enabled and is_vbpl_available():
            with st.spinner("🤔 Đang phân tích câu hỏi với VBPL database..."):
                
                vbpl_result = process_with_vbpl(prompt)
                
                if vbpl_result.get('success'):
                    # Successful VBPL response
                    response = vbpl_result['response']
                    
                    # Display response
                    st.markdown(f'<div class="assistant-message">{response}</div>', 
                               unsafe_allow_html=True)
                    
                    # Show detailed results
                    if vbpl_result.get('sources'):
                        show_vbpl_results_details(vbpl_result)
                    
                    # Update token stats (estimate)
                    input_tokens = count_tokens(prompt)
                    output_tokens = count_tokens(response)
                    update_stats(input_tokens, output_tokens, selected_model)
                    
                else:
                    # VBPL failed, show fallback response
                    response = vbpl_result['response']
                    st.markdown(f'<div class="assistant-message">{response}</div>', 
                               unsafe_allow_html=True)
        
        else:
            # Fallback when VBPL not available
            fallback_response = """🗄️ **Cơ sở dữ liệu VBPL không khả dụng**

Để có thông tin chính xác nhất về vấn đề này, bạn vui lòng:

1. **Tham khảo trực tiếp** tại thuvienphapluat.vn
2. **Liên hệ** Sở Tài nguyên và Môi trường địa phương
3. **Tham khảo** Luật Khoáng sản hiện hành và các nghị định hướng dẫn

💡 **Gợi ý**: Để sử dụng tính năng tìm kiếm database chính xác, vui lòng cung cấp file `vbpl.db`."""
            
            st.markdown(f'<div class="assistant-message">{fallback_response}</div>', 
                       unsafe_allow_html=True)
        
        # Add response to history
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()