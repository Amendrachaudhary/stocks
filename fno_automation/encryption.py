"""
encryption.py - Cryptographic Security & At-Rest Data Protection
================================================================
Provides AES-128-CBC with HMAC-SHA256 authenticated symmetric encryption via Fernet.
Secures local SQLite databases, Telethon session files, and credential caches at rest.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("fno_automation.encryption")
BASE_DIR = Path(__file__).resolve().parent


def generate_encryption_key() -> str:
    """
    Generates a cryptographically secure, URL-safe base64-encoded 32-byte Fernet key.

    Returns:
        str: 44-character base64 encoded symmetric key.
    """
    return Fernet.generate_key().decode("utf-8")


class DataProtector:
    """
    Utility class for encrypting and decrypting sensitive data files at rest.
    Sources symmetric master key from the ENCRYPTION_KEY environment variable.
    """

    def __init__(self, key: Optional[Union[str, bytes]] = None):
        """
        Initializes the DataProtector with a symmetric key.

        Args:
            key: Optional 32-byte Fernet key. If omitted, fetched from ENCRYPTION_KEY env var.
        """
        raw_key = key or os.getenv("ENCRYPTION_KEY")

        if not raw_key:
            # Generate a secure fallback key if not detected in environment
            generated = generate_encryption_key()
            logger.warning(
                "[SECURITY ADVISORY] No ENCRYPTION_KEY detected in environment. "
                "Generated transient key. Set ENCRYPTION_KEY in .env for persistent decryption."
            )
            raw_key = generated

        if isinstance(raw_key, str):
            raw_key = raw_key.strip().encode("utf-8")

        try:
            self._fernet = Fernet(raw_key)
            self._key = raw_key
        except Exception as exc:
            raise ValueError(f"Invalid Fernet encryption key format: {exc}") from exc

    @property
    def key_str(self) -> str:
        """Returns the active key as a decoded string."""
        return self._key.decode("utf-8")

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypts arbitrary raw bytes."""
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, token: bytes) -> bytes:
        """Decrypts Fernet ciphertext token back to raw bytes."""
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise ValueError("Decryption failed: Token is invalid, corrupted, or key does not match.") from exc

    def encrypt_file(
        self,
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None
    ) -> str:
        """
        Encrypts a file at rest using authenticated Fernet encryption.

        Args:
            file_path: Absolute or relative path to file to encrypt.
            output_path: Optional destination path. If None, encrypts in-place atomically.

        Returns:
            str: Resolved path to the encrypted file.
        """
        src = Path(file_path)
        if not src.is_absolute():
            src = BASE_DIR / src

        if not src.exists():
            raise FileNotFoundError(f"File not found for encryption: {src}")

        raw_bytes = src.read_bytes()

        # Idempotence check: avoid double-encrypting already encrypted tokens
        if raw_bytes.startswith(b"gAAAAA"):
            try:
                # If it successfully decrypts with current key, it's already encrypted
                self._fernet.decrypt(raw_bytes)
                logger.info(f"[ENCRYPTION] File {src.name} is already encrypted. Skipping.")
                return str(src)
            except Exception:
                pass

        cipher_bytes = self.encrypt_bytes(raw_bytes)
        dst = Path(output_path) if output_path else src
        if not dst.is_absolute():
            dst = BASE_DIR / dst

        # Write to temporary file first for atomic swap
        temp_file = dst.with_suffix(dst.suffix + ".tmp")
        temp_file.write_bytes(cipher_bytes)
        temp_file.replace(dst)

        logger.info(f"[ENCRYPTION] Successfully secured file: {dst}")
        return str(dst)

    def decrypt_file(
        self,
        file_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None
    ) -> bytes:
        """
        Decrypts an encrypted file at rest.

        Args:
            file_path: Absolute or relative path to encrypted file.
            output_path: Optional destination path to write decrypted bytes. If None, returns bytes.

        Returns:
            bytes: Decrypted raw file payload.
        """
        src = Path(file_path)
        if not src.is_absolute():
            src = BASE_DIR / src

        if not src.exists():
            raise FileNotFoundError(f"File not found for decryption: {src}")

        cipher_bytes = src.read_bytes()
        decrypted_bytes = self.decrypt_bytes(cipher_bytes)

        if output_path:
            dst = Path(output_path)
            if not dst.is_absolute():
                dst = BASE_DIR / dst
            temp_file = dst.with_suffix(dst.suffix + ".tmp")
            temp_file.write_bytes(decrypted_bytes)
            temp_file.replace(dst)
            logger.info(f"[DECRYPTION] Decrypted payload written to: {dst}")

        return decrypted_bytes
