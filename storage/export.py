# -*- coding: utf-8 -*-
"""
وحدة تصدير البيانات من بوت التخزين
"""

import io
import csv
import logging
from typing import Optional, List, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes

from .database import StorageDatabaseManager

logger = logging.getLogger(__name__)

class DataExporter:
    """مصدر تصدير البيانات من بوت التخزين"""
    
    def __init__(self, db_manager: StorageDatabaseManager):
        self.db_manager = db_manager

    async def export_group_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 group_id: str) -> bool:
        """تصدير أعضاء مجموعة معينة إلى ملف CSV"""
        try:
            # جلب بيانات الأعضاء
            members = self.db_manager.get_stored_members(group_id)
            
            if not members:
                await update.callback_query.answer("❌ لا توجد أعضاء مخزنين في هذه المجموعة", show_alert=True)
                return False
            
            # الحصول على عنوان المجموعة
            group_title = self._get_group_title(group_id)
            if not group_title:
                group_title = "Unknown Group"
            
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

    def _get_group_title(self, group_id: str) -> Optional[str]:
        """الحصول على عنوان المجموعة"""
        try:
            with self.db_manager.db_path as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM storage_groups WHERE id = ?", (group_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"خطأ في الحصول على عنوان المجموعة: {str(e)}")
            return None

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
                member.get('is_bot', 0),
                member.get('is_premium', 0),
                member.get('transfer_status', 'pending')
            ])
        
        # إعداد الملف للإرسال
        output.seek(0)
        csv_data = output.getvalue().encode('utf-8')
        output.close()
        
        return csv_data

    async def export_category_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 category_id: str) -> bool:
        """تصدير جميع بيانات فئة معينة"""
        try:
            # الحصول على جميع المجموعات في الفئة
            groups = self.db_manager.get_storage_groups_by_category(category_id)
            
            if not groups:
                await update.callback_query.answer("❌ لا توجد مجموعات في هذه الفئة", show_alert=True)
                return False
            
            # تصدير كل مجموعة
            exported_count = 0
            for group in groups:
                members = self.db_manager.get_stored_members(group['id'])
                if members:
                    csv_data = self._create_csv_data(members)
                    
                    await context.bot.send_document(
                        chat_id=update.callback_query.message.chat_id,
                        document=io.BytesIO(csv_data),
                        filename=f"{group['title']}_members.csv",
                        caption=f"📤 تم تصدير {len(members)} عضو من مجموعة {group['title']}"
                    )
                    exported_count += 1
            
            await update.callback_query.answer(f"✅ تم تصدير {exported_count} مجموعة بنجاح")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في تصدير بيانات الفئة: {str(e)}", exc_info=True)
            return False

    def get_export_statistics(self, category_id: Optional[str] = None) -> Dict[str, Any]:
        """الحصول على إحصائيات التصدير"""
        try:
            if category_id:
                groups = self.db_manager.get_storage_groups_by_category(category_id)
            else:
                groups = self.db_manager.get_storage_categories()
            
            total_groups = len(groups)
            total_members = 0
            
            for group in groups:
                members = self.db_manager.get_stored_members(group['id'])
                total_members += len(members)
            
            return {
                'total_groups': total_groups,
                'total_members': total_members,
                'average_members_per_group': total_members / total_groups if total_groups > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على إحصائيات التصدير: {str(e)}")
            return {
                'total_groups': 0,
                'total_members': 0,
                'average_members_per_group': 0
            }