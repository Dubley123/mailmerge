from cryptography.fernet import Fernet
import os
import base64
import hashlib


def _get_cipher_suite():
    """Return a Fernet instance using a valid 32-byte urlsafe base64 key.

    Priority:
    1. Use `ENCRYPTION_KEY` env if provided (must already be a valid Fernet key).
    2. Derive a key from `SECRET_KEY` env deterministically (sha256 -> urlsafe base64).
    3. As a last resort (dev only), generate a fresh Fernet key.

    Note: In production you should set `ENCRYPTION_KEY` to a persistent secret.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if key:
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    # Try to derive from SECRET_KEY for a deterministic dev key
    secret = os.getenv("SECRET_KEY")
    if secret:
        if isinstance(secret, str):
            secret = secret.encode()
        # sha256 produces 32 bytes; base64.urlsafe_b64encode gives a valid Fernet key (44 bytes)
        digest = hashlib.sha256(secret).digest()
        derived_key = base64.urlsafe_b64encode(digest)
        return Fernet(derived_key)

    # Last resort: generate a new key (non-deterministic). This is only suitable for ephemeral/dev runs.
    generated = Fernet.generate_key()
    return Fernet(generated)


def encrypt_value(value: str) -> str:
    """Encrypts a string value and returns a utf-8 string.

    Returns `None` for falsy inputs to keep backward compatibility.
    """
    if not value:
        return None
    cipher_suite = _get_cipher_suite()
    encrypted_bytes = cipher_suite.encrypt(value.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_value(encrypted_value: str) -> str:
    """Decrypts a previously encrypted value.

    Returns `None` for falsy inputs to keep backward compatibility.
    """
    if not encrypted_value:
        return None
    cipher_suite = _get_cipher_suite()
    decrypted_bytes = cipher_suite.decrypt(encrypted_value.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")
