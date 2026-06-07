# -*- coding: utf-8 -*-
"""
إعدادات بوت النقل ومتغيرات البيئة
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
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import (
    API_ID, API_HASH, ADMIN_IDS, PASSPHRASE, SALT, 
    ACCOUNTS_DB_PATH, STORAGE_DB_PATH, TRANSFER_BOT_TOKEN
)

# === إعدادات التطبيق ===
BOT_TOKEN = os.getenv('TRANSFER_BOT_TOKEN', '8664202831:AAFLn8vijJqr4HbQrTY7WmHDsFcAKjdb2C8')
DB_PATH = 'transfer.db'
KEY = None  # سيتم توليده عند أول استخدام

# === تحميل مكتبة TDLib من مسار Termux الثابت ===
TDLIB_PATH = os.path.join(os.environ.get('PREFIX', '/data/data/com.termux/files/usr'), 'lib', 'libtdjson.so')

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
    SELECT_SOURCE_GROUP,
    SELECT_ACCOUNT_CATEGORY,
    SELECT_ACCOUNTS,
    ENTER_TARGET_GROUP,
    CONFIRM_TRANSFER,
    TRANSFER_IN_PROGRESS,
    VIEW_TRANSFER_HISTORY,
    VIEW_AVAILABLE_GROUPS
) = range(9)

# === إعدادات النقل ===
MAX_MEMBERS_PER_BATCH = 10  # عدد الأعضاء في كل دفعة
TRANSFER_DELAY = 2  # تأخير بين كل عملية نقل (ثواني)
MAX_RETRIES = 3  # عدد المحاولات عند الفشل
# === إعدادات النقل المتقدمة (Behavior Simulation) ===
MIN_JITTER_DELAY = float(os.getenv('MIN_JITTER_DELAY', '5.0'))
MAX_JITTER_DELAY = float(os.getenv('MAX_JITTER_DELAY', '15.0'))
BATCH_ROTATE_DELAY = float(os.getenv('BATCH_ROTATE_DELAY', '30.0'))
ACCOUNT_WAIT_TIMEOUT = float(os.getenv('ACCOUNT_WAIT_TIMEOUT', '60.0'))
