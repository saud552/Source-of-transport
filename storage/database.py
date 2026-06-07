# -*- coding: utf-8 -*-
"""
إدارة قاعدة بيانات التخزين (Async PostgreSQL version)
"""

import asyncpg
import uuid
import logging
from typing import Optional, List, Dict, Any
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class StorageDatabaseManager:
    """مدير قاعدة بيانات التخزين باستخدام PostgreSQL"""

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
            logger.info("تم الاتصال بـ PostgreSQL بنجاح (Storage)")
        except Exception as e:
            logger.error(f"فشل الاتصال بـ PostgreSQL: {e}")
            raise
    
    async def init_db(self):
        """تهيئة جداول التخزين في PostgreSQL"""
        async with self.pool.acquire() as conn:
            # إنشاء جدول فئات التخزين
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_categories (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المجموعات المخزنة
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_groups (
                    id UUID PRIMARY KEY,
                    category_id UUID NOT NULL REFERENCES storage_categories(id) ON DELETE CASCADE,
                    group_id BIGINT NOT NULL,
                    title TEXT NOT NULL,
                    username TEXT,
                    total_members INTEGER NOT NULL,
                    storage_type TEXT NOT NULL,
                    scan_months INTEGER,
                    last_seen_months INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول الأعضاء المخزنين
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS stored_members (
                    id UUID PRIMARY KEY,
                    storage_group_id UUID NOT NULL REFERENCES storage_groups(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    last_seen TIMESTAMP WITH TIME ZONE,
                    is_bot BOOLEAN DEFAULT FALSE,
                    is_premium BOOLEAN DEFAULT FALSE,
                    stored_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    transfer_status TEXT DEFAULT 'pending',
                    UNIQUE(storage_group_id, user_id)
                )
            ''')
            
            # جدول تتبع التقدم
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_progress (
                    id UUID PRIMARY KEY,
                    storage_group_id UUID NOT NULL REFERENCES storage_groups(id) ON DELETE CASCADE,
                    account_id UUID NOT NULL,
                    total_members INTEGER DEFAULT 0,
                    stored_members INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    last_offset INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def get_or_create_storage_category(self, category_name: str) -> str:
        """إنشاء أو استرجاع فئة التخزين"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM storage_categories WHERE name = $1", category_name)
            if row:
                return str(row['id'])
            
            category_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO storage_categories (id, name) VALUES ($1, $2)",
                category_id, category_name
            )
            return str(category_id)
    
    async def create_storage_group(self, category_id: str, group_id: int, title: str,
                           username: str, total_members: int, storage_type: str,
                           scan_months: int = 0, last_seen_months: int = 0) -> str:
        """إنشاء مجموعة تخزين جديدة"""
        storage_group_id = uuid.uuid4()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO storage_groups (id, category_id, group_id, title, username, total_members, storage_type, scan_months, last_seen_months) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                storage_group_id, uuid.UUID(category_id), group_id, title, username, total_members, storage_type, scan_months, last_seen_months
            )
        return str(storage_group_id)
    
    async def get_storage_categories(self) -> List[Dict[str, Any]]:
        """الحصول على جميع فئات التخزين"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM storage_categories ORDER BY created_at DESC")
            return [dict(row) for row in rows]
    
    async def get_storage_groups_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """الحصول على مجموعات فئة معينة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM storage_groups
                WHERE category_id = $1
                ORDER BY created_at DESC
            """, uuid.UUID(category_id))
            return [dict(row) for row in rows]
    
    async def store_member(self, storage_group_id: str, user_info: Dict[str, Any]) -> bool:
        """تخزين عضو في قاعدة البيانات"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO stored_members (id, storage_group_id, user_id, username, first_name, last_name, phone, last_seen, is_bot, is_premium)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                       ON CONFLICT (storage_group_id, user_id) DO NOTHING""",
                    uuid.uuid4(),
                    uuid.UUID(storage_group_id),
                    user_info['id'],
                    user_info.get('username'),
                    user_info.get('first_name'),
                    user_info.get('last_name'),
                    user_info.get('phone'),
                    user_info.get('last_seen'),
                    bool(user_info.get('is_bot', 0)),
                    bool(user_info.get('is_premium', 0))
                )
            return True
        except Exception as e:
            logger.error(f"خطأ في تخزين العضو: {e}")
            return False

    async def update_storage_progress(self, storage_group_id: str, account_id: str,
                              stored_members: int, status: str) -> bool:
        """تحديث تقدم التخزين"""
        try:
            # ملاحظة: account_id يجب أن يكون UUID صالح
            acc_id = uuid.UUID(account_id) if account_id != 'system' else uuid.NAMESPACE_DNS
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO storage_progress (id, storage_group_id, account_id, stored_members, status, updated_at)
                       VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                       ON CONFLICT (id) DO UPDATE SET stored_members = $4, status = $5, updated_at = CURRENT_TIMESTAMP""",
                    uuid.uuid4(), uuid.UUID(storage_group_id), acc_id, stored_members, status
                )
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث تقدم التخزين: {e}")
            return False

    async def get_active_storage_jobs(self) -> List[Dict[str, Any]]:
        """الحصول على مهام التخزين النشطة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sg.title, sp.status, sp.stored_members, sp.total_members
                FROM storage_progress sp
                JOIN storage_groups sg ON sp.storage_group_id = sg.id
                WHERE sp.status IN ('running', 'paused')
            """)
            return [dict(row) for row in rows]

    async def close(self):
        """إغلاق مجمع اتصالات قاعدة البيانات"""
        if self.pool:
            await self.pool.close()
