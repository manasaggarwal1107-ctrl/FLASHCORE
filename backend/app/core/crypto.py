import base64
import binascii
import os
import re
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_URLSAFE_B64_RE = re.compile(r"^[A-Za-z0-9_-]{43}=?$")
_KEY_VERSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
_REQUIRED_KEY_BYTES = 32
_MIN_UNIQUE_BYTES = 8


class KeyManagementProvider(Protocol):
    """Abstraction allowing future KMS swap without changing callers."""

    def get_data_key(self, key_version: str) -> bytes: ...


class EnvKeyManagementProvider:
    """Environment-backed key provider for merchant credential encryption.

    Supported environment configuration (`FLASHCORE_CREDENTIAL_ENCRYPTION_KEY`):
    - Must be a securely generated 32-byte key encoded as canonical URL-safe
      Base64 (44 characters with '=' padding or 43 unpadded characters).
    - Example generation:
      `python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
    - Short passphrases, weak repeated-byte keys, raw UTF-8 strings, and
      malformed Base64 values are strictly rejected without fallback derivation.
    """

    ENV_VAR = "FLASHCORE_CREDENTIAL_ENCRYPTION_KEY"

    @classmethod
    def parse_master_key(cls, raw_value: str | None) -> bytes:
        if raw_value is None or not raw_value.strip():
            raise RuntimeError(
                f"{cls.ENV_VAR} is not configured; refusing to encrypt or decrypt credentials."
            )

        token = raw_value.strip()
        if any(ch.isspace() for ch in token) or not _URLSAFE_B64_RE.fullmatch(token):
            raise RuntimeError(
                f"{cls.ENV_VAR} has invalid encoding; expected a 32-byte URL-safe Base64 key."
            )

        padded = token if len(token) == 44 else f"{token}="
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError(
                f"{cls.ENV_VAR} has malformed URL-safe Base64 encoding."
            ) from exc

        if len(decoded) != _REQUIRED_KEY_BYTES:
            raise RuntimeError(
                f"{cls.ENV_VAR} must decode to exactly {_REQUIRED_KEY_BYTES} bytes."
            )

        # Reject non-canonical trailing padding bits or corrupt Base64 tails.
        canonical = base64.urlsafe_b64encode(decoded).decode("ascii")
        if token != canonical and token != canonical.rstrip("="):
            raise RuntimeError(
                f"{cls.ENV_VAR} is not canonical URL-safe Base64."
            )

        if len(set(decoded)) < _MIN_UNIQUE_BYTES:
            raise RuntimeError(
                f"{cls.ENV_VAR} is too weak; provide a randomly generated 32-byte key."
            )

        return decoded

    def get_data_key(self, key_version: str) -> bytes:
        if not _KEY_VERSION_RE.fullmatch(key_version):
            raise ValueError("Invalid encryption key version identifier.")

        master_key = self.parse_master_key(os.getenv(self.ENV_VAR))
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=_REQUIRED_KEY_BYTES,
            salt=None,
            info=f"flashcore-credentials-{key_version}".encode("utf-8"),
        )
        return hkdf.derive(master_key)


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
