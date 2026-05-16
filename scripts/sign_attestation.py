#!/usr/bin/env python3
"""Sign a prepared Doc Chain attestation with Foundry `cast`."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from _docchain_script import cast_path, load_json, subprocess_error_detail, write_json


def main() -> int:
    try:
        args = _parse_args()
        prepared = load_json(Path(args.prepared))
        signature = sign_typed_data(prepared["typedData"], args)
        signed = {
            "schema": "doc-chain-signed-attestation-v1",
            "prepared": prepared,
            "signature": signature,
            "signedAt": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        write_json(Path(args.out), signed)
        print(args.out)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"sign_attestation.py: {subprocess_error_detail(exc)}")
        return 2
    except (KeyError, OSError, ValueError) as exc:
        print(f"sign_attestation.py: {exc}")
        return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sign prepared Doc Chain EIP-712 typed data.")
    parser.add_argument("prepared", nargs="?", default="build/attestations/attestation.prepared.json")
    parser.add_argument("--out", default="build/attestations/attestation.signed.json")
    parser.add_argument("--cast", default=os.environ.get("CAST"))
    parser.add_argument("--interactive", action="store_true", help="Prompt for the private key.")
    parser.add_argument("--private-key-env", default="PRIVATE_KEY")
    return parser.parse_args()


def sign_typed_data(typed_data: object, args: argparse.Namespace) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(typed_data, tmp, separators=(",", ":"), sort_keys=True)
        tmp_path = tmp.name
    try:
        command = [cast_path(args.cast), "wallet", "sign", "--data", "--from-file", tmp_path]
        if args.interactive:
            command.append("--interactive")
        else:
            private_key = os.environ.get(args.private_key_env)
            if not private_key:
                raise ValueError(f"set {args.private_key_env} or use --interactive")
            command.extend(["--private-key", private_key])
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        signature = result.stdout.strip().splitlines()[-1].strip()
        if not signature.startswith("0x"):
            raise ValueError(f"cast did not return a hex signature: {signature}")
        return signature
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
