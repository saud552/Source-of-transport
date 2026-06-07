#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تشغيل محسن للبوتات الثلاثة
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotManager:
    """مدير البوتات"""
    
    def __init__(self):
        self.bots = {}
        self.running = False
        self.threads = {}
        
    def start_bot(self, bot_name, bot_module):
        """تشغيل بوت معين"""
        try:
            logger.info(f"🚀 بدء تشغيل {bot_name}...")
            bot_module.main()
        except Exception as e:
            logger.error(f"❌ خطأ في تشغيل {bot_name}: {str(e)}")
    
    def start_all_bots(self):
        """تشغيل جميع البوتات"""
        logger.info("🚀 بدء تشغيل نظام البوتات الثلاثة...")
        logger.info("=" * 60)
        
        # استيراد البوتات
        try:
            from add import main as add_main
            from storage import main as storage_main
            from transf.main import main as transfer_main
            
            self.bots = {
                'add': add_main,
                'storage': storage_main,
                'transfer': transfer_main
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في استيراد البوتات: {str(e)}")
            return False
        
        # تشغيل البوتات في خيوط منفصلة
        for bot_name, bot_main in self.bots.items():
            try:
                thread = threading.Thread(
                    target=self.start_bot,
                    args=(bot_name, bot_main),
                    name=f"{bot_name}_bot"
                )
                thread.daemon = True
                thread.start()
                self.threads[bot_name] = thread
                
                # تأخير قصير بين البوتات
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ خطأ في تشغيل {bot_name}: {str(e)}")
        
        self.running = True
        logger.info("✅ تم تشغيل جميع البوتات بنجاح!")
        logger.info("📱 بوت إضافة الحسابات: جاهز")
        logger.info("💾 بوت التخزين: جاهز")
        logger.info("📤 بوت النقل: جاهز")
        logger.info("=" * 60)
        
        return True
    
    def stop_all_bots(self):
        """إيقاف جميع البوتات"""
        logger.info("⏹️ إيقاف جميع البوتات...")
        self.running = False
        
        # انتظار انتهاء الخيوط
        for bot_name, thread in self.threads.items():
            try:
                thread.join(timeout=5)
                logger.info(f"✅ تم إيقاف {bot_name}")
            except Exception as e:
                logger.error(f"❌ خطأ في إيقاف {bot_name}: {str(e)}")
    
    def check_bots_status(self):
        """فحص حالة البوتات"""
        active_bots = []
        for bot_name, thread in self.threads.items():
            if thread.is_alive():
                active_bots.append(bot_name)
        
        if active_bots:
            logger.info(f"🟢 البوتات النشطة: {', '.join(active_bots)}")
        else:
            logger.warning("🔴 لا توجد بوتات نشطة")
        
        return active_bots

def main():
    """الدالة الرئيسية"""
    print("🤖 نظام البوتات الثلاثة المتكاملة")
    print("=" * 60)
    print("📱 بوت إضافة الحسابات")
    print("💾 بوت التخزين")
    print("📤 بوت النقل")
    print("=" * 60)
    
    # إنشاء مدير البوتات
    bot_manager = BotManager()
    
    try:
        # تشغيل البوتات
        if not bot_manager.start_all_bots():
            logger.error("❌ فشل في تشغيل البوتات")
            return False
        
        # مراقبة البوتات
        while bot_manager.running:
            try:
                time.sleep(30)  # فحص كل 30 ثانية
                bot_manager.check_bots_status()
                
            except KeyboardInterrupt:
                logger.info("⏹️ تم إيقاف النظام بواسطة المستخدم")
                break
            except Exception as e:
                logger.error(f"❌ خطأ في مراقبة البوتات: {str(e)}")
                break
        
    except Exception as e:
        logger.error(f"❌ خطأ حرج: {str(e)}")
        return False
    
    finally:
        # تنظيف
        bot_manager.stop_all_bots()
        logger.info("🔚 انتهاء تشغيل النظام")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)