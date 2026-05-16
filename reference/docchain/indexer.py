"""Dependency-free JSON-RPC helpers for generic Doc Chain event indexing."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from .abi import DOC_ATTESTED_EVENT_TOPIC0
from .logs import decode_doc_attested_log
from .model import DocAttested


class RpcError(RuntimeError):
    """Raised when an Ethereum JSON-RPC request fails."""


class EthereumRpc:
    """Small JSON-RPC client for the methods needed by a log indexer."""

    def __init__(self, rpc_url: str, timeout: float = 30.0) -> None:
        self.rpc_url = rpc_url
        self.timeout = timeout
        self._next_id = 1

    def call(self, method: str, params: list[object]) -> object:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params,
        }
        self._next_id += 1
        request = urllib.request.Request(
            self.rpc_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RpcError(f"{method} request failed: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RpcError(f"{method} request failed: {exc}") from exc
        if "error" in body:
            raise RpcError(f"{method} returned error: {body['error']}")
        return body["result"]

    def block_number(self) -> int:
        result = self.call("eth_blockNumber", [])
        if not isinstance(result, str):
            raise RpcError("eth_blockNumber returned a non-string result")
        return int(result, 16)

    def get_logs(
        self,
        address: str,
        from_block: int,
        to_block: int,
        topics: list[str | None],
    ) -> list[object]:
        result = self.call(
            "eth_getLogs",
            [
                {
                    "address": normalize_address(address),
                    "fromBlock": hex(from_block),
                    "toBlock": hex(to_block),
                    "topics": topics,
                }
            ],
        )
        if not isinstance(result, list):
            raise RpcError("eth_getLogs returned a non-list result")
        return result


def iter_doc_attested_chunks(
    rpc: EthereumRpc,
    address: str,
    from_block: int,
    to_block: int,
    *,
    chunk_size: int = 2_000,
    doc_chain_id: str | None = None,
    attester: str | None = None,
    doc_ref: int | None = None,
) -> Iterator[tuple[int, int, list[DocAttested]]]:
    """Yield decoded `DocAttested` events in inclusive block-range chunks."""
    topics = doc_attested_topics(
        doc_chain_id=doc_chain_id,
        attester=attester,
        doc_ref=doc_ref,
    )
    for start, end in block_ranges(from_block, to_block, chunk_size):
        yield from _iter_doc_attested_range(rpc, address, start, end, topics)


def block_ranges(from_block: int, to_block: int, chunk_size: int) -> Iterator[tuple[int, int]]:
    """Split an inclusive block range into provider-friendly chunks."""
    if from_block < 0 or to_block < 0:
        raise ValueError("block numbers must not be negative")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    start = from_block
    while start <= to_block:
        end = min(start + chunk_size - 1, to_block)
        yield start, end
        start = end + 1


def _iter_doc_attested_range(
    rpc: EthereumRpc,
    address: str,
    from_block: int,
    to_block: int,
    topics: list[str | None],
) -> Iterator[tuple[int, int, list[DocAttested]]]:
    try:
        logs = rpc.get_logs(address, from_block, to_block, topics)
    except RpcError:
        if from_block >= to_block:
            raise
        mid_block = (from_block + to_block) // 2
        yield from _iter_doc_attested_range(rpc, address, from_block, mid_block, topics)
        yield from _iter_doc_attested_range(rpc, address, mid_block + 1, to_block, topics)
        return
    yield from_block, to_block, [decode_doc_attested_log(log) for log in logs]


def doc_attested_topics(
    *,
    doc_chain_id: str | None = None,
    attester: str | None = None,
    doc_ref: int | None = None,
) -> list[str | None]:
    """Build an `eth_getLogs` topic filter for `DocAttested`."""
    return [
        DOC_ATTESTED_EVENT_TOPIC0,
        normalize_bytes32(doc_chain_id) if doc_chain_id is not None else None,
        topic_address(attester) if attester is not None else None,
        topic_uint64(doc_ref) if doc_ref is not None else None,
    ]


def normalize_address(address: str) -> str:
    body = _hex_body(address, "address")
    if len(body) != 40:
        raise ValueError("address must be 20 bytes")
    return "0x" + body


def normalize_bytes32(value: str) -> str:
    body = _hex_body(value, "bytes32")
    if len(body) != 64:
        raise ValueError("bytes32 value must be 32 bytes")
    return "0x" + body


def topic_address(address: str) -> str:
    return "0x" + ("0" * 24) + normalize_address(address)[2:]


def topic_uint64(value: int) -> str:
    if value < 0 or value > 2**64 - 1:
        raise ValueError("doc_ref must fit uint64")
    return "0x" + format(value, "064x")


def _hex_body(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{field} must be a 0x-prefixed hex string")
    body = value[2:].lower()
    try:
        int(body or "0", 16)
    except ValueError as exc:
        raise ValueError(f"{field} contains non-hex characters") from exc
    return body
