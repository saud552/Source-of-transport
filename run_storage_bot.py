#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تشغيل بوت التخزين منفصل
"""

import sys
import os

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from storage import main
    main()