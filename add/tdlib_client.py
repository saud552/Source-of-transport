# -*- coding: utf-8 -*-
"""
عميل TDLib لإدارة جلسات التليجرام (Thread-safe version)
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
    """عميل TDLib مع حلقة أحداث آمنة وخيوط معالجة موحدة"""
    
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

    def _receive_loop(self):
        """الخيط الوحيد المسؤول عن استدعاء receive من TDLib"""
        logger.debug("Starting dedicated TDLib receiver thread.")
        while not self._stop_event.is_set():
            try:
                # استدعاء receive بشكل حصرى هنا
                result = tdjson.td_json_client_receive(self.client, 1.0)
                if result:
                    event = json.loads(result.decode('utf-8'))
                    # دفع الحدث إلى queue الخاص بـ asyncio بشكل آمن
                    self.loop.call_soon_threadsafe(self.event_queue.put_nowait, event)
            except Exception as e:
                logger.error(f"Error in receiver thread: {e}")
                if "closed" in str(e).lower():
                    break
        logger.debug("Receiver thread finished.")

    async def _dispatcher_loop(self):
        """معالجة الأحداث القادمة من الـ queue وتوزيعها"""
        while True:
            try:
                event = await self.event_queue.get()
                event_type = event.get('@type')
                logger.debug(f"Dispatcher received event: {event_type}")

                if event_type == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']['@type']
                    logger.info(f"Auth state updated: {self.auth_state}")
                    self._auth_state_event.set()

                elif event_type == 'user' and event.get('id') == self.me_id if hasattr(self, 'me_id') else True:
                    # معالجة بيانات المستخدم إذا كان هذا ردًا على getMe (بشكل مبسط)
                    pass

                # إخطار أي waiter ينتظر هذا النوع من الأحداث
                # ملاحظة: يمكن تحسين هذا باستخدام @extra
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
        """الانتظار حتى يتم الوصول إلى حالة مصادقة معينة عبر حلقة الأحداث"""
        logger.info(f"Waiting for auth state: {expected_state}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.auth_state == expected_state:
                return True

            self._auth_state_event.clear()
            try:
                await asyncio.wait_for(self._auth_state_event.wait(), timeout=max(0.1, timeout - (time.time() - start_time)))
            except asyncio.TimeoutError:
                continue

        logger.error(f"Timeout waiting for state {expected_state}. Current: {self.auth_state}")
        return False

    async def start(self):
        """بدء العميل والبدء فى استقبال الأحداث"""
        if not self._receiver_thread:
            self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receiver_thread.start()

        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        # إرسال معاملات TDLib
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
        """إرسال استعلام إلى TDLib (آمن للخيوط)"""
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    async def login(self):
        """إدارة عملية تسجيل الدخول الكاملة"""
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
        """إرسال رمز التحقق والانتظار عبر الـ queue"""
        self.send({'@type': 'checkAuthenticationCode', 'code': str(code)})
        await self._wait_for_state('authorizationStateReady', timeout=20)
        if self.auth_state not in ['authorizationStateReady', 'authorizationStateWaitPassword']:
            raise Exception(f"Failed to login with code. State: {self.auth_state}")

    async def send_password(self, password: str):
        """إرسال كلمة المرور والانتظار عبر الـ queue"""
        self.send({'@type': 'checkAuthenticationPassword', 'password': password})
        if not await self._wait_for_state('authorizationStateReady', timeout=20):
            raise Exception(f"Failed to login with password. State: {self.auth_state}")

    async def get_me(self) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المستخدم عبر نظام الانتظار الموحد"""
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
            logger.error("Timeout waiting for getMe response")
            return None

    async def close(self):
        """إغلاق العميل وتنظيف الموارد بشكل آمن"""
        self._stop_event.set()
        if self._dispatcher_task:
            self._dispatcher_task.cancel()

        try:
            self.send({'@type': 'close'})
            # انتظار حتى يتم الإغلاق من طرف TDLib
            await self._wait_for_state('authorizationStateClosed', timeout=5.0)
        finally:
            tdjson.td_json_client_destroy(self.client)
            if self.db_directory and os.path.exists(self.db_directory):
                try:
                    await asyncio.to_thread(shutil.rmtree, self.db_directory)
                except Exception as e:
                    logger.error(f"Error removing temp directory: {e}")

    def save_session(self) -> Optional[str]:
        """حفظ الجلسة (بناءً على الملفات في المجلد المؤقت)"""
        if not self.db_directory:
            return None
        
        # التأكد من ثبات الملفات
        time.sleep(1)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for root, _, files in os.walk(self.db_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.db_directory)
                    zf.write(file_path, arcname)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @staticmethod
    async def load_session(session_str: str, api_id: int, api_hash: str, device_info: Dict[str, str]):
        """تحميل جلسة من سلسلة مشفرة"""
        session_bytes = base64.b64decode(session_str.encode('utf-8'))
        db_directory = tempfile.mkdtemp()
        
        buffer = io.BytesIO(session_bytes)
        with zipfile.ZipFile(buffer, 'r') as zf:
            zf.extractall(db_directory)
        
        if isinstance(device_info, str):
            device_info = json.loads(device_info)
            
        client = TDLibClient(api_id, api_hash, device_info, db_directory=db_directory)
        await client.start()
        
        if not await client._wait_for_state('authorizationStateReady', timeout=20):
            await client.close()
            raise Exception("Session is invalid or expired.")
        
        await client.get_me()
        return client
