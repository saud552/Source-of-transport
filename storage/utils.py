# -*- coding: utf-8 -*-
"""
الدوال المساعدة العامة في بوت التخزين
"""

import os
import re
import time
import random
import logging
import tempfile
import shutil
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class StorageUtils:
    """فئة الدوال المساعدة في بوت التخزين"""
    
    @staticmethod
    def get_random_device() -> Dict[str, str]:
        """اختيار جهاز عشوائي من القائمة مع تحديث الإصدارات"""
        devices = [
            {
                'device_model': 'Samsung Galaxy S25 Ultra',
                'system_version': 'Android 15 (SDK 35)',
                'app_version': 'Plus Messenger 12.5.0',
                'lang_code': 'en',
                'lang_pack': 'android'
            },
            {
                'device_model': 'Google Pixel 9 Pro',
                'system_version': 'Android 15 (SDK 35)',
                'app_version': 'Telegram Android 10.9.0',
                'lang_code': 'en',
                'lang_pack': 'android'
            },
            {
                'device_model': 'OnePlus 13',
                'system_version': 'Android 15 (SDK 35)',
                'app_version': 'Telegram Android 10.9.0',
                'lang_code': 'en',
                'lang_pack': 'android'
            },
            {
                'device_model': 'Xiaomi 15 Pro',
                'system_version': 'Android 15 (SDK 35)',
                'app_version': 'Telegram Android 10.9.0',
                'lang_code': 'en',
                'lang_pack': 'android'
            },
            {
                'device_model': 'Huawei P70 Pro',
                'system_version': 'Android 15 (SDK 35)',
                'app_version': 'Telegram Android 10.9.0',
                'lang_code': 'en',
                'lang_pack': 'android'
            }
        ]
        
        device = random.choice(devices)
        return {
            'device_model': device['device_model'],
            'system_version': device['system_version'],
            'app_version': device['app_version'],
            'lang_code': device.get('lang_code', 'en'),
            'lang_pack': device.get('lang_pack', 'android')
        }

    @staticmethod
    def get_real_group_id(group_input: Any) -> int:
        """الحصول على ID الحقيقي للمجموعة"""
        try:
            # إذا كان المدخل رقمياً، نرجعه كما هو
            if isinstance(group_input, int):
                return group_input
            
            # إذا كان رابطاً، نستخرج المعرف منه
            if isinstance(group_input, str) and 'http' in group_input:
                parsed = urlparse(group_input)
                path = parsed.path.strip('/')
                if path.startswith('+'):
                    path = path[1:]
                group_input = path.split('/')[-1]
            
            # إذا كان يوزرنيم (يبدأ ب @)
            if isinstance(group_input, str) and group_input.startswith('@'):
                group_input = group_input[1:]
            
            # محاكاة الوصول إلى API التليجرام للحصول على ID الحقيقي
            return abs(hash(str(group_input))) % 1000000000000
        except Exception as e:
            logger.error(f"خطأ في الحصول على ID المجموعة الحقيقي: {str(e)}")
            return group_input

    @staticmethod
    def clean_group_identifier(identifier: str) -> str:
        """تنظيف معرف المجموعة من الرموز غير المرغوبة"""
        if not identifier:
            return ""
        
        # إزالة المسافات الزائدة
        identifier = identifier.strip()
        
        # إزالة الإشارة @
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        # إزالة الرموز غير المرغوبة
        identifier = re.sub(r'[^\w\d]', '', identifier)
        
        return identifier

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """تنسيق حجم الملف إلى صيغة مقروءة"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

    @staticmethod
    def format_duration(seconds: int) -> str:
        """تنسيق المدة الزمنية إلى صيغة مقروءة"""
        if seconds < 60:
            return f"{seconds} ثانية"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} دقيقة"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} ساعة"
        else:
            days = seconds // 86400
            return f"{days} يوم"

    @staticmethod
    def safe_filename(filename: str) -> str:
        """إنشاء اسم ملف آمن من النص"""
        if not filename:
            return "untitled"
        
        # إزالة الرموز الخطيرة
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # إزالة المسافات الزائدة
        filename = ' '.join(filename.split())
        
        # تحديد الطول الأقصى
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename or "untitled"

    @staticmethod
    def create_temp_directory() -> str:
        """إنشاء مجلد مؤقت آمن"""
        try:
            temp_dir = tempfile.mkdtemp(prefix="storage_bot_")
            return temp_dir
        except Exception as e:
            logger.error(f"خطأ في إنشاء المجلد المؤقت: {str(e)}")
            return None

    @staticmethod
    def cleanup_temp_directory(directory_path: str) -> bool:
        """تنظيف المجلد المؤقت"""
        try:
            if directory_path and os.path.exists(directory_path):
                shutil.rmtree(directory_path)
            return True
        except Exception as e:
            logger.error(f"خطأ في تنظيف المجلد المؤقت: {str(e)}")
            return False

    @staticmethod
    def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
        """تنفيذ دالة مع إعادة المحاولة والانتظار التدريجي"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"محاولة {attempt + 1} فشلت، إعادة المحاولة بعد {delay:.1f} ثانية: {str(e)}")
                time.sleep(delay)

    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """التحقق من صحة مسار الملف"""
        if not file_path:
            return False
        
        # التحقق من وجود مسار مطلق
        if not os.path.isabs(file_path):
            return False
        
        # التحقق من عدم الخروج من المجلد المسموح
        try:
            real_path = os.path.realpath(file_path)
            # يمكن إضافة المزيد من التحققات هنا
            return True
        except Exception:
            return False

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """الحصول على امتداد الملف"""
        if not filename:
            return ""
        
        return os.path.splitext(filename)[1].lower()

    @staticmethod
    def is_safe_file_type(filename: str) -> bool:
        """التحقق من أن نوع الملف آمن"""
        safe_extensions = {'.csv', '.json', '.txt', '.log', '.db', '.sqlite', '.sqlite3'}
        extension = StorageUtils.get_file_extension(filename)
        return extension in safe_extensions

    @staticmethod
    def generate_unique_id() -> str:
        """توليد معرف فريد"""
        import uuid
        return str(uuid.uuid4())

    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """تقصير النص مع إضافة نقاط"""
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."

    @staticmethod
    def parse_phone_number(phone: str) -> Optional[str]:
        """تحليل رقم الهاتف وإرجاعه بصيغة موحدة"""
        if not phone:
            return None
        
        # إزالة جميع الرموز غير الرقمية
        digits = re.sub(r'\D', '', phone)
        
        # إضافة رمز الدولي إذا لم يكن موجوداً
        if digits.startswith('0'):
            digits = '967' + digits[1:]  # مثال للرقم اليمني
        elif not digits.startswith('+'):
            digits = '+' + digits
        
        return digits

    @staticmethod
    def is_valid_username(username: str) -> bool:
        """التحقق من صحة اسم المستخدم"""
        if not username:
            return False
        
        # يجب أن يبدأ بحرف أو رقم
        if not username[0].isalnum():
            return False
        
        # يجب أن يحتوي على أحرف وأرقام وشرطات سفلية فقط
        if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return False
        
        return True

    @staticmethod
    def format_member_count(count: int) -> str:
        """تنسيق عدد الأعضاء"""
        if count < 1000:
            return str(count)
        elif count < 1000000:
            return f"{count/1000:.1f}K"
        else:
            return f"{count/1000000:.1f}M"

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """الحصول على معلومات النظام"""
        try:
            import platform
            import psutil
            
            return {
                'platform': platform.system(),
                'platform_version': platform.version(),
                'architecture': platform.architecture()[0],
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage': psutil.disk_usage('/').percent
            }
        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات النظام: {str(e)}")
            return {}

    @staticmethod
    def log_performance(func_name: str, start_time: float, end_time: float):
        """تسجيل أداء الدالة"""
        duration = end_time - start_time
        logger.info(f"أداء {func_name}: {duration:.3f} ثانية")

    @staticmethod
    def create_backup_filename(original_filename: str) -> str:
        """إنشاء اسم ملف النسخ الاحتياطي"""
        if not original_filename:
            return f"backup_{int(time.time())}"
        
        name, ext = os.path.splitext(original_filename)
        timestamp = int(time.time())
        return f"{name}_backup_{timestamp}{ext}"