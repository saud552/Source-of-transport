# -*- coding: utf-8 -*-
"""
إدارة قاعدة بيانات النقل
"""

import sqlite3
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import ACCOUNTS_DB_PATH, STORAGE_DB_PATH

logger = logging.getLogger(__name__)

class TransferDatabaseManager:
    """مدير قاعدة بيانات النقل"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_transfer_db()
        self.init_connections()
    
    def init_transfer_db(self):
        """تهيئة قاعدة بيانات النقل"""
        with sqlite3.connect(self.db_path) as conn:
            # جدول عمليات النقل
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_operations (
                    id TEXT PRIMARY KEY,
                    source_group_id INTEGER NOT NULL,
                    source_group_title TEXT NOT NULL,
                    target_group_id INTEGER NOT NULL,
                    target_group_title TEXT NOT NULL,
                    account_category TEXT NOT NULL,
                    total_members INTEGER DEFAULT 0,
                    transferred_members INTEGER DEFAULT 0,
                    failed_members INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            # جدول تفاصيل النقل
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_details (
                    id TEXT PRIMARY KEY,
                    transfer_operation_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    transfer_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    transferred_at TIMESTAMP,
                    FOREIGN KEY (transfer_operation_id) REFERENCES transfer_operations(id)
                )
            ''')
            
            # جدول الحسابات المستخدمة في النقل
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_accounts (
                    id TEXT PRIMARY KEY,
                    transfer_operation_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    account_phone TEXT NOT NULL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transfer_operation_id) REFERENCES transfer_operations(id)
                )
            ''')
            
            conn.commit()
    
    def init_connections(self):
        """تهيئة الاتصالات بقواعد البيانات الأخرى"""
        self.accounts_db_path = ACCOUNTS_DB_PATH
        self.storage_db_path = STORAGE_DB_PATH
    
    def create_transfer_operation(self, source_group_id: int, source_group_title: str,
                                target_group_id: int, target_group_title: str,
                                account_category: str) -> str:
        """إنشاء عملية نقل جديدة"""
        transfer_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO transfer_operations (id, source_group_id, source_group_title, target_group_id, target_group_title, account_category) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (transfer_id, source_group_id, source_group_title, target_group_id, target_group_title, account_category)
            )
            conn.commit()
        return transfer_id
    
    def get_available_source_groups(self) -> List[Dict[str, Any]]:
        """الحصول على المجموعات المتاحة للنقل من قاعدة بيانات التخزين"""
        try:
            with sqlite3.connect(self.storage_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT sg.group_id, sg.title, sg.username, sg.total_members,
                           COUNT(sm.user_id) as stored_members_count
                    FROM storage_groups sg
                    LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id
                    GROUP BY sg.group_id, sg.title, sg.username, sg.total_members
                    HAVING stored_members_count > 0
                    ORDER BY sg.created_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.error(f"خطأ في الحصول على المجموعات المتاحة: {str(e)}")
            return []
    
    def get_account_categories(self) -> List[Dict[str, Any]]:
        """الحصول على فئات الحسابات المتاحة"""
        try:
            with sqlite3.connect(self.accounts_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.name, COUNT(a.id) as account_count
                    FROM categories c
                    LEFT JOIN accounts a ON c.id = a.category_id
                    WHERE a.session_str IS NOT NULL AND a.session_str != ''
                    GROUP BY c.id, c.name
                    HAVING account_count > 0
                    ORDER BY c.created_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.error(f"خطأ في الحصول على فئات الحسابات: {str(e)}")
            return []
    
    def get_accounts_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """الحصول على حسابات فئة معينة"""
        try:
            with sqlite3.connect(self.accounts_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phone, username, session_str, device_info
                    FROM accounts
                    WHERE category_id = ? AND session_str IS NOT NULL AND session_str != ''
                    ORDER BY last_used DESC, created_at DESC
                """, (category_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.error(f"خطأ في الحصول على حسابات الفئة: {str(e)}")
            return []
    
    def get_stored_members_for_group(self, group_id: int) -> List[Dict[str, Any]]:
        """الحصول على الأعضاء المخزنين لمجموعة معينة"""
        try:
            with sqlite3.connect(self.storage_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sm.user_id, sm.username, sm.first_name, sm.last_name, sm.phone,
                           sm.last_seen, sm.is_bot, sm.is_premium
                    FROM stored_members sm
                    JOIN storage_groups sg ON sm.storage_group_id = sg.id
                    WHERE sg.group_id = ? AND sm.transfer_status = 'pending'
                    ORDER BY sm.stored_at DESC
                """, (group_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.error(f"خطأ في الحصول على الأعضاء المخزنين: {str(e)}")
            return []
    
    def add_transfer_details(self, transfer_operation_id: str, members: List[Dict[str, Any]]) -> bool:
        """إضافة تفاصيل النقل"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for member in members:
                    conn.execute(
                        "INSERT INTO transfer_details (id, transfer_operation_id, user_id, username, first_name, last_name) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            transfer_operation_id,
                            member['user_id'],
                            member.get('username', ''),
                            member.get('first_name', ''),
                            member.get('last_name', '')
                        )
                    )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في إضافة تفاصيل النقل: {str(e)}")
            return False
    
    def update_transfer_operation(self, transfer_id: str, **kwargs) -> bool:
        """تحديث عملية النقل"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
                values = list(kwargs.values()) + [transfer_id]
                
                conn.execute(
                    f"UPDATE transfer_operations SET {set_clause} WHERE id = ?",
                    values
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث عملية النقل: {str(e)}")
            return False
    
    def update_member_transfer_status(self, transfer_operation_id: str, user_id: int, 
                                    status: str, error_message: str = None) -> bool:
        """تحديث حالة نقل عضو"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE transfer_details SET transfer_status = ?, error_message = ?, transferred_at = ? WHERE transfer_operation_id = ? AND user_id = ?",
                    (status, error_message, datetime.now(), transfer_operation_id, user_id)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث حالة نقل العضو: {str(e)}")
            return False
    
    def get_transfer_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """الحصول على عمليات النقل الأخيرة"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transfer_operations
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_transfer_details(self, transfer_operation_id: str) -> List[Dict[str, Any]]:
        """الحصول على تفاصيل عملية نقل معينة"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transfer_details
                WHERE transfer_operation_id = ?
                ORDER BY transferred_at DESC
            """, (transfer_operation_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_transfer_statistics(self, transfer_operation_id: str) -> Dict[str, int]:
        """الحصول على إحصائيات عملية النقل"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN transfer_status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN transfer_status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN transfer_status = 'pending' THEN 1 ELSE 0 END) as pending
                FROM transfer_details
                WHERE transfer_operation_id = ?
            """, (transfer_operation_id,))
            result = cursor.fetchone()
            return {
                'total': result[0] or 0,
                'successful': result[1] or 0,
                'failed': result[2] or 0,
                'pending': result[3] or 0
            }