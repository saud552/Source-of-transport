# -*- coding: utf-8 -*-
"""
مدير عمليات النقل (Async PostgreSQL version)
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from .tdlib_client import TDLibClient
from .database import TransferDatabaseManager
from .config import BATCH_SIZE, TRANSFER_DELAY

logger = logging.getLogger(__name__)

class TransferManager:
    """مدير عمليات النقل والتنسيق بين الحسابات"""
    
    def __init__(self, db_manager: TransferDatabaseManager):
        self.db_manager = db_manager
        self.active_transfers = {}
    
    async def start_transfer(self, transfer_id: str, members: List[Dict[str, Any]], 
                             accounts: List[Dict[str, Any]], update, context) -> None:
        """بدء عملية النقل وتوزيعها على دفعات"""
        try:
            self.active_transfers[transfer_id] = {
                'status': 'running',
                'total_count': len(members),
                'transferred_count': 0,
                'failed_count': 0,
                'current_account_index': 0,
                'started_at': datetime.now(),
                'members': members
            }
            
            # تقسيم الأعضاء إلى دفعات
            batches = self._create_batches(members, BATCH_SIZE)
            
            for i, batch in enumerate(batches):
                # التحقق من حالة العملية
                if transfer_id not in self.active_transfers or self.active_transfers[transfer_id]['status'] == 'cancelled':
                    break
                
                # معالجة الدفعة
                await self._process_batch(transfer_id, batch, accounts, update, context)
                
                # تحديث التقدم
                progress = ((i + 1) / len(batches)) * 100
                await self._update_progress(transfer_id, progress, update, context)
                
                # تأخير بسيط بين الدفعات
                await asyncio.sleep(TRANSFER_DELAY)
            
            # إنهاء العملية
            await self._complete_transfer(transfer_id, update, context)
            
        except Exception as e:
            logger.error(f"خطأ في عملية النقل {transfer_id}: {str(e)}")
            await self._handle_transfer_error(transfer_id, str(e), update, context)
        finally:
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]
    
    def _create_batches(self, members: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        batches = []
        for i in range(0, len(members), batch_size):
            batches.append(members[i:i + batch_size])
        return batches
    
    async def _process_batch(self, transfer_id: str, batch: List[Dict[str, Any]], 
                           accounts: List[Dict[str, Any]], update, context) -> None:
        transfer_info = self.active_transfers.get(transfer_id)
        if not transfer_info: return
        
        current_account_index = transfer_info['current_account_index']
        account = accounts[current_account_index % len(accounts)]
        
        client = TDLibClient(account['session_str'], account['device_info'])
        try:
            if await client.initialize():
                for member in batch:
                    if transfer_id not in self.active_transfers: break
                    if self.active_transfers[transfer_id]['status'] == 'paused':
                        await self._wait_for_resume(transfer_id)
                    if self.active_transfers[transfer_id]['status'] == 'cancelled': break

                    success = await self._transfer_member(client, member, transfer_id)
                    if success:
                        self.active_transfers[transfer_id]['transferred_count'] += 1
                    else:
                        self.active_transfers[transfer_id]['failed_count'] += 1

                    await asyncio.sleep(1)
            
            self.active_transfers[transfer_id]['current_account_index'] = (current_account_index + 1) % len(accounts)
        finally:
            await client.close()
    
    async def _transfer_member(self, client: TDLibClient, member: Dict[str, Any], 
                             transfer_id: str) -> bool:
        try:
            ops = await self.db_manager.get_transfer_operations(limit=1)
            if not ops: return False
            target_group_id = ops[0]['target_group_id']
            
            result = await client.add_chat_member(target_group_id, member['user_id'])
            if result:
                await self.db_manager.update_member_transfer_status(transfer_id, member['user_id'], 'success')
                return True
            else:
                await self.db_manager.update_member_transfer_status(transfer_id, member['user_id'], 'failed', 'فشل في الإضافة')
                return False
        except Exception as e:
            logger.error(f"Error transferring member {member['user_id']}: {e}")
            await self.db_manager.update_member_transfer_status(transfer_id, member['user_id'], 'failed', str(e))
            return False
    
    async def _update_progress(self, transfer_id: str, progress: float, update, context) -> None:
        info = self.active_transfers.get(transfer_id)
        if not info: return

        await self.db_manager.update_transfer_operation(
            transfer_id,
            transferred_members=info['transferred_count'],
            failed_members=info['failed_count']
        )

        text = (f"🚀 **تقدم عملية النقل...**\n\n"
                f"📊 **التقدم:** {progress:.1f}%\n"
                f"✅ **تم النقل:** {info['transferred_count']}\n"
                f"❌ **فشل:** {info['failed_count']}\n")

        if hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _complete_transfer(self, transfer_id: str, update, context) -> None:
        info = self.active_transfers.get(transfer_id)
        if not info: return
        await self.db_manager.update_transfer_operation(transfer_id, status='completed', completed_at=datetime.now())
        text = f"✅ **تم إنجاز عملية النقل!**\n\nتم نقل {info['transferred_count']} عضو بنجاح."
        if hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _handle_transfer_error(self, transfer_id: str, error_message: str, update, context) -> None:
        await self.db_manager.update_transfer_operation(transfer_id, status='failed')
        text = f"❌ **فشلت عملية النقل!**\n\nسبب الخطأ: {error_message}"
        if hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass

    async def _wait_for_resume(self, transfer_id: str) -> None:
        while (transfer_id in self.active_transfers and self.active_transfers[transfer_id]['status'] == 'paused'):
            await asyncio.sleep(1)
