"""Framing, transport, and compilation. Domain rules live exclusively in helpers."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import yaml

PROFILE = "fenced-zti/v1"
SCHEMA = "dev-spec/v1"
VERSION = "devloop-helpers/v1"
PIN = "b667e3c5018e69a3f8e39948a73a6c57c514de6e"

class Refusal(Exception):
    pass

def command(argv, data=None, check=True):
    p = subprocess.run(argv, input=data, text=True, capture_output=True)
    if check and p.returncode:
        raise Refusal(f"E_COMMAND {argv[0]}: {p.stderr.strip() or p.stdout.strip()}")
    return p

def assets():
    source = Path(__file__).resolve().parent.parent
    for root in (source, Path(sys.prefix) / "share/devloop"):
        if (root / "helpers/v1/validate.zt").is_file():
            return root
    raise Refusal("E_INSTALL: installed contracts/helpers missing")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def helper_identity():
    root = assets()
    # Package manifests decide which module each alias resolves to, so they are
    # part of the helper identity, not incidental packaging.
    files = sorted([*root.glob("contracts/**/*.zt"), *root.glob("helpers/**/*.zt"), *root.glob("contracts/**/zutai.zti"), *root.glob("helpers/**/zutai.zti")])
    return VERSION + ":" + sha(b"".join(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0" for p in files) + PIN.encode())

def zti(value):
    """Encode transport data, never execute or interpret predicates."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise Refusal("E_INT: outside signed 64-bit range")
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + "".join(zti(x) + ";" for x in value) + "]"
    if isinstance(value, dict):
        if set(value) == {"$atom"}:
            atom = value["$atom"]
            if not isinstance(atom, str) or not re.fullmatch(r"[^\W\d][\w-]*", atom):
                raise Refusal("E_ATOM")
            return "#" + atom
        if not all(isinstance(k, str) and k.isidentifier() for k in value):
            raise Refusal("E_FIELD")
        return "{" + "".join(k + "=" + zti(v) + ";" for k, v in sorted(value.items())) + "}"
    raise Refusal("E_TRANSPORT: unsupported immediate transport value")

def decode(payload):
    return json.loads(command(["devloop-zutai", "decode"], payload).stdout)

def canonical(payload):
    return command(["devloop-zutai", "format"], payload).stdout.rstrip("\n") + "\n"

def digest(payload, helper):
    return sha(b"devloop/requirements/v1\0" + SCHEMA.encode() + b"\0" + helper.encode() + b"\0" + payload.encode())

def frame(payload):
    # JSON escaped strings never contain a literal closing fence on its own line.
    if "\n```" in payload:
        raise Refusal("E_FENCE_ESCAPE")
    return "\n```zti\n" + payload + "```\n"

def unframe(body):
    match = re.fullmatch(r"\n```zti\n([\s\S]*\n)```\n", body)
    if not match or "```" in match.group(1):
        raise Refusal("E_PROFILE: exactly one canonical zti fence, no adjacent prose")
    payload = match.group(1)
    if canonical(payload) != payload:
        raise Refusal("E_CANONICAL: noncanonical payload")
    return payload

def record(item):
    raw = item.get("consumers", {}).get("devloop")
    if raw is None:
        raise Refusal("E_PROFILE: unrecorded devloop profile")
    value = yaml.safe_load(raw)
    if not isinstance(value, dict) or set(value) != {"devloop"} or not isinstance(value["devloop"], dict):
        raise Refusal("E_CONSUMER")
    return value["devloop"]

def raw_record(value):
    return yaml.safe_dump({"devloop": value}, sort_keys=False, allow_unicode=True)

def stored(item):
    if item.get("api") != "myque/v2" or item.get("retired"):
        raise Refusal("E_API: unsupported API or body unavailable after retirement")
    rec = record(item)
    from .bindings import fields
    fields("consumer", "Consumer", rec)
    if rec.get("recordSchema") != "devloop-consumer/v1":
        raise Refusal("E_CONSUMER_VERSION")
    for evidence in rec["evidence"]:
        fields("execution", "Evidence", evidence)
        fields("execution", "Identity", evidence["identity"])
    if rec.get("bodyProfile") != PROFILE or rec.get("schema") != SCHEMA:
        raise Refusal("E_PROFILE: unsupported recorded profile/schema")
    if rec.get("helper") != helper_identity():
        raise Refusal("E_HELPER: unsupported helper identity")
    payload = unframe(item["body"])
    if rec.get("requirementsDigest") != digest(payload, rec["helper"]):
        raise Refusal("E_DIGEST: requirements changed")
    if not isinstance(rec.get("admission"), str) or not rec["admission"]:
        raise Refusal("E_ADMISSION")
    spec = decode(payload)
    fields("spec", "Spec", spec)
    return payload, spec, rec

def native(payload, execution, mode="structure", acceptance=None, evidence=None):
    """Compile only trusted fixed calls with inert literals. No evaluator command."""
    root = assets()
    with tempfile.TemporaryDirectory(prefix="devloop-native-") as tmp:
        tmp = Path(tmp)
        (tmp / "spec.zti").write_text(payload)
        (tmp / "execution.zti").write_text(zti(execution))
        # Zutai resolves quoted imports downward only, so cross-tree contracts
        # are reached the way the standard library is: declared package
        # dependencies of a throwaway package holding the wrapper module.
        (tmp / "zutai.zti").write_text(
            '{ formatVersion = 1; name = "devloop_validation"; compilerCompatibility = "0.1.0";'
            ' modules = [ { name = "validate"; path = "validate.zt"; }; ];'
            ' dependencies = [ { alias = "dev_spec"; path = ' + json.dumps(str(root / "contracts/dev-spec/v1")) + '; };'
            ' { alias = "execution"; path = ' + json.dumps(str(root / "contracts/execution/v1")) + '; };'
            ' { alias = "helpers"; path = ' + json.dumps(str(root / "helpers/v1")) + '; }; ]; }\n'
        )
        source = 's ::= import dev_spec.schema;\ne ::= import execution.schema;\nh ::= import helpers.validate;\nt ::= import stdlib.text;\n'
        source += 'spec :: s.Spec = import "spec.zti";\nexecution :: e.Execution = import "execution.zti";\n'
        if mode == "structure":
            source += 'h.report (h.structure spec execution.gates)\n'
        elif mode == "completion":
            source += 'h.report (h.completion spec execution)\n'
        elif mode == "projection":
            source += 'h.report (h.projection spec)\n'
        elif mode == "bound":
            (tmp / "acceptance.zti").write_text(zti(acceptance))
            (tmp / "evidence.zti").write_text(zti(evidence))
            source += 'a :: s.Acceptance = import "acceptance.zti";\nb :: e.Evidence = import "evidence.zti";\n'
            source += 'if h.bound spec execution a b then "" else t.join "" { "E_EVIDENCE:"; a.id; }\n'
        else:
            raise Refusal("E_INTERNAL_MODE")
        (tmp / "validate.zt").write_text(source)
        binary = tmp / "validate"
        command(["zutai-cli", "compile", str(tmp / "validate.zt"), "--emit", "bin", "-o", str(binary)])
        result = json.loads(command([str(binary)]).stdout)
        if not isinstance(result, str):
            raise Refusal("E_NATIVE_PROTOCOL")
        return result.splitlines()

def require_valid(errors):
    if errors:
        raise Refusal("\n".join(errors))
