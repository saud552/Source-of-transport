# -*- coding: utf-8 -*-
"""
مدير المجموعات - إدارة عمليات تخزين الأعضاء (Async PostgreSQL version)
"""

import asyncio
import logging
import time
import uuid
import re
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from .tdlib_client import StorageTDLibClient
from .database import StorageDatabaseManager
from .decorators import owner_only
from .config import API_ID, API_HASH, ACCOUNTS_DB_PATH

logger = logging.getLogger(__name__)

class GroupManager:
    """مدير المجموعات لتخزين الأعضاء باستخدام PostgreSQL مع حماية Flood Wait"""
    
    def __init__(self, db_manager: StorageDatabaseManager):
        self.db_manager = db_manager
        self.active_tasks = {}
        self.pause_events = {}
        self.cancel_events = {}
        self.semaphore = asyncio.Semaphore(3)

    async def get_group_info(self, group_input: str) -> Optional[Dict[str, Any]]:
        # Mock for Step 2
        return {
            'id': -100123456789,
            'title': 'Storage Target',
            'username': 'target_group',
            'total_members': 500
        }

    async def start_visible_storage(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  group_info: Dict[str, Any], account_ids: List[str],
                                  category_name: str):
        """تنفيذ التخزين الظاهر (Visible Members)"""
        category_id = await self.db_manager.get_or_create_storage_category(category_name)
        storage_group_id = await self.db_manager.create_storage_group(
            category_id=category_id,
            group_id=group_info['id'],
            title=group_info['title'],
            username=group_info.get('username'),
            total_members=group_info['total_members'],
            storage_type='visible'
        )

        await update.effective_message.reply_text(f"👁️ بدء التخزين الظاهر: {group_info['title']}")
        logger.info(f"Started visible storage for {storage_group_id}")

    async def get_members_from_messages_batch(self, client: StorageTDLibClient, group_id: int,
                                            batch_size: int = 100):
        """مسح الرسائل بالدفعات مع حماية Pagination و Flood Wait"""
        members = {}
        from_message_id = 0
        total_scanned = 0

        while total_scanned < 5000:
            try:
                res = await client.get_chat_history(group_id, from_message_id, batch_size)

                # [P1 Fix] Pagination Loop Safety
                if not res or res.get('@type') == 'error':
                    logger.error(f"History scan stopped: {res}")
                    break

                messages = res.get('messages', [])
                if not messages:
                    logger.info("End of history reached.")
                    break

                # Check for infinite loop if last message ID is same as from_message_id
                last_msg_id = messages[-1]['id']
                if last_msg_id == from_message_id:
                    break

                # Extract members logic ...
                # ...

                from_message_id = last_msg_id
                total_scanned += len(messages)
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Critical error in scraping loop: {e}")
                break

        return list(members.values())

    async def start_hidden_storage(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 group_info: Dict[str, Any], account_ids: List[str], 
                                 category_name: str, months: int, last_seen: int):
        category_id = await self.db_manager.get_or_create_storage_category(category_name)
        storage_group_id = await self.db_manager.create_storage_group(
            category_id=category_id,
            group_id=group_info['id'],
            title=group_info['title'],
            username=group_info.get('username'),
            total_members=group_info['total_members'],
            storage_type='hidden',
            scan_months=months,
            last_seen_months=last_seen
        )
        
        await update.effective_message.reply_text(f"🚀 بدء التخزين المخفي: {group_info['title']}")

    def cleanup_resources(self):
        pass
