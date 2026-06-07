# -*- coding: utf-8 -*-
"""
وحدات لوحات المفاتيح والواجهات
"""

import sqlite3
from typing import Optional, List, Tuple
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from .config import PAGE_SIZE

def get_categories_keyboard(page: int = 0, action: str = "check", db_path: str = "accounts.db") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح للفئات مع التصفح"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.id, c.name, COUNT(a.id)
        FROM categories c
        LEFT JOIN accounts a ON c.id = a.category_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """)
    categories = cursor.fetchall()
    conn.close()
    
    if not categories:
        return None
    
    total_pages = (len(categories) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for category_id, category_name, account_count in page_categories:
        if action != "storage" or category_name != "حسابات التخزين":
            keyboard.append([InlineKeyboardButton(
                f"{category_name} ({account_count})",
                callback_data=f"{action}_category_{category_id}"
            )])
    
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"prev_{page}"))
    if end_idx < len(categories):
        navigation_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"next_{page}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_accounts_keyboard(category_id: str, page: int = 0, action_prefix: str = "account", 
                         db_path: str = "accounts.db") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح للحسابات مع التصفح"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, phone
        FROM accounts
        WHERE category_id = ?
        ORDER BY created_at DESC
    """, (category_id,))
    accounts = cursor.fetchall()
    conn.close()
    
    if not accounts:
        return None
    
    total_pages = (len(accounts) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_accounts = accounts[start_idx:end_idx]
    
    keyboard = []
    for account_id, phone in page_accounts:
        keyboard.append([InlineKeyboardButton(phone, callback_data=f"{action_prefix}_{account_id}")])
    
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"prev_{page}"))
    if end_idx < len(accounts):
        navigation_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"next_{page}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    keyboard.append([InlineKeyboardButton("رجوع", callback_data="back_categories")])
    keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)