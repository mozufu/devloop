import argparse
import json
from pathlib import Path
import re
import sys
import time
import uuid

from .core import (PROFILE, SCHEMA, Refusal, canonical, command, decode, digest, frame,
                   helper_identity, native, raw_record, record, require_valid, sha, stored)
from .bindings import fields


def myque(args, data=None):
    return command(["myque", *args], None if data is None else json.dumps(data)).stdout


def get(id):
    try:
        if str(uuid.UUID(id)) != id:
            raise ValueError()
    except ValueError:
        raise Refusal("E_UUID: select a full canonical UUID") from None
    return json.loads(myque(["api", "get", id]))


def policy(path):
    raw = Path(path).read_bytes()
    p = json.loads(raw)
    fields("policy", "Policy", p)
    if p.get("schema") != "devloop-policy/v1" or p.get("bodyProfile") != PROFILE:
        raise Refusal("E_POLICY")
    if not isinstance(p.get("gates"), list) or not isinstance(p.get("approvalArgv"), list) or not p["approvalArgv"]:
        raise Refusal("E_POLICY: gates and explicit approvalArgv required")
    if not isinstance(p.get("codePaths"), list) or not p["codePaths"] or not all(isinstance(x, str) and x and not Path(x).is_absolute() and ".." not in Path(x).parts for x in p["codePaths"]):
        raise Refusal("E_POLICY: explicit relative codePaths required")
    for g in p["gates"]:
        fields("policy", "Gate", g)
        for declaration in g["observations"]:
            fields("policy", "Declaration", declaration)
        if g.get("mode") == "automated" and (not isinstance(g.get("argv"), list) or not g["argv"]):
            raise Refusal("E_POLICY: automated gate requires configured argv")
        if type(g.get("ttlSeconds")) is not int or g["ttlSeconds"] <= 0:
            raise Refusal("E_POLICY: positive evidence lifetime required")
    return p, sha(raw)


def context(args, p, policy_digest, rec, requirements, item, approve=False):
    files = {}
    for name in p["codePaths"]:
        path = Path(name)
        if not path.exists() or path.is_symlink():
            raise Refusal("E_CODE: missing or symlink source path")
        for file in ([path] if path.is_file() else sorted(path.rglob("*"))):
            if file.is_symlink():
                raise Refusal("E_CODE: symlink source path")
            if file.is_file():
                files[file.as_posix()] = file
    if not files:
        raise Refusal("E_CODE: empty source set")
    code = sha(b"devloop/code/v1\0" + b"".join(name.encode() + b"\0" + str(file.stat().st_mode & 0o111).encode() + b"\0" + bytes.fromhex(sha(file.read_bytes())) for name, file in sorted(files.items())))
    execution = {
        "identity": {"requirements": requirements, "helper": helper_identity(),
                     "code": code, "policy": policy_digest,
                     "inputs": sha(Path(args.inputs).read_bytes()), "target": args.target,
                     "image": args.image, "epoch": rec["epoch"]},
        "now": int(time.time()), "ready": bool(item.get("dependenciesDone", False)),
        "approved": False,
        "gates": [{"id": g["id"], "mode": g["mode"], "observations": g["observations"]} for g in p["gates"]],
        "evidence": rec["evidence"],
    }
    if approve:
        result = command(p["approvalArgv"], json.dumps({"item": item, "execution": execution}), check=False)
        if result.returncode == 0:
            answer = json.loads(result.stdout)
            execution["approved"] = answer == {"approved": True}
    return execution


def structural_execution(gates):
    return {"identity": {k: "" for k in ("requirements", "helper", "code", "policy", "inputs", "target", "image", "epoch")},
            "now": 0, "ready": False, "approved": False, "gates": gates, "evidence": []}


def put(item, rec):
    return json.loads(myque(["api", "put", item["id"], "--expected", item["revision"]],
                           {"consumers": {"devloop": raw_record(rec)}}))


def text(value):
    # Rendering prose is not interpretation. Escape Markdown markup and HTML.
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", str(value)).replace("&", "&amp;").replace("<", "&lt;")


def render(item):
    if "devloop" not in item.get("consumers", {}):
        body = item.get("body")
        if not isinstance(body, str):
            raise Refusal("E_BODY_UNAVAILABLE")
        if re.match(r"\s*(?:`{3,}|~{3,})\s*(?:zt|zti)\b", body):
            raise Refusal("E_PROFILE: unrecorded structured body")
        return body
    payload, spec, rec = stored(item)
    require_valid(native(payload, structural_execution([]), "projection"))
    lines = ["## Problem", "", text(spec["problem"]), "", "## Scope", ""]
    lines += ["- " + text(s) for s in spec["scope"]]
    lines += ["", "## Non-goals", ""] + ["- " + text(s) for s in spec["nonGoals"]]
    lines += ["", "## Requirements", ""]
    for r in spec["requirements"]:
        lines += [f"- **{text(r['id'])}**: {text(r['statement'])}",
                  "  - Acceptance: " + ", ".join(text(a) for a in r["acceptance"])]
    lines += ["", "## Acceptance obligations", ""]
    for a in spec["acceptance"]:
        entries = [e for e in rec["evidence"] if e["acceptance"] == a["id"]]
        status = "pending human observation" if a["mode"] == "human" else "pending automated gate"
        if entries:
            status = "recorded evidence (freshness and completion require current execution validation)"
        lines += [f"- **{text(a['id'])}** ({a['mode']}, {'mandatory' if a['mandatory'] else 'optional'}): {text(a['rationale'])}",
                  f"  - Gate: {text(a['gate'])}; predicate: {text(a['predicate'])}", f"  - State: {status}"]
    lines += ["", "## Expected observations and predicates", ""]
    for p in spec["predicates"]:
        if p["kind"] == "equal":
            val = p["expected"]
            expected = val[{"int": "intValue", "text": "textValue", "bool": "boolValue"}[val["kind"]]]
            # Show the value as the payload spells it, not as a host repr.
            detail = f"{p['observation']} equals {json.dumps(expected)} ({val['kind']})"
        elif p["kind"] == "bounds":
            detail = f"{p['observation']} in {'[' if p['lowerInclusive'] else '('}{p['lower']}, {p['upper']}{']' if p['upperInclusive'] else ')'} (integer)"
        else:
            detail = p["kind"] + " of: " + ", ".join(p["members"])
        lines.append(f"- **{text(p['id'])}**: {text(detail)}")
    return "\n".join(lines) + "\n"


def parser():
    p = argparse.ArgumentParser(prog="devloop")
    p.add_argument("--version", action="version", version="devloop 0.1.0")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("render")
    sub.add_parser("select")
    a = sub.add_parser("admit")
    a.add_argument("source")
    a.add_argument("--title", required=True)
    a.add_argument("--kind", default="task")
    a.add_argument("--admission", required=True, help="persisted retry token; never auto-generated")
    a.add_argument("--policy", required=True)
    for name in ("validate", "start", "gate", "human", "eligible", "complete"):
        a = sub.add_parser(name)
        a.add_argument("id")
        a.add_argument("--policy", required=True)
        if name not in ("validate", "start"):
            a.add_argument("--inputs", required=True)
            a.add_argument("--target", required=True)
            a.add_argument("--image", required=True)
        if name in ("gate", "human"):
            a.add_argument("acceptance")
        if name == "human":
            a.add_argument("--observations", required=True)
            a.add_argument("--observer", required=True)
    return p


def run(args):
    if args.command == "render":
        sys.stdout.write(render(json.load(sys.stdin)))
        return
    if args.command == "select":
        rows = [json.loads(line) for line in myque(["next", "--format", "json"]).splitlines() if line]
        print(json.dumps([r["id"] for r in rows]))
        return
    p, policy_digest = policy(args.policy)
    gates = [{"id": g["id"], "mode": g["mode"], "observations": g["observations"]} for g in p["gates"]]
    if args.command == "admit":
        payload = canonical(command(["devloop-zutai", "admit", args.source]).stdout)
        require_valid(native(payload, structural_execution(gates)))
        helper = helper_identity()
        rec = {"schema": SCHEMA, "recordSchema": "devloop-consumer/v1", "bodyProfile": PROFILE,
               "helper": helper, "requirementsDigest": digest(payload, helper),
               "admission": args.admission, "epoch": "unstarted", "evidence": []}
        result = myque(["api", "create", "--admission", args.admission],
                       {"title": args.title, "kind": args.kind, "body": frame(payload), "consumers": {"devloop": raw_record(rec)}})
        print(result, end="")
        return
    item = get(args.id)
    payload, spec, rec = stored(item)
    require_valid(native(payload, structural_execution(gates)))
    if args.command == "validate":
        print(json.dumps({"id": item["id"], "structural": True, "observed": False}))
        return
    if args.command == "start":
        if not item["ready"]:
            raise Refusal("E_NOT_READY: MyQue did not select this item as ready")
        approval = command(p["approvalArgv"], json.dumps({"operation": "start", "item": item}), check=False)
        if approval.returncode or json.loads(approval.stdout) != {"approved": True}:
            raise Refusal("E_APPROVAL")
        # Rotate epoch before state transition. A crash leaves a safe open item; retry rotates again.
        rec["epoch"] = str(uuid.uuid4())
        updated = put(item, rec)
        myque(["start", item["id"], "--expected", updated["revision"]])
        print(json.dumps(get(item["id"])))
        return
    if item["state"] != "active":
        raise Refusal("E_STATE: evidence/closure requires active item started through devloop")
    if rec["epoch"] == "unstarted":
        raise Refusal("E_EPOCH: start through devloop first")
    execution = context(args, p, policy_digest, rec, rec["requirementsDigest"], item,
                        approve=args.command in ("eligible", "complete"))
    if args.command in ("eligible", "complete"):
        require_valid(native(payload, execution, "completion"))
        latest = get(args.id)
        if latest["revision"] != item["revision"]:
            raise Refusal("E_CONFLICT: item changed during eligibility")
        final_execution = context(args, p, policy_digest, rec, rec["requirementsDigest"], latest)
        if final_execution["identity"] != execution["identity"] or sha(Path(args.policy).read_bytes()) != policy_digest:
            raise Refusal("E_CHANGED: execution inputs changed during eligibility")
        if args.command == "complete":
            myque(["close", args.id, "--expected", item["revision"]])
        print(json.dumps({"id": args.id, "eligible": True, "closed": args.command == "complete"}))
        return
    matches = [a for a in spec["acceptance"] if a["id"] == args.acceptance]
    if len(matches) != 1:
        raise Refusal("E_ACCEPTANCE")
    acceptance = matches[0]
    gate = next(g for g in p["gates"] if g["id"] == acceptance["gate"])
    if (args.command == "gate") != (gate["mode"] == "automated"):
        raise Refusal("E_MODE: use explicit human recording, never fabricate observations")
    before = execution["identity"]
    if args.command == "gate":
        result = command(gate["argv"], json.dumps({"item": item, "acceptance": acceptance,
                                                   "execution": execution, "inputs": str(Path(args.inputs).resolve())}), check=False)
        passed = result.returncode == 0
        observations = json.loads(result.stdout) if result.stdout.strip() else []
        observer = "argv:" + json.dumps(gate["argv"])
    else:
        observations = json.loads(Path(args.observations).read_text())
        passed = True
        observer = args.observer
    after = context(args, p, policy_digest, rec, rec["requirementsDigest"], item)
    if after["identity"] != before or sha(Path(args.policy).read_bytes()) != policy_digest:
        raise Refusal("E_CHANGED: tested inputs changed while gate ran")
    now = int(time.time())
    evidence = {"acceptance": acceptance["id"], "gate": gate["id"], "mode": gate["mode"],
                "identity": before, "observedAt": now, "expiresAt": now + gate["ttlSeconds"],
                "passed": passed, "observer": observer, "observations": observations}
    execution["now"] = now
    errors = native(payload, execution, "bound", acceptance, evidence)
    rec["evidence"].append(evidence)
    put(item, rec)
    require_valid(errors)
    print(json.dumps({"id": args.id, "acceptance": acceptance["id"], "recorded": True}))


def main():
    try:
        run(parser().parse_args())
    except (Refusal, OSError, ValueError, KeyError, TypeError, StopIteration) as e:
        print(f"devloop: {e}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
