# -*- coding: utf-8 -*-
"""
إعدادات التطبيق ومتغيرات البيئة
"""

import os
import json
import logging
import ctypes
import sys

# ========== إعدادات التهيئة ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  
)
logger = logging.getLogger(__name__)

# استيراد الإعدادات المشتركة
from shared_config import (
    API_ID, API_HASH, ADMIN_IDS, PASSPHRASE, SALT, 
    ACCOUNTS_DB_PATH, SESSION_TIMEOUT, PAGE_SIZE
)

# === إعدادات التطبيق ===
BOT_TOKEN = os.getenv('ADD_BOT_TOKEN', '8600331776:AAEUmbwd01q15l0bgYtQEOm_zDT7QgoiVXo')
DB_PATH = ACCOUNTS_DB_PATH

# === تحميل قائمة الأجهزة من ملف خارجي ===
DEVICES = []
devices_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'devices.json')

try:
    if os.path.exists(devices_file):
        with open(devices_file, 'r', encoding='utf-8') as f:
            DEVICES = json.load(f)
        logger.info(f"Loaded {len(DEVICES)} device profiles from devices.json")
    else:
        logger.warning("devices.json not found, using minimal fallback profile")
        DEVICES = [{'device_model': 'Generic Android', 'system_version': 'Android 14', 'app_version': 'Telegram 10.0', 'lang_code': 'en', 'lang_pack': 'android'}]
except Exception as e:
    logger.error(f"Failed to load devices.json: {e}")
    DEVICES = [{'device_model': 'Generic Android', 'system_version': 'Android 14', 'app_version': 'Telegram 10.0', 'lang_code': 'en', 'lang_pack': 'android'}]

# === تحميل مكتبة TDLib ===
TDLIB_PATH = os.path.join(os.environ.get('PREFIX', '/data/data/com.termux/files/usr'), 'lib', 'libtdjson.so')
if not os.path.exists(TDLIB_PATH):
    logger.error(f"المكتبة غير موجودة في المسار المتوقع: {TDLIB_PATH}")
    if 'test' not in sys.argv[0]:
        sys.exit(1)

try:
    tdjson = ctypes.CDLL(TDLIB_PATH)
    logger.info(f"تم تحميل مكتبة TDLib من: {TDLIB_PATH}")
except OSError as e:
    logger.error(f"فشل تحميل مكتبة TDLib: {e}")
    if 'test' in sys.argv[0]:
        class MockTDLib:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        tdjson = MockTDLib()
    else:
        sys.exit(1)

# تعريف دوال TDLib
tdjson.td_json_client_create.restype = ctypes.c_void_p
tdjson.td_json_client_create.argtypes = []
tdjson.td_json_client_destroy.restype = None
tdjson.td_json_client_destroy.argtypes = [ctypes.c_void_p]
tdjson.td_json_client_send.restype = None
tdjson.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
tdjson.td_json_client_receive.restype = ctypes.c_char_p
tdjson.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("يجب تعيين المتغيرات البيئية: TG_API_ID, TG_API_HASH, BOT_TOKEN")

# === حالات المحادثة ===
(
    MAIN_MENU, ADD_ACCOUNT_CATEGORY, ADD_ACCOUNT_PHONE,
    ADD_ACCOUNT_PHONE_HANDLE_EXISTING, ADD_ACCOUNT_CODE,
    ADD_ACCOUNT_PASSWORD, DELETE_CATEGORY_SELECT,
    DELETE_ACCOUNT_SELECT, VIEW_CATEGORY_SELECT, VIEW_ACCOUNTS,
    CHECK_CATEGORY_SELECT, CHECK_ACCOUNT_SELECT, CHECK_ACCOUNT_DETAILS,
    CHECK_ACCOUNTS_IN_PROGRESS, STORAGE_CATEGORY_SELECT, STORAGE_ACCOUNT_SELECT
) = range(16)
