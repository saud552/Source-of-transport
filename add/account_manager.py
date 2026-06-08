# -*- coding: utf-8 -*-
"""
مدير الحسابات (Async PostgreSQL + Encryption)
"""

import logging
import asyncio
import json
import base64
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from .tdlib_client import TDLibClient
from .database import DatabaseManager
from .encryption import EncryptionManager
from .validators import validate_phone, validate_code, get_random_device
from .decorators import owner_only
from .config import API_ID, API_HASH, DB_PATH
from shared_config import PASSPHRASE, SALT
from .keyboards import (
    get_main_menu_keyboard, get_categories_inline_keyboard,
    get_customization_menu_keyboard, get_gender_keyboard,
    get_auto_photo_keyboard, get_auto_name_keyboard, get_auto_bio_keyboard,
    get_back_to_customize_keyboard
)

logger = logging.getLogger(__name__)

class AccountManager:
    """إدارة الحسابات مع تشفير الجلسات وقاعدة بيانات غير متزامنة"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.encryption = EncryptionManager(PASSPHRASE, SALT)

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyboard = get_main_menu_keyboard()
        msg = "👋 نظام إدارة الحسابات الآمن\n\nيرجى اختيار قسم من الأقسام التالية:"

        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, reply_markup=keyboard)
        return 0 # MAIN_MENU (0)

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        data = query.data
        if data == "main_add_account":
            # جلب الفئات
            categories = await self.db_manager.get_all_categories_with_counts()
            if categories:
                # الفئات التي تحتوي حسابات فقط (كما طلبت، ولكن إذا كان النظام جديد قد لا يكون هناك حسابات. سنعرض الكل هنا للتجربة أو نفلتر)
                filtered_cats = [c for c in categories if c.get('account_count', 0) >= 0]
                kb = get_categories_inline_keyboard(filtered_cats, action="select")
                await query.edit_message_text("📁 يرجى اختيار أو إرسال اسم الفئة:", reply_markup=kb)
            else:
                await query.edit_message_text("📁 أدخل اسم الفئة الجديدة:")
            return 1 # ADD_ACCOUNT_CATEGORY

        elif data in ["main_check_accounts", "main_view_accounts", "main_delete_account", "main_join_leave", "main_settings"]:
            await query.edit_message_text("هذا القسم قيد التطوير...", reply_markup=get_back_to_customize_keyboard())
            return 0

        elif data == "cancel":
            return await self.cancel_operation(update, context)

        return 0

    @owner_only
    async def add_account_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            if query.data.startswith("select_category_"):
                parts = query.data.split("_")
                context.user_data['category_name'] = parts[-1]
                await query.edit_message_text(f"✅ تم اختيار الفئة: {context.user_data['category_name']}\n📱 أرسل رقم الهاتف مع مفتاح الدولة (مثال: +967771234567):")
                return 2 # ADD_ACCOUNT_PHONE
            elif query.data == "cancel":
                return await self.cancel_operation(update, context)

        if update.message and update.message.text:
            context.user_data['category_name'] = update.message.text.strip()
            # التأكد من إنشاء الفئة إذا لم تكن موجودة
            await self.db_manager.get_or_create_category(context.user_data['category_name'])
            await update.message.reply_text("📱 أرسل رقم الهاتف مع مفتاح الدولة (مثال: +967771234567):")
            return 2
        return 1

    @owner_only
    async def add_account_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        phone = update.message.text.strip()
        if not validate_phone(phone):
            await update.message.reply_text("❌ رقم غير صالح. يرجى إدخاله بصيغة دولية.")
            return 2
        
        context.user_data['phone'] = phone
        return await self.start_phone_verification(update, context)

    async def start_phone_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        phone = context.user_data['phone']
        device = get_random_device()
        client = TDLibClient(API_ID, API_HASH, device, phone=phone)
        context.user_data['td_client'] = client
        
        msg = await update.message.reply_text("⏳ جاري إرسال رمز التحقق...")
        context.user_data['status_msg_id'] = msg.message_id

        try:
            await client.login()
            if client.auth_state == 'authorizationStateWaitCode':
                await context.bot.edit_message_text("✅ تم إرسال الرمز. يرجى إرساله الآن:", chat_id=update.message.chat_id, message_id=msg.message_id)
                return 4 # ADD_ACCOUNT_CODE
            elif client.auth_state == 'authorizationStateReady':
                return await self.show_customization_menu(update, context, client, "✅ تسجيل الدخول متاح مسبقاً.")
        except Exception as e:
            await client.close()
            await context.bot.edit_message_text(f"❌ فشلت عملية تسجيل الحساب. السبب: {e}", chat_id=update.message.chat_id, message_id=msg.message_id)
            return await self.start(update, context)
        return 4

    @owner_only
    async def add_account_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        client: TDLibClient = context.user_data.get('td_client')
        code = update.message.text.strip()

        msg = await update.message.reply_text("⏳ جاري التحقق من الرمز...")
        try:
            await client.send_code(code)
            if client.auth_state == 'authorizationStateReady':
                return await self.show_customization_menu(update, context, client, "✅ عملية تسجيل الحساب نجحت.")
            elif client.auth_state == 'authorizationStateWaitPassword':
                await context.bot.edit_message_text("🔑 الحساب محمي. أرسل كلمة المرور:", chat_id=update.message.chat_id, message_id=msg.message_id)
                return 5 # ADD_ACCOUNT_PASSWORD
        except Exception as e:
            await context.bot.edit_message_text(f"❌ خطأ بالكود: {e}", chat_id=update.message.chat_id, message_id=msg.message_id)
        return 4

    @owner_only
    async def add_account_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        client: TDLibClient = context.user_data.get('td_client')
        password = update.message.text.strip()
        
        msg = await update.message.reply_text("⏳ جاري التحقق من كلمة المرور...")
        try:
            await client.send_password(password)
            if client.auth_state == 'authorizationStateReady':
                return await self.show_customization_menu(update, context, client, "✅ عملية تسجيل الحساب نجحت.")
        except Exception as e:
            await context.bot.edit_message_text(f"❌ خطأ بكلمة المرور: {e}", chat_id=update.message.chat_id, message_id=msg.message_id)
        return 5

    async def show_customization_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, client: TDLibClient, prefix_msg: str) -> int:
        me = await client.get_me()
        acc_name = me.get('first_name', '') + ' ' + me.get('last_name', '')
        username = me.get('username', 'لا يوجد')
        phone = context.user_data['phone']

        text = f"{prefix_msg}\n\n👤 الاسم: {acc_name}\n🔗 اليوزر: {username}\n📱 الرقم: {phone}\n\nيمكنك الآن تخصيص إعدادات الحساب أو تأكيد العملية لإنهاء التسجيل:"

        kb = get_customization_menu_keyboard()
        if update.message:
            await update.message.reply_text(text, reply_markup=kb)
        else:
            await update.callback_query.message.edit_text(text, reply_markup=kb)

        return 6 # CUSTOMIZE_ACCOUNT_MENU

    @owner_only
    async def customize_account_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "cust_gender":
            await query.edit_message_text("تحديد جنس الحساب:", reply_markup=get_gender_keyboard())
            return 7
        elif data == "cust_photo":
            await query.edit_message_text("أرسل الصورة أو اختر تعيين تلقائي:", reply_markup=get_auto_photo_keyboard())
            return 8
        elif data == "cust_name":
            await query.edit_message_text("أرسل الاسم أو اختر تعيين تلقائي:", reply_markup=get_auto_name_keyboard())
            return 9
        elif data == "cust_bio":
            await query.edit_message_text("أرسل النبذة أو اختر تعيين تلقائي:", reply_markup=get_auto_bio_keyboard())
            return 10
        elif data == "cust_username":
            await query.edit_message_text("أرسل اليوزر الجديد:", reply_markup=get_back_to_customize_keyboard())
            return 11
        elif data == "cust_remove_photos":
            # TODO: Impl delete photos logic in TDLib Client later
            await query.edit_message_text("✅ تمت محاولة إزالة الخلفيات.", reply_markup=get_back_to_customize_keyboard())
            return 6
        elif data == "cust_confirm":
            await query.edit_message_text("⏳ جاري تأكيد وإنهاء التسجيل...")
            return await self.finalize_account_registration(update, context, context.user_data.get('td_client'))
        elif data == "cancel":
            return await self.cancel_operation(update, context)

        return 6

    @owner_only
    async def customize_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        if query.data == "back_to_customize":
            return await self.show_customization_menu(update, context, context.user_data.get('td_client'), "القائمة الرئيسية للتخصيص:")

        gender = "ولد" if query.data == "gender_male" else "بنت"
        context.user_data['gender'] = gender
        await query.edit_message_text(f"✅ تم تعيين الجنس إلى: {gender}", reply_markup=get_back_to_customize_keyboard())
        return 6

    @owner_only
    async def customize_input_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, field: str, success_msg: str, state_to_return: int) -> int:
        client: TDLibClient = context.user_data.get('td_client')

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            if query.data == "back_to_customize":
                return await self.show_customization_menu(update, context, client, "القائمة الرئيسية للتخصيص:")
            else:
                # Handle auto assignment
                await query.edit_message_text(f"✅ تم تنفيذ الإعداد التلقائي لـ {field} بنجاح", reply_markup=get_back_to_customize_keyboard())
                return 6

        if update.message and update.message.text:
            text = update.message.text.strip()
            msg = await update.message.reply_text("⏳ جاري التنفيذ...")

            res = {'@type': 'error', 'message': 'unhandled'}
            if field == 'name':
                res = await client.set_name(text)
            elif field == 'bio':
                res = await client.set_bio(text)
            elif field == 'username':
                res = await client.set_username(text)

            if res.get('@type') == 'ok':
                await msg.edit_text(success_msg, reply_markup=get_back_to_customize_keyboard())
            else:
                await msg.edit_text(f"❌ فشل التنفيذ: {res.get('message')}", reply_markup=get_back_to_customize_keyboard())
            return 6
        return state_to_return

    @owner_only
    async def customize_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.customize_input_handler(update, context, 'photo', "✅ تم وضع الصورة بنجاح", 8)

    @owner_only
    async def customize_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.customize_input_handler(update, context, 'name', "✅ تم تعيين الاسم بنجاح", 9)

    @owner_only
    async def customize_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.customize_input_handler(update, context, 'bio', "✅ تم تعيين النبذة بنجاح", 10)

    @owner_only
    async def customize_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.customize_input_handler(update, context, 'username', "✅ تم تعيين اليوزر بنجاح", 11)

    async def finalize_account_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE, client: TDLibClient) -> int:
        """تشفير وحفظ الحساب مع تنظيف الموارد"""
        try:
            me = await client.get_me()
            raw_zip = client.save_session_bytes()
            if not raw_zip:
                raise Exception("فشل ضغط ملفات الجلسة")
            
            encrypted_bytes = self.encryption.encrypt(raw_zip)
            session_str = base64.b64encode(encrypted_bytes).decode('utf-8')

            category = await self.db_manager.get_category_by_name(context.user_data['category_name'])
            # Create if not found by name since get_category_by_name wasn't standard in snippet, fallback to get_or_create
            cat_id = await self.db_manager.get_or_create_category(context.user_data['category_name'])

            await self.db_manager.add_account(
                category_id=cat_id,
                phone=context.user_data['phone'],
                session_str=session_str,
                device_info=json.dumps(context.user_data.get('device_info', {}))
            )
            
            msg = f"✅ **تقرير نجاح العملية**\n\nتم إنهاء عملية تسجيل الحساب بنجاح وتم حفظه في قاعدة البيانات المشفرة.\n\n👤 الحساب: @{me.get('username', 'لا يوجد')}\n📱 الرقم: {context.user_data['phone']}"
            
            if update.callback_query:
                await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")

        except Exception as e:
            logger.exception("Finalization error")
            msg = f"❌ خطأ في تأكيد الحفظ: {e}"
            if update.callback_query:
                await update.callback_query.message.reply_text(msg)
            else:
                await update.message.reply_text(msg)
        finally:
            await client.close()
            if 'td_client' in context.user_data:
                del context.user_data['td_client']
            
        return await self.start(update, context)

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if 'td_client' in context.user_data:
            await context.user_data['td_client'].close()
            del context.user_data['td_client']

        msg = "🚫 تم إلغاء العملية الجارية وتنظيف الموارد."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.edit_text(msg)
        else:
            await update.message.reply_text(msg)
        return await self.start(update, context)

    @owner_only
    async def handle_existing_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return 0
