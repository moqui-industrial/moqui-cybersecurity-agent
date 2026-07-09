---
name: plc-code-security-analysis
description: Use when a PLC program (CODESYS/SCL) or C/C++ firmware source needs to be checked against secure-coding norms (Top 20 Secure PLC Coding Practices, IEC 62443-4-1/4-2) - ingesting real source into a moqui-plc-knowledge code graph and running check#CodeSecureCodingCompliance to crosswalk real findings to real norm clauses. Also the reference for what this project's C parser already detects vs. what still needs a human/future tree-sitter pass.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# PLC / Code Security Analysis

`moqui-plc-knowledge` already has a real, working parse-to-graph
pipeline (originally built for change-impact analysis, not security) -
this skill is entirely about reusing it and adding one missing piece
(a systematic code-to-norm crosswalk), not rebuilding anything.

## 1. What already exists, don't rebuild it

- **PLC (CODESYS/Siemens SCL)**: `tools/source-indexer/
  parse_plc_sources.py` &#8594; IR &#8594; `generate_plc_graph.py` &#8594;
  `load#PlcOfflineGraph` (`service/org/moqui/plc/PlcKnowledgeServices.xml`).
  Solid, real, already loaded (graph `TestIec61131Codesys`).
- **C firmware**: same graph substrate, different parser -
  `parse_c_firmware.py` &#8594; `parser/c_firmware_parser.py`. Real, tested
  against a real ESP-IDF/FreeRTOS codebase
  (`moqui-plc/iot-firmware`, 184 files) - not a toy fixture. It is
  regex/tree-sitter-hybrid (tree-sitter for parsing structure, no
  libclang/full semantic analysis), a real, documented limitation, not
  invisible.
- **The C parser already emits security findings**, not just parse
  diagnostics - `SecurityObservation` code elements for three real,
  concrete rules (`parser/c_firmware_parser.py`):
  `C_UNBOUNDED_COPY` (call to `strcpy`/`strcat`/`sprintf`/`gets`/
  `vsprintf`, CWE-120/676), `C_PLAINTEXT_NETWORK_SCHEME` (a string
  literal matching `mqtt://`, unencrypted transport), and
  `C_SHARED_GLOBAL_MULTI_WRITER` (a global written from more than one
  function in the same file, no visible synchronization - a
  reliability/race-condition signal). **Before writing new detection
  logic, check whether the parser already emits it** - this skill's own
  crosswalk service was nearly built to duplicate this before the real
  parser source was read.
- **Device&#8596;code linkage**: `moqui.device.DeviceMathModel` binds a
  `Device` to a `moqui.math.MathModel`
  (`modelTypeEnumId="MmtPlcProgram"`) whose `graphId` points at the
  offline-loaded code graph - already generic, not PLC-specific (works
  identically for a C-firmware `MathModel`).

## 2. The real gap: crosswalk, not detection

Before this skill, exactly one crosswalk edge existed
(`CyberPlcNormCrosswalkDemoSeedData.xml`: a real hardcoded-credential
`Symbol` &#8594; IEC 62443-3-3 SR 1.7 RE 1), hand-picked, never
generalized. `check#CodeSecureCodingCompliance`
(`service/org/moqui/cyber/CyberCodeSecurityServices.xml`) generalizes
it into a systematic service, for any code `graphId` (PLC or C,
identical query path via the shared `PlcGraphVertexMeta` view):

1. Every `SecurityObservation` vertex &#8594; looked up in a **verified**
   rule-id-to-clause table (each entry confirmed against the real
   loaded corpus via `search#NormClauses`/`search#NormClausesSemantic`
   before being hardcoded in the service - never guessed from a rule
   name alone): `C_UNBOUNDED_COPY` &#8594; IEC-62443-4-1 8.4.1 ("security
   coding standards... periodically reviewed"), `C_PLAINTEXT_NETWORK_SCHEME`
   &#8594; IEC-62443-4-2 8.2 (confidentiality of data in transit).
   `C_SHARED_GLOBAL_MULTI_WRITER` has **no verified match** - reported
   as a finding with `crosswalkedTo: null`, deliberately not forced
   onto a loosely-related clause.
2. Every `Symbol` vertex with `codeKind=Variable` and a
   `canonicalName` matching a credential-like pattern
   (`password|secret|credential|token|apikey`, case-insensitive) &#8594;
   IEC-62443-3-3 5.9.3.1 (SR 1.7 RE 1) - the same real signal as the
   original hand-made edge, now applied systematically instead of once.

Writes into the same dedicated `CyberPlcNormCrosswalk` `Graph` the
original edge lives in (never merges the code graph and the norm graph
- `GraphEdge.fromVertexId`/`toVertexId` reference vertices that
physically live in two other graphs, a deliberate, already-proven
pattern). **Idempotent by construction**: before creating an edge,
check for an existing one by `(graphId, fromVertexId, toVertexId,
label)`, not just the derived `graphEdgeId` hash - otherwise a
generalized service re-running against a graph that already has a
hand-authored edge (different id scheme) creates a duplicate. Wrapped
in `MathModelRun` (`math-model-run-tracking`, sixth reuse in this
project).

## 3. Validate on two real graphs, expect two different real outcomes

Same discipline as `cyber-vulnerability-intelligence`'s "two real
cases, not one": run against the existing PLC graph (must reproduce the
one known real finding exactly, proving the generalized service matches
the hand-made result) **and** a genuinely new code graph. A "zero
findings" result on the new graph is not a service failure to
investigate - it is a real, honest fact about that codebase (confirmed
by manually checking the codebase's actual global symbol names when
this skill was built: none matched the credential pattern, and the
parser's own security-rule pass found nothing either). Don't tune the
detection logic to manufacture a positive result on a real codebase
that legitimately has none.

## 4. Extending detection (future work, not done here)

The C parser's 3 rules are pattern-matching on tree-sitter nodes
directly in `c_firmware_parser.py`, not on the loaded graph - adding a
4th rule means extending that parser, then re-running
`parse_c_firmware.py`/`generate_plc_graph.py`/`load#PlcOfflineGraph` on
the affected codebase, not writing new Moqui-side detection logic.
`check#CodeSecureCodingCompliance` only needs its rule-to-clause table
extended to crosswalk a new rule once the parser emits it. A real,
still-open gap (documented, not solved): the parser has no C++ support
and no true AST/semantic analysis (libclang/tree-sitter's full grammar)
- fine for the structural, syntactic patterns above, not sufficient for
deeper flow-sensitive checks (e.g. tainted-input tracking).

## Related

- `math-model-run-tracking` - the run-history pattern reused here.
- `norm-product-classification` /
  `mechanical-safety-crosswalk` - the same "crosswalk real evidence to
  real, verified norm clauses, never force a match" principle applied
  to Product/Device data instead of code graphs.
