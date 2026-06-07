# -*- coding: utf-8 -*-
"""
إعدادات بوت التخزين ومتغيرات البيئة
"""

import os
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
    ACCOUNTS_DB_PATH, STORAGE_DB_PATH
)

# === إعدادات التطبيق ===
BOT_TOKEN = os.getenv('STORAGE_BOT_TOKEN', '8604949254:AAEwfA5hGRKUHkvBpY8e68rJVfZljZcRwME')
DB_PATH = STORAGE_DB_PATH
KEY = None  # سيتم توليده عند أول استخدام

# === تحميل مكتبة TDLib من مسار Termux الثابت ===
from shared_config import TDLIB_PATH

if not os.path.exists(TDLIB_PATH):
    print(f"المكتبة غير موجودة في المسار المتوقع: {TDLIB_PATH}")
    print("تأكد من أنك نسخت libtdjson.so إلى مجلد /data/data/com.termux/files/usr/lib/")
    # لا نوقف البرنامج في بيئة الاختبار
    if 'test' not in sys.argv[0]:
        sys.exit(1)

try:
    tdjson = ctypes.CDLL(TDLIB_PATH)
    print(f"تم تحميل مكتبة TDLib من: {TDLIB_PATH}")
except OSError as e:
    print(f"فشل تحميل مكتبة TDLib: {e}")
    # إنشاء كائن وهمي للاختبار
    if 'test' in sys.argv[0]:
        class MockTDLib:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        tdjson = MockTDLib()
        print("تم إنشاء كائن وهمي لـ TDLib للاختبار")
    else:
        sys.exit(1)

# تعريف دوال TDLib الأساسية
tdjson.td_json_client_create.restype = ctypes.c_void_p
tdjson.td_json_client_create.argtypes = []

tdjson.td_json_client_destroy.restype = None
tdjson.td_json_client_destroy.argtypes = [ctypes.c_void_p]

tdjson.td_json_client_send.restype = None
tdjson.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

tdjson.td_json_client_receive.restype = ctypes.c_char_p
tdjson.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]

# === حالات المحادثة ===
(
    MAIN_MENU,
    STORAGE_HIDDEN_GROUP,
    STORAGE_HIDDEN_CONFIRM,
    STORAGE_HIDDEN_CATEGORY_NAME,
    STORAGE_HIDDEN_ACCOUNTS,
    STORAGE_HIDDEN_LAST_SEEN,
    STORAGE_HIDDEN_MONTHS,
    STORAGE_VISIBLE_GROUP,
    STORAGE_VISIBLE_CONFIRM,
    STORAGE_VISIBLE_CATEGORY_NAME,
    STORAGE_VISIBLE_ACCOUNTS,
    VIEW_STORAGE_CATEGORIES,
    VIEW_STORAGE_GROUPS,
    STORAGE_IN_PROGRESS,
    EXPORT_DATA
) = range(15)
# === إعدادات التخزين (Scraping Limits) ===
MAX_MESSAGES_SCAN = int(os.getenv('MAX_MESSAGES_SCAN', '10000'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
DB_INSERT_BATCH_SIZE = int(os.getenv('DB_INSERT_BATCH_SIZE', '500'))
