# -*- coding: utf-8 -*-
"""
Production Configuration for Render
"""
import os

# API Settings
API_ID = int(os.getenv('TG_API_ID', '26924046'))
API_HASH = os.getenv('TG_API_HASH', '4c6ef4cee5e129b7a674de156e2bcc15')

# Admin Settings
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '985612253').split(',') if x]

# Encryption Settings
PASSPHRASE = os.getenv('ENCRYPTION_PASSPHRASE', 'default_pass').encode()
SALT = os.getenv('ENCRYPTION_SALT', 'default_salt').encode()



# PostgreSQL Settings (Parsed from DATABASE_URL if available)
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Parsing DATABASE_URL: postgres://user:password@host:port/dbname
    # Manually parsing to avoid Python 3.14 urllib bug with bracketed passwords triggering IPv6 validation
    dsn = DATABASE_URL.replace("postgres://", "").replace("postgresql://", "")
    auth, rest = dsn.split("@", 1)
    DB_USER, DB_PASSWORD = auth.split(":", 1)
    host_port, DB_NAME = rest.split("/", 1)
    if ":" in host_port:
        DB_HOST, port_str = host_port.split(":", 1)
        DB_PORT = int(port_str)
    else:
        DB_HOST = host_port
        DB_PORT = 5432
else:


    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    DB_NAME = os.getenv('DB_NAME', 'telegram_bots')

# Bot Tokens
ADD_BOT_TOKEN = os.getenv('ADD_BOT_TOKEN', '8600331776:AAEUmbwd01q15l0bgYtQEOm_zDT7QgoiVXo')
STORAGE_BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN', '8604949254:AAEwfA5hGRKUHkvBpY8e68rJVfZljZcRwME')
TRANSFER_BOT_TOKEN = os.getenv('TRANSFER_BOT_TOKEN', '8664202831:AAFLn8vijJqr4HbQrTY7WmHDsFcAKjdb2C8')

# Global Constants
DEFAULT_COUNTRY_CODE = os.getenv('DEFAULT_COUNTRY_CODE', '+967')
PHONE_VALIDATION_PATTERN = r'^\+\d{7,15}$'
TDLIB_PATH = os.getenv('TDLIB_PATH', os.path.join(os.getcwd(), 'libtdjson.so'))

# === Legacy Compatibility Paths ===
ACCOUNTS_DB_PATH = 'accounts.db'
STORAGE_DB_PATH = 'storage.db'
SESSION_TIMEOUT = 60
PAGE_SIZE = 5
