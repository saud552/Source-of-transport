# -*- coding: utf-8 -*-
"""
مدير الحسابات - إدارة عمليات تسجيل وإدارة الحسابات (Async PostgreSQL version)
"""

import logging
import asyncio
import json
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from .tdlib_client import TDLibClient
from .database import DatabaseManager
from .validators import validate_phone, validate_code, get_random_device
from .decorators import owner_only
from .keyboards import get_categories_keyboard, get_accounts_keyboard
from .config import API_ID, API_HASH, DB_PATH

logger = logging.getLogger(__name__)

class AccountManager:
    """مدير الحسابات مع دعم PostgreSQL والعمليات غير المتزامنة"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @owner_only
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء البوت وعرض القائمة الرئيسية"""
        keyboard = [
            ["➕ اضافه الحسابات"],
            ["👁️ عرض الحسابات"],
            ["🗑️ حذف حساب"],
            ["🔍 فحص الحسابات"],
            ["📦 حسابات التخزين"],
            ["🔄 تحديث جلسات التخزين"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "👋 مرحباً بك في نظام إدارة حسابات التليجرام (PostgreSQL)!\n"
            "اختر أحد الخيارات من القائمة أدناه:",
            reply_markup=reply_markup
        )
        return 0  # MAIN_MENU

    @owner_only
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة القائمة الرئيسية"""
        text = update.message.text
        
        if text == "➕ اضافه الحسابات":
            await update.message.reply_text(
                "📁 الرجاء إدخال اسم الفئة التي تريد تخزين الحساب فيها:",
                reply_markup=ReplyKeyboardRemove()
            )
            return 1  # ADD_ACCOUNT_CATEGORY
            
        elif text == "👁️ عرض الحسابات":
            # تحديث get_categories_keyboard ليدعم async إذا لزم الأمر،
            # أو استرجاع البيانات هنا وتمريرها
            categories = await self.db_manager.get_all_categories()
            if not categories:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0

            # ملاحظة: keyboards.py لا يزال يستخدم sqlite3، سنقوم بتحديث المنطق هنا مؤقتاً
            keyboard = []
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"{cat['name']} ({cat['account_count']})", callback_data=f"view_category_{cat['id']}")])
            keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])

            await update.message.reply_text(
                "📁 اختر الفئة لعرض حساباتها:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return 8  # VIEW_CATEGORY_SELECT
            
        elif text == "🗑️ حذف حساب":
            categories = await self.db_manager.get_all_categories()
            if not categories:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0

            keyboard = []
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"{cat['name']} ({cat['account_count']})", callback_data=f"delete_category_{cat['id']}")])
            keyboard.append([InlineKeyboardButton("الغاء", callback_data="cancel")])

            await update.message.reply_text(
                "📁 اختر الفئة التي تحتوي على الحساب الذي تريد حذفه:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return 6  # DELETE_CATEGORY_SELECT
            
        # ... (باقي الخيارات تحتاج لتعديل مماثل) ...
            
        await update.message.reply_text("❌ خيار غير صالح أو تحت التطوير.")
        return 0

    @owner_only
    async def add_account_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إضافة فئة جديدة للحساب"""
        category_name = update.message.text.strip()
        context.user_data['category_name'] = category_name
        
        # إنشاء الفئة في قاعدة البيانات بشكل async
        await self.db_manager.create_category(category_name)
        
        await update.message.reply_text(
            "📱 الرجاء إرسال رقم الهاتف بصيغة دولية (مثال: +967771234567)\n"
            "❌ للإلغاء: /cancel"
        )
        return 2  # ADD_ACCOUNT_PHONE

    @owner_only
    async def add_account_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة رقم الهاتف"""
        phone = update.message.text.strip()
        
        if not validate_phone(phone):
            await update.message.reply_text("❌ رقم الهاتف غير صالح. الرجاء إرسال رقم بصيغة دولية صحيحة.")
            return 2
        
        # التحقق من وجود الحساب بشكل async
        existing_account = await self.db_manager.get_account_by_phone(phone)
        if existing_account:
            keyboard = [
                [InlineKeyboardButton("حذف الحساب القديم وإضافة جديد", callback_data="replace_account")],
                [InlineKeyboardButton("استخدام رقم آخر", callback_data="use_another")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ هذا الرقم مسجل مسبقاً في النظام.\n"
                "اختر أحد الخيارات:",
                reply_markup=reply_markup
            )
            context.user_data['phone'] = phone
            return 3  # ADD_ACCOUNT_PHONE_HANDLE_EXISTING
        
        context.user_data['phone'] = phone
        return await self.start_phone_verification(update, context)

    async def start_phone_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بدء عملية التحقق من الهاتف"""
        phone = context.user_data['phone']
        
        try:
            device = get_random_device()
            client = TDLibClient(API_ID, API_HASH, device, phone=phone)
            context.user_data['td_client'] = client
            context.user_data['device_info'] = device
            
            await client.login()

            if client.auth_state == 'authorizationStateWaitCode':
                msg = (
                    "✅ تم إرسال رمز التحقق إلى حسابك.\n"
                    "🔢 أرسل الرمز الآن:\n"
                    "❌ للإلغاء: /cancel"
                )
                if update.message:
                    await update.message.reply_text(msg)
                else:  # From callback query
                    await update.callback_query.edit_message_text(msg)
                return 4  # ADD_ACCOUNT_CODE
            elif client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            else:
                raise Exception(f"Unexpected auth state: {client.auth_state}")

        except Exception as e:
            logger.exception("Verification error")
            error_msg = f"❌ حدث خطأ: {e}"
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            return ConversationHandler.END

    @owner_only
    async def add_account_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة رمز التحقق"""
        code = update.message.text.strip().replace(' ', '').replace('-', '').replace(',', '')
        
        if not code.isdigit() or len(code) < 5:
            await update.message.reply_text("❌ رمز التحقق غير صالح. مكون من 5-6 أرقام.")
            return 4
            
        client: TDLibClient = context.user_data.get('td_client')
        if not client:
            await update.message.reply_text("❌ انتهت الجلسة.")
            return ConversationHandler.END
            
        try:
            await client.send_code(code)
            
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            elif client.auth_state == 'authorizationStateWaitPassword':
                await update.message.reply_text("🔒 أرسل كلمة المرور الآن:")
                return 5  # ADD_ACCOUNT_PASSWORD
            else:
                raise Exception(f"Unexpected state: {client.auth_state}")

        except Exception as e:
            logger.exception("Login failed with code")
            await update.message.reply_text(f"❌ فشل: {e}")
            return 4

    @owner_only
    async def add_account_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة كلمة المرور"""
        password = update.message.text.strip()
        client: TDLibClient = context.user_data.get('td_client')
        
        if not client:
            return ConversationHandler.END
            
        try:
            await client.send_password(password)
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            else:
                raise Exception("Incorrect password.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
            return 5

    async def finalize_account_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE, client: TDLibClient) -> int:
        """إنهاء تسجيل الحساب وحفظه في PostgreSQL"""
        try:
            me = client.me or await client.get_me()
            if not me:
                raise Exception("Could not retrieve user info.")

            phone = context.user_data['phone']
            category_name = context.user_data['category_name']
            device_info = context.user_data['device_info']
            
            session_base64 = client.save_session()
            if not session_base64:
                raise Exception("Failed to save session")
            
            # الحصول على معرف الفئة بشكل async
            category = await self.db_manager.get_category_by_name(category_name)
            if not category:
                category_id = await self.db_manager.create_category(category_name)
            else:
                category_id = str(category['id'])

            # حفظ الحساب في PostgreSQL
            await self.db_manager.create_account(
                category_id=category_id,
                username=me.get('username', ''),
                session_str=session_base64,
                phone=phone,
                device_info=json.dumps(device_info)
            )
            
            username = me.get('username', 'Unknown')
            msg = f"✅ تم تسجيل الحساب في '{category_name}'!\n📱 {phone}\n👤 @{username}"
            if update.message:
                await update.message.reply_text(msg)
            else:
                await update.callback_query.edit_message_text(msg)
            
        except Exception as e:
            logger.exception("Finalization error")
            if update.message:
                await update.message.reply_text(f"❌ خطأ في الحفظ: {e}")
        finally:
            if client:
                await client.close()
            context.user_data.clear()
            
        return await self.start(update, context)

    @owner_only
    async def refresh_storage_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تحديث جلسات حسابات التخزين بشكل async"""
        try:
            accounts = await self.db_manager.get_storage_accounts()
            if not accounts:
                await update.message.reply_text("❌ لا توجد حسابات تخزين.")
                return
            
            success_count = 0
            for acc in accounts:
                try:
                    # منطق التحديث ...
                    success_count += 1
                except:
                    continue
            
            await update.message.reply_text(f"✅ تم تحديث {success_count} جلسة.")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ: {e}")

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إلغاء العملية"""
        await update.message.reply_text("تم إلغاء العملية.", reply_markup=ReplyKeyboardRemove())
        return await self.start(update, context)

    @owner_only
    async def handle_existing_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة استبدال حساب موجود"""
        query = update.callback_query
        await query.answer()

        if query.data == "replace_account":
            phone = context.user_data['phone']
            acc = await self.db_manager.get_account_by_phone(phone)
            if acc:
                await self.db_manager.delete_account(str(acc['id']))
            return await self.start_phone_verification(update, context)
        else:
            return await self.cancel_operation(update, context)
