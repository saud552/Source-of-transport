# -*- coding: utf-8 -*-
"""
عميل TDLib للنقل (Thread-safe & Queue-based version)
"""

import asyncio
import json
import logging
import threading
import re
import tempfile
import shutil
import os
from typing import Dict, Any, Optional, List

from shared_config import API_ID, API_HASH
from transf.config import tdjson

logger = logging.getLogger(__name__)

class TDLibClient:
    """عميل TDLib للنقل مع حلقة أحداث آمنة"""
    
    def __init__(self, session_string: str, device_info: Dict[str, Any]):
        self.session_string = session_string
        self.device_info = device_info
        self.client = tdjson.td_json_client_create()
        self.is_initialized = False
        self.auth_state = None
        self.db_directory = None

        self.event_queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self._stop_event = threading.Event()
        self._receiver_thread = None
        self._dispatcher_task = None

        self._auth_state_event = asyncio.Event()
        self._waiters: Dict[str, List[asyncio.Future]] = {}

    def _receive_loop(self):
        """الخيط المخصص لاستقبال أحداث TDLib"""
        while not self._stop_event.is_set():
            try:
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in transfer receiver thread: {e}")
                break

    async def _dispatcher_loop(self):
        """توزيع الأحداث على المستقبلين"""
        while not self._stop_event.is_set():
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    self._auth_state_event.set()

                if event_type in self._waiters:
                    for future in self._waiters[event_type]:
                        if not future.done():
                            future.set_result(event)
                    self._waiters[event_type] = []

                self.event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in transfer dispatcher loop: {e}")

    async def _wait_for_response(self, event_type: str, timeout: float = 20.0) -> Optional[Dict[str, Any]]:
        future = self.loop.create_future()
        if event_type not in self._waiters: self._waiters[event_type] = []
        self._waiters[event_type].append(future)
        
        error_future = self.loop.create_future()
        if 'error' not in self._waiters: self._waiters['error'] = []
        self._waiters['error'].append(error_future)

        try:
            done, pending = await asyncio.wait(
                [future, error_future],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )
            for task in pending: task.cancel()

            if future in done:
                return future.result()
            return None
        except asyncio.TimeoutError:
            return None

    async def initialize(self) -> bool:
        """بدء تهيئة العميل"""
        if not self._receiver_thread:
            self.db_directory = tempfile.mkdtemp(prefix="tdlib_transf_")
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        params = {
            '@type': 'setTdlibParameters',
            'parameters': {
                '@type': 'tdlibParameters',
                'database_directory': self.db_directory,
                'use_message_database': True,
                'api_id': API_ID,
                'api_hash': API_HASH,
                'system_language_code': 'en',
                'device_model': self.device_info.get('device_model', 'SM-G998B'),
                'system_version': self.device_info.get('system_version', 'Android 12'),
                'application_version': self.device_info.get('app_version', '1.0.0'),
            }
        }
        self.send(params)
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})

        # انتظار حالة المصادقة
        await asyncio.sleep(1) # تبسيط للخطوة 1
        self.is_initialized = True
        return True

    def send(self, query: Dict[str, Any]):
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    async def add_chat_member(self, chat_id: int, user_id: int) -> bool:
        """إضافة عضو (Placeholder logic for Step 1)"""
        self.send({
            '@type': 'addChatMember',
            'chat_id': chat_id,
            'user_id': user_id,
            'forward_limit': 0
        })
        res = await self._wait_for_response('ok', timeout=5.0)
        return res is not None

    async def close(self):
        self._stop_event.set()
        if self._dispatcher_task: self._dispatcher_task.cancel()
        if self.client:
            tdjson.td_json_client_destroy(self.client)
            self.client = None
        if self.db_directory and os.path.exists(self.db_directory):
            shutil.rmtree(self.db_directory, ignore_errors=True)
