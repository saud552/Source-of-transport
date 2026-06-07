# -*- coding: utf-8 -*-
"""
الأدوات المساعدة لبوت النقل
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import ADMIN_IDS

logger = logging.getLogger(__name__)

class TransferUtils:
    """الأدوات المساعدة لبوت النقل"""
    
    def is_admin(self, user_id: int) -> bool:
        """التحقق من صلاحيات المدير"""
        return user_id in ADMIN_IDS
    
    def extract_group_info(self, group_input: str) -> Tuple[Optional[int], str]:
        """استخراج معلومات المجموعة من الرابط أو المعرف"""
        try:
            group_input = group_input.strip()
            
            # إذا كان معرف مباشر (مثل: @groupname)
            if group_input.startswith('@'):
                username = group_input[1:]
                return None, username  # سنحتاج للبحث عن المعرف أولاً
            
            # إذا كان رابط تيليجرام
            if 't.me/' in group_input:
                # استخراج المعرف من الرابط
                match = re.search(r't\.me/([a-zA-Z0-9_]+)', group_input)
                if match:
                    username = match.group(1)
                    return None, username
            
            # إذا كان رقم معرف المجموعة مباشرة
            if group_input.isdigit():
                return int(group_input), f"Group {group_input}"
            
            # إذا كان معرف بدون @
            if re.match(r'^[a-zA-Z0-9_]+$', group_input):
                return None, group_input
            
            return None, group_input
            
        except Exception as e:
            logger.error(f"خطأ في استخراج معلومات المجموعة: {str(e)}")
            return None, group_input
    
    def validate_group_input(self, group_input: str) -> bool:
        """التحقق من صحة رابط المجموعة"""
        try:
            group_input = group_input.strip()
            
            # التحقق من المعرف
            if group_input.startswith('@'):
                username = group_input[1:]
                return bool(re.match(r'^[a-zA-Z0-9_]{5,32}$', username))
            
            # التحقق من رابط تيليجرام
            if 't.me/' in group_input:
                match = re.search(r't\.me/([a-zA-Z0-9_]+)', group_input)
                if match:
                    username = match.group(1)
                    return bool(re.match(r'^[a-zA-Z0-9_]{5,32}$', username))
            
            # التحقق من الرقم
            if group_input.isdigit():
                return True
            
            # التحقق من المعرف بدون @
            if re.match(r'^[a-zA-Z0-9_]{5,32}$', group_input):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من صحة رابط المجموعة: {str(e)}")
            return False
    
    def format_member_info(self, member: Dict[str, Any]) -> str:
        """تنسيق معلومات العضو"""
        try:
            info_parts = []
            
            # الاسم
            if member.get('first_name'):
                info_parts.append(f"الاسم: {member['first_name']}")
            
            # المعرف
            if member.get('username'):
                info_parts.append(f"المعرف: @{member['username']}")
            
            # الهاتف
            if member.get('phone'):
                info_parts.append(f"الهاتف: {member['phone']}")
            
            # آخر ظهور
            if member.get('last_seen'):
                info_parts.append(f"آخر ظهور: {member['last_seen']}")
            
            # حالة البوت
            if member.get('is_bot'):
                info_parts.append("🤖 بوت")
            
            # حالة البريميوم
            if member.get('is_premium'):
                info_parts.append("⭐ بريميوم")
            
            return " | ".join(info_parts) if info_parts else "معلومات غير متاحة"
            
        except Exception as e:
            logger.error(f"خطأ في تنسيق معلومات العضو: {str(e)}")
            return "خطأ في تنسيق المعلومات"
    
    def format_transfer_stats(self, stats: Dict[str, int]) -> str:
        """تنسيق إحصائيات النقل"""
        try:
            total = stats.get('total', 0)
            successful = stats.get('successful', 0)
            failed = stats.get('failed', 0)
            pending = stats.get('pending', 0)
            
            if total == 0:
                return "لا توجد بيانات"
            
            success_rate = (successful / total) * 100 if total > 0 else 0
            
            stats_text = f"📊 **إحصائيات النقل:**\n\n"
            stats_text += f"📈 **إجمالي الأعضاء:** {total}\n"
            stats_text += f"✅ **تم النقل بنجاح:** {successful}\n"
            stats_text += f"❌ **فشل في النقل:** {failed}\n"
            stats_text += f"⏳ **في الانتظار:** {pending}\n"
            stats_text += f"📊 **معدل النجاح:** {success_rate:.1f}%"
            
            return stats_text
            
        except Exception as e:
            logger.error(f"خطأ في تنسيق إحصائيات النقل: {str(e)}")
            return "خطأ في تنسيق الإحصائيات"
    
    def format_time_duration(self, seconds: int) -> str:
        """تنسيق مدة الوقت"""
        try:
            if seconds < 60:
                return f"{seconds} ثانية"
            elif seconds < 3600:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                return f"{minutes} دقيقة و {remaining_seconds} ثانية"
            else:
                hours = seconds // 3600
                remaining_minutes = (seconds % 3600) // 60
                return f"{hours} ساعة و {remaining_minutes} دقيقة"
                
        except Exception as e:
            logger.error(f"خطأ في تنسيق مدة الوقت: {str(e)}")
            return "وقت غير محدد"
    
    def sanitize_filename(self, filename: str) -> str:
        """تنظيف اسم الملف"""
        try:
            # إزالة الأحرف غير المسموحة
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            # إزالة المسافات الزائدة
            filename = re.sub(r'\s+', '_', filename)
            # تقصير الاسم إذا كان طويلاً
            if len(filename) > 100:
                filename = filename[:100]
            return filename
            
        except Exception as e:
            logger.error(f"خطأ في تنظيف اسم الملف: {str(e)}")
            return "file"
    
    def validate_account_data(self, account: Dict[str, Any]) -> bool:
        """التحقق من صحة بيانات الحساب"""
        try:
            required_fields = ['id', 'phone', 'session_str', 'device_info']
            
            for field in required_fields:
                if field not in account or not account[field]:
                    return False
            
            # التحقق من صحة معرف الهاتف
            phone = account['phone']
            if not re.match(r'^\+\d{10,15}$', phone):
                return False
            
            # التحقق من صحة سلسلة الجلسة
            session_str = account['session_str']
            if len(session_str) < 10:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من صحة بيانات الحساب: {str(e)}")
            return False
    
    def get_error_message(self, error_code: int) -> str:
        """الحصول على رسالة خطأ باللغة العربية"""
        error_messages = {
            400: "طلب غير صحيح",
            401: "غير مصرح بالوصول",
            403: "ممنوع الوصول",
            404: "غير موجود",
            429: "تم تجاوز الحد المسموح",
            500: "خطأ في الخادم",
            502: "خطأ في البوابة",
            503: "الخدمة غير متاحة",
            504: "انتهت مهلة الطلب"
        }
        
        return error_messages.get(error_code, f"خطأ غير معروف (كود: {error_code})")
    
    def truncate_text(self, text: str, max_length: int = 100) -> str:
        """تقصير النص"""
        try:
            if len(text) <= max_length:
                return text
            
            return text[:max_length-3] + "..."
            
        except Exception as e:
            logger.error(f"خطأ في تقصير النص: {str(e)}")
            return text[:max_length] if text else ""