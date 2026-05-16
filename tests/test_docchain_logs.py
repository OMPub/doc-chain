import unittest

from reference.docchain.abi import DOC_ATTESTED_EVENT_TOPIC0
from reference.docchain.indexer import (
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


if __name__ == "__main__":
    unittest.main()
