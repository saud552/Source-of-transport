# -*- coding: utf-8 -*-
"""
معالجات الأوامر والمحادثات في بوت التخزين (Async PostgreSQL version)
"""

import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand
from telegram.ext import ContextTypes

from .decorators import owner_only
from .keyboards import get_storage_categories_keyboard, get_storage_groups_keyboard, get_storage_accounts_keyboard
from .group_manager import GroupManager
from .database import StorageDatabaseManager
from .export import DataExporter
from .config import ADMIN_IDS, DB_PATH

logger = logging.getLogger(__name__)

class StorageHandlers:
    """معالجات الأوامر والمحادثات في بوت التخزين"""
    
    def __init__(self, db_manager: StorageDatabaseManager, group_manager: GroupManager):
        self.db_manager = db_manager
        self.group_manager = group_manager
        self.exporter = DataExporter(db_manager)
        self.active_tasks = {}
        self.pause_events = {}
        self.cancel_events = {}

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء البوت وإعداد القائمة الرئيسية"""
        commands = [
            BotCommand("start", "إعادة تشغيل البوت"),
            BotCommand("cancel", "إلغاء العملية الحالية"),
            BotCommand("status", "حالة المهام الجارية")
        ]
        await context.bot.set_my_commands(commands)
        
        keyboard = [
            ["📥 تخزين الأعضاء من قروب مخفي"],
            ["👁️ تخزين الأعضاء من قروب ظاهر"],
            ["📂 عرض القروبات المخزنة", "📤 تصدير البيانات"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "👋 مرحباً بك في نظام تخزين أعضاء التليجرام (PostgreSQL)!\n"
            "اختر أحد الخيارات من القائمة أدناه:",
            reply_markup=reply_markup
        )
        return 0  # MAIN_MENU

    @owner_only
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض حالة المهام الجارية"""
        active_jobs = await self.db_manager.get_active_storage_jobs()
        
        if not active_jobs:
            await update.message.reply_text("لا توجد مهام تخزين نشطة حالياً.")
            return
        
        message = "📊 حالة المهام الجارية:\n\n"
        for job in active_jobs:
            total = job['total_members'] or 0
            stored = job['stored_members'] or 0
            progress = (stored / total) * 100 if total > 0 else 0
            message += (
                f"🏷️ المجموعة: {job['title']}\n"
                f"🔄 الحالة: {'⏸ متوقفة' if job['status'] == 'paused' else '▶️ جارية'}\n"
                f"📈 التقدم: {stored}/{total} ({progress:.1f}%)\n\n"
            )
        
        await update.message.reply_text(message)

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        
        if text == "📥 تخزين الأعضاء من قروب مخفي":
            await update.message.reply_text("📩 أرسل رابط/معرف المجموعة المخفية:", reply_markup=ReplyKeyboardRemove())
            return 1 # STORAGE_HIDDEN_GROUP
        
        elif text == "👁️ تخزين الأعضاء من قروب ظاهر":
            await update.message.reply_text("📩 أرسل رابط/معرف المجموعة الظاهرة:", reply_markup=ReplyKeyboardRemove())
            return 7 # STORAGE_VISIBLE_GROUP (Adjusted as per range(15))
        
        elif text == "📂 عرض القروبات المخزنة":
            keyboard = await get_storage_categories_keyboard(db_manager=self.db_manager)
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات.")
                return 0
            await update.message.reply_text("📁 اختر فئة:", reply_markup=keyboard)
            return 11 # VIEW_STORAGE_CATEGORIES
        
        await update.message.reply_text("❌ خيار غير صالح.")
        return 0

    @owner_only
    async def storage_hidden_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        group_input = update.message.text.strip()
        group_info = await self.group_manager.get_group_info(group_input)
        
        if not group_info:
            await update.message.reply_text("❌ تعذر العثور على المجموعة.")
            return 1
        
        context.user_data['hidden_group_info'] = group_info
        keyboard = [[InlineKeyboardButton("تأكيد", callback_data="confirm_hidden_group")]]
        await update.message.reply_text(f"🔍 المجموعة: {group_info['title']}\nالأعضاء: {group_info['total_members']}\nتأكيد؟", reply_markup=InlineKeyboardMarkup(keyboard))
        return 2 # STORAGE_HIDDEN_CONFIRM

    @owner_only
    async def storage_hidden_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📁 أدخل اسم الفئة للتخزين:")
        return 3 # STORAGE_HIDDEN_CATEGORY_NAME

    @owner_only
    async def storage_hidden_category_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['hidden_category_name'] = update.message.text.strip()
        keyboard = await get_storage_accounts_keyboard()
        if not keyboard:
            await update.message.reply_text("❌ لا توجد حسابات تخزين.")
            return 0
        await update.message.reply_text("👤 اختر الحسابات:", reply_markup=keyboard)
        return 4 # STORAGE_HIDDEN_ACCOUNTS

    @owner_only
    async def storage_hidden_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        
        if query.data == "all_accounts":
            # التحصيل من PostgreSQL (سيتطلب تحديث logic في group_manager لجلب الحسابات من pg)
            context.user_data['hidden_accounts'] = ['all']
        else:
            context.user_data['hidden_accounts'] = [query.data.split("_")[1]]

        await query.edit_message_text("⏳ أدخل عدد أشهر النشاط (0 للكل):")
        return 5 # STORAGE_HIDDEN_LAST_SEEN

    @owner_only
    async def storage_hidden_last_seen(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            context.user_data['last_seen'] = int(update.message.text.strip())
        except:
            context.user_data['last_seen'] = 0
        await update.message.reply_text("📅 أدخل عدد أشهر الانضمام (0 للكل):")
        return 6 # STORAGE_HIDDEN_MONTHS

    @owner_only
    async def storage_hidden_months(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            months = int(update.message.text.strip())
        except:
            months = 0
        
        group_info = context.user_data['hidden_group_info']
        # تحويل account_ids لمجموعة فعلية إذا كانت 'all'
        # ... logic ...
        
        await self.group_manager.start_hidden_storage(
            update, context, group_info, ['system'], # placeholder
            context.user_data['hidden_category_name'], months, context.user_data['last_seen']
        )
        return 13 # STORAGE_IN_PROGRESS

    async def start_from_query(self, query, context):
        await query.edit_message_text("العودة...")
        return await self.start(query, context)

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return await self.start(update, context)
