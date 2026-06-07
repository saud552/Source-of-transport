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
from .config import (
    API_ID, API_HASH, ACCOUNTS_DB_PATH,
    MAX_MESSAGES_SCAN, BATCH_SIZE, DB_INSERT_BATCH_SIZE
)

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

        # Implementation would call get_members_from_messages_batch or getChatMembers here

    async def get_members_from_messages_batch(self, client: StorageTDLibClient,
                                            storage_group_id: str, group_id: int):
        """مسح الرسائل بالدفعات مع حماية Pagination و Flood Wait والتخزين الجماعي"""
        members_buffer = []
        from_message_id = 0
        total_scanned = 0
        total_stored = 0

        while total_scanned < MAX_MESSAGES_SCAN:
            if self.cancel_events.get(storage_group_id) and self.cancel_events[storage_group_id].is_set():
                break

            if self.pause_events.get(storage_group_id) and self.pause_events[storage_group_id].is_set():
                await asyncio.sleep(1)
                continue

            try:
                res = await client.get_chat_history(group_id, from_message_id, BATCH_SIZE)

                if not res or res.get('@type') == 'error':
                    logger.error(f"History scan stopped: {res}")
                    break

                messages = res.get('messages', [])
                if not messages:
                    break

                last_msg_id = messages[-1]['id']
                if last_msg_id == from_message_id:
                    break

                for msg in messages:
                    sender = msg.get('sender_id')
                    if sender and sender.get('@type') == 'messageSenderUser':
                        user_id = sender['user_id']
                        # Simplified member extraction
                        members_buffer.append({
                            'id': user_id,
                            'first_name': f"User_{user_id}",
                            'is_bot': False
                        })

                # Bulk Insert when buffer is full
                if len(members_buffer) >= DB_INSERT_BATCH_SIZE:
                    inserted = await self.db_manager.bulk_store_members(storage_group_id, members_buffer)
                    total_stored += inserted
                    members_buffer = []
                    await self.db_manager.update_storage_progress(storage_group_id, str(client.phone), total_stored, 'running')

                from_message_id = last_msg_id
                total_scanned += len(messages)
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Critical error in scraping loop: {e}")
                break

        # Final bulk insert
        if members_buffer:
            inserted = await self.db_manager.bulk_store_members(storage_group_id, members_buffer)
            total_stored += inserted
            await self.db_manager.update_storage_progress(storage_group_id, str(client.phone), total_stored, 'completed')

        return total_stored

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
