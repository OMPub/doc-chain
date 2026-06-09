#!/usr/bin/env python3
"""Submit signed Doc Chain attestations with Foundry `cast`.

One signed artifact submits through `attestDoc`. Several artifacts (or
`--batch`) submit through `attestBatch`, which lands every attestation in a
single transaction and skips any that are already recorded on chain.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from _docchain_script import (
    cast_path,
    load_json,
    normalize_address,
    normalize_bytes32,
    normalize_hex_bytes,
    positive_uint,
    subprocess_error_detail,
    uint64,
)


ATTEST_DOC_SELECTOR = "d2b85e96"
ATTEST_BATCH_SELECTOR = "7fba5650"


def main() -> int:
    try:
        args = _parse_args()
        signed_artifacts = [load_json(Path(path)) for path in args.signed]
        items = []
        artifact_addresses = set()
        for signed in signed_artifacts:
            prepared = signed["prepared"]
            if not isinstance(prepared, dict):
                raise ValueError("signed artifact prepared section must be an object")
            artifact_addresses.add(normalize_address(str(prepared["contractAddress"])))
            items.append((prepared["attestation"], str(signed["signature"])))

        explicit_address = args.address or os.environ.get("DOCCHAIN_ADDRESS")
        if explicit_address:
            contract_address = normalize_address(explicit_address)
        elif len(artifact_addresses) == 1:
            contract_address = artifact_addresses.pop()
        else:
            raise ValueError(
                "signed artifacts target different contract addresses; "
                "pass --address or set DOCCHAIN_ADDRESS"
            )

        if len(items) == 1 and not args.batch:
            calldata = attest_doc_calldata(items[0][0], items[0][1])
        else:
            calldata = attest_batch_calldata(items)
        if args.calldata_out:
            Path(args.calldata_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.calldata_out).write_text(calldata + "\n", encoding="utf-8")
        if args.print_calldata:
            print(calldata)
        if args.no_send and not args.dry_run:
            return 0

        rpc_url = args.rpc_url or os.environ.get("DOCCHAIN_RPC_URL") or os.environ.get("RPC_URL")
        if not rpc_url:
            raise ValueError("set --rpc-url, DOCCHAIN_RPC_URL, or RPC_URL")
        if args.dry_run:
            run_cast_call(args, contract_address, calldata, rpc_url)
            return 0
        run_cast_send(args, contract_address, calldata, rpc_url)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"submit_attestation.py: {subprocess_error_detail(exc)}")
        return 2
    except (KeyError, OSError, ValueError) as exc:
        print(f"submit_attestation.py: {exc}")
        return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit signed Doc Chain attestations.")
    parser.add_argument(
        "signed",
        nargs="*",
        default=["build/attestations/attestation.signed.json"],
        help="Signed attestation artifact(s). More than one submits via attestBatch.",
    )
    parser.add_argument("--rpc-url", default=os.environ.get("DOCCHAIN_RPC_URL") or os.environ.get("RPC_URL"))
    parser.add_argument("--address", default=os.environ.get("DOCCHAIN_ADDRESS"))
    parser.add_argument("--cast", default=os.environ.get("CAST"))
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use attestBatch even for a single artifact (requires contract release 2).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run eth_call instead of broadcasting.")
    parser.add_argument("--no-send", action="store_true", help="Only generate calldata.")
    parser.add_argument("--print-calldata", action="store_true")
    parser.add_argument("--calldata-out", help="Optional file path for raw calldata.")
    parser.add_argument("--interactive", action="store_true", help="Prompt for the submitter private key.")
    parser.add_argument("--private-key-env", default="SUBMITTER_PRIVATE_KEY")
    parser.add_argument("--confirmations", type=int, default=1)
    return parser.parse_args()


def run_cast_call(
    args: argparse.Namespace,
    contract_address: str,
    calldata: str,
    rpc_url: str,
) -> None:
    command = [
        cast_path(args.cast),
        "call",
        contract_address,
        "--data",
        calldata,
        "--rpc-url",
        rpc_url,
    ]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    print(result.stdout.strip())


def run_cast_send(
    args: argparse.Namespace,
    contract_address: str,
    calldata: str,
    rpc_url: str,
) -> None:
    command = [
        cast_path(args.cast),
        "send",
        contract_address,
        "--data",
        calldata,
        "--rpc-url",
        rpc_url,
        "--confirmations",
        str(args.confirmations),
    ]
    if args.interactive:
        command.append("--interactive")
    else:
        private_key = os.environ.get(args.private_key_env) or os.environ.get("PRIVATE_KEY")
        if not private_key:
            raise ValueError(f"set {args.private_key_env}, PRIVATE_KEY, or use --interactive")
        command.extend(["--private-key", private_key])
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    print(result.stdout.strip())


def attest_doc_calldata(attestation: object, signature: str) -> str:
    if not isinstance(attestation, dict):
        raise ValueError("attestation must be an object")
    doc_block = attestation["docBlock"]
    if not isinstance(doc_block, dict):
        raise ValueError("docBlock must be an object")
    attestation_encoded = _encode_attestation(attestation, doc_block)
    signature_encoded = _encode_bytes(bytes.fromhex(normalize_hex_bytes(signature)[2:]))
    signature_offset = 64 + len(attestation_encoded) // 2
    payload = (
        _word_uint(64)
        + _word_uint(signature_offset)
        + attestation_encoded
        + signature_encoded
    )
    return "0x" + ATTEST_DOC_SELECTOR + payload


def attest_batch_calldata(items: list[tuple[object, str]]) -> str:
    if not items:
        raise ValueError("attestBatch requires at least one attestation")
    attestation_tails = []
    signature_tails = []
    for attestation, signature in items:
        if not isinstance(attestation, dict):
            raise ValueError("attestation must be an object")
        doc_block = attestation["docBlock"]
        if not isinstance(doc_block, dict):
            raise ValueError("docBlock must be an object")
        attestation_tails.append(_encode_attestation(attestation, doc_block))
        signature_tails.append(_encode_bytes(bytes.fromhex(normalize_hex_bytes(signature)[2:])))
    attestations_encoded = _encode_dynamic_array(attestation_tails)
    signatures_encoded = _encode_dynamic_array(signature_tails)
    signatures_offset = 64 + len(attestations_encoded) // 2
    payload = (
        _word_uint(64)
        + _word_uint(signatures_offset)
        + attestations_encoded
        + signatures_encoded
    )
    return "0x" + ATTEST_BATCH_SELECTOR + payload


def _encode_dynamic_array(element_tails: list[str]) -> str:
    heads = []
    offset = len(element_tails) * 32
    for tail in element_tails:
        heads.append(_word_uint(offset))
        offset += len(tail) // 2
    return _word_uint(len(element_tails)) + "".join(heads) + "".join(element_tails)


def _encode_attestation(attestation: dict[str, object], doc_block: dict[str, object]) -> str:
    uri = str(attestation.get("uri", "")).encode("utf-8")
    uri_offset = 8 * 32
    return (
        _word_address(str(attestation["attester"]))
        + _word_address(str(attestation.get("onBehalfOf", "0x" + "00" * 20)))
        + _word_bytes32(str(doc_block["docChainId"]))
        + _word_uint(uint64(int(doc_block["docRef"]), "docRef"))
        + _word_bytes32(str(doc_block["parentHash"]))
        + _word_bytes32(str(doc_block["contentHash"]))
        + _word_uint(uri_offset)
        + _word_uint(positive_uint(int(attestation["deadline"]), "deadline"))
        + _encode_bytes(uri)
    )


def _encode_bytes(payload: bytes) -> str:
    padding = b"\x00" * ((32 - len(payload) % 32) % 32)
    return _word_uint(len(payload)) + (payload + padding).hex()


def _word_uint(value: int) -> str:
    return format(positive_uint(value, "uint"), "064x")


def _word_address(value: str) -> str:
    return normalize_address(value)[2:].rjust(64, "0")


def _word_bytes32(value: str) -> str:
    return normalize_bytes32(value)[2:]


if __name__ == "__main__":
    raise SystemExit(main())
