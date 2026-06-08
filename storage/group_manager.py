# -*- coding: utf-8 -*-
import asyncio
import logging
import uuid
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from add.tdlib_client import TDLibClient # Assuming we can reuse it, or we import StorageTDLibClient
from .database import StorageDatabaseManager
from .keyboards import get_storage_progress_keyboard
from shared_config import API_ID, API_HASH
from add.encryption import EncryptionManager
from shared_config import PASSPHRASE, SALT

logger = logging.getLogger(__name__)

class GroupManager:
    """مدير المجموعات لتخزين الأعضاء باستخدام PostgreSQL وتوزيع الحسابات"""
    
    def __init__(self, db_manager: StorageDatabaseManager):
        self.db_manager = db_manager
        self.active_tasks = {}
        self.pause_events = {}
        self.cancel_events = {}
        self.encryption = EncryptionManager(PASSPHRASE, SALT)

    async def get_group_info(self, client: TDLibClient, group_link: str) -> Optional[Dict[str, Any]]:
        # Resolve username or link to get group ID and info
        username = group_link.split("/")[-1].replace("@", "")
        chat_id = await client.get_chat_id_by_username(username)
        if not chat_id:
            return None

        # Get chat info
        future = client.loop.create_future()
        if 'chat' not in client._waiters: client._waiters['chat'] = []
        client._waiters['chat'].append(future)
        client.send({'@type': 'getChat', 'chat_id': chat_id})

        try:
            chat = await asyncio.wait_for(future, timeout=5.0)
            if future in client._waiters.get('chat', []): client._waiters['chat'].remove(future)
            return {
                'id': chat['id'],
                'title': chat.get('title', username),
                'username': username,
                'total_members': 0 # We might not know exact count yet
            }
        except:
            return None

    async def start_hidden_storage(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 group_links: List[str], accounts: List[Dict[str, Any]],
                                 storage_category: str, mechanism: str):

        cat_id = await self.db_manager.get_or_create_storage_category(storage_category)

        job_id = str(uuid.uuid4())
        self.active_tasks[job_id] = {
            'status': 'running',
            'groups': group_links,
            'accounts': accounts,
            'mechanism': mechanism,
            'total_scanned': 0,
            'total_stored': 0
        }

        msg = await update.callback_query.message.reply_text("🚀 **بدء التخزين المخفي...**\nجاري تجهيز الحسابات والاتصال بالمجموعات...", parse_mode="Markdown")
        context.user_data['current_storage_job'] = job_id
        context.user_data['storage_msg_id'] = msg.message_id

        asyncio.create_task(self._hidden_storage_engine(job_id, cat_id, update, context))

    async def _hidden_storage_engine(self, job_id: str, cat_id: str, update, context):
        task = self.active_tasks[job_id]
        accounts = task['accounts']
        group_links = task['groups']
        mechanism = task['mechanism']

        # 1. Initialize all clients
        clients = []
        for acc in accounts:
            db_dir = TDLibClient.load_session(acc['session_str'], self.encryption)
            if db_dir:
                client = TDLibClient(API_ID, API_HASH, {"device_model": "StorageWorker", "system_version": "1.0", "app_version": "1.0"}, phone=acc['phone'], db_directory=db_dir)
                try:
                    await client.start()
                    if client.auth_state == 'authorizationStateReady':
                        clients.append(client)
                    else:
                        await client.close()
                except:
                    await client.close()

        if not clients:
            await context.bot.edit_message_text("❌ فشل التخزين: لا يوجد حسابات فعالة للعمل.", chat_id=update.effective_chat.id, message_id=context.user_data['storage_msg_id'])
            return

        # 2. Process groups
        for link in group_links:
            if task['status'] == 'cancelled': break

            # Use first client to resolve group
            g_info = await self.get_group_info(clients[0], link)
            if not g_info:
                continue

            storage_group_id = await self.db_manager.create_storage_group(
                category_id=cat_id, group_id=g_info['id'], title=g_info['title'],
                username=g_info['username'], total_members=0, storage_type='hidden'
            )

            # 3. Distribution logic
            if mechanism == 'monthly':
                # e.g., last 3 months
                await self._run_monthly_scraping(job_id, storage_group_id, g_info['id'], clients, update, context)
            else:
                # e.g., 100k messages
                await self._run_count_scraping(job_id, storage_group_id, g_info['id'], clients, update, context)

        # Cleanup
        for c in clients:
            await c.close()

        if task['status'] != 'cancelled':
            await self._update_progress_msg(job_id, update, context, final=True)

    async def _run_monthly_scraping(self, job_id, storage_group_id, chat_id, clients, update, context):
        # Simply split tasks by offset date
        task = self.active_tasks[job_id]
        num_clients = len(clients)

        months_str = await self.db_manager.get_setting('monthly_duration')
        months = int(months_str) if months_str else 3
        total_days = months * 30

        now = datetime.now()
        start_date = now - timedelta(days=total_days)

        days_per_client = total_days // num_clients

        tasks = []
        for i, client in enumerate(clients):
            c_end = now - timedelta(days=i*days_per_client)
            c_start = c_end - timedelta(days=days_per_client)
            if i == num_clients - 1: c_start = start_date # Ensure full coverage

            tasks.append(asyncio.create_task(
                self._scrape_worker(job_id, storage_group_id, chat_id, client, update, context, start_date=c_start, end_date=c_end)
            ))

        await asyncio.gather(*tasks)

    async def _run_count_scraping(self, job_id, storage_group_id, chat_id, clients, update, context):
        task = self.active_tasks[job_id]
        num_clients = len(clients)

        count_str = await self.db_manager.get_setting('message_count')
        total_count = int(count_str) if count_str else 100000

        msgs_per_client = total_count // num_clients

        # Getting first message id is tricky without knowing the top,
        # assume offset 0 starts at newest, and we just use `offset` parameter in getChatHistory
        tasks = []
        for i, client in enumerate(clients):
            offset = i * msgs_per_client
            limit = msgs_per_client
            tasks.append(asyncio.create_task(
                self._scrape_worker(job_id, storage_group_id, chat_id, client, update, context, offset=offset, limit=limit)
            ))

        await asyncio.gather(*tasks)

    async def _scrape_worker(self, job_id, storage_group_id, chat_id, client, update, context,
                             start_date=None, end_date=None, offset=0, limit=10000):
        ls_filter = await self.db_manager.get_setting('last_seen_filter') or 'all'
        task = self.active_tasks[job_id]

        from_message_id = 0
        scanned = 0
        members_buffer = []

        # For simplicity, we just use getChatHistory
        # In a perfect TDLib implementation, we'd find the exact message ID for the date.

        while scanned < limit:
            while task['status'] == 'paused':
                await asyncio.sleep(1)
            if task['status'] == 'cancelled':
                break

            future = client.loop.create_future()
            if 'messages' not in client._waiters: client._waiters['messages'] = []
            client._waiters['messages'].append(future)

            client.send({
                '@type': 'getChatHistory',
                'chat_id': chat_id,
                'from_message_id': from_message_id,
                'offset': offset if scanned == 0 else 0,
                'limit': min(100, limit - scanned),
                'only_local': False
            })

            try:
                res = await asyncio.wait_for(future, timeout=10.0)
                if future in client._waiters.get('messages', []): client._waiters['messages'].remove(future)

                msgs = res.get('messages', [])
                if not msgs: break

                last_msg_id = msgs[-1]['id']
                if last_msg_id == from_message_id: break
                from_message_id = last_msg_id

                for m in msgs:
                    # date check
                    msg_date = datetime.fromtimestamp(m['date'])
                    if start_date and msg_date < start_date: continue
                    if end_date and msg_date > end_date: continue

                    sender = m.get('sender_id')
                    if sender and sender.get('@type') == 'messageSenderUser':
                        user_id = sender['user_id']
                        # if ls_filter != 'all': fetch user and check status ... (omitted for brevity)
                        members_buffer.append({'id': user_id, 'is_bot': False})

                scanned += len(msgs)
                task['total_scanned'] += len(msgs)

                if len(members_buffer) >= 100:
                    inserted = await self.db_manager.bulk_store_members(storage_group_id, members_buffer)
                    task['total_stored'] += inserted
                    members_buffer = []
                    await self._update_progress_msg(job_id, update, context)

            except:
                break

        if members_buffer:
            inserted = await self.db_manager.bulk_store_members(storage_group_id, members_buffer)
            task['total_stored'] += inserted
            await self._update_progress_msg(job_id, update, context)

    async def _update_progress_msg(self, job_id, update, context, final=False):
        task = self.active_tasks.get(job_id)
        if not task: return

        status_ar = "▶️ جاري التخزين"
        if task['status'] == 'paused': status_ar = "⏸️ متوقف مؤقتاً"
        if task['status'] == 'cancelled': status_ar = "❌ تم الإلغاء"
        if final: status_ar = "✅ اكتمل التخزين"

        text = f"📊 **تقدم عملية التخزين**\n\n"
        text += f"الحالة: {status_ar}\n"
        text += f"الرسائل المفحوصة: {task['total_scanned']}\n"
        text += f"الأعضاء المخزنين: {task['total_stored']}\n"
        
        kb = get_storage_progress_keyboard() if not final and task['status'] != 'cancelled' else None

        try:
            await context.bot.edit_message_text(text, chat_id=update.effective_chat.id,
                                              message_id=context.user_data['storage_msg_id'],
                                              reply_markup=kb, parse_mode="Markdown")
        except: pass

    def pause_job(self, job_id):
        if job_id in self.active_tasks: self.active_tasks[job_id]['status'] = 'paused'
    def resume_job(self, job_id):
        if job_id in self.active_tasks: self.active_tasks[job_id]['status'] = 'running'
    def cancel_job(self, job_id):
        if job_id in self.active_tasks: self.active_tasks[job_id]['status'] = 'cancelled'

