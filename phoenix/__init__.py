"""Phoenix - PNG steganography toolkit."""

from .core import (
    PhoenixError,
    PNG_END,
    PNG_MAGIC,
    bind,
    decrypt_payload,
    encrypt_payload,
    find_payload,
    generate_key,
    is_png,
    read,
    validate_png,
)

VERSION = "0.2:1"

__all__ = [
    "VERSION",
    "PhoenixError",
    "PNG_END",
    "PNG_MAGIC",
    "bind",
    "decrypt_payload",
    "encrypt_payload",
    "find_payload",
    "generate_key",
    "is_png",
    "read",
    "validate_png",
]
