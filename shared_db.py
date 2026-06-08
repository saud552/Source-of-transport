import asyncpg
import os
import logging
import asyncio
import ssl
from shared_config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger("Database")





async def get_db_pool():
    """Returns a new connection pool for the current event loop, with robust SSL fallback."""
    dsn = os.getenv('DATABASE_URL', '')

    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # We will attempt 3 modes:
    # 1. Custom SSL context (for external connections with self-signed certs)
    # 2. 'require' (for standard external secure connections)
    # 3. False (for internal Render connections which drop connections if SSL is attempted)
    ssl_modes = [ssl_context, 'require', False]

    for mode in ssl_modes:
        try:
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                ssl=mode,
                min_size=1,
                max_size=5,
                command_timeout=30
            )
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info(f"Database pool created successfully with ssl={mode}")
            return pool
        except Exception as e:
            logger.warning(f"Failed DB connection with ssl={mode}: {e}")
            await asyncio.sleep(0.5)

    raise Exception("All DB connection attempts failed.")
