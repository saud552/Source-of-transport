import asyncpg
import os
import logging
import asyncio
import ssl
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger("Database")

async def get_db_pool():
    """Returns a new connection pool for the current event loop."""
    dsn = os.getenv('DATABASE_URL')
    if not dsn:
        dsn = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


    # Render requires SSL
    if 'render.com' in dsn or 'DB_HOST' in os.environ:
        ssl_mode = ssl.create_default_context()
        ssl_mode.check_hostname = False
        ssl_mode.verify_mode = ssl.CERT_NONE
    else:
        ssl_mode = None



    for attempt in range(3):
        try:
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                ssl=ssl_mode,
                min_size=1,
                max_size=5,
                command_timeout=60
            )

            # Connectivity check
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info(f"Database pool created successfully for loop {id(asyncio.get_running_loop())}")
            return pool
        except Exception as e:
            logger.error(f"Failed to create DB pool (attempt {attempt+1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2)
            else:
                raise
