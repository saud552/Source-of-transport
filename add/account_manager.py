# -*- coding: utf-8 -*-
"""
مدير الحسابات - إدارة عمليات تسجيل وإدارة الحسابات
"""

import logging
import asyncio
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
    """مدير الحسابات"""
    
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
            "👋 مرحباً بك في نظام إدارة حسابات التليجرام!\n"
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
            keyboard = get_categories_keyboard(action="view", db_path=DB_PATH)
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0
            await update.message.reply_text(
                "📁 اختر الفئة لعرض حساباتها:",
                reply_markup=keyboard
            )
            return 8  # VIEW_CATEGORY_SELECT
            
        elif text == "🗑️ حذف حساب":
            keyboard = get_categories_keyboard(action="delete", db_path=DB_PATH)
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0
            await update.message.reply_text(
                "📁 اختر الفئة التي تحتوي على الحساب الذي تريد حذفه:",
                reply_markup=keyboard
            )
            return 6  # DELETE_CATEGORY_SELECT
            
        elif text == "🔍 فحص الحسابات":
            keyboard = get_categories_keyboard(action="check", db_path=DB_PATH)
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0
            await update.message.reply_text(
                "📁 اختر الفئة لفحص حساباتها:",
                reply_markup=keyboard
            )
            return 10  # CHECK_CATEGORY_SELECT
            
        elif text == "📦 حسابات التخزين":
            keyboard = get_categories_keyboard(action="storage", db_path=DB_PATH)
            if not keyboard:
                await update.message.reply_text("❌ لا توجد فئات متاحة.")
                return 0
            await update.message.reply_text(
                "📁 اختر الفئة التي تحتوي على الحساب المراد نقله للتخزين:",
                reply_markup=keyboard
            )
            return 14  # STORAGE_CATEGORY_SELECT
            
        elif text == "🔄 تحديث جلسات التخزين":
            await update.message.reply_text("جاري تحديث جلسات حسابات التخزين...")
            await self.refresh_storage_sessions(update, context)
            return 0
            
        await update.message.reply_text("❌ خيار غير صالح. الرجاء الاختيار من القائمة.")
        return 0

    @owner_only
    async def add_account_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إضافة فئة جديدة للحساب"""
        category_name = update.message.text.strip()
        context.user_data['category_name'] = category_name
        
        # إنشاء الفئة في قاعدة البيانات
        self.db_manager.create_category(category_name)
        
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
        
        # التحقق من وجود الحساب
        existing_account = self.db_manager.get_account_by_phone(phone)
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
                if isinstance(update, Update):
                    await update.message.reply_text(msg)
                else:  # From callback query
                    await update.edit_message_text(msg)
                return 4  # ADD_ACCOUNT_CODE
            elif client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            else:
                raise Exception(f"Unexpected auth state after login attempt: {client.auth_state}")

        except Exception as e:
            logger.exception("Verification error")
            error_msg = f"❌ حدث خطأ: {e}"
            if isinstance(update, Update):
                await update.message.reply_text(error_msg)
            else:
                await update.edit_message_text(error_msg)
            return ConversationHandler.END

    @owner_only
    async def add_account_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة رمز التحقق"""
        code = update.message.text.strip().replace(' ', '').replace('-', '').replace(',', '')
        
        if not code.isdigit() or len(code) < 5:
            await update.message.reply_text("❌ رمز التحقق غير صالح. الرجاء إرسال رمز مكون من 5-6 أرقام.")
            return 4
            
        client: TDLibClient = context.user_data.get('td_client')
        if not client:
            await update.message.reply_text("❌ انتهت جلسة التسجيل. الرجاء البدء من جديد.")
            return ConversationHandler.END
            
        try:
            await client.send_code(code)
            
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            elif client.auth_state == 'authorizationStateWaitPassword':
                await update.message.reply_text(
                    "🔒 هذا الحساب محمي بكلمة مرور.\n"
                    "🔑 أرسل كلمة المرور الآن:"
                )
                return 5  # ADD_ACCOUNT_PASSWORD
            else:
                raise Exception(f"Unexpected state after sending code: {client.auth_state}")

        except Exception as e:
            logger.exception("فشل تسجيل الدخول بالكود")
            error_msg = f"❌ فشل تسجيل الدخول: {e}"
            if "PHONE_CODE_INVALID" in str(e):
                error_msg = "❌ رمز التحقق غير صحيح."
            await update.message.reply_text(error_msg)
            return 4

    @owner_only
    async def add_account_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """معالجة كلمة المرور"""
        password = update.message.text.strip()
        client: TDLibClient = context.user_data.get('td_client')
        
        if not client:
            await update.message.reply_text("❌ انتهت جلسة التسجيل. الرجاء البدء من جديد.")
            return ConversationHandler.END
            
        try:
            await client.send_password(password)
            if client.auth_state == 'authorizationStateReady':
                return await self.finalize_account_registration(update, context, client)
            else:
                raise Exception("Password was incorrect or another error occurred.")
                
        except Exception as e:
            logger.exception("فشل تسجيل الدخول بكلمة المرور")
            await update.message.reply_text(f"❌ فشل تسجيل الدخول: {e}")
            return 5

    async def finalize_account_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE, client: TDLibClient) -> int:
        """إنهاء تسجيل الحساب وحفظه في قاعدة البيانات"""
        try:
            me = client.me or await client.get_me()
            if not me:
                raise Exception("Could not retrieve user info after login.")

            phone = context.user_data['phone']
            category_name = context.user_data['category_name']
            device_info = context.user_data['device_info']
            
            session_base64 = client.save_session()
            if not session_base64:
                raise Exception("فشل في حفظ الجلسة")
            
            # اختبار الجلسة المحفوظة
            test_client = None
            try:
                logger.info("Testing saved session...")
                test_client = await TDLibClient.load_session(session_base64, API_ID, API_HASH, device_info)
                if not test_client.me or test_client.me['id'] != me['id']:
                    raise Exception("Session test failed: user mismatch.")
                logger.info("Session test successful.")
            finally:
                if test_client:
                    await test_client.close()
            
            # الحصول على معرف الفئة
            category = self.db_manager.get_category_by_name(category_name)
            if not category:
                category_id = self.db_manager.create_category(category_name)
            else:
                category_id = category['id']

            # حفظ الحساب في قاعدة البيانات
            self.db_manager.create_account(
                category_id=category_id,
                username=me.get('username', ''),
                session_str=session_base64,
                phone=phone,
                device_info=str(device_info)
            )
            
            username = me.get('username', 'غير معروف')
            await update.message.reply_text(
                f"✅ تم تسجيل الحساب بنجاح في فئة '{category_name}'!\n\n"
                f"📱 الهاتف: {phone}\n"
                f"👤 المستخدم: @{username}"
            )
            
        except Exception as e:
            logger.exception("Finalization error")
            await update.message.reply_text(f"❌ حدث خطأ أثناء حفظ الحساب: {e}")
        finally:
            if client:
                await client.close()
            context.user_data.clear()
            
        # العودة للقائمة الرئيسية
        keyboard = [
            ["➕ اضافه الحسابات"], ["👁️ عرض الحسابات"],
            ["🗑️ حذف حساب"], ["🔍 فحص الحسابات"],
            ["📦 حسابات التخزين"], ["🔄 تحديث جلسات التخزين"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("اختر خيارًا:", reply_markup=reply_markup)
        return 0  # MAIN_MENU

    @owner_only
    async def refresh_storage_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تحديث جلسات حسابات التخزين"""
        try:
            # الحصول على فئة التخزين
            storage_category = self.db_manager.get_category_by_name("حسابات التخزين")
            if not storage_category:
                await update.message.reply_text("❌ فئة التخزين غير موجودة.")
                return
            
            # جلب جميع حسابات التخزين
            accounts = self.db_manager.get_accounts_by_category(storage_category['id'])
            
            if not accounts:
                await update.message.reply_text("❌ لا توجد حسابات في فئة التخزين.")
                return
            
            success_count = 0
            failed_count = 0
            need_verification = []
            
            for account in accounts:
                account_id = account['id']
                phone = account['phone']
                session_str = account['session_str']
                device_info_str = account['device_info']
                
                client = None
                try:
                    # تحليل معلومات الجهاز
                    import json
                    device_info = json.loads(device_info_str) if device_info_str else get_random_device()
                    
                    # تحميل الجلسة
                    client = await TDLibClient.load_session(session_str, API_ID, API_HASH, device_info)
                    
                    # اختبار الجلسة
                    me = await client.get_me()
                    if me:
                        new_session = client.save_session()
                        self.db_manager.update_account_session(account_id, new_session)
                        success_count += 1
                        logger.info(f"✅ تم تحديث جلسة الحساب: {phone}")
                    else:
                        need_verification.append(phone)
                        logger.warning(f"⚠️ الحساب {phone} يحتاج إلى إعادة تسجيل الدخول")
                
                except Exception as e:
                    logger.exception(f"❌ فشل تحديث جلسة الحساب {phone}: {str(e)}")
                    failed_count += 1
                
                finally:
                    if client:
                        try:
                            await client.close()
                        except:
                            pass
            
            # إعداد رسالة النتيجة
            message = f"✅ تم تحديث {success_count} حساب بنجاح\n"
            message += f"❌ فشل تحديث {failed_count} حساب\n"
            
            if need_verification:
                message += "\n⚠️ الحسابات التالية تحتاج إلى إعادة تسجيل الدخول:\n"
                message += "\n".join([f"- {phone}" for phone in need_verification])
                message += "\n\nالرجاء استخدام أمر /add_account لإضافتها مرة أخرى"
            
            await update.message.reply_text(message)
        
        except Exception as e:
            logger.exception("خطأ في تحديث الجلسات")
            await update.message.reply_text(f"❌ حدث خطأ أثناء تحديث الجلسات: {e}")

    @owner_only
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """إلغاء العملية الحالية"""
        await update.message.reply_text(
            "تم إلغاء العملية.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await self.start(update, context)