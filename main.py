import asyncio
import nest_asyncio
import threading
import time

nest_asyncio.apply()

def run_add_bot():
    """تشغيل بوت إضافة الحسابات"""
    from add import main as add_main
    add_main()

def run_storage_bot():
    """تشغيل بوت التخزين"""
    from storage import main as storage_main
    storage_main()

def run_transfer_bot():
    """تشغيل بوت النقل"""
    from transf.main import main as transfer_main
    transfer_main()

if __name__ == "__main__":
    print("🚀 بدء تشغيل نظام البوتات الثلاثة...")
    
    # إنشاء خيوط منفصلة لكل بوت
    add_thread = threading.Thread(target=run_add_bot, name="AddBot")
    storage_thread = threading.Thread(target=run_storage_bot, name="StorageBot")
    transfer_thread = threading.Thread(target=run_transfer_bot, name="TransferBot")
    
    # تشغيل البوتات
    add_thread.start()
    time.sleep(2)  # تأخير قصير بين البوتات
    
    storage_thread.start()
    time.sleep(2)
    
    transfer_thread.start()
    
    print("✅ تم تشغيل جميع البوتات بنجاح!")
    print("📱 بوت إضافة الحسابات: جاهز")
    print("💾 بوت التخزين: جاهز")
    print("📤 بوت النقل: جاهز")
    
    try:
        # انتظار انتهاء جميع الخيوط
        add_thread.join()
        storage_thread.join()
        transfer_thread.join()
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف جميع البوتات بواسطة المستخدم")
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوتات: {str(e)}")
