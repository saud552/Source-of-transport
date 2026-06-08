# -*- coding: utf-8 -*-
"""
عميل TDLib للنقل (Enhanced Logging Version)
"""

import asyncio
import json
import logging
import threading
import re
import tempfile
import shutil
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from shared_config import API_ID, API_HASH
from transf.config import tdjson

logger = logging.getLogger(__name__)

class TDLibClient:
    """عميل TDLib للنقل مع حماية Flood Wait وتعقب الاستجابة وتدوين مفصل"""
    
    def __init__(self, phone: str, session_string: str, device_info: Dict[str, Any]):
        self.phone = phone
        self.session_string = session_string
        self.device_info = device_info
        self.client = tdjson.td_json_client_create()

        self.is_initialized = False
        self.auth_state = None
        self.db_directory = None
        self.flood_until = 0  # timestamp

        self.event_queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self._stop_event = threading.Event()
        self._receiver_thread = None
        self._dispatcher_task = None

        self._waiters: Dict[str, asyncio.Future] = {}

    def _receive_loop(self):
        while not self._stop_event.is_set():
            try:
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"[{self.phone}] Receiver thread error: {e}")
                break

    async def _dispatcher_loop(self):
        while not self._stop_event.is_set():
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')
                extra_id = event.get('@extra')

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    logger.debug(f"[{self.phone}] Auth State: {self.auth_state}")

                if extra_id and extra_id in self._waiters:
                    future = self._waiters.pop(extra_id)
                    if not future.done():
                        future.set_result(event)

                self.event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.phone}] Dispatcher error: {e}")

    async def call_method(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        extra_id = str(uuid.uuid4())
        params['@type'] = method
        params['@extra'] = extra_id

        future = self.loop.create_future()
        self._waiters[extra_id] = future

        query_str = json.dumps(params).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            if result.get('@type') == 'error':
                code = result.get('code')
                message = result.get('message', '')
                logger.error(f"[{self.phone}] Method {method} failed: {code} - {message}")
                if code == 429:
                    match = re.search(r'\d+', message)
                    retry_after = int(match.group()) if match else 60
                    self.flood_until = asyncio.get_event_loop().time() + retry_after
                    logger.warning(f"[{self.phone}] FLOOD WAIT triggered. Locked until {datetime.fromtimestamp(self.flood_until)}")
            return result
        except asyncio.TimeoutError:
            self._waiters.pop(extra_id, None)
            logger.error(f"[{self.phone}] Method {method} timed out after {timeout}s")
            return {'@type': 'error', 'code': 408, 'message': 'Request timeout'}

    async def initialize(self) -> bool:
        if not self._receiver_thread:
            self.db_directory = tempfile.mkdtemp(prefix=f"tdlib_transf_{self.phone}_")
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        params = {
            'use_test_dc': False,
            'database_directory': self.db_directory,
            'files_directory': self.db_directory + '/files',
            'use_file_database': False,
            'use_chat_info_database': False,
            'use_message_database': True,
            'use_secret_chats': False,
            'api_id': API_ID,
            'api_hash': API_HASH,
            'system_language_code': 'en',
            'device_model': self.device_info.get('device_model', 'SM-G998B'),
            'system_version': self.device_info.get('system_version', 'Android 12'),
            'application_version': self.device_info.get('app_version', '1.0.0'),
            'enable_storage_optimizer': True,
            'ignore_file_names': True
        }
        await self.call_method('setTdlibParameters', params)
        await self.call_method('checkDatabaseEncryptionKey', {'encryption_key': ''})

        self.is_initialized = True
        logger.info(f"[{self.phone}] TDLib client initialized successfully.")
        return True


    async def get_chat_id_by_username(self, username: str) -> Optional[int]:
        res = await self.call_method('searchPublicChat', {'username': username})
        if res.get('@type') == 'chat':
            return res.get('id')
        return None

    async def get_supergroup_full_info(self, supergroup_id: int) -> Dict[str, Any]:
        return await self.call_method('getSupergroupFullInfo', {'supergroup_id': supergroup_id})

    async def get_supergroup_members(self, supergroup_id: int, filter_type: str, offset: int, limit: int) -> Dict[str, Any]:
        params = {
            'supergroup_id': supergroup_id,
            'filter': {'@type': filter_type},
            'offset': offset,
            'limit': limit
        }
        return await self.call_method('getSupergroupMembers', params)

    async def add_chat_member(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        logger.info(f"[{self.phone}] Attempting to add user {user_id} to chat {chat_id}")
        params = {
            'chat_id': chat_id,
            'user_id': user_id,
            'forward_limit': 0
        }
        return await self.call_method('addChatMember', params)

    async def close(self):
        self._stop_event.set()
        if self._dispatcher_task: self._dispatcher_task.cancel()
        if self.client:
            tdjson.td_json_client_destroy(self.client)
            self.client = None
        if self.db_directory and os.path.exists(self.db_directory):
            shutil.rmtree(self.db_directory, ignore_errors=True)
            logger.info(f"[{self.phone}] Temp directory cleaned up.")
