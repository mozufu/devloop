import json
from pathlib import Path
import tempfile
import unittest
from devloop.core import Refusal, canonical, command, decode, digest, frame, helper_identity, raw_record, stored, unframe
from devloop.cli import render


class Profile(unittest.TestCase):
    def test_import_snapshot_atoms_and_first_order_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared.zti"
            shared.write_text('{ value = #ready; text = "#ready"; }')
            source = root / "author.zt"
            source.write_text('x ::= import "shared.zti"; x')
            payload = command(["devloop-zutai", "admit", str(source)]).stdout
            self.assertEqual(decode(payload), {"value": {"$atom": "ready"}, "text": "#ready"})
            shared.write_text('{ value = #changed; text = "different"; }')
            self.assertEqual(decode(payload)["value"], {"$atom": "ready"})
            for invalid in ('import "missing.zti"', '\\x. x', '{ nested = \\x. x; }'):
                source.write_text(invalid)
                with self.assertRaises(Refusal):
                    command(["devloop-zutai", "admit", str(source)])

    def test_framing_digest_and_renderer(self):
        payload = canonical(Path("examples/queue.zti").read_text())
        self.assertEqual(unframe(frame(payload)), payload)
        for body in ("", frame(payload) * 2, frame(payload) + "Extra requirement", frame(payload).replace("```zti", "```zt")):
            with self.assertRaises(Refusal):
                unframe(body)
        helper = helper_identity()
        rec = {"recordSchema": "devloop-consumer/v1", "schema": "dev-spec/v1", "bodyProfile": "fenced-zti/v1", "helper": helper, "requirementsDigest": digest(payload, helper), "admission": "test", "epoch": "unstarted", "evidence": []}
        item = {"api": "myque/v2", "id": "019a10d8-8d48-7b77-a414-f95ab7af31be", "retired": False, "body": frame(payload), "consumers": {"devloop": raw_record(rec)}}
        markdown = render(item)
        self.assertIn("Queue growth", markdown)
        self.assertNotIn("```", markdown)
        self.assertIn("pending automated gate", markdown)
        item["body"] = item["body"].replace("64", "65")
        with self.assertRaises(Refusal):
            stored(item)
        legacy = "Explanation\n```zt\n1\n```\n"
        self.assertEqual(render({"body": legacy, "consumers": {}}), legacy)
        with self.assertRaises(Refusal):
            render({"body": frame(payload), "consumers": {}})
        for key, value in (("bodyProfile", "unknown"), ("helper", "old")):
            changed = dict(rec)
            changed[key] = value
            item["consumers"]["devloop"] = raw_record(changed)
            with self.assertRaises(Refusal):
                stored(item)


if __name__ == "__main__":
    unittest.main()
