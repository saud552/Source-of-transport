# -*- coding: utf-8 -*-
"""
معالجات بوت النقل
"""

import logging
import asyncio
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transf.config import (
    MAIN_MENU, SELECT_SOURCE_GROUP, SELECT_ACCOUNT_CATEGORY, SELECT_ACCOUNTS,
    ENTER_TARGET_GROUP, CONFIRM_TRANSFER, TRANSFER_IN_PROGRESS,
    VIEW_TRANSFER_HISTORY, VIEW_AVAILABLE_GROUPS, MAX_MEMBERS_PER_BATCH
)
from transf.database import TransferDatabaseManager
from transf.transfer_manager import TransferManager
from transf.keyboards import TransferKeyboards
from transf.utils import TransferUtils

logger = logging.getLogger(__name__)

class TransferHandlers:
    """معالجات بوت النقل"""
    
    def __init__(self, db_manager: TransferDatabaseManager):
        self.db_manager = db_manager
        self.transfer_manager = TransferManager(db_manager)
        self.keyboards = TransferKeyboards()
        self.utils = TransferUtils()
        self.current_transfer = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء البوت"""
        user_id = update.effective_user.id
        
        # التحقق من صلاحيات المدير
        if not self.utils.is_admin(user_id):
            await update.message.reply_text("❌ عذراً، هذا البوت مخصص للمديرين فقط.")
            return ConversationHandler.END
        
        welcome_text = """
🤖 **بوت نقل الأعضاء**

مرحباً بك في بوت نقل الأعضاء! يمكنك استخدام هذا البوت لنقل الأعضاء من المجموعات المخزنة مسبقاً إلى مجموعات جديدة.

**الوظائف المتاحة:**
• 📤 نقل الأعضاء من المجموعات المخزنة
• 📊 عرض تاريخ عمليات النقل
• 📋 عرض المجموعات المتاحة للنقل
• ⚙️ إدارة عمليات النقل

اختر الوظيفة المطلوبة:
        """
        
        keyboard = self.keyboards.main_menu()
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return MAIN_MENU
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """القائمة الرئيسية"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "start_transfer":
            return await self.start_transfer_flow(update, context)
        elif query.data == "view_history":
            return await self.view_transfer_history(update, context)
        elif query.data == "view_groups":
            return await self.view_available_groups(update, context)
        elif query.data == "cancel":
            await query.edit_message_text("تم إلغاء العملية.")
            return ConversationHandler.END
        
        return MAIN_MENU
    
    async def start_transfer_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء عملية النقل"""
        query = update.callback_query
        await query.answer()
        
        # الحصول على المجموعات المتاحة
        groups = await self.db_manager.get_available_source_groups()
        
        if not groups:
            await query.edit_message_text(
                "❌ لا توجد مجموعات مخزنة متاحة للنقل.\n\nتأكد من أنك قمت بتخزين أعضاء من مجموعات مسبقاً."
            )
            return MAIN_MENU
        
        keyboard = self.keyboards.source_groups_keyboard(groups)
        await query.edit_message_text(
            "📤 **اختر المجموعة المصدر:**\n\n"
            "اختر المجموعة التي تريد نقل الأعضاء منها:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_SOURCE_GROUP
    
    async def select_source_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """اختيار المجموعة المصدر"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self.main_menu(update, context)
        
        # استخراج معرف المجموعة
        group_id = int(query.data.split("_")[1])
        
        # حفظ معرف المجموعة في السياق
        context.user_data['source_group_id'] = group_id
        
        # الحصول على معلومات المجموعة
        groups = await self.db_manager.get_available_source_groups()
        selected_group = next((g for g in groups if g['group_id'] == group_id), None)
        
        if not selected_group:
            await query.edit_message_text("❌ المجموعة المحددة غير موجودة.")
            return MAIN_MENU
        
        # حفظ معلومات المجموعة
        context.user_data['source_group_info'] = selected_group
        
        # الحصول على فئات الحسابات
        categories = await self.db_manager.get_account_categories()
        
        if not categories:
            await query.edit_message_text(
                "❌ لا توجد حسابات متاحة للنقل.\n\nتأكد من أنك قمت بتسجيل حسابات مسبقاً."
            )
            return MAIN_MENU
        
        keyboard = self.keyboards.account_categories_keyboard(categories)
        await query.edit_message_text(
            f"📱 **اختر فئة الحسابات:**\n\n"
            f"**المجموعة المصدر:** {selected_group['title']}\n"
            f"**عدد الأعضاء المخزنين:** {selected_group['stored_members_count']}\n\n"
            f"اختر فئة الحسابات التي تريد استخدامها للنقل:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_ACCOUNT_CATEGORY
    
    async def select_account_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """اختيار فئة الحسابات"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self.start_transfer_flow(update, context)
        
        # استخراج معرف الفئة
        category_id = query.data.split("_")[1]
        
        # حفظ معرف الفئة في السياق
        context.user_data['account_category_id'] = category_id
        
        # الحصول على حسابات الفئة
        accounts = await self.db_manager.get_accounts_by_category(category_id)
        
        if not accounts:
            await query.edit_message_text(
                "❌ لا توجد حسابات متاحة في هذه الفئة."
            )
            return SELECT_ACCOUNT_CATEGORY
        
        # حفظ الحسابات في السياق
        context.user_data['selected_accounts'] = accounts
        
        keyboard = self.keyboards.confirm_accounts_keyboard(accounts)
        await query.edit_message_text(
            f"✅ **تأكيد الحسابات المختارة:**\n\n"
            f"تم العثور على {len(accounts)} حساب في هذه الفئة.\n\n"
            f"هل تريد المتابعة مع هذه الحسابات؟",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_ACCOUNTS
    
    async def select_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأكيد الحسابات المختارة"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            return await self.select_source_group(update, context)
        elif query.data == "confirm_accounts":
            await query.edit_message_text(
                "📝 **أدخل رابط أو معرف المجموعة الهدف:**\n\n"
                "أرسل رابط المجموعة أو معرفها (مثل: @groupname أو https://t.me/groupname):",
                parse_mode=ParseMode.MARKDOWN
            )
            return ENTER_TARGET_GROUP
        
        return SELECT_ACCOUNTS
    
    async def enter_target_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إدخال المجموعة الهدف"""
        if update.message.text.lower() in ['/cancel', 'إلغاء']:
            await update.message.reply_text("تم إلغاء العملية.")
            return ConversationHandler.END
        
        target_group_input = update.message.text.strip()
        
        # استخراج معرف المجموعة من الرابط
        target_group_id, target_group_title = self.utils.extract_group_info(target_group_input)
        
        if not target_group_id:
            await update.message.reply_text(
                "❌ رابط المجموعة غير صحيح.\n\n"
                "تأكد من أن الرابط صحيح (مثل: @groupname أو https://t.me/groupname)"
            )
            return ENTER_TARGET_GROUP
        
        # حفظ معلومات المجموعة الهدف
        context.user_data['target_group_id'] = target_group_id
        context.user_data['target_group_title'] = target_group_title
        
        # الحصول على معلومات المجموعة المصدر
        source_group_info = context.user_data.get('source_group_info', {})
        selected_accounts = context.user_data.get('selected_accounts', [])
        
        # عرض تأكيد العملية
        keyboard = self.keyboards.confirm_transfer_keyboard()
        await update.message.reply_text(
            f"📋 **تأكيد عملية النقل:**\n\n"
            f"**المجموعة المصدر:** {source_group_info.get('title', 'غير محدد')}\n"
            f"**المجموعة الهدف:** {target_group_title}\n"
            f"**عدد الحسابات:** {len(selected_accounts)}\n"
            f"**عدد الأعضاء المتوقع:** {source_group_info.get('stored_members_count', 0)}\n\n"
            f"هل تريد المتابعة مع هذه الإعدادات؟",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return CONFIRM_TRANSFER
    
    async def confirm_transfer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأكيد عملية النقل"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            await query.edit_message_text(
                "📝 **أدخل رابط أو معرف المجموعة الهدف:**\n\n"
                "أرسل رابط المجموعة أو معرفها (مثل: @groupname أو https://t.me/groupname):",
                parse_mode=ParseMode.MARKDOWN
            )
            return ENTER_TARGET_GROUP
        elif query.data == "start_transfer":
            return await self.start_transfer_process(update, context)
        
        return CONFIRM_TRANSFER
    
    async def start_transfer_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء عملية النقل الفعلية"""
        query = update.callback_query
        await query.answer()
        
        # الحصول على البيانات المحفوظة
        source_group_info = context.user_data.get('source_group_info', {})
        target_group_id = context.user_data.get('target_group_id')
        target_group_title = context.user_data.get('target_group_title')
        selected_accounts = context.user_data.get('selected_accounts', [])
        account_category_id = context.user_data.get('account_category_id')
        
        # إنشاء عملية النقل
        transfer_id = await self.db_manager.create_transfer_operation(
            source_group_id=source_group_info['group_id'],
            source_group_title=source_group_info['title'],
            target_group_id=target_group_id,
            target_group_title=target_group_title,
            account_category=account_category_id
        )
        
        # الحصول على الأعضاء المخزنين
        stored_members = await self.db_manager.get_stored_members_for_group(source_group_info['group_id'])
        
        if not stored_members:
            await query.edit_message_text(
                "❌ لا توجد أعضاء مخزنين في هذه المجموعة."
            )
            return MAIN_MENU
        
        # إضافة تفاصيل النقل
        await self.db_manager.add_transfer_details(transfer_id, stored_members)
        
        # تحديث إحصائيات العملية
        await self.db_manager.update_transfer_operation(
            transfer_id,
            total_members=len(stored_members),
            status='running',
            started_at=context.bot_data.get('current_time', 'now')
        )
        
        # بدء عملية النقل
        keyboard = self.keyboards.transfer_control_keyboard()
        await query.edit_message_text(
            f"🚀 **بدء عملية النقل...**\n\n"
            f"**المجموعة المصدر:** {source_group_info['title']}\n"
            f"**المجموعة الهدف:** {target_group_title}\n"
            f"**عدد الأعضاء:** {len(stored_members)}\n"
            f"**عدد الحسابات:** {len(selected_accounts)}\n\n"
            f"⏳ جاري النقل...",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # تشغيل عملية النقل في الخلفية
        asyncio.create_task(self.transfer_manager.start_transfer(
            transfer_id, stored_members, selected_accounts, update, context
        ))
        
        return TRANSFER_IN_PROGRESS
    
    async def view_transfer_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """عرض تاريخ عمليات النقل"""
        query = update.callback_query
        await query.answer()
        
        operations = await self.db_manager.get_transfer_operations(limit=10)
        
        if not operations:
            await query.edit_message_text(
                "📊 **تاريخ عمليات النقل:**\n\nلا توجد عمليات نقل سابقة.",
                parse_mode=ParseMode.MARKDOWN
            )
            return MAIN_MENU
        
        text = "📊 **تاريخ عمليات النقل:**\n\n"
        for i, op in enumerate(operations, 1):
            status_emoji = {
                'completed': '✅',
                'running': '🔄',
                'failed': '❌',
                'paused': '⏸️',
                'pending': '⏳'
            }.get(op['status'], '❓')
            
            text += f"{i}. {status_emoji} **{op['source_group_title']}** → **{op['target_group_title']}**\n"
            text += f"   📊 {op['transferred_members']}/{op['total_members']} أعضاء\n"
            text += f"   📅 {op['created_at']}\n\n"
        
        keyboard = self.keyboards.back_to_main_keyboard()
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return MAIN_MENU
    
    async def view_available_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """عرض المجموعات المتاحة للنقل"""
        query = update.callback_query
        await query.answer()
        
        groups = await self.db_manager.get_available_source_groups()
        
        if not groups:
            await query.edit_message_text(
                "📋 **المجموعات المتاحة للنقل:**\n\nلا توجد مجموعات مخزنة متاحة للنقل.",
                parse_mode=ParseMode.MARKDOWN
            )
            return MAIN_MENU
        
        text = "📋 **المجموعات المتاحة للنقل:**\n\n"
        for i, group in enumerate(groups, 1):
            text += f"{i}. **{group['title']}**\n"
            text += f"   👥 {group['stored_members_count']} عضو مخزن\n"
            if group.get('username'):
                text += f"   🔗 @{group['username']}\n"
            text += "\n"
        
        keyboard = self.keyboards.back_to_main_keyboard()
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return MAIN_MENU
    
    async def handle_transfer_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة أزرار التحكم في النقل"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "pause_transfer":
            # إيقاف النقل مؤقتاً
            await query.edit_message_text("⏸️ تم إيقاف النقل مؤقتاً.")
        elif query.data == "resume_transfer":
            # استئناف النقل
            await query.edit_message_text("🔄 تم استئناف النقل.")
        elif query.data == "cancel_transfer":
            # إلغاء النقل
            await query.edit_message_text("❌ تم إلغاء النقل.")
            return MAIN_MENU
        
        return TRANSFER_IN_PROGRESS
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إلغاء العملية الحالية"""
        await update.message.reply_text("تم إلغاء العملية.")
        return ConversationHandler.END