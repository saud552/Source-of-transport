# -*- coding: utf-8 -*-
"""
لوحات المفاتيح لبوت النقل
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any

class TransferKeyboards:
    """لوحات المفاتيح لبوت النقل"""
    
    def main_menu(self) -> InlineKeyboardMarkup:
        """القائمة الرئيسية"""
        keyboard = [
            [InlineKeyboardButton("📤 بدء نقل الأعضاء", callback_data="start_transfer")],
            [InlineKeyboardButton("📊 تاريخ النقل", callback_data="view_history")],
            [InlineKeyboardButton("📋 المجموعات المتاحة", callback_data="view_groups")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def source_groups_keyboard(self, groups: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """لوحة مفاتيح المجموعات المصدر"""
        keyboard = []
        
        for group in groups:
            button_text = f"📁 {group['title']} ({group['stored_members_count']} عضو)"
            if len(button_text) > 60:  # تقصير النص إذا كان طويلاً
                button_text = f"📁 {group['title'][:40]}... ({group['stored_members_count']} عضو)"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"group_{group['group_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
        return InlineKeyboardMarkup(keyboard)
    
    def account_categories_keyboard(self, categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """لوحة مفاتيح فئات الحسابات"""
        keyboard = []
        
        for category in categories:
            button_text = f"📱 {category['name']} ({category['account_count']} حساب)"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"category_{category['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
        return InlineKeyboardMarkup(keyboard)
    
    def confirm_accounts_keyboard(self, accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """لوحة مفاتيح تأكيد الحسابات"""
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحسابات", callback_data="confirm_accounts")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def confirm_transfer_keyboard(self) -> InlineKeyboardMarkup:
        """لوحة مفاتيح تأكيد النقل"""
        keyboard = [
            [InlineKeyboardButton("🚀 بدء النقل", callback_data="start_transfer")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def transfer_control_keyboard(self) -> InlineKeyboardMarkup:
        """لوحة مفاتيح التحكم في النقل"""
        keyboard = [
            [
                InlineKeyboardButton("⏸️ إيقاف", callback_data="pause_transfer"),
                InlineKeyboardButton("🔄 استئناف", callback_data="resume_transfer")
            ],
            [InlineKeyboardButton("❌ إلغاء النقل", callback_data="cancel_transfer")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def back_to_main_keyboard(self) -> InlineKeyboardMarkup:
        """لوحة مفاتيح العودة للقائمة الرئيسية"""
        keyboard = [
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def transfer_progress_keyboard(self, transfer_id: str) -> InlineKeyboardMarkup:
        """لوحة مفاتيح تقدم النقل"""
        keyboard = [
            [
                InlineKeyboardButton("⏸️ إيقاف", callback_data=f"pause_{transfer_id}"),
                InlineKeyboardButton("🔄 استئناف", callback_data=f"resume_{transfer_id}")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{transfer_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def pagination_keyboard(self, current_page: int, total_pages: int, 
                          prefix: str, extra_buttons: List[InlineKeyboardButton] = None) -> InlineKeyboardMarkup:
        """لوحة مفاتيح التصفح"""
        keyboard = []
        
        # إضافة الأزرار الإضافية
        if extra_buttons:
            keyboard.append(extra_buttons)
        
        # أزرار التصفح
        nav_buttons = []
        if current_page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}_prev_{current_page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"صفحة {current_page} من {total_pages}", callback_data="noop"))
        
        if current_page < total_pages:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{prefix}_next_{current_page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
        return InlineKeyboardMarkup(keyboard)