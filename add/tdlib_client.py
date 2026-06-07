# -*- coding: utf-8 -*-
"""
عميل TDLib لإدارة جلسات التليجرام
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
from typing import Optional, Dict, Any

from .config import tdjson, API_ID, API_HASH

logger = logging.getLogger(__name__)

class TDLibClient:
    """عميل TDLib لإدارة جلسات التليجرام"""
    
    def __init__(self, api_id: int, api_hash: str, device_info: Dict[str, str], 
                 phone: Optional[str] = None, db_directory: Optional[str] = None):
        self.client = tdjson.td_json_client_create()
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_info = device_info
        self.phone = phone
        self.db_directory = db_directory or tempfile.mkdtemp()
        
        self.auth_state = None
        self.auth_event = asyncio.Event()
        self.me = None
        self.loop_task = None

    def send(self, query: Dict[str, Any]):
        """إرسال استعلام إلى TDLib"""
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    def receive(self, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """استقبال استجابة من TDLib"""
        result = tdjson.td_json_client_receive(self.client, timeout)
        if result:
            return json.loads(result.decode('utf-8'))
        return None

    async def _event_loop(self):
        """حلقة مخصصة لمعالجة الأحداث بشكل مستمر"""
        logger.debug("Starting TDLib event loop.")
        while True:
            try:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event:
                    logger.debug(f"Event received: {event.get('@type')}")
                    if event.get('@type') == 'updateAuthorizationState':
                        self.auth_state = event['authorization_state']['@type']
                        logger.info(f"Authorization state updated: {self.auth_state}")
                        self.auth_event.set()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
                break
            await asyncio.sleep(0.01)

    async def _wait_for_state(self, expected_state: str, timeout: float = 30.0) -> bool:
        """الانتظار حتى يتم الوصول إلى حالة مصادقة معينة"""
        logger.info(f"Waiting for state: {expected_state}")
        try:
            async with asyncio.timeout(timeout):
                while self.auth_state != expected_state:
                    self.auth_event.clear()
                    await self.auth_event.wait()
            logger.info(f"Successfully reached state: {expected_state}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for state {expected_state}. Current state: {self.auth_state}")
            return False

    async def start(self):
        """بدء العميل وحلقة الأحداث"""
        if not self.loop_task:
            self.loop_task = asyncio.create_task(self._event_loop())

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
        
        # انتظار حالة طلب مفتاح التشفير
        if not await self._wait_for_state('authorizationStateWaitEncryptionKey'):
            raise Exception("Failed to get authorizationStateWaitEncryptionKey")
        
        # إرسال مفتاح التشفير (فارغ للجلسات الجديدة)
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})

    async def login(self):
        """إدارة عملية تسجيل الدخول الكاملة"""
        await self.start()
        
        if self.auth_state == 'authorizationStateReady':
            logger.info("Client is already authorized.")
            await self.get_me()
            return

        if await self._wait_for_state('authorizationStateWaitPhoneNumber', timeout=15):
            self.send({
                '@type': 'setAuthenticationPhoneNumber',
                'phone_number': self.phone
            })

        if await self._wait_for_state('authorizationStateWaitCode', timeout=15):
            return
        
        # Handle cases where it jumps to other states
        if self.auth_state == 'authorizationStateReady':
            await self.get_me()

    async def send_code(self, code: str):
        """إرسال رمز التحقق"""
        self.send({'@type': 'checkAuthenticationCode', 'code': str(code)})
        await self._wait_for_state('authorizationStateReady', timeout=20)
        if self.auth_state != 'authorizationStateReady':
            if self.auth_state != 'authorizationStateWaitPassword':
                raise Exception(f"Failed to login with code. Current state: {self.auth_state}")

    async def send_password(self, password: str):
        """إرسال كلمة المرور"""
        self.send({'@type': 'checkAuthenticationPassword', 'password': password})
        if not await self._wait_for_state('authorizationStateReady', timeout=20):
            raise Exception(f"Failed to login with password. Current state: {self.auth_state}")

    async def get_me(self) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المستخدم الحالي"""
        self.send({'@type': 'getMe'})
        async with asyncio.timeout(20):
            while not self.me:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event and event.get('@type') == 'user':
                    self.me = event
                    logger.info(f"User info received: {self.me.get('first_name')}")
                    return self.me
                elif event and event.get('@type') == 'error':
                    raise Exception(f"TDLib error on getMe: {event.get('message')}")
        return self.me

    async def close(self):
        """إغلاق العميل وتنظيف الموارد"""
        if self.loop_task:
            self.loop_task.cancel()
        try:
            self.send({'@type': 'close'})
            await asyncio.sleep(2)
        finally:
            tdjson.td_json_client_destroy(self.client)
            if self.db_directory and os.path.exists(self.db_directory):
                try:
                    await asyncio.to_thread(shutil.rmtree, self.db_directory)
                except Exception as e:
                    logger.error(f"Error removing temp directory: {e}")

    def save_session(self) -> Optional[str]:
        """حفظ الجلسة كمصفوفة بايت مشفرة"""
        if not self.db_directory:
            return None
        
        time.sleep(2)
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
            raise Exception("Session is invalid or expired.")
        
        await client.get_me()
        return client

    # ===== دوال مساعدة إضافية للتعامل مع المجموعات =====
    async def search_public_chat(self, username: str) -> Optional[Dict[str, Any]]:
        """البحث عن دردشة عامة"""
        self.send({'@type': 'searchPublicChat', 'username': username})
        async with asyncio.timeout(10):
            while True:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event and event.get('@type') == 'chat':
                    return event
                elif event and event.get('@type') == 'error':
                    return None
    
    async def get_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات دردشة"""
        self.send({'@type': 'getChat', 'chat_id': chat_id})
        async with asyncio.timeout(10):
            while True:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event and event.get('@type') == 'chat':
                    return event
                elif event and event.get('@type') == 'error':
                    return None
                    
    async def get_supergroup_full_info(self, supergroup_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المجموعة الكاملة"""
        self.send({'@type': 'getSupergroupFullInfo', 'supergroup_id': supergroup_id})
        async with asyncio.timeout(10):
            while True:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event and event.get('@type') == 'supergroupFullInfo':
                    return event
                elif event and event.get('@type') == 'error':
                    return None

    async def get_supergroup_members(self, supergroup_id: int, offset: int = 0, 
                                   limit: int = 200, 
                                   filter_dict: Dict[str, Any] = None) -> list:
        """الحصول على أعضاء المجموعة"""
        if filter_dict is None:
            filter_dict = {'@type': 'supergroupMembersFilterRecent'}
            
        self.send({
            '@type': 'getSupergroupMembers',
            'supergroup_id': supergroup_id,
            'filter': filter_dict,
            'offset': offset,
            'limit': limit
        })
        async with asyncio.timeout(20):
            while True:
                event = await asyncio.to_thread(self.receive, 1.0)
                if event and event.get('@type') == 'chatMembers':
                    return event['members']
                elif event and event.get('@type') == 'error':
                    logger.error(f"Error getting members: {event['message']}")
                    return []