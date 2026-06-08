# -*- coding: utf-8 -*-
"""
بوت إدارة حسابات التليجرام - الملف الرئيسي (Async version)
"""

import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

from add.config import (
    BOT_TOKEN, MAIN_MENU, ADD_ACCOUNT_CATEGORY, ADD_ACCOUNT_PHONE,
    ADD_ACCOUNT_PHONE_HANDLE_EXISTING, ADD_ACCOUNT_CODE, ADD_ACCOUNT_PASSWORD,
    CUSTOMIZE_ACCOUNT_MENU, CUSTOMIZE_ACCOUNT_GENDER,
    CUSTOMIZE_ACCOUNT_PHOTO, CUSTOMIZE_ACCOUNT_NAME,
    CUSTOMIZE_ACCOUNT_BIO, CUSTOMIZE_ACCOUNT_USERNAME
)
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
    db_manager = DatabaseManager()
    await db_manager.connect()

    account_manager = AccountManager(db_manager)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', account_manager.start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(account_manager.main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.main_menu)
            ],
            ADD_ACCOUNT_CATEGORY: [
                CallbackQueryHandler(account_manager.add_account_category),
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_category),
            ],
            ADD_ACCOUNT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_phone),
            ],
            ADD_ACCOUNT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_code),
            ],
            ADD_ACCOUNT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.add_account_password),
            ],
            CUSTOMIZE_ACCOUNT_MENU: [
                CallbackQueryHandler(account_manager.customize_account_menu)
            ],
            CUSTOMIZE_ACCOUNT_GENDER: [
                CallbackQueryHandler(account_manager.customize_gender)
            ],
            CUSTOMIZE_ACCOUNT_PHOTO: [
                CallbackQueryHandler(account_manager.customize_photo),
                MessageHandler(filters.PHOTO, account_manager.customize_photo)
            ],
            CUSTOMIZE_ACCOUNT_NAME: [
                CallbackQueryHandler(account_manager.customize_name),
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.customize_name)
            ],
            CUSTOMIZE_ACCOUNT_BIO: [
                CallbackQueryHandler(account_manager.customize_bio),
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.customize_bio)
            ],
            CUSTOMIZE_ACCOUNT_USERNAME: [
                CallbackQueryHandler(account_manager.customize_username),
                MessageHandler(filters.TEXT & ~filters.COMMAND, account_manager.customize_username)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', account_manager.cancel_operation),
            MessageHandler(filters.Regex('^الغاء$'), account_manager.cancel_operation),
            CallbackQueryHandler(account_manager.cancel_operation, pattern="^cancel$")
        ]
    )

    app.add_handler(conv_handler)
    logger.info("Starting Account Registration Bot...")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

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
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
