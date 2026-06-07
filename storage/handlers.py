# -*- coding: utf-8 -*-
"""
معالجات الأوامر والمحادثات في بوت التخزين
"""

import asyncio
import logging
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
        # إعداد أوامر القائمة
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
            "👋 مرحباً بك في نظام تخزين أعضاء التليجرام المتطور!\n"
            "اختر أحد الخيارات من القائمة أدناه:",
            reply_markup=reply_markup
        )
        return 0  # MAIN_MENU

    @owner_only
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض حالة المهام الجارية"""
        active_jobs = self.db_manager.get_active_storage_jobs()
        
        if not active_jobs:
            await update.message.reply_text("لا توجد مهام تخزين نشطة حالياً.")
            return
        
        message = "📊 حالة المهام الجارية:\n\n"
        for job in active_jobs:
            progress = (job['stored_members'] / job['total_members']) * 100 if job['total_members'] > 0 else 0
            message += (
                f"🏷️ المجموعة: {job['title']}\n"
                f"🔄 الحالة: {'⏸ متوقفة' if job['status'] == 'paused' else '▶️ جارية'}\n"
                f"📈 التقدم: {job['stored_members']}/{job['total_members']} ({progress:.1f}%)\n\n"
            )
        
        await update.message.reply_text(message)

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة القائمة الرئيسية"""
        text = update.message.text
        
        if text == "📥 تخزين الأعضاء من قروب مخفي":
            await update.message.reply_text(
                "📩 الرجاء إرسال رابط المجموعة المخفية أو معرفها:",
                reply_markup=ReplyKeyboardRemove()
            )
            return 1  # STORAGE_HIDDEN_GROUP
        
        elif text == "👁️ تخزين الأعضاء من قروب ظاهر":
            await update.message.reply_text(
                "📩 الرجاء إرسال رابط المجموعة الظاهرة أو معرفها:",
                reply_markup=ReplyKeyboardRemove()
            )
            return 4  # STORAGE_VISIBLE_GROUP
        
        elif text == "📂 عرض القروبات المخزنة":
            keyboard = get_storage_categories_keyboard()
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات مخزنة.")
                return 0
            await update.message.reply_text(
                "📁 اختر فئة لعرض المجموعات المخزنة فيها:",
                reply_markup=keyboard
            )
            return 11  # VIEW_STORAGE_CATEGORIES
        
        elif text == "📤 تصدير البيانات":
            keyboard = get_storage_categories_keyboard(action="export")
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات مخزنة.")
                return 0
            await update.message.reply_text(
                "📁 اختر فئة لتصدير بيانات مجموعاتها:",
                reply_markup=keyboard
            )
            return 14  # EXPORT_DATA
        
        await update.message.reply_text("❌ خيار غير صالح. الرجاء الاختيار من القائمة.")
        return 0

    @owner_only
    async def storage_hidden_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة إدخال مجموعة مخفية"""
        group_input = update.message.text.strip()
        context.user_data['hidden_group'] = group_input
        
        group_info = await self.group_manager.get_group_info(group_input)
        
        if not group_info:
            await update.message.reply_text("❌ تعذر الحصول على معلومات المجموعة. الرجاء التأكد من الرابط/المعرف.")
            return 1
        
        context.user_data['hidden_group_info'] = group_info
        
        keyboard = [
            [InlineKeyboardButton("تأكيد", callback_data="confirm_hidden_group")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔍 تم التعرف على المجموعة:\n\n"
            f"🏷️ الاسم: {group_info['title']}\n"
            f"🆔 المعرف: {group_info['id']}\n"
            f"👥 عدد الأعضاء: {group_info['total_members']}\n\n"
            "هل تريد المتابعة؟",
            reply_markup=reply_markup
        )
        return 2  # STORAGE_HIDDEN_CONFIRM

    @owner_only
    async def storage_hidden_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأكيد تخزين المجموعة المخفية"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_hidden_group":
            await query.edit_message_text(
                "📁 الرجاء إرسال اسم الفئة التي تريد تخزين الأعضاء فيها:"
            )
            return 3  # STORAGE_HIDDEN_CATEGORY_NAME
        
        return 2

    @owner_only
    async def storage_hidden_category_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إدخال اسم فئة التخزين للمجموعة المخفية"""
        category_name = update.message.text.strip()
        context.user_data['hidden_category_name'] = category_name
        
        keyboard = get_storage_accounts_keyboard()
        if not keyboard:
            await update.message.reply_text("❌ لا توجد حسابات تخزين متاحة.")
            return 0
        
        await update.message.reply_text(
            "👤 اختر الحسابات التي تريد استخدامها في التخزين:",
            reply_markup=keyboard
        )
        return 4  # STORAGE_HIDDEN_ACCOUNTS

    @owner_only
    async def storage_hidden_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """اختيار حسابات التخزين للمجموعة المخفية"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("تم الإلغاء.")
            return await self.start_from_query(query, context)
        
        if query.data == "all_accounts":
            try:
                accounts = self.db_manager.get_storage_accounts()
                account_ids = [account['id'] for account in accounts]
                context.user_data['hidden_accounts'] = account_ids
            except Exception as e:
                logger.error(f"خطأ في الحصول على جميع الحسابات: {str(e)}")
                await query.answer("❌ حدث خطأ أثناء جلب الحسابات", show_alert=True)
                return 4
        elif query.data.startswith("account_"):
            account_id = query.data.split("_")[1]
            context.user_data['hidden_accounts'] = [account_id]
        
        await query.edit_message_text(
            "⏳ الرجاء إدخال عدد الأشهر لآخر ظهور للعضو (0 لجميع الأعضاء):"
        )
        return 5  # STORAGE_HIDDEN_LAST_SEEN

    @owner_only
    async def storage_hidden_last_seen(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إدخال فترة آخر ظهور للمجموعة المخفية"""
        months = update.message.text.strip()
        try:
            months = int(months)
            if months < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ عدد الأشهر غير صالح. الرجاء إدخال رقم صحيح غير سالب.")
            return 5
        
        context.user_data['last_seen'] = months
        
        await update.message.reply_text(
            "⏳ الرجاء إدخال عدد الأشهر المراد فحصها لتاريخ الانضمام (0 لجميع الأعضاء):"
        )
        return 6  # STORAGE_HIDDEN_MONTHS

    @owner_only
    async def storage_hidden_months(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إدخال فترة الانضمام للمجموعة المخفية"""
        months = update.message.text.strip()
        try:
            months = int(months)
            if months < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ عدد الأشهر غير صالح. الرجاء إدخال رقم صحيح غير سالب.")
            return 6
        
        context.user_data['hidden_months'] = months
        
        # بدء عملية التخزين
        group_info = context.user_data['hidden_group_info']
        account_ids = context.user_data['hidden_accounts']
        category_name = context.user_data['hidden_category_name']
        last_seen = context.user_data.get('last_seen', 0)
        
        await self.group_manager.start_hidden_storage(
            update, context, group_info, account_ids, category_name, months, last_seen
        )
        return 10  # STORAGE_IN_PROGRESS

    @owner_only
    async def storage_visible_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة إدخال مجموعة ظاهرة"""
        group_input = update.message.text.strip()
        context.user_data['visible_group'] = group_input
        
        group_info = await self.group_manager.get_group_info(group_input)
        
        if not group_info:
            await update.message.reply_text("❌ تعذر الحصول على معلومات المجموعة. الرجاء التأكد من الرابط/المعرف.")
            return 4
        
        context.user_data['visible_group_info'] = group_info
        
        keyboard = [
            [InlineKeyboardButton("تأكيد", callback_data="confirm_visible_group")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔍 تم التعرف على المجموعة:\n\n"
            f"🏷️ الاسم: {group_info['title']}\n"
            f"🆔 المعرف: {group_info['id']}\n"
            f"👥 عدد الأعضاء: {group_info['total_members']}\n\n"
            "هل تريد المتابعة؟",
            reply_markup=reply_markup
        )
        return 5  # STORAGE_VISIBLE_CONFIRM

    @owner_only
    async def storage_visible_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأكيد تخزين المجموعة الظاهرة"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_visible_group":
            await query.edit_message_text(
                "📁 الرجاء إرسال اسم الفئة التي تريد تخزين الأعضاء فيها:"
            )
            return 6  # STORAGE_VISIBLE_CATEGORY_NAME
        
        return 5

    @owner_only
    async def storage_visible_category_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إدخال اسم فئة التخزين للمجموعة الظاهرة"""
        category_name = update.message.text.strip()
        context.user_data['visible_category_name'] = category_name
        
        keyboard = get_storage_accounts_keyboard()
        if not keyboard:
            await update.message.reply_text("❌ لا توجد حسابات تخزين متاحة.")
            return 0
        
        await update.message.reply_text(
            "👤 اختر الحسابات التي تريد استخدامها في التخزين:",
            reply_markup=keyboard
        )
        return 7  # STORAGE_VISIBLE_ACCOUNTS

    @owner_only
    async def storage_visible_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """اختيار حسابات التخزين للمجموعة الظاهرة"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("تم الإلغاء.")
            return await self.start_from_query(query, context)
        
        if query.data == "all_accounts":
            try:
                accounts = self.db_manager.get_storage_accounts()
                account_ids = [account['id'] for account in accounts]
                context.user_data['visible_accounts'] = account_ids
            except Exception as e:
                logger.error(f"خطأ في الحصول على جميع الحسابات: {str(e)}")
                await query.answer("❌ حدث خطأ أثناء جلب الحسابات", show_alert=True)
                return 7
        elif query.data.startswith("account_"):
            account_id = query.data.split("_")[1]
            context.user_data['visible_accounts'] = [account_id]
        
        # بدء عملية التخزين للمجموعة الظاهرة
        group_info = context.user_data['visible_group_info']
        account_ids = context.user_data['visible_accounts']
        category_name = context.user_data['visible_category_name']
        
        await self.group_manager.start_visible_storage(
            update, context, group_info, account_ids, category_name
        )
        return 10  # STORAGE_IN_PROGRESS

    @owner_only
    async def handle_storage_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة طلبات التحكم في التخزين"""
        query = update.callback_query
        await query.answer()
        
        action, storage_group_id = query.data.split('_', 1)
        
        if action == "pause":
            if storage_group_id in self.pause_events:
                self.pause_events[storage_group_id].set()
                await query.answer("⏸ تم إيقاف التخزين مؤقتاً")
            else:
                await query.answer("❌ المهمة غير موجودة أو تم إكمالها")
        
        elif action == "resume":
            if storage_group_id in self.pause_events:
                self.pause_events[storage_group_id].clear()
                await query.answer("▶ تم استئناف التخزين")
            else:
                await query.answer("❌ المهمة غير موجودة أو تم إكمالها")
        
        elif action == "cancel":
            if storage_group_id in self.cancel_events:
                self.cancel_events[storage_group_id].set()
                await query.answer("❌ تم إلغاء التخزين")
                
                if storage_group_id in self.active_tasks:
                    task = self.active_tasks[storage_group_id]
                    task.cancel()
                    del self.active_tasks[storage_group_id]
            else:
                await query.answer("❌ المهمة غير موجودة أو تم إكمالها")
        
        return 10  # STORAGE_IN_PROGRESS

    @owner_only
    async def view_storage_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """عرض فئات التخزين"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("تم الإلغاء.")
            return await self.start_from_query(query, context)
        
        if query.data.startswith("view_category_"):
            category_id = query.data.split("_")[2]
            context.user_data['view_category_id'] = category_id
            context.user_data['view_page'] = 0
            
            keyboard = get_storage_groups_keyboard(category_id, 0)
            if not keyboard:
                await query.edit_message_text("❌ لا توجد مجموعات مخزنة في هذه الفئة.")
                return 11
            
            await query.edit_message_text(
                "📋 المجموعات المخزنة في هذه الفئة:",
                reply_markup=keyboard
            )
            return 12  # VIEW_STORAGE_GROUPS
        
        return 11

    @owner_only
    async def view_storage_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """عرض مجموعات التخزين"""
        query = update.callback_query
        await query.answer()
        
        category_id = context.user_data['view_category_id']
        page = context.user_data.get('view_page', 0)
        
        if query.data == "cancel":
            await query.edit_message_text("تم الإلغاء.")
            return await self.start_from_query(query, context)
        
        if query.data == "back_categories":
            keyboard = get_storage_categories_keyboard()
            await query.edit_message_text(
                "📁 اختر فئة لعرض المجموعات المخزنة فيها:",
                reply_markup=keyboard
            )
            return 11
        
        if query.data.startswith("prev_") or query.data.startswith("next_"):
            parts = query.data.split('_')
            page = int(parts[1])
            action = parts[2] if len(parts) > 2 else "view"
            context.user_data['view_page'] = page
            
            keyboard = get_storage_groups_keyboard(category_id, page, action)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            return 12
        
        return 12

    @owner_only
    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تصدير البيانات"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("تم الإلغاء.")
            return await self.start_from_query(query, context)
        
        if query.data.startswith("export_category_"):
            category_id = query.data.split("_")[2]
            context.user_data['export_category_id'] = category_id
            context.user_data['export_page'] = 0
            
            keyboard = get_storage_groups_keyboard(category_id, 0, "export")
            if not keyboard:
                await query.edit_message_text("❌ لا توجد مجموعات مخزنة في هذه الفئة.")
                return 14
            
            await query.edit_message_text(
                "📋 اختر مجموعة لتصدير أعضائها:",
                reply_markup=keyboard
            )
            return 14
        
        return 14

    @owner_only
    async def export_group_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تصدير بيانات مجموعة معينة"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("export_group_"):
            group_id = query.data.split("_")[2]
            
            # تصدير البيانات
            success = await self.exporter.export_group_members(update, context, group_id)
            if success:
                await query.answer("✅ تم تصدير البيانات بنجاح")
            else:
                await query.answer("❌ فشل في تصدير البيانات", show_alert=True)
        
        elif query.data.startswith("prev_") or query.data.startswith("next_"):
            parts = query.data.split('_')
            page = int(parts[1])
            context.user_data['export_page'] = page
            
            category_id = context.user_data['export_category_id']
            keyboard = get_storage_groups_keyboard(category_id, page, "export")
            await query.edit_message_reply_markup(reply_markup=keyboard)
            return 14
        
        return 14

    @owner_only
    async def start_from_query(self, query, context):
        """العودة للقائمة الرئيسية من استعلام"""
        await query.edit_message_text("العودة للقائمة الرئيسية...")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="اختر أحد الخيارات:",
            reply_markup=ReplyKeyboardMarkup([
                ["📥 تخزين الأعضاء من قروب مخفي"],
                ["👁️ تخزين الأعضاء من قروب ظاهر"],
                ["📂 عرض القروبات المخزنة", "📤 تصدير البيانات"]
            ], resize_keyboard=True)
        )
        return 0

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إلغاء العملية الحالية"""
        await update.message.reply_text(
            "تم إلغاء العملية.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await self.start(update, context)