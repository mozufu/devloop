"""Release-time host binding generation through upstream schema reflection.

The generated descriptors describe fields, not acceptance semantics. Runtime
validation still uses typed native helper calls. No source-language parser here.
"""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
# alias -> (package directory, module, type names)
CONTRACTS = {
    "spec": ("contracts/dev-spec/v1", "schema", ["Value", "Observation", "Predicate", "Acceptance", "Requirement", "Spec"]),
    "execution": ("contracts/execution/v1", "schema", ["Declaration", "Gate", "Identity", "Evidence", "Execution"]),
    "consumer": ("contracts/consumer/v1", "schema", ["Consumer"]),
    "policy": ("contracts/execution/v1", "policy", ["Declaration", "Gate", "Policy"]),
}


def main():
    out = {}
    for alias, (package, module, types) in CONTRACTS.items():
        with tempfile.TemporaryDirectory(prefix="devloop-bindings-") as tmp:
            tmp = Path(tmp)
            # Quoted imports resolve downward only; a throwaway package reaches
            # the contract the way any dependent package does.
            (tmp / "zutai.zti").write_text(
                '{ formatVersion = 1; name = "devloop_bindings"; compilerCompatibility = "0.1.0";'
                ' modules = [ { name = "reflect"; path = "reflect.zt"; }; ];'
                ' dependencies = [ { alias = "contract"; path = ' + json.dumps(str(ROOT / package)) + '; }; ]; }\n'
            )
            (tmp / "reflect.zt").write_text(
                'r ::= import stdlib.reflect;\n'
                's ::= import contract.' + module + ';\n'
                '{' + "".join(name + '=r.schemaFields s.' + name + ';' for name in types) + '}\n'
            )
            result = subprocess.run(["zutai-cli", "json", str(tmp / "reflect.zt")], text=True, capture_output=True, check=True)
            out[alias] = json.loads(result.stdout)
    (ROOT / "devloop/bindings.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
