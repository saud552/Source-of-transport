import uuid
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


    async def start_direct_transfer(self, target_group_id: int, source_links: List[str],
                                    accounts: List[Dict[str, Any]], update, context) -> None:
        client_pool = ClientPool(accounts)
        await client_pool.initialize_all()

        transfer_id = str(uuid.uuid4())
        self.active_transfers[transfer_id] = {
            'status': 'extracting',
            'transferred_count': 0,
            'failed_count': 0,
            'privacy_count': 0,
            'members': [],
            'start_time': datetime.now()
        }

        await self.db_manager.create_transfer_operation(
            source_group_id=0, source_group_title="Direct Links",
            target_group_id=target_group_id, target_group_title=str(target_group_id),
            account_category=accounts[0].get('category_id') if accounts else None
        )

        msg = await update.callback_query.message.reply_text("🚀 **بدء الاستخراج المباشر...**\nجاري سحب الأعضاء...", parse_mode="Markdown")
        context.user_data['direct_transfer_id'] = transfer_id
        context.user_data['transfer_msg_id'] = msg.message_id

        asyncio.create_task(self._direct_transfer_engine(transfer_id, target_group_id, source_links, client_pool, update, context))

    async def _direct_transfer_engine(self, transfer_id, target_group_id, source_links, client_pool, update, context):
        task = self.active_transfers[transfer_id]

        # 1. Extraction Phase
        members_buffer = []
        for link in source_links:
            if task['status'] == 'cancelled': break

            client = client_pool.get_next_available()
            if not client: continue

            # Resolve group link
            username = link.split("/")[-1].replace("@", "")
            source_id = await client.get_chat_id_by_username(username)
            if not source_id: continue

            # If Supergroup, extract
            if str(source_id).startswith("-100"):
                supergroup_id = int(str(source_id)[4:])

                try:
                    info_res = await client.get_supergroup_full_info(supergroup_id)
                    if info_res.get('@type') == 'supergroupFullInfo':
                        member_count = info_res.get('member_count', 1000)
                        limit = min(200, member_count) # Direct transfer sample size limit to avoid long wait

                        m_res = await client.get_supergroup_members(supergroup_id, 'supergroupMembersFilterRecent', 0, limit)

                        if m_res.get('@type') == 'chatMembers':
                            for m in m_res.get('members', []):
                                mid = m.get('member_id', {}).get('user_id')
                                if mid: members_buffer.append({'user_id': mid})
                except Exception as e:
                    logger.error(f"Extraction error: {e}")

        task['members'] = members_buffer
        if task['status'] == 'cancelled':
            await client_pool.close_all()
            return

        task['status'] = 'running'

        # 2. Add Phase (reusing start_transfer logic internally but we already have pool)
        await self._transfer_execution_loop(transfer_id, members_buffer, target_group_id, client_pool, update, context)

    async def _transfer_execution_loop(self, transfer_id, members, target_group_id, client_pool, update, context):
        task = self.active_transfers[transfer_id]

        # Resolve target group ID if it's a string username
        if isinstance(target_group_id, str):
            resolve_client = client_pool.get_next_available()
            if resolve_client:
                resolved_id = await resolve_client.get_chat_id_by_username(target_group_id)
                if resolved_id: target_group_id = resolved_id

        try:
            # Settings
            min_delay = int(await self.db_manager.get_setting('delay_min') or 2)
            max_delay = int(await self.db_manager.get_setting('delay_max') or 5)
            batch_size = int(await self.db_manager.get_setting('batch_size') or 10)
            
            adds_this_account = 0
            current_client = client_pool.get_next_available()

            for i, member in enumerate(members):
                if task['status'] == 'cancelled': break
                while task['status'] == 'paused': await asyncio.sleep(1)
                
                if adds_this_account >= batch_size:
                    current_client = client_pool.get_next_available()
                    adds_this_account = 0

                if not current_client:
                    await asyncio.sleep(30)
                    current_client = client_pool.get_next_available()
                    if not current_client: continue

                res = await current_client.add_chat_member(target_group_id, member['user_id'])
                
                if res.get('@type') == 'ok':
                    task['transferred_count'] += 1
                    # Update status in db if we have group_db_id (stored transfer), for direct we skip
                    if 'group_db_id' in task:
                        await self.db_manager.update_stored_member_transfer_status(member['user_id'], task['group_db_id'], 'success')
                else:
                    err = res.get('message', '')
                    if 'PRIVACY' in err:
                        task['privacy_count'] += 1
                        status = 'privacy'
                    else:
                        task['failed_count'] += 1
                        status = 'failed'

                    if 'group_db_id' in task:
                        await self.db_manager.update_stored_member_transfer_status(member['user_id'], task['group_db_id'], status)

                adds_this_account += 1

                if (i + 1) % 5 == 0 or (i + 1) == len(members):
                    progress = ((i + 1) / len(members)) * 100
                    await self._update_progress(transfer_id, progress, update, context)
                
                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)

            await self._complete_transfer(transfer_id, update, context)
        except Exception as e:
            logger.error(f"Transfer loop error: {e}")
        finally:
            await client_pool.close_all()
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]

    async def start_stored_transfer(self, transfer_id: str, group_db_id: str, target_group_id: int,
                                  members: List[Dict[str, Any]], accounts: List[Dict[str, Any]],
                                  update, context) -> None:
        client_pool = ClientPool(accounts)
        await client_pool.initialize_all()

        self.active_transfers[transfer_id] = {
            'status': 'running',
            'transferred_count': 0,
            'failed_count': 0,
            'privacy_count': 0,
            'members': members,
            'start_time': datetime.now(),
            'group_db_id': group_db_id
        }

        await self.db_manager.create_transfer_operation(
            source_group_id=0, source_group_title="Stored Group",
            target_group_id=target_group_id, target_group_title=str(target_group_id),
            account_category=accounts[0].get('category_id') if accounts else None
        )

        msg = await update.callback_query.message.reply_text("🚀 **بدء نقل الأعضاء المخزنين...**", parse_mode="Markdown")
        context.user_data['transfer_msg_id'] = msg.message_id

        asyncio.create_task(self._transfer_execution_loop(transfer_id, members, target_group_id, client_pool, update, context))


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
