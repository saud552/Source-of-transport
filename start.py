#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تشغيل بسيط للبوتات
"""

import sys
import os

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """الدالة الرئيسية"""
    print("🤖 نظام البوتات الثلاثة المتكاملة")
    print("=" * 50)
    print("1. بوت إضافة الحسابات")
    print("2. بوت التخزين")
    print("3. بوت النقل")
    print("4. تشغيل جميع البوتات")
    print("5. اختبار النظام")
    print("=" * 50)
    
    while True:
        try:
            choice = input("اختر رقم البوت (1-5): ").strip()
            
            if choice == "1":
                print("🚀 تشغيل بوت إضافة الحسابات...")
                from add import main as add_main
                add_main()
                break
                
            elif choice == "2":
                print("🚀 تشغيل بوت التخزين...")
                from storage import main as storage_main
                storage_main()
                break
                
            elif choice == "3":
                print("🚀 تشغيل بوت النقل...")
                from transf.main import main as transfer_main
                transfer_main()
                break
                
            elif choice == "4":
                print("🚀 تشغيل جميع البوتات...")
                from start_bots import main as start_all
                start_all()
                break
                
            elif choice == "5":
                print("🔍 اختبار النظام...")
                from test_system import main as test_main
                test_main()
                break
                
            else:
                print("❌ اختيار غير صحيح. يرجى المحاولة مرة أخرى.")
                
        except KeyboardInterrupt:
            print("\n⏹️ تم إيقاف النظام بواسطة المستخدم")
            break
        except Exception as e:
            print(f"❌ خطأ: {str(e)}")
            break

if __name__ == "__main__":
    main()