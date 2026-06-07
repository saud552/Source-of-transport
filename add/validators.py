# -*- coding: utf-8 -*-
"""
وحدات التحقق من صحة البيانات
"""

import re
import random
from typing import Dict, Any

from .config import DEVICES

def get_random_device() -> Dict[str, str]:
    """اختيار جهاز عشوائي من القائمة مع تحديث الإصدارات"""
    device = random.choice(DEVICES)
    return {
        'device_model': device['device_model'],
        'system_version': device['system_version'],
        'app_version': device['app_version'],
        'lang_code': device.get('lang_code', 'en'),
        'lang_pack': device.get('lang_pack', 'android')
    }

def validate_phone(phone: str) -> bool:
    """التحقق من صحة رقم الهاتف بدقة أعلى"""
    # دعم الأرقام بدون رمز الدولي (تخمين الرمز)
    if phone.startswith('0'):
        phone = '+967' + phone[1:]  # مثال لتعديل الأرقام اليمنية
        
    pattern = r'^\+\d{7,15}$'
    return re.match(pattern, phone) is not None

def validate_code(code: str) -> bool:
    """التحقق من صحة رمز التحقق مع دعم رموز أطول"""
    code = code.replace(' ', '').replace('-', '').replace(',', '')
    # دعم رموز من 5 إلى 8 أرقام (بعض الأنظمة تستخدم رموز أطول)
    return re.match(r'^\d{5,8}$', code) is not None