# Comprehensive Repository Architecture: Integrated Three-Bot System

## 1. Architectural Overview

This system is a high-performance Telegram automation suite comprising three specialized bots that operate in a synchronized ecosystem. The architecture is designed for scalability, security, and maximum efficiency in Telegram account handling, member scraping, and group population.

### Core Components
1.  **Add Bot (`add/`)**: Handles the lifecycle of Telegram accounts. It uses TDLib to authenticate sessions and stores them in a structured, AES-256-CBC encrypted format within PostgreSQL.
2.  **Storage Bot (`storage/`)**: A sophisticated scraping engine. It features parallel processing and account pooling to extract members from both public and restricted Telegram groups.
3.  **Transfer Bot (`transf/`)**: An orchestration engine for group growth. It utilizes the scraped data and the managed accounts to programmatically add members to target groups using safety-first batching techniques.

### Integration Layer
-   **Shared Configuration**: Centralized settings in `shared_config.py` and environment variables ensure consistency across all components.
-   **Async PostgreSQL Backbone**: The system has been migrated to a highly concurrent PostgreSQL backend using `asyncpg` for non-blocking I/O.
-   **Thread-Safe TDLib Handling**: Implements a dedicated background thread for the TDLib `receive` loop, dispatching events to an `asyncio.Queue` for thread-safe asynchronous processing.
-   **Unified Execution**: Multi-threaded entry points (`main.py`, `run_bots.py`) allow for seamless simultaneous operation.

---

## 2. Comprehensive Repository Matrix

| File Name | File Path | Core Functions / Classes | Exact Purpose & Inter-dependencies |
| :--- | :--- | :--- | :--- |
| **main.py** | `./main.py` | `run_add_bot`, `run_storage_bot`, `run_transfer_bot` | Main entry point; uses `threading` and `nest_asyncio` to run all three bots in parallel. |
| **shared_config.py** | `./shared_config.py` | Global Constants | Defines shared PostgreSQL credentials, encryption keys, and internationalization settings (country codes). |
| **devices.json** | `./devices.json` | JSON Data | Externalized database of mobile device fingerprints for legitimate client emulation. |
| **config.py** | `./config.py` | Global Constants | Basic configuration file (API_ID, BOT_TOKEN, OWNER_ID). |
| **requirements.txt** | `./requirements.txt` | N/A | List of dependencies including `asyncpg` for PostgreSQL and `pycryptodome` for AES encryption. |
| **README.md** | `./README.md` | N/A | General project overview, features, installation, and usage instructions. |
| **FINAL_COMPATIBILITY_REPORT.md** | `./FINAL_COMPATIBILITY_REPORT.md` | N/A | Documentation of the fixes applied to ensure bots can coexist and share data. |
| **add.py** | `./add.py` | `main` | Wrapper to launch the Add Bot. |
| **storage.py** | `./storage.py` | `main`, `StorageBot` | Entry point for the Storage Bot; initializes components and starts polling. |
| **transf.py** | `./transf.py` | `main` | Entry point for the Transfer Bot; initializes `TransferBot` class. |
| **run_bots.py** | `./run_bots.py` | `BotManager` | Advanced daemon-like script that monitors bot threads and provides health checks. |
| **test_system.py** | `./test_system.py` | `test_imports`, `test_database` | Diagnostic tool updated to verify PostgreSQL connectivity and AES library availability. |
| **standards.md** | `./standards.md` | N/A | Project-specific coding standards documentation. |
| **add/config.py** | `add/config.py` | Dynamic Loader | Loads `devices.json` and `libtdjson.so`; manages Add Bot conversation states. |
| **add/database.py** | `add/database.py` | `DatabaseManager` | Asynchronous PostgreSQL manager; handles account and category persistence with UUID support. |
| **add/account_manager.py**| `add/account_manager.py`| `AccountManager` | Orchestrates async registration flow, including session encryption (AES-256) and resource cleanup. |
| **add/tdlib_client.py** | `add/tdlib_client.py` | `TDLibClient` | Thread-safe TDLib wrapper using a dedicated receiver thread and `asyncio.Queue`. Supports automatic directory purging. |
| **add/encryption.py** | `add/encryption.py` | `EncryptionManager` | Implements high-level AES-256-CBC encryption for session bytes using PBKDF2. |
| **add/validators.py** | `add/validators.py` | `validate_phone` | Decoupled validation logic using configurable country codes and patterns. |
| **storage/database.py** | `storage/database.py` | `StorageDatabaseManager` | Manages scraping progress and member metadata. |
| **storage/group_manager.py**| `storage/group_manager.py`| `TDLibClientPool`, `ParallelProcessor` | High-concurrency engine for member scraping with advanced resource management. |
| **transf/transfer_manager.py**| `transf/transfer_manager.py`| `TransferManager` | Manages the transfer loop, batching, and account rotation logic. |

---

## 3. Detailed Data & Logic Flow

### Account Lifecycle (Add Bot)
1. User provides Phone -> `TDLibClient` requests Code via dedicated background thread.
2. User provides Code/Password -> TDLib authorizes.
3. System gathers device info from `devices.json` and ZIP-compresses the local TDLib database folder.
4. The raw ZIP bytes are encrypted with **AES-256-CBC** using a key derived from `PASSPHRASE` via PBKDF2.
5. The encrypted payload is Base64 encoded and stored in the **PostgreSQL** `accounts` table.
6. Temporary session directories are immediately purged from disk upon completion or failure.

### Scraping Logic (Storage Bot)
1. **Visible Mode**: Uses `getSupergroupMembers` to pull from the official list.
2. **Hidden Mode**: Uses `getChatHistory` to scan active senders.
3. **Optimizations**: Uses a `Semaphore` to limit concurrent tasks and a `RateLimiter`.

### Transfer Logic (Transfer Bot)
1. Loads "Pending" members and authorized accounts.
2. Rotates accounts every X members (batch size) to minimize detection.
3. Tracks detailed success/failure status per member.

---

## 4. Technical Specifications

### Database Schema (PostgreSQL)
- **Tables**: `categories` (UUID), `accounts` (UUID, category_id, session_str, phone, device_info).
- **Integrity**: Foreign keys with `ON DELETE CASCADE` and timezone-aware timestamps.

### Security Implementation
- **Data-at-Rest Protection**: All Telegram sessions are encrypted with AES-256 before database insertion.
- **Memory/Thread Safety**: Strict isolation of the TDLib `receive` loop prevents memory corruption in the JSON interface.
- **Resource Management**: Uses async Context Managers (`__aenter__`/`__aexit__`) to guarantee removal of sensitive temporary files.

### System Dependencies
- `python-telegram-bot`: Bot API interface.
- `TDLib` (JSON Interface): Low-level automation.
- `asyncpg`: High-performance asynchronous PostgreSQL driver.
- `PyCryptodome`: Cryptographic operations.
