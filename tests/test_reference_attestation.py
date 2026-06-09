import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from reference.docchain.attestation import (
    attest_batch_calldata,
    attest_doc_calldata,
    doc_block_hash_payload,
    doc_block_hash_with_cast,
    prepare_attestation,
    sign_prepared_with_cast,
    typed_data_for_attestation,
)

BATCH_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "attest-batch-calldata.json"
)


class ReferenceAttestationTest(unittest.TestCase):
    def test_typed_data_shape_includes_on_behalf_of(self):
        typed_data = typed_data_for_attestation(
            chain_id=1,
            contract_address="0x" + "aa" * 20,
            attestation=sample_attestation(),
        )

        self.assertEqual(typed_data["domain"]["version"], "1")
        self.assertIn(
            {"name": "onBehalfOf", "type": "address"},
            typed_data["types"]["DocAttestation"],
        )

    def test_calldata_starts_with_attest_doc_selector(self):
        self.assertTrue(attest_doc_calldata(sample_attestation(), "0x1234").startswith("0xd2b85e96"))

    def test_doc_block_hash_payload_matches_contract_hash_struct_input(self):
        self.assertEqual(
            doc_block_hash_payload(sample_attestation()["docBlock"]),
            "0xb84212102d711af6fc7ae9fa3e37753befb8b25762a552631b0e9ff9e8d07894"
            "3333333333333333333333333333333333333333333333333333333333333333"
            "0000000000000000000000000000000000000000000000000000000000000007"
            "4444444444444444444444444444444444444444444444444444444444444444"
            "5555555555555555555555555555555555555555555555555555555555555555",
        )

    def test_doc_block_hash_with_cast_normalizes_output(self):
        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[1], "keccak")
            return subprocess.CompletedProcess(command, 0, stdout="0X" + "AB" * 32 + "\n", stderr="")

        self.assertEqual(
            doc_block_hash_with_cast(sample_attestation()["docBlock"], run=fake_run),
            "0x" + "ab" * 32,
        )

    def test_batch_calldata_matches_live_transaction_fixture(self):
        # The fixture calldata was broadcast on Sepolia and accepted by the
        # deployed contract release 2; the encoder must reproduce it exactly.
        fixture = json.loads(BATCH_FIXTURE_PATH.read_text(encoding="utf-8"))
        items = list(zip(fixture["attestations"], fixture["signatures"]))

        self.assertEqual(attest_batch_calldata(items), fixture["calldata"])

    def test_batch_calldata_starts_with_selector(self):
        calldata = attest_batch_calldata([(sample_attestation(), "0x1234")])

        self.assertTrue(calldata.startswith("0x7fba5650"))

    def test_batch_calldata_rejects_empty(self):
        with self.assertRaises(ValueError):
            attest_batch_calldata([])

    def test_batch_single_item_reuses_attest_doc_tuple_encoding(self):
        attestation = sample_attestation()
        signature = "0x" + "ab" * 65

        single = attest_doc_calldata(attestation, signature)
        batch = attest_batch_calldata([(attestation, signature)])

        # attestDoc layout: selector + two head words + tuple tail + bytes tail.
        # The tuple tail (8 fixed words) must appear unchanged inside the batch.
        tuple_tail_words = single[10 + 64 * 2 : 10 + 64 * 2 + 8 * 64]
        self.assertIn(tuple_tail_words, batch)

    def test_batch_calldata_round_trips_structurally(self):
        attestations = []
        signatures = []
        for index, uri in enumerate(["", "ar://tx/abc123", "x" * 100]):
            attestation = json.loads(json.dumps(sample_attestation()))
            attestation["uri"] = uri
            attestation["docBlock"]["docRef"] = 20260420000000 + index * 1_000_000
            attestations.append(attestation)
            signatures.append("0x" + ("0%d" % (index + 1)) * 65)

        calldata = attest_batch_calldata(list(zip(attestations, signatures)))
        body = calldata[10:]

        def word(i):
            return body[i * 64 : (i + 1) * 64]

        attestations_start = int(word(0), 16) // 32
        signatures_start = int(word(1), 16) // 32
        self.assertEqual(int(word(attestations_start), 16), 3)
        self.assertEqual(int(word(signatures_start), 16), 3)

        for k in range(3):
            element = attestations_start + 1 + int(word(attestations_start + 1 + k), 16) // 32
            self.assertEqual("0x" + word(element + 2), attestations[k]["docBlock"]["docChainId"])
            self.assertEqual(int(word(element + 3), 16), attestations[k]["docBlock"]["docRef"])
            uri_word = element + int(word(element + 6), 16) // 32
            uri_length = int(word(uri_word), 16)
            uri_hex = body[(uri_word + 1) * 64 : (uri_word + 1) * 64 + uri_length * 2]
            self.assertEqual(bytes.fromhex(uri_hex).decode("utf-8"), attestations[k]["uri"])

            signature_word = signatures_start + 1 + int(word(signatures_start + 1 + k), 16) // 32
            signature_length = int(word(signature_word), 16)
            signature_hex = body[
                (signature_word + 1) * 64 : (signature_word + 1) * 64 + signature_length * 2
            ]
            self.assertEqual("0x" + signature_hex, signatures[k])

    def test_sign_prepared_checks_private_key_address(self):
        def fake_run(command, check, capture_output, text):
            if command[1:3] == ["wallet", "address"]:
                return subprocess.CompletedProcess(command, 0, stdout="0x1111111111111111111111111111111111111111\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="0x1234\n", stderr="")

        prepared = prepare_attestation(
            chain_id=1,
            contract_address="0x" + "aa" * 20,
            attester="0x" + "11" * 20,
            doc_chain_id="0x" + "33" * 32,
            doc_ref=7,
            parent_hash="0x" + "44" * 32,
            content_hash="0x" + "55" * 32,
            deadline=123,
        )

        with patch.dict("os.environ", {"PRIVATE_KEY": "0xabc"}, clear=False):
            self.assertEqual(sign_prepared_with_cast(prepared, run=fake_run), "0x1234")


def sample_attestation():
    return {
        "attester": "0x" + "11" * 20,
        "onBehalfOf": "0x" + "22" * 20,
        "docBlock": {
            "docChainId": "0x" + "33" * 32,
            "docRef": 7,
            "parentHash": "0x" + "44" * 32,
            "contentHash": "0x" + "55" * 32,
        },
        "uri": "",
        "deadline": 123,
    }


if __name__ == "__main__":
    unittest.main()
