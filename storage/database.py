# -*- coding: utf-8 -*-
"""
إدارة قاعدة بيانات التخزين
"""

import sqlite3
import uuid
import logging
from typing import Optional, List, Dict, Any

from .config import API_ID, API_HASH, ACCOUNTS_DB_PATH

logger = logging.getLogger(__name__)

class StorageDatabaseManager:
    """مدير قاعدة بيانات التخزين"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_storage_db()
        self.init_accounts_db()
    
    def init_storage_db(self):
        """تهيئة قاعدة بيانات التخزين"""
        with sqlite3.connect(self.db_path) as conn:
            # إنشاء جدول فئات التخزين
            conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المجموعات المخزنة
            conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_groups (
                    id TEXT PRIMARY KEY,
                    category_id TEXT NOT NULL,
                    group_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    username TEXT,
                    total_members INTEGER NOT NULL,
                    storage_type TEXT NOT NULL,
                    scan_months INTEGER,
                    last_seen_months INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES storage_categories(id)
                )
            ''')
            
            # جدول الأعضاء المخزنين مع تفاصيل إضافية
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stored_members (
                    id TEXT PRIMARY KEY,
                    storage_group_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    last_seen TIMESTAMP,
                    is_bot INTEGER DEFAULT 0,
                    is_premium INTEGER DEFAULT 0,
                    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transfer_status TEXT DEFAULT 'pending',
                    FOREIGN KEY (storage_group_id) REFERENCES storage_groups(id)
                )
            ''')
            
            # جدول لتتبع تقدم التخزين
            conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_progress (
                    id TEXT PRIMARY KEY,
                    storage_group_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    total_members INTEGER DEFAULT 0,
                    stored_members INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    last_offset INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (storage_group_id) REFERENCES storage_groups(id)
                )
            ''')
            
            # التحقق من وجود الأعمدة scan_months و last_seen_months
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(storage_groups)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'scan_months' not in columns:
                conn.execute("ALTER TABLE storage_groups ADD COLUMN scan_months INTEGER")
            if 'last_seen_months' not in columns:
                conn.execute("ALTER TABLE storage_groups ADD COLUMN last_seen_months INTEGER")
            
            conn.commit()
    
    def init_accounts_db(self):
        """تهيئة قاعدة بيانات الحسابات مع إضافة الأعمدة المطلوبة"""
        with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
            cursor = conn.cursor()
            
            # جدول الفئات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    category_id TEXT NOT NULL,
                    username TEXT,
                    session_str TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    device_info TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            """)
            
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'api_id' not in columns:
                conn.execute("ALTER TABLE accounts ADD COLUMN api_id INTEGER")
            if 'api_hash' not in columns:
                conn.execute("ALTER TABLE accounts ADD COLUMN api_hash TEXT")
            
            conn.execute("UPDATE accounts SET api_id = ? WHERE api_id IS NULL", (API_ID,))
            conn.execute("UPDATE accounts SET api_hash = ? WHERE api_hash IS NULL", (API_HASH,))
            
            # التأكد من وجود فئة "حسابات التخزين"
            cursor.execute(
                "INSERT OR IGNORE INTO categories (id, name) VALUES (?, ?)",
                ('storage_accounts', 'حسابات التخزين')
            )
            
            conn.commit()
    
    def get_or_create_storage_category(self, category_name: str) -> str:
        """إنشاء أو استرجاع فئة التخزين"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM storage_categories WHERE name = ?", (category_name,))
            category = cursor.fetchone()
            
            if category:
                return category[0]
            
            category_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO storage_categories (id, name) VALUES (?, ?)",
                (category_id, category_name)
            )
            conn.commit()
            return category_id
    
    def create_storage_group(self, category_id: str, group_id: int, title: str, 
                           username: str, total_members: int, storage_type: str,
                           scan_months: int = 0, last_seen_months: int = 0) -> str:
        """إنشاء مجموعة تخزين جديدة"""
        storage_group_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO storage_groups (id, category_id, group_id, title, username, total_members, storage_type, scan_months, last_seen_months) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (storage_group_id, category_id, group_id, title, username, total_members, storage_type, scan_months, last_seen_months)
            )
            conn.commit()
        return storage_group_id
    
    def get_storage_categories(self) -> List[Dict[str, Any]]:
        """الحصول على جميع فئات التخزين"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name 
                FROM storage_categories
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_storage_groups_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """الحصول على مجموعات فئة معينة"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, group_id, storage_type 
                FROM storage_groups 
                WHERE category_id = ?
                ORDER BY created_at DESC
            """, (category_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_storage_accounts(self) -> List[Dict[str, Any]]:
        """الحصول على حسابات التخزين من قاعدة بيانات البوت الأول"""
        try:
            with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.id, a.phone, a.session_str, a.device_info
                    FROM accounts a
                    JOIN categories c ON a.category_id = c.id
                    WHERE c.name = 'حسابات التخزين'
                """)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                # إنشاء الجداول المطلوبة
                self._create_accounts_tables()
                return []
            else:
                raise e
    
    def store_member(self, storage_group_id: str, user_info: Dict[str, Any]) -> bool:
        """تخزين عضو في قاعدة البيانات"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stored_members (id, storage_group_id, user_id, username, first_name, last_name, phone, last_seen, is_bot, is_premium) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        storage_group_id,
                        user_info['id'],
                        user_info.get('username', ''),
                        user_info.get('first_name', ''),
                        user_info.get('last_name', ''),
                        user_info.get('phone', ''),
                        user_info.get('last_seen'),
                        user_info.get('is_bot', 0),
                        user_info.get('is_premium', 0)
                    )
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في تخزين العضو: {str(e)}")
            return False
    
    def get_stored_members(self, storage_group_id: str) -> List[Dict[str, Any]]:
        """الحصول على الأعضاء المخزنين لمجموعة معينة"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, phone, 
                       last_seen, is_bot, is_premium, transfer_status
                FROM stored_members
                WHERE storage_group_id = ?
            """, (storage_group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_storage_progress(self, storage_group_id: str, account_id: str, 
                              stored_members: int, status: str) -> bool:
        """تحديث تقدم التخزين"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO storage_progress (id, storage_group_id, account_id, stored_members, status) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), storage_group_id, account_id, stored_members, status)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث تقدم التخزين: {str(e)}")
            return False
    
    def get_active_storage_jobs(self) -> List[Dict[str, Any]]:
        """الحصول على مهام التخزين النشطة"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sg.title, sp.status, sp.stored_members, sp.total_members
                FROM storage_progress sp
                JOIN storage_groups sg ON sp.storage_group_id = sg.id
                WHERE sp.status IN ('running', 'paused')
            """)
            return [dict(row) for row in cursor.fetchall()]