"""Shared stdlib helpers for Doc Chain command-line scripts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

MAX_URI_BYTES = 8192


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_deployment(path: str | None) -> dict[str, object]:
    if path is None:
        return {}
    return load_json(Path(path))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compact_json(value) + "\n", encoding="utf-8")


def compact_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def normalize_address(value: str) -> str:
    body = _hex_body(value, "address")
    if len(body) != 40:
        raise ValueError("address must be 20 bytes")
    return "0x" + body


def normalize_bytes32(value: str) -> str:
    body = _hex_body(value, "bytes32")
    if len(body) != 64:
        raise ValueError("bytes32 value must be 32 bytes")
    return "0x" + body


def normalize_hex_bytes(value: str) -> str:
    body = _hex_body(value, "bytes")
    if len(body) % 2 != 0:
        raise ValueError("bytes value must have even hex length")
    return "0x" + body


def positive_uint(value: int, field: str) -> int:
    if value < 0:
        raise ValueError(f"{field} must not be negative")
    return value


def uint64(value: int, field: str) -> int:
    positive_uint(value, field)
    if value > 2**64 - 1:
        raise ValueError(f"{field} must fit uint64")
    return value


def cast_path(value: str | None = None) -> str:
    if value:
        return value
    foundry_cast = Path.home() / ".foundry" / "bin" / "cast"
    if foundry_cast.exists():
        return str(foundry_cast)
    return os.environ.get("CAST", "cast")


def subprocess_error_detail(exc: subprocess.CalledProcessError) -> str:
    detail = (exc.stderr or "").strip() or (exc.stdout or "").strip()
    if not detail:
        detail = f"command exited with {exc.returncode}"
    return redact_secret_values(detail)


def redact_secret_values(text: str) -> str:
    redacted = text
    for name in ("PRIVATE_KEY", "SUBMITTER_PRIVATE_KEY"):
        value = os.environ.get(name)
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def _hex_body(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.lower().startswith("0x"):
        raise ValueError(f"{field} must be a 0x-prefixed hex string")
    body = value[2:].lower()
    try:
        int(body or "0", 16)
    except ValueError as exc:
        raise ValueError(f"{field} contains non-hex characters") from exc
    return body
