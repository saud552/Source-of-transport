# -*- coding: utf-8 -*-
"""
وحدات التحقق من صحة البيانات (Decoupled version)
"""

import re
import random
from typing import Dict, Any

from .config import DEVICES
from shared_config import DEFAULT_COUNTRY_CODE, PHONE_VALIDATION_PATTERN

def get_random_device() -> Dict[str, str]:
    """اختيار جهاز عشوائي من القائمة المحملة ديناميكياً"""
    if not DEVICES:
         return {
            'device_model': 'Generic Android',
            'system_version': 'Android 14',
            'app_version': 'Telegram 10.0',
            'lang_code': 'en',
            'lang_pack': 'android'
        }
    device = random.choice(DEVICES)
    return {
        'device_model': device['device_model'],
        'system_version': device['system_version'],
        'app_version': device['app_version'],
        'lang_code': device.get('lang_code', 'en'),
        'lang_pack': device.get('lang_pack', 'android')
    }

def validate_phone(phone: str) -> bool:
    """التحقق من صحة رقم الهاتف باستخدام الإعدادات المشتركة"""
    # معالجة الأرقام التي تبدأ بـ 0 باستخدام رمز الدولة الافتراضي من الإعدادات
    if phone.startswith('0'):
        phone = DEFAULT_COUNTRY_CODE + phone[1:]
        
    return re.match(PHONE_VALIDATION_PATTERN, phone) is not None

def validate_code(code: str) -> bool:
    """التحقق من صحة رمز التحقق"""
    code = code.replace(' ', '').replace('-', '').replace(',', '')
    return re.match(r'^\d{5,8}$', code) is not None
