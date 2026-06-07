# -*- coding: utf-8 -*-
"""
إدارة قاعدة بيانات النقل (Async PostgreSQL version)
"""

import asyncpg
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class TransferDatabaseManager:
    """مدير قاعدة بيانات النقل باستخدام PostgreSQL"""

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
            logger.info("تم الاتصال بـ PostgreSQL بنجاح (Transfer)")
        except Exception as e:
            logger.error(f"فشل الاتصال بـ PostgreSQL: {e}")
            raise
    
    async def init_db(self):
        """تهيئة جداول النقل في PostgreSQL"""
        async with self.pool.acquire() as conn:
            # جدول عمليات النقل
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_operations (
                    id UUID PRIMARY KEY,
                    source_group_id BIGINT NOT NULL,
                    source_group_title TEXT NOT NULL,
                    target_group_id BIGINT NOT NULL,
                    target_group_title TEXT NOT NULL,
                    account_category UUID,
                    total_members INTEGER DEFAULT 0,
                    transferred_members INTEGER DEFAULT 0,
                    failed_members INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE
                )
            ''')
            
            # جدول تفاصيل النقل لكل عضو
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_details (
                    id UUID PRIMARY KEY,
                    transfer_operation_id UUID NOT NULL REFERENCES transfer_operations(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    transfer_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    transferred_at TIMESTAMP WITH TIME ZONE
                )
            ''')
            
            # جدول الحسابات المستخدمة في النقل
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_accounts (
                    id UUID PRIMARY KEY,
                    transfer_operation_id UUID NOT NULL REFERENCES transfer_operations(id) ON DELETE CASCADE,
                    account_id UUID NOT NULL,
                    account_phone TEXT NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def create_transfer_operation(self, source_group_id: int, source_group_title: str,
                                target_group_id: int, target_group_title: str,
                                account_category: str) -> str:
        """إنشاء عملية نقل جديدة"""
        transfer_id = uuid.uuid4()
        cat_id = uuid.UUID(account_category) if account_category else None
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO transfer_operations (id, source_group_id, source_group_title, target_group_id, target_group_title, account_category) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                transfer_id, source_group_id, source_group_title, target_group_id, target_group_title, cat_id
            )
        return str(transfer_id)
    
    async def get_available_source_groups(self) -> List[Dict[str, Any]]:
        """الحصول على المجموعات المتاحة للنقل من قاعدة بيانات التخزين"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT sg.group_id, sg.title, sg.username, sg.total_members,
                       COUNT(sm.user_id) as stored_members_count
                FROM storage_groups sg
                LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id
                GROUP BY sg.group_id, sg.title, sg.username, sg.total_members
                HAVING COUNT(sm.user_id) > 0
                ORDER BY sg.created_at DESC
            """)
            return [dict(row) for row in rows]
    
    async def get_account_categories(self) -> List[Dict[str, Any]]:
        """الحصول على فئات الحسابات المتاحة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.id, c.name, COUNT(a.id) as account_count
                FROM categories c
                LEFT JOIN accounts a ON c.id = a.category_id
                WHERE a.session_str IS NOT NULL AND a.session_str != ''
                GROUP BY c.id, c.name
                HAVING COUNT(a.id) > 0
            """)
            return [dict(row) for row in rows]
    
    async def get_accounts_by_category(self, category_id: str) -> List[Dict[str, Any]]:
        """الحصول على حسابات فئة معينة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, phone, username, session_str, device_info
                FROM accounts
                WHERE category_id = $1 AND session_str IS NOT NULL AND session_str != ''
            """, uuid.UUID(category_id))
            return [dict(row) for row in rows]
    
    async def get_stored_members_for_group(self, group_id: int) -> List[Dict[str, Any]]:
        """الحصول على الأعضاء المخزنين لمجموعة معينة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sm.user_id, sm.username, sm.first_name, sm.last_name, sm.phone
                FROM stored_members sm
                JOIN storage_groups sg ON sm.storage_group_id = sg.id
                WHERE sg.group_id = $1 AND sm.transfer_status = 'pending'
            """, group_id)
            return [dict(row) for row in rows]
    
    async def add_transfer_details(self, transfer_operation_id: str, members: List[Dict[str, Any]]) -> bool:
        """إضافة تفاصيل النقل"""
        try:
            op_id = uuid.UUID(transfer_operation_id)
            data = [
                (uuid.uuid4(), op_id, m['user_id'], m.get('username'), m.get('first_name'), m.get('last_name'))
                for m in members
            ]
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO transfer_details (id, transfer_operation_id, user_id, username, first_name, last_name) VALUES ($1, $2, $3, $4, $5, $6)",
                    data
                )
            return True
        except Exception as e:
            logger.error(f"خطأ في إضافة تفاصيل النقل: {e}")
            return False
    
    async def update_transfer_operation(self, transfer_id: str, **kwargs) -> bool:
        """تحديث عملية النقل"""
        if not kwargs: return True
        try:
            set_parts = []
            values = []
            for i, (key, value) in enumerate(kwargs.items(), 1):
                set_parts.append(f"{key} = ${i}")
                values.append(value)

            values.append(uuid.UUID(transfer_id))
            query = f"UPDATE transfer_operations SET {', '.join(set_parts)} WHERE id = ${len(values)}"

            async with self.pool.acquire() as conn:
                await conn.execute(query, *values)
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث عملية النقل: {e}")
            return False
    
    async def update_member_transfer_status(self, transfer_operation_id: str, user_id: int,
                                    status: str, error_message: str = None) -> bool:
        """تحديث حالة نقل عضو"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE transfer_details SET transfer_status = $1, error_message = $2, transferred_at = CURRENT_TIMESTAMP WHERE transfer_operation_id = $3 AND user_id = $4",
                    status, error_message, uuid.UUID(transfer_operation_id), user_id
                )
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث حالة نقل العضو: {e}")
            return False
    
    async def get_transfer_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """الحصول على عمليات النقل الأخيرة"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM transfer_operations ORDER BY created_at DESC LIMIT $1", limit)
            return [dict(row) for row in rows]

    async def close(self):
        if self.pool:
            await self.pool.close()
