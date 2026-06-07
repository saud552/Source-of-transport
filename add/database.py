# -*- coding: utf-8 -*-
"""
إدارة قاعدة البيانات والحسابات
"""

import sqlite3
import uuid
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """مدير قاعدة البيانات للحسابات"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()
    
    def init_db(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول"""
        cursor = self.conn.cursor()
        
        # جدول الفئات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الحسابات
        cursor.execute('''
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
        ''')
        
        # التأكد من وجود فئة "حسابات التخزين"
        cursor.execute(
            "INSERT OR IGNORE INTO categories (id, name) VALUES (?, ?)",
            (str(uuid.uuid4()), "حسابات التخزين")
        )
        
        self.conn.commit()
    
    def create_category(self, name: str) -> str:
        """إنشاء فئة جديدة"""
        category_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO categories (id, name) VALUES (?, ?)",
            (category_id, name)
        )
        self.conn.commit()
        return category_id
    
    def get_category_by_name(self, name: str):
        """الحصول على فئة بالاسم"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE name = ?", (name,))
        return cursor.fetchone()
    
    def get_category_by_id(self, category_id: str):
        """الحصول على فئة بالمعرف"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return cursor.fetchone()
    
    def get_all_categories(self):
        """الحصول على جميع الفئات مع عدد الحسابات"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, COUNT(a.id) as account_count
            FROM categories c
            LEFT JOIN accounts a ON c.id = a.category_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """)
        return cursor.fetchall()
    
    def create_account(self, category_id: str, username: str, session_str: str, 
                      phone: str, device_info: str) -> str:
        """إنشاء حساب جديد"""
        account_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (id, category_id, username, session_str, phone, device_info) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, category_id, username, session_str, phone, device_info)
        )
        self.conn.commit()
        return account_id
    
    def get_accounts_by_category(self, category_id: str):
        """الحصول على حسابات فئة معينة"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, phone, username, created_at, last_used
            FROM accounts
            WHERE category_id = ?
            ORDER BY created_at DESC
        """, (category_id,))
        return cursor.fetchall()
    
    def get_account_by_id(self, account_id: str):
        """الحصول على حساب بالمعرف"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        return cursor.fetchone()
    
    def get_account_by_phone(self, phone: str):
        """الحصول على حساب برقم الهاتف"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE phone = ?", (phone,))
        return cursor.fetchone()
    
    def delete_account(self, account_id: str) -> bool:
        """حذف حساب"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_account_session(self, account_id: str, session_str: str) -> bool:
        """تحديث جلسة الحساب"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE accounts SET session_str = ? WHERE id = ?",
            (session_str, account_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_account_last_used(self, account_id: str):
        """تحديث آخر استخدام للحساب"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE accounts SET last_used = CURRENT_TIMESTAMP WHERE id = ?",
            (account_id,)
        )
        self.conn.commit()
    
    def get_storage_accounts(self):
        """الحصول على حسابات التخزين"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.id, a.phone, a.session_str, a.device_info
            FROM accounts a
            JOIN categories c ON a.category_id = c.id
            WHERE c.name = 'حسابات التخزين'
        """)
        return cursor.fetchall()
    
    def close(self):
        """إغلاق اتصال قاعدة البيانات"""
        if self.conn:
            self.conn.close()