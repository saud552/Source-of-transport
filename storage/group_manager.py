# -*- coding: utf-8 -*-
"""
مدير المجموعات - إدارة عمليات تخزين الأعضاء (النسخة المحسنة)
"""

import asyncio
import logging
import time
import sqlite3
import json
import contextlib
import threading
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime, timedelta
import pytz
from urllib.parse import urlparse
import re
from collections import defaultdict

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from .tdlib_client import StorageTDLibClient
from .database import StorageDatabaseManager
from .decorators import owner_only
from .config import API_ID, API_HASH, ACCOUNTS_DB_PATH
from .utils import StorageUtils

logger = logging.getLogger(__name__)

class TDLibClientPool:
    """تجمع عملاء TDLib لإعادة الاستخدام وتحسين الأداء"""
    
    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self.active_clients: Dict[str, List[StorageTDLibClient]] = {}
        self.available_clients: asyncio.Queue = asyncio.Queue()
        self.creation_count = 0
        self._lock = asyncio.Lock()
        
    async def get_client(self, account_id: str) -> Optional[StorageTDLibClient]:
        """الحصول على عميل من التجمع"""
        async with self._lock:
            try:
                # محاولة إعادة استخدام عميل موجود
                while not self.available_clients.empty():
                    try:
                        client = self.available_clients.get_nowait()
                        if await self.validate_client(client):
                            if account_id not in self.active_clients:
                                self.active_clients[account_id] = []
                            self.active_clients[account_id].append(client)
                            logger.debug(f"♻️ إعادة استخدام عميل موجود للحساب {account_id}")
                            return client
                        else:
                            await self.close_client(client)
                    except asyncio.QueueEmpty:
                        break
                
                # إنشاء عميل جديد إذا لم نتجاوز الحد الأقصى
                current_count = sum(len(clients) for clients in self.active_clients.values())
                if current_count < self.max_size:
                    client = await self.create_new_client(account_id)
                    if client:
                        if account_id not in self.active_clients:
                            self.active_clients[account_id] = []
                        self.active_clients[account_id].append(client)
                        self.creation_count += 1
                        logger.debug(f"🆕 إنشاء عميل جديد للحساب {account_id} (الإجمالي: {self.creation_count})")
                        return client
                
                # الانتظار حتى يتوفر عميل
                logger.debug(f"⏳ انتظار عميل متاح للحساب {account_id}")
                try:
                    client = await asyncio.wait_for(self.available_clients.get(), timeout=30.0)
                    if client and await self.validate_client(client):
                        if account_id not in self.active_clients:
                            self.active_clients[account_id] = []
                        self.active_clients[account_id].append(client)
                        return client
                except asyncio.TimeoutError:
                    logger.error(f"⏰ انتهت مهلة الانتظار للحصول على عميل للحساب {account_id}")
                
                return None
                
            except Exception as e:
                logger.error(f"❌ خطأ في الحصول على عميل من التجمع: {str(e)}")
                return None
    
    async def release_client(self, account_id: str, client: StorageTDLibClient):
        """إعادة العميل إلى التجمع"""
        async with self._lock:
            try:
                if account_id in self.active_clients and client in self.active_clients[account_id]:
                    self.active_clients[account_id].remove(client)
                
                if await self.validate_client(client):
                    await self.available_clients.put(client)
                    logger.debug(f"📥 إعادة عميل إلى التجمع للحساب {account_id}")
                else:
                    await self.close_client(client)
            except Exception as e:
                logger.error(f"❌ خطأ في إعادة العميل: {str(e)}")
                await self.close_client(client)
    
    async def validate_client(self, client: StorageTDLibClient) -> bool:
        """التحقق من صلاحية العميل"""
        try:
            # إرسال طلب بسيط للتحقق من اتصال العميل
            client.send({'@type': 'getMe'})
            
            # انتظار الرد
            start_time = time.time()
            while time.time() - start_time < 5:
                event = client.receive(timeout=0.5)
                if event and event.get('@type') == 'user':
                    return True
                await asyncio.sleep(0.1)
            
            return False
        except Exception:
            return False
    
    async def create_new_client(self, account_id: str) -> Optional[StorageTDLibClient]:
        """إنشاء عميل جديد"""
        try:
            # جلب بيانات الحساب
            with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_str, phone, device_info
                    FROM accounts
                    WHERE id = ?
                """, (account_id,))
                account_data = cursor.fetchone()

            if not account_data:
                logger.error(f"❌ لا يوجد حساب بهذا المعرف: {account_id}")
                return None

            session_str, phone, device_info_str = account_data

            # تحليل معلومات الجهاز
            device_info = (
                json.loads(device_info_str)
                if device_info_str
                else StorageUtils.get_random_device()
            )

            # تحميل الجلسة
            client = StorageTDLibClient.load_session(
                session_str=session_str,
                api_id=API_ID,
                api_hash=API_HASH,
                device_info=device_info
            )

            # تهيئة العميل
            client.initialize()

            # انتظار حتى يصبح العميل جاهزاً
            start_time = time.time()
            while time.time() - start_time < 15:
                event = client.receive(timeout=0.5)
                if event and event.get('@type') == 'updateAuthorizationState':
                    auth_state = event['authorization_state']['@type']
                    if auth_state == 'authorizationStateReady':
                        logger.info(f"✅ عميل جاهز للحساب {account_id}")
                        return client
                    elif auth_state == 'authorizationStateWaitPhoneNumber':
                        logger.warning(f"⚠️ جلسة منتهية للحساب {account_id}")
                        break
                await asyncio.sleep(0.05)

            return None

        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء عميل جديد: {str(e)}")
            return None
    
    async def close_client(self, client: StorageTDLibClient):
        """إغلاق العميل بشكل آمن"""
        try:
            client.close()
        except Exception as e:
            logger.error(f"❌ خطأ في إغلاق العميل: {str(e)}")
    
    def cleanup(self):
        """تنظيف جميع العملاء"""
        try:
            while not self.available_clients.empty():
                try:
                    client = self.available_clients.get_nowait()
                    self.close_client(client)
                except asyncio.QueueEmpty:
                    break
            
            for account_id, clients in list(self.active_clients.items()):
                for client in clients:
                    self.close_client(client)
                self.active_clients[account_id].clear()
                
            logger.info("🧹 تم تنظيف تجمع العملاء")
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف التجمع: {str(e)}")

class RateLimiter:
    """محدد معدل الطلبات"""
    
    def __init__(self, max_requests: int = 50, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """التحقق من إمكانية إرسال طلب جديد"""
        async with self._lock:
            now = time.time()
            
            # إزالة الطلبات القديمة
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                # حساب وقت الانتظار المطلوب
                oldest_request = self.requests[0]
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    logger.debug(f"⏳ معدل الطلبات ممتلئ، انتظار {wait_time:.1f} ثانية")
                    await asyncio.sleep(wait_time)
                    now = time.time()
            
            # إضافة الطلب الجديد
            self.requests.append(now)
            return True

class PerformanceMonitor:
    """مراقب أداء النظام"""
    
    def __init__(self):
        self.metrics = {
            'storage_operations': 0,
            'successful_storages': 0,
            'failed_storages': 0,
            'average_processing_time': 0,
            'total_members_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.operation_times = []
        self.start_time = time.time()
        self._lock = threading.Lock()
        
    def record_operation(self, operation_type: str, duration: float, success: bool, items_processed: int = 0):
        """تسجيل عملية وأدائها"""
        with self._lock:
            self.metrics['storage_operations'] += 1
            if success:
                self.metrics['successful_storages'] += 1
                self.metrics['total_members_processed'] += items_processed
            else:
                self.metrics['failed_storages'] += 1
                
            self.operation_times.append(duration)
            
            # تحديث متوسط وقت المعالجة
            if self.operation_times:
                self.metrics['average_processing_time'] = sum(self.operation_times) / len(self.operation_times)
    
    def record_cache_hit(self):
        """تسجيل ضربة cache"""
        with self._lock:
            self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        """تسجيل فشل cache"""
        with self._lock:
            self.metrics['cache_misses'] += 1
    
    def get_performance_report(self) -> Dict[str, Any]:
        """تقرير أداء مفصل"""
        with self._lock:
            uptime = time.time() - self.start_time
            success_rate = (self.metrics['successful_storages'] / self.metrics['storage_operations'] * 100) if self.metrics['storage_operations'] > 0 else 0
            
            cache_hits = self.metrics['cache_hits']
            cache_misses = self.metrics['cache_misses']
            cache_total = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0
            
            return {
                'uptime_seconds': uptime,
                'total_operations': self.metrics['storage_operations'],
                'success_rate_percent': success_rate,
                'average_processing_time_seconds': self.metrics['average_processing_time'],
                'total_members_processed': self.metrics['total_members_processed'],
                'operations_per_second': self.metrics['storage_operations'] / uptime if uptime > 0 else 0,
                'members_per_second': self.metrics['total_members_processed'] / uptime if uptime > 0 else 0,
                'cache_hit_rate_percent': cache_hit_rate,
                'cache_hits': cache_hits,
                'cache_misses': cache_misses
            }

class MemoryManager:
    """مدير ذاكرة متقدم"""
    
    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_mb = max_memory_mb
        self.cache = {}
        self.cache_size = 0
        self.access_count = defaultdict(int)
        self._lock = threading.Lock()
        
    def cache_get(self, key: str) -> Any:
        """استرجاع عنصر من الذاكرة المؤقتة"""
        with self._lock:
            if key in self.cache:
                self.access_count[key] += 1
                return self.cache[key]
            return None
    
    def cache_set(self, key: str, value: Any, size_mb: float = 0.1):
        """تخزين عنصر في الذاكرة المؤقتة"""
        with self._lock:
            # التحقق من حدود الذاكرة
            if self.cache_size + size_mb > self.max_memory_mb:
                self._evict_least_used()
            
            self.cache[key] = value
            self.cache_size += size_mb
            self.access_count[key] = 1
    
    def _evict_least_used(self):
        """إزالة العناصر الأقل استخداماً"""
        if not self.cache:
            return
            
        # العثور على العناصر الأقل استخداماً
        min_access = min(self.access_count.values())
        keys_to_remove = [k for k, v in self.access_count.items() if v == min_access]
        
        # إزالة بعض العناصر
        for key in keys_to_remove[:5]:  # إزالة 5 عناصر كحد أقصى
            if key in self.cache:
                del self.cache[key]
                del self.access_count[key]
    
    def clear_cache(self):
        """مسح الذاكرة المؤقتة"""
        with self._lock:
            self.cache.clear()
            self.access_count.clear()
            self.cache_size = 0

class ParallelProcessor:
    """معالج متوازي لعمليات التخزين"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        
    async def process_members_batch(self, members_batch: List[Dict], storage_group_id: str, db_manager: StorageDatabaseManager) -> int:
        """معالجة دفعة من الأعضاء بشكل متوازي"""
        processed_count = 0
        batch_size = len(members_batch)
        
        if batch_size == 0:
            return 0
        
        # تقسيم الدفعة إلى مجموعات أصغر
        chunk_size = max(1, batch_size // self.max_workers)
        chunks = [members_batch[i:i + chunk_size] for i in range(0, batch_size, chunk_size)]
        
        # معالجة المجموعات بشكل متوازي
        tasks = []
        for chunk in chunks:
            task = asyncio.create_task(
                self._process_chunk(chunk, storage_group_id, db_manager)
            )
            tasks.append(task)
        
        # جمع النتائج
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, int):
                processed_count += result
        
        return processed_count
    
    async def _process_chunk(self, chunk: List[Dict], storage_group_id: str, db_manager: StorageDatabaseManager) -> int:
        """معالجة مجموعة فرعية من الأعضاء"""
        processed = 0
        for member in chunk:
            try:
                if db_manager.store_member(storage_group_id, member):
                    processed += 1
            except Exception as e:
                logger.error(f"خطأ في معالجة العضو: {str(e)}")
                continue
        return processed

class GroupManager:
    """مدير المجموعات لتخزين الأعضاء (النسخة المحسنة)"""
    
    def __init__(self, db_manager: StorageDatabaseManager):
        self.db_manager = db_manager
        self.active_tasks = {}
        self.pause_events = {}
        self.cancel_events = {}
        self.semaphore = asyncio.Semaphore(3)  # حد أقصى 3 مهام متزامنة
        self.client_pool = TDLibClientPool(max_size=5)  # تجميع العملاء
        self.rate_limiter = RateLimiter(max_requests=50, time_window=60)  # 50 طلب/دقيقة
        self.performance_monitor = PerformanceMonitor()
        self.memory_manager = MemoryManager(max_memory_mb=500)
        self.parallel_processor = ParallelProcessor(max_workers=4)
        
        # cache لمعلومات المستخدمين
        self.user_cache = {}
        self.last_cache_cleanup = time.time()
        self.cache_lock = asyncio.Lock()
        
    def log_performance_metrics(self, operation: str, start_time: float, items_processed: int = 0):
        """تسجيل مقاييس الأداء"""
        duration = time.time() - start_time
        items_per_second = items_processed / duration if duration > 0 else 0
        
        logger.info(
            f"📊 مقاييس الأداء - {operation}: "
            f"الوقت: {duration:.2f}ث, "
            f"العناصر: {items_processed}, "
            f"السرعة: {items_per_second:.2f} عنصر/ث"
        )

    async def get_group_info(self, group_input: str) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المجموعة الحقيقية باستخدام TDLib"""
        client = None
        start_time = time.time()
        try:
            logger.info(f"🚀 بدء جلب معلومات المجموعة: {group_input}")
            
            # الحصول على حساب تخزين
            with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM categories WHERE name = ?", ("حسابات التخزين",))
                storage_category = cursor.fetchone()
                
                if not storage_category:
                    logger.error("❌ فئة التخزين غير موجودة")
                    return None
                
                cursor.execute("SELECT id FROM accounts WHERE category_id = ? ORDER BY RANDOM() LIMIT 1", (storage_category[0],))
                account = cursor.fetchone()
                
                if not account:
                    logger.error("❌ لا توجد حسابات تخزين متاحة")
                    return None
                
                account_id = account[0]
                logger.info(f"👤 استخدام حساب التخزين: {account_id}")
            
            # الحصول على عميل TDLib من التجمع
            async with self.get_client_context(account_id) as client:
                if not client:
                    logger.error("❌ فشل في الحصول على عميل")
                    return None
                
                # تحويل المدخل إلى معرف المجموعة
                chat_id = await self.resolve_group_identifier(client, group_input)
                
                if not chat_id:
                    logger.error(f"❌ تعذر تحويل المدخل: {group_input}")
                    return None
                
                logger.info(f"🆔 معرف المجموعة: {chat_id}")
                
                # الحصول على معلومات المجموعة
                chat = await client.get_chat(chat_id)
                if not chat:
                    logger.error("❌ فشل جلب معلومات المجموعة")
                    return None
                
                # الحصول على معلومات المجموعة الكاملة
                full_info = await client.get_chat_full_info(chat_id)
                if not full_info:
                    logger.error("❌ فشل جلب معلومات المجموعة الكاملة")
                    return None
                
                total_members = full_info.get('member_count', 0)
                
                group_info = {
                    'id': chat['id'],
                    'title': chat['title'],
                    'username': chat.get('username', ''),
                    'total_members': total_members,
                    'is_private': chat.get('type', {}).get('@type') in ['chatTypePrivate', 'chatTypeSecret']
                }
                
                self.log_performance_metrics("جلب معلومات المجموعة", start_time, 1)
                self.performance_monitor.record_operation("get_group_info", time.time() - start_time, True, 1)
                logger.info(f"✅ معلومات المجموعة: {group_info}")
                return group_info
            
        except Exception as e:
            duration = time.time() - start_time
            self.performance_monitor.record_operation("get_group_info", duration, False)
            logger.error(f"🔥 خطأ في الحصول على معلومات المجموعة: {str(e)}", exc_info=True)
            return None

    @contextlib.asynccontextmanager
    async def get_client_context(self, account_id: str) -> AsyncGenerator[Optional[StorageTDLibClient], None]:
        """إدارة سياق العميل مع التجميع"""
        client = None
        try:
            client = await self.client_pool.get_client(account_id)
            yield client
        except Exception as e:
            logger.error(f"❌ خطأ في سياق العميل: {str(e)}")
            yield None
        finally:
            if client:
                await self.client_pool.release_client(account_id, client)

    async def resolve_group_identifier(self, client: StorageTDLibClient, identifier: str) -> Optional[int]:
        """تحويل معرف المجموعة أو الرابط إلى chat_id"""
        try:
            logger.info(f"🔍 بدء تحويل المعرف: {identifier}")
            
            # إذا كان المعرف رقميًا
            if isinstance(identifier, int):
                logger.info(f"🆔 المعرف رقمي: {identifier}")
                return identifier
            
            # تنظيف المدخل
            clean_identifier = identifier.strip()
            
            # معالجة الروابط
            if clean_identifier.startswith('https://t.me/'):
                path = urlparse(clean_identifier).path
                clean_identifier = path.split('/')[-1] if path else clean_identifier
                logger.info(f"🔗 رابط المجموعة: {clean_identifier}")
            
            # إزالة الإشارة @
            if clean_identifier.startswith('@'):
                clean_identifier = clean_identifier[1:]
                logger.info(f"📛 معرف المجموعة: {clean_identifier}")
            
            # إزالة الرموز غير المرغوبة
            clean_identifier = re.sub(r'[^\w\d]', '', clean_identifier)
            
            if not clean_identifier:
                logger.warning("⚠️ المعرف فارغ بعد التنظيف")
                return None
            
            logger.info(f"🧹 المعرف النظيف: {clean_identifier}")
            
            # البحث عن المجموعة
            chat = await client.search_public_chat(clean_identifier)
            
            if chat and chat.get('@type') == 'chat':
                logger.info(f"✅ تم العثور على المجموعة: {chat.get('title')} (ID: {chat['id']})")
                return chat['id']
            
            logger.warning(f"⚠️ لم يتم العثور على دردشة للمعرف: {clean_identifier}")
            return None
        
        except Exception as e:
            logger.error(f"🔥 خطأ في تحويل معرف المجموعة: {str(e)}", exc_info=True)
            return None

    async def get_members_from_messages_batch(self, client: StorageTDLibClient, group_id: int, 
                                            batch_size: int = 1000, 
                                            last_seen_months: int = 0, 
                                            scan_months: int = 0) -> List[Dict[str, Any]]:
        """نسخة محسنة من دالة مسح الرسائل بالدفعات"""
        members = {}
        total_processed = 0
        max_messages = 10000  # حد أقصى للرسائل
        start_time = time.time()
        
        try:
            # تطبيق حدود المعدل
            await self.rate_limiter.acquire()
            
            # حساب تواريخ الفلترة
            now = datetime.now(pytz.utc)
            last_seen_date = (now - timedelta(days=last_seen_months*30)).timestamp() if last_seen_months > 0 else 0
            scan_date = (now - timedelta(days=scan_months*30)).timestamp() if scan_months > 0 else 0
            
            # الحصول على الرسائل بالدفعات
            from_message_id = 0
            processed_count = 0
            
            while processed_count < max_messages:
                # التحقق من وجود المزيد من الرسائل
                if processed_count > 0 and from_message_id == 0:
                    break
                    
                # جلب دفعة من الرسائل
                history_result = await client.get_chat_history(
                    chat_id=group_id,
                    from_message_id=from_message_id,
                    limit=batch_size
                )
                
                messages = history_result.get('messages', [])
                if not messages:
                    break
                    
                # معالجة الدفعة
                batch_members = await self.process_message_batch(
                    client, group_id, messages, last_seen_date, scan_date
                )
                
                # دمج النتائج
                for member_id, member_info in batch_members.items():
                    if member_id not in members:
                        members[member_id] = member_info
                    else:
                        members[member_id]['message_count'] += member_info['message_count']
                
                processed_count += len(messages)
                from_message_id = messages[-1]['id'] if messages else 0
                
                # تحديث التقدم
                if processed_count % 500 == 0:
                    logger.info(f"📊 معالجة {processed_count} رسالة...")
                
                # إضافة تأخير لتجنب rate limits
                await asyncio.sleep(0.1)
                
                # التحقق من وجود المزيد من الرسائل
                if len(messages) < batch_size:
                    break
            
            self.log_performance_metrics("مسح الرسائل بالدفعات", start_time, processed_count)
            self.performance_monitor.record_operation("get_members_from_messages_batch", time.time() - start_time, True, processed_count)
            logger.info(f"✅ تم معالجة {processed_count} رسالة والعثور على {len(members)} عضو")
            return list(members.values())
            
        except Exception as e:
            duration = time.time() - start_time
            self.performance_monitor.record_operation("get_members_from_messages_batch", duration, False)
            logger.error(f"❌ خطأ في المسح بالدفعات: {str(e)}", exc_info=True)
            return list(members.values())

    async def process_message_batch(self, client, group_id, messages, last_seen_date, scan_date):
        """معالجة دفعة من الرسائل"""
        batch_members = {}
        message_ids = []
        
        # تجميع معرفات الرسائل
        for message in messages:
            if (message.get('@type') == 'message' and 
                message.get('id') and 
                (scan_date == 0 or message.get('date', 0) >= scan_date)):
                message_ids.append(message['id'])
        
        if not message_ids:
            return batch_members
        
        # تقسيم message_ids إلى دفعات صغيرة لتجنب حدود TDLib
        chunk_size = 100
        message_chunks = [message_ids[i:i + chunk_size] for i in range(0, len(message_ids), chunk_size)]
        
        for chunk in message_chunks:
            try:
                # تطبيق حدود المعدل لكل دفعة
                await self.rate_limiter.acquire()
                
                # الحصول على المرسلين في دفعة واحدة
                senders_result = await client.get_message_senders(
                    chat_id=group_id,
                    message_ids=chunk
                )
                
                # معالجة المرسلين
                for sender in senders_result.get('senders', []):
                    if sender.get('@type') == 'messageSenderUser':
                        user_id = sender.get('user_id')
                        if user_id and user_id not in batch_members:
                            user_info = await self.get_user_info_fast(client, user_id)
                            if user_info and self.filter_user_by_last_seen(user_info, last_seen_date):
                                batch_members[user_id] = user_info
            
            except Exception as e:
                logger.error(f"❌ خطأ في معالجة الدفعة: {str(e)}")
                continue
        
        return batch_members

    async def get_user_info_fast(self, client: StorageTDLibClient, user_id: int) -> Optional[Dict[str, Any]]:
        """نسخة سريعة من دالة جلب معلومات المستخدم مع cache"""
        try:
            # تنظيف cache كل 5 دقائق
            current_time = time.time()
            if current_time - self.last_cache_cleanup > 300:
                async with self.cache_lock:
                    self.user_cache.clear()
                    self.last_cache_cleanup = current_time
            
            # استخدام cache محلي
            cache_key = f"user_{user_id}"
            
            # التحقق من cache أولاً
            cached_user = self.memory_manager.cache_get(cache_key)
            if cached_user:
                self.performance_monitor.record_cache_hit()
                return cached_user
            
            self.performance_monitor.record_cache_miss()
            
            client.send({
                '@type': 'getUser',
                'user_id': user_id
            })
            
            # وقت انتظار أقصر
            start_time = time.time()
            while time.time() - start_time < 3:  # 3 ثواني فقط
                event = client.receive(timeout=0.1)
                if event and event.get('@type') == 'user':
                    user_info = {
                        'id': event.get('id'),
                        'username': event.get('username', ''),
                        'first_name': event.get('first_name', ''),
                        'last_name': event.get('last_name', ''),
                        'phone': event.get('phone_number', ''),
                        'last_seen': datetime.fromtimestamp(event.get('last_online_date', 0)) if event.get('last_online_date') else None,
                        'is_bot': 1 if event.get('type', {}).get('@type') == 'userTypeBot' else 0,
                        'is_premium': 1 if event.get('is_premium', False) else 0,
                        'message_count': 1
                    }
                    
                    # تخزين في cache
                    self.memory_manager.cache_set(cache_key, user_info, size_mb=0.01)
                    
                    return user_info
                
                await asyncio.sleep(0.05)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في get_user_info_fast: {str(e)}")
            return None

    def filter_user_by_last_seen(self, user_info: Dict[str, Any], last_seen_date: float) -> bool:
        """فلترة سريعة للمستخدمين حسب آخر ظهور"""
        if last_seen_date == 0:
            return True
        
        last_seen = user_info.get('last_seen')
        if not last_seen:
            return False
        
        return last_seen.timestamp() >= last_seen_date

    def should_cancel(self, storage_group_id: str) -> bool:
        """التحقق من طلب إلغاء المهمة"""
        return (storage_group_id in self.cancel_events and 
                self.cancel_events[storage_group_id].is_set())

    def should_pause(self, storage_group_id: str) -> bool:
        """التحقق من طلب إيقاف المهمة مؤقتاً"""
        return (storage_group_id in self.pause_events and 
                self.pause_events[storage_group_id].is_set())

    async def start_hidden_storage(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 group_info: Dict[str, Any], account_ids: List[str], 
                                 category_name: str, months: int, last_seen: int):
        """بدء تخزين الأعضاء من مجموعة مخفية"""
        try:
            # إنشاء أو استرجاع الفئة
            category_id = self.db_manager.get_or_create_storage_category(category_name)
            
            # إنشاء معرف فريد لمجموعة التخزين
            storage_group_id = self.db_manager.create_storage_group(
                category_id=category_id,
                group_id=group_info['id'],
                title=group_info['title'],
                username=group_info.get('username', ''),
                total_members=group_info['total_members'],
                storage_type='hidden',
                scan_months=months,
                last_seen_months=last_seen
            )
            
            # إعداد مفاتيح التحكم في المهمة
            self.pause_events[storage_group_id] = asyncio.Event()
            self.cancel_events[storage_group_id] = asyncio.Event()
            
            # بدء المهمة في الخلفية
            task = asyncio.create_task(
                self.run_optimized_storage_task(
                    context,
                    update.effective_chat.id,
                    storage_group_id,
                    group_info,
                    account_ids,
                    months,
                    last_seen
                )
            )
            self.active_tasks[storage_group_id] = task
            
            # إرسال رسالة بدء العملية
            keyboard = [
                [
                    InlineKeyboardButton("⏸ إيقاف مؤقت", callback_data=f"pause_{storage_group_id}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{storage_group_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⏳ بدء تخزين الأعضاء من {group_info['title']} ...\n"
                     f"🔍 عدد الحسابات المستخدمة: {len(account_ids)}\n"
                     f"📅 فترة النشاط: {last_seen} أشهر\n"
                     f"📅 فترة الانضمام: {months} أشهر\n"
                     f"📊 إجمالي الأعضاء: {group_info['total_members']}",
                reply_markup=reply_markup
            )
            
            context.user_data['progress_message_id'] = message.message_id
            
        except Exception as e:
            logger.error(f"❌ خطأ في بدء تخزين الأعضاء المخفيين: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ حدث خطأ أثناء بدء التخزين: {str(e)}"
            )

    async def run_optimized_storage_task(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                                       storage_group_id: str, group_info: Dict[str, Any], 
                                       account_ids: List[str], months: int, last_seen: int):
        """تشغيل عملية التخزين المحسنة"""
        async with self.semaphore:  # التحكم في التزامن
            total_stored = 0
            failed_accounts = []
            start_time = time.time()
            
            try:
                # توزيع العمل على الحسابات بشكل متوازي
                accounts_per_batch = max(1, len(account_ids) // 2)
                account_batches = [account_ids[i:i + accounts_per_batch] for i in range(0, len(account_ids), accounts_per_batch)]
                
                for batch in account_batches:
                    if self.should_cancel(storage_group_id):
                        await self.finalize_storage(context, chat_id, storage_group_id, "canceled", total_stored)
                        return
                        
                    # معالجة الدفعة بشكل متوازي
                    batch_results = await asyncio.gather(
                        *[self._process_account_storage(account_id, group_info, months, last_seen, storage_group_id) 
                          for account_id in batch],
                        return_exceptions=True
                    )
                    
                    for account_id, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            logger.error(f"❌ فشل الحساب {account_id}: {str(result)}")
                            failed_accounts.append(account_id)
                        elif isinstance(result, int):
                            total_stored += result
                            logger.info(f"✅ الحساب {account_id} خزن {result} عضو")
                
                # تحديث الحالة النهائية
                status = "completed" if len(failed_accounts) < len(account_ids) else "partial"
                await self.finalize_storage(context, chat_id, storage_group_id, status, total_stored, failed_accounts)
                
                # تسجيل مقاييس الأداء
                duration = time.time() - start_time
                self.performance_monitor.record_operation("storage_task", duration, True, total_stored)
                self.log_performance_metrics("مهمة التخزين الكاملة", start_time, total_stored)
                
            except Exception as e:
                duration = time.time() - start_time
                self.performance_monitor.record_operation("storage_task", duration, False)
                logger.error(f"❌ خطأ في مهمة التخزين: {str(e)}", exc_info=True)
                await self.finalize_storage(context, chat_id, storage_group_id, "failed", total_stored, failed_accounts)
            finally:
                # تنظيف الموارد
                if storage_group_id in self.active_tasks:
                    del self.active_tasks[storage_group_id]
                if storage_group_id in self.pause_events:
                    del self.pause_events[storage_group_id]
                if storage_group_id in self.cancel_events:
                    del self.cancel_events[storage_group_id]

    async def _process_account_storage(self, account_id: str, group_info: Dict[str, Any], 
                                     months: int, last_seen: int, storage_group_id: str) -> int:
        """معالجة تخزين الأعضاء لحساب معين"""
        try:
            async with self.get_client_context(account_id) as client:
                if not client:
                    raise Exception(f"فشل في الحصول على عميل للحساب {account_id}")
                
                # استخدام المسح بالدفعات
                members = await self.get_members_from_messages_batch(
                    client, 
                    group_info['id'], 
                    batch_size=500,
                    last_seen_months=last_seen,
                    scan_months=months
                )
                
                if not members:
                    logger.warning(f"⚠️ لم يتم العثور على أعضاء للحساب {account_id}")
                    return 0
                
                # تخزين الأعضاء بشكل متوازي
                stored_count = await self.parallel_processor.process_members_batch(
                    members, storage_group_id, self.db_manager
                )
                
                logger.info(f"✅ الحساب {account_id} خزن {stored_count} عضو من أصل {len(members)}")
                return stored_count
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة تخزين الحساب {account_id}: {str(e)}")
            raise e

    async def finalize_storage(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                             storage_group_id: str, status: str, stored_count: int, 
                             failed_accounts: List[str] = None):
        """إنهاء عملية التخزين وإرسال التقرير النهائي"""
        try:
            # حفظ الحالة النهائية في قاعدة البيانات
            self.db_manager.update_storage_progress(storage_group_id, 'system', stored_count, status)
            
            # الحصول على تفاصيل المجموعة
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, total_members FROM storage_groups WHERE id = ?", (storage_group_id,))
                row = cursor.fetchone()
                
                if row:
                    group_title, total_members = row
                else:
                    group_title = "مجموعة غير معروفة"
                    total_members = 0
            
            # إعداد رسالة النتيجة
            status_texts = {
                "completed": "✅ مكتملة",
                "partial": "⚠️ جزئي",
                "failed": "❌ فاشلة", 
                "canceled": "⏹️ ملغاة"
            }
            
            status_text = status_texts.get(status, "❓ غير معروفة")
            
            result_message = (
                f"🎊 تم الانتهاء من عملية التخزين\n\n"
                f"🏷️ المجموعة: {group_title}\n"
                f"🔄 الحالة: {status_text}\n"
                f"📦 الأعضاء المخزنون: {stored_count}/{total_members}\n"
            )
            
            if failed_accounts:
                result_message += f"❌ الحسابات الفاشلة: {len(failed_accounts)}\n"
            
            # إضافة إحصائيات الأداء
            performance_report = self.performance_monitor.get_performance_report()
            result_message += f"\n📊 إحصائيات الأداء:\n"
            result_message += f"• نسبة النجاح: {performance_report['success_rate_percent']:.1f}%\n"
            result_message += f"• متوسط وقت المعالجة: {performance_report['average_processing_time_seconds']:.2f} ثانية\n"
            result_message += f"• معدل الذاكرة المؤقتة: {performance_report['cache_hit_rate_percent']:.1f}%\n"
            
            # تحديث الرسالة النهائية
            message_id = context.user_data.get('progress_message_id')
            if message_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=result_message
                    )
                except Exception as e:
                    logger.error(f"❌ خطأ في تحديث الرسالة النهائية: {str(e)}")
                    await context.bot.send_message(chat_id=chat_id, text=result_message)
            else:
                await context.bot.send_message(chat_id=chat_id, text=result_message)
                
        except Exception as e:
            logger.error(f"❌ خطأ في إنهاء التخزين: {str(e)}", exc_info=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ حدث خطأ أثناء إنهاء التخزين: {str(e)}"
            )

    async def update_storage_progress(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                                    storage_group_id: str, status: str, stored_count: int):
        """تحديث حالة التقدم وإرسال التحديث للمستخدم"""
        try:
            # حفظ الحالة في قاعدة البيانات
            self.db_manager.update_storage_progress(storage_group_id, 'system', stored_count, status)
            
            # الحصول على تفاصيل المجموعة
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, total_members FROM storage_groups WHERE id = ?", (storage_group_id,))
                row = cursor.fetchone()
                
                if not row:
                    group_title = "مجموعة غير معروفة"
                    total_members = 0
                else:
                    group_title, total_members = row
            
            # حساب النسبة المئوية
            progress_percent = (stored_count / total_members) * 100 if total_members > 0 else 0
            
            # إعداد رسالة التقدم
            status_texts = {
                "running": "▶️ جارية",
                "paused": "⏸ متوقفة", 
                "completed": "✅ مكتملة",
                "canceled": "❌ ملغاة",
                "failed": "❌ فاشلة"
            }
            
            progress_text = (
                f"📊 تقدم تخزين الأعضاء:\n\n"
                f"🏷️ المجموعة: {group_title}\n"
                f"🔄 الحالة: {status_texts.get(status, '❓ غير معروفة')}\n"
                f"📦 الأعضاء المخزنون: {stored_count}/{total_members} ({progress_percent:.1f}%)\n"
            )
            
            # إضافة إحصائيات الأداء
            performance_report = self.performance_monitor.get_performance_report()
            progress_text += f"📈 سرعة المعالجة: {performance_report['members_per_second']:.1f} عضو/ثانية\n"
            
            # إعداد أزرار التحكم
            keyboard = []
            if status == 'running':
                keyboard.append([
                    InlineKeyboardButton("⏸ إيقاف مؤقت", callback_data=f"pause_{storage_group_id}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{storage_group_id}")
                ])
            elif status == 'paused':
                keyboard.append([
                    InlineKeyboardButton("▶ استئناف", callback_data=f"resume_{storage_group_id}"),
                    InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{storage_group_id}")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            # تحديث الرسالة
            message_id = context.user_data.get('progress_message_id')
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=progress_text,
                    reply_markup=reply_markup
                )
        
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث رسالة التقدم: {str(e)}", exc_info=True)

    async def refresh_account_session(self, account_id: str) -> Optional[str]:
        """تحديث جلسة الحساب تلقائيًا"""
        try:
            # جلب بيانات الحساب
            with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT phone, device_info FROM accounts WHERE id = ?", (account_id,))
                phone, device_info_str = cursor.fetchone()
                
                device_info = json.loads(device_info_str) if device_info_str else StorageUtils.get_random_device()
                
            # إنشاء عميل جديد لتحديث الجلسة
            client = StorageTDLibClient(API_ID, API_HASH, phone, device_info)
            client.initialize()
            client.send_phone_number()
            
            # انتظار رمز التحقق
            start_time = time.time()
            auth_state = None
            while time.time() - start_time < 30:
                event = client.receive(timeout=1.0)
                if event and event.get('@type') == 'updateAuthorizationState':
                    auth_state = event['authorization_state']['@type']
                    logger.info(f"حالة المصادقة: {auth_state}")
                    if auth_state == 'authorizationStateReady':
                        break
                await asyncio.sleep(0.1)
            
            if auth_state != 'authorizationStateReady':
                raise Exception("فشل تحديث الجلسة")
            
            # حفظ الجلسة المحدثة
            new_session_str = client.save_session()
            
            with sqlite3.connect(ACCOUNTS_DB_PATH) as conn:
                conn.execute(
                    "UPDATE accounts SET session_str = ? WHERE id = ?",
                    (new_session_str, account_id)
                )
                conn.commit()
            
            logger.info(f"✅ تم تحديث جلسة الحساب: {account_id}")
            return new_session_str
            
        except Exception as e:
            logger.error(f"❌ فشل تحديث الجلسة: {str(e)}")
            return None

    def get_performance_report(self) -> Dict[str, Any]:
        """الحصول على تقرير أداء مفصل"""
        return self.performance_monitor.get_performance_report()

    def cleanup_resources(self):
        """تنظيف جميع الموارد"""
        try:
            # تنظيف تجمع العملاء
            self.client_pool.cleanup()
            
            # تنظيف الذاكرة المؤقتة
            self.memory_manager.clear_cache()
            
            # تنظيف cache المحلي
            self.user_cache.clear()
            
            # إلغاء المهام النشطة
            for task_id, task in list(self.active_tasks.items()):
                if not task.done():
                    task.cancel()
            
            logger.info("🧹 تم تنظيف جميع موارد GroupManager")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الموارد: {str(e)}")

    def __del__(self):
        """الدمار - تنظيف الموارد"""
        self.cleanup_resources()