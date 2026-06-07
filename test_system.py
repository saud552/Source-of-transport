#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
اختبار النظام الأساسي
"""

import sys
import os
import sqlite3

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """اختبار استيراد الوحدات"""
    print("🔍 اختبار استيراد الوحدات...")
    
    try:
        from shared_config import API_ID, API_HASH, ADMIN_IDS
        print("✅ تم استيراد الإعدادات المشتركة بنجاح")
    except Exception as e:
        print(f"❌ خطأ في استيراد الإعدادات المشتركة: {e}")
        return False
    
    try:
        from add.database import DatabaseManager
        print("✅ تم استيراد قاعدة بيانات الحسابات بنجاح")
    except Exception as e:
        print(f"❌ خطأ في استيراد قاعدة بيانات الحسابات: {e}")
        return False
    
    try:
        from storage.database import StorageDatabaseManager
        print("✅ تم استيراد قاعدة بيانات التخزين بنجاح")
    except Exception as e:
        print(f"❌ خطأ في استيراد قاعدة بيانات التخزين: {e}")
        return False
    
    try:
        from transf.database import TransferDatabaseManager
        print("✅ تم استيراد قاعدة بيانات النقل بنجاح")
    except Exception as e:
        print(f"❌ خطأ في استيراد قاعدة بيانات النقل: {e}")
        return False
    
    return True

def test_databases():
    """اختبار قواعد البيانات"""
    print("\n🔍 اختبار قواعد البيانات...")
    
    try:
        # اختبار قاعدة بيانات الحسابات
        db_manager = DatabaseManager('test_accounts.db')
        print("✅ تم إنشاء قاعدة بيانات الحسابات بنجاح")
        db_manager.close()
        
        # اختبار قاعدة بيانات التخزين
        storage_db = StorageDatabaseManager('test_storage.db')
        print("✅ تم إنشاء قاعدة بيانات التخزين بنجاح")
        
        # اختبار قاعدة بيانات النقل
        transfer_db = TransferDatabaseManager('test_transfer.db')
        print("✅ تم إنشاء قاعدة بيانات النقل بنجاح")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء قواعد البيانات: {e}")
        return False

def test_config():
    """اختبار الإعدادات"""
    print("\n🔍 اختبار الإعدادات...")
    
    try:
        from shared_config import API_ID, API_HASH, ADMIN_IDS
        
        if API_ID and API_HASH:
            print("✅ تم تحميل إعدادات API بنجاح")
        else:
            print("⚠️ تحذير: إعدادات API غير مكتملة")
        
        if ADMIN_IDS:
            print("✅ تم تحميل قائمة المديرين بنجاح")
        else:
            print("⚠️ تحذير: قائمة المديرين فارغة")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في تحميل الإعدادات: {e}")
        return False

def cleanup_test_files():
    """تنظيف ملفات الاختبار"""
    print("\n🧹 تنظيف ملفات الاختبار...")
    
    test_files = [
        'test_accounts.db',
        'test_storage.db', 
        'test_transfer.db'
    ]
    
    for file in test_files:
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"✅ تم حذف {file}")
        except Exception as e:
            print(f"⚠️ لم يتم حذف {file}: {e}")

def main():
    """الدالة الرئيسية للاختبار"""
    print("🚀 بدء اختبار النظام...")
    print("=" * 50)
    
    success = True
    
    # اختبار الاستيراد
    if not test_imports():
        success = False
    
    # اختبار قواعد البيانات
    if not test_databases():
        success = False
    
    # اختبار الإعدادات
    if not test_config():
        success = False
    
    # تنظيف ملفات الاختبار
    cleanup_test_files()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ تم اختبار النظام بنجاح! جميع المكونات تعمل بشكل صحيح.")
    else:
        print("❌ فشل في اختبار النظام. يرجى مراجعة الأخطاء أعلاه.")
    
    return success

if __name__ == "__main__":
    main()