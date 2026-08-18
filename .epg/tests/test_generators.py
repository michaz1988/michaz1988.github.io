import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


EPG_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EPG_DIR))

import make_guide
import make_lists
import validate_outputs


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class FakeClient:
    def get(self, url, timeout, **kwargs):
        return FakeResponse({"ok": True})


class GeneratorTests(unittest.TestCase):
    def test_json_request_helper(self):
        self.assertEqual(
            make_guide.request_json(FakeClient(), "get", "https://example.test"),
            {"ok": True},
        )

    def test_stbemu_entries_are_normalized_and_deduplicated(self):
        values = {}
        make_lists.add_stbemu_mac(values, "http://example.test:80", "AA:BB")
        make_lists.add_stbemu_mac(values, "http://example.test/c", "AA:BB")
        self.assertEqual(values, {"http://example.test/c": ["AA:BB"]})

    def test_release_outputs_validate_together(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            guide = b'<?xml version="1.0"?><tv><channel id="one"/></tv>'
            (output / "guide.xml").write_bytes(guide)
            with gzip.open(output / "guide.xml.gz", "wb") as handle:
                handle.write(guide)
            (output / "maclist.json").write_text(
                json.dumps({"http://example.test/c": ["AA:BB"]}),
                encoding="utf-8",
            )
            (output / "xtreamlist.json").write_text(
                json.dumps({"regions": ["DE"], "urls": [{"url": "x"}]}),
                encoding="utf-8",
            )
            validate_outputs.validate_outputs(output)


if __name__ == "__main__":
    unittest.main()
