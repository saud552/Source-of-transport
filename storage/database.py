import asyncpg
import uuid
import logging
from shared_db import get_db_pool

logger = logging.getLogger(__name__)

class StorageDatabaseManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await get_db_pool()
        async with self.pool.acquire() as conn:
            await conn.execute('CREATE TABLE IF NOT EXISTS storage_categories (id UUID PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)')
            await conn.execute('CREATE TABLE IF NOT EXISTS storage_groups (id UUID PRIMARY KEY, category_id UUID NOT NULL REFERENCES storage_categories(id) ON DELETE CASCADE, group_id BIGINT NOT NULL, title TEXT NOT NULL, username TEXT, total_members INTEGER NOT NULL, storage_type TEXT NOT NULL, scan_months INTEGER, last_seen_months INTEGER, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)')
            await conn.execute('CREATE TABLE IF NOT EXISTS stored_members (id UUID PRIMARY KEY, storage_group_id UUID NOT NULL REFERENCES storage_groups(id) ON DELETE CASCADE, user_id BIGINT NOT NULL, username TEXT, first_name TEXT, last_name TEXT, phone TEXT, last_seen TIMESTAMP WITH TIME ZONE, is_bot BOOLEAN DEFAULT FALSE, is_premium BOOLEAN DEFAULT FALSE, stored_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, transfer_status TEXT DEFAULT \'pending\', UNIQUE(storage_group_id, user_id))')
            await conn.execute('CREATE TABLE IF NOT EXISTS storage_progress (id UUID PRIMARY KEY, storage_group_id UUID NOT NULL REFERENCES storage_groups(id) ON DELETE CASCADE, account_id UUID NOT NULL, total_members INTEGER DEFAULT 0, stored_members INTEGER DEFAULT 0, status TEXT DEFAULT \'running\', last_offset INTEGER DEFAULT 0, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)')

    async def get_or_create_storage_category(self, name: str) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM storage_categories WHERE name = $1", name)
            if row: return str(row['id'])
            uid = uuid.uuid4()
            await conn.execute("INSERT INTO storage_categories (id, name) VALUES ($1, $2)", uid, name)
            return str(uid)

    async def create_storage_group(self, category_id, group_id, title, username, total_members, storage_type, scan_months=0, last_seen_months=0):
        uid = uuid.uuid4()
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO storage_groups (id, category_id, group_id, title, username, total_members, storage_type, scan_months, last_seen_months) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)", uid, uuid.UUID(category_id), group_id, title, username, total_members, storage_type, scan_months, last_seen_months)
        return str(uid)

    async def bulk_store_members(self, storage_group_id, members):
        if not members: return 0
        data = [(uuid.uuid4(), uuid.UUID(storage_group_id), m['id'], m.get('username'), m.get('first_name'), m.get('last_name'), m.get('phone'), m.get('last_seen'), bool(m.get('is_bot', 0)), bool(m.get('is_premium', 0))) for m in members]
        async with self.pool.acquire() as conn:
            await conn.executemany("INSERT INTO stored_members (id, storage_group_id, user_id, username, first_name, last_name, phone, last_seen, is_bot, is_premium) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING", data)
        return len(members)

    async def update_storage_progress(self, storage_group_id, account_id, stored_members, status):
        # account_id is actually phone here sometimes, or string uuid. Handle carefully.
        try: acc_id = uuid.UUID(account_id)
        except: acc_id = uuid.NAMESPACE_DNS
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO storage_progress (id, storage_group_id, account_id, stored_members, status, updated_at) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET stored_members = $4, status = $5, updated_at = CURRENT_TIMESTAMP", uuid.uuid4(), uuid.UUID(storage_group_id), acc_id, stored_members, status)

    async def close(self):
        if self.pool: await self.pool.close()
