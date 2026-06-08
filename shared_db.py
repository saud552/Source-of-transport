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

    try:
        pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            ssl=ssl_context,
            min_size=1,
            max_size=5,
            command_timeout=30
        )
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database pool created successfully with ssl_context via explicit kwargs")
        return pool
    except Exception as e:
        logger.warning(f"Failed DB connection via explicit kwargs + SSLContext: {e}")
        try:
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                ssl='require',
                min_size=1,
                max_size=5,
                command_timeout=30
            )
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info("Database pool created successfully with ssl='require' via explicit kwargs")
            return pool
        except Exception as e2:
            logger.error(f"Failed DB connection via explicit kwargs + require: {e2}")
            raise Exception(f"All DB connection attempts failed. Last error: {e2}")
