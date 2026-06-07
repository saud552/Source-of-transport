# -*- coding: utf-8 -*-
"""
وحدات لوحات المفاتيح والواجهات
"""

import sqlite3
import logging
from typing import Optional, List, Dict, Any

try:
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    _has_telegram = True
except ImportError:
    _has_telegram = False
    # إنشاء فئات وهمية للاختبار
    class InlineKeyboardMarkup:
        def __init__(self, keyboard):
            self.keyboard = keyboard
    
    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

logger = logging.getLogger(__name__)

def get_storage_categories_keyboard(action: str = "view", db_path: str = "storage.db") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح لفئات التخزين"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name 
            FROM storage_categories
            ORDER BY created_at DESC
        """)
        categories = cursor.fetchall()
    
    if not categories:
        return None
    
    keyboard = []
    for category_id, category_name in categories:
        if action == "export":
            callback_data = f"export_category_{category_id}"
        else:
            callback_data = f"view_category_{category_id}"
        keyboard.append([InlineKeyboardButton(category_name, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_storage_groups_keyboard(category_id: str, page: int = 0, action: str = "view", 
                               db_path: str = "storage.db") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح لمجموعات التخزين مع التصفح"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, group_id, storage_type 
            FROM storage_groups 
            WHERE category_id = ?
            ORDER BY created_at DESC
        """, (category_id,))
        groups = cursor.fetchall()
    
    if not groups:
        return None
    
    total_pages = (len(groups) + 5 - 1) // 5
    start_idx = page * 5
    end_idx = start_idx + 5
    page_groups = groups[start_idx:end_idx]
    
    keyboard = []
    for group_id, title, group_id_val, storage_type in page_groups:
        cursor.execute("SELECT COUNT(*) FROM stored_members WHERE storage_group_id = ?", (group_id,))
        count = cursor.fetchone()[0]
        
        if action == "export":
            button_text = f"{title} ({count})"
            callback_data = f"export_group_{group_id}"
        else:
            button_text = f"{title} ({count})"
            callback_data = f"view_group_{group_id}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"prev_{page}_{action}"))
    if end_idx < len(groups):
        navigation_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"next_{page}_{action}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    keyboard.append([InlineKeyboardButton("رجوع", callback_data="back_categories")])
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_storage_accounts_keyboard(accounts_db_path: str = "accounts.db") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح لحسابات التخزين من قاعدة بيانات البوت الأول"""
    try:
        with sqlite3.connect(accounts_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", ("حسابات التخزين",))
            storage_category = cursor.fetchone()
            
            if not storage_category:
                logger.error("فئة التخزين غير موجودة في قاعدة بيانات الحسابات")
                return None
            
            category_id = storage_category[0]
            cursor.execute("""
                SELECT id, phone 
                FROM accounts 
                WHERE category_id = ?
            """, (category_id,))
            accounts = cursor.fetchall()
        
        if not accounts:
            logger.warning("لا توجد حسابات في فئة التخزين")
            return None
        
        keyboard = []
        for account_id, phone in accounts:
            keyboard.append([InlineKeyboardButton(phone, callback_data=f"account_{account_id}")])
        
        keyboard.append([InlineKeyboardButton("الكل", callback_data="all_accounts")])
        keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"خطأ في الحصول على حسابات التخزين: {str(e)}", exc_info=True)
        return None