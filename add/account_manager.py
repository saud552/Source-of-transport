# -*- coding: utf-8 -*-
"""
مدير الحسابات (Async PostgreSQL + Encryption)
"""

import logging
import asyncio
import json
import base64
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from .tdlib_client import TDLibClient
from .database import DatabaseManager
from .encryption import EncryptionManager
from .validators import validate_phone, validate_code, get_random_device
from .decorators import owner_only
from .config import API_ID, API_HASH, DB_PATH
from shared_config import PASSPHRASE, SALT

logger = logging.getLogger(__name__)

class AccountManager:
    """إدارة الحسابات مع تشفير الجلسات وقاعدة بيانات غير متزامنة"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.encryption = EncryptionManager(PASSPHRASE, SALT)

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyboard = [["➕ اضافه الحسابات"], ["👁️ عرض الحسابات"], ["🗑️ حذف حساب"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("👋 نظام إدارة الحسابات الآمن (PostgreSQL + AES-256)", reply_markup=reply_markup)
        return 0

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        if text == "➕ اضافه الحسابات":
            await update.message.reply_text("📁 أدخل اسم الفئة:", reply_markup=ReplyKeyboardRemove())
            return 1
        return 0

    @owner_only
    async def add_account_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['category_name'] = update.message.text.strip()
        await self.db_manager.create_category(context.user_data['category_name'])
        await update.message.reply_text("📱 أرسل رقم الهاتف (صيغة دولية):")
        return 2

    @owner_only
    async def add_account_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        phone = update.message.text.strip()
        if not validate_phone(phone):
            await update.message.reply_text("❌ رقم غير صالح.")
            return 2
        
        context.user_data['phone'] = phone
        return await self.start_phone_verification(update, context)

    async def start_phone_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        phone = context.user_data['phone']
        device = get_random_device()

        # استخدام Context Manager لضمان تنظيف المجلدات حتى لو فشل التحقق
        client = TDLibClient(API_ID, API_HASH, device, phone=phone)
        context.user_data['td_client'] = client
        
        try:
            await client.login()
            if client.auth_state == 'authorizationStateWaitCode':
                await update.message.reply_text("✅ تم إرسال الرمز:")
                return 4
            elif client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
        except Exception as e:
            await client.close()
            await update.message.reply_text(f"❌ خطأ: {e}")
            return ConversationHandler.END
        return 4

    @owner_only
    async def add_account_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        client: TDLibClient = context.user_data.get('td_client')
        code = update.message.text.strip()

        try:
            await client.send_code(code)
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            elif client.auth_state == 'authorizationStateWaitPassword':
                await update.message.reply_text("🔑 أرسل كلمة المرور:")
                return 5
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ بالكود: {e}")
        return 4

    @owner_only
    async def add_account_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        client: TDLibClient = context.user_data.get('td_client')
        password = update.message.text.strip()
        
        try:
            await client.send_password(password)
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ بكلمة المرور: {e}")
        return 5

    async def finalize_account_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE, client: TDLibClient) -> int:
        """تشفير وحفظ الحساب مع تنظيف الموارد"""
        try:
            me = await client.get_me()
            # 1. الحصول على ZIP كـ bytes
            raw_zip = client.save_session_bytes()
            if not raw_zip:
                raise Exception("فشل ضغط ملفات الجلسة")
            
            # 2. التشفير باستخدام AES-256
            encrypted_bytes = self.encryption.encrypt(raw_zip)
            
            # 3. التحويل لـ Base64 للحفظ في DB
            session_str = base64.b64encode(encrypted_bytes).decode('utf-8')

            category = await self.db_manager.get_category_by_name(context.user_data['category_name'])

            await self.db_manager.create_account(
                category_id=str(category['id']),
                username=me.get('username', ''),
                session_str=session_str,
                phone=context.user_data['phone'],
                device_info=json.dumps(context.user_data.get('device_info', {}))
            )
            
            await update.message.reply_text(f"✅ تم التسجيل والتشفير بنجاح: @{me.get('username')}")
            
        except Exception as e:
            logger.exception("Finalization error")
            await update.message.reply_text(f"❌ خطأ: {e}")
        finally:
            await client.close() # purging temp directory
            if 'td_client' in context.user_data:
                del context.user_data['td_client']
            
        return await self.start(update, context)

    @owner_only
    async def handle_existing_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return 0

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if 'td_client' in context.user_data:
            await context.user_data['td_client'].close()
        await update.message.reply_text("🚫 تم الإلغاء وتنظيف الموارد.")
        return await self.start(update, context)
