# -*- coding: utf-8 -*-
"""
وحدة التحقق من صحة البيانات في بوت التخزين
"""

import re
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DataValidator:
    """مدقق البيانات في بوت التخزين"""
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """التحقق من صحة رقم الهاتف بدقة أعلى"""
        if not phone:
            return False
            
        # دعم الأرقام بدون رمز الدولي (تخمين الرمز)
        if phone.startswith('0'):
            phone = '+967' + phone[1:]  # مثال لتعديل الأرقام اليمنية
        
        pattern = r'^\+\d{7,15}$'
        return re.match(pattern, phone) is not None

    @staticmethod
    def validate_code(code: str) -> bool:
        """التحقق من صحة رمز التحقق مع دعم رموز أطول"""
        if not code:
            return False
            
        code = code.replace(' ', '').replace('-', '').replace(',', '')
        # دعم رموز من 5 إلى 8 أرقام (بعض الأنظمة تستخدم رموز أطول)
        return re.match(r'^\d{5,8}$', code) is not None

    @staticmethod
    def validate_group_identifier(identifier: str) -> bool:
        """التحقق من صحة معرف المجموعة"""
        if not identifier:
            return False
        
        # تنظيف المدخل
        clean_identifier = identifier.strip()
        
        # إذا كان رابط تليجرام
        if clean_identifier.startswith('https://t.me/'):
            path = urlparse(clean_identifier).path
            clean_identifier = path.split('/')[-1] if path else clean_identifier
        
        # إذا كان يوزرنيم
        if clean_identifier.startswith('@'):
            clean_identifier = clean_identifier[1:]
        
        # إزالة الرموز غير المرغوبة
        clean_identifier = re.sub(r'[^\w\d]', '', clean_identifier)
        
        # التحقق من أن المعرف غير فارغ
        return len(clean_identifier) > 0

    @staticmethod
    def validate_category_name(category_name: str) -> bool:
        """التحقق من صحة اسم الفئة"""
        if not category_name:
            return False
        
        # التحقق من الطول (1-50 حرف)
        if len(category_name.strip()) < 1 or len(category_name.strip()) > 50:
            return False
        
        # التحقق من عدم احتواء أسماء محظورة
        forbidden_names = ['', 'null', 'none', 'undefined', 'test', 'temp']
        if category_name.strip().lower() in forbidden_names:
            return False
        
        return True

    @staticmethod
    def validate_months_input(months: str) -> bool:
        """التحقق من صحة إدخال عدد الأشهر"""
        if not months:
            return False
        
        try:
            months_int = int(months)
            return 0 <= months_int <= 120  # الحد الأقصى 10 سنوات
        except ValueError:
            return False

    @staticmethod
    def validate_user_data(user_data: Dict[str, Any]) -> bool:
        """التحقق من صحة بيانات المستخدم"""
        if not user_data:
            return False
        
        # التحقق من وجود المعرف
        if 'id' not in user_data or not user_data['id']:
            return False
        
        # التحقق من صحة المعرف (رقم صحيح)
        try:
            user_id = int(user_data['id'])
            if user_id <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        # التحقق من صحة اسم المستخدم إذا كان موجوداً
        if 'username' in user_data and user_data['username']:
            username = user_data['username']
            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                return False
        
        # التحقق من صحة رقم الهاتف إذا كان موجوداً
        if 'phone' in user_data and user_data['phone']:
            if not DataValidator.validate_phone(user_data['phone']):
                return False
        
        return True

    @staticmethod
    def validate_storage_group_data(group_data: Dict[str, Any]) -> bool:
        """التحقق من صحة بيانات مجموعة التخزين"""
        if not group_data:
            return False
        
        required_fields = ['id', 'title', 'total_members', 'storage_type']
        for field in required_fields:
            if field not in group_data or not group_data[field]:
                return False
        
        # التحقق من نوع التخزين
        if group_data['storage_type'] not in ['hidden', 'visible']:
            return False
        
        # التحقق من عدد الأعضاء
        try:
            total_members = int(group_data['total_members'])
            if total_members < 0:
                return False
        except (ValueError, TypeError):
            return False
        
        return True

    @staticmethod
    def sanitize_input(input_string: str) -> str:
        """تنظيف المدخل من الرموز الضارة"""
        if not input_string:
            return ""
        
        # إزالة الرموز الخطيرة
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\r', '\n']
        for char in dangerous_chars:
            input_string = input_string.replace(char, '')
        
        # إزالة المسافات الزائدة
        input_string = ' '.join(input_string.split())
        
        return input_string.strip()

    @staticmethod
    def validate_account_data(account_data: Dict[str, Any]) -> bool:
        """التحقق من صحة بيانات الحساب"""
        if not account_data:
            return False
        
        required_fields = ['id', 'phone', 'session_str', 'device_info']
        for field in required_fields:
            if field not in account_data or not account_data[field]:
                return False
        
        # التحقق من صحة رقم الهاتف
        if not DataValidator.validate_phone(account_data['phone']):
            return False
        
        # التحقق من صحة معلومات الجهاز
        try:
            import json
            device_info = json.loads(account_data['device_info'])
            required_device_fields = ['device_model', 'system_version', 'app_version']
            for field in required_device_fields:
                if field not in device_info or not device_info[field]:
                    return False
        except (json.JSONDecodeError, TypeError):
            return False
        
        return True

    @staticmethod
    def validate_export_request(export_data: Dict[str, Any]) -> bool:
        """التحقق من صحة طلب التصدير"""
        if not export_data:
            return False
        
        # التحقق من وجود معرف المجموعة أو الفئة
        if 'group_id' not in export_data and 'category_id' not in export_data:
            return False
        
        # التحقق من نوع التصدير
        if 'export_type' in export_data:
            if export_data['export_type'] not in ['csv', 'json', 'excel']:
                return False
        
        return True

    @staticmethod
    def validate_pagination_params(page: int, per_page: int) -> bool:
        """التحقق من صحة معاملات التصفح"""
        if not isinstance(page, int) or not isinstance(per_page, int):
            return False
        
        if page < 0 or per_page < 1 or per_page > 100:
            return False
        
        return True

    @staticmethod
    def validate_search_query(query: str) -> bool:
        """التحقق من صحة استعلام البحث"""
        if not query:
            return False
        
        # التحقق من الطول
        if len(query.strip()) < 2 or len(query.strip()) > 100:
            return False
        
        # التحقق من عدم احتواء رموز خطيرة
        dangerous_patterns = [r'<script', r'javascript:', r'data:', r'vbscript:']
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False
        
        return True