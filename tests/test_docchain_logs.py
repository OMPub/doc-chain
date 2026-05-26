import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from reference.docchain.abi import DOC_ATTESTED_EVENT_TOPIC0
from reference.docchain.indexer import (
    BlockRangeLimitError,
    EthereumRpc,
    RateLimitError,
    RpcError,
    block_ranges,
    doc_attested_topics,
    iter_doc_attested_chunks,
)
from reference.docchain.logs import decode_doc_attested_log
from reference.docchain.model import normalize_doc_attested


DOC_CHAIN_ID = "0x" + "11" * 32
ATTESTER = "0x" + "22" * 20
SUBMITTER = "0x" + "33" * 20
PARENT_HASH = "0x" + "44" * 32
DOC_BLOCK_HASH = "0x" + "55" * 32
CONTENT_HASH = "0x" + "66" * 32
URI_HASH = "0x" + "77" * 32
TX_HASH = "0x" + "88" * 32
ETHEREUM_BLOCK_HASH = "0x" + "99" * 32


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def http_error(code: int, payload: dict[str, object], headers: dict[str, str] | None = None):
    return urllib.error.HTTPError(
        "https://example.invalid",
        code,
        "error",
        headers or {},
        io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


def word(hex_body: str) -> str:
    return hex_body.rjust(64, "0")


def raw_log(uri: str = "ar://example") -> dict[str, object]:
    uri_hex = uri.encode("utf-8").hex()
    uri_padding = "0" * ((64 - len(uri_hex) % 64) % 64)
    data = (
        word(SUBMITTER[2:])
        + PARENT_HASH[2:]
        + DOC_BLOCK_HASH[2:]
        + CONTENT_HASH[2:]
        + URI_HASH[2:]
        + word(hex(6 * 32)[2:])
        + word(hex(len(uri.encode("utf-8")))[2:])
        + uri_hex
        + uri_padding
    )
    return {
        "address": "0x" + "aa" * 20,
        "blockHash": ETHEREUM_BLOCK_HASH,
        "blockNumber": "0x7b",
        "data": "0x" + data,
        "logIndex": "0x2",
        "topics": [
            DOC_ATTESTED_EVENT_TOPIC0,
            DOC_CHAIN_ID,
            "0x" + word(ATTESTER[2:]),
            "0x" + word("7"),
        ],
        "transactionHash": TX_HASH,
    }


class DocChainLogsTest(unittest.TestCase):
    def test_decode_doc_attested_log(self) -> None:
        event = decode_doc_attested_log(raw_log())

        self.assertEqual(event.doc_chain_id, DOC_CHAIN_ID)
        self.assertEqual(event.attester, ATTESTER)
        self.assertEqual(event.doc_ref, 7)
        self.assertEqual(event.submitter, SUBMITTER)
        self.assertEqual(event.parent_hash, PARENT_HASH)
        self.assertEqual(event.block_hash, DOC_BLOCK_HASH)
        self.assertEqual(event.content_hash, CONTENT_HASH)
        self.assertEqual(event.uri_hash, URI_HASH)
        self.assertEqual(event.uri, "ar://example")
        self.assertEqual(event.block_number, 123)
        self.assertEqual(event.transaction_hash, TX_HASH)
        self.assertEqual(event.log_index, 2)
        self.assertEqual(event.ethereum_block_hash, ETHEREUM_BLOCK_HASH)

    def test_decode_empty_uri(self) -> None:
        self.assertEqual(decode_doc_attested_log(raw_log("")).uri, "")

    def test_normalize_decoded_mapping_keeps_existing_shape(self) -> None:
        event = normalize_doc_attested(
            {
                "docChainId": DOC_CHAIN_ID,
                "attester": ATTESTER,
                "docRef": "7",
                "submitter": SUBMITTER,
                "parentHash": PARENT_HASH,
                "blockHash": DOC_BLOCK_HASH,
                "contentHash": CONTENT_HASH,
                "uriHash": URI_HASH,
                "uri": "ar://example",
                "blockNumber": "123",
                "transactionHash": TX_HASH,
                "logIndex": "2",
            }
        )
        self.assertEqual(event.block_hash, DOC_BLOCK_HASH)
        self.assertEqual(event.ethereum_block_hash, "")

    def test_topic_filters(self) -> None:
        self.assertEqual(
            doc_attested_topics(doc_chain_id=DOC_CHAIN_ID, attester=ATTESTER, doc_ref=7),
            [
                DOC_ATTESTED_EVENT_TOPIC0,
                DOC_CHAIN_ID,
                "0x" + word(ATTESTER[2:]),
                "0x" + word("7"),
            ],
        )

    def test_block_ranges_are_inclusive(self) -> None:
        self.assertEqual(list(block_ranges(10, 15, 3)), [(10, 12), (13, 15)])

    def test_iter_doc_attested_chunks_decodes_rpc_logs(self) -> None:
        class FakeRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((address, from_block, to_block, topics))
                return [raw_log()]

        rpc = FakeRpc()
        chunks = list(iter_doc_attested_chunks(rpc, "0x" + "aa" * 20, 10, 11, chunk_size=2))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0:2], (10, 11))
        self.assertEqual(chunks[0][2][0].block_number, 123)
        self.assertEqual(rpc.calls[0][0], "0x" + "aa" * 20)

    def test_iter_doc_attested_chunks_splits_failed_ranges(self) -> None:
        class RangeLimitedRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((from_block, to_block))
                if to_block - from_block + 1 > 10:
                    raise RpcError("range too large")
                return []

        rpc = RangeLimitedRpc()
        chunks = list(iter_doc_attested_chunks(rpc, "0x" + "aa" * 20, 100, 119))

        self.assertEqual(chunks, [(100, 109, []), (110, 119, [])])
        self.assertEqual(rpc.calls, [(100, 119), (100, 109), (110, 119)])

    def test_iter_doc_attested_chunks_does_not_split_rate_limits(self) -> None:
        class RateLimitedRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((from_block, to_block))
                raise RateLimitError("too many requests")

        rpc = RateLimitedRpc()
        with self.assertRaises(RateLimitError):
            list(iter_doc_attested_chunks(rpc, "0x" + "aa" * 20, 100, 119))
        self.assertEqual(rpc.calls, [(100, 119)])

    def test_iter_doc_attested_chunks_honors_provider_block_range_limit(self) -> None:
        class RangeLimitedRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((from_block, to_block))
                if to_block - from_block + 1 > 10:
                    raise BlockRangeLimitError("up to a 10 block range", max_block_range=10)
                return []

        rpc = RangeLimitedRpc()
        chunks = list(iter_doc_attested_chunks(rpc, "0x" + "aa" * 20, 100, 119))

        self.assertEqual(chunks, [(100, 109, []), (110, 119, [])])
        self.assertEqual(rpc.calls, [(100, 119), (100, 109), (110, 119)])

    def test_rpc_retries_json_rpc_rate_limit_errors(self) -> None:
        calls = [
            FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": 429, "message": "compute units per second"},
                }
            ),
            FakeResponse({"jsonrpc": "2.0", "id": 1, "result": "0x7b"}),
        ]

        with patch("reference.docchain.indexer.time.sleep") as sleep:
            with patch("reference.docchain.indexer.random.uniform", return_value=0):
                with patch("reference.docchain.indexer.urllib.request.urlopen", side_effect=calls):
                    self.assertEqual(EthereumRpc("https://example.invalid").block_number(), 123)
        sleep.assert_called_once()

    def test_rpc_retries_http_429_with_retry_after(self) -> None:
        calls = [
            http_error(
                429,
                {"jsonrpc": "2.0", "id": 1, "error": {"code": 429, "message": "limited"}},
                headers={"Retry-After": "9"},
            ),
            FakeResponse({"jsonrpc": "2.0", "id": 1, "result": "0x7b"}),
        ]

        with patch("reference.docchain.indexer.time.sleep") as sleep:
            with patch("reference.docchain.indexer.urllib.request.urlopen", side_effect=calls):
                self.assertEqual(EthereumRpc("https://example.invalid").block_number(), 123)
        sleep.assert_called_once_with(9.0)

    def test_rpc_surfaces_provider_block_range_limit_from_json_rpc_error(self) -> None:
        response = FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32600,
                    "message": "Under the Free tier plan, you can make eth_getLogs "
                    "requests with up to a 10 block range.",
                },
            }
        )

        with patch("reference.docchain.indexer.urllib.request.urlopen", return_value=response):
            with self.assertRaises(BlockRangeLimitError) as raised:
                EthereumRpc("https://example.invalid").get_logs(
                    "0x" + "aa" * 20,
                    100,
                    119,
                    doc_attested_topics(doc_chain_id=DOC_CHAIN_ID),
                )
        self.assertEqual(raised.exception.max_block_range, 10)

    def test_rpc_surfaces_provider_block_range_limit_from_http_error(self) -> None:
        error = http_error(
            400,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32600,
                    "message": "eth_getLogs accepts up to a 1,000 block range",
                },
            },
        )

        with patch("reference.docchain.indexer.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(BlockRangeLimitError) as raised:
                EthereumRpc("https://example.invalid").get_logs(
                    "0x" + "aa" * 20,
                    100,
                    119,
                    doc_attested_topics(doc_chain_id=DOC_CHAIN_ID),
                )
        self.assertEqual(raised.exception.max_block_range, 1000)

    def test_get_logs_rejects_non_list_result(self) -> None:
        response = FakeResponse({"jsonrpc": "2.0", "id": 1, "result": {"not": "logs"}})

        with patch("reference.docchain.indexer.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(RpcError, "non-list"):
                EthereumRpc("https://example.invalid").get_logs(
                    "0x" + "aa" * 20,
                    100,
                    101,
                    doc_attested_topics(),
                )


if __name__ == "__main__":
    unittest.main()
