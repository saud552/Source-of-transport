# Microscopic Diagnostic Report: Storage Bot Module

## 1. Architectural Overview
The Storage Bot module is responsible for scraping Telegram group members using authorized accounts. It utilizes a `TDLibClientPool` for account management and a `ParallelProcessor` for batch data storage. However, several critical flaws were identified in its implementation of concurrency, resource safety, and official TDLib protocol adherence.

---

## 2. Critical Errors & Bugs

### [P1] Missing Core Functionality (`start_visible_storage`)
In `storage/handlers.py`, the code attempts to call `self.group_manager.start_visible_storage`. However, this method is **completely absent** from `storage/group_manager.py`.
- **Impact:** The "Visible Scraping" feature will crash the bot immediately upon invocation.

### [P1] Thread-Unsafe `receive` Violation
Methods like `get_user_info_fast`, `get_chat`, and `get_chat_full_info` in `storage/tdlib_client.py` call the blocking `receive` function directly.
- **Violation:** The [TDLib JSON Client API](https://core.telegram.org/tdlib/docs/td__json__client_8h.html) strictly states that the returned pointer is owned by TDLib and is only valid until the next call in the *same thread*.
- **Impact:** Concurrent calls from multiple workers/async tasks will cause pointer corruption, "stolen" events, and segmentation faults.

### [P1] Missing Flood Wait (429) & Error Logic
The scraping loops (specifically in `get_members_from_messages_batch`) lack explicit handling for TDLib `error` types with code `429` (Flood Wait).
- **Impact:** When Telegram triggers a flood wait, the bot will likely ignore it, continue sending requests, and eventually cause the scraping accounts to be permanently banned.

### [P1] Improper Pagination & History Handling
In `get_members_from_messages_batch`, the loop for history scanning uses `from_message_id`. If `history_result` returns an error or empty list, the logic for `from_message_id = messages[-1]['id']` lacks sufficient safety checks.
- **Impact:** Potential for infinite loops or premature termination of the scraping process.

---

## 3. Architectural & Database Improvements

### High-Volume Data Optimization
- **Transition to PostgreSQL:** Current SQLite implementation uses blocking calls (e.g., `sqlite3.connect` inside async methods). Moving to `asyncpg` is mandatory for high-concurrency member storage.
- **Bulk Inserts:** `store_member` performs a single `INSERT OR IGNORE` per user. For batches of 500+ members, this should be refactored into a `executemany` or PostgreSQL `COPY` command to prevent I/O bottlenecks.

### Resource & Memory Management
- **Zombie Directory Prevention:** Temporary directories created in `initialize()` remain on disk if `close()` is not reached. Implementation of a context manager or `__del__` purge logic is required.
- **Client Queueing:** The `TDLibClientPool` should be redesigned to use a single dedicated reader thread per client that populates an `asyncio.Queue`, ensuring thread-safety.

---

## 4. Prioritized Action Plan

| Priority | Finding | Action |
| :--- | :--- | :--- |
| **[P1]** | **Absent `start_visible_storage`** | Implement the missing logic using `getChatMembers`. |
| **[P1]** | **Race Condition on `receive`** | Refactor TDLib client to use a single-consumer event queue per instance. |
| **[P1]** | **Blocking Database I/O** | Migrate `StorageDatabaseManager` to `asyncpg` (PostgreSQL). |
| **[P1]** | **Flood Wait Ignorance** | Implement a global `error` handler that parses `retry_after` seconds. |
| **[P2]** | **Inefficient single-row inserts** | Refactor member storage to use bulk batch insertion. |
| **[P2]** | **Manual directory cleanup** | Use Python's `with` statement or async context managers for clients. |
| **[P3]** | **Hardcoded scraping limits** | Move `max_messages = 10000` to a configurable setting. |

---
**Status:** Diagnostic Complete. Awaiting remediation commands.
