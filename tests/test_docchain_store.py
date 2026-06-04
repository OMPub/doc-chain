import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from reference.docchain.abi import DOC_ATTESTED_EVENT_TOPIC0
from reference.docchain.store import (
    ScanContext,
    append_event_cache,
    build_docchain_index,
    checkpoint_from_block,
    dedupe_events,
    event_key,
    load_event_cache,
    update_event_cache,
    write_checkpoint,
)
from reference.docchain.model import DocAttested


DOC_CHAIN_ID = "0x" + "11" * 32
ATTESTER = "0x" + "22" * 20
ON_BEHALF_OF = "0x" + "29" * 20
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
        word(ON_BEHALF_OF[2:])
        + word(SUBMITTER[2:])
        + PARENT_HASH[2:]
        + DOC_BLOCK_HASH[2:]
        + CONTENT_HASH[2:]
        + URI_HASH[2:]
        + word(hex(7 * 32)[2:])
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
    def test_missing_checkpoint_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "missing.json"

            self.assertIsNone(
                checkpoint_from_block(checkpoint, ScanContext(address="0x" + "aa" * 20))
            )

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

    def test_checkpoint_rejects_network_and_chain_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            write_checkpoint(
                checkpoint,
                ScanContext(address="0x" + "aa" * 20, chain_id=1, network="mainnet"),
                123,
            )

            with self.assertRaisesRegex(ValueError, "chain_id"):
                checkpoint_from_block(
                    checkpoint,
                    ScanContext(address="0x" + "aa" * 20, chain_id=11155111, network="mainnet"),
                )
            with self.assertRaisesRegex(ValueError, "network"):
                checkpoint_from_block(
                    checkpoint,
                    ScanContext(address="0x" + "aa" * 20, chain_id=1, network="sepolia"),
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

    def test_event_cache_loads_camel_case_records_and_ignores_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            cache.write_text(
                "\n"
                + json.dumps(
                    {
                        "docChainId": DOC_CHAIN_ID,
                        "attester": ATTESTER,
                        "docRef": "7",
                        "onBehalfOf": ON_BEHALF_OF,
                        "submitter": SUBMITTER,
                        "parentHash": PARENT_HASH,
                        "blockHash": DOC_BLOCK_HASH,
                        "contentHash": CONTENT_HASH,
                        "uriHash": URI_HASH,
                        "uri": "ar://example",
                        "blockNumber": "123",
                        "transactionHash": TX_HASH,
                        "logIndex": "2",
                        "ethereumBlockHash": ETHEREUM_BLOCK_HASH,
                    }
                )
                + "\n\n",
                encoding="utf-8",
            )

            events = load_event_cache(cache)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].block_hash, DOC_BLOCK_HASH)
            self.assertEqual(events[0].on_behalf_of, ON_BEHALF_OF)
            self.assertEqual(events[0].ethereum_block_hash, ETHEREUM_BLOCK_HASH)

    def test_event_cache_defaults_legacy_on_behalf_of_to_zero_address(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            cache.write_text(
                json.dumps(
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
                + "\n",
                encoding="utf-8",
            )

            events = load_event_cache(cache)

            self.assertEqual(events[0].on_behalf_of, "0x" + "00" * 20)

    def test_event_cache_rejects_non_object_lines_with_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            append_event_cache(cache, [make_event()])
            with cache.open("a", encoding="utf-8") as stream:
                stream.write("[]\n")

            with self.assertRaisesRegex(ValueError, "line 2"):
                load_event_cache(cache)

    def test_event_cache_rejects_malformed_json_with_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            append_event_cache(cache, [make_event()])
            with cache.open("a", encoding="utf-8") as stream:
                stream.write('{"docChainId":\n')

            with self.assertRaisesRegex(ValueError, "line 2 is invalid JSON"):
                load_event_cache(cache)

    def test_event_cache_rejects_invalid_records_with_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Path(tmpdir) / "events.jsonl"
            append_event_cache(cache, [make_event()])
            with cache.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"docChainId": DOC_CHAIN_ID}) + "\n")

            with self.assertRaisesRegex(ValueError, "line 2 is invalid"):
                load_event_cache(cache)

    def test_dedupe_events_keeps_chain_order(self) -> None:
        first = make_event(block_number=10, log_index=5, transaction_hash="0x" + "b" * 64)
        second = make_event(block_number=10, log_index=3, transaction_hash="0x" + "a" * 64)
        third = make_event(block_number=11, log_index=1, transaction_hash="0x" + "c" * 64)

        deduped = dedupe_events([third, first, second, second])

        self.assertEqual([event.transaction_hash for event in deduped], [
            "0x" + "a" * 64,
            "0x" + "b" * 64,
            "0x" + "c" * 64,
        ])

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

    def test_update_event_cache_resumes_after_checkpoint(self) -> None:
        class FakeRpc:
            def __init__(self) -> None:
                self.calls = []

            def get_logs(self, address, from_block, to_block, topics):
                self.calls.append((from_block, to_block))
                return []

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            context = ScanContext(
                address="0x" + "aa" * 20,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )
            write_checkpoint(checkpoint, context, 105)
            rpc = FakeRpc()

            result = update_event_cache(
                rpc=rpc,
                address="0x" + "aa" * 20,
                cache_path=Path(tmpdir) / "events.jsonl",
                checkpoint_path=checkpoint,
                from_block=100,
                to_block=109,
                chunk_size=2,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )

            self.assertEqual(result.from_block, 106)
            self.assertEqual(rpc.calls, [(106, 107), (108, 109)])

    def test_update_event_cache_skips_rpc_when_checkpoint_is_past_target(self) -> None:
        class FakeRpc:
            def get_logs(self, address, from_block, to_block, topics):
                raise AssertionError("no RPC calls expected")

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            context = ScanContext(
                address="0x" + "aa" * 20,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )
            write_checkpoint(checkpoint, context, 109)

            result = update_event_cache(
                rpc=FakeRpc(),
                address="0x" + "aa" * 20,
                cache_path=Path(tmpdir) / "events.jsonl",
                checkpoint_path=checkpoint,
                from_block=100,
                to_block=109,
                chunk_size=2,
                doc_chain_id=DOC_CHAIN_ID,
                chain_id=11155111,
                network="sepolia",
            )

            self.assertEqual(result.from_block, 110)
            self.assertEqual(result.last_scanned_block, 109)
            self.assertEqual(result.chunk_count, 0)

    def test_update_event_cache_does_not_checkpoint_failed_cache_append(self) -> None:
        class FakeRpc:
            def get_logs(self, address, from_block, to_block, topics):
                return [raw_log()]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_directory = Path(tmpdir) / "cache-is-directory"
            cache_directory.mkdir()
            checkpoint = Path(tmpdir) / "checkpoint.json"

            with self.assertRaises(IsADirectoryError):
                update_event_cache(
                    rpc=FakeRpc(),
                    address="0x" + "aa" * 20,
                    cache_path=cache_directory,
                    checkpoint_path=checkpoint,
                    from_block=100,
                    to_block=100,
                    chunk_size=1,
                    doc_chain_id=DOC_CHAIN_ID,
                )
            self.assertFalse(checkpoint.exists())

    def test_update_event_cache_reports_progress_per_chunk(self) -> None:
        class FakeRpc:
            def get_logs(self, address, from_block, to_block, topics):
                log = raw_log(doc_ref=from_block)
                log["transactionHash"] = "0x" + format(from_block, "064x")
                return [log]

        progress_calls = []
        with tempfile.TemporaryDirectory() as tmpdir:
            result = update_event_cache(
                rpc=FakeRpc(),
                address="0x" + "aa" * 20,
                cache_path=Path(tmpdir) / "events.jsonl",
                from_block=100,
                to_block=101,
                chunk_size=1,
                doc_chain_id=DOC_CHAIN_ID,
                progress=lambda start, end, matched, new_total: progress_calls.append(
                    (start, end, matched, new_total)
                ),
            )

        self.assertEqual(result.chunk_count, 2)
        self.assertEqual(progress_calls, [(100, 100, 1, 1), (101, 101, 1, 2)])

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
        self.assertEqual(index["events"][0]["onBehalfOf"], ON_BEHALF_OF)

    def test_build_docchain_index_sorts_by_doc_ref_and_dedupes(self) -> None:
        later_ref = make_event(
            doc_ref=9,
            block_number=120,
            transaction_hash="0x" + "9" * 64,
            block_hash="0x" + "9" * 64,
        )
        earlier_ref = make_event(
            doc_ref=7,
            block_number=121,
            transaction_hash="0x" + "7" * 64,
            block_hash="0x" + "7" * 64,
        )

        index = build_docchain_index(
            events=[later_ref, earlier_ref, earlier_ref],
            indexed_at="2026-05-25T00:00:00Z",
        )

        self.assertEqual(index["eventCount"], 2)
        self.assertEqual([event["docRef"] for event in index["events"]], [7, 9])
        self.assertEqual(list(index["docRefs"].keys()), ["7", "9"])

    def test_build_docchain_index_groups_multiple_candidates_for_ref(self) -> None:
        first = make_event(
            doc_ref=7,
            block_number=120,
            transaction_hash="0x" + "1" * 64,
            block_hash="0x" + "1" * 64,
            content_hash="0x" + "a" * 64,
        )
        second = make_event(
            doc_ref=7,
            block_number=121,
            transaction_hash="0x" + "2" * 64,
            block_hash="0x" + "2" * 64,
            content_hash="0x" + "b" * 64,
        )

        index = build_docchain_index(
            events=[second, first],
            indexed_at="2026-05-25T00:00:00Z",
        )

        ref = index["docRefs"]["7"]
        self.assertEqual(ref["candidateCount"], 2)
        self.assertEqual(ref["blockHashes"], ["0x" + "1" * 64, "0x" + "2" * 64])
        self.assertEqual(ref["contentHashes"], ["0x" + "a" * 64, "0x" + "b" * 64])
        self.assertEqual([event["transactionHash"] for event in ref["events"]], [
            "0x" + "1" * 64,
            "0x" + "2" * 64,
        ])


def make_event(
    *,
    doc_chain_id=DOC_CHAIN_ID,
    doc_ref=7,
    block_number=123,
    transaction_hash=TX_HASH,
    log_index=2,
    block_hash=DOC_BLOCK_HASH,
    content_hash=CONTENT_HASH,
) -> DocAttested:
    event = DocAttested(
        doc_chain_id=DOC_CHAIN_ID,
        attester=ATTESTER,
        doc_ref=doc_ref,
        on_behalf_of=ON_BEHALF_OF,
        submitter=SUBMITTER,
        parent_hash=PARENT_HASH,
        block_hash=block_hash,
        content_hash=content_hash,
        uri_hash=URI_HASH,
        uri="ar://example",
        block_number=block_number,
        transaction_hash=transaction_hash,
        log_index=log_index,
        ethereum_block_hash=ETHEREUM_BLOCK_HASH,
    )
    return replace(event, doc_chain_id=doc_chain_id)


if __name__ == "__main__":
    unittest.main()
