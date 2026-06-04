import sys
import subprocess
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _docchain_script import subprocess_error_detail
from prepare_attestation import prepare_attestation, typed_data_for_attestation
from submit_attestation import attest_doc_calldata


class AttestationScriptsTest(unittest.TestCase):
    def test_typed_data_shape_matches_contract_domain(self) -> None:
        attestation = {
            "attester": "0x1111111111111111111111111111111111111111",
            "onBehalfOf": "0x2222222222222222222222222222222222222222",
            "docBlock": {
                "docChainId": "0x" + "33" * 32,
                "docRef": 7,
                "parentHash": "0x" + "44" * 32,
                "contentHash": "0x" + "55" * 32,
            },
            "uri": "ipfs://example",
            "deadline": 123,
        }

        typed_data = typed_data_for_attestation(
            chain_id=11155111,
            contract_address="0xace3a26fe2f993e351a0ef74fb727cfe1029884b",
            attestation=attestation,
        )

        self.assertEqual(typed_data["primaryType"], "DocAttestation")
        self.assertEqual(typed_data["domain"]["name"], "Doc Chain")
        self.assertEqual(typed_data["domain"]["version"], "1")
        self.assertEqual(typed_data["domain"]["chainId"], 11155111)
        self.assertEqual(typed_data["message"], attestation)
        self.assertIn({"name": "onBehalfOf", "type": "address"}, typed_data["types"]["DocAttestation"])

    def test_prepare_attestation_defaults_on_behalf_of_to_zero_address(self) -> None:
        prepared = prepare_attestation(
            Namespace(
                deployment=None,
                chain_id=11155111,
                contract_address="0xace3a26fe2f993e351a0ef74fb727cfe1029884b",
                network="sepolia",
                attester="0x1111111111111111111111111111111111111111",
                on_behalf_of="0x" + "00" * 20,
                doc_chain_id="0x" + "22" * 32,
                doc_ref=7,
                parent_hash="0x" + "00" * 32,
                content_hash="0x" + "44" * 32,
                uri="",
                deadline=123,
                ttl=86400,
                out="unused.json",
            )
        )

        self.assertEqual(prepared["schema"], "doc-chain-prepared-attestation-v1")
        self.assertEqual(prepared["attestation"]["onBehalfOf"], "0x" + "00" * 20)
        self.assertEqual(prepared["typedData"]["domain"]["version"], "1")

    def test_prepare_attestation_normalizes_on_behalf_of(self) -> None:
        prepared = prepare_attestation(
            Namespace(
                deployment=None,
                chain_id=11155111,
                contract_address="0xace3a26fe2f993e351a0ef74fb727cfe1029884b",
                network="sepolia",
                attester="0x1111111111111111111111111111111111111111",
                on_behalf_of="0X2222222222222222222222222222222222222222",
                doc_chain_id="0x" + "22" * 32,
                doc_ref=7,
                parent_hash="0x" + "00" * 32,
                content_hash="0x" + "44" * 32,
                uri="",
                deadline=123,
                ttl=86400,
                out="unused.json",
            )
        )

        self.assertEqual(prepared["attestation"]["onBehalfOf"], "0x" + "22" * 20)

    def test_attest_doc_calldata_matches_foundry_encoding(self) -> None:
        attestation = {
            "attester": "0x1111111111111111111111111111111111111111",
            "onBehalfOf": "0x2222222222222222222222222222222222222222",
            "docBlock": {
                "docChainId": "0x" + "33" * 32,
                "docRef": 7,
                "parentHash": "0x" + "44" * 32,
                "contentHash": "0x" + "55" * 32,
            },
            "uri": "ipfs://example",
            "deadline": 123,
        }

        self.assertEqual(
            attest_doc_calldata(attestation, "0x1234"),
            "0xd2b85e96"
            "0000000000000000000000000000000000000000000000000000000000000040"
            "0000000000000000000000000000000000000000000000000000000000000180"
            "0000000000000000000000001111111111111111111111111111111111111111"
            "0000000000000000000000002222222222222222222222222222222222222222"
            "3333333333333333333333333333333333333333333333333333333333333333"
            "0000000000000000000000000000000000000000000000000000000000000007"
            "4444444444444444444444444444444444444444444444444444444444444444"
            "5555555555555555555555555555555555555555555555555555555555555555"
            "0000000000000000000000000000000000000000000000000000000000000100"
            "000000000000000000000000000000000000000000000000000000000000007b"
            "000000000000000000000000000000000000000000000000000000000000000e"
            "697066733a2f2f6578616d706c65000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000002"
            "1234000000000000000000000000000000000000000000000000000000000000",
        )

    def test_attest_doc_calldata_defaults_legacy_on_behalf_of_to_zero_address(self) -> None:
        attestation = {
            "attester": "0x1111111111111111111111111111111111111111",
            "docBlock": {
                "docChainId": "0x" + "33" * 32,
                "docRef": 7,
                "parentHash": "0x" + "44" * 32,
                "contentHash": "0x" + "55" * 32,
            },
            "uri": "",
            "deadline": 123,
        }

        calldata = attest_doc_calldata(attestation, "0x")

        self.assertTrue(calldata.startswith("0xd2b85e96"))
        payload = calldata[10:]
        struct_start = 2 * 64
        on_behalf_of_word = payload[struct_start + 64 : struct_start + 128]
        self.assertEqual(on_behalf_of_word, "0" * 64)

    def test_subprocess_error_detail_redacts_private_keys(self) -> None:
        error = subprocess.CalledProcessError(
            1,
            ["cast", "wallet", "sign", "--private-key", "0xabc"],
            stderr="failed with 0xabc",
        )

        with patch.dict("os.environ", {"PRIVATE_KEY": "0xabc"}, clear=False):
            self.assertEqual(subprocess_error_detail(error), "failed with <redacted>")


if __name__ == "__main__":
    unittest.main()
