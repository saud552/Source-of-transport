# -*- coding: utf-8 -*-
"""
وحدات لوحات المفاتيح والواجهات (Async PostgreSQL version)
"""

import uuid
from typing import Optional, List, Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def get_storage_categories_keyboard(action: str = "view", db_manager=None) -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح لفئات التخزين"""
    categories = await db_manager.get_storage_categories()
    
    if not categories:
        return None
    
    keyboard = []
    for cat in categories:
        cat_id = str(cat['id'])
        if action == "export":
            callback_data = f"export_category_{cat_id}"
        else:
            callback_data = f"view_category_{cat_id}"
        keyboard.append([InlineKeyboardButton(cat['name'], callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

async def get_storage_groups_keyboard(category_id: str, page: int = 0, action: str = "view",
                               db_manager=None) -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح لمجموعات التخزين مع التصفح"""
    groups = await db_manager.get_storage_groups_by_category(category_id)
    
    if not groups:
        return None
    
    # تصفح بسيط
    start_idx = page * 5
    end_idx = start_idx + 5
    page_groups = groups[start_idx:end_idx]
    
    keyboard = []
    for group in page_groups:
        group_id = str(group['id'])
        button_text = f"{group['title']}"
        callback_data = f"{action}_group_{group_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # أزرار التنقل
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"prev_{page-1}_{action}"))
    if end_idx < len(groups):
        nav.append(InlineKeyboardButton("▶️ التالي", callback_data=f"next_{page+1}_{action}"))
    if nav: keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("رجوع", callback_data="back_categories")])
    return InlineKeyboardMarkup(keyboard)

async def get_storage_accounts_keyboard() -> Optional[InlineKeyboardMarkup]:
    # مؤقتاً نرجع زر الكل فقط أو placeholders حتى نربط مع pg الخاص بـ add bot
    keyboard = [[InlineKeyboardButton("جميع الحسابات", callback_data="all_accounts")]]
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)
