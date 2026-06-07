# -*- coding: utf-8 -*-
import os
import sys
import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transf.config import BOT_TOKEN, DB_PATH
from transf.database import TransferDatabaseManager
from transf.handlers import TransferHandlers
from transf.config import (
    MAIN_MENU, SELECT_SOURCE_GROUP, SELECT_ACCOUNT_CATEGORY, SELECT_ACCOUNTS,
    ENTER_TARGET_GROUP, CONFIRM_TRANSFER, TRANSFER_IN_PROGRESS,
    VIEW_TRANSFER_HISTORY, VIEW_AVAILABLE_GROUPS
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class TransferBot:
    def __init__(self):
        self.db_manager = TransferDatabaseManager()
        self.handlers = TransferHandlers(self.db_manager)
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.handlers.start)],
            states={
                MAIN_MENU: [CallbackQueryHandler(self.handlers.main_menu)],
                SELECT_SOURCE_GROUP: [CallbackQueryHandler(self.handlers.select_source_group)],
                SELECT_ACCOUNT_CATEGORY: [CallbackQueryHandler(self.handlers.select_account_category)],
                SELECT_ACCOUNTS: [CallbackQueryHandler(self.handlers.select_accounts)],
                ENTER_TARGET_GROUP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.enter_target_group),
                    CommandHandler('cancel', self.handlers.cancel_operation),
                ],
                CONFIRM_TRANSFER: [CallbackQueryHandler(self.handlers.confirm_transfer)],
                TRANSFER_IN_PROGRESS: [CallbackQueryHandler(self.handlers.handle_transfer_control, pattern=r"^(pause|resume|cancel)_")],
                VIEW_TRANSFER_HISTORY: [CallbackQueryHandler(self.handlers.view_transfer_history)],
                VIEW_AVAILABLE_GROUPS: [CallbackQueryHandler(self.handlers.view_available_groups)],
            },
            fallbacks=[CommandHandler('cancel', self.handlers.cancel_operation)]
        )
        self.app.add_handler(conv_handler)

    async def run_async(self):
        logger.info("🚀 Starting Transfer Bot database...")
        await self.db_manager.connect()
        logger.info("🚀 Starting Transfer Bot polling...")
        async with self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            while True:
                await asyncio.sleep(3600)

def main():
    try:
        bot = TransferBot()
        asyncio.run(bot.run_async())
    except Exception as e:
        logger.critical(f"❌ Critical error in Transfer Bot: {e}", exc_info=True)

if __name__ == '__main__':
    main()
