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

# إضافة مسار المجلد الحالي
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.config import BOT_TOKEN, MAIN_MENU, HIDDEN_INPUT_LINKS, HIDDEN_SELECT_ACC_CAT, HIDDEN_SELECT_STORAGE_CAT, HIDDEN_SELECT_MECHANISM, STORAGE_IN_PROGRESS, VISIBLE_INPUT_LINKS, VISIBLE_SELECT_ACC_CAT, VISIBLE_SELECT_STORAGE_CAT, VISIBLE_CONFIRM, VIEW_STORAGE_CATEGORIES, VIEW_STORAGE_GROUPS, SETTINGS_MENU, SETTINGS_MONTHLY, SETTINGS_COUNT, SETTINGS_LAST_SEEN
from storage.database import StorageDatabaseManager
from storage.handlers import StorageHandlers
from storage.group_manager import GroupManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_storage_bot():
    db_manager = StorageDatabaseManager()
    await db_manager.connect()

    group_manager = GroupManager(db_manager)
    handlers = StorageHandlers(db_manager, group_manager)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', handlers.start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(handlers.main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.main_menu)
            ],
            HIDDEN_INPUT_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.hidden_input_links)
            ],
            HIDDEN_SELECT_ACC_CAT: [
                CallbackQueryHandler(handlers.hidden_select_acc_cat)
            ],
            HIDDEN_SELECT_STORAGE_CAT: [
                CallbackQueryHandler(handlers.hidden_select_storage_cat),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.hidden_select_storage_cat)
            ],
            HIDDEN_SELECT_MECHANISM: [
                CallbackQueryHandler(handlers.hidden_select_mechanism)
            ],
            STORAGE_IN_PROGRESS: [
                CallbackQueryHandler(handlers.handle_storage_control)
            ],
            VISIBLE_INPUT_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.visible_input_links)
            ],
            VISIBLE_SELECT_ACC_CAT: [
                CallbackQueryHandler(handlers.visible_select_acc_cat)
            ],
            VISIBLE_SELECT_STORAGE_CAT: [
                CallbackQueryHandler(handlers.visible_select_storage_cat),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.visible_select_storage_cat)
            ],
            VISIBLE_CONFIRM: [
                CallbackQueryHandler(handlers.visible_confirm)
            ],
            VIEW_STORAGE_CATEGORIES: [
                CallbackQueryHandler(handlers.view_storage_categories)
            ],
            VIEW_STORAGE_GROUPS: [
                CallbackQueryHandler(handlers.view_storage_groups)
            ],
            SETTINGS_MENU: [
                CallbackQueryHandler(handlers.storage_settings_menu)
            ],
            SETTINGS_MONTHLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.settings_monthly_input)
            ],
            SETTINGS_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.settings_count_input)
            ],
            SETTINGS_LAST_SEEN: [
                CallbackQueryHandler(handlers.settings_last_seen_select)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', handlers.cancel_operation),
            MessageHandler(filters.Regex('^الغاء$'), handlers.cancel_operation),
            CallbackQueryHandler(handlers.cancel_operation, pattern="^cancel$")
        ]
    )

    app.add_handler(conv_handler)

    logger.info("Starting Storage Bot...")
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
        asyncio.run(run_storage_bot())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
