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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# استيراد الوحدات الجديدة
from transf.config import BOT_TOKEN, DB_PATH
from transf.database import TransferDatabaseManager
from transf.handlers import TransferHandlers

# ========== إعدادات التهيئة ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  
)
logger = logging.getLogger(__name__)

# === حالات المحادثة ===
from transf.config import (
    MAIN_MENU, SELECT_SOURCE_GROUP, SELECT_ACCOUNT_CATEGORY, SELECT_ACCOUNTS,
    ENTER_TARGET_GROUP, CONFIRM_TRANSFER, TRANSFER_IN_PROGRESS,
    VIEW_TRANSFER_HISTORY, VIEW_AVAILABLE_GROUPS
)

class TransferBot:
    """البوت الرئيسي لنقل الأعضاء"""
    
    def __init__(self):
        # تهيئة المديرين
        self.db_manager = TransferDatabaseManager(DB_PATH)
        self.handlers = TransferHandlers(self.db_manager)
        
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
                    CallbackQueryHandler(self.handlers.main_menu),
                ],
                SELECT_SOURCE_GROUP: [
                    CallbackQueryHandler(self.handlers.select_source_group),
                ],
                SELECT_ACCOUNT_CATEGORY: [
                    CallbackQueryHandler(self.handlers.select_account_category),
                ],
                SELECT_ACCOUNTS: [
                    CallbackQueryHandler(self.handlers.select_accounts),
                ],
                ENTER_TARGET_GROUP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.enter_target_group),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                CONFIRM_TRANSFER: [
                    CallbackQueryHandler(self.handlers.confirm_transfer),
                ],
                TRANSFER_IN_PROGRESS: [
                    CallbackQueryHandler(self.handlers.handle_transfer_control, pattern=r"^(pause|resume|cancel)_"),
                ],
                VIEW_TRANSFER_HISTORY: [
                    CallbackQueryHandler(self.handlers.view_transfer_history),
                ],
                VIEW_AVAILABLE_GROUPS: [
                    CallbackQueryHandler(self.handlers.view_available_groups),
                ],
            },
            fallbacks=[CommandHandler('cancel', self.handlers.cancel_operation)]
        )
        
        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler('status', self.handlers.cancel_operation))

    def run(self):
        """تشغيل البوت"""
        logger.info("🚀 بدء تشغيل بوت النقل...")
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
        
        # إنشاء وتشغيل البوت
        bot = TransferBot()
        bot.run()
        
    except Exception as e:
        logger.critical(f"❌ خطأ حرج في تشغيل البوت: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()