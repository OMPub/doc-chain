#!/usr/bin/env python3
"""Prepare Doc Chain EIP-712 typed data for signing."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from _docchain_script import (
    MAX_URI_BYTES,
    compact_json,
    load_deployment,
    normalize_address,
    normalize_bytes32,
    positive_uint,
    uint64,
    write_json,
)


def main() -> int:
    try:
        args = _parse_args()
        prepared = prepare_attestation(args)
        write_json(Path(args.out), prepared)
        print(args.out)
        return 0
    except (OSError, ValueError) as exc:
        print(f"prepare_attestation.py: {exc}")
        return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Doc Chain attestation typed data.")
    parser.add_argument("--deployment", help="Deployment registry JSON.")
    parser.add_argument("--chain-id", type=int, help="EIP-712 domain chain ID.")
    parser.add_argument("--contract-address", default=os.environ.get("DOCCHAIN_ADDRESS"))
    parser.add_argument("--network", help="Optional network name for metadata.")
    parser.add_argument(
        "--attester",
        default=os.environ.get("DOCCHAIN_ATTESTER") or os.environ.get("ATTESTER_ADDRESS"),
        help="Address that will sign the attestation.",
    )
    parser.add_argument("--doc-chain-id", required=True, help="Profile docChainId bytes32.")
    parser.add_argument("--doc-ref", required=True, type=int, help="Profile-defined uint64 docRef.")
    parser.add_argument(
        "--parent-hash",
        default="0x" + "00" * 32,
        help="Parent DocBlock blockHash. Defaults to bytes32(0).",
    )
    parser.add_argument("--content-hash", required=True, help="Profile-defined contentHash bytes32.")
    parser.add_argument("--uri", default="", help="Optional publication URI.")
    parser.add_argument("--deadline", type=int, help="Unix timestamp signing deadline.")
    parser.add_argument("--ttl", type=int, default=86_400, help="Seconds from now if --deadline is omitted.")
    parser.add_argument("--out", default="build/attestations/attestation.prepared.json")
    return parser.parse_args()


def prepare_attestation(args: argparse.Namespace) -> dict[str, object]:
    deployment = load_deployment(args.deployment) if args.deployment else {}
    chain_id = args.chain_id if args.chain_id is not None else deployment.get("chainId")
    if chain_id is None:
        raise ValueError("set --chain-id or pass --deployment with chainId")
    contract_address = args.contract_address or deployment.get("address")
    if contract_address is None:
        raise ValueError("set --contract-address, DOCCHAIN_ADDRESS, or --deployment")
    if args.attester is None:
        raise ValueError("set --attester, DOCCHAIN_ATTESTER, or ATTESTER_ADDRESS")
    deadline = args.deadline if args.deadline is not None else int(time.time()) + args.ttl
    if args.deadline is None and args.ttl <= 0:
        raise ValueError("--ttl must be positive")
    uri = str(args.uri)
    if len(uri.encode("utf-8")) > MAX_URI_BYTES:
        raise ValueError(f"uri exceeds {MAX_URI_BYTES} UTF-8 bytes")

    attestation = {
        "attester": normalize_address(args.attester),
        "docBlock": {
            "docChainId": normalize_bytes32(args.doc_chain_id),
            "docRef": uint64(args.doc_ref, "docRef"),
            "parentHash": normalize_bytes32(args.parent_hash),
            "contentHash": normalize_bytes32(args.content_hash),
        },
        "uri": uri,
        "deadline": positive_uint(deadline, "deadline"),
    }
    typed_data = typed_data_for_attestation(
        chain_id=positive_uint(int(chain_id), "chainId"),
        contract_address=normalize_address(str(contract_address)),
        attestation=attestation,
    )
    return {
        "schema": "doc-chain-prepared-attestation-v1",
        "contract": "DocChain",
        "contractAddress": normalize_address(str(contract_address)),
        "network": args.network or deployment.get("network", ""),
        "chainId": positive_uint(int(chain_id), "chainId"),
        "attestation": attestation,
        "typedData": typed_data,
        "preparedAt": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def typed_data_for_attestation(
    *,
    chain_id: int,
    contract_address: str,
    attestation: dict[str, object],
) -> dict[str, object]:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "DocBlock": [
                {"name": "docChainId", "type": "bytes32"},
                {"name": "docRef", "type": "uint64"},
                {"name": "parentHash", "type": "bytes32"},
                {"name": "contentHash", "type": "bytes32"},
            ],
            "DocAttestation": [
                {"name": "attester", "type": "address"},
                {"name": "docBlock", "type": "DocBlock"},
                {"name": "uri", "type": "string"},
                {"name": "deadline", "type": "uint256"},
            ],
        },
        "primaryType": "DocAttestation",
        "domain": {
            "name": "Doc Chain",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": contract_address,
        },
        "message": attestation,
    }


if __name__ == "__main__":
    raise SystemExit(main())
