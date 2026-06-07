#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# إضافة مسار المجلد الحالي إلى Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# استيراد الوحدات الجديدة
from storage.config import BOT_TOKEN, DB_PATH, ACCOUNTS_DB_PATH
from storage.database import StorageDatabaseManager
from storage.handlers import StorageHandlers
from storage.group_manager import GroupManager
from storage.export import DataExporter
from storage.validation import DataValidator
from storage.encryption import EncryptionManager
from storage.utils import StorageUtils

# ========== إعدادات التهيئة ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  
)
logger = logging.getLogger(__name__)

# === حالات المحادثة ===
(
    MAIN_MENU,
    STORAGE_HIDDEN_GROUP,
    STORAGE_HIDDEN_CONFIRM,
    STORAGE_HIDDEN_CATEGORY_NAME,
    STORAGE_HIDDEN_ACCOUNTS,
    STORAGE_HIDDEN_LAST_SEEN,
    STORAGE_HIDDEN_MONTHS,
    STORAGE_VISIBLE_GROUP,
    STORAGE_VISIBLE_CONFIRM,
    STORAGE_VISIBLE_CATEGORY_NAME,
    STORAGE_VISIBLE_ACCOUNTS,
    VIEW_STORAGE_CATEGORIES,
    VIEW_STORAGE_GROUPS,
    STORAGE_IN_PROGRESS,
    EXPORT_DATA
) = range(15)

class StorageBot:
    """البوت الرئيسي لتخزين أعضاء التليجرام"""
    
    def __init__(self):
        # تهيئة المديرين
        self.db_manager = StorageDatabaseManager(DB_PATH)
        self.group_manager = GroupManager(self.db_manager)
        self.handlers = StorageHandlers(self.db_manager, self.group_manager)
        self.validator = DataValidator()
        self.encryption_manager = EncryptionManager()
        self.utils = StorageUtils()
        
        # إعداد التطبيق
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """إعداد معالجات البوت"""
        # إعداد محادثة البوت
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.handlers.start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.main_menu),
                    CommandHandler('status', self.handlers.status_command),
                ],
                STORAGE_HIDDEN_GROUP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_hidden_group),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_HIDDEN_CONFIRM: [
                    CallbackQueryHandler(self.handlers.storage_hidden_confirm),
                ],
                STORAGE_HIDDEN_CATEGORY_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_hidden_category_name),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_HIDDEN_ACCOUNTS: [
                    CallbackQueryHandler(self.handlers.storage_hidden_accounts),
                ],
                STORAGE_HIDDEN_LAST_SEEN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_hidden_last_seen),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_HIDDEN_MONTHS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_hidden_months),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_VISIBLE_GROUP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_visible_group),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_VISIBLE_CONFIRM: [
                    CallbackQueryHandler(self.handlers.storage_visible_confirm),
                ],
                STORAGE_VISIBLE_CATEGORY_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.storage_visible_category_name),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                STORAGE_VISIBLE_ACCOUNTS: [
                    CallbackQueryHandler(self.handlers.storage_visible_accounts),
                ],
                STORAGE_IN_PROGRESS: [
                    CallbackQueryHandler(self.handlers.handle_storage_control, pattern=r"^(pause|resume|cancel)_"),
                ],
                VIEW_STORAGE_CATEGORIES: [
                    CallbackQueryHandler(self.handlers.view_storage_categories),
                ],
                VIEW_STORAGE_GROUPS: [
                    CallbackQueryHandler(self.handlers.view_storage_groups),
                ],
                EXPORT_DATA: [
                    CallbackQueryHandler(self.handlers.export_data),
                    CallbackQueryHandler(self.handlers.export_group_data, pattern=r"^export_group_|prev_|next_"),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.handlers.cancel_operation)]
        )
        
        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler('status', self.handlers.status_command))

    def run(self):
        """تشغيل البوت"""
        logger.info("🚀 بدء تشغيل بوت التخزين...")
        try:
            self.app.run_polling()
        except KeyboardInterrupt:
            logger.info("⏹️ تم إيقاف البوت بواسطة المستخدم")
        except Exception as e:
            logger.error(f"❌ خطأ في تشغيل البوت: {str(e)}", exc_info=True)
        finally:
            logger.info("🔚 انتهاء تشغيل البوت")

def main():
    """الدالة الرئيسية"""
    try:
        # التحقق من وجود الملفات المطلوبة
        if not os.path.exists(DB_PATH):
            logger.warning(f"تحذير: ملف قاعدة البيانات {DB_PATH} غير موجود، سيتم إنشاؤه تلقائياً")
        
        if not os.path.exists(ACCOUNTS_DB_PATH):
            logger.warning(f"تحذير: ملف قاعدة بيانات الحسابات {ACCOUNTS_DB_PATH} غير موجود")
        
        # إنشاء وتشغيل البوت
        bot = StorageBot()
        bot.run()
        
    except Exception as e:
        logger.critical(f"❌ خطأ حرج في تشغيل البوت: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()