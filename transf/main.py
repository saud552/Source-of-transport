# -*- coding: utf-8 -*-
import sys
import os
import asyncio
import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transf.config import (
    BOT_TOKEN, MAIN_MENU, DIRECT_INPUT_LINKS, DIRECT_TARGET_LINK,
    DIRECT_SELECT_ACC_CAT, DIRECT_CONFIRM, TRANSFER_IN_PROGRESS,
    VIEW_STORAGE_CATEGORIES, VIEW_STORAGE_GROUPS, STORED_TARGET_LINK,
    STORED_SELECT_ACC_CAT, STORED_CONFIRM, SETTINGS_MENU, SETTINGS_DELAY,
    SETTINGS_BATCH_SIZE, SETTINGS_LAST_SEEN_FILTER
)
from transf.database import TransferDatabaseManager
from transf.handlers import TransferHandlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_transfer_bot():
    db_manager = TransferDatabaseManager()
    await db_manager.connect()

    handlers = TransferHandlers(db_manager)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', handlers.start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(handlers.main_menu)
            ],
            DIRECT_INPUT_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.direct_input_links)
            ],
            DIRECT_TARGET_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.direct_target_link)
            ],
            DIRECT_SELECT_ACC_CAT: [
                CallbackQueryHandler(handlers.direct_select_acc_cat)
            ],
            DIRECT_CONFIRM: [
                CallbackQueryHandler(handlers.direct_confirm)
            ],
            TRANSFER_IN_PROGRESS: [
                CallbackQueryHandler(handlers.transfer_control)
            ],
            VIEW_STORAGE_CATEGORIES: [
                CallbackQueryHandler(handlers.view_storage_categories)
            ],
            VIEW_STORAGE_GROUPS: [
                CallbackQueryHandler(handlers.view_storage_groups)
            ],
            7: [ # view_storage_groups inner actions
                CallbackQueryHandler(handlers.handle_stored_actions)
            ],
            STORED_TARGET_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.stored_target_link)
            ],
            STORED_SELECT_ACC_CAT: [
                CallbackQueryHandler(handlers.stored_select_acc_cat)
            ],
            STORED_CONFIRM: [
                CallbackQueryHandler(handlers.stored_confirm)
            ],
            SETTINGS_MENU: [
                CallbackQueryHandler(handlers.settings_menu)
            ],
            SETTINGS_DELAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.settings_delay_input)
            ],
            SETTINGS_BATCH_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.settings_batch_input)
            ],
            SETTINGS_LAST_SEEN_FILTER: [
                CallbackQueryHandler(handlers.settings_ls_filter)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', handlers.cancel_operation),
            MessageHandler(filters.Regex('^الغاء$'), handlers.cancel_operation),
            CallbackQueryHandler(handlers.cancel_operation, pattern="^cancel$")
        ]
    )

    app.add_handler(conv_handler)
    logger.info("Starting Transfer Bot...")

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            await db_manager.close()

def main():
    try:
        asyncio.run(run_transfer_bot())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
