# -*- coding: utf-8 -*-
"""
مدير عمليات النقل (Client Pooling & Flood Protection Version)
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .tdlib_client import TDLibClient
from .database import TransferDatabaseManager
from .config import BATCH_SIZE, TRANSFER_DELAY

logger = logging.getLogger(__name__)

class ClientPool:
    """إدارة مجموعة من عملاء TDLib النشطين"""

    def __init__(self, accounts: List[Dict[str, Any]]):
        self.clients: List[TDLibClient] = []
        self._accounts = accounts
        self._current_index = 0

    async def initialize_all(self):
        """تهيئة جميع الحسابات في مجمع العملاء"""
        for acc in self._accounts:
            client = TDLibClient(
                phone=acc['phone'],
                session_string=acc['session_str'],
                device_info=json.loads(acc['device_info']) if isinstance(acc['device_info'], str) else acc['device_info']
            )
            if await client.initialize():
                self.clients.append(client)
        logger.info(f"Initialized client pool with {len(self.clients)} active clients.")

    def get_next_available(self) -> Optional[TDLibClient]:
        """الحصول على الحساب التالي المتوفر وغير المحظور مؤقتاً"""
        if not self.clients: return None

        start_index = self._current_index
        now = asyncio.get_event_loop().time()

        while True:
            client = self.clients[self._current_index % len(self.clients)]
            self._current_index += 1

            if client.flood_until <= now:
                return client

            if (self._current_index % len(self.clients)) == start_index:
                # All accounts are flood-waited
                return None

    async def close_all(self):
        for client in self.clients:
            await client.close()
        self.clients = []

class TransferManager:
    """مدير عمليات النقل والتنسيق الذكي"""
    
    def __init__(self, db_manager: TransferDatabaseManager):
        self.db_manager = db_manager
        self.active_transfers = {}
    
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
                'members': members
            }
            
            for i, member in enumerate(members):
                if transfer_id not in self.active_transfers or self.active_transfers[transfer_id]['status'] == 'cancelled':
                    break
                
                # Handling pause
                if self.active_transfers[transfer_id]['status'] == 'paused':
                    while self.active_transfers[transfer_id]['status'] == 'paused':
                        await asyncio.sleep(1)

                client = client_pool.get_next_available()
                if not client:
                    logger.warning("All clients are flood-waited. Waiting 30s...")
                    await asyncio.sleep(30)
                    continue

                # Add member
                success = await self._process_member_addition(client, member, transfer_id)
                
                if success == 'success':
                    self.active_transfers[transfer_id]['transferred_count'] += 1
                elif success == 'privacy_restricted':
                    self.active_transfers[transfer_id]['privacy_count'] += 1
                else:
                    self.active_transfers[transfer_id]['failed_count'] += 1

                # Update progress every 5 members
                if i % 5 == 0:
                    progress = ((i + 1) / len(members)) * 100
                    await self._update_progress(transfer_id, progress, update, context)
                
                await asyncio.sleep(TRANSFER_DELAY)
            
            await self._complete_transfer(transfer_id, update, context)
            
        except Exception as e:
            logger.error(f"Transfer {transfer_id} error: {e}")
            await self._handle_transfer_error(transfer_id, str(e), update, context)
        finally:
            await client_pool.close_all()
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]

    async def _process_member_addition(self, client: TDLibClient, member: Dict[str, Any],
                                     transfer_id: str) -> str:
        """إضافة عضو مع التحقق الصارم من الاستجابة"""
        try:
            ops = await self.db_manager.get_transfer_operations(limit=1)
            target_group_id = ops[0]['target_group_id']
            
            res = await client.add_chat_member(target_group_id, member['user_id'])

            status = 'failed'
            error_msg = None

            if res.get('@type') == 'ok':
                status = 'success'
            elif res.get('@type') == 'error':
                error_msg = res.get('message', 'Unknown Error')
                if 'PRIVACY' in error_msg:
                    status = 'privacy_restricted'
                elif res.get('code') == 429:
                    # Flood wait already handled in client.call_method
                    return 'flood'

            await self.db_manager.update_member_transfer_status(
                transfer_id, member['user_id'], status, error_msg
            )
            return status
        except Exception as e:
            logger.error(f"Error in _process_member_addition: {e}")
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
                f"✅ **تم النقل:** {info['transferred_count']}\n"
                f"🔐 **خصوصية:** {info['privacy_count']}\n"
                f"❌ **فشل:** {info['failed_count']}\n")

        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _complete_transfer(self, transfer_id: str, update, context) -> None:
        info = self.active_transfers.get(transfer_id)
        if not info: return
        await self.db_manager.update_transfer_operation(transfer_id, status='completed', completed_at=datetime.now())
        text = f"✅ **تم إنجاز عملية النقل!**\n\nالنجاح: {info['transferred_count']}\nالخصوصية: {info['privacy_count']}"
        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _handle_transfer_error(self, transfer_id: str, error_message: str, update, context) -> None:
        await self.db_manager.update_transfer_operation(transfer_id, status='failed')
        if hasattr(update, 'callback_query') and update.callback_query:
            try: await update.callback_query.edit_message_text(f"❌ **خطأ:** {error_message}", parse_mode='Markdown')
            except: pass
