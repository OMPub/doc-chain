import subprocess
import unittest
from unittest.mock import patch

from reference.docchain.attestation import (
    attest_doc_calldata,
    doc_block_hash_payload,
    doc_block_hash_with_cast,
    prepare_attestation,
    sign_prepared_with_cast,
    typed_data_for_attestation,
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
