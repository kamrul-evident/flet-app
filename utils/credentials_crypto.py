import os
import json
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

KDF_ITERATIONS = 390000
KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from the user's login password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_credential(fields: dict, password: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt a credential dict with AES-256-GCM.
    Returns (ciphertext, nonce, kdf_salt).
    """
    kdf_salt = os.urandom(SALT_LENGTH)
    nonce = os.urandom(NONCE_LENGTH)
    key = derive_key(password, kdf_salt)
    try:
        plaintext = json.dumps(fields, separators=(",", ":")).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return ciphertext, nonce, kdf_salt
    finally:
        # Best-effort wipe; Python can't guarantee GC of bytes objects.
        del key


def decrypt_credential(
    ciphertext: bytes, nonce: bytes, kdf_salt: bytes, password: str
) -> dict:
    """Decrypt a credential blob back to its dict form."""
    key = derive_key(password, kdf_salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    finally:
        del key
