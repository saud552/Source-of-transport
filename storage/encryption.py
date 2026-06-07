# -*- coding: utf-8 -*-
"""
وحدة التشفير وفك التشفير في بوت التخزين
"""

import base64
import hashlib
import logging
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

from .config import PASSPHRASE, SALT

logger = logging.getLogger(__name__)

class EncryptionManager:
    """مدير التشفير وفك التشفير في بوت التخزين"""
    
    def __init__(self):
        self._key = None

    def get_encryption_key(self) -> bytes:
        """إعادة استخدام مفتاح التشفير المحسوب مسبقاً"""
        if self._key is None:
            self._key = PBKDF2(
                PASSPHRASE,
                SALT,
                dkLen=32,  # 256-bit key
                count=100000,
                prf=lambda p, s: hashlib.sha256(p + s).digest()
            )
        return self._key

    def encrypt_session(self, session_bytes: bytes) -> str:
        """تشفير جلسة TDLib باستخدام AES-CBC"""
        try:
            key = self.get_encryption_key()
            cipher = AES.new(key, AES.MODE_CBC)
            ct_bytes = cipher.encrypt(pad(session_bytes, AES.block_size))
            encrypted = cipher.iv + ct_bytes  # IV + النص المشفر
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"خطأ في تشفير الجلسة: {str(e)}")
            raise e

    def decrypt_session(self, encrypted_session: str) -> bytes:
        """فك تشفير جلسة TDLib باستخدام AES-CBC"""
        try:
            key = self.get_encryption_key()
            encrypted = base64.b64decode(encrypted_session.encode('utf-8'))
            
            # التحقق من طول البيانات
            if len(encrypted) < 16:
                raise ValueError("البيانات المشفرة أقصر من الطول المتوقع")
            
            iv = encrypted[:16]  # أول 16 بايت هي IV
            ct = encrypted[16:]
            
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            decrypted = unpad(cipher.decrypt(ct), AES.block_size)
            return decrypted
        except Exception as e:
            logger.error(f"خطأ في فك تشفير الجلسة: {str(e)}")
            raise e

    def hash_password(self, password: str) -> str:
        """تشفير كلمة المرور باستخدام SHA-256"""
        try:
            return hashlib.sha256(password.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"خطأ في تشفير كلمة المرور: {str(e)}")
            raise e

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """التحقق من صحة كلمة المرور"""
        try:
            return self.hash_password(password) == hashed_password
        except Exception as e:
            logger.error(f"خطأ في التحقق من كلمة المرور: {str(e)}")
            return False

    def generate_session_token(self, user_id: int) -> str:
        """توليد رمز جلسة فريد للمستخدم"""
        try:
            import time
            import random
            import string
            
            # إنشاء رمز فريد
            timestamp = str(int(time.time()))
            random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            token_data = f"{user_id}_{timestamp}_{random_part}"
            
            # تشفير الرمز
            return self.hash_password(token_data)
        except Exception as e:
            logger.error(f"خطأ في توليد رمز الجلسة: {str(e)}")
            raise e

    def encrypt_sensitive_data(self, data: str) -> str:
        """تشفير البيانات الحساسة"""
        try:
            key = self.get_encryption_key()
            cipher = AES.new(key, AES.MODE_CBC)
            ct_bytes = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
            encrypted = cipher.iv + ct_bytes
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"خطأ في تشفير البيانات الحساسة: {str(e)}")
            raise e

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """فك تشفير البيانات الحساسة"""
        try:
            key = self.get_encryption_key()
            encrypted = base64.b64decode(encrypted_data.encode('utf-8'))
            
            if len(encrypted) < 16:
                raise ValueError("البيانات المشفرة أقصر من الطول المتوقع")
            
            iv = encrypted[:16]
            ct = encrypted[16:]
            
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            decrypted = unpad(cipher.decrypt(ct), AES.block_size)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"خطأ في فك تشفير البيانات الحساسة: {str(e)}")
            raise e

    def generate_secure_random_string(self, length: int = 32) -> str:
        """توليد سلسلة عشوائية آمنة"""
        try:
            import secrets
            import string
            
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))
        except Exception as e:
            logger.error(f"خطأ في توليد السلسلة العشوائية: {str(e)}")
            # استخدام بديل أقل أماناً
            import random
            import string
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def validate_encrypted_data(self, encrypted_data: str) -> bool:
        """التحقق من صحة البيانات المشفرة"""
        try:
            # محاولة فك التشفير للتحقق من الصحة
            self.decrypt_session(encrypted_data)
            return True
        except Exception:
            return False

    def get_encryption_info(self) -> dict:
        """الحصول على معلومات التشفير"""
        return {
            'algorithm': 'AES-CBC',
            'key_size': 256,
            'iv_size': 128,
            'padding': 'PKCS7',
            'key_derivation': 'PBKDF2',
            'iterations': 100000
        }