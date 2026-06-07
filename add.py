# -*- coding: utf-8 -*-
"""
بوت إدارة حسابات التليجرام - الملف الرئيسي
يستدعي الوحدات من مجلد add
"""

import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

from add.config import BOT_TOKEN, MAIN_MENU, ADD_ACCOUNT_CATEGORY, ADD_ACCOUNT_PHONE, ADD_ACCOUNT_PHONE_HANDLE_EXISTING, ADD_ACCOUNT_CODE, ADD_ACCOUNT_PASSWORD, DELETE_CATEGORY_SELECT, DELETE_ACCOUNT_SELECT, VIEW_CATEGORY_SELECT, VIEW_ACCOUNTS, CHECK_CATEGORY_SELECT, CHECK_ACCOUNT_SELECT, CHECK_ACCOUNT_DETAILS, CHECK_ACCOUNTS_IN_PROGRESS, STORAGE_CATEGORY_SELECT, STORAGE_ACCOUNT_SELECT
from add.database import DatabaseManager
from add.account_manager import AccountManager

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  
)
logger = logging.getLogger(__name__)

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء مدير قاعدة البيانات
    db_manager = DatabaseManager('accounts.db')
    
    # إنشاء مدير الحسابات
    account_manager = AccountManager(db_manager)
    
    # إنشاء التطبيق
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # إعداد معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', account_manager.start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.main_menu)],
            ADD_ACCOUNT_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_category),
                CommandHandler('cancel', account_manager.cancel_operation)
            ],
            ADD_ACCOUNT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_phone),
                CommandHandler('cancel', account_manager.cancel_operation)
            ],
            ADD_ACCOUNT_PHONE_HANDLE_EXISTING: [
                CallbackQueryHandler(account_manager.handle_existing_account)
            ],
            ADD_ACCOUNT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_code),
                CommandHandler('cancel', account_manager.cancel_operation)
            ],
            ADD_ACCOUNT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_password),
                CommandHandler('cancel', account_manager.cancel_operation)
            ],
            # يمكن إضافة باقي الحالات هنا عند الحاجة
        },
        fallbacks=[CommandHandler('cancel', account_manager.cancel_operation)]
    )
    
    app.add_handler(conv_handler)
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == '__main__':
    main()