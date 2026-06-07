# -*- coding: utf-8 -*-
"""
مدير عمليات النقل (Jitter & Enhanced Logging Version)
"""

import asyncio
import logging
import json
import random
from datetime import datetime
from typing import List, Dict, Any, Optional

from .tdlib_client import TDLibClient
from .database import TransferDatabaseManager
from .config import (
    BATCH_SIZE, MIN_JITTER_DELAY, MAX_JITTER_DELAY,
    BATCH_ROTATE_DELAY, ACCOUNT_WAIT_TIMEOUT
)

logger = logging.getLogger(__name__)

class ClientPool:
    """إدارة مجموعة من عملاء TDLib النشطين مع تدوين مفصل للتدوير"""

    def __init__(self, accounts: List[Dict[str, Any]]):
        self.clients: List[TDLibClient] = []
        self._accounts = accounts
        self._current_index = 0

    async def initialize_all(self):
        for acc in self._accounts:
            client = TDLibClient(
                phone=acc['phone'],
                session_string=acc['session_str'],
                device_info=json.loads(acc['device_info']) if isinstance(acc['device_info'], str) else acc['device_info']
            )
            if await client.initialize():
                self.clients.append(client)
        logger.info(f"Client pool ready with {len(self.clients)} accounts.")

    def get_next_available(self) -> Optional[TDLibClient]:
        if not self.clients: return None

        start_index = self._current_index
        now = asyncio.get_event_loop().time()

        while True:
            client = self.clients[self._current_index % len(self.clients)]
            self._current_index += 1

            if client.flood_until <= now:
                logger.debug(f"Rotating to account: {client.phone}")
                return client

            if (self._current_index % len(self.clients)) == start_index:
                return None

    async def close_all(self):
        for client in self.clients:
            await client.close()
        self.clients = []

class TransferManager:
    """مدير عمليات النقل بمحاكاة سلوك بشري وتدوين دقيق"""
    
    def __init__(self, db_manager: TransferDatabaseManager):
        self.db_manager = db_manager
        self.active_transfers = {}
    
    def get_jitter(self):
        """توليد تأخير عشوائي لمحاكاة النشاط البشري"""
        return random.uniform(MIN_JITTER_DELAY, MAX_JITTER_DELAY)

    async def start_transfer(self, transfer_id: str, members: List[Dict[str, Any]], 
                             accounts: List[Dict[str, Any]], update, context) -> None:
        client_pool = ClientPool(accounts)
        await client_pool.initialize_all()

        try:
            self.active_transfers[transfer_id] = {
                'status': 'running',
                'transferred_count': 0,
                'failed_count': 0,
                'privacy_count': 0,
                'members': members,
                'start_time': datetime.now()
            }
            
            logger.info(f"Starting Transfer ID: {transfer_id} for {len(members)} members.")

            for i, member in enumerate(members):
                if transfer_id not in self.active_transfers or self.active_transfers[transfer_id]['status'] == 'cancelled':
                    logger.info(f"Transfer {transfer_id} was cancelled.")
                    break
                
                if self.active_transfers[transfer_id]['status'] == 'paused':
                    logger.info(f"Transfer {transfer_id} is paused.")
                    while self.active_transfers[transfer_id]['status'] == 'paused':
                        await asyncio.sleep(1)

                client = client_pool.get_next_available()
                if not client:
                    logger.warning(f"All accounts in pool are flood-waited. Waiting {BATCH_ROTATE_DELAY}s")
                    await asyncio.sleep(BATCH_ROTATE_DELAY)
                    continue

                # Add member
                status = await self._process_member_addition(client, member, transfer_id)
                
                if status == 'success':
                    self.active_transfers[transfer_id]['transferred_count'] += 1
                elif status == 'privacy_restricted':
                    self.active_transfers[transfer_id]['privacy_count'] += 1
                else:
                    self.active_transfers[transfer_id]['failed_count'] += 1

                # Progress Update
                if (i + 1) % 5 == 0 or (i + 1) == len(members):
                    progress = ((i + 1) / len(members)) * 100
                    await self._update_progress(transfer_id, progress, update, context)
                
                # Human behavior jitter
                delay = self.get_jitter()
                logger.debug(f"Applying jitter delay: {delay:.2f}s")
                await asyncio.sleep(delay)
            
            await self._complete_transfer(transfer_id, update, context)
            
        except Exception as e:
            logger.exception(f"Critical failure in transfer {transfer_id}: {e}")
            await self._handle_transfer_error(transfer_id, str(e), update, context)
        finally:
            await client_pool.close_all()
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]

    async def _process_member_addition(self, client: TDLibClient, member: Dict[str, Any],
                                     transfer_id: str) -> str:
        try:
            ops = await self.db_manager.get_transfer_operations(limit=1)
            target_group_id = ops[0]['target_group_id']
            
            res = await client.add_chat_member(target_group_id, member['user_id'])

            status = 'failed'
            error_msg = None

            if res.get('@type') == 'ok':
                status = 'success'
                logger.info(f"SUCCESS: User {member['user_id']} added to {target_group_id} via {client.phone}")
            elif res.get('@type') == 'error':
                error_msg = res.get('message', 'Unknown Error')
                if 'PRIVACY' in error_msg:
                    status = 'privacy_restricted'
                    logger.warning(f"PRIVACY: User {member['user_id']} restricted additions via {client.phone}")
                elif res.get('code') == 429:
                    logger.error(f"FLOOD: Account {client.phone} hit limit during addition.")
                    return 'flood'
                else:
                    logger.error(f"FAILED: User {member['user_id']} addition failed: {error_msg}")

            await self.db_manager.update_member_transfer_status(
                transfer_id, member['user_id'], status, error_msg
            )
            return status
        except Exception as e:
            logger.error(f"Unexpected error in addition: {e}")
            return 'failed'

    async def _update_progress(self, transfer_id: str, progress: float, update, context) -> None:
        info = self.active_transfers.get(transfer_id)
        if not info: return

        await self.db_manager.update_transfer_operation(
            transfer_id,
            transferred_members=info['transferred_count'],
            failed_members=info['failed_count'] + info['privacy_count']
        )

        text = (f"🚀 **تقدم عملية النقل...**\n\n"
                f"📊 **التقدم:** {progress:.1f}%\n"
                f"✅ **نجاح:** {info['transferred_count']}\n"
                f"🔐 **خصوصية:** {info['privacy_count']}\n"
                f"❌ **فشل:** {info['failed_count']}\n")

        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _complete_transfer(self, transfer_id: str, update, context) -> None:
        info = self.active_transfers.get(transfer_id)
        if not info: return
        duration = datetime.now() - info['start_time']
        await self.db_manager.update_transfer_operation(transfer_id, status='completed', completed_at=datetime.now())

        logger.info(f"Transfer {transfer_id} completed in {duration}. Success: {info['transferred_count']}")

        text = (f"✅ **تم إنجاز عملية النقل!**\n\n"
                f"⏱ **الوقت المستغرق:** {str(duration).split('.')[0]}\n"
                f"✅ **تم النقل:** {info['transferred_count']}\n"
                f"🔐 **قيود الخصوصية:** {info['privacy_count']}")

        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _handle_transfer_error(self, transfer_id: str, error_message: str, update, context) -> None:
        await self.db_manager.update_transfer_operation(transfer_id, status='failed')
        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(f"❌ **خطأ:** {error_message}", parse_mode='Markdown')
            except: pass
