import asyncpg
import uuid
import logging
from shared_db import get_db_pool

logger = logging.getLogger(__name__)

class TransferDatabaseManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await get_db_pool()
        async with self.pool.acquire() as conn:
            await conn.execute('CREATE TABLE IF NOT EXISTS transfer_operations (id UUID PRIMARY KEY, source_group_id BIGINT NOT NULL, source_group_title TEXT NOT NULL, target_group_id BIGINT NOT NULL, target_group_title TEXT NOT NULL, account_category UUID, total_members INTEGER DEFAULT 0, transferred_members INTEGER DEFAULT 0, failed_members INTEGER DEFAULT 0, status TEXT DEFAULT \'pending\', created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP WITH TIME ZONE, completed_at TIMESTAMP WITH TIME ZONE)')
            await conn.execute('CREATE TABLE IF NOT EXISTS transfer_details (id UUID PRIMARY KEY, transfer_operation_id UUID NOT NULL REFERENCES transfer_operations(id) ON DELETE CASCADE, user_id BIGINT NOT NULL, username TEXT, first_name TEXT, last_name TEXT, transfer_status TEXT DEFAULT \'pending\', error_message TEXT, transferred_at TIMESTAMP WITH TIME ZONE)')
            await conn.execute('CREATE TABLE IF NOT EXISTS transfer_accounts (id UUID PRIMARY KEY, transfer_operation_id UUID NOT NULL REFERENCES transfer_operations(id) ON DELETE CASCADE, account_id UUID NOT NULL, account_phone TEXT NOT NULL, used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)')
        await self.init_settings_table()

    async def create_transfer_operation(self, source_group_id, source_group_title, target_group_id, target_group_title, account_category):
        uid = uuid.uuid4()
        cat_id = uuid.UUID(account_category) if account_category else None
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO transfer_operations (id, source_group_id, source_group_title, target_group_id, target_group_title, account_category) VALUES ($1, $2, $3, $4, $5, $6)", uid, source_group_id, source_group_title, target_group_id, target_group_title, cat_id)
        return str(uid)

    async def get_transfer_operations(self, limit=10):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM transfer_operations ORDER BY created_at DESC LIMIT $1", limit)
            return [dict(r) for r in rows]

    async def update_transfer_operation(self, transfer_id, **kwargs):
        if not kwargs: return True
        set_parts = [f"{k} = ${i}" for i, k in enumerate(kwargs.keys(), 1)]
        values = list(kwargs.values())
        values.append(uuid.UUID(transfer_id))
        query = f"UPDATE transfer_operations SET {', '.join(set_parts)} WHERE id = ${len(values)}"
        async with self.pool.acquire() as conn:
            await conn.execute(query, *values)
        return True

    async def update_member_transfer_status(self, transfer_operation_id, user_id, status, error_message=None):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE transfer_details SET transfer_status = $1, error_message = $2, transferred_at = CURRENT_TIMESTAMP WHERE transfer_operation_id = $3 AND user_id = $4", status, error_message, uuid.UUID(transfer_operation_id), user_id)

    async def get_available_source_groups(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT sg.group_id, sg.title, sg.username, sg.total_members, COUNT(sm.user_id) as stored_members_count FROM storage_groups sg LEFT JOIN stored_members sm ON sg.id = sm.storage_group_id GROUP BY sg.group_id, sg.title, sg.username, sg.total_members, sg.created_at ORDER BY sg.created_at DESC")
            return [dict(r) for r in rows]

    async def get_account_categories(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT c.id, c.name, COUNT(a.id) as account_count FROM categories c LEFT JOIN accounts a ON c.id = a.category_id WHERE a.session_str IS NOT NULL GROUP BY c.id, c.name")
            return [dict(r) for r in rows]

    async def get_accounts_by_category(self, category_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, phone, username, session_str, device_info FROM accounts WHERE category_id = $1", uuid.UUID(category_id))
            return [dict(r) for r in rows]

    async def get_stored_members_for_group(self, group_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT sm.user_id, sm.username, sm.first_name, sm.last_name, sm.phone FROM stored_members sm JOIN storage_groups sg ON sm.storage_group_id = sg.id WHERE sg.group_id = $1 AND sm.transfer_status = 'pending'", group_id)
            return [dict(r) for r in rows]

    async def add_transfer_details(self, transfer_operation_id, members):
        op_id = uuid.UUID(transfer_operation_id)
        data = [(uuid.uuid4(), op_id, m['user_id'], m.get('username'), m.get('first_name'), m.get('last_name')) for m in members]
        async with self.pool.acquire() as conn:
            await conn.executemany("INSERT INTO transfer_details (id, transfer_operation_id, user_id, username, first_name, last_name) VALUES ($1, $2, $3, $4, $5, $6)", data)

    async def close(self):
        if self.pool: await self.pool.close()

    async def init_settings_table(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transfer_settings (
                    id SERIAL PRIMARY KEY,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL
                )
            ''')
            # Defaults
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ('delay_min', '2') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ('delay_max', '5') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ('batch_size', '10') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ('ls_filter_enabled', 'false') ON CONFLICT DO NOTHING")
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ('ls_filter', 'all') ON CONFLICT DO NOTHING")

    async def get_setting(self, key: str) -> str:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT setting_value FROM transfer_settings WHERE setting_key = $1", key)

    async def set_setting(self, key: str, value: str):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO transfer_settings (setting_key, setting_value) VALUES ($1, $2) ON CONFLICT (setting_key) DO UPDATE SET setting_value = $2", key, value)

    # Added Storage-like methods to match Storage Bot's view
    async def get_storage_categories(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM storage_categories ORDER BY created_at DESC")
            return [dict(r) for r in rows]

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

    async def get_total_groups_in_category(self, category_id: str) -> int:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT COUNT(id) FROM storage_groups WHERE category_id = $1", uuid.UUID(category_id))
            return val or 0

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

    async def update_stored_member_transfer_status(self, member_id: int, group_db_id: str, status: str):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE stored_members SET transfer_status = $1 WHERE user_id = $2 AND storage_group_id = $3", status, member_id, uuid.UUID(group_db_id))

    async def get_stored_members_by_status(self, group_db_id: str, status: str = None):
        """If status is None, returns all members, otherwise filters by transfer_status (pending, success, failed)"""
        async with self.pool.acquire() as conn:
            query = "SELECT user_id, username, first_name, last_name FROM stored_members WHERE storage_group_id = $1"
            args = [uuid.UUID(group_db_id)]
            if status:
                query += " AND transfer_status = $2"
                args.append(status)
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def reset_stored_members_status(self, group_db_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE stored_members SET transfer_status = 'pending' WHERE storage_group_id = $1", uuid.UUID(group_db_id))
