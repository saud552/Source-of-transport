# Microscopic Diagnostic Report: Account Registration Bot (`add/`)

## 1. Architectural Overview
This report provides a detailed analysis of the `add/` module, responsible for Telegram account registration and session management via TDLib. The analysis focused on security, concurrency, and adherence to official TDLib JSON interface contracts.

---

## 2. Critical Errors & Bugs

### [P1] Thread-Unsafe `receive` Violation (Memory Corruption Risk)
In `add/tdlib_client.py`, the `_event_loop` method runs a continuous `receive` loop in a background thread via `asyncio.to_thread`. Concurrently, methods like `get_me` and `_wait_for_state` invoke `receive` again in separate threads.
- **Violation:** The [TDLib JSON Client API](https://core.telegram.org/tdlib/docs/td__json__client_8h.html) strictly states: *"The returned pointer is owned by TDLib and will be deallocated by the next call to any JSON function in the same thread."*
- **Impact:** Calling `receive` from multiple threads will cause pointer corruption, "stolen" JSON events (where one thread consumes data intended for another), or segmentation faults.

### [P1] Plaintext Session Storage (Security Breach)
While `add/encryption.py` implements a PBKDF2-based AES-256-CBC encryption scheme, it is **never instantiated or called** in `account_manager.py`.
- **Evidence:** In `finalize_account_registration`, the session ZIP-compressed folder is Base64 encoded and inserted directly into the `session_str` column of `accounts.db`.
- **Impact:** All registered Telegram accounts are stored in an unencrypted state. If the database file is accessed, every account can be instantly hijacked.

### [P1] Event Loop Starvation (Blocking SQLite)
The `DatabaseManager` uses the standard synchronous `sqlite3` library. Operations like `conn.commit()` and `cursor.execute()` are performed directly within `async` handlers in `AccountManager`.
- **Impact:** This blocks the main `asyncio` thread during disk I/O, causing the bot to become unresponsive to other users or Telegram signals during registration or account checking.

### [P2] Missing Environmental Dependencies
`add/encryption.py` relies on `pycryptodome` (`from Crypto.Cipher import AES`), which is absent from `requirements.txt`. The bot will fail to start in a standard clean environment.

---

## 3. Architectural & Security Improvements

### Centralized Event Dispatching
The `TDLibClient` should be redesigned to have exactly **one** reader thread calling `receive` and pushing events into an `asyncio.Queue`. All other methods must consume from this queue rather than calling `receive` directly.

### Asynchronous Database Driver
Refactor the storage layer to use `aiosqlite`. This moves database operations to a separate thread while maintaining a non-blocking `async` interface for the bot.

### Encryption Lifecycle Integration
Instantiate the `EncryptionManager` using the `PASSPHRASE` and `SALT` defined in `shared_config.py`. Apply this to the raw ZIP bytes before Base64 encoding in the saving flow, and vice-versa in the loading flow.

### Internationalization of Validators
`add/validators.py` hardcodes the `+967` prefix for numbers starting with `0`. This should be replaced with a more flexible logic using a library like `phonenumbers` or move the default prefix to `shared_config.py`.

---

## 4. Prioritized Action Plan

| Priority | Finding | Action |
| :--- | :--- | :--- |
| **[P1]** | **Concurrency Race on `receive`** | Redesign client to use a single consumer queue. |
| **[P1]** | **Unencrypted Session Storage** | Integrate `EncryptionManager` into the registration flow. |
| **[P1]** | **Blocking Database Calls** | Migrate `DatabaseManager` to `aiosqlite`. |
| **[P2]** | **Missing Dependency** | Add `pycryptodome` to `requirements.txt`. |
| **[P2]** | **Zombie Temp Directories** | Implement a global cleanup signal handler for `mkdtemp` paths. |
| **[P3]** | **Hardcoded Device Profiles** | Move `DEVICES` in `config.py` to an external `devices.json`. |

---
**Status:** Diagnostic Complete. Awaiting remediation commands.
