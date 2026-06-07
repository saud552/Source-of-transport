# -*- coding: utf-8 -*-
"""
إعدادات التطبيق ومتغيرات البيئة
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
    ACCOUNTS_DB_PATH, SESSION_TIMEOUT, PAGE_SIZE
)

# === إعدادات التطبيق ===
BOT_TOKEN = os.getenv('ADD_BOT_TOKEN', '8600331776:AAEUmbwd01q15l0bgYtQEOm_zDT7QgoiVXo')
DB_PATH = ACCOUNTS_DB_PATH
KEY = None  # سيتم توليده عند أول استخدام

# === تحميل مكتبة TDLib من مسار Termux الثابت ===
TDLIB_PATH = os.path.join(os.environ.get('PREFIX', '/data/data/com.termux/files/usr'), 'lib', 'libtdjson.so')
if not os.path.exists(TDLIB_PATH):
    logger.error(f"المكتبة غير موجودة في المسار المتوقع: {TDLIB_PATH}")
    logger.error("تأكد من أنك نسخت libtdjson.so إلى مجلد /data/data/com.termux/files/usr/lib/")
    # لا نوقف البرنامج في بيئة الاختبار
    if 'test' not in sys.argv[0]:
        sys.exit(1)

try:
    tdjson = ctypes.CDLL(TDLIB_PATH)
    logger.info(f"تم تحميل مكتبة TDLib من: {TDLIB_PATH}")
except OSError as e:
    logger.error(f"فشل تحميل مكتبة TDLib: {e}")
    # إنشاء كائن وهمي للاختبار
    if 'test' in sys.argv[0]:
        class MockTDLib:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        tdjson = MockTDLib()
        logger.info("تم إنشاء كائن وهمي لـ TDLib للاختبار")
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

# === تحقق من المتغيرات البيئية ===
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("يجب تعيين المتغيرات البيئية: TG_API_ID, TG_API_HASH, BOT_TOKEN")

# === قائمة أجهزة Android ديناميكية ===
DEVICES = [
    # Samsung - أخر إصدارات
    {'device_model': 'Samsung Galaxy S25 Ultra', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Plus Messenger 12.5.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Samsung Galaxy Z Fold 6', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Nekogram X 12.3.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Samsung Galaxy A35 5G', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Premium 10.8.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Google - أخر إصدارات
    {'device_model': 'Google Pixel 9 Pro', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Telegram Android 10.9.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Google Pixel Fold 2', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'BGram 12.2.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Google Pixel 8a', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Plus Messenger 12.4.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # OnePlus - أخر إصدارات
    {'device_model': 'OnePlus 13', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Telegram Android 10.9.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'OnePlus Open 2', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Nekogram X 12.3.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'OnePlus Nord 4', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'BGram 12.1.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Xiaomi/Redmi/POCO - أخر إصدارات
    {'device_model': 'Xiaomi 15 Pro', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Telegram Android 10.9.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Redmi Note 14 Pro', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Plus Messenger 12.4.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'POCO F6', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Nekogram X 12.2.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Realme - أخر إصدارات
    {'device_model': 'Realme GT 5 Pro', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Android 10.8.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Realme 11 Pro+', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'BGram 12.0.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Motorola - أخر إصدارات
    {'device_model': 'Motorola Edge 40 Ultra', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Android 10.8.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Motorola Razr 50', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Plus Messenger 12.3.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Sony - أخر إصدارات
    {'device_model': 'Sony Xperia 1 VI', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Android 10.9.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Sony Xperia 5 VI', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Nekogram X 12.2.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # Huawei - أخر إصدارات
    {'device_model': 'Huawei P60 Pro', 'system_version': 'HarmonyOS 4.0', 'app_version': 'Telegram Android 10.7.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Huawei Mate X3', 'system_version': 'HarmonyOS 4.0', 'app_version': 'Plus Messenger 12.2.0', 'lang_code': 'en', 'lang_pack': 'android'},
    # أشهر أجهزة أخرى
    {'device_model': 'Nothing Phone 3', 'system_version': 'Android 15 (SDK 35)', 'app_version': 'Telegram Android 10.9.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Asus ROG Phone 8', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Nekogram X 12.3.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Oppo Find X7', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'BGram 12.1.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Vivo X100 Pro', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Android 10.8.0', 'lang_code': 'en', 'lang_pack': 'android'},
    {'device_model': 'Google Pixel 7a', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Plus Messenger 12.3.0', 'lang_code': 'ar', 'lang_pack': 'android'},
    {'device_model': 'Samsung Galaxy A25 5G', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Telegram Android 10.7.0', 'lang_code': 'fr', 'lang_pack': 'android'},
    {'device_model': 'Xiaomi Redmi Note 13', 'system_version': 'Android 13 (SDK 33)', 'app_version': 'BGram 11.9.0', 'lang_code': 'es', 'lang_pack': 'android'},
    {'device_model': 'Samsung Galaxy A32 5G', 'system_version': 'Android 13 (SDK 33)', 'app_version': 'Plus Messenger 11.12.0', 'lang_code': 'ar', 'lang_pack': 'android'},
    {'device_model': 'Motorola Edge 40 Ultra', 'system_version': 'Android 14 (SDK 34)', 'app_version': 'Plus Messenger 10.8.0', 'lang_code': 'ar', 'lang_pack': 'android'}
]

# === حالات المحادثة ===
(
    MAIN_MENU, ADD_ACCOUNT_CATEGORY, ADD_ACCOUNT_PHONE,
    ADD_ACCOUNT_PHONE_HANDLE_EXISTING, ADD_ACCOUNT_CODE,
    ADD_ACCOUNT_PASSWORD, DELETE_CATEGORY_SELECT,
    DELETE_ACCOUNT_SELECT, VIEW_CATEGORY_SELECT, VIEW_ACCOUNTS,
    CHECK_CATEGORY_SELECT, CHECK_ACCOUNT_SELECT, CHECK_ACCOUNT_DETAILS,
    CHECK_ACCOUNTS_IN_PROGRESS, STORAGE_CATEGORY_SELECT, STORAGE_ACCOUNT_SELECT
) = range(16)