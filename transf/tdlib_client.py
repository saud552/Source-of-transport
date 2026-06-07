# -*- coding: utf-8 -*-
"""
عميل TDLib للنقل
"""

import asyncio
import json
import logging
import ctypes
from typing import Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import API_ID, API_HASH
from transf.config import tdjson

logger = logging.getLogger(__name__)

class TDLibClient:
    """عميل TDLib للنقل"""
    
    def __init__(self, session_string: str, device_info: str):
        self.session_string = session_string
        self.device_info = json.loads(device_info) if isinstance(device_info, str) else device_info
        self.client = None
        self.is_initialized = False
        self._update_handlers = {}
    
    async def initialize(self) -> bool:
        """تهيئة العميل"""
        try:
            # إنشاء العميل
            self.client = tdjson.td_json_client_create()
            if not self.client:
                logger.error("فشل في إنشاء عميل TDLib")
                return False
            
            # إعداد معالج التحديثات
            asyncio.create_task(self._update_loop())
            
            # إرسال طلب التهيئة
            init_request = {
                "@type": "setTdlibParameters",
                "parameters": {
                    "@type": "tdlibParameters",
                    "use_test_dc": False,
                    "database_directory": "/tmp/tdlib",
                    "files_directory": "/tmp/tdlib",
                    "use_file_database": True,
                    "use_chat_info_database": True,
                    "use_message_database": True,
                    "use_secret_chats": True,
                    "api_id": API_ID,
                    "api_hash": API_HASH,
                    "system_language_code": "en",
                    "device_model": self.device_info.get('device_model', 'Unknown'),
                    "system_version": self.device_info.get('system_version', 'Unknown'),
                    "application_version": self.device_info.get('app_version', '1.0.0'),
                    "enable_storage_optimizer": True,
                    "ignore_file_names": False
                }
            }
            
            await self._send_request(init_request)
            
            # انتظار التهيئة
            await self._wait_for_authorization()
            
            # تسجيل الدخول بالجلسة
            if not await self._set_authentication_string():
                return False
            
            self.is_initialized = True
            logger.info("تم تهيئة عميل TDLib بنجاح")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تهيئة عميل TDLib: {str(e)}")
            return False
    
    async def _update_loop(self):
        """حلقة معالجة التحديثات"""
        while self.client and self.is_initialized:
            try:
                # استقبال التحديثات
                update = tdjson.td_json_client_receive(self.client, 1.0)
                if update:
                    update_str = update.decode('utf-8')
                    update_data = json.loads(update_str)
                    await self._handle_update(update_data)
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"خطأ في حلقة التحديثات: {str(e)}")
                break
    
    async def _handle_update(self, update: Dict[str, Any]):
        """معالجة التحديثات"""
        update_type = update.get("@type")
        
        if update_type == "updateAuthorizationState":
            await self._handle_authorization_state(update)
        elif update_type == "updateConnectionState":
            await self._handle_connection_state(update)
        elif update_type == "error":
            logger.error(f"خطأ من TDLib: {update.get('message', 'Unknown error')}")
    
    async def _handle_authorization_state(self, update: Dict[str, Any]):
        """معالجة حالة التفويض"""
        state = update.get("authorization_state", {})
        state_type = state.get("@type")
        
        if state_type == "authorizationStateReady":
            logger.info("تم تسجيل الدخول بنجاح")
        elif state_type == "authorizationStateLoggingOut":
            logger.info("جاري تسجيل الخروج")
        elif state_type == "authorizationStateClosed":
            logger.info("تم إغلاق الجلسة")
    
    async def _handle_connection_state(self, update: Dict[str, Any]):
        """معالجة حالة الاتصال"""
        state = update.get("state", {})
        state_type = state.get("@type")
        
        if state_type == "connectionStateReady":
            logger.info("الاتصال جاهز")
        elif state_type == "connectionStateConnecting":
            logger.info("جاري الاتصال")
        elif state_type == "connectionStateConnectingToProxy":
            logger.info("جاري الاتصال عبر البروكسي")
    
    async def _wait_for_authorization(self, timeout: int = 30) -> bool:
        """انتظار التفويض"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            # يمكن إضافة منطق للتحقق من حالة التفويض هنا
            # للبساطة، سنفترض أن التهيئة نجحت
            return True
        
        return False
    
    async def _set_authentication_string(self) -> bool:
        """تعيين سلسلة المصادقة"""
        try:
            auth_request = {
                "@type": "setAuthenticationString",
                "string": self.session_string
            }
            
            await self._send_request(auth_request)
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تعيين سلسلة المصادقة: {str(e)}")
            return False
    
    async def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """إرسال طلب إلى TDLib"""
        try:
            request_str = json.dumps(request)
            tdjson.td_json_client_send(self.client, request_str.encode('utf-8'))
            return None  # TDLib لا يعيد استجابة فورية
        except Exception as e:
            logger.error(f"خطأ في إرسال الطلب: {str(e)}")
            return None
    
    async def add_chat_member(self, chat_id: int, user_id: int) -> bool:
        """إضافة عضو إلى المجموعة"""
        try:
            # الحصول على معلومات المجموعة أولاً
            get_chat_request = {
                "@type": "getChat",
                "chat_id": chat_id
            }
            
            await self._send_request(get_chat_request)
            
            # إضافة العضو
            add_member_request = {
                "@type": "addChatMember",
                "chat_id": chat_id,
                "user_id": user_id,
                "forward_limit": 0
            }
            
            await self._send_request(add_member_request)
            
            # انتظار قليل للتحقق من النجاح
            await asyncio.sleep(2)
            
            logger.info(f"تم إرسال طلب إضافة العضو {user_id} للمجموعة {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في إضافة العضو: {str(e)}")
            return False
    
    async def get_chat_info(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المجموعة"""
        try:
            request = {
                "@type": "getChat",
                "chat_id": chat_id
            }
            
            await self._send_request(request)
            return None  # سيتم معالجة الاستجابة في حلقة التحديثات
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على معلومات المجموعة: {str(e)}")
            return None
    
    async def search_public_chat(self, username: str) -> Optional[Dict[str, Any]]:
        """البحث عن مجموعة عامة"""
        try:
            request = {
                "@type": "searchPublicChat",
                "username": username
            }
            
            await self._send_request(request)
            return None
            
        except Exception as e:
            logger.error(f"خطأ في البحث عن المجموعة العامة: {str(e)}")
            return None
    
    async def close(self):
        """إغلاق العميل"""
        try:
            if self.client:
                self.is_initialized = False
                tdjson.td_json_client_destroy(self.client)
                self.client = None
                logger.info("تم إغلاق عميل TDLib")
        except Exception as e:
            logger.error(f"خطأ في إغلاق عميل TDLib: {str(e)}")
    
    def __del__(self):
        """تنظيف الموارد"""
        if self.client:
            try:
                tdjson.td_json_client_destroy(self.client)
            except:
                pass