import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from index_events import _checkpoint_from_block, _write_checkpoint


class IndexEventsScriptTest(unittest.TestCase):
    def test_checkpoint_records_and_validates_scan_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "nested" / "checkpoint.json"
            args = Namespace(
                attester="0x" + "22" * 20,
                doc_chain_id="0x" + "11" * 32,
                doc_ref=7,
            )
            config = {"address": "0x" + "aa" * 20}

            _write_checkpoint(str(checkpoint), str(config["address"]), args, 123)

            raw = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(raw["last_block"], 123)
            self.assertEqual(raw["doc_chain_id"], args.doc_chain_id)
            self.assertEqual(raw["attester"], args.attester)
            self.assertEqual(raw["doc_ref"], 7)
            self.assertEqual(_checkpoint_from_block(str(checkpoint), config, args), 124)

    def test_checkpoint_rejects_mismatched_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "checkpoint.json"
            checkpoint.write_text(
                json.dumps(
                    {
                        "address": "0x" + "aa" * 20,
                        "doc_chain_id": "",
                        "attester": "",
                        "doc_ref": None,
                        "last_block": 123,
                    }
                ),
                encoding="utf-8",
            )
            args = Namespace(attester=None, doc_chain_id="0x" + "11" * 32, doc_ref=None)
            config = {"address": "0x" + "aa" * 20}

            with self.assertRaisesRegex(ValueError, "doc_chain_id"):
                _checkpoint_from_block(str(checkpoint), config, args)


if __name__ == "__main__":
    unittest.main()
