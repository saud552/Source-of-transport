# -*- coding: utf-8 -*-
"""
عميل TDLib لإدارة جلسات التليجرام في بوت التخزين
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

class StorageTDLibClient:
    """عميل TDLib لإدارة جلسات التليجرام في بوت التخزين"""
    
    def __init__(self, api_id: int, api_hash: str, phone: str, device_info: Dict[str, str]):
        self.client = tdjson.td_json_client_create()
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.device_info = device_info
        self.auth_state = None
        self.me = None
        self.db_directory = None
        self.session_data = None

    def send(self, query: Dict[str, Any]):
        """إرسال استعلام إلى TDLib"""
        query_str = json.dumps(query).encode('utf-8')
        tdjson.td_json_client_send(self.client, query_str)

    def receive(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """استقبال استجابة من TDLib"""
        result = tdjson.td_json_client_receive(self.client, timeout)
        if result:
            return json.loads(result.decode('utf-8'))
        return None

    def initialize(self):
        """تهيئة العميل"""
        self.db_directory = tempfile.mkdtemp()
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
            'enable_storage_optimizer': True,
            'platform': 'android',
            'application': {
                '@type': 'application',
                'name': self.device_info['app_version'].split()[0],
                'version': self.device_info['app_version'].split()[-1]
            },
            'use_test_dc': False,
            'use_file_database': True,
            'use_chat_info_database': True,
            'ignore_file_names': False,
            'connection_timeout': 30,
            'verbosity_level': 2
        }
        self.send(params)
        self.send({'@type': 'checkDatabaseEncryptionKey', 'encryption_key': ''})
        self.run(15.0)

    def run(self, timeout: float = 10.0):
        """استقبال التحديثات بفعالية أكبر مع مراعاة مهلة زمنية"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            event = self.receive(timeout=1.0)
            if event:
                logger.debug(f"حدث مستلم: {event.get('@type')}")
                if event.get('@type') == 'updateAuthorizationState':
                    self.auth_state = event['authorization_state']
                    logger.info(f"تم تحديث حالة المصادقة: {self.auth_state.get('@type')}")
                    return
                if event.get('@type') == 'authorizationStateReady':
                    return
        logger.warning("انتهت المهلة دون استلام تحديث حالة المصادقة")

    def send_phone_number(self):
        """إرسال رقم الهاتف"""
        self.send({
            '@type': 'setAuthenticationPhoneNumber',
            'phone_number': self.phone,
            'settings': {
                '@type': 'phoneNumberAuthenticationSettings',
                'allow_flash_call': False,
                'is_current_phone_number': False,
                'allow_sms_retriever_api': False
            }
        })
        self.run(20.0)

    def send_code(self, code: str):
        """إرسال رمز التحقق"""
        self.send({
            '@type': 'checkAuthenticationCode',
            'code': str(code)
        })
        self.run(20.0)

    def send_password(self, password: str):
        """إرسال كلمة المرور"""
        self.send({
            '@type': 'checkAuthenticationPassword',
            'password': password
        })
        self.run(20.0)

    def get_me(self) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المستخدم الحالي"""
        self.send({'@type': 'getMe'})
        start_time = time.time()
        while time.time() - start_time < 60:
            event = self.receive(timeout=5.0)
            if event:
                if event.get('@type') == 'user':
                    self.me = event
                    return self.me
                if event.get('@type') == 'error':
                    raise Exception(event.get('message', 'Unknown error'))
        raise TimeoutError("انتهت المهلة دون استلام معلومات المستخدم")

    async def get_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المجموعة"""
        try:
            self.send({
                '@type': 'getChat',
                'chat_id': chat_id
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'chat':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في الحصول على المجموعة: {event.get('message')}")
                        return None
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون استلام معلومات المجموعة")
            return None
            
        except Exception as e:
            logger.error(f"خطأ في get_chat: {str(e)}")
            return None

    async def get_chat_full_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المجموعة الكاملة"""
        try:
            self.send({
                '@type': 'getSupergroupFullInfo',
                'supergroup_id': chat_id
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'supergroupFullInfo':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في الحصول على معلومات المجموعة الكاملة: {event.get('message')}")
                        return None
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون استلام معلومات المجموعة الكاملة")
            return None
            
        except Exception as e:
            logger.error(f"خطأ في get_chat_full_info: {str(e)}")
            return None

    async def search_public_chat(self, username: str) -> Optional[Dict[str, Any]]:
        """البحث عن مجموعة عامة بالاسم"""
        try:
            self.send({
                '@type': 'searchPublicChat',
                'username': username
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'chat':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في البحث عن المجموعة: {event.get('message')}")
                        return None
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون العثور على المجموعة")
            return None
            
        except Exception as e:
            logger.error(f"خطأ في search_public_chat: {str(e)}")
            return None

    async def get_chat_members(self, chat_id: int, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """الحصول على أعضاء المجموعة"""
        try:
            self.send({
                '@type': 'getChatMembers',
                'chat_id': chat_id,
                'filter': {
                    '@type': 'chatMembersFilterRecent'
                },
                'limit': limit,
                'offset': offset
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'chatMembers':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في الحصول على أعضاء المجموعة: {event.get('message')}")
                        return {'members': []}
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون استلام أعضاء المجموعة")
            return {'members': []}
            
        except Exception as e:
            logger.error(f"خطأ في get_chat_members: {str(e)}")
            return {'members': []}

    async def get_chat_history(self, chat_id: int, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """الحصول على تاريخ رسائل المجموعة"""
        try:
            self.send({
                '@type': 'getChatHistory',
                'chat_id': chat_id,
                'from_message_id': 0,
                'offset': offset,
                'limit': limit,
                'only_local': False
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'messages':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في الحصول على تاريخ الرسائل: {event.get('message')}")
                        return {'messages': []}
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون استلام تاريخ الرسائل")
            return {'messages': []}
            
        except Exception as e:
            logger.error(f"خطأ في get_chat_history: {str(e)}")
            return {'messages': []}

    async def get_message_senders(self, chat_id: int, message_ids: list) -> Dict[str, Any]:
        """الحصول على مرسلي رسائل محددة"""
        try:
            self.send({
                '@type': 'getMessageSenders',
                'chat_id': chat_id,
                'message_ids': message_ids
            })
            
            start_time = time.time()
            while time.time() - start_time < 30:
                event = self.receive(timeout=2.0)
                if event:
                    if event.get('@type') == 'messageSenders':
                        return event
                    if event.get('@type') == 'error':
                        logger.error(f"خطأ في الحصول على مرسلي الرسائل: {event.get('message')}")
                        return {'senders': []}
                await asyncio.sleep(0.1)
            
            logger.warning("انتهت المهلة دون استلام مرسلي الرسائل")
            return {'senders': []}
            
        except Exception as e:
            logger.error(f"خطأ في get_message_senders: {str(e)}")
            return {'senders': []}

    def close(self):
        """إغلاق العميل وتنظيف الموارد"""
        try:
            self.send({'@type': 'close'})
            time.sleep(2)
        finally:
            tdjson.td_json_client_destroy(self.client)
            try:
                if self.db_directory and os.path.exists(self.db_directory):
                    shutil.rmtree(self.db_directory)
            except Exception as e:
                logger.error(f"خطأ في حذف الدليل المؤقت: {str(e)}")
    
    def save_session(self) -> Optional[str]:
        """حفظ جلسة TDLib كمصفوفة بايت مشفرة"""
        if not self.db_directory:
            logger.error("لا يوجد دليل قاعدة بيانات لحفظ الجلسة")
            return None
            
        time.sleep(2)
        buffer = io.BytesIO()
        
        try:
            exclude_dirs = ['emoji', 'temp', 'logs']
            exclude_files = ['log.txt', 'cache.db', 'temp.db']
            
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                for root, dirs, files in os.walk(self.db_directory):
                    dirs[:] = [d for d in dirs if d not in exclude_dirs]
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        if os.path.getsize(file_path) > 20 * 1024 * 1024:  # 20MB
                            logger.warning(f"تخطي ملف كبير: {file_path}")
                            continue
                        
                        if file in exclude_files:
                            continue
                        
                        arcname = os.path.relpath(file_path, self.db_directory)
                        zipf.write(file_path, arcname)
                        
            buffer.seek(0)
            session_bytes = buffer.getvalue()
            session_base64 = base64.b64encode(session_bytes).decode('utf-8')
            
            return session_base64
        
        except Exception as e:
            logger.error(f"خطأ في حفظ الجلسة: {str(e)}", exc_info=True)
            return None
        finally:
            buffer.close()

    @staticmethod
    def load_session(session_str: str, api_id: int, api_hash: str, device_info: Dict[str, str]):
        """تحميل جلسة من سلسلة مشفرة"""
        if isinstance(device_info, str):
            try:
                device_info = json.loads(device_info)
            except json.JSONDecodeError:
                logger.error("فشل تحليل JSON لمعلومات الجهاز")
                device_info = get_random_device()
        
        try:
            session_bytes = base64.b64decode(session_str.encode('utf-8'))
        except Exception as e:
            logger.error(f"خطأ في فك ترميز الجلسة: {str(e)}")
            raise e
        
        buffer = io.BytesIO(session_bytes)
        db_directory = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(buffer, 'r') as zipf:
                zipf.extractall(db_directory)
            
            client = StorageTDLibClient(api_id, api_hash, "", device_info)
            client.db_directory = db_directory
            client.initialize()
            
            if not client.get_me():
                raise ValueError("فشل تحميل معلومات المستخدم")
                
            return client
        except Exception as e:
            logger.error(f"خطأ في تحميل الجلسة: {str(e)}", exc_info=True)
            try:
                shutil.rmtree(db_directory)
            except Exception as e2:
                logger.error(f"خطأ في تنظيف الدليل: {str(e2)}")
            raise e
        finally:
            buffer.close()

def get_random_device() -> Dict[str, str]:
    """اختيار جهاز عشوائي - دالة مؤقتة للتوافق مع الكود القديم"""
    from .utils import StorageUtils
    return StorageUtils.get_random_device()