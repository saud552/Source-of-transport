# -*- coding: utf-8 -*-
"""
وحدات التشفير وفك التشفير للجلسات (AES-256-CBC)
"""

import base64
import hashlib
import logging
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger(__name__)

class EncryptionManager:
    """مدير التشفير للجلسات باستخدام AES-256-CBC"""
    
    def __init__(self, passphrase: bytes, salt: bytes):
        self.passphrase = passphrase
        self.salt = salt
        self._key = None
    
    def get_encryption_key(self) -> bytes:
        """إعادة استخدام مفتاح التشفير المحسوب مسبقاً عبر PBKDF2"""
        if self._key is None:
            self._key = PBKDF2(
                self.passphrase,
                self.salt,
                dkLen=32,  # 256-bit key
                count=100000,
                prf=lambda p, s: hashlib.sha256(p + s).digest()
            )
        return self._key
    
    def encrypt(self, data: bytes) -> bytes:
        """تشفير البيانات الخام باستخدام AES-CBC"""
        try:
            key = self.get_encryption_key()
            cipher = AES.new(key, AES.MODE_CBC)
            ct_bytes = cipher.encrypt(pad(data, AES.block_size))
            return cipher.iv + ct_bytes  # إرجاع IV مدمج مع النص المشفر
        except Exception as e:
            logger.error(f"خطأ في تشفير البيانات: {str(e)}")
            raise e
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """فك تشفير البيانات الخام باستخدام AES-CBC"""
        try:
            if len(encrypted_data) < 16:
                raise ValueError("البيانات المشفرة أقصر من طول IV المتوقع")
                
            key = self.get_encryption_key()
            iv = encrypted_data[:16]
            ct = encrypted_data[16:]
            
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            return unpad(cipher.decrypt(ct), AES.block_size)
        except Exception as e:
            logger.error(f"خطأ في فك تشفير البيانات: {str(e)}")
            raise e
