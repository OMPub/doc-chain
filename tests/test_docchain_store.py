import json
import tempfile
import unittest
from pathlib import Path

from reference.docchain.abi import DOC_ATTESTED_EVENT_TOPIC0
from reference.docchain.store import (
    ScanContext,
    append_event_cache,
    build_docchain_index,
    checkpoint_from_block,
    event_key,
    load_event_cache,
    update_event_cache,
    write_checkpoint,
)
from reference.docchain.model import DocAttested


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


def raw_log(doc_ref: int = 7) -> dict[str, object]:
    uri = "ar://example"
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
            "0x" + word(hex(doc_ref)[2:]),
        ],
        "transactionHash": TX_HASH,
    }


class DocChainStoreTest(unittest.TestCase):
    def test_checkpoint_records_and_validates_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            context = ScanContext(
                address="0x" + "aa" * 20,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )

            write_checkpoint(checkpoint, context, 123)

            self.assertEqual(checkpoint_from_block(checkpoint, context), 124)
            raw = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(raw["last_block"], 123)
            self.assertEqual(raw["chain_id"], 11155111)
            self.assertEqual(raw["network"], "sepolia")

    def test_checkpoint_rejects_context_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            write_checkpoint(checkpoint, ScanContext(address="0x" + "aa" * 20), 123)

            with self.assertRaisesRegex(ValueError, "doc_chain_id"):
                checkpoint_from_block(
                    checkpoint,
                    ScanContext(address="0x" + "aa" * 20, doc_chain_id=DOC_CHAIN_ID),
                )

    def test_event_cache_appends_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            event = make_event()

            self.assertEqual(append_event_cache(cache, [event, event]), 1)
            self.assertEqual(append_event_cache(cache, [event]), 0)

            events = load_event_cache(cache)
            self.assertEqual(len(events), 1)
            self.assertEqual(event_key(events[0]), f"{TX_HASH}:2")

    def test_update_event_cache_checkpoints_after_cache_append(self) -> None:
        class FakeRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((from_block, to_block))
                return [raw_log()]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            checkpoint = Path(tmpdir) / "checkpoint.json"
            rpc = FakeRpc()

            result = update_event_cache(
                rpc=rpc,
                address="0x" + "aa" * 20,
                cache_path=cache,
                checkpoint_path=checkpoint,
                from_block=100,
                to_block=101,
                chunk_size=2,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )

            self.assertEqual(result.chunk_count, 1)
            self.assertEqual(result.matched_event_count, 1)
            self.assertEqual(result.new_event_count, 1)
            self.assertEqual(len(load_event_cache(cache)), 1)
            self.assertEqual(
                checkpoint_from_block(
                    checkpoint,
                    ScanContext(
                        address="0x" + "aa" * 20,
                        doc_chain_id=DOC_CHAIN_ID,
                        chain_id=11155111,
                        network="sepolia",
                    ),
                ),
                102,
            )

    def test_build_docchain_index_groups_events(self) -> None:
        index = build_docchain_index(
            events=[make_event()],
            network="sepolia",
            chain_id=11155111,
            contract_address="0x" + "aa" * 20,
            doc_chain_id=DOC_CHAIN_ID,
            profile_uri="https://example.invalid/profile",
            from_block=100,
            to_block=101,
            latest_chain_block=120,
            confirmations=12,
            indexed_at="2026-05-25T00:00:00Z",
        )

        self.assertEqual(index["schema"], "docchain-index-v1")
        self.assertEqual(index["eventCount"], 1)
        self.assertIn("7", index["docRefs"])
        self.assertEqual(index["docRefs"]["7"]["candidateCount"], 1)
        self.assertEqual(index["events"][0]["transactionHash"], TX_HASH)


def make_event() -> DocAttested:
    return DocAttested(
        doc_chain_id=DOC_CHAIN_ID,
        attester=ATTESTER,
        doc_ref=7,
        submitter=SUBMITTER,
        parent_hash=PARENT_HASH,
        block_hash=DOC_BLOCK_HASH,
        content_hash=CONTENT_HASH,
        uri_hash=URI_HASH,
        uri="ar://example",
        block_number=123,
        transaction_hash=TX_HASH,
        log_index=2,
        ethereum_block_hash=ETHEREUM_BLOCK_HASH,
    )


if __name__ == "__main__":
    unittest.main()
