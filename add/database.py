import asyncpg
import uuid
import logging
from shared_db import get_db_pool

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await get_db_pool()
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id UUID PRIMARY KEY,
                    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
                    phone TEXT NOT NULL UNIQUE,
                    username TEXT,
                    session_str TEXT,
                    device_info JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_used TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def get_or_create_category(self, name: str) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM categories WHERE name = $1", name)
            if row: return str(row['id'])
            uid = uuid.uuid4()
            await conn.execute("INSERT INTO categories (id, name) VALUES ($1, $2)", uid, name)
            return str(uid)

    async def add_account(self, category_id, phone, session_str, device_info):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO accounts (id, category_id, phone, session_str, device_info) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (phone) DO UPDATE SET session_str = $4, device_info = $5",
                uuid.uuid4(), uuid.UUID(category_id), phone, session_str, device_info
            )
    
    async def get_accounts_by_category(self, category_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, phone, username, session_str, device_info FROM accounts WHERE category_id = $1", uuid.UUID(category_id))
            return [dict(r) for r in rows]

    async def close(self):
        if self.pool: await self.pool.close()
