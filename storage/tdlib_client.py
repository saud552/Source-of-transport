# -*- coding: utf-8 -*-
"""
عميل TDLib لبوت التخزين (Thread-safe & Resource-safe version)
"""

import os
import json
import time
import asyncio
import tempfile
import shutil
import zipfile
import io
import base64
import logging
import threading
from typing import Optional, Dict, Any, List

from .config import tdjson, API_ID, API_HASH

logger = logging.getLogger(__name__)

class StorageTDLibClient:
    """عميل TDLib لبوت التخزين مع حلقة أحداث آمنة وإدارة تلقائية للموارد"""
    
    def __init__(self, api_id: int, api_hash: str, phone: str, device_info: Dict[str, str]):
        self.client = tdjson.td_json_client_create()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.device_info = device_info

        self.auth_state = None
        self.me = None
        self.db_directory = None

        # حلقة أحداث آمنة
        self.event_queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self._stop_event = threading.Event()
        self._receiver_thread = None
        self._dispatcher_task = None

        # مستمعون للأحداث
        self._auth_state_event = asyncio.Event()
        self._waiters: Dict[str, List[asyncio.Future]] = {} # type: ignore

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _receive_loop(self):
        """الخيط الوحيد المسؤول عن استدعاء receive من TDLib"""
        logger.debug("Starting dedicated Storage TDLib receiver thread.")
        while not self._stop_event.is_set():
            try:
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                logger.error(f"Error in storage receiver thread: {e}")
                if "closed" in str(e).lower():
                    break
        logger.debug("Storage receiver thread finished.")

    async def _dispatcher_loop(self):
        """معالجة الأحداث وتوزيعها"""
        while True:
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    logger.info(f"Storage Auth state: {self.auth_state}")
                    self._auth_state_event.set()

                # توزيع الأحداث على الـ waiters
                if event_type in self._waiters:
                    for future in self._waiters[event_type]:
                        if not future.done():
                            future.set_result(event)
                    self._waiters[event_type] = []

                self.event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in storage dispatcher loop: {e}")

    async def _wait_for_state(self, expected_state: str, timeout: float = 30.0) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.auth_state == expected_state:
                return True
            self._auth_state_event.clear()
            try:
                await asyncio.wait_for(self._auth_state_event.wait(), timeout=max(0.1, timeout - (time.time() - start_time)))
            except asyncio.TimeoutError:
                continue
        return False

    def initialize(self):
        """تهيئة العميل وبدء الخيوط"""
        if not self._receiver_thread:
            self.db_directory = tempfile.mkdtemp()
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()

        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        params = {
            '@type': 'setTdlibParameters',
            'database_directory': self.db_directory,
            'use_message_database': True,
            'use_secret_chats': True,
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'system_language_code': 'en',
            'device_model': self.device_info['device_model'],
            'system_version': self.device_info['system_version'],
            'application_version': self.device_info['app_version'],
            'enable_storage_optimizer': True
        }
        self.send(params)
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})

    def send(self, query: Dict[str, Any]):
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    async def get_me(self) -> Optional[Dict[str, Any]]:
        future = self.loop.create_future()
        if 'user' not in self._waiters: self._waiters['user'] = []
        self._waiters['user'].append(future)
        self.send({'@type': 'getMe'})
        try:
            return await asyncio.wait_for(future, timeout=20.0)
        except asyncio.TimeoutError:
            return None

    async def get_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        future = self.loop.create_future()
        if 'chat' not in self._waiters: self._waiters['chat'] = []
        self._waiters['chat'].append(future)
        self.send({'@type': 'getChat', 'chat_id': chat_id})
        try:
            return await asyncio.wait_for(future, timeout=20.0)
        except asyncio.TimeoutError:
            return None

    async def get_chat_full_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        # التوافق مع getSupergroupFullInfo للقروبات الكبيرة
        future = self.loop.create_future()
        if 'supergroupFullInfo' not in self._waiters: self._waiters['supergroupFullInfo'] = []
        self._waiters['supergroupFullInfo'].append(future)
        self.send({'@type': 'getSupergroupFullInfo', 'supergroup_id': chat_id})
        try:
            return await asyncio.wait_for(future, timeout=20.0)
        except asyncio.TimeoutError:
            return None

    async def search_public_chat(self, username: str) -> Optional[Dict[str, Any]]:
        future = self.loop.create_future()
        if 'chat' not in self._waiters: self._waiters['chat'] = []
        self._waiters['chat'].append(future)
        self.send({'@type': 'searchPublicChat', 'username': username})
        try:
            return await asyncio.wait_for(future, timeout=20.0)
        except asyncio.TimeoutError:
            return None

    async def close(self):
        self._stop_event.set()
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
        try:
            self.send({'@type': 'close'})
            await self._wait_for_state('authorizationStateClosed', timeout=5.0)
        finally:
            tdjson.td_json_client_destroy(self.client)
            if self.db_directory and os.path.exists(self.db_directory):
                try:
                    await asyncio.to_thread(shutil.rmtree, self.db_directory)
                except:
                    pass

    def save_session(self) -> Optional[str]:
        if not self.db_directory: return None
        time.sleep(1.5)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for root, _, files in os.walk(self.db_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    zf.write(file_path, os.path.relpath(file_path, self.db_directory))
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @staticmethod
    def load_session(session_str: str, api_id: int, api_hash: str, device_info: Dict[str, str]):
        session_bytes = base64.b64decode(session_str.encode('utf-8'))
        db_directory = tempfile.mkdtemp()
        with zipfile.ZipFile(io.BytesIO(session_bytes), 'r') as zf:
            zf.extractall(db_directory)

        client = StorageTDLibClient(api_id, api_hash, "", device_info)
        client.db_directory = db_directory
        client.initialize()
        return client
