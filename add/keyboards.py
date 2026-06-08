# -*- coding: utf-8 -*-
"""
وحدات لوحات المفاتيح والواجهات
"""

from typing import Optional, List, Tuple, Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

from .config import PAGE_SIZE

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح القائمة الرئيسية للبوت"""
    keyboard = [
        [InlineKeyboardButton("1️⃣ اضافة حساب", callback_data="main_add_account")],
        [InlineKeyboardButton("2️⃣ فحص الحسابات", callback_data="main_check_accounts")],
        [InlineKeyboardButton("3️⃣ عرض الحسابات", callback_data="main_view_accounts")],
        [InlineKeyboardButton("4️⃣ حذف حساب", callback_data="main_delete_account")],
        [InlineKeyboardButton("5️⃣ المغادرة والانظمام", callback_data="main_join_leave")],
        [InlineKeyboardButton("6️⃣ الاعدادات", callback_data="main_settings")],
        [InlineKeyboardButton("❌ الغاء", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_categories_inline_keyboard(categories: List[Dict[str, Any]], page: int = 0, action: str = "check") -> Optional[InlineKeyboardMarkup]:
    """إنشاء لوحة مفاتيح للفئات مع التصفح"""
    if not categories:
        return None
    
    total_pages = (len(categories) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_categories = categories[start_idx:end_idx]
    
    keyboard = []
    for category in page_categories:
        category_id = category.get('id')
        category_name = category.get('name')
        account_count = category.get('account_count', 0)

        keyboard.append([InlineKeyboardButton(
            f"{category_name} ({account_count})",
            callback_data=f"{action}_category_{category_id}_{category_name}"
        )])
    
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{action}_prev_{page}"))
    if end_idx < len(categories):
        navigation_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"{action}_next_{page}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    keyboard.append([InlineKeyboardButton("❌ الغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_customization_menu_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح تخصيص الحساب"""
    keyboard = [
        [InlineKeyboardButton("⚧ جنس الحساب", callback_data="cust_gender")],
        [InlineKeyboardButton("🖼 وضع صوره للحساب", callback_data="cust_photo")],
        [InlineKeyboardButton("📝 وضع اسم للحساب", callback_data="cust_name")],
        [InlineKeyboardButton("🗒 وضع بايو للحساب", callback_data="cust_bio")],
        [InlineKeyboardButton("🔗 تغيير يوزر", callback_data="cust_username")],
        [InlineKeyboardButton("🗑 ازالة خلفيات الحساب", callback_data="cust_remove_photos")],
        [InlineKeyboardButton("✅ تاكيد العملية", callback_data="cust_confirm")],
        [InlineKeyboardButton("❌ الغاء", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_gender_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح لاختيار الجنس"""
    keyboard = [
        [InlineKeyboardButton("👨 ولد", callback_data="gender_male")],
        [InlineKeyboardButton("👩 بنت", callback_data="gender_female")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_customize")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_customize_keyboard() -> InlineKeyboardMarkup:
    """زر الرجوع لقائمة التخصيص"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_customize")]])

def get_auto_photo_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🤖 تعيين صوره تلقائيه", callback_data="auto_photo")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_customize")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_auto_name_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🤖 تعيين اسم تلقائي", callback_data="auto_name")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_customize")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_auto_bio_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🤖 تعيين نبذة تلقائيه", callback_data="auto_bio")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_customize")]
    ]
    return InlineKeyboardMarkup(keyboard)

