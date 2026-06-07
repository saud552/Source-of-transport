# -*- coding: utf-8 -*-
"""
بوت إدارة حسابات التليجرام - الملف الرئيسي (Async version)
"""

import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

from add.config import BOT_TOKEN, MAIN_MENU, ADD_ACCOUNT_CATEGORY, ADD_ACCOUNT_PHONE, ADD_ACCOUNT_PHONE_HANDLE_EXISTING, ADD_ACCOUNT_CODE, ADD_ACCOUNT_PASSWORD
from add.database import DatabaseManager
from add.account_manager import AccountManager

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_bot():
    """تشغيل البوت بشكل غير متزامن"""
    # إنشاء ومدير قاعدة البيانات
    db_manager = DatabaseManager()
    await db_manager.connect()

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
        },
        fallbacks=[CommandHandler('cancel', account_manager.cancel_operation)]
    )

    app.add_handler(conv_handler)

    logger.info("Starting Account Registration Bot...")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        # الانتظار حتى يتم إيقاف البوت
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Stopping bot...")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            await db_manager.close()

def main():
    """الدالة الرئيسية للتوافق"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
