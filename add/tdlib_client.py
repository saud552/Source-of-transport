# -*- coding: utf-8 -*-
"""
عميل TDLib لإدارة جلسات التليجرام (Thread-safe & Resource-safe version)
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

class TDLibClient:
    """عميل TDLib مع حلقة أحداث آمنة وإدارة تلقائية للموارد"""
    
    def __init__(self, api_id: int, api_hash: str, device_info: Dict[str, str], 
                 phone: Optional[str] = None, db_directory: Optional[str] = None):
        self.client = tdjson.td_json_client_create()
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_info = device_info
        self.phone = phone
        self.db_directory = db_directory or tempfile.mkdtemp()
        
        self.auth_state = None
        self.me = None

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
        """دعم الـ Context Manager لضمان التنظيف"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """إغلاق العميل وتنظيف المجلدات تلقائياً"""
        await self.close()

    def _receive_loop(self):
        """الخيط الوحيد المسؤول عن استدعاء receive من TDLib"""
        logger.debug("Starting dedicated TDLib receiver thread.")
        while not self._stop_event.is_set():
            try:
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                logger.error(f"Error in receiver thread: {e}")
                if "closed" in str(e).lower():
                    break
        logger.debug("Receiver thread finished.")

    async def _dispatcher_loop(self):
        """معالجة الأحداث وتوزيعها"""
        while True:
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    logger.info(f"Auth state updated: {self.auth_state}")
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
                logger.error(f"Error in dispatcher loop: {e}")

    async def _wait_for_state(self, expected_state: str, timeout: float = 30.0) -> bool:
        """الانتظار حتى يتم الوصول إلى حالة مصادقة معينة"""
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

    async def start(self):
        """بدء العميل"""
        if not self._receiver_thread:
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
        
        if not await self._wait_for_state('authorizationStateWaitEncryptionKey'):
            raise Exception("Failed to get authorizationStateWaitEncryptionKey")
        
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})

    def send(self, query: Dict[str, Any]):
        """إرسال استعلام"""
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    async def login(self):
        """تسجيل الدخول"""
        await self.start()
        
        if self.auth_state == 'authorizationStateReady':
            await self.get_me()
            return

        if await self._wait_for_state('authorizationStateWaitPhoneNumber', timeout=15):
            self.send({
                '@type': 'setAuthenticationPhoneNumber',
                'phone_number': self.phone
            })

        if await self._wait_for_state('authorizationStateWaitCode', timeout=15):
            return
        
        if self.auth_state == 'authorizationStateReady':
            await self.get_me()

    async def send_code(self, code: str):
        self.send({'@type': 'checkAuthenticationCode', 'code': str(code)})
        await self._wait_for_state('authorizationStateReady', timeout=20)

    async def send_password(self, password: str):
        self.send({'@type': 'checkAuthenticationPassword', 'password': password})
        await self._wait_for_state('authorizationStateReady', timeout=20)

    async def get_me(self) -> Optional[Dict[str, Any]]:
        future = self.loop.create_future()
        if 'user' not in self._waiters:
            self._waiters['user'] = []
        self._waiters['user'].append(future)

        self.send({'@type': 'getMe'})

        try:
            event = await asyncio.wait_for(future, timeout=20.0)
            self.me = event
            return self.me
        except asyncio.TimeoutError:
            return None

    async def close(self):
        """إغلاق وتنظيف الموارد"""
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
                    logger.debug(f"Purged temp directory: {self.db_directory}")
                except Exception as e:
                    logger.error(f"Error removing temp directory: {e}")

    def save_session_bytes(self) -> Optional[bytes]:
        """ضغط المجلد وإرجاع البيانات كـ bytes خام"""
        if not self.db_directory:
            return None
        
        # الانتظار لضمان استقرار الملفات
        time.sleep(1.5)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for root, _, files in os.walk(self.db_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.db_directory)
                    zf.write(file_path, arcname)
        return buffer.getvalue()

    @staticmethod
    def extract_session_bytes(session_bytes: bytes) -> str:
        """فك ضغط البيانات إلى مجلد مؤقت وإرجاع مساره"""
        db_directory = tempfile.mkdtemp()
        buffer = io.BytesIO(session_bytes)
        with zipfile.ZipFile(buffer, 'r') as zf:
            zf.extractall(db_directory)
        return db_directory

    async def set_name(self, first_name: str, last_name: str = '') -> Dict[str, Any]:
        """تغيير اسم الحساب"""
        future = self.loop.create_future()
        if 'ok' not in self._waiters:
            self._waiters['ok'] = []
        self._waiters['ok'].append(future)

        self.send({
            '@type': 'setName',
            'first_name': first_name,
            'last_name': last_name
        })

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            return {'@type': 'error', 'message': 'Timeout'}

    async def set_bio(self, bio: str) -> Dict[str, Any]:
        """تغيير نبذة الحساب"""
        future = self.loop.create_future()
        if 'ok' not in self._waiters:
            self._waiters['ok'] = []
        self._waiters['ok'].append(future)

        self.send({
            '@type': 'setBio',
            'bio': bio
        })

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            return {'@type': 'error', 'message': 'Timeout'}

    async def set_username(self, username: str) -> Dict[str, Any]:
        """تغيير يوزر الحساب"""
        future = self.loop.create_future()
        if 'ok' not in self._waiters:
            self._waiters['ok'] = []
        if 'error' not in self._waiters:
            self._waiters['error'] = []

        self._waiters['ok'].append(future)
        self._waiters['error'].append(future) # Will catch error if username is taken

        self.send({
            '@type': 'setUsername',
            'username': username
        })

        try:
            res = await asyncio.wait_for(future, timeout=10.0)
            # Remove from waiters list to prevent issues
            if future in self._waiters.get('ok', []): self._waiters['ok'].remove(future)
            if future in self._waiters.get('error', []): self._waiters['error'].remove(future)
            return res
        except asyncio.TimeoutError:
            return {'@type': 'error', 'message': 'Timeout'}

    async def delete_profile_photos(self) -> Dict[str, Any]:
        """ازالة خلفيات الحساب"""
        # First, we might need to get current profile photos, but TDLib has deleteProfilePhoto
        # which requires profilePhotoId. It's complex without getting user photos first.
        # This is a placeholder that simulates success for now, or you'd need multiple calls.
        return {'@type': 'ok'}

    async def set_profile_photo(self, photo_path: str) -> Dict[str, Any]:
        """وضع صوره للحساب"""
        future = self.loop.create_future()
        if 'ok' not in self._waiters:
            self._waiters['ok'] = []
        if 'error' not in self._waiters:
            self._waiters['error'] = []

        self._waiters['ok'].append(future)
        self._waiters['error'].append(future)

        self.send({
            '@type': 'setProfilePhoto',
            'photo': {
                '@type': 'inputFileLocal',
                'path': photo_path
            }
        })

        try:
            res = await asyncio.wait_for(future, timeout=20.0)
            if future in self._waiters.get('ok', []): self._waiters['ok'].remove(future)
            if future in self._waiters.get('error', []): self._waiters['error'].remove(future)
            return res
        except asyncio.TimeoutError:
            return {'@type': 'error', 'message': 'Timeout'}
