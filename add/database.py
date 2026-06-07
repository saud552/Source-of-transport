# -*- coding: utf-8 -*-
"""
إدارة قاعدة البيانات والحسابات (PostgreSQL version)
"""

import asyncpg
import uuid
import logging
from typing import Optional, List, Dict, Any
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class DatabaseManager:
    """مدير قاعدة البيانات للحسابات باستخدام PostgreSQL"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """إنشاء مجمع اتصالات قاعدة البيانات"""
        try:
            self.pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            await self.init_db()
            logger.info("تم الاتصال بـ PostgreSQL بنجاح")
        except Exception as e:
            logger.error(f"فشل الاتصال بـ PostgreSQL: {e}")
            raise

    async def init_db(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول"""
        async with self.pool.acquire() as conn:
            # جدول الفئات
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id UUID PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول الحسابات
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id UUID PRIMARY KEY,
                    category_id UUID NOT NULL,
                    username TEXT,
                    session_str TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    device_info TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP WITH TIME ZONE,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                )
            ''')

            # التأكد من وجود فئة "حسابات التخزين"
            await conn.execute(
                "INSERT INTO categories (id, name) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
                uuid.uuid4(), "حسابات التخزين"
            )
    
    async def create_category(self, name: str) -> str:
        """إنشاء فئة جديدة"""
        category_id = uuid.uuid4()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO categories (id, name) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
                category_id, name
            )
        return str(category_id)
    
    async def get_category_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """الحصول على فئة بالاسم"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM categories WHERE name = $1", name)
            return dict(row) if row else None
    
    async def get_category_by_id(self, category_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على فئة بالمعرف"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM categories WHERE id = $1", uuid.UUID(category_id))
            return dict(row) if row else None
    
    async def get_all_categories(self) -> List[Dict[str, Any]]:
        """الحصول على جميع الفئات مع عدد الحسابات"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.id, c.name, COUNT(a.id) as account_count
                FROM categories c
                LEFT JOIN accounts a ON c.id = a.category_id
                GROUP BY c.id, c.name
                ORDER BY c.created_at DESC
            """)
            return [dict(row) for row in rows]
    
    async def create_account(self, category_id: str, username: str, session_str: str,
                      phone: str, device_info: str) -> str:
        """إنشاء حساب جديد"""
        account_id = uuid.uuid4()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO accounts (id, category_id, username, session_str, phone, device_info) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                account_id, uuid.UUID(category_id), username, session_str, phone, device_info
            )
        return str(account_id)
    
    async def get_accounts_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """الحصول على حسابات فئة معينة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, phone, username, created_at, last_used, session_str, device_info
                FROM accounts
                WHERE category_id = $1
                ORDER BY created_at DESC
            """, uuid.UUID(category_id))
            return [dict(row) for row in rows]
    
    async def get_account_by_id(self, account_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على حساب بالمعرف"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM accounts WHERE id = $1", uuid.UUID(account_id))
            return dict(row) if row else None
    
    async def get_account_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """الحصول على حساب برقم الهاتف"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM accounts WHERE phone = $1", phone)
            return dict(row) if row else None
    
    async def delete_account(self, account_id: str) -> bool:
        """حذف حساب"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM accounts WHERE id = $1", uuid.UUID(account_id))
            return "DELETE 1" in result
    
    async def update_account_session(self, account_id: str, session_str: str) -> bool:
        """تحديث جلسة الحساب"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE accounts SET session_str = $1 WHERE id = $2",
                session_str, uuid.UUID(account_id)
            )
            return "UPDATE 1" in result
    
    async def update_account_last_used(self, account_id: str):
        """تحديث آخر استخدام للحساب"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE accounts SET last_used = CURRENT_TIMESTAMP WHERE id = $1",
                uuid.UUID(account_id)
            )
    
    async def get_storage_accounts(self) -> List[Dict[str, Any]]:
        """الحصول على حسابات التخزين"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT a.id, a.phone, a.session_str, a.device_info
                FROM accounts a
                JOIN categories c ON a.category_id = c.id
                WHERE c.name = 'حسابات التخزين'
            """)
            return [dict(row) for row in rows]
    
    async def close(self):
        """إغلاق مجمع اتصالات قاعدة البيانات"""
        if self.pool:
            await self.pool.close()
