# -*- coding: utf-8 -*-
"""
عميل TDLib لبوت التخزين (Thread-safe & Flood-aware version)
"""

import os
import json
import time
import asyncio
import tempfile
import shutil
import logging
import threading
import re
from typing import Optional, Dict, Any, List

from .config import tdjson

logger = logging.getLogger(__name__)

class StorageTDLibClient:
    """عميل TDLib لبوت التخزين مع حلقة أحداث آمنة ومعالجة Flood Wait"""
    
    def __init__(self, api_id: int, api_hash: str, phone: str, device_info: Dict[str, str]):
        self.client = tdjson.td_json_client_create()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.device_info = device_info

        self.auth_state = None
        self.db_directory = None

        # حلقة أحداث آمنة
        self.event_queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self._stop_event = threading.Event()
        self._receiver_thread = None
        self._dispatcher_task = None

        # مستمعون للأحداث
        self._auth_state_event = asyncio.Event()
        self._waiters: Dict[str, List[asyncio.Future]] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _receive_loop(self):
        """الخيط الوحيد المسؤول عن استدعاء receive من TDLib"""
        while not self._stop_event.is_set():
            try:
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in storage receiver thread: {e}")
                break

    async def _dispatcher_loop(self):
        """معالجة الأحداث وتوزيعها"""
        while not self._stop_event.is_set():
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    self._auth_state_event.set()

                elif event_type == 'error':
                    code = event.get('code')
                    message = event.get('message', '')
                    if code == 429:
                        logger.warning(f"Flood Wait detected for {self.phone}: {message}")

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

    async def _wait_for_response(self, event_type: str, timeout: float = 20.0) -> Optional[Dict[str, Any]]:
        """انتظار رد معين مع معالجة الأخطاء وحماية Flood Wait"""
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
            elif error_future in done:
                err = error_future.result()
                if err.get('code') == 429:
                    # استخراج مدة الانتظار
                    match = re.search(r'\d+', err.get('message', ''))
                    retry_after = int(match.group()) if match else 30
                    logger.warning(f"Account {self.phone} flood waited. Cooling down for {retry_after}s")
                    await asyncio.sleep(retry_after)
                return err
            return None
        except asyncio.TimeoutError:
            return None

    def initialize(self):
        """تهيئة العميل مع مسار تخزين مؤقت"""
        if not self._receiver_thread:
            self.db_directory = tempfile.mkdtemp(prefix=f"tdlib_storage_{self.phone}_")
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()

        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        params = {
            '@type': 'setTdlibParameters',
            'database_directory': self.db_directory,
            'use_message_database': True,
            'use_secret_chats': False,
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'system_language_code': 'en',
            'device_model': self.device_info.get('device_model', 'SM-G998B'),
            'system_version': self.device_info.get('system_version', 'Android 12'),
            'application_version': self.device_info.get('app_version', '8.5.1'),
            'enable_storage_optimizer': True
        }
        self.send(params)
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})

    def send(self, query: Dict[str, Any]):
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    async def get_chat_history(self, chat_id: int, from_message_id: int, limit: int) -> Optional[Dict[str, Any]]:
        self.send({
            '@type': 'getChatHistory',
            'chat_id': chat_id,
            'from_message_id': from_message_id,
            'limit': limit,
            'only_local': False
        })
        res = await self._wait_for_response('messages')
        return res if res and res.get('@type') == 'messages' else None

    async def close(self):
        """إغلاق آمن للعميل وتنظيف الموارد"""
        self._stop_event.set()
        if self._dispatcher_task:
            self._dispatcher_task.cancel()

        try:
            # محاولة إغلاق TDLib بشكل نظامي
            self.send({'@type': 'close'})
            # انتظار قصير للحالة Closed
            for _ in range(10):
                if self.auth_state == 'authorizationStateClosed':
                    break
                await asyncio.sleep(0.1)
        except Exception:
            pass
        finally:
            if self.client:
                tdjson.td_json_client_destroy(self.client)
                self.client = None

            # تنظيف المجلد المؤقت بشكل نهائي ومضمون
            if self.db_directory and os.path.exists(self.db_directory):
                try:
                    shutil.rmtree(self.db_directory, ignore_errors=True)
                    logger.info(f"Cleaned up temp directory for {self.phone}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {self.db_directory}: {e}")

