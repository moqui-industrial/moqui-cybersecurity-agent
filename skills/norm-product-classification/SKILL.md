---
name: norm-product-classification
description: Use when extracting a norm's component-category and technical-requirement vocabulary into Moqui ProductCategory/ProductFeature/ProductFeatureGroup seed data, or when classifying a real Product/Asset/Device against that vocabulary using its attached certificates/datasheets (ProductContent/AssetContent/DeviceContent) or explicit user input. This is how the norm-to-product compliance crosswalk gets built and populated at scale, one norm or one product at a time, instead of hand-writing one-off crosswalk edges per case.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Norm-to-Product Classification

Norms define their own vocabulary of component categories (e.g. a norm
section stating "the purpose of this set of requirements is to document
requirements specific to X") and concrete technical requirements (checklist
language such as "shall provide/support/have the capability to Y", or a
numeric threshold such as "at least N characters"). That vocabulary is the
join key between the normative graph and any real machine's Product/Asset/
Device graph — it turns the crosswalk from semantic/NLP text matching into
taxonomic classification, which is auditable and defensible.

Moqui already has the entities for this (mantle-udm, never invented new
ones for this purpose): `ProductCategory`, `ProductFeature`/
`ProductFeatureAppl`, `ProductFeatureGroup`/`ProductFeatureGroupAppl`,
`ProductCategoryFeatGrpAppl`. `ProductCategory` is a pure organizational
grouping (Silverston's Data Model Resource Book: "classification of
products... to group products together"); `ProductFeature` is an intrinsic
characteristic of the product itself. Do not invent a new crosswalk entity
before checking whether one of these already fits.

**A second, distinct target also matters here**: `moqui.basic.Enumeration`
hierarchies — `DeviceTypeEnumId` (`moqui-device`, electronic/automation
components only, a real deep `parentEnumId` tree, e.g.
`DtPhysicalDevice→DtComputer→DtServer→...`), `AssetClassEnumId`
(`mantle-udm`, universal — covers mechanical/electromechanical components
with no firmware too, a shallower 1-2 level tree, many top-level leaves
with no parent), and `ProductTypeEnumId` (`mantle-udm`, **flat, only ~9
values** — not a tree, just the coarsest possible bucket, e.g. `PtAsset`).
These are a fundamentally different mechanism from `ProductCategory`: an
enum value is a controlled-vocabulary foreign key referenced directly by
`Device.deviceTypeEnumId`/`Asset.classEnumId`/`Product.productTypeEnumId`,
not a classifiable record with its own membership join. Both mechanisms
get populated from the same norm-reading pass — a clause defining a
component-type taxonomy (e.g. IEC 62443-4-2's "Network Device"/"Embedded
Device"/"Host Device"/"Software Application") is evidence for a
`DeviceTypeEnumId`/`AssetClassEnumId` value, while a clause stating a
scope + testable requirements is evidence for the
`ProductCategory`/`ProductFeature`/`ProductFeatureGroup` chain — the same
clause can justify both.

## Workflow A: Vocabulary Extraction (norm → schema), systematic pass

This is a **one-time, thorough pass per norm document**, not a one-off
lookup — the goal is a complete, human-reviewed vocabulary for that
document before moving to the next one, not scattered ad hoc examples.
Process documents in priority order: norms with an explicit
component-type or function taxonomy first (IEC 62443-4-2, ISO 12100,
ISO/TR 22100-4 — all three define real taxonomies directly in their
text), norms stating abstract requirements not tied to a component type
later (IEC 62443-3-2/3-3) or skipped entirely if a full read confirms
they yield nothing usable here (methodology documents like ISO/DIS 24882,
or regulatory-entity-scope documents like NIS2/CRA that classify
*organizations*, not *components*).

1. **List every clause of the document systematically**, not just a
   targeted search: `find#NormClausesByDocument` (paginated, full
   untruncated `clauseText`, ordered by `clauseNumber`) — walk the whole
   document, not a sample. For a large document, use
   `search#NormClausesSemantic` first with trigger queries ("requirements
   specific to a type of component", "the product shall provide the
   capability to", "classification of devices/components") to shortlist
   candidate clauses to read in full, rather than reading every single
   clause of a large corpus cold — but the shortlist is a reading aid, not
   a filter that silently drops real vocabulary; if a document is small
   enough to read entirely (ISO 12100, ISO/TR 22100-4 both are), just read
   it entirely.
2. Never invent a category, enum value, or requirement. Always quote the
   real clause number and clause text you found into the `description`
   field of the record you generate — this is the same evidence/provenance
   discipline already used for the normative graph itself (EXTRACTED/
   DERIVED/INFERRED/MANUALLY_REVIEWED). A category, enum value, or feature
   with no traceable clause behind it should not be created. Discard
   clauses that are process/policy language ("shall have a policy for...")
   with no testable technical criterion — forcing one into a
   `ProductFeature` would fabricate a compliance criterion the norm never
   actually specified.
3. **For each component-type/category clause found, decide which
   mechanism it belongs to, in this order**:
   - Component is intrinsically electronic/automation (network stack,
     controller, firmware, software) → candidate `DeviceTypeEnumId`. Query
     existing `moqui.basic.Enumeration` rows (`enumTypeId='DeviceType'`)
     **first** for a value that already fits, or a close parent to extend
     under — only add a new row (`<moqui.basic.Enumeration enumId=...
     parentEnumId=... enumTypeId="DeviceType" description=.../>`, same
     static-seed-XML pattern used everywhere else in this project, no
     create-service exists or is needed) as a child of the closest
     existing node when genuinely missing. Never add an unrelated new
     top-level value without first checking the existing ~150-value tree.
   - Component may be mechanical/electromechanical with no firmware, or
     the clause's scope is broader than "device" → candidate
     `AssetClassEnumId`, same cerca-prima-di-creare discipline against the
     existing ~213-value tree.
   - The clause is best read as an organizational/regulatory scope
     statement rather than a component type (e.g. "the purpose of this set
     of requirements is to document requirements specific to X") → create
     one `ProductCategory` record with `productCategoryTypeEnumId=
     "PctRegulatory"` (none of the e-commerce-oriented category types fit
     a norm-derived category).
   - `ProductTypeEnumId` is **not** a target for new values from norm
     reading — its ~9 flat values already cover every real case
     (`PtAsset` for physical equipment, `PtPickAssembly` for assemblies,
     etc.). Do not propose new `ProductTypeEnumId` values.
   A single clause can justify more than one of these (e.g. IEC 62443-4-2's
   Network Device definition justifies both a `DeviceTypeEnumId` value
   *and* the `NCAT_IEC62443_4_2_NETDEV` `ProductCategory` already in this
   project) — they answer different questions (what kind of thing is this
   vs. what regulatory scope applies to it) and are not mutually exclusive.
4. For each requirement found, decide its shape before modeling it:
   - **Boolean/capability-style** ("shall provide the capability to..."):
     one `ProductFeature` record, `productFeatureTypeEnumId` marking it as
     a capability-style feature type (add one if none exists yet, distinct
     from commercial feature types like color/size).
   - **Numeric-threshold-style** ("at least N", "no more than N"): one
     `ProductFeature` record *per threshold value*, using
     `numberSpecified`/`numberUomId` on the `ProductFeature` itself. This
     matches both the existing Color/Size seed pattern (one record per
     value, e.g. `ColorBlue`, `SizeSmall`) and Silverston's own DIMENSION
     example ("8½-inch width" as its own feature). Share the same
     `productFeatureTypeEnumId` across different thresholds of the same
     parameter family so they can be compared programmatically later.
   - **Never use `ProductFeatureAppl.amount`** for a technical value. That
     field is an e-commerce pricing field (a flat add-on charge for
     `PfatOptional` features) — confirmed by grepping the actual pricing
     service code, not by its name or entity comment. Reusing it for a
     technical quantity will silently produce wrong or misleading data.
5. **Before deciding `ProductFeatureGroup` granularity, check the real
   cross-reference signal — don't group by document chapter structure
   alone.** Call `find#NormClauseReferences` on the clause(s) involved: if
   several clauses (even across *different* documents) reference each
   other with real `REFERENCES`/`HARMONIZES_WITH` edges, that is concrete
   evidence they belong in one `ProductFeatureGroup` together — not an
   editorial choice made by looking at how the document happens to be
   organized into chapters. This edge data already exists in the graph
   (776 `REFERENCES` + 8 `HARMONIZES_WITH` in `OtCyberNormGraph` as of
   2026-07-09, built by the Phase 1 pipeline but unused until this
   service existed) and is often the norm's *own* explicit correspondence
   table, not an inferred pattern — e.g. IEC 62443-3-3's Annex B
   ("Mapping of SRs and REs to FR SL levels 1-4") and EN 40000-1-3's Annex
   ZA ("Correspondence between this European Standard and... the Cyber
   Resilience Act") are both real mapping tables the norms themselves
   wrote, and both are the highest-out-degree `REFERENCES` clauses in the
   whole graph — use them as the calibration reference for what a strong
   grouping signal looks like versus an isolated one-off citation.
6. Group the requirements relevant to a category into one
   `ProductFeatureGroup`, linking each member feature via
   `ProductFeatureGroupAppl`. Link the category to the group via
   `ProductCategoryFeatGrpAppl` — **note this entity's package is
   `mantle.product.feature`, not `mantle.product.category`** (a real,
   easy-to-repeat mistake: it lives alongside `ProductFeatureGroup`, not
   alongside `ProductCategory`). Use `applTypeEnumId="PfatStandard"` for
   this link: the requirement is an intrinsic/regulatory characteristic,
   not a `PfatSelectable` commercial variant or a `PfatOptional` paid
   add-on. If a requirement genuinely doesn't belong to any category-scoped
   group (e.g. it applies universally, like the existing ISO 12100 safety
   functions checked by `check#DeviceSafetyExposure` directly against
   `ProductFeatureAppl`, not through a category traversal), it's fine to
   leave it standalone — but standalone features are only discoverable via
   `cyber_find_classification_vocabulary`'s `standaloneFeatures` output
   (added 2026-07-09 specifically because this was found to be a real,
   silent discoverability gap), so don't forget that output exists when
   reading back what vocabulary is already available.
7. Set `sourceGraphId`/`sourceGraphVertexId` on every new `ProductFeature`/
   `ProductCategory` record to the real `graphVertexId` of the clause it
   was extracted from (fields added 2026-07-09,
   `CyberDeviceAssetExtensions.xml`) — this is what makes "which vocabulary
   cites this clause" a real query instead of only a free-text description
   match.
8. Emit everything as `entity-facade-xml` seed data directly under `data/`
   (Moqui's data loader only scans a component's top-level `data/`
   directory, not subdirectories - confirmed empirically, a real trap:
   files placed in a `data/norm-vocabulary/` subdirectory are silently
   never loaded, no error), one file per norm document, named
   `CyberNormVocabulary_<documentId>.xml` (e.g.
   `CyberNormVocabulary_IEC-62443-4-2.xml`), `type="seed-initial"` (pure
   reference vocabulary, always loaded, zero product-specific instance
   data — same convention as `CyberMechanicalSafetyVocabularySeedData.xml`)
   for human review before it is ever loaded. Do not auto-load newly
   extracted vocabulary, and do not add the new file to `component.xml`'s
   `load-data` until it has been reviewed.

## Workflow B: Classification (real product → vocabulary), hierarchical

Run this when a real `Product`/`Asset`/`Device` needs to be classified
against the vocabulary Workflow A already materialized — normally at
BOM-import time (`plm-bom-import` §4.5 triggers this), but also whenever
new evidence (a newly attached datasheet/certificate) becomes available
for an already-imported product. **This is mandatory, not optional**: a
product left on `plm-bom-import`'s generic default (`AsClsMfgEquip`/
`PtAsset`) when better vocabulary genuinely exists is an unfinished
classification, not an acceptable shortcut — the user has explicitly said
they don't expect to classify better than the agent, so silently leaving
the generic default is a regression, not a neutral outcome.

1. Gather evidence: the BOM line's own description/manufacturer text,
   attached `ProductContent`/`AssetContent`/`DeviceContent` (certificates,
   datasheets — read their content when the user has shared it in the
   conversation, e.g. via `product-content-attachment`), or explicit
   information the user provides directly.
2. Call `cyber_find_classification_vocabulary` (optionally with a keyword
   filter) to see the real candidate `DeviceTypeEnumId`/`AssetClassEnumId`
   trees and the norm-derived `ProductCategory`/`ProductFeatureGroup` list
   — read the returned trees yourself and judge the match; this tool does
   **not** auto-rank by embedding similarity (the enum labels are 2-4
   words, too short for reliable automatic semantic matching against
   paragraph-length evidence) — the agent's own reading of the evidence
   against the returned vocabulary is the actual classification step.
3. **Classify hierarchically, most-specific-first**:
   - Only attempt `DeviceTypeEnumId` if the component is genuinely
     electronic/automation — in practice, if it's a component that would
     get (or already has) its own `moqui.device.Device` row (network
     gear, controllers, sensors with a communication interface). Most BOM
     line items (breakers, terminal blocks, mechanical hardware) never
     reach this branch.
   - Always attempt `AssetClassEnumId` — every real physical component
     has one, this is the branch that actually replaces the generic
     `AsClsMfgEquip` default for the great majority of BOM items.
   - Always attempt matching against norm-derived `ProductCategory`
     records independently of the above (a component can be both a
     specific `AssetClassEnumId` value and a member of a regulatory
     `ProductCategory` — they answer different questions, see Workflow A).
4. **If no confident match is found at any level for a component that
   plausibly has one** (i.e. the evidence is genuinely ambiguous, not
   simply "this really is generic mechanical hardware with no norm
   vocabulary yet"), ask the user explicitly rather than guessing or
   silently leaving the generic default — same mandatory-question
   discipline already used in `product-content-attachment` for
   single-product-vs-family. It is fine, and expected, for many BOM items
   to legitimately end at the generic default when no more specific
   vocabulary applies to them — the mandatory question is for genuine
   ambiguity, not for every item.
5. Once decided, call `cyber_classify_product` to apply it: updates
   `Asset.classEnumId`, `Device.deviceTypeEnumId` (if a `Device` exists
   for that asset), and ensures `ProductCategoryMember` for each chosen
   `ProductCategory` (idempotent, same ensure-membership pattern as
   `cyber_attach_product_family_content`).
6. For each `ProductCategory` the product now belongs to, look at the
   technical requirements in its associated `ProductFeatureGroup`(s) and
   check the evidence against each one:
   - If the evidence confirms the product has the capability/meets the
     threshold, emit a `ProductFeatureAppl` record
     (`applTypeEnumId="PfatStandard"`).
   - If the evidence is silent or contradicts it, **do not emit a
     `ProductFeatureAppl` record, and do not force one to make the product
     look compliant.** A confirmed gap is a valid, useful result — the
     entire point of this mechanism is to surface real gaps automatically,
     not to manufacture a passing report.
7. Verify the result with the existing `check#ProductCategoryCompliance`
   service (`moqui-cybersecurity-agent`) rather than re-deriving the
   category→group→feature traversal by hand — it already reuses
   `find#ProductFeatureGroups` (`mantle-usl`) for that.

## Validation rules (apply every time)

- `find#ProductFeatureGroups` requires its `applTypeEnumId` parameter to be
  passed as the exact real value (e.g. `"PfatStandard"`). Passing an empty
  string does **not** fall through its `ignore-if-empty` condition the way
  an absent/null parameter would, despite the service's own
  `default-value="PfatSelectable"` — this was confirmed by direct testing,
  not assumed from the entity/service definitions.
- Validate every generated XML file with a well-formedness check (e.g.
  Python's `xml.dom.minidom`) before attempting to load it. Never write
  `" -- "` inside an XML `<!-- -->` comment — it breaks the whole file's
  parsing, not just that comment. This has been the single most-repeated
  mistake when authoring Moqui seed XML in this project; check for it
  every time, in every new or edited comment, even after fixing it once.
- One `ProductFeature` record per specific value, never a shared "amount"
  or generic quantity field reused across different products/thresholds.

## Related

- `plm-bom-import` §4.5 — the real trigger point for Workflow B: every
  BOM-imported product gets a generic default classification that this
  workflow is meant to refine, ideally in the same session as the import.
- `product-content-attachment` — the datasheets/certificates it attaches
  are exactly the "evidence" Workflow B step 1 reads; classification
  quality improves whenever a new document is attached, not just at
  BOM-import time.
- `moqui-mcp/skills/moqui-datadocument-datafeed/SKILL.md` (same project) —
  use once classification results need to be projected into a denormalized
  `DataDocument`/OpenSearch read model for search/reporting, rather than
  queried live via `check#ProductCategoryCompliance`.
- A complete worked example (one real norm clause, one real product,
  verified end-to-end) exists in this project's design session log if you
  want to see this workflow applied once, start to finish, before applying
  it to a new norm or product — it is a reference for calibration, not a
  template to copy verbatim.
