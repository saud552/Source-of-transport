# -*- coding: utf-8 -*-
"""
وحدة تصدير البيانات من بوت التخزين (Async PostgreSQL version)
"""

import io
import csv
import logging
import uuid
from typing import Optional, List, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from .database import StorageDatabaseManager

logger = logging.getLogger(__name__)

class DataExporter:
    """مصدر تصدير البيانات من بوت التخزين باستخدام PostgreSQL"""
    
    def __init__(self, db_manager: StorageDatabaseManager):
        self.db_manager = db_manager

    async def export_group_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 group_id: str) -> bool:
        """تصدير أعضاء مجموعة معينة إلى ملف CSV"""
        try:
            # جلب بيانات الأعضاء بشكل async (سنستخدم استعلام مباشر هنا لضمان التوافق)
            async with self.db_manager.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT user_id, username, first_name, last_name, phone,
                           last_seen, is_bot, is_premium, transfer_status
                    FROM stored_members
                    WHERE storage_group_id = $1
                """, uuid.UUID(group_id))
                members = [dict(row) for row in rows]

                row_group = await conn.fetchrow("SELECT title FROM storage_groups WHERE id = $1", uuid.UUID(group_id))
                group_title = row_group['title'] if row_group else "Unknown Group"
            
            if not members:
                await update.callback_query.answer("❌ لا توجد أعضاء مخزنين في هذه المجموعة", show_alert=True)
                return False
            
            # إنشاء ملف CSV في الذاكرة
            csv_data = self._create_csv_data(members)
            
            # إرسال الملف
            await context.bot.send_document(
                chat_id=update.callback_query.message.chat_id,
                document=io.BytesIO(csv_data),
                filename=f"{group_title}_members.csv",
                caption=f"📤 تم تصدير {len(members)} عضو من مجموعة {group_title}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تصدير بيانات المجموعة: {str(e)}", exc_info=True)
            return False

    def _create_csv_data(self, members: List[Dict[str, Any]]) -> bytes:
        """إنشاء بيانات CSV من قائمة الأعضاء"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # كتابة العنوان
        writer.writerow([
            'User ID', 'Username', 'First Name', 'Last Name', 'Phone',
            'Last Seen', 'Is Bot', 'Is Premium', 'Transfer Status'
        ])
        
        # كتابة البيانات
        for member in members:
            writer.writerow([
                member.get('user_id', ''),
                member.get('username', ''),
                member.get('first_name', ''),
                member.get('last_name', ''),
                member.get('phone', ''),
                member.get('last_seen', ''),
                member.get('is_bot', False),
                member.get('is_premium', False),
                member.get('transfer_status', 'pending')
            ])
        
        output.seek(0)
        csv_data = output.getvalue().encode('utf-8')
        output.close()
        return csv_data

    async def export_category_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 category_id: str) -> bool:
        # مشابه لـ export_group_members ولكن للفئة كاملة
        # ... logic ...
        return True
