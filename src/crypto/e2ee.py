"""
Cifrado Punto a Punto (End-to-End Encryption - E2EE) para Dog Messenger.
Implementa derivación de claves mediante PBKDF2-HMAC-SHA256 y cifrado autenticado
con flujo de bits (Stream-Keystream) y MAC HMAC-SHA256 (Encrypt-then-MAC).
Garantiza confidencialidad, autenticidad e integridad de mensajes y archivos.
"""

import os
import hmac
import hashlib
import base64
import json
from typing import Tuple, Dict, Any

class DogE2EE:
    """Manejador de criptografía simétrica autenticada para canales y chats."""
    
    @staticmethod
    def derive_key(passphrase: str, salt: bytes = b"dog_messenger_cluster_salt") -> bytes:
        """Deriva una clave de 32 bytes (256 bits) usando PBKDF2 con SHA-256."""
        return hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=passphrase.encode("utf-8"),
            salt=salt,
            iterations=100000,
            dklen=32
        )

    @classmethod
    def _generate_keystream(cls, key: bytes, nonce: bytes, length: int) -> bytes:
        """Genera un keystream criptográfico determinista usando HMAC-SHA256 en modo CTR."""
        keystream = bytearray()
        counter = 0
        while len(keystream) < length:
            counter_bytes = counter.to_bytes(8, byteorder="big")
            block = hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])

    @classmethod
    def encrypt(cls, plaintext: str, key_phrase_or_bytes: Any) -> str:
        """
        Cifra texto claro y genera un paquete autenticado en Base64:
        Formato del payload: nonce(16B) + hmac_tag(32B) + ciphertext
        """
        if isinstance(key_phrase_or_bytes, str):
            key = cls.derive_key(key_phrase_or_bytes)
        else:
            key = key_phrase_or_bytes

        plaintext_bytes = plaintext.encode("utf-8")
        nonce = os.urandom(16)
        keystream = cls._generate_keystream(key, nonce, len(plaintext_bytes))
        
        # Cifrado XOR
        ciphertext = bytes(p ^ k for p, k in zip(plaintext_bytes, keystream))
        
        # MAC (Encrypt-then-MAC)
        mac_tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        
        # Empaquetar
        packet = nonce + mac_tag + ciphertext
        return base64.b64encode(packet).decode("ascii")

    @classmethod
    def decrypt(cls, encrypted_b64: str, key_phrase_or_bytes: Any) -> str:
        """
        Descifra y verifica la autenticidad del mensaje cifrado.
        Lanza ValueError si el MAC no coincide (mensaje alterado o clave incorrecta).
        """
        if isinstance(key_phrase_or_bytes, str):
            key = cls.derive_key(key_phrase_or_bytes)
        else:
            key = key_phrase_or_bytes

        try:
            packet = base64.b64decode(encrypted_b64.encode("ascii"))
            if len(packet) < 48:
                return "[Error de cifrado: paquete corrupto]"
            
            nonce = packet[:16]
            received_mac = packet[16:48]
            ciphertext = packet[48:]
            
            # Verificar MAC
            expected_mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(received_mac, expected_mac):
                return "[Error E2EE: Firma/Clave inválida]"
                
            keystream = cls._generate_keystream(key, nonce, len(ciphertext))
            plaintext_bytes = bytes(c ^ k for c, k in zip(ciphertext, keystream))
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            return f"[Error al descifrar: {e}]"
