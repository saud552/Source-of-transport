# Comprehensive Repository Architecture: Integrated Three-Bot System

## 1. Architectural Overview

This system is a high-performance Telegram automation suite comprising three specialized bots that operate in a synchronized ecosystem. The architecture is designed for scalability, security, and maximum efficiency in Telegram account handling, member scraping, and group population.

### Core Components
1.  **Add Bot (`add/`)**: Handles the lifecycle of Telegram accounts. It uses TDLib to authenticate sessions and stores them in a structured, encrypted format.
2.  **Storage Bot (`storage/`)**: A sophisticated scraping engine. It features parallel processing and account pooling to extract members from both public and restricted Telegram groups.
3.  **Transfer Bot (`transf/`)**: An orchestration engine for group growth. It utilizes the scraped data and the managed accounts to programmatically add members to target groups using safety-first batching techniques.

### Integration Layer
-   **Shared Configuration**: Centralized settings in `shared_config.py` and environment variables ensure consistency across all components.
-   **Cross-Component Database Access**: The Storage and Transfer bots directly interface with the Account database created by the Add bot.
-   **Unified Execution**: Multi-threaded entry points (`main.py`, `run_bots.py`) allow for seamless simultaneous operation.

---

## 2. Comprehensive Repository Matrix

| File Name | File Path | Core Functions / Classes | Exact Purpose & Inter-dependencies |
| :--- | :--- | :--- | :--- |
| **main.py** | `./main.py` | `run_add_bot`, `run_storage_bot`, `run_transfer_bot` | Main entry point; uses `threading` and `nest_asyncio` to run all three bots in parallel. |
| **shared_config.py** | `./shared_config.py` | Global Constants | Defines shared environment variables (API IDs, Tokens, DB paths, Admin IDs) used by all sub-modules. |
| **config.py** | `./config.py` | Global Constants | Basic configuration file (API_ID, BOT_TOKEN, OWNER_ID). |
| **requirements.txt** | `./requirements.txt` | N/A | List of Python dependencies (python-telegram-bot, pycryptodome, etc.). |
| **README.md** | `./README.md` | N/A | General project overview, features, installation, and usage instructions. |
| **FINAL_COMPATIBILITY_REPORT.md** | `./FINAL_COMPATIBILITY_REPORT.md` | N/A | Documentation of the fixes applied to ensure bots can coexist and share data. |
| **add.py** | `./add.py` | `main` | Entry point for the Add Bot; initializes `AccountManager` and starts polling. |
| **run_add_bot.py** | `./run_add_bot.py` | N/A | Helper script to run the Add Bot independently. |
| **storage.py** | `./storage.py` | `main`, `StorageBot` | Entry point for the Storage Bot; initializes components and starts polling. |
| **run_storage_bot.py** | `./run_storage_bot.py` | N/A | Helper script to run the Storage Bot independently. |
| **transf.py** | `./transf.py` | `main` | Entry point for the Transfer Bot; initializes `TransferBot` class. |
| **run_transfer_bot.py** | `./run_transfer_bot.py` | N/A | Helper script to run the Transfer Bot independently. |
| **run_bots.py** | `./run_bots.py` | `BotManager` | Advanced daemon-like script that monitors bot threads and provides health checks. |
| **start_bots.py** | `./start_bots.py` | N/A | Mirror of `run_bots.py` (Enhanced supervisor). |
| **start.py** | `./start.py` | `main` | Simple interactive menu for running bots or testing. |
| **run.py** | `./run.py` | `main` CLI | Interactive terminal interface for selectively launching components or testing the system. |
| **setup.py** | `./setup.py` | `install_requirements`, `create_directories` | Installation script for environment setup, dependency resolution, and directory bootstrapping. |
| **test_system.py** | `./test_system.py` | `test_imports`, `test_databases` | Comprehensive diagnostic tool to verify environment health and DB connectivity. |
| **td_errors_consts.py** | `./td_errors_consts.py` | Error Constants | Exhaustive dictionary of TDLib error codes (e.g., `SESSION_EXPIRED`) with documentation. |
| **standards.md** | `./standards.md` | N/A | Project-specific coding standards documentation (SOLID principles, OOP guidelines). |
| **add/__init__.py** | `add/__init__.py` | N/A | Package initialization for the Add Bot module. |
| **add/config.py** | `add/config.py` | `DEVICES` list, `tdjson` | Loads `libtdjson.so`, defines mobile device profiles, and manages Add Bot states. |
| **add/database.py** | `add/database.py` | `DatabaseManager` | Manages `accounts.db`; implements account/category CRUD. |
| **add/account_manager.py** | `add/account_manager.py` | `AccountManager` | Orchestrates the Telegram UI for account registration and session finalization. |
| **add/tdlib_client.py** | `add/tdlib_client.py` | `TDLibClient` | Encapsulates TDLib's JSON interface for authentication and session ZIP-persistence. |
| **add/encryption.py** | `add/encryption.py` | `EncryptionManager` | Provides AES-256-CBC encryption using PBKDF2 for securing session data. |
| **add/validators.py** | `add/validators.py` | `validate_phone`, `get_random_device` | Validates phone numbers/codes and selects random device fingerprints. |
| **add/keyboards.py** | `add/keyboards.py` | `get_categories_keyboard` | Generates inline keyboards for account management. |
| **add/decorators.py** | `add/decorators.py` | `owner_only` | Restricts command access to administrative users. |
| **storage/__init__.py** | `storage/__init__.py` | N/A | Package initialization for the Storage Bot module. |
| **storage/config.py** | `storage/config.py` | N/A | Configuration specific to the Storage Bot (Tokens, DB paths). |
| **storage/database.py** | `storage/database.py` | `StorageDatabaseManager` | Manages `storage.db`; tracks member scraping progress and group metadata. |
| **storage/handlers.py** | `storage/handlers.py` | `StorageHandlers` | Implements the Telegram conversation states for the scraping interface. |
| **storage/group_manager.py** | `storage/group_manager.py` | `TDLibClientPool`, `ParallelProcessor`, `PerformanceMonitor` | High-concurrency engine for member scraping with advanced resource management. |
| **storage/tdlib_client.py** | `storage/tdlib_client.py` | `StorageTDLibClient` | Optimized TDLib client for bulk history scanning and member list extraction. |
| **storage/encryption.py** | `storage/encryption.py` | `EncryptionManager` | Encryption logic for the Storage Bot component (AES-CBC). |
| **storage/export.py** | `storage/export.py` | `DataExporter` | Generates CSV reports of scraped members for external analysis. |
| **storage/utils.py** | `storage/utils.py` | `StorageUtils` | Utility functions for system info, formatting, and file management. |
| **storage/validation.py** | `storage/validation.py` | `DataValidator` | Validates inputs (phone, code, group ID) for the scraping process. |
| **storage/keyboards.py** | `storage/keyboards.py` | `get_storage_categories_keyboard` | Generates inline keyboards for scraping operations. |
| **storage/decorators.py** | `storage/decorators.py` | `owner_only` | Permission enforcement for Storage Bot commands. |
| **storage/REFACTORING_SUMMARY.md**| `storage/REFACTORING_SUMMARY.md` | N/A | Summary of improvements and optimizations made to the storage module. |
| **transf/__init__.py** | `transf/__init__.py` | N/A | Package initialization for the Transfer Bot module. |
| **transf/config.py** | `transf/config.py` | N/A | Configuration specific to the Transfer Bot (Batch sizes, delays). |
| **transf/database.py** | `transf/database.py` | `TransferDatabaseManager` | Manages `transfer.db`; bridges the gap between stored members and active accounts. |
| **transf/handlers.py** | `transf/handlers.py` | `TransferHandlers` | Implements the Telegram conversation states for initiating and monitoring transfers. |
| **transf/transfer_manager.py** | `transf/transfer_manager.py` | `TransferManager` | Manages the transfer loop, batching, and account rotation logic. |
| **transf/tdlib_client.py** | `transf/tdlib_client.py` | `TDLibClient` | Minimalist TDLib implementation focused on `addChatMember` operations. |
| **transf/utils.py** | `transf/utils.py` | `TransferUtils` | Utility functions for admin checks and text formatting in the transfer bot. |
| **transf/keyboards.py** | `transf/keyboards.py` | `TransferKeyboards` | Generates inline keyboards for transfer management. |
| **transf/main.py** | `transf/main.py` | `TransferBot` | Bootstraps the Transfer Bot application and its conversation handlers. |

---

## 3. Detailed Data & Logic Flow

### Account Lifecycle (Add Bot)
1. User provides Phone -> TDLib requests Code.
2. User provides Code/Password -> TDLib authorizes.
3. System gathers device info and ZIP-compresses the local TDLib database folder.
4. The ZIP buffer is encrypted with AES-256-CBC using PBKDF2 derived keys and stored as a Base64 string in `accounts.db`.

### Scraping Logic (Storage Bot)
1. **Visible Mode**: Uses `getSupergroupMembers` to pull from the official member list.
2. **Hidden Mode**: Uses `getChatHistory` to iterate through messages and extracts `sender_user_id` from contributors, filtered by activity time.
3. **Optimizations**: Uses a `TDLibClientPool` for account rotation, a `ParallelProcessor` for batch database operations, and a `RateLimiter` to avoid flood protections.

### Transfer Logic (Transfer Bot)
1. Loads "Pending" members from `storage.db`.
2. Loads authorized accounts from `accounts.db`.
3. Rotates accounts every X members (defined by `MAX_MEMBERS_PER_BATCH`) to distribute the "Add" actions and avoid bans.
4. Tracks `success`/`fail` status per member in the `transfer_details` table.

---

## 4. Technical Specifications

### Database Schema Details
- **accounts.db**:
    - `categories`: Metadata for grouping accounts.
    - `accounts`: Core credentials (encrypted session, phone, device fingerprint, API credentials).
- **storage.db**:
    - `storage_categories`: User-defined groups for scraped data.
    - `storage_groups`: Metadata of groups being scraped.
    - `stored_members`: Individual member records with activity metadata.
    - `storage_progress`: Real-time tracking of scraping tasks.
- **transfer.db**:
    - `transfer_operations`: Metadata for transfer tasks.
    - `transfer_details`: Granular logs of which member was transferred by which account and the outcome.
    - `transfer_accounts`: Log of accounts used in specific transfer operations.

### Security Implementations
- **Session Encryption**: Employs `AES-256-CBC` encryption for sensitive session data stored in SQLite.
- **Access Control**: Proprietary `@owner_only` decorator validates Telegram User IDs against `ADMIN_IDS` whitelist.
- **Bot Isolation**: Each bot runs its own polling loop or webhook, with distinct tokens and specialized error handling.
- **Fingerprinting**: Uses a detailed `DEVICES` list (Samsung, Google, OnePlus, Xiaomi) to emulate legitimate mobile client behavior and reduce detection.

### System Dependencies
- `python-telegram-bot`: The primary framework for bot-user interaction.
- `TDLib` (via `ctypes`): Low-level Telegram protocol interface for account automation.
- `SQLite3`: Decentralized persistent storage for accounts, members, and logs.
- `PyCryptodome`: High-level cryptographic primitives for data protection.
