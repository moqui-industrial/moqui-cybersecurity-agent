---
name: compliance-scope-intake
description: Use at the START of any engagement that involves a real BOM/electrical-schematic upload, before running any classification or compliance-check skill - asks the user which compliance domain(s) they actually want (cybersecurity OT, UL/CSA electrical safety, IEC 60204-1 electrical safety, or a sequential combination), then routes to the right skill(s)/tools without ever re-requesting documents already ingested.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Compliance Scope Intake

This project's document ingestion (`plm-bom-import`, `product-content-attachment`) is shared
across every compliance domain this toolset supports - a real electrical BOM CSV, electrical
schematics, network diagram, datasheets, and certificates become the *same* `Product`/
`ProductAssoc`/`ProductContent` rows regardless of which norm they'll later be checked against.
The domains themselves are served by separate, independent components (`moqui-cybersecurity-agent`
for OT cybersecurity; `moqui-electrical-compliance-agent` for UL 508A/IEC 60204-1 electrical
safety) with their own `ProductCategoryType`/`ProductFeatureType` values
(`PctRegulatory`/`PftSafetyFunction`+`PftSecurityCapability` vs. `PctElectricalSafety`/
`PftElectricalSafety`), so their vocabularies and compliance checks never mix. What decides which
one(s) run is a single question asked once, at the start - not a document re-upload.

## The question to ask, before doing anything else

As soon as a real BOM/schematic upload or a request for "compliance analysis" is identified, ask
the user explicitly which of these they want (do not assume - a wrong assumption here means
running the wrong compliance engine on real data):

1. **Solo cybersecurity OT** - the existing TARA (`iso24882-risk-assessment`)/norm-product-
   classification/mechanical-safety-crosswalk flow. No electrical-safety tools are relevant.
2. **Solo conformità UL/CSA** - `electrical_find_classification_vocabulary`/
   `electrical_classify_product`/`electrical_check_product_category_compliance`, scoped to UL
   508A vocabulary only (filter or read results by category id prefix `NCAT_UL508A_`).
3. **Solo conformità IEC 60204-1** - same electrical tools, scoped to IEC 60204-1 vocabulary
   (`NCAT_IEC60204_`).
4. **UL/CSA oppure IEC 60204-1, seguita da cybersecurity OT** - the electrical checks run first
   (a panel's electrical build either targets the US/Canada market via UL/CSA or the IEC/EU market
   via IEC 60204-1 - **mutually exclusive**, a real panel has one destination market, never both
   at once; ask which market if not already stated), then the cybersecurity OT flow runs against
   the same already-classified products.

If the user's request doesn't make the scope obvious (e.g. they just say "analizza questa
distinta"), ask this question directly rather than defaulting to cybersecurity OT alone - the
electrical-compliance capability is easy to miss if never mentioned, and running the wrong (or
only one of several intended) engine on real data wastes the analyst's time reviewing the wrong
output.

## Routing after the answer

- **Cybersecurity OT only**: proceed directly with `norm-product-classification`
  (Workflow B) and the rest of the existing cyber toolset. Nothing from
  `moqui-electrical-compliance-agent` is called.
- **UL/CSA or IEC 60204-1 only**: run `electrical_find_classification_vocabulary` →
  `electrical_classify_product` → `electrical_check_product_category_compliance` against the
  already-ingested `Product`/`ProductAssoc` rows. Never call any `cyber_*` classification tool in
  this branch - it would apply the wrong vocabulary.
- **Sequential (electrical then cyber)**: run the electrical branch first (it typically drives
  physical/mechanical classification decisions - e.g. enclosure IP rating, grounding scheme - that
  the cyber OT risk analysis can then treat as already-established fact), then hand off to the
  cybersecurity OT flow on the same products. Do not re-run `plm-bom-import` between the two -
  the BOM was already ingested once, at the start.

## What this skill deliberately does NOT do

It does not itself extract vocabulary from new norms (that's `norm-product-classification`'s
Workflow A, already generic across domains - reused as-is for UL 508A/IEC 60204-1, no
modification needed) and it does not itself ingest documents (that's `plm-bom-import`/
`product-content-attachment`). It is purely the up-front routing decision - keep it that way; if
a third compliance domain is added later, this skill only needs a new question option and a new
routing branch, not new ingestion or extraction logic.
