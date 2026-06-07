# -*- coding: utf-8 -*-
"""
ديكورات التحقق من الصلاحيات
"""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from .config import ADMIN_IDS

logger = logging.getLogger(__name__)

def owner_only(func):
    """ديكور للتحقق من أن المستخدم هو المالك"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = None
        for arg in args:
            if isinstance(arg, Update):
                update = arg
                break
        if not update:
            for value in kwargs.values():
                if isinstance(value, Update):
                    update = value
                    break
        
        if update:
            if update.message:
                uid = update.message.from_user.id
            elif update.callback_query:
                uid = update.callback_query.from_user.id
            else:
                uid = None
        else:
            uid = None
            
        if uid not in ADMIN_IDS:
            if update and update.callback_query:
                await update.callback_query.answer("⛔ هذا البوت مخصص للمالك فقط.", show_alert=True)
            elif update and update.message:
                await update.message.reply_text("⛔ هذا البوت مخصص للمالك فقط.")
            return
        
        return await func(*args, **kwargs)
    return wrapper