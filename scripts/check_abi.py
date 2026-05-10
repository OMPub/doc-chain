#!/usr/bin/env python3
"""Compare two ABI JSON files after normalizing JSON formatting."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _param_signature(params: object) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(params, list):
        return ()

    signature = []
    for param in params:
        if not isinstance(param, dict):
            continue
        signature.append(
            (
                str(param.get("name", "")),
                str(param.get("type", "")),
                str(param.get("internalType", "")),
            )
        )
    return tuple(signature)


def _abi_entry_key(entry: object) -> tuple[str, str, tuple[tuple[str, str, str], ...]]:
    if not isinstance(entry, dict):
        return ("", "", ())
    return (
        str(entry.get("type", "")),
        str(entry.get("name", "")),
        _param_signature(entry.get("inputs", [])),
    )


def normalize_abi(raw: object) -> object:
    if isinstance(raw, dict) and "abi" in raw:
        raw = raw["abi"]
    if isinstance(raw, list):
        return sorted(raw, key=_abi_entry_key)
    return raw


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_abi.py <generated-abi> <committed-abi>", file=sys.stderr)
        return 2

    generated_path = Path(sys.argv[1])
    committed_path = Path(sys.argv[2])

    generated = normalize_abi(load_json(generated_path))
    committed = normalize_abi(load_json(committed_path))

    if generated != committed:
        print(
            f"ABI mismatch: {committed_path} is not equal to {generated_path}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
