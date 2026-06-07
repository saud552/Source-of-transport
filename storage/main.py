#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
بوت التخزين (Async PostgreSQL version)
"""

import os
import sys
import logging
import asyncio
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

from storage.config import BOT_TOKEN
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

    # حالات المحادثة
    # ... logic (Simplified for Step 1) ...
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', handlers.start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.main_menu)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.storage_hidden_group)],
            2: [CallbackQueryHandler(handlers.storage_hidden_confirm)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.storage_hidden_category_name)],
            4: [CallbackQueryHandler(handlers.storage_hidden_accounts)],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.storage_hidden_last_seen)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.storage_hidden_months)],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel_operation)]
    )

    app.add_handler(conv_handler)

    logger.info("Starting Storage Bot (PostgreSQL)...")
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
