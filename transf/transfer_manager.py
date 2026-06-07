# -*- coding: utf-8 -*-
"""
مدير عمليات النقل
"""

import asyncio
import logging
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transf.config import MAX_MEMBERS_PER_BATCH, TRANSFER_DELAY, MAX_RETRIES
from transf.tdlib_client import TDLibClient
from transf.utils import TransferUtils

logger = logging.getLogger(__name__)

class TransferManager:
    """مدير عمليات النقل"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.utils = TransferUtils()
        self.active_transfers = {}
    
    async def start_transfer(self, transfer_id: str, members: List[Dict[str, Any]], 
                           accounts: List[Dict[str, Any]], update, context) -> None:
        """بدء عملية النقل"""
        try:
            logger.info(f"بدء عملية النقل {transfer_id} مع {len(members)} عضو و {len(accounts)} حساب")
            
            # حفظ العملية النشطة
            self.active_transfers[transfer_id] = {
                'status': 'running',
                'started_at': datetime.now(),
                'members': members,
                'accounts': accounts,
                'current_account_index': 0,
                'transferred_count': 0,
                'failed_count': 0
            }
            
            # تقسيم الأعضاء إلى دفعات
            batches = self._create_batches(members, MAX_MEMBERS_PER_BATCH)
            
            total_batches = len(batches)
            logger.info(f"تم تقسيم الأعضاء إلى {total_batches} دفعة")
            
            # معالجة كل دفعة
            for batch_index, batch in enumerate(batches, 1):
                if transfer_id not in self.active_transfers:
                    logger.info(f"تم إلغاء عملية النقل {transfer_id}")
                    break
                
                if self.active_transfers[transfer_id]['status'] == 'paused':
                    logger.info(f"تم إيقاف عملية النقل {transfer_id} مؤقتاً")
                    await self._wait_for_resume(transfer_id)
                
                if self.active_transfers[transfer_id]['status'] == 'cancelled':
                    logger.info(f"تم إلغاء عملية النقل {transfer_id}")
                    break
                
                # معالجة الدفعة
                await self._process_batch(transfer_id, batch, accounts, update, context)
                
                # تحديث التقدم
                progress = (batch_index / total_batches) * 100
                await self._update_progress(transfer_id, progress, update, context)
                
                # تأخير بين الدفعات
                if batch_index < total_batches:
                    await asyncio.sleep(TRANSFER_DELAY)
            
            # إنهاء العملية
            await self._complete_transfer(transfer_id, update, context)
            
        except Exception as e:
            logger.error(f"خطأ في عملية النقل {transfer_id}: {str(e)}")
            await self._handle_transfer_error(transfer_id, str(e), update, context)
        finally:
            # تنظيف العملية النشطة
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]
    
    def _create_batches(self, members: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        """تقسيم الأعضاء إلى دفعات"""
        batches = []
        for i in range(0, len(members), batch_size):
            batch = members[i:i + batch_size]
            batches.append(batch)
        return batches
    
    async def _process_batch(self, transfer_id: str, batch: List[Dict[str, Any]], 
                           accounts: List[Dict[str, Any]], update, context) -> None:
        """معالجة دفعة من الأعضاء"""
        transfer_info = self.active_transfers.get(transfer_id)
        if not transfer_info:
            return
        
        current_account_index = transfer_info['current_account_index']
        account = accounts[current_account_index % len(accounts)]
        
        # إنشاء عميل TDLib
        client = TDLibClient(account['session_str'], account['device_info'])
        
        try:
            # تسجيل الدخول
            await client.initialize()
            
            # نقل كل عضو في الدفعة
            for member in batch:
                if transfer_id not in self.active_transfers:
                    break
                
                if self.active_transfers[transfer_id]['status'] == 'paused':
                    await self._wait_for_resume(transfer_id)
                
                if self.active_transfers[transfer_id]['status'] == 'cancelled':
                    break
                
                # محاولة نقل العضو
                success = await self._transfer_member(client, member, transfer_id)
                
                if success:
                    self.active_transfers[transfer_id]['transferred_count'] += 1
                else:
                    self.active_transfers[transfer_id]['failed_count'] += 1
                
                # تأخير بين الأعضاء
                await asyncio.sleep(1)
            
            # تحديث فهرس الحساب
            self.active_transfers[transfer_id]['current_account_index'] = (current_account_index + 1) % len(accounts)
            
        except Exception as e:
            logger.error(f"خطأ في معالجة الدفعة: {str(e)}")
            # تحديث فهرس الحساب في حالة الخطأ
            self.active_transfers[transfer_id]['current_account_index'] = (current_account_index + 1) % len(accounts)
        finally:
            # إغلاق العميل
            await client.close()
    
    async def _transfer_member(self, client: TDLibClient, member: Dict[str, Any], 
                             transfer_id: str) -> bool:
        """نقل عضو واحد"""
        try:
            # الحصول على معرف المجموعة الهدف من قاعدة البيانات
            transfer_operation = self.db_manager.get_transfer_operations(limit=1)
            if not transfer_operation:
                return False
            
            target_group_id = transfer_operation[0]['target_group_id']
            
            # محاولة إضافة العضو للمجموعة
            result = await client.add_chat_member(target_group_id, member['user_id'])
            
            if result:
                # تحديث حالة العضو في قاعدة البيانات
                self.db_manager.update_member_transfer_status(
                    transfer_id, member['user_id'], 'success'
                )
                logger.info(f"تم نقل العضو {member['user_id']} بنجاح")
                return True
            else:
                # تحديث حالة العضو كفاشل
                self.db_manager.update_member_transfer_status(
                    transfer_id, member['user_id'], 'failed', 'فشل في إضافة العضو'
                )
                logger.warning(f"فشل في نقل العضو {member['user_id']}")
                return False
                
        except Exception as e:
            logger.error(f"خطأ في نقل العضو {member['user_id']}: {str(e)}")
            self.db_manager.update_member_transfer_status(
                transfer_id, member['user_id'], 'failed', str(e)
            )
            return False
    
    async def _update_progress(self, transfer_id: str, progress: float, update, context) -> None:
        """تحديث تقدم النقل"""
        try:
            transfer_info = self.active_transfers.get(transfer_id)
            if not transfer_info:
                return
            
            # تحديث قاعدة البيانات
            self.db_manager.update_transfer_operation(
                transfer_id,
                transferred_members=transfer_info['transferred_count'],
                failed_members=transfer_info['failed_count']
            )
            
            # تحديث الرسالة
            progress_text = f"🚀 **تقدم عملية النقل...**\n\n"
            progress_text += f"📊 **التقدم:** {progress:.1f}%\n"
            progress_text += f"✅ **تم النقل:** {transfer_info['transferred_count']}\n"
            progress_text += f"❌ **فشل:** {transfer_info['failed_count']}\n"
            progress_text += f"⏳ **المتبقي:** {len(transfer_info['members']) - transfer_info['transferred_count'] - transfer_info['failed_count']}\n\n"
            
            if transfer_info['status'] == 'paused':
                progress_text += "⏸️ **متوقف مؤقتاً**"
            elif transfer_info['status'] == 'cancelled':
                progress_text += "❌ **تم الإلغاء**"
            else:
                progress_text += "🔄 **جاري النقل...**"
            
            # تحديث الرسالة
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    progress_text,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"خطأ في تحديث التقدم: {str(e)}")
    
    async def _complete_transfer(self, transfer_id: str, update, context) -> None:
        """إنهاء عملية النقل"""
        try:
            transfer_info = self.active_transfers.get(transfer_id)
            if not transfer_info:
                return
            
            # تحديث حالة العملية
            self.db_manager.update_transfer_operation(
                transfer_id,
                status='completed',
                completed_at=datetime.now()
            )
            
            # رسالة الإنجاز
            completion_text = f"✅ **تم إنجاز عملية النقل!**\n\n"
            completion_text += f"📊 **الإحصائيات:**\n"
            completion_text += f"✅ **تم النقل بنجاح:** {transfer_info['transferred_count']}\n"
            completion_text += f"❌ **فشل في النقل:** {transfer_info['failed_count']}\n"
            completion_text += f"📈 **معدل النجاح:** {(transfer_info['transferred_count'] / (transfer_info['transferred_count'] + transfer_info['failed_count']) * 100):.1f}%\n\n"
            completion_text += f"⏱️ **وقت الإنجاز:** {datetime.now() - transfer_info['started_at']}"
            
            # تحديث الرسالة
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    completion_text,
                    parse_mode='Markdown'
                )
            
            logger.info(f"تم إنجاز عملية النقل {transfer_id}")
            
        except Exception as e:
            logger.error(f"خطأ في إنهاء عملية النقل: {str(e)}")
    
    async def _handle_transfer_error(self, transfer_id: str, error_message: str, update, context) -> None:
        """معالجة خطأ في النقل"""
        try:
            # تحديث حالة العملية
            self.db_manager.update_transfer_operation(
                transfer_id,
                status='failed'
            )
            
            # رسالة الخطأ
            error_text = f"❌ **فشلت عملية النقل!**\n\n"
            error_text += f"🔍 **سبب الخطأ:** {error_message}\n\n"
            error_text += f"يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني."
            
            # تحديث الرسالة
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    error_text,
                    parse_mode='Markdown'
                )
            
            logger.error(f"فشلت عملية النقل {transfer_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"خطأ في معالجة خطأ النقل: {str(e)}")
    
    async def _wait_for_resume(self, transfer_id: str) -> None:
        """انتظار استئناف النقل"""
        while (transfer_id in self.active_transfers and 
               self.active_transfers[transfer_id]['status'] == 'paused'):
            await asyncio.sleep(1)
    
    def pause_transfer(self, transfer_id: str) -> bool:
        """إيقاف النقل مؤقتاً"""
        if transfer_id in self.active_transfers:
            self.active_transfers[transfer_id]['status'] = 'paused'
            return True
        return False
    
    def resume_transfer(self, transfer_id: str) -> bool:
        """استئناف النقل"""
        if transfer_id in self.active_transfers:
            self.active_transfers[transfer_id]['status'] = 'running'
            return True
        return False
    
    def cancel_transfer(self, transfer_id: str) -> bool:
        """إلغاء النقل"""
        if transfer_id in self.active_transfers:
            self.active_transfers[transfer_id]['status'] = 'cancelled'
            return True
        return False
    
    def get_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على حالة النقل"""
        return self.active_transfers.get(transfer_id)