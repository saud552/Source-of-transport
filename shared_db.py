import asyncpg
import os
import logging
import asyncio
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger("Database")

async def get_db_pool():
    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        dsn = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Try connecting with SSL first (Production)
    try:
        pool = await asyncpg.create_pool(dsn, ssl='require', min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return pool
    except Exception as e:
        logger.warning(f"SSL connection failed, trying without SSL: {e}")
        return await asyncpg.create_pool(dsn, min_size=1, max_size=5)
