"""Core steganography engine for Phoenix.

Payloads are appended to a PNG file, immediately after the final ``IEND``
chunk.  Nothing inside the PNG structure is touched, so the carrier image
stays a perfectly valid PNG for any decoder that tolerates trailing bytes
(PIL, Qt, browsers, all of them do).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "PNG_MAGIC",
    "PNG_END",
    "PhoenixError",
    "MAX_PAYLOAD_BYTES",
    "MAX_IMAGE_BYTES",
    "is_png",
    "validate_png",
    "find_payload",
    "generate_key",
    "encrypt_payload",
    "decrypt_payload",
    "bind",
    "read",
    "inspect",
]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"
PNG_END_LEN = len(PNG_END)

# 64 MiB keeps a corrupt / non-image file from eating all available memory.
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 256 * 1024 * 1024

PathLike = Union[str, "os.PathLike[str]"]


class PhoenixError(Exception):
    """User-facing error. The GUI shows ``str(exc)`` verbatim."""


def _as_path(path: PathLike, label: str = "file") -> Path:
    if path is None or (isinstance(path, str) and not path.strip()):
        raise PhoenixError(f"No {label} selected.")
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise PhoenixError(f"{label.capitalize()} not found: {resolved}")
    if not resolved.is_file():
        raise PhoenixError(f"Not a regular file: {resolved}")
    return resolved


def _walk_chunks(blob: bytes):
    """Yield ``(end_offset, chunk_type)`` for every PNG chunk in *blob*.

    Stops at the first malformed chunk and at ``IEND``. Trailing bytes after
    ``IEND`` are payload data and are never parsed as structure.
    """
    if not blob.startswith(PNG_MAGIC):
        raise PhoenixError(
            "This file is not a PNG image. Only PNG files are supported."
        )
    offset = len(PNG_MAGIC)
    total = len(blob)
    while offset + 8 <= total:
        length = int.from_bytes(blob[offset : offset + 4], "big")
        chunk_type = blob[offset + 4 : offset + 8]
        end = offset + 12 + length
        if length < 0 or end > total:
            raise PhoenixError(
                "The PNG structure is incomplete; the file is truncated or "
                "corrupted."
            )
        yield end, chunk_type
        if chunk_type == b"IEND":
            return
        offset = end
    raise PhoenixError(
        "The PNG structure is incomplete; the file is truncated or corrupted."
    )


def _payload_offset(blob: bytes) -> int:
    """Byte offset where the appended payload starts (just past ``IEND``)."""
    for end, chunk_type in _walk_chunks(blob):
        if chunk_type == b"IEND":
            return end
    raise PhoenixError(  # pragma: no cover - _walk_chunks always raises or yields IEND
        "The PNG structure is incomplete; the file is truncated or corrupted."
    )


def is_png(path: PathLike) -> bool:
    """True when *path* is a structurally valid PNG."""
    try:
        validate_png(path)
    except PhoenixError:
        return False
    return True


def validate_png(path: PathLike) -> Path:
    """Validate that *path* is a PNG terminated by an ``IEND`` chunk.

    Replaces the old unchecked ``open()`` / ``split()[1]`` pair that raised a
    bare ``IndexError`` on non-PNG input.
    """
    resolved = _as_path(path, "image")
    try:
        size = resolved.stat().st_size
        if size < len(PNG_MAGIC) + 12:
            raise PhoenixError(
                f"{resolved.name} is too small to be a PNG image."
            )
        blob = resolved.read_bytes()
    except OSError as exc:
        raise PhoenixError(f"Cannot read {resolved.name}: {exc}") from exc
    if size > MAX_IMAGE_BYTES:
        raise PhoenixError(
            f"{resolved.name} is {size // (1024 * 1024)} MiB. Phoenix only "
            f"handles images up to {MAX_IMAGE_BYTES // (1024 * 1024)} MiB."
        )
    _payload_offset(blob)
    return resolved


def find_payload(blob: bytes) -> bytes:
    """Return everything appended after the ``IEND`` chunk.

    The real chunk stream is walked instead of using ``split``/``rfind``, so a
    payload that itself contains the ``IEND`` byte pattern survives intact
    rather than being silently truncated, and re-binding onto an already
    bound image resolves to the most recent payload.
    """
    return blob[_payload_offset(blob) :]


def generate_key() -> str:
    """Return a fresh URL-safe base64 Fernet key."""
    return Fernet.generate_key().decode("ascii")


def _fernet(key: str):
    if not key or not key.strip():
        raise PhoenixError("Decryption key is empty.")
    try:
        return Fernet(key.strip().encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise PhoenixError(
            "Malformed key. A Phoenix key looks like "
            "gAAAAABm...= (44 URL-safe characters)."
        ) from exc


def encrypt_payload(plaintext: Union[str, bytes], key: str) -> str:
    """Encrypt *plaintext* with *key* and return the base64 token."""
    data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    try:
        return _fernet(key).encrypt(data).decode("ascii")
    except PhoenixError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise PhoenixError(f"Encryption failed: {exc}") from exc


def decrypt_payload(token: str, key: str) -> str:
    """Decrypt a Fernet *token* with *key*.

    A wrong key raises :class:`InvalidToken` internally; it is translated into
    a :class:`PhoenixError` so callers never mistake a failure for success.
    """
    try:
        raw = _fernet(key).decrypt(token.strip().encode("ascii"))
    except (PhoenixError, ValueError, UnicodeEncodeError):
        raise
    except InvalidToken as exc:
        raise PhoenixError(
            "Wrong decryption key, or the payload was altered."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise PhoenixError(f"Decryption failed: {exc}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PhoenixError("Decrypted payload is not valid UTF-8 text.") from exc


def bind(
    source: PathLike,
    destination: PathLike,
    payload: Union[str, bytes],
) -> int:
    """Write *payload* into a copy of the PNG at *source*.

    Returns the number of payload bytes stored.  The carrier image bytes are
    copied verbatim, so the result remains a decodable PNG.
    """
    src = validate_png(source)
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if not data:
        raise PhoenixError("Nothing to hide: the payload is empty.")

    dest = Path(destination).expanduser()
    if dest.resolve() == src.resolve():
        raise PhoenixError("The output file cannot be the input file.")
    if dest.parent and not dest.parent.exists():
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PhoenixError(f"Cannot create {dest.parent}: {exc}") from exc

    try:
        with open(src, "rb") as fh:
            image = fh.read()
        with open(dest, "wb") as fh:
            fh.write(image)
            fh.write(data)
    except OSError as exc:
        raise PhoenixError(f"Write failed for {dest.name}: {exc}") from exc
    return len(data)


def read(source: PathLike, key: Optional[str] = None) -> str:
    """Read the payload out of *source*.

    ``key=None`` (the default) returns the payload as plain UTF-8 text.
    Passing any string - including an empty one - means "decrypt with this
    key", so a missing key is reported instead of silently handing the raw
    ciphertext back as if it were the plaintext.
    """
    path = validate_png(source)
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise PhoenixError(f"Cannot read {path.name}: {exc}") from exc

    payload = find_payload(blob)
    if not payload:
        raise PhoenixError(
            "This image carries no hidden data. Bind some data first."
        )
    try:
        token = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PhoenixError(
            "Hidden data is not valid text. It was probably encrypted or "
            "the file was tampered with."
        ) from exc

    if key is None:
        return token
    return decrypt_payload(token, key)


def inspect(source: PathLike) -> dict:
    """Describe a PNG carrier without decrypting anything."""
    path = validate_png(source)
    size = path.stat().st_size
    blob = path.read_bytes()
    payload = find_payload(blob)
    return {
        "path": str(path),
        "name": path.name,
        "file_size": size,
        "image_size": size - len(payload),
        "payload_size": len(payload),
        # Every Fernet token starts with this versioned prefix.
        "encrypted": payload.startswith(b"gAAAA"),
    }
