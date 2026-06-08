# -*- coding: utf-8 -*-
import asyncio
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import uuid

from .decorators import owner_only
from .keyboards import TransferKeyboards
from .transfer_manager import TransferManager
from .database import TransferDatabaseManager

logger = logging.getLogger(__name__)

class TransferHandlers:
    def __init__(self, db_manager: TransferDatabaseManager):
        self.db_manager = db_manager
        self.transfer_manager = TransferManager(db_manager)
        self.kb = TransferKeyboards()

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        msg = "👋 مرحباً بك في نظام نقل أعضاء التليجرام\nاختر أحد الخيارات:"
        keyboard = self.kb.main_menu()
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, reply_markup=keyboard)
        return 0 # MAIN_MENU

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "transfer_direct":
            await query.edit_message_text("📥 أرسل روابط المجموعات المصدر (كل رابط في سطر منفصل):")
            return 1 # DIRECT_INPUT_LINKS
        elif data == "transfer_view_storage":
            cats = await self.db_manager.get_storage_categories()
            if not cats:
                await query.edit_message_text("❌ لا توجد فئات تخزين.", reply_markup=self.kb.main_menu())
                return 0
            # Reuse account cat keyboard visually
            kb = self.kb.account_categories_keyboard(cats)
            await query.edit_message_text("📂 اختر فئة לעرض المجموعات المخزنة:", reply_markup=kb)
            return 6 # VIEW_STORAGE_CATEGORIES
        elif data == "transfer_settings":
            kb = self.kb.settings_menu()
            await query.edit_message_text("⚙️ **إعدادات النقل**\n\nاختر القسم لتعديله:", reply_markup=kb, parse_mode="Markdown")
            return 11 # SETTINGS_MENU
        elif data == "cancel":
            return await self.cancel_operation(update, context)
        return 0

    # ----- Direct Transfer Flow -----
    @owner_only
    async def direct_input_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        links = [line.strip() for line in text.split('\n') if line.strip()]
        if not links:
            await update.message.reply_text("❌ لم يتم التعرف على روابط صالحة.")
            return 1
        context.user_data['direct_links'] = links
        await update.message.reply_text("📥 أرسل رابط/معرف المجموعة الهدف:")
        return 2 # DIRECT_TARGET_LINK

    @owner_only
    async def direct_target_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        # Resolve username simple
        target_group = text.split("/")[-1].replace("@", "")
        # Real logic would resolve this to an ID. We assume string for now or basic mock.
        context.user_data['direct_target'] = target_group
        
        cats = await self.db_manager.get_account_categories()
        if not cats:
            await update.message.reply_text("❌ لا توجد فئات حسابات.")
            return await self.start(update, context)
        kb = self.kb.account_categories_keyboard(cats)
        await update.message.reply_text("👤 اختر فئة الحسابات للنقل:", reply_markup=kb)
        return 3 # DIRECT_SELECT_ACC_CAT

    @owner_only
    async def direct_select_acc_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        cat_id = query.data.split("_")[1]
        accounts = await self.db_manager.get_accounts_by_category(cat_id)
        if not accounts:
            await query.edit_message_text("❌ الفئة لا تحتوي على حسابات نشطة.")
            return await self.start(update, context)

        context.user_data['direct_accounts'] = accounts
        kb = self.kb.confirm_transfer_keyboard()
        await query.edit_message_text("✅ تم اختيار الحسابات بنجاح.\nهل أنت متأكد من بدء عملية النقل المباشر؟", reply_markup=kb)
        return 4 # DIRECT_CONFIRM

    @owner_only
    async def direct_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        links = context.user_data['direct_links']
        accounts = context.user_data['direct_accounts']
        target = context.user_data['direct_target']
        
        # Call direct transfer (Need resolved integer target id usually, assuming 0 for now in this mock path)
        await self.transfer_manager.start_direct_transfer(target, links, accounts, update, context)
        return 5 # TRANSFER_IN_PROGRESS

    # ----- Stored Transfer Flow -----
    @owner_only
    async def view_storage_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        cat_id = query.data.split("_")[1]
        groups = await self.db_manager.get_groups_by_category(cat_id)
        if not groups:
            await query.edit_message_text("❌ لا توجد مجموعات مخزنة هنا.")
            return await self.start(update, context)

        # Simplified keyboard for demo
        kb = self.kb.source_groups_keyboard([{'title': g['title'], 'stored_members_count': g['member_count'], 'group_id': g['id']} for g in groups])
        await query.edit_message_text("📁 اختر المجموعة المخزنة:", reply_markup=kb)
        return 7 # VIEW_STORAGE_GROUPS

    @owner_only
    async def view_storage_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        group_id = query.data.split("_")[1]
        context.user_data['stored_group_id'] = group_id
        
        kb = self.kb.stored_group_action_keyboard(group_id, "dummy")
        await query.edit_message_text("⚙️ **خيارات النقل للمجموعة:**", reply_markup=kb, parse_mode="Markdown")
        # Reuse same state, we just catch the actions
        return 7
        
    @owner_only
    async def handle_stored_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.startswith("t_back_"): return await self.start(update, context)
        
        if data.startswith("t_new_"):
            context.user_data['transfer_mode'] = 'new'
            await self.db_manager.reset_stored_members_status(data.split("_")[2])
        elif data.startswith("t_resume_"):
            context.user_data['transfer_mode'] = 'resume'
        elif data.startswith("t_retry_"):
            context.user_data['transfer_mode'] = 'retry'

        await query.edit_message_text("📥 أرسل رابط/معرف المجموعة الهدف:")
        return 8 # STORED_TARGET_LINK

    @owner_only
    async def stored_target_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        target = update.message.text.strip().split("/")[-1].replace("@", "")
        context.user_data['stored_target'] = target
        
        cats = await self.db_manager.get_account_categories()
        kb = self.kb.account_categories_keyboard(cats)
        await update.message.reply_text("👤 اختر فئة الحسابات للنقل:", reply_markup=kb)
        return 9 # STORED_SELECT_ACC_CAT

    @owner_only
    async def stored_select_acc_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        cat_id = query.data.split("_")[1]
        accounts = await self.db_manager.get_accounts_by_category(cat_id)
        context.user_data['stored_accounts'] = accounts
        
        kb = self.kb.confirm_transfer_keyboard()
        await query.edit_message_text("✅ تم التأكيد. بدء عملية النقل؟", reply_markup=kb)
        return 10 # STORED_CONFIRM

    @owner_only
    async def stored_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back": return await self.start(update, context)
        
        group_id = context.user_data['stored_group_id']
        accounts = context.user_data['stored_accounts']
        target = context.user_data['stored_target']
        mode = context.user_data['transfer_mode']
        
        status_filter = 'pending' if mode == 'resume' else 'success' if mode == 'retry' else None
        members = await self.db_manager.get_stored_members_by_status(group_id, status_filter)
        
        if not members:
            await query.edit_message_text("❌ لا يوجد أعضاء لنقلهم بهذه الحالة.")
            return await self.start(update, context)
            
        transfer_id = str(uuid.uuid4())
        await self.transfer_manager.start_stored_transfer(transfer_id, group_id, target, members, accounts, update, context)
        return 5 # TRANSFER_IN_PROGRESS

    # ----- Settings Flow -----
    @owner_only
    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "back_to_main": return await self.start(update, context)
        
        if data == "set_delay":
            await query.edit_message_text("⏱️ أرسل الفاصل الزمني (أدنى، أقصى) مفصولاً بفاصلة. مثال: `2,5`")
            return 12 # SETTINGS_DELAY
        elif data == "set_batch_size":
            await query.edit_message_text("🔄 أرسل عدد الإضافات لكل حساب قبل التبديل:")
            return 13 # SETTINGS_BATCH_SIZE
        elif data == "set_ls_filter":
            kb = self.kb.last_seen_settings_keyboard()
            await query.edit_message_text("⏳ اختر فلتر آخر ظهور المطلوب:", reply_markup=kb)
            return 15 # SETTINGS_LAST_SEEN_FILTER
        return 11

    @owner_only
    async def settings_delay_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        try:
            min_d, max_d = map(int, text.split(","))
            await self.db_manager.set_setting('delay_min', str(min_d))
            await self.db_manager.set_setting('delay_max', str(max_d))
            await update.message.reply_text("✅ تم تحديث الفاصل الزمني.", reply_markup=self.kb.settings_menu())
        except:
            await update.message.reply_text("❌ صيغة خاطئة. مثال: 2,5")
            return 12
        return 11

    @owner_only
    async def settings_batch_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        if text.isdigit():
            await self.db_manager.set_setting('batch_size', text)
            await update.message.reply_text("✅ تم تحديث عدد الإضافات.", reply_markup=self.kb.settings_menu())
            return 11
        await update.message.reply_text("❌ يرجى إرسال أرقام فقط.")
        return 13

    @owner_only
    async def settings_ls_filter(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "transfer_settings":
            await query.edit_message_text("⚙️ **إعدادات النقل**\n\nاختر القسم لتعديله:", reply_markup=self.kb.settings_menu(), parse_mode="Markdown")
            return 11

        if data.startswith("tls_"):
            await self.db_manager.set_setting('ls_filter', data.split("_")[1])
            await query.edit_message_text("✅ تم تحديث فلتر آخر ظهور.", reply_markup=self.kb.settings_menu())
            return 11
        return 15

    # ----- Controls -----
    @owner_only
    async def transfer_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        # Real logic interacts with transfer_manager to pause/resume based on ID.
        # Since ID is in context or embedded in callback_data:
        tid = data.split("_")[-1] if "_" in data else context.user_data.get('direct_transfer_id')
        if tid and tid in self.transfer_manager.active_transfers:
            if "pause" in data:
                self.transfer_manager.active_transfers[tid]['status'] = 'paused'
            elif "resume" in data:
                self.transfer_manager.active_transfers[tid]['status'] = 'running'
            elif "cancel" in data:
                self.transfer_manager.active_transfers[tid]['status'] = 'cancelled'
                await query.edit_message_text("🚫 تم إلغاء عملية النقل.")
                return await self.start(update, context)
        return 5

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        msg = "🚫 تم إلغاء العملية."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return await self.start(update, context)
