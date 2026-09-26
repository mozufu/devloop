# Devloop 0.1.0

Standalone UUID-bound requirements, pure Zutai semantic helpers, human-readable
projection, and evidence tools. Source destination:
<https://github.com/mozufu/devloop>. BSD-3-Clause. Publishing a repository/tag or
artifact requires explicit authority; a local build or recipe is not a published
release. Release verification and artifact SHA256s belong in the release notes.

## Supported dependencies and install

- Python >=3.11, PyYAML >=6.0,<7, setuptools >=68.
- MyQue >=0.2.0.0,<0.3, including the `myque/v2` machine API, `dependenciesDone`,
  admission-token transactions and `start/close --expected REV`. Qualified
  against mozufu/myque v0.2.0.0, commit
  `d25241fcbf1d6b1e06283717c246576e88f6fa5d`.
- myque-gh 0.2.0.0 when using GitHub projection. Qualified against
  mozufu/myque-gh v0.2.0.0, commit
  `376fe90742c11bc0a60236ad327a769dac2b9e13`.
- Zutai exact upstream revision `b667e3c5018e69a3f8e39948a73a6c57c514de6e`,
  <https://github.com/iceice666/zutai>. Rust edition 2024 toolchain; LLVM `llc`
  and `clang` supporting the host native target. The compiler executable alone
  is insufficient: ship/install its matching stdlib and runtime archive.

From an independent directory, not a product checkout:

```sh
git clone https://github.com/iceice666/zutai zutai-toolchain
git -C zutai-toolchain checkout b667e3c5018e69a3f8e39948a73a6c57c514de6e
cargo install --locked --path zutai-toolchain/crates/cli
cargo build --release --manifest-path zutai-toolchain/Cargo.toml -p zutai-rt
export ZUTAI_STDLIB_ROOT="$PWD/zutai-toolchain/stdlib"
export ZUTAI_RUNTIME_ARCHIVE="$PWD/zutai-toolchain/target/release/libzutai_rt.a"
# Set ZUTAI_LLC and ZUTAI_CLANG to the matching installed LLVM binaries if needed.
cd devloop
cargo install --locked --path .
python3 tools/generate_bindings.py
python3 -m pip install .
```

The Rust bridge pins upstream through Cargo, never a local product path. Release
packaging includes generated `devloop/bindings.json`, schemas, helpers and the
skill under `$prefix/share/devloop/skills/devloop/SKILL.md`. Register that installed
skill with the host's skill discovery or symlink its directory into the host's
configured skill search path. Source checkouts can use `PYTHONPATH=.` and the
bridge in `target/release` for qualification. Consumers may configure exact
compiler/runtime paths through the upstream environment variables above. These
are trusted installation configuration, not item fields.

Upgrade the whole distribution and compiler pin together. Helper identity changes
invalidate old evidence and refuse existing records until explicitly readmitted
through the owning migration process; there is no silent legacy adoption or
implicit evidence migration. MyQue owns v1/v2 envelope migration independently.

## Contracts and single semantics implementation

`contracts/dev-spec/v1/schema.zt` owns requirements; `contracts/execution/v1/`
owns execution, evidence and policy; `contracts/consumer/v1/schema.zt` owns the
namespaced consumer record. Host JSON is transport generated from those contracts
by `tools/generate_bindings.py`, using upstream `stdlib.reflect.schemaFields`.
Generation happens at release build time, not validation time.

Each contract directory and `helpers/v1` is its own Zutai package (`zutai.zti`),
and cross-tree references are declared dependencies (`import dev_spec.schema`),
exactly as the standard library does. This is required, not stylistic: the
pinned compiler resolves a quoted import only downward from the importing file
and refuses `../` with `zutai::import::path_traversal`. The manifests are part
of the helper identity, so relocating a module invalidates existing evidence.
Installations must therefore ship each `zutai.zti` beside its modules, and any
tool that compiles against them must pass the compiler a path with real parent
directories so package discovery can find the manifest.

`helpers/v1/validate.zt` is the only semantic implementation, reusing
`stdlib.validate` and `stdlib.result` conventions. Exported typed functions:

- `projection : Spec -> List Text`: structural/semantic consistency without
  claiming policy approval or observed acceptance.
- `structure : Spec -> List Gate -> List Text`: projection plus policy resolution.
- `observe : Int -> Text -> List Predicate -> List Observation -> Bool` and
  `compatible` with the same signature: a bounded traversal of the declared DAG.
- `bound : Spec -> Execution -> Acceptance -> Evidence -> Bool`.
- `completion : Spec -> Execution -> List Text`.
- `report : List Text -> Text`: diagnostics joined by LF.

Each validation creates a temporary trusted wrapper importing fixed installed
helpers, types and inert `.zti` input files, invokes `zutai-cli compile --emit bin`,
and executes that native binary. There is no `run`, `json`, `eval_path`, or
reference evaluator call on validation/projection. Only admission invokes the
reference evaluator for `.zt` authoring. Generated wrappers contain fixed calls
and trusted paths; item data never becomes source identifiers, imports, executable
paths or shell text. Native compilation on each call costs compiler startup,
typechecking, LLVM assembly/linking, and process startup; there is no misleading
claim of cached low-latency validation. The upstream backend must compile these
helpers; backend rejection is a hard refusal, never a host semantic fallback.

### Primitive semantics

IDs are nonempty, case-sensitive Unicode strings, unique within requirement,
acceptance, predicate and gate namespaces. Every requirement has nonempty unique
resolved acceptance coverage. Predicate groups reference predicate IDs; cycles,
missing references, duplicate members and empty all/any groups refuse. `all`
requires every member; `any` requires at least one passing member but **all**
referenced observation inputs must be present and type-compatible, even in a
branch that would otherwise short-circuit.

`Value.kind` is exactly `int`, `bool`, or `text`. Values carry `intValue`,
`boolValue`, and `textValue`; only the selected typed slot is meaningful. Equality
never coerces types. Bounds operate on signed 64-bit integers; each endpoint
explicitly chooses inclusive or exclusive. Reversed and empty equal-endpoint
intervals refuse. `Predicate.kind` is exactly `equal`, `bounds`, `all`, or `any`;
these are a finite versioned data contract, not an extensible expression language.
All variants carry the common schema fields; unused slots are inert data.

Policy declares gate IDs, automated/human mode and typed observation IDs. Every
acceptance resolves to a matching policy gate and its predicate inputs resolve to
the gate's declaration. Gate code/argv is **only** in consumer policy. A required
human gate remains pending without explicit observations. Text rationale is not a
program, proof or observation.

Evidence matches acceptance, gate, mode, requirements digest, helper identity,
code content identity, exact policy bytes, exact execution input bytes, target,
image and start epoch. `observedAt <= now < expiresAt` is the freshness interval;
future observations and nonpositive lifetimes refuse. Failed executions, missing
observations, incompatible values and failed predicates never satisfy acceptance.
Mandatory obligations all need valid evidence; optional ones do not block close.
MyQue's `dependenciesDone` and consumer approval must both hold. No graph is
recomputed in devloop. An actual recorded observation may still be false: tools
bind provenance and run configured gates, not prove the physical world.

Diagnostics include `E_SCHEMA`, `E_PROBLEM`, `E_REQUIREMENT_IDS`,
`E_ACCEPTANCE_IDS`, `E_PREDICATE_IDS`, `E_COVERAGE:REQ`, `E_PREDICATE:PRED`,
`E_OBLIGATION:ACC`, `E_GATE:ACC`, `E_NOT_READY`, `E_APPROVAL`, `E_EVIDENCE:ACC`.
Host framing/transport failures use `E_PROFILE`, `E_CANONICAL`, `E_DIGEST`,
`E_HELPER`, `E_CONSUMER_VERSION`, `E_FIELDS`, `E_CODE`, `E_CHANGED`, and
`E_COMMAND`. Upstream structural type errors retain compiler locations; a type
check succeeding is not semantic success.

## Admission and profile

`examples/queue.zti` and `examples/policy.json` are the complete shape examples.
Authors may instead compute the record in `.zt`. A relative `.zti` import is
resolved downward from the authoring file; reaching the published types needs a
consumer-side `zutai.zti` that declares the installed
`contracts/dev-spec/v1` package as a dependency:

```zt
limits ::= import "limits.zti";
s ::= import dev_spec.schema;

ignored :: s.Value = { kind = "bool"; intValue = 0; boolValue = true; textValue = ""; };
within :: Text -> Text -> Int -> s.Predicate
= id observation upper => { id =; kind = "bounds"; observation =; expected = ignored; lower = 0; upper =; lowerInclusive = true; upperInclusive = true; members = noMembers; };
```

Admission calls upstream `eval_path` and walks its deeply forced **Value**, not
JSON. Atoms and strings beginning `#` remain distinct; immediate output uses the
upstream formatter. Functions, runtime types, opaque values, nonfinite floats,
and other values without a lossless immediate representation refuse even when
nested. Tagged payloads and tuples have no immediate representation and refuse,
not a guessed JSON envelope. Unresolved imports refuse. The final imported values
are materialized once; later changes to author/import files do not change the
stored body. Devloop never copies author sources into a second spec store.

The body after the title is exactly LF + three-backtick `zti` opening line +
canonical UTF-8 immediate payload ending in LF + three-backtick closing line +
LF. No BOM/CRLF, independently editable adjacent prose, duplicate blocks, comments
or alternate fences. Payload strings use JSON escaping; literal fence lines
inside payload refuse. `fenced-zti/v1` is selected by policy and recorded under
`devloop`, never guessed as validated from a fence. Legacy prose without a record
passes projection unchanged, including incidental code examples. A leading
unrecorded structured fence, malformed recorded body or unknown profile refuses.

The digest is lowercase SHA256 of
`devloop/requirements/v1 NUL dev-spec/v1 NUL HELPER_ID NUL PAYLOAD_UTF8`.
Payload is upstream canonical format with exactly one trailing LF; no Unicode
normalization or line-ending repair on stored reads. Helper ID is
`devloop-helpers/v1:SHA256` over sorted installed contract/helper relative UTF-8
paths, NUL, exact file bytes, NUL, followed by the exact Zutai pin. This binds both
schema and helper bytes. Item identity is the unchanged canonical MyQue UUID;
the admission token is persisted by MyQue, and retries with identical payload
resolve the same UUID. Conflicting token payloads refuse. Supply a durable token
from the calling workflow; no randomly regenerated retry token. Evidence appends
patch only the devloop consumer entry using MyQue revision CAS, never body bytes.

## Commands and consumer effects

```sh
devloop admit examples/queue.zti --title 'Bound queue' --admission queue-2026-01 --policy policy.json
devloop select
devloop validate UUID --policy policy.json
devloop start UUID --policy policy.json
devloop gate UUID A1 --policy policy.json --inputs inputs.json --target host --image image-sha256
devloop human UUID A2 --policy policy.json --inputs inputs.json --target host --image image-sha256 --observations human.json --observer PERSON
devloop eligible UUID --policy policy.json --inputs inputs.json --target host --image image-sha256
devloop complete UUID --policy policy.json --inputs inputs.json --target host --image image-sha256
myque api get UUID | devloop render
myque-gh --body-renderer devloop --body-renderer-arg render
```

Run tools from the consumer root. `codePaths` explicitly names all relevant source
files/directories, gate scripts, approval code and configuration required to
reproduce execution. Code identity hashes sorted relative path bytes, NUL,
executable bits, NUL, raw file SHA256; symlinks and empty/missing sets refuse.
Untracked source is included. MyQue tracked store updates outside these paths do
not change code identity. **The consumer owns dependency closure**: omitted
source/tool dependencies cannot be magically detected. Pin interpreter/compiler
and executable artifacts in the execution input manifest, along with build
options and environment that matter. Put target/image artifact hashes in their
explicit arguments, not informal names when artifacts matter. Host checks source,
policy and input identities before/after gates and again before closure.

Configured gate argv runs without a shell. Its stdin is JSON
`{item, acceptance, execution, inputs}`; `inputs` is an absolute manifest path.
Stdout is a JSON observation array, e.g.
`[{"id":"depth","value":{"kind":"int","intValue":64,"boolValue":false,"textValue":""}}]`.
Stderr carries diagnostics; exit zero means execution succeeded, not acceptance.
Nonzero execution is recorded as failed when observations decode. Invalid output
refuses without inventing an observation. Human command reads the same array
from an explicitly supplied file and records the named observer. A consumer
approval argv receives the item (and execution at completion); only exit zero
with exactly `{"approved":true}` approves. This must represent a real consumer
decision, not a bundled unconditional-success script.

Start rotates epoch under CAS before guarded MyQue start; interrupted open start
can retry safely. Resuming an active UUID keeps its epoch. Reopen then devloop
start rotates epoch so historical evidence cannot approve reopened work. Item
start/close transitions use `--expected` revisions; competing item writes refuse.
CAS does not lock arbitrary source files, the clock, deployment hardware or the
whole consumer filesystem. Consumers needing strict concurrent execution isolation
must run inside an immutable build snapshot/exclusive execution policy. Never
claim the final check eliminates all filesystem TOCTOU races.

## Closure and retention limits

Direct `myque close UUID` intentionally bypasses devloop evidence eligibility.
MyQue owns states and stores opaque consumer records; it does not invoke helpers.
Demonstrate this boundary in a disposable store, not by evading production policy.
Direct reopen/start likewise bypasses epoch lifecycle; use this skill's tools for
spec-driven work. Consumer permissions and review enforce the supported path.
Retirement/history retention remains MyQue-owned. Retired API records may expose
UUID and terminal metadata without an offline body. Devloop refuses unavailable
bodies and never reconstructs them. Missing/pruned history is a recovery blocker,
not fabricated evidence. GitHub projection is a view, not a second authority.

## Qualification and release

After source changes settle:

```sh
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
python3 tools/generate_bindings.py
python3 -m unittest discover -s tests -v
python3 -m build
```

The tests compile and execute real helpers and admission, including import
pinning, atom preservation, duplicate/reference/coverage failures, unknown
semantics, bounds, empty groups, typing, freshness and identity invalidation.
Run a separate consumer's actual failed-gate/fix/review/retry/complete cycle too;
tests with supplied observations are not proof that consumer hardware was tested.

Release destination is GitHub `mozufu/devloop`, tag `v0.1.0`, source archive,
Python wheel/sdist and host-specific bridge artifact or reproducible Cargo
installation. Record source commit, generated bindings, Cargo.lock, exact
MyQue/myque-gh releases, compiler pin, toolchain, artifact SHA256 and clean-install
verification in release notes. Build wheel after bindings generation; install it
and bridge into a fresh prefix and confirm skill/contracts/helper discovery and
real consumer workflow outside any product tree. Do not publish a local recipe
as if qualification already happened. No automatic remote publication is part
of the devloop tools.
