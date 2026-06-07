# -*- coding: utf-8 -*-
"""
وحدات التشفير وفك التشفير للجلسات
"""

import base64
import hashlib
import logging
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger(__name__)

class EncryptionManager:
    """مدير التشفير للجلسات"""
    
    def __init__(self, passphrase: bytes, salt: bytes):
        self.passphrase = passphrase
        self.salt = salt
        self._key = None
    
    def get_encryption_key(self):
        """إعادة استخدام مفتاح التشفير المحسوب مسبقاً"""
        if self._key is None:
            self._key = PBKDF2(
                self.passphrase,
                self.salt,
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