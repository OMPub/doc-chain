#!/usr/bin/env python3
"""Index Doc Chain attestations from an Ethereum JSON-RPC endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))

from docchain.indexer import EthereumRpc, RpcError, iter_doc_attested_chunks


def main() -> int:
    args = _parse_args()
    try:
        config = _load_config(args)
        rpc = EthereumRpc(config["rpc_url"], timeout=args.timeout)
        from_block, to_block = _resolve_range(args, config, rpc)

        total = 0
        blocks: set[int] = set()
        with _output(args.out) as stream:
            if to_block < from_block:
                if args.format == "summary":
                    _write_summary(stream, config["address"], from_block, to_block, 0, [])
                return 0
            for chunk_start, chunk_end, events in iter_doc_attested_chunks(
                rpc,
                config["address"],
                from_block,
                to_block,
                chunk_size=args.chunk_size,
                doc_chain_id=args.doc_chain_id,
                attester=args.attester,
                doc_ref=args.doc_ref,
            ):
                total += len(events)
                for event in events:
                    _write_event(args.format, stream, event, blocks)
                    blocks.add(event.block_number)
                if args.checkpoint:
                    stream.flush()
                    _write_checkpoint(args.checkpoint, config["address"], args, chunk_end)
            if args.format == "summary":
                _write_summary(stream, config["address"], from_block, to_block, total, sorted(blocks))
        return 0
    except (KeyError, OSError, ValueError, RpcError) as exc:
        print(f"index_events.py: {exc}", file=sys.stderr)
        return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and decode DocAttested logs from an Ethereum RPC endpoint.",
    )
    parser.add_argument("--rpc-url", default=os.environ.get("DOCCHAIN_RPC_URL") or os.environ.get("RPC_URL"))
    parser.add_argument("--address", default=os.environ.get("DOCCHAIN_ADDRESS"))
    parser.add_argument("--deployment", help="Deployment registry JSON with address and blockNumber.")
    parser.add_argument("--from-block", help="First block to scan. Defaults to deployment blockNumber.")
    parser.add_argument("--to-block", default="latest", help="Last block to scan, or 'latest'.")
    parser.add_argument("--confirmations", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=2_000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--checkpoint", help="Optional JSON checkpoint file.")
    parser.add_argument("--out", help="Write output to this file instead of stdout.")
    parser.add_argument("--format", choices=("jsonl", "blocks", "summary"), default="jsonl")
    parser.add_argument("--doc-chain-id", help="Optional indexed docChainId topic filter.")
    parser.add_argument("--attester", help="Optional indexed attester topic filter.")
    parser.add_argument("--doc-ref", type=int, help="Optional indexed docRef topic filter.")
    return parser.parse_args()


def _load_config(args: argparse.Namespace) -> dict[str, object]:
    deployment = {}
    if args.deployment:
        deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))

    rpc_url = args.rpc_url
    if not rpc_url:
        raise ValueError("set --rpc-url, DOCCHAIN_RPC_URL, or RPC_URL")

    address = args.address or deployment.get("address")
    if not address:
        raise ValueError("set --address, DOCCHAIN_ADDRESS, or --deployment")

    return {
        "address": str(address),
        "deployment_block": deployment.get("blockNumber"),
        "rpc_url": rpc_url,
    }


def _resolve_range(
    args: argparse.Namespace,
    config: dict[str, object],
    rpc: EthereumRpc,
) -> tuple[int, int]:
    if args.confirmations < 0:
        raise ValueError("--confirmations must not be negative")

    from_block = _from_block(args, config)
    checkpoint_block = _checkpoint_from_block(args.checkpoint, config, args)
    if checkpoint_block is not None:
        from_block = max(from_block, checkpoint_block)

    to_block = _to_block(args.to_block, rpc)
    if args.to_block == "latest" and args.confirmations:
        to_block = max(0, to_block - args.confirmations)
    return from_block, to_block


def _from_block(args: argparse.Namespace, config: dict[str, object]) -> int:
    if args.from_block is not None:
        return _parse_block(args.from_block)
    if config["deployment_block"] is not None:
        return int(config["deployment_block"])
    raise ValueError("set --from-block or pass --deployment with blockNumber")


def _checkpoint_from_block(
    path: str | None,
    config: dict[str, object],
    args: argparse.Namespace,
) -> int | None:
    if not path:
        return None
    checkpoint = Path(path)
    if not checkpoint.exists():
        return None
    raw = json.loads(checkpoint.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("checkpoint must be a JSON object")
    _validate_checkpoint(raw, config, args)
    if "last_block" not in raw:
        return None
    return int(raw["last_block"]) + 1


def _validate_checkpoint(
    raw: dict[str, object],
    config: dict[str, object],
    args: argparse.Namespace,
) -> None:
    expected = {
        "address": str(config["address"]).lower(),
        "doc_chain_id": (args.doc_chain_id or "").lower(),
        "attester": (args.attester or "").lower(),
        "doc_ref": args.doc_ref,
    }
    actual = {
        "address": str(raw.get("address", "")).lower(),
        "doc_chain_id": str(raw.get("doc_chain_id", "")).lower(),
        "attester": str(raw.get("attester", "")).lower(),
        "doc_ref": raw.get("doc_ref"),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value:
            raise ValueError(f"checkpoint {field} does not match current scan")


def _to_block(value: str, rpc: EthereumRpc) -> int:
    if value == "latest":
        return rpc.block_number()
    return _parse_block(value)


def _parse_block(value: str) -> int:
    if value.startswith("0x"):
        parsed = int(value, 16)
    else:
        parsed = int(value)
    if parsed < 0:
        raise ValueError("block numbers must not be negative")
    return parsed


def _output(path: str | None) -> TextIO:
    if path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path.open("w", encoding="utf-8")
    return _StdoutContext()


def _write_event(format_name: str, stream: TextIO, event: object, blocks: set[int]) -> None:
    record = asdict(event)
    if format_name == "jsonl":
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    elif format_name == "blocks":
        block_number = record["block_number"]
        if block_number not in blocks:
            stream.write(f"{block_number}\n")


def _write_summary(
    stream: TextIO,
    address: object,
    from_block: int,
    to_block: int,
    event_count: int,
    blocks: list[int],
) -> None:
    summary = {
        "address": address,
        "blocks": blocks,
        "eventCount": event_count,
        "fromBlock": from_block,
        "toBlock": to_block,
    }
    stream.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def _write_checkpoint(path: str, address: str, args: argparse.Namespace, last_block: int) -> None:
    checkpoint = {
        "address": address,
        "attester": args.attester or "",
        "doc_chain_id": args.doc_chain_id or "",
        "doc_ref": args.doc_ref,
        "last_block": last_block,
        "updated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = checkpoint_path.with_name(checkpoint_path.name + ".tmp")
    tmp_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, checkpoint_path)


class _StdoutContext:
    def __enter__(self) -> TextIO:
        return sys.stdout

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
