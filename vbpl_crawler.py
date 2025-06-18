#!/usr/bin/env python3
"""
VBPL CLI Crawler - Automated Document Processing & Database Storage
Crawl và xử lý các văn bản VBPL từ judgment_id gốc, tự động mở rộng chuỗi thông qua vbpl_diagram
"""

import os
import sys
import json
import sqlite3
import time
import argparse
from collections import deque
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path

# Import từ update_vbpl_CL.py đã sửa
try:
    from update_vbpl_CL import (
        get_processor_for_crawler,
        extract_judgment_ids_from_result, 
        extract_relations_from_result
    )
except ImportError as e:
    print(f"❌ Cannot import from update_vbpl_CL.py: {e}")
    print("📝 Make sure update_vbpl_CL.py is in the same directory and contains required functions")
    sys.exit(1)

@dataclass
class CrawlerConfig:
    """Configuration for VBPL Crawler"""
    start_id: str
    log_dir: str = "./logs"
    db_path: str = "./vbpl.db"
    report_path: str = "./vbpl_report.json"
    max_workers: int = 1  # Sequential processing for stability
    retry_attempts: int = 3
    delay_between_requests: float = 2.0  # Rate limiting
    enable_resume: bool = True
    max_documents: int = 1000  # Safety limit
    complete_scan: bool = False  # Complete discovery scan

class CrawlerStats:
    """Track crawler statistics"""
    def __init__(self):
        self.total_processed = 0
        self.total_success = 0
        self.total_failed = 0
        self.total_skipped = 0
        self.start_time = datetime.now()
        self.relations_found = 0
        self.unique_ids_discovered = 0

    def to_dict(self) -> Dict:
        duration = datetime.now() - self.start_time
        return {
            "total_processed": self.total_processed,
            "total_success": self.total_success, 
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "relations_found": self.relations_found,
            "unique_ids_discovered": self.unique_ids_discovered,
            "duration_minutes": duration.total_seconds() / 60,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat()
        }

class SQLiteDatabase:
    """SQLite database operations for VBPL data"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database với schema tối ưu"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    judgment_id TEXT PRIMARY KEY,
                    judgment_number TEXT,
                    judgment_name TEXT,
                    full_judgment_name TEXT,
                    date_issued TEXT,
                    state TEXT,
                    state_id INTEGER,
                    doc_type TEXT,
                    issuing_authority TEXT,
                    s3_key TEXT,
                    application_date TEXT,
                    expiration_date TEXT,
                    expiration_date_not_applicable BOOLEAN,
                    type_document TEXT,
                    sector TEXT,
                    processing_timestamp TEXT,
                    total_sections INTEGER,
                    total_clauses INTEGER,
                    total_points INTEGER,
                    processing_status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Elements table - tất cả structural elements
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS elements (
                    element_id TEXT PRIMARY KEY,
                    judgment_id TEXT NOT NULL,
                    element_type TEXT NOT NULL,
                    element_number TEXT,
                    element_name TEXT,
                    element_content TEXT,
                    tag_id TEXT,
                    immediate_parent_id TEXT,
                    immediate_parent_type TEXT,
                    level INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (judgment_id) REFERENCES documents(judgment_id),
                    FOREIGN KEY (immediate_parent_id) REFERENCES elements(element_id)
                )
            """)
            
            # Relations table với relationship types
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vbpl_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_judgment_id TEXT NOT NULL,
                    target_judgment_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    relation_name TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (source_judgment_id) REFERENCES documents(judgment_id),
                    FOREIGN KEY (target_judgment_id) REFERENCES documents(judgment_id),
                    
                    UNIQUE(source_judgment_id, target_judgment_id, relation_type)
                )
            """)
            
            # Processing queue table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    judgment_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    last_attempt_at TIMESTAMP,
                    error_message TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_judgment_id ON elements(judgment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_type ON elements(element_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_parent ON elements(immediate_parent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON vbpl_relations(source_judgment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON vbpl_relations(target_judgment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_type ON vbpl_relations(relation_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status)")
            
            conn.commit()
    
    def document_exists(self, judgment_id: str) -> bool:
        """Check if document đã xử lý"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM documents WHERE judgment_id = ?", (judgment_id,))
            return cursor.fetchone() is not None
    
    def insert_document(self, judgment_id: str, metadata: Dict):
        """Insert document metadata"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Prepare data
            data = {
                'judgment_id': judgment_id,
                'judgment_number': metadata.get('judgment_number'),
                'judgment_name': metadata.get('judgment_name'),
                'full_judgment_name': metadata.get('full_judgment_name'),
                'date_issued': metadata.get('date_issued'),
                'state': metadata.get('state'),
                'state_id': metadata.get('state_id'),
                'doc_type': metadata.get('doc_type'),
                'issuing_authority': metadata.get('issuing_authority'),
                's3_key': metadata.get('s3_key'),
                'application_date': metadata.get('application_date'),
                'expiration_date': metadata.get('expiration_date'),
                'expiration_date_not_applicable': metadata.get('expiration_date_not_applicable'),
                'type_document': metadata.get('type_document'),
                'sector': metadata.get('sector'),
                'processing_timestamp': datetime.now().isoformat()
            }
            
            cursor.execute("""
                INSERT OR REPLACE INTO documents 
                (judgment_id, judgment_number, judgment_name, full_judgment_name, 
                 date_issued, state, state_id, doc_type, issuing_authority, s3_key,
                 application_date, expiration_date, expiration_date_not_applicable,
                 type_document, sector, processing_timestamp)
                VALUES 
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['judgment_id'], data['judgment_number'], data['judgment_name'],
                data['full_judgment_name'], data['date_issued'], data['state'], 
                data['state_id'], data['doc_type'], data['issuing_authority'],
                data['s3_key'], data['application_date'], data['expiration_date'],
                data['expiration_date_not_applicable'], data['type_document'],
                data['sector'], data['processing_timestamp']
            ))
            
            conn.commit()
    
    def insert_element(self, judgment_id: str, element_type: str, element: Dict):
        """Insert structural element"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Map element fields based on type
            field_mapping = {
                'vbpl_big_part': ('vbpl_big_part_id', 'big_part_number', 'big_part_name', 'big_part_content'),
                'vbpl_chapter': ('vbpl_chapter_id', 'chapter_number', 'chapter_name', 'chapter_content'),
                'vbpl_part': ('vbpl_part_id', 'part_number', 'part_name', 'part_content'),
                'vbpl_mini_part': ('vbpl_mini_part_id', 'mini_part_number', 'mini_part_name', 'mini_part_content'),
                'vbpl_section': ('vbpl_section_id', 'section_number', 'section_name', 'section_content'),
                'vbpl_clause': ('vbpl_clause_id', 'clause_number', 'clause_name', 'clause_content'),
                'vbpl_point': ('vbpl_point_id', 'point_number', 'point_name', 'point_content')
            }
            
            if element_type not in field_mapping:
                return
            
            id_field, number_field, name_field, content_field = field_mapping[element_type]
            
            # Get level from element type
            level_mapping = {
                'vbpl_big_part': 1, 'vbpl_chapter': 2, 'vbpl_part': 3, 
                'vbpl_mini_part': 4, 'vbpl_section': 5, 'vbpl_clause': 6, 'vbpl_point': 7
            }
            
            cursor.execute("""
                INSERT OR REPLACE INTO elements 
                (element_id, judgment_id, element_type, element_number, element_name, 
                 element_content, tag_id, immediate_parent_id, immediate_parent_type, level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                element.get(id_field),
                judgment_id,
                element_type,
                element.get(number_field),
                element.get(name_field),
                element.get(content_field),
                element.get('tag_id'),
                element.get('immediate_parent_id'),
                element.get('immediate_parent_type'),
                level_mapping[element_type]
            ))
            
            conn.commit()
    
    def insert_relation(self, source_judgment_id: str, target_judgment_id: str, relation_type: str):
        """Insert relationship between documents"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO vbpl_relations 
                (source_judgment_id, target_judgment_id, relation_type, relation_name)
                VALUES (?, ?, ?, ?)
            """, (source_judgment_id, target_judgment_id, relation_type, relation_type))
            
            conn.commit()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Document counts
            cursor.execute("SELECT COUNT(*) FROM documents")
            stats['total_documents'] = cursor.fetchone()[0]
            
            # Element counts by type
            cursor.execute("""
                SELECT element_type, COUNT(*) 
                FROM elements 
                GROUP BY element_type
            """)
            stats['elements_by_type'] = dict(cursor.fetchall())
            
            # Relation counts
            cursor.execute("SELECT COUNT(*) FROM vbpl_relations")
            stats['total_relations'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT relation_type, COUNT(*) 
                FROM vbpl_relations 
                GROUP BY relation_type
            """)
            stats['relations_by_type'] = dict(cursor.fetchall())
            
            return stats

class VBPLCrawler:
    """Main VBPL Crawler với queue-based processing"""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.db = SQLiteDatabase(config.db_path)
        self.processor = get_processor_for_crawler(config.log_dir)
        self.queue = deque([config.start_id])
        self.processed: Set[str] = set()
        self.failed: Set[str] = set()
        self.stats = CrawlerStats()
        
        # Setup logging directory
        Path(config.log_dir).mkdir(parents=True, exist_ok=True)
        if os.path.exists(config.db_path):
            self.get_database_summary()
        
        print(f"🚀 VBPL Crawler initialized")
        print(f"📊 Database: {config.db_path}")
        print(f"📁 Logs: {config.log_dir}")
        print(f"🎯 Starting from: {config.start_id}")
    
    def should_skip(self, judgment_id: str) -> bool:
        """Check if document should be skipped"""
        if judgment_id in self.processed:
            return True
        
        if judgment_id in self.failed:
            return True
        
        if self.db.document_exists(judgment_id):
            print(f"⚠️  Đã có: {judgment_id}, bỏ qua")
            self.stats.total_skipped += 1
            self.processed.add(judgment_id)
            return True
        
        return False
    
    def process_document(self, judgment_id: str) -> bool:
        """Process single document với error handling"""
        print(f"🔄 Đang xử lý: {judgment_id}")
        
        try:
            # Call processor với return data
            success, result_data = self.processor.process_document(judgment_id)
            
            if success and result_data:
                # Save to database
                self.save_to_database(judgment_id, result_data)
                
                # Extract và queue related IDs
                related_ids = extract_judgment_ids_from_result(result_data)
                self.queue_related_ids(related_ids)
                
                print(f"✅ Đã xử lý và lưu: {judgment_id}")
                if related_ids:
                    print(f"📎 Tìm thấy {len(related_ids)} liên kết")
                    
                self.stats.total_success += 1
                self.stats.relations_found += len(related_ids)
                return True
            else:
                print(f"❌ Lỗi xử lý: {judgment_id}")
                self.stats.total_failed += 1
                self.failed.add(judgment_id)
                return False
                
        except Exception as e:
            print(f"❌ Exception: {judgment_id} - {e}")
            self.stats.total_failed += 1
            self.failed.add(judgment_id)
            return False
    
    def save_to_database(self, judgment_id: str, result_data: Dict):
        """Save processed data to SQLite"""
        try:
            # Extract metadata và structure data
            metadata = result_data.get('document_metadata', {})
            structure_data = result_data.get('structure_data', {})
            
            # Save document
            self.db.insert_document(judgment_id, metadata)
            
            # Save elements
            total_elements = 0
            for element_type, elements in structure_data.items():
                for element in elements:
                    self.db.insert_element(judgment_id, element_type, element)
                    total_elements += 1
            
            # Save relations từ vbpl_diagram
            relations = extract_relations_from_result(result_data)
            for relation in relations:
                self.db.insert_relation(
                    judgment_id, 
                    relation['target_judgment_id'],
                    relation['relation_type']
                )
            
            print(f"💾 Lưu DB: {total_elements} elements, {len(relations)} relations")
            
        except Exception as e:
            print(f"⚠️  Lỗi lưu DB cho {judgment_id}: {e}")
            raise
    
    def queue_related_ids(self, related_ids: List[str]):
        """Add related IDs to processing queue"""
        new_ids = 0
        for related_id in related_ids:
            if (related_id not in self.processed and 
                related_id not in self.queue and 
                related_id not in self.failed):
                self.queue.append(related_id)
                new_ids += 1
                print(f"📎 Queue: {related_id}")
        
        if new_ids > 0:
            self.stats.unique_ids_discovered += new_ids
    def load_unprocessed_queue(self):
        """Load unprocessed related documents vào queue"""
        with sqlite3.connect(self.config.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all target IDs chưa được processed
            cursor.execute("""
                SELECT DISTINCT target_judgment_id 
                FROM vbpl_relations 
                WHERE target_judgment_id NOT IN (
                    SELECT judgment_id FROM documents
                )
                ORDER BY target_judgment_id
            """)
            
            unprocessed_ids = [row[0] for row in cursor.fetchall()]
            
            # Add to queue
            for judgment_id in unprocessed_ids:
                if judgment_id not in self.queue:
                    self.queue.append(judgment_id)
            
            print(f"📥 Loaded {len(unprocessed_ids)} unprocessed IDs from database")
            return len(unprocessed_ids)

    def get_database_summary(self):
        """Get database summary for debugging"""
        with sqlite3.connect(self.config.db_path) as conn:
            cursor = conn.cursor()
            
            # Total stats
            cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT target_judgment_id) FROM vbpl_relations")
            total_targets = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(DISTINCT target_judgment_id) 
                FROM vbpl_relations 
                WHERE target_judgment_id NOT IN (SELECT judgment_id FROM documents)
            """)
            unprocessed = cursor.fetchone()[0]
            
            print(f"📊 Database Summary:")
            print(f"   📄 Processed docs: {total_docs}")
            print(f"   🎯 Total targets discovered: {total_targets}")
            print(f"   ⏳ Unprocessed targets: {unprocessed}")
            if total_targets > 0:
                print(f"   📈 Coverage: {(total_docs/total_targets*100):.1f}%")
            
            return {
                'processed': total_docs,
                'total_targets': total_targets, 
                'unprocessed': unprocessed
            }
    
    def run(self):
        """Main crawler loop với comprehensive discovery"""
        print(f"\n🚀 Bắt đầu crawling từ ID: {self.config.start_id}")
        print(f"📊 Giới hạn: {self.config.max_documents} documents")
        print("-" * 60)
        
        # Complete discovery scan if requested
        if hasattr(self.config, 'complete_scan') and self.config.complete_scan and os.path.exists(self.config.db_path):
            new_discoveries = self.complete_discovery_scan()
            if new_discoveries > 0:
                print(f"🎯 Found {new_discoveries} additional documents to process")
        
        # Auto-resume logic
        if self.db.document_exists(self.config.start_id):
            print(f"⚠️  Start ID {self.config.start_id} đã processed, loading unprocessed queue...")
            loaded = self.load_unprocessed_queue()
            if loaded == 0 and len(self.queue) == 0:
                print("✅ Tất cả related documents đã được processed!")
                print("🎯 Try với start ID khác để discover thêm documents")
                self.generate_report()
                self.print_final_stats()
                return
        
        while self.queue and self.stats.total_processed < self.config.max_documents:
            judgment_id = self.queue.popleft()
            
            if self.should_skip(judgment_id):
                continue
            
            # Rate limiting
            if self.stats.total_processed > 0:
                time.sleep(self.config.delay_between_requests)
            
            # Process document
            self.process_document(judgment_id)
            self.processed.add(judgment_id)
            self.stats.total_processed += 1
            
            # Progress update
            if self.stats.total_processed % 5 == 0:
                self.print_progress()
        
        # Final results
        self.generate_report()
        print(f"\n🎉 Crawler hoàn thành!")
        self.print_final_stats()
    
    def print_progress(self):
        """Print progress summary"""
        print(f"\n📊 Tiến độ:")
        print(f"   ✅ Thành công: {self.stats.total_success}")
        print(f"   ❌ Thất bại: {self.stats.total_failed}")
        print(f"   ⚠️  Đã có: {self.stats.total_skipped}")
        print(f"   📎 Queue còn: {len(self.queue)}")
        print(f"   🔗 Relations: {self.stats.relations_found}")
    
    def print_final_stats(self):
        """Print final statistics"""
        db_stats = self.db.get_stats()
        print(f"\n📊 Thống kê cuối:")
        print(f"   📄 Documents: {db_stats['total_documents']}")
        print(f"   🧱 Elements: {sum(db_stats['elements_by_type'].values())}")
        print(f"   🔗 Relations: {db_stats['total_relations']}")
        print(f"   ⏱️  Thời gian: {(datetime.now() - self.stats.start_time).total_seconds():.1f}s")
        print(f"   💾 Database: {self.config.db_path}")
    
    def generate_report(self):
        """Generate final JSON report"""
        report = {
            "crawler_stats": self.stats.to_dict(),
            "database_stats": self.db.get_stats(),
            "config": {
                "start_id": self.config.start_id,
                "max_documents": self.config.max_documents,
                "db_path": self.config.db_path
            },
            "failed_ids": list(self.failed) if self.failed else [],
            "queue_remaining": list(self.queue) if self.queue else []
        }
        
        try:
            with open(self.config.report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"📄 Report saved: {self.config.report_path}")
        except Exception as e:
            print(f"⚠️  Cannot save report: {e}")

    def complete_discovery_scan(self):
        """Comprehensive scan để ensure không miss relations"""
        print("🔍 Starting complete discovery scan...")
        
        with sqlite3.connect(self.config.db_path) as conn:
            cursor = conn.cursor()
            
            # Get ALL processed documents
            cursor.execute("SELECT judgment_id FROM documents")
            processed_docs = [row[0] for row in cursor.fetchall()]
            
            new_discoveries = 0
            total_new_relations = 0
            
            for doc_id in processed_docs:
                print(f"🔍 Re-scanning: {doc_id}")
                
                # Re-read vbpl_diagram từ processed files
                complete_file = os.path.join(self.config.log_dir, f"optimized_complete_{doc_id}.json")
                
                if os.path.exists(complete_file):
                    try:
                        with open(complete_file, 'r', encoding='utf-8') as f:
                            result_data = json.load(f)
                        
                        # Extract relations again
                        relations = extract_relations_from_result(result_data)
                        
                        for relation in relations:
                            target_id = relation['target_judgment_id']
                            
                            # Check if this target is new (not in documents and not in current queue)
                            cursor.execute("SELECT 1 FROM documents WHERE judgment_id = ?", (target_id,))
                            if not cursor.fetchone() and target_id not in self.queue:
                                self.queue.append(target_id)
                                new_discoveries += 1
                                print(f"📎 New discovery: {target_id}")
                            
                            # Re-insert relation (INSERT OR IGNORE will handle duplicates)
                            self.db.insert_relation(doc_id, target_id, relation['relation_type'])
                            total_new_relations += 1
                    
                    except Exception as e:
                        print(f"⚠️  Error re-scanning {doc_id}: {e}")
            
            print(f"🔍 Discovery scan complete:")
            print(f"   📎 New documents found: {new_discoveries}")
            print(f"   🔗 Relations re-verified: {total_new_relations}")
            
            return new_discoveries

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="VBPL Document Crawler")
    parser.add_argument("start_id", help="Starting judgment ID")
    parser.add_argument("--log-dir", default="./logs", help="Log directory")
    parser.add_argument("--db-path", default="./vbpl.db", help="SQLite database path")  
    parser.add_argument("--report-path", default="./vbpl_report.json", help="Report output path")
    parser.add_argument("--max-docs", type=int, default=100, help="Maximum documents to process")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    parser.add_argument("--complete-scan", action="store_true", help="Do complete discovery scan before resume")
    
    args = parser.parse_args()
    
    # Create configuration
    config = CrawlerConfig(
        start_id=args.start_id,
        log_dir=args.log_dir,
        db_path=args.db_path,
        report_path=args.report_path,
        max_documents=args.max_docs,
        delay_between_requests=args.delay,
        complete_scan=args.complete_scan
    )
    
    # Run crawler
    crawler = VBPLCrawler(config)
    try:
        crawler.run()
    except KeyboardInterrupt:
        print(f"\n⏹️  Crawler stopped by user")
        crawler.generate_report()
        crawler.print_final_stats()
    except Exception as e:
        print(f"\n❌ Crawler error: {e}")
        crawler.generate_report()
if __name__ == "__main__":
    main()