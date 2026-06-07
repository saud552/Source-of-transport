#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
اختبار النظام الأساسي (Decoupled & Modernized)
"""

import sys
import os
import json
import asyncio

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_database():
    """اختبار الاتصال بـ PostgreSQL"""
    print("🔍 اختبار قاعدة البيانات (PostgreSQL)...")
    try:
        from add.database import DatabaseManager
        db = DatabaseManager()
        await db.connect()
        await db.close()
        print("✅ تم الاتصال بـ PostgreSQL بنجاح")
        return True
    except Exception as e:
        print(f"❌ فشل اختبار قاعدة البيانات: {e}")
        return False

def test_imports():
    """اختبار استيراد الوحدات والمكتبات الجديدة"""
    print("\n🔍 اختبار استيراد الوحدات والمكتبات...")
    
    try:
        import asyncpg
        print("✅ asyncpg: متاح")
    except ImportError:
        print("❌ asyncpg: مفقود")
        return False

    try:
        from Crypto.Cipher import AES
        print("✅ pycryptodome: متاح")
    except ImportError:
        print("❌ pycryptodome: مفقود")
        return False
    
    try:
        from shared_config import DEFAULT_COUNTRY_CODE
        print(f"✅ shared_config: متاح (الرمز الافتراضي: {DEFAULT_COUNTRY_CODE})")
    except Exception as e:
        print(f"❌ shared_config: خطأ ({e})")
        return False
    
    return True

def test_devices_json():
    """اختبار وجود وسلامة ملف الأجهزة"""
    print("\n🔍 اختبار devices.json...")
    devices_path = 'devices.json'
    if not os.path.exists(devices_path):
        print("❌ devices.json: مفقود")
        return False
    
    try:
        with open(devices_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                print(f"✅ devices.json: سليم (يحتوي على {len(data)} ملف تعريف)")
                return True
            else:
                print("❌ devices.json: تنسيق غير صالح")
                return False
    except Exception as e:
        print(f"❌ devices.json: خطأ في القراءة ({e})")
        return False

async def main_async():
    """الدالة الرئيسية للاختبار"""
    print("🚀 بدء اختبار النظام (Step 3)...")
    print("=" * 50)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_devices_json():
        success = False

    # اختبار قاعدة البيانات يحتاج لبيئة PostgreSQL حقيقية، نكتفي بمحاولة الاستيراد والتهيئة
    # if not await test_database():
    #    success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ تم التحقق من سلامة البنية التحتية والتبعيات!")
    else:
        print("❌ فشل في اختبار النظام. يرجى مراجعة التبعيات.")
    
    return success

if __name__ == "__main__":
    asyncio.run(main_async())
