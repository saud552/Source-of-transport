# -*- coding: utf-8 -*-
import asyncio
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from .decorators import owner_only
from .keyboards import (
    get_settings_menu_keyboard, get_last_seen_settings_keyboard,
    get_storage_category_groups_keyboard, get_storage_group_detail_keyboard,
    get_storage_main_menu, get_categories_keyboard,
    get_storage_mechanism_keyboard
)
from .group_manager import GroupManager
from .database import StorageDatabaseManager
from .export import DataExporter

logger = logging.getLogger(__name__)

class StorageHandlers:
    def __init__(self, db_manager: StorageDatabaseManager, group_manager: GroupManager):
        self.db_manager = db_manager
        self.group_manager = group_manager
        self.exporter = DataExporter(db_manager)

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        msg = "👋 مرحباً بك في نظام تخزين أعضاء التليجرام\nاختر أحد الخيارات:"
        kb = get_storage_main_menu()
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=kb)
        else:
            await update.message.reply_text(msg, reply_markup=kb)
        return 0 # MAIN_MENU

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "storage_hidden":
            await query.edit_message_text("📩 أرسل روابط المجموعات (كل رابط في سطر منفصل):")
            return 1 # HIDDEN_INPUT_LINKS
        elif data == "storage_visible":
            await query.edit_message_text("👁️ أرسل روابط المجموعات (كل رابط في سطر منفصل):")
            return 6 # VISIBLE_INPUT_LINKS
        elif data == "view_storage":
            cats = await self.db_manager.get_storage_categories()
            if not cats:
                await query.edit_message_text("❌ لا توجد فئات تخزين.", reply_markup=get_storage_main_menu())
                return 0
            kb = get_categories_keyboard(cats, prefix="view_cat")
            await query.edit_message_text("📂 اختر فئة لعرض المجموعات المخزنة:", reply_markup=kb)
            return 10 # VIEW_STORAGE_CATEGORIES
        elif data == "storage_settings":
            await query.edit_message_text("هذا القسم قيد التطوير...", reply_markup=get_storage_main_menu())
            return 0
        elif data == "cancel":
            return await self.cancel_operation(update, context)

        return 0

    @owner_only
    async def hidden_input_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        links = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not links:
            await update.message.reply_text("❌ لم يتم التعرف على روابط صالحة.")
            return 1

        context.user_data['hidden_links'] = links
        
        # عرض فئات الحسابات
        cats = await self.db_manager.get_account_categories()
        if not cats:
            await update.message.reply_text("❌ لا توجد فئات حسابات لاستخدامها.")
            return await self.start(update, context)

        kb = get_categories_keyboard(cats, prefix="acc_cat")
        await update.message.reply_text("👤 اختر فئة الحسابات التي ستقوم بعملية التخزين:", reply_markup=kb)
        return 2 # HIDDEN_SELECT_ACC_CAT

    @owner_only
    async def hidden_select_acc_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel": return await self.cancel_operation(update, context)
        
        cat_id = query.data.split("_")[2]
        accounts = await self.db_manager.get_accounts_by_category(cat_id)
        if not accounts:
            await query.edit_message_text("❌ لا يوجد حسابات فعالة في هذه الفئة.")
            return await self.start(update, context)

        context.user_data['hidden_accounts'] = accounts
        
        # عرض فئات مجموعات التخزين
        storage_cats = await self.db_manager.get_storage_categories()
        kb = get_categories_keyboard(storage_cats, prefix="stg_cat")
        await query.edit_message_text("📁 أرسل اسم فئة المجموعات لتخزين البيانات فيها أو اختر فئة موجودة:", reply_markup=kb)
        return 3 # HIDDEN_SELECT_STORAGE_CAT

    @owner_only
    async def hidden_select_storage_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            if query.data == "cancel": return await self.cancel_operation(update, context)

            # Fetch name based on ID, simple workaround is parsing name or refetching
            cat_id = query.data.split("_")[2]
            storage_cats = await self.db_manager.get_storage_categories()
            cat_name = next((c['name'] for c in storage_cats if str(c['id']) == cat_id), "Default")
            context.user_data['hidden_storage_cat'] = cat_name

            kb = get_storage_mechanism_keyboard()
            await query.edit_message_text(f"✅ الفئة: {cat_name}\n\n⚙️ اختر آلية التخزين المخفي:", reply_markup=kb)
            return 4 # HIDDEN_SELECT_MECHANISM

        if update.message and update.message.text:
            context.user_data['hidden_storage_cat'] = update.message.text.strip()
            kb = get_storage_mechanism_keyboard()
            await update.message.reply_text("⚙️ اختر آلية التخزين المخفي:", reply_markup=kb)
            return 4

    @owner_only
    async def hidden_select_mechanism(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel": return await self.cancel_operation(update, context)
        
        mech = 'monthly' if query.data == "mech_monthly" else 'count'
        
        links = context.user_data['hidden_links']
        accounts = context.user_data['hidden_accounts']
        cat_name = context.user_data['hidden_storage_cat']

        # Start storage engine in group_manager
        await self.group_manager.start_hidden_storage(update, context, links, accounts, cat_name, mech)
        return 5 # STORAGE_IN_PROGRESS


    @owner_only
    async def visible_input_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        links = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not links:
            await update.message.reply_text("❌ لم يتم التعرف على روابط صالحة.")
            return 6

        context.user_data['visible_links'] = links
        
        # عرض فئات الحسابات
        cats = await self.db_manager.get_account_categories()
        if not cats:
            await update.message.reply_text("❌ لا توجد فئات حسابات لاستخدامها.")
            return await self.start(update, context)

        kb = get_categories_keyboard(cats, prefix="vis_acc_cat")
        await update.message.reply_text("👤 اختر فئة الحسابات التي ستقوم بعملية التخزين الظاهر:", reply_markup=kb)
        return 7 # VISIBLE_SELECT_ACC_CAT

    @owner_only
    async def visible_select_acc_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel": return await self.cancel_operation(update, context)

        cat_id = query.data.split("_")[3]
        accounts = await self.db_manager.get_accounts_by_category(cat_id)
        if not accounts:
            await query.edit_message_text("❌ لا يوجد حسابات فعالة في هذه الفئة.")
            return await self.start(update, context)

        context.user_data['visible_accounts'] = accounts

        # عرض فئات مجموعات التخزين
        storage_cats = await self.db_manager.get_storage_categories()
        kb = get_categories_keyboard(storage_cats, prefix="vis_stg_cat")
        await query.edit_message_text("📁 أرسل اسم فئة المجموعات لتخزين البيانات فيها أو اختر فئة موجودة:", reply_markup=kb)
        return 8 # VISIBLE_SELECT_STORAGE_CAT

    @owner_only
    async def visible_select_storage_cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        cat_name = ""
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            if query.data == "cancel": return await self.cancel_operation(update, context)

            cat_id = query.data.split("_")[3]
            storage_cats = await self.db_manager.get_storage_categories()
            cat_name = next((c['name'] for c in storage_cats if str(c['id']) == cat_id), "Default")
            context.user_data['visible_storage_cat'] = cat_name

            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأكيد بدء التخزين الظاهر", callback_data="confirm_visible_storage")]])
            await query.edit_message_text(f"✅ الفئة: {cat_name}\n\nتأكيد بدء العملية؟", reply_markup=kb)
            return 9 # VISIBLE_CONFIRM

        if update.message and update.message.text:
            cat_name = update.message.text.strip()
            context.user_data['visible_storage_cat'] = cat_name
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأكيد بدء التخزين الظاهر", callback_data="confirm_visible_storage")]])
            await update.message.reply_text(f"✅ الفئة: {cat_name}\n\nتأكيد بدء العملية؟", reply_markup=kb)
            return 9

    @owner_only
    async def visible_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel": return await self.cancel_operation(update, context)

        links = context.user_data['visible_links']
        accounts = context.user_data['visible_accounts']
        cat_name = context.user_data['visible_storage_cat']

        # Start visible storage engine
        await self.group_manager.start_visible_storage(update, context, links, accounts, cat_name)
        return 5 # STORAGE_IN_PROGRESS

    @owner_only
    async def handle_storage_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        job_id = context.user_data.get('current_storage_job')

        if not job_id: return 5
        
        if data == "pause_storage":
            self.group_manager.pause_job(job_id)
        elif data == "resume_storage":
            self.group_manager.resume_job(job_id)
        elif data == "finish_storage":
            self.group_manager.cancel_job(job_id)
            await query.edit_message_text("✅ تم إنهاء العملية والرجوع للقائمة الرئيسية.")
            return await self.start(update, context)

        return 5

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        job_id = context.user_data.get('current_storage_job')
        if job_id:
            self.group_manager.cancel_job(job_id)

        msg = "🚫 تم إلغاء العملية."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return await self.start(update, context)


    @owner_only
    async def view_storage_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "cancel": return await self.cancel_operation(update, context)
        if data == "view_storage": return await self.main_menu(update, context)

        cat_id = data.split("_")[2]
        stats = await self.db_manager.get_storage_category_stats(cat_id)

        msg = f"📊 **إحصائيات الفئة**\n\n"
        msg += f"📁 المجموعات: {stats['total_groups']}\n"
        msg += f"👥 الأعضاء المخزنين: {stats['total_members']}\n"
        msg += f"✅ تم النقل: {stats['total_transferred']}\n"
        msg += f"⏳ لم يتم النقل: {stats['total_pending']}\n"

        total_groups = await self.db_manager.get_total_groups_in_category(cat_id)
        groups = await self.db_manager.get_groups_by_category(cat_id, offset=0, limit=40)

        kb = get_storage_category_groups_keyboard(groups, cat_id, page=0, total_groups=total_groups)
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
        return 11 # VIEW_STORAGE_GROUPS

    @owner_only
    async def view_storage_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "cancel": return await self.cancel_operation(update, context)
        if data == "view_storage":
            cats = await self.db_manager.get_storage_categories()
            kb = get_categories_keyboard(cats, prefix="view_cat")
            await query.edit_message_text("📂 اختر فئة لعرض المجموعات المخزنة:", reply_markup=kb)
            return 10

        if data.startswith("page_groups_"):
            parts = data.split("_")
            cat_id = parts[2]
            page = int(parts[3])
            offset = page * 40

            stats = await self.db_manager.get_storage_category_stats(cat_id)
            total_groups = await self.db_manager.get_total_groups_in_category(cat_id)
            groups = await self.db_manager.get_groups_by_category(cat_id, offset=offset, limit=40)

            msg = f"📊 **إحصائيات الفئة**\n\n"
            msg += f"📁 المجموعات: {stats['total_groups']}\n"
            msg += f"👥 الأعضاء المخزنين: {stats['total_members']}\n"
            msg += f"✅ تم النقل: {stats['total_transferred']}\n"
            msg += f"⏳ لم يتم النقل: {stats['total_pending']}\n"

            kb = get_storage_category_groups_keyboard(groups, cat_id, page=page, total_groups=total_groups)
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
            return 11

        elif data.startswith("view_group_"):
            group_id = data.split("_")[2]
            g = await self.db_manager.get_storage_group_details(group_id)
            if not g:
                await query.edit_message_text("❌ لم يتم العثور على المجموعة.")
                return 11

            msg = f"ℹ️ **معلومات المجموعة**\n\n"
            msg += f"📛 الاسم: {g['title']}\n"
            msg += f"🔗 الرابط/اليوزر: @{g.get('username') or 'لا يوجد'}\n"
            msg += f"🆔 الايدي: {g['group_id']}\n"
            msg += f"⚙️ نوع التخزين: {'ظاهر' if g['storage_type'] == 'visible' else 'مخفي'}\n\n"
            msg += f"👥 إجمالي المخزنين: {g['total_members']}\n"
            msg += f"✅ تم النقل: {g['total_transferred']}\n"
            msg += f"⏳ لم يتم النقل: {g['total_pending']}\n"

            # Need category id to go back
            cat_id = await self.db_manager.pool.fetchval("SELECT category_id FROM storage_groups WHERE id = $1", g['id'])

            kb = get_storage_group_detail_keyboard(str(g['id']), str(cat_id))
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
            return 11

        elif data.startswith("delete_group_"):
            group_id = data.split("_")[2]
            cat_id = await self.db_manager.pool.fetchval("SELECT category_id FROM storage_groups WHERE id = $1", group_id)
            await self.db_manager.delete_storage_group(group_id)
            await query.answer("✅ تم مسح التخزين وتنظيف البيانات", show_alert=True)

            # Go back to category page 0
            stats = await self.db_manager.get_storage_category_stats(str(cat_id))
            total_groups = await self.db_manager.get_total_groups_in_category(str(cat_id))
            groups = await self.db_manager.get_groups_by_category(str(cat_id), offset=0, limit=40)
            msg = f"📊 **إحصائيات الفئة**\n\n📁 المجموعات: {stats['total_groups']}\n👥 المخزنين: {stats['total_members']}\n✅ تم النقل: {stats['total_transferred']}\n⏳ لم يتم النقل: {stats['total_pending']}\n"
            kb = get_storage_category_groups_keyboard(groups, str(cat_id), page=0, total_groups=total_groups)
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
            return 11

        elif data.startswith("restart_group_"):
            group_id = data.split("_")[2]
            await self.db_manager.clear_group_members(group_id)
            await query.answer("✅ تم مسح الأعضاء السابقين. يرجى استخدام قسم التخزين للبدء من جديد.", show_alert=True)
            # Future enhancement: could actually restart the background task if we preserved the exact mechanism config.
            return 11

        return 11

    @owner_only
    async def storage_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "cancel": return await self.cancel_operation(update, context)
        
        if data == "settings_monthly":
            current_val = await self.db_manager.get_setting('monthly_duration')
            await query.edit_message_text(f"📅 **إعداد التخزين الشهري**\n\nالقيمة الحالية: {current_val} أشهر\n\nأرسل عدد الأشهر الجديد (أرقام فقط):", parse_mode="Markdown")
            return 14 # SETTINGS_MONTHLY

        elif data == "settings_count":
            current_val = await self.db_manager.get_setting('message_count')
            await query.edit_message_text(f"💬 **إعداد عدد الرسائل**\n\nالقيمة الحالية: {current_val} رسالة\n\nأرسل عدد الرسائل الجديد (مثلاً 50000):", parse_mode="Markdown")
            return 15 # SETTINGS_COUNT

        elif data == "settings_last_seen":
            current_val = await self.db_manager.get_setting('last_seen_filter')

            val_map = {
                'recently': 'منذ زمن قريب',
                'week': 'منذ أسبوع أو أكثر',
                'month': 'منذ شهر أو أكثر',
                'empty': 'منذ زمن طويل',
                'all': 'جميع الخيارات'
            }

            kb = get_last_seen_settings_keyboard()
            await query.edit_message_text(f"⏳ **فلتر آخر ظهور**\n\nالقيمة الحالية: {val_map.get(current_val, current_val)}\n\nاختر الفلتر الجديد:", reply_markup=kb, parse_mode="Markdown")
            return 16 # SETTINGS_LAST_SEEN

        return 13

    @owner_only
    async def settings_monthly_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        val = update.message.text.strip()
        if not val.isdigit():
            await update.message.reply_text("❌ يرجى إرسال أرقام فقط.")
            return 14

        await self.db_manager.set_setting('monthly_duration', val)
        await update.message.reply_text("✅ تم الحفظ بنجاح.", reply_markup=get_settings_menu_keyboard())
        return 13

    @owner_only
    async def settings_count_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        val = update.message.text.strip()
        if not val.isdigit():
            await update.message.reply_text("❌ يرجى إرسال أرقام فقط.")
            return 15

        await self.db_manager.set_setting('message_count', val)
        await update.message.reply_text("✅ تم الحفظ بنجاح.", reply_markup=get_settings_menu_keyboard())
        return 13

    @owner_only
    async def settings_last_seen_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "storage_settings":
            kb = get_settings_menu_keyboard()
            await query.edit_message_text("⚙️ **إعدادات بوت التخزين**\n\nاختر القسم الذي تريد تعديله:", reply_markup=kb, parse_mode="Markdown")
            return 13

        if data.startswith("ls_"):
            val = data.split("_")[1]
            await self.db_manager.set_setting('last_seen_filter', val)

            kb = get_settings_menu_keyboard()
            await query.edit_message_text("✅ تم تحديث فلتر آخر ظهور بنجاح.", reply_markup=kb)
            return 13

        return 16
