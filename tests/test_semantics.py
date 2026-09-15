"""Real native helper tests; requires the installed pinned compiler/runtime."""
import copy
from pathlib import Path
import unittest
from devloop.core import canonical, decode, native, zti
from devloop.cli import structural_execution


class Semantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = decode(Path("examples/queue.zti").read_text())
        cls.execution = structural_execution([{"id": "queue", "mode": "automated", "observations": [{"id": "depth", "kind": "int"}]}])

    def check(self, spec, execution=None, mode="structure"):
        return native(canonical(zti(spec)), execution or self.execution, mode)

    def test_identity_reference_and_predicate_refusals(self):
        self.assertEqual(self.check(self.spec), [])
        cases = [
            ("duplicate requirement", lambda s: s["requirements"].append(copy.deepcopy(s["requirements"][0]))),
            ("duplicate acceptance", lambda s: s["acceptance"].append(copy.deepcopy(s["acceptance"][0]))),
            ("dangling reference", lambda s: s["requirements"][0].update(acceptance=["missing"])),
            ("uncovered", lambda s: s["requirements"][0].update(acceptance=[])),
            ("unknown predicate", lambda s: s["predicates"][0].update(kind="shell")),
            ("empty all", lambda s: s["predicates"][0].update(kind="all")),
            ("empty any", lambda s: s["predicates"][0].update(kind="any")),
            ("cyclic", lambda s: s["predicates"][0].update(kind="all", members=["P1"])),
            ("missing gate", lambda s: s["acceptance"][0].update(gate="missing")),
            ("mode mismatch", lambda s: s["acceptance"][0].update(mode="human")),
            ("reversed bounds", lambda s: s["predicates"][0].update(lower=65)),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                spec = copy.deepcopy(self.spec)
                mutate(spec)
                self.assertTrue(self.check(spec))

    def evidence(self, number=64):
        execution = copy.deepcopy(self.execution)
        execution.update(now=100, ready=True, approved=True)
        execution["identity"] = {k: k for k in execution["identity"]}
        evidence = {"acceptance": "A1", "gate": "queue", "mode": "automated", "identity": copy.deepcopy(execution["identity"]), "observedAt": 100, "expiresAt": 101, "passed": True, "observer": "real-native-test-input", "observations": [{"id": "depth", "value": {"kind": "int", "intValue": number, "boolValue": False, "textValue": ""}}]}
        execution["evidence"] = [evidence]
        return execution

    def test_bounds_types_missing_and_freshness(self):
        self.assertEqual(self.check(self.spec, self.evidence(), "completion"), [])
        self.assertTrue(self.check(self.spec, self.evidence(65), "completion"))
        exclusive = copy.deepcopy(self.spec)
        exclusive["predicates"][0]["upperInclusive"] = False
        self.assertTrue(self.check(exclusive, self.evidence(64), "completion"))
        self.assertEqual(self.check(exclusive, self.evidence(63), "completion"), [])
        for kind in ("code", "requirements", "helper", "policy", "inputs", "target", "image", "epoch"):
            execution = self.evidence()
            execution["identity"][kind] = "changed"
            with self.subTest(identity=kind):
                self.assertTrue(self.check(self.spec, execution, "completion"))
        mutations = [
            lambda e: e.update(now=101),
            lambda e: e.update(now=99),
            lambda e: e.update(ready=False),
            lambda e: e.update(approved=False),
            lambda e: e.update(evidence=[]),
            lambda e: e["evidence"][0].update(passed=False),
            lambda e: e["evidence"][0].update(observations=[]),
            lambda e: e["evidence"][0]["observations"][0]["value"].update(kind="text"),
        ]
        for mutation in mutations:
            execution = self.evidence()
            mutation(execution)
            self.assertTrue(self.check(self.spec, execution, "completion"))

    def test_typed_equality_and_composition(self):
        spec = copy.deepcopy(self.spec)
        spec["predicates"][0].update(kind="equal", expected={"kind": "int", "intValue": 64, "boolValue": False, "textValue": ""})
        self.assertEqual(self.check(spec, self.evidence(), "completion"), [])
        self.assertTrue(self.check(spec, self.evidence(63), "completion"))
        group = copy.deepcopy(spec["predicates"][0])
        group.update(id="P2", kind="all", members=["P1"])
        spec["predicates"].append(group)
        spec["acceptance"][0]["predicate"] = "P2"
        self.assertEqual(self.check(spec, self.evidence(), "completion"), [])
        group["kind"] = "any"
        self.assertTrue(self.check(spec, self.evidence(63), "completion"))

    def test_latest_entry_decides_each_obligation(self):
        # A later failing run must not be satisfied by an earlier passing one.
        passing = self.evidence()["evidence"][0]
        failing = copy.deepcopy(passing)
        failing["observations"][0]["value"]["intValue"] = 65
        execution = self.evidence()
        execution["evidence"] = [passing, failing]
        self.assertTrue(self.check(self.spec, execution, "completion"))
        execution["evidence"] = [failing, passing]
        self.assertEqual(self.check(self.spec, execution, "completion"), [])
        # An entry for another obligation never stands in for this one.
        other = copy.deepcopy(passing)
        other["acceptance"] = "A2"
        execution["evidence"] = [passing, other]
        self.assertEqual(self.check(self.spec, execution, "completion"), [])


if __name__ == "__main__":
    unittest.main()
