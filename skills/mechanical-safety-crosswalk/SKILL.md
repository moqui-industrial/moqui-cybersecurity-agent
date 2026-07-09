---
name: mechanical-safety-crosswalk
description: Use when a machine risk assessment needs to account for physical/mechanical consequences of a cyber compromise, not just IT/OT impact - deriving ISO 12100 safety-function vocabulary for real Products, mapping ISO/TR 22100-4 attack vectors (physical ports, remote access) onto real Devices, and running check#DeviceSafetyExposure to answer "can this vector reach that safety function?" Also the reference for how to extend the normative graph with a norm that has no source PDF yet.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Mechanical Safety Crosswalk (ISO 12100 / ISO-TR 22100-4)

Electrical/software analysis alone answers *how* an attacker gets in;
it does not answer *what physically happens* if they succeed, or
*which procedural/physical attack surface* exists outside the network.
ISO 12100 defines what must be physically protected (control-system
reliability requirements whose violation causes a mechanical hazard);
ISO/TR 22100-4 is the real bridge document that tells a manufacturer to
treat a cyber attack as a "reasonably foreseeable misuse" under ISO
12100, and gives the concrete question an auditor must ask. This skill
is how that bridge gets modeled generically in this project's schema -
never as case-specific narrative text.

## 1. The guiding question (ISO/TR 22100-4 clause 3), operationalized

*"Can a cyber compromise through this connection reach a Safety
function or cause a dangerous movement?"* is not a new field - it is a
join between two things this project already models generically:

- **The vector**: `moqui.device.DeviceConnection` with a physical-port
  driver (`DcdUsbPhysical`/`DcdSerialPhysical`/`DcdSdCardPhysical` -
  added in `entity/CyberDeviceAssetExtensions.xml`, real
  `DeviceConnectionDriver` extend-entity values) or a
  `DcpMaintenance`/`DcpDiagnostics` purpose (real, already in
  moqui-device - a remote-access/teleassistenza gateway is just another
  `Device` at a zone boundary, per `device-group-zone-modeling`), plus
  any `org.moqui.cyber.CyberDeviceCommunicationFlow` row for the
  device.
- **The thing to protect**: `mantle.product.feature.ProductFeature`
  with `productFeatureTypeEnumId="PftSafetyFunction"` on the Device's
  linked Product - either the ISO 12100 6.2.11.4 vocabulary (5 generic
  safety functions, see `data/
  CyberMechanicalSafetyVocabularySeedData.xml`: unexpected-start
  prevention, parameter integrity, stop-not-impeded, no-ejection,
  protective-device integrity) or the EPLAN `SAFETYRELATED_*`
  parameters from `plm-bom-import` (PL/SIL/PFHd/MTTFd) - same
  `ProductFeatureType`, two different real sources for the same kind of
  fact, deliberately not split into two enum values.

`check#DeviceSafetyExposure`
(`service/org/moqui/cyber/CyberMechanicalSafetyServices.xml`) does
exactly this join for a real Device, wrapped in a `MathModelRun`
(`math-model-run-tracking`). Three possible honest outcomes, none
forced: `REQUIRES_MITIGATION_REVIEW` (vector + safety function both on
record), `NO_SAFETY_FUNCTION_ON_RECORD` (a real vector exists but no
safety-function data to correlate it against - a gap to flag, not a
false "safe"), `NO_EXPOSURE_VECTOR_ON_RECORD` (nothing to review yet).
A machine with no mechanical BOM/P&amp;ID document (common - see the
document checklist in `plm-bom-import` §6) will correctly and
permanently return the last case until that document exists. Do not
manufacture a vector or a safety function to force a different answer.

## 2. Extending the normative graph without a source PDF

The real `tools/norm-indexer/parse_norm_sources.py` pipeline needs a
real PDF. When a norm is directly relevant but no PDF exists yet
(ISO 12100 and ISO/TR 22100-4 both started this way in this project),
the fallback is not to skip the norm or to fabricate its text from
training-data recall - it is to author a small, honest, PARTIAL IR by
hand (`tools/norm-indexer/work/ir-manual/` is the real precedent:
`documents.jsonl`/`clauses.jsonl`/`relations.jsonl`, same schema as
`ir/schema/*.schema.json`) covering only the specific clauses actually
available (e.g. quoted directly by the user), then run the real
`generate_norm_graph.py` unmodified against that manual IR to get
vertex/edge ids consistent with every other norm, then `load#NormGraph`
additively (no `clearExisting`).

Mark every such clause `provenanceClass="MANUAL_PARTIAL"` (distinct
from `EXTRACTED`) in both the metadata and, in the `clauseText` itself,
with an explicit `[copertura parziale...]`-style note - this must never
look indistinguishable from a fully-parsed norm. Register the document
in `tools/norm-indexer/config/norm-sources.json` with `sourceFile:
null` and a `note` explaining the gap, so a future real PDF is a normal
pipeline run, not a special-case migration. Re-run
`index#NormDocuments` afterward (idempotent) to extend embedding
coverage - **never invent an ISO 12100/22100-4 hazard taxonomy from
memory**; only the specific clauses actually sourced get modeled, full
taxonomy import (like `AssetClass`/MITRE ATT&amp;CK) waits for the real
document.

## 3. Interpretive notes are not norm text

A norm clause's literal wording and an analyst's (or user's) own
"how does this apply to cyber" interpretation are different kinds of
fact. Keep the literal quote first, then a clearly delimited
interpretive note (e.g. `[Applicazione Cyber - nota interpretativa, non
testo ufficiale della norma]: ...`) in the same `clauseText` - combining
them into one string (rather than a separate field) is a deliberate,
pragmatic choice: this project's norm-vertex schema has no vertex-level
rationale field (only `GraphEdge`s carry `CyberNormRationaleParam`), and
semantic search benefits from the interpretive framing being indexed
too. The labeling is what prevents misattribution, not the field
boundary.

## Related

- `norm-product-classification` - the general norm-to-Product
  crosswalk mechanism this skill's Device-level join mirrors.
- `device-group-zone-modeling` - remote-access gateways as
  zone-boundary Devices, reused as-is for ISO/TR 22100-4 clause 2's
  teleassistenza vector.
- `plm-bom-import` - source of the EPLAN `SAFETYRELATED_*`
  `PftSafetyFunction` data, and the document checklist (mechanical
  BOM/P&amp;ID, ISO 12100 safety analysis) this skill's exposure checks
  ultimately depend on.
- `math-model-run-tracking` - the `check#DeviceSafetyExposure` run
  history pattern.
