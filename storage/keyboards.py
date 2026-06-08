# -*- coding: utf-8 -*-
"""
لوحات المفاتيح لبوت التخزين
"""

from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def get_storage_main_menu() -> InlineKeyboardMarkup:
    """لوحة مفاتيح القائمة الرئيسية لبوت التخزين"""
    keyboard = [
        [InlineKeyboardButton("📥 تخزين مخفي", callback_data="storage_hidden")],
        [InlineKeyboardButton("👁️ تخزين ظاهر", callback_data="storage_visible")],
        [InlineKeyboardButton("📂 عرض المجموعات المخزنة", callback_data="view_storage")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="storage_settings")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_categories_keyboard(categories: List[Dict[str, Any]], prefix: str) -> InlineKeyboardMarkup:
    """لوحة مفاتيح لعرض الفئات (للحسابات أو مجموعات التخزين)"""
    keyboard = []
    for cat in categories:
        count_str = f" ({cat['account_count']})" if 'account_count' in cat else ""
        keyboard.append([InlineKeyboardButton(f"{cat['name']}{count_str}", callback_data=f"{prefix}_{cat['id']}")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_storage_mechanism_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح اختيار آلية التخزين"""
    keyboard = [
        [InlineKeyboardButton("📅 تخزين شهري", callback_data="mech_monthly")],
        [InlineKeyboardButton("💬 تخزين لعدد رسائل", callback_data="mech_count")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_storage_progress_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح التحكم أثناء عملية التخزين"""
    keyboard = [
        [InlineKeyboardButton("⏸️ إيقاف العملية", callback_data="pause_storage")],
        [InlineKeyboardButton("▶️ استئناف العملية", callback_data="resume_storage")],
        [InlineKeyboardButton("🔙 إنهاء والرجوع للقائمة الرئيسية", callback_data="finish_storage")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Legacy support for older parts if needed
async def get_storage_categories_keyboard(db_manager=None, page=0) -> Optional[InlineKeyboardMarkup]:
    if not db_manager: return None
    cats = await db_manager.get_storage_categories()
    if not cats: return None
    return get_categories_keyboard(cats, "view_cat")

async def get_storage_groups_keyboard(db_manager, category_id, page=0) -> Optional[InlineKeyboardMarkup]:
    return None

async def get_storage_accounts_keyboard(db_manager=None, page=0) -> Optional[InlineKeyboardMarkup]:
    return None

def get_storage_category_groups_keyboard(groups: List[Dict[str, Any]], category_id: str, page: int, total_groups: int, limit: int = 40) -> InlineKeyboardMarkup:
    """لوحة مفاتيح لعرض المجموعات مع التصفح 40 لكل صفحة"""
    keyboard = []
    
    # 2 columns per row to fit nicely
    row = []
    for i, g in enumerate(groups):
        btn = InlineKeyboardButton(f"{g['title']} ({g['member_count']})", callback_data=f"view_group_{g['id']}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"page_groups_{category_id}_{page-1}"))

    total_pages = (total_groups + limit - 1) // limit
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️ التالي", callback_data=f"page_groups_{category_id}_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 رجوع للفئات", callback_data="view_storage")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_storage_group_detail_keyboard(group_id: str, category_id: str) -> InlineKeyboardMarkup:
    """لوحة مفاتيح تفاصيل المجموعة المخزنة"""
    keyboard = [
        [InlineKeyboardButton("🔄 إعادة التخزين", callback_data=f"restart_group_{group_id}")],
        [InlineKeyboardButton("🗑️ مسح التخزين", callback_data=f"delete_group_{group_id}")],
        [InlineKeyboardButton("🔙 رجوع للمجموعات", callback_data=f"page_groups_{category_id}_0")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح إعدادات التخزين"""
    keyboard = [
        [InlineKeyboardButton("📅 ضبط آلية التخزين الشهري", callback_data="settings_monthly")],
        [InlineKeyboardButton("💬 ضبط عدد رسائل التخزين", callback_data="settings_count")],
        [InlineKeyboardButton("⏳ ضبط فلتر آخر ظهور", callback_data="settings_last_seen")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_last_seen_settings_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح خيارات آخر ظهور"""
    keyboard = [
        [InlineKeyboardButton("🟢 آخر ظهور منذ زمن قريب", callback_data="ls_recently")],
        [InlineKeyboardButton("🟡 آخر ظهور منذ أسبوع أو أكثر", callback_data="ls_week")],
        [InlineKeyboardButton("🟠 آخر ظهور منذ شهر أو أكثر", callback_data="ls_month")],
        [InlineKeyboardButton("🔴 آخر ظهور منذ زمن طويل", callback_data="ls_empty")],
        [InlineKeyboardButton("♾️ جميع الخيارات", callback_data="ls_all")],
        [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="storage_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)
