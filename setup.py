#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
إعداد النظام
"""

import os
import sys
import subprocess

def install_requirements():
    """تثبيت المتطلبات"""
    print("📦 تثبيت المتطلبات...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ تم تثبيت المتطلبات بنجاح")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ خطأ في تثبيت المتطلبات: {e}")
        return False

def create_env_file():
    """إنشاء ملف البيئة"""
    print("🔧 إنشاء ملف البيئة...")
    
    if os.path.exists(".env"):
        print("⚠️ ملف .env موجود بالفعل")
        return True
    
    try:
        with open(".env.example", "r", encoding="utf-8") as f:
            content = f.read()
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write(content)
        
        print("✅ تم إنشاء ملف .env")
        print("⚠️ يرجى ملء القيم في ملف .env")
        return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء ملف .env: {e}")
        return False

def create_directories():
    """إنشاء المجلدات المطلوبة"""
    print("📁 إنشاء المجلدات...")
    
    directories = [
        "logs",
        "data",
        "backups"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ تم إنشاء مجلد {directory}")
        except Exception as e:
            print(f"❌ خطأ في إنشاء مجلد {directory}: {e}")

def test_system():
    """اختبار النظام"""
    print("🔍 اختبار النظام...")
    
    try:
        from test_system import main as test_main
        return test_main()
    except Exception as e:
        print(f"❌ خطأ في اختبار النظام: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("🚀 إعداد نظام البوتات الثلاثة")
    print("=" * 50)
    
    success = True
    
    # تثبيت المتطلبات
    if not install_requirements():
        success = False
    
    # إنشاء ملف البيئة
    if not create_env_file():
        success = False
    
    # إنشاء المجلدات
    create_directories()
    
    # اختبار النظام
    if not test_system():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ تم إعداد النظام بنجاح!")
        print("📝 الخطوات التالية:")
        print("1. املأ ملف .env بالقيم الصحيحة")
        print("2. شغل python run.py لبدء العمل")
    else:
        print("❌ فشل في إعداد النظام")
        print("يرجى مراجعة الأخطاء أعلاه")
    
    return success

if __name__ == "__main__":
    main()