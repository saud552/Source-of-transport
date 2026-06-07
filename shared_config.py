# -*- coding: utf-8 -*-
"""
الإعدادات المشتركة بين البوتين
"""

import os

# === إعدادات API المشتركة ===
API_ID = int(os.getenv('TG_API_ID', '26924046'))
API_HASH = os.getenv('TG_API_HASH', '4c6ef4cee5e129b7a674de156e2bcc15')

# === إعدادات المدراء ===
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '985612253').split(',') if x]

# === إعدادات التشفير المشتركة ===
PASSPHRASE = os.getenv('ENCRYPTION_PASSPHRASE', 'default_pass').encode()
SALT = os.getenv('ENCRYPTION_SALT', 'default_salt').encode()

# === مسارات قواعد البيانات ===
ACCOUNTS_DB_PATH = 'accounts.db'
STORAGE_DB_PATH = 'storage.db'

# === إعدادات TDLib ===
TDLIB_PATH = os.path.join(os.environ.get('PREFIX', '/data/data/com.termux/files/usr'), 'lib', 'libtdjson.so')

# === إعدادات البوتات الثلاثة ===
ADD_BOT_TOKEN = os.getenv('ADD_BOT_TOKEN', '8600331776:AAEUmbwd01q15l0bgYtQEOm_zDT7QgoiVXo')
STORAGE_BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN', '8604949254:AAEwfA5hGRKUHkvBpY8e68rJVfZljZcRwME')
TRANSFER_BOT_TOKEN = os.getenv('TRANSFER_BOT_TOKEN', '8664202831:AAFLn8vijJqr4HbQrTY7WmHDsFcAKjdb2C8')

# === إعدادات أخرى ===
SESSION_TIMEOUT = 60  # ثانية
PAGE_SIZE = 5  # عدد العناصر في الصفحة الواحدة