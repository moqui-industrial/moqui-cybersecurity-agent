---
name: iso24882-risk-assessment
description: Use when conducting a Threat Analysis and Risk Assessment (TARA) per ISO/DIS 24882 (or a structurally similar risk-assessment norm) for a machine/system already modeled in this project's Device/Asset/PLC graphs. Maps the norm's 7-step methodology onto moqui-math Graph/GraphVertex/Parameter and reuses the existing ProductFeature/ProductFeatureGroup crosswalk for the final requirements step, instead of inventing new risk-assessment entities.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# ISO/DIS 24882 Risk Assessment (TARA)

A TARA's own vocabulary (Asset, Damage Scenario, Threat Scenario, Impact,
Likelihood, Risk Rating, Risk Treatment, Cybersecurity Requirement) is
not the same thing as this project's Device/Asset/Product graphs, and
should not be forced into them. Model it as its own `Graph`
(moqui-math), cross-referenced to the real Device/Asset/Product graph by
ID where a vertex has a real physical counterpart — same "separate
graphs, cross-referenced by ID, never merged" principle used for the
PLC-to-norm crosswalk. Do not invent a new risk-assessment entity before
checking whether `GraphVertex`/`Parameter`/`GraphEdge` already fit (they
do, for every step below).

## The 7 steps, mapped to Moqui constructs

1. **System of Interest + Asset** (norm's Asset ≠ `mantle.product.asset.Asset`
   — it's a "digital asset": a data flow, a data-at-rest/config item, a
   HW/SW component, or an external interface). One `GraphVertex` per
   asset, tagged by category via `Parameter`; Confidentiality/Integrity/
   Availability criticality also via `Parameter`. A vertex with a real
   physical counterpart gets a soft cross-reference `Parameter`
   (`textValue` = the real `Device`/`DeviceConnection`/`Product` ID); a
   purely logical asset (e.g. control logic, configuration data) gets
   none — don't force one.
2. **Damage Scenario**: one `GraphVertex` per scenario, Impact rated on
   the norm's own categories (typically Safety/Financial/Privacy/
   Availability) via `Parameter`, Overall = the max across them. Link to
   its involved Assets via `GraphEdge` (e.g. `label="INVOLVES_ASSET"`).
3. **Threat Scenario (STRIDE or equivalent)**: one `GraphVertex` per
   threat, STRIDE type via `Parameter`, a precondition/attack-vector
   free-text `Parameter`, `GraphEdge`s to its involved Assets and to the
   Damage Scenario(s) it would realize (e.g.
   `label="REALIZES_DAMAGE_SCENARIO"`).
4. **Likelihood**: the norm's attack-potential sub-parameters (typically
   5: elapsed time, expertise, knowledge of the system, window of
   opportunity, equipment) are analyst judgment, not computed — assign
   each as a `Parameter` (`numericValue` = the norm's table value,
   `parameterEnumId` = the chosen level, for readability). **Verify the
   exact scale values and banding thresholds against the real, loaded
   norm text directly** (e.g. via this project's `search#NormClauses`)
   before using them — a third-party reference document's numbers can be
   wrong even when everything else about it is trustworthy (a real
   discrepancy was caught this way: a professional reference TARA had
   one attack-potential value off from the norm's own table).
5. **Risk Rating**: a computed value (sum of the Likelihood sub-scores →
   banded rating; Impact × Likelihood → a matrix lookup). Since this is
   a deterministic, code-defined calculation with a per-vertex history
   worth tracking, wrap it as a `check#<X>Risk` service following
   `math-model-run-tracking`: register a `MathModelDef`/`MathModel`
   (`modelTypeEnumId="MmtCodeDefinedFunction"`), and on each call create
   a `MathModelRun`, compute, and write the results back onto the
   `ThreatScenario` vertex as `Parameter` rows (create-or-update, so
   re-running is safe).
6. **Risk Treatment**: define and justify a per-engagement acceptance
   threshold once — attach it as a `Parameter` on the `Graph` itself
   (no `graphVertexId`), not per-threat, since it's an engagement-level
   decision. **Offer the alternative of a stricter threshold explicitly**
   when the system's consequences warrant it (e.g. food-safety, not just
   generic "typical practice") rather than silently defaulting. Then
   Mitigate/Share/Avoid/Accept per threat is itself a `Parameter`, with a
   free-text rationale required especially for any Accept.
7. **Cybersecurity Requirements**: for every threat being Mitigated,
   derive concrete technical requirements and reuse this project's
   existing norm-to-product crosswalk mechanism directly (see
   `norm-product-classification`) — `ProductFeature` (one per
   requirement, `productFeatureTypeEnumId="PftSecurityCapability"`),
   grouped into `ProductFeatureGroup`(s) by shared underlying weakness
   (not one group per threat), linked to whichever real `ProductCategory`
   records already classify the affected components via
   `ProductCategoryFeatGrpAppl` (`applTypeEnumId="PfatStandard"`). This
   closes the loop for free: `check#ProductCategoryCompliance` (already
   built, no code changes needed) can now check real products against
   these new requirements, and will correctly aggregate them alongside
   any other `ProductCategory` a product already belongs to. Add a soft
   cross-reference `Parameter` from each Mitigate `ThreatScenario` to the
   `ProductFeature` addressing it, for traceability.

## Workflow discipline

- **One step at a time, with an explicit checkpoint after each.** Do not
  advance to the next step, or silently decide open judgment calls
  (Impact severity absent a documented compensating control, an
  acceptance threshold, a treatment choice), without the user's
  confirmation — these are real risk-management decisions, not modeling
  details.
- When a real reference document (a prior TARA, a vendor report) or a
  packaged assessment methodology/skill is available, use it as a
  **cross-check**, not a source of truth to copy: independently
  re-derive the judgment-heavy step (typically Impact or Likelihood)
  from the same real facts and compare — convergence is reassuring,
  divergence tells you something real (see the field verification note
  in step 4).
- Validate one real system/case end-to-end before generalizing to
  others. The specific case is scaffolding to prove the mechanism and to
  build/exercise the reusable services (this skill, plus whatever
  `check#*` service the Likelihood/Risk computation needs) — it is not
  itself the deliverable, and should not be repeated case-by-case once
  the mechanism is proven; the norm's own vocabulary and this skill are
  what should scale, not hand-written examples.

## Known field-length gotchas

- Moqui `type="id"` fields are `VARCHAR(40)` — a `ParameterDef`/entity
  ID built by concatenating descriptive words (common in this project's
  naming convention) can exceed this without looking obviously long;
  check length before naming, or let the load fail once and read the
  exact H2 error (it names the column and its real size) rather than
  guessing at a fix.
- `type="text-medium"` fields are `VARCHAR(255)` — free-text
  descriptions on norm-derived entities (`ProductFeature.description`,
  `Graph.description`, etc.) are easy to overrun when transcribing a
  norm clause; keep them to a summary and put the fuller rationale in a
  dedicated rationale `Parameter` (`textValue`, `text-long`) instead.
- New `ParameterDef`/`Enumeration` records referenced by a `demo`-type
  seed file can fail to load if placed in a `data/` `seed-initial` file
  that happens to sort alphabetically *after* that demo file — the
  entity-data loader processes all included types in one alphabetically
  sorted pass, not grouped by type. Fix: put any `ParameterDef`/
  `Enumeration` a demo file depends on in an `extend-entity`'s
  `seed-data` block instead (entity seed-data loads before the
  file-by-file data pass, regardless of alphabetical order).

## Related

- `math-model-run-tracking` — the pattern for wrapping the Likelihood/
  Risk Rating calculation (step 5) as a tracked `MathModelRun`.
- `norm-product-classification` — the exact mechanism reused for step 7
  (Cybersecurity Requirements), and the discipline of never forcing a
  false pass (a `MISSING` compliance result is a valid, useful finding).
- `device-group-zone-modeling` — if the system being assessed has
  network zones/conduits relevant to Availability Damage Scenarios,
  model them there first; this skill's Asset step can then soft-
  cross-reference the resulting `DeviceGroup`s the same way it
  cross-references `Device`/`DeviceConnection`.
