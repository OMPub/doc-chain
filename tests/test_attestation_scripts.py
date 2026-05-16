import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _docchain_script import subprocess_error_detail
from prepare_attestation import typed_data_for_attestation
from submit_attestation import attest_doc_calldata


class AttestationScriptsTest(unittest.TestCase):
    def test_typed_data_shape_matches_contract_domain(self) -> None:
        attestation = {
            "attester": "0x1111111111111111111111111111111111111111",
            "docBlock": {
                "docChainId": "0x" + "22" * 32,
                "docRef": 7,
                "parentHash": "0x" + "33" * 32,
                "contentHash": "0x" + "44" * 32,
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

    def test_attest_doc_calldata_matches_foundry_encoding(self) -> None:
        attestation = {
            "attester": "0x1111111111111111111111111111111111111111",
            "docBlock": {
                "docChainId": "0x" + "22" * 32,
                "docRef": 7,
                "parentHash": "0x" + "33" * 32,
                "contentHash": "0x" + "44" * 32,
            },
            "uri": "ipfs://example",
            "deadline": 123,
        }

        self.assertEqual(
            attest_doc_calldata(attestation, "0x1234"),
            "0x827b0644"
            "0000000000000000000000000000000000000000000000000000000000000040"
            "0000000000000000000000000000000000000000000000000000000000000160"
            "0000000000000000000000001111111111111111111111111111111111111111"
            "2222222222222222222222222222222222222222222222222222222222222222"
            "0000000000000000000000000000000000000000000000000000000000000007"
            "3333333333333333333333333333333333333333333333333333333333333333"
            "4444444444444444444444444444444444444444444444444444444444444444"
            "00000000000000000000000000000000000000000000000000000000000000e0"
            "000000000000000000000000000000000000000000000000000000000000007b"
            "000000000000000000000000000000000000000000000000000000000000000e"
            "697066733a2f2f6578616d706c65000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000002"
            "1234000000000000000000000000000000000000000000000000000000000000",
        )

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
