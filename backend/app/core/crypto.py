import base64
import os
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class KeyManagementProvider(Protocol):
    """Abstraction allowing future KMS swap without changing callers."""

    def get_data_key(self, key_version: str) -> bytes: ...


class EnvKeyManagementProvider:
    ENV_VAR = "FLASHCORE_CREDENTIAL_ENCRYPTION_KEY"

    def get_data_key(self, key_version: str) -> bytes:
        raw = os.getenv(self.ENV_VAR)
        if not raw or not raw.strip():
            raise RuntimeError(
                f"{self.ENV_VAR} is not configured; refusing to encrypt or decrypt credentials."
            )

        secret_bytes = raw.strip().encode("utf-8")
        try:
            decoded = base64.urlsafe_b64decode(raw.strip() + "==")
            if len(decoded) == 32:
                secret_bytes = decoded
        except Exception:
            pass

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=f"flashcore-credentials-{key_version}".encode("utf-8"),
        )
        return hkdf.derive(secret_bytes)


_DEFAULT_PROVIDER = EnvKeyManagementProvider()


def encrypt_secret(
    plaintext: str,
    *,
    aad: str,
    key_version: str = "v1",
    provider: KeyManagementProvider = _DEFAULT_PROVIDER,
) -> str:
    if not plaintext:
        raise ValueError("Cannot encrypt an empty secret.")
    key = provider.get_data_key(key_version)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(
        nonce, plaintext.encode("utf-8"), aad.encode("utf-8")
    )
    return (
        f"{key_version}:"
        f"{base64.urlsafe_b64encode(nonce).decode('ascii')}:"
        f"{base64.urlsafe_b64encode(ciphertext).decode('ascii')}"
    )


def decrypt_secret(
    token: str,
    *,
    aad: str,
    provider: KeyManagementProvider = _DEFAULT_PROVIDER,
) -> str:
    parts = token.split(":", 2)
    if len(parts) != 3:
        raise ValueError("Malformed encrypted credential payload.")
    key_version, nonce_b64, ct_b64 = parts
    key = provider.get_data_key(key_version)
    nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
    ciphertext = base64.urlsafe_b64decode(ct_b64.encode("ascii"))
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad.encode("utf-8"))
    return plaintext.decode("utf-8")
