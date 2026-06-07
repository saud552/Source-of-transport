# Senior System Architect: TDLib Multi-Bot Patterns

## 1. Thread-Safe TDLib JSON Interface
The TDLib JSON interface (`receive`) is not thread-safe for concurrent calls.
**Pattern**: Use a dedicated background thread with a non-blocking `receive` loop that pushes events into an `asyncio.Queue`. The main async loop consumes from this queue.

## 2. Secure Session Persistence
Telegram session files (TDLib database) contain sensitive keys.
**Pattern**: ZIP the session directory, encrypt the bytes with AES-256-CBC (using PBKDF2 for key derivation), and store the encrypted blob in PostgreSQL. Use async context managers to ensure temporary files are deleted from disk immediately after encryption.

## 3. High-Concurrency Scrapers
Scraping from restricted groups requires account rotation and flood wait handling.
**Pattern**: Implement a `retry_after` parser for TDLib error 429. Use a `Semaphore` to limit concurrent scraping tasks and a pool of clients to rotate when one hits a rate limit.

## 4. Database Migration (SQLite to PostgreSQL)
SQLite's blocking I/O can starve the `python-telegram-bot` event loop under load.
**Pattern**: Use `asyncpg` for non-blocking PostgreSQL interactions. This allows the bot to handle high message volumes without latency spikes.
