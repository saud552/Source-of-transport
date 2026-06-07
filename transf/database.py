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
