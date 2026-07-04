"""Encrypt secrets on this Windows PC (DPAPI). Never commit local-secrets/."""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
SECRETS_DIR = BASE_DIR / "local-secrets"
ENC_FILE = SECRETS_DIR / "secrets.enc"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _is_windows() -> bool:
    return sys.platform == "win32"


def _blob_from_bytes(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data)
    blob = _DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
    return blob


def _encrypt_bytes(data: bytes) -> bytes:
    if not _is_windows():
        raise RuntimeError("Local encryption only works on Windows")
    blob_in = _blob_from_bytes(data)
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise RuntimeError("Windows encryption failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _decrypt_bytes(data: bytes) -> bytes:
    if not _is_windows():
        raise RuntimeError("Local decryption only works on Windows")
    blob_in = _blob_from_bytes(data)
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise RuntimeError("Windows decryption failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _load_store() -> dict:
    if not ENC_FILE.exists():
        return {}
    try:
        payload = json.loads(_decrypt_bytes(base64.b64decode(ENC_FILE.read_text(encoding="utf-8"))))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_store(data: dict) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ENC_FILE.write_text(base64.b64encode(_encrypt_bytes(raw)).decode("ascii"), encoding="utf-8")


def save_secret(name: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        raise ValueError("empty secret")
    data = _load_store()
    data[name] = value
    _save_store(data)


def load_secret(name: str) -> str:
    return (_load_store().get(name) or "").strip()


def load_groq_key() -> str:
    """Groq key: env first, then encrypted local store."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    if _is_windows():
        return load_secret("groq_api_key")
    return ""