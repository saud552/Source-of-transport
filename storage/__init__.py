# -*- coding: utf-8 -*-
"""
حزمة تخزين أعضاء التليجرام
تحتوي على جميع الوحدات المطلوبة لتخزين أعضاء المجموعات

الوحدات المتاحة:
- config: إعدادات البوت ومتغيرات البيئة
- database: إدارة قاعدة البيانات
- handlers: معالجات الأوامر والمحادثات
- group_manager: إدارة المجموعات وعمليات التخزين
- export: تصدير البيانات
- validation: التحقق من صحة البيانات
- encryption: تشفير وفك تشفير الجلسات
- utils: الدوال المساعدة العامة
- keyboards: لوحات المفاتيح والواجهات
- decorators: ديكورات التحقق من الصلاحيات
- tdlib_client: عميل TDLib لإدارة الجلسات
"""

__version__ = "2.0.0"
__author__ = "Telegram Storage Manager"
__description__ = "نظام متطور لتخزين أعضاء مجموعات التليجرام"

# استيراد الوحدات الأساسية
from .config import *
from .database import StorageDatabaseManager
from .validation import DataValidator
from .encryption import EncryptionManager
from .utils import StorageUtils

# استيراد الوحدات الاختيارية (تحتاج إلى مكتبات خارجية)
try:
    from .handlers import StorageHandlers
    from .group_manager import GroupManager
    from .export import DataExporter
    _has_telegram = True
except ImportError:
    _has_telegram = False

__all__ = [
    'StorageDatabaseManager',
    'DataValidator',
    'EncryptionManager',
    'StorageUtils'
]

if _has_telegram:
    __all__.extend(['StorageHandlers', 'GroupManager', 'DataExporter'])