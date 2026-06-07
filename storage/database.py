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
        await self.init_settings_table()

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

    async def get_account_categories(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT c.id, c.name, COUNT(a.id) as account_count FROM categories c LEFT JOIN accounts a ON c.id = a.category_id AND a.session_str IS NOT NULL GROUP BY c.id, c.name ORDER BY c.created_at DESC")
            return [dict(r) for r in rows]

    async def get_storage_categories(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM storage_categories ORDER BY created_at DESC")
            return [dict(r) for r in rows]

    async def get_accounts_by_category(self, category_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, phone, session_str, device_info FROM accounts WHERE category_id = $1 AND session_str IS NOT NULL AND is_active = TRUE", uuid.UUID(category_id))
            return [dict(r) for r in rows]

    async def update_storage_group_total(self, group_id: str, new_total: int):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE storage_groups SET total_members = $1 WHERE id = $2", new_total, uuid.UUID(group_id))

    async def get_storage_category_stats(self, category_id: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT
                    COUNT(DISTINCT sg.id) as total_groups,
                    COUNT(sm.id) as total_members,
                    COUNT(sm.id) FILTER (WHERE sm.transfer_status = 'success') as total_transferred,
                    COUNT(sm.id) FILTER (WHERE sm.transfer_status = 'pending') as total_pending
                FROM storage_groups sg
                LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id
                WHERE sg.category_id = $1
            ''', uuid.UUID(category_id))
            return dict(row) if row else {'total_groups': 0, 'total_members': 0, 'total_transferred': 0, 'total_pending': 0}

    async def get_groups_by_category(self, category_id: str, offset: int = 0, limit: int = 40):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT sg.id, sg.title, COUNT(sm.id) as member_count
                FROM storage_groups sg
                LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id
                WHERE sg.category_id = $1
                GROUP BY sg.id, sg.title, sg.created_at
                ORDER BY sg.created_at DESC
                LIMIT $2 OFFSET $3
            ''', uuid.UUID(category_id), limit, offset)
            return [dict(r) for r in rows]

    async def get_total_groups_in_category(self, category_id: str) -> int:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT COUNT(id) FROM storage_groups WHERE category_id = $1", uuid.UUID(category_id))
            return val or 0

    async def get_storage_group_details(self, group_id: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT
                    sg.id, sg.title, sg.username, sg.group_id, sg.storage_type,
                    COUNT(sm.id) as total_members,
                    COUNT(sm.id) FILTER (WHERE sm.transfer_status = 'success') as total_transferred,
                    COUNT(sm.id) FILTER (WHERE sm.transfer_status = 'pending') as total_pending
                FROM storage_groups sg
                LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id
                WHERE sg.id = $1
                GROUP BY sg.id, sg.title, sg.username, sg.group_id, sg.storage_type
            ''', uuid.UUID(group_id))
            return dict(row) if row else None

    async def delete_storage_group(self, group_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM storage_groups WHERE id = $1", uuid.UUID(group_id))

    async def clear_group_members(self, group_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM stored_members WHERE storage_group_id = $1", uuid.UUID(group_id))

    async def init_settings_table(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS storage_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )
            ''')
            # Insert defaults if not exist
            await conn.execute("INSERT INTO storage_settings (setting_key, setting_value) VALUES ('monthly_duration', '3') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO storage_settings (setting_key, setting_value) VALUES ('message_count', '100000') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO storage_settings (setting_key, setting_value) VALUES ('last_seen_filter', 'all') ON CONFLICT DO NOTHING")

    async def get_setting(self, key: str) -> str:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT setting_value FROM storage_settings WHERE setting_key = $1", key)
            return val

    async def set_setting(self, key: str, value: str):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO storage_settings (setting_key, setting_value) VALUES ($1, $2) ON CONFLICT (setting_key) DO UPDATE SET setting_value = $2", key, value)
