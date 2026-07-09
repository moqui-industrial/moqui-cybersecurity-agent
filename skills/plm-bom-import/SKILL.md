---
name: plm-bom-import
description: Use when a real bill-of-materials export (EPLAN-style CSV, or similar CAD/ERP parts list) needs to become complete Moqui PLM seed data - Product, ProductAssoc (BOM structure), ProductCategory, and selective ProductFeature - for a machine/locale being onboarded into this project. Also the reference checklist for what document set (electrical, mechanical, safety, network, procedural) a complete IEC 62443-style OT risk assessment actually needs before it can assign a defensible risk/impact level.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# PLM / BOM Import

Converting a real distinta base into Moqui seed data is a mechanical,
repeatable transform once the source format's quirks are known - the goal
is to encode that transform once, generate XML with a script (never
transcribe a BOM of any real size by hand), and keep the Moqui PLM model as
complete as the real source data allows, no more and no less.

## 1. EPLAN CSV export format (real, verified quirks)

- **Encoding is UTF-16LE**, not UTF-8 - `open(path, encoding="utf-16-le")`
  in Python, `csv.reader(..., delimiter=";")` (never a naive `str.split(";")`:
  several real columns, e.g. multi-locale descriptions, contain literal `;`
  characters inside a field).
- **Two header rows**, not one: row 0 is a coarse group label
  (`device`/`device/part`), row 1 has the real field names
  (`P_ARTICLE_TYPENR`, `P_ARTICLEREF_PARTNO`, ...). Data starts at row 2.
- **`P_ARTICLE_DESCR1` is multi-locale**, format `locale@text;locale@text;...`
  (e.g. `en_US@...;it_IT@...`) - parse it, prefer `en_US`, fall back to
  `it_IT`, then to whatever is present. Never copy the raw multi-locale
  string into `productName`/`description`.
- **`P_ARTICLE_MANUFACTURER` is an abbreviated code** (`SIE`=Siemens,
  `RIT`=Rittal, `WEI`=Weidmüller, `DAN`=Danfoss, `PXC`=Phoenix Contact,
  ...). Expand only the codes you can verify with confidence; leave an
  unrecognized code as-is in `pseudoId`/`productId` rather than guessing a
  full manufacturer name.
- **A distinct part (`P_ARTICLE_TYPENR`) can appear on many rows**, one per
  physical instance/device-tag (`P_FUNC_DEVICETAG_MAIN`). Aggregate by
  `P_ARTICLE_TYPENR`: sum `P_ARTICLEREF_COUNT` across its rows for the real
  total quantity, collect the device tags for traceability. This is not
  just data hygiene - `ProductAssoc`'s primary key
  (`productId`+`toProductId`+`productAssocTypeEnumId`+`fromDate`, see
  `mantle-udm/entity/ProductDefinitionEntities.xml`) has no `sequenceNum`,
  so it cannot hold one row per device-tag instance of the same part
  without a PK collision - aggregation is a schema requirement, not a
  choice.
- **`P_ARTICLEREF_ASSEMBLY`/`MODULE_PART`/`ASSEMBLYSTRUCTURE`** encode a
  multi-level sub-assembly hierarchy *when populated* - check them before
  assuming a flat, one-level BOM. In the first real case handled by this
  skill (Smoking Cell 1, `hvac-cell/Distinta.csv`) they were empty on every
  row: a genuinely flat panel→components BOM, not a simplification.
- **22 real `P_ARTICLE_SAFETYRELATED_*` columns exist** (PL, SILCL, PFHd,
  MTTFd, MTBF, B10, B10d, hierarchy levels 1-5) - real EPLAN functional-
  safety fields, distinct from the general BOM columns. Extract them
  generically (if populated, write a `ProductFeature` with
  `productFeatureTypeEnumId="PftSafetyFunction"`, one per populated
  column) - don't special-case them away just because they were empty in
  the first real case. An empty result here is a real finding about that
  specific export, not a reason to skip the extraction logic.

## 2. Product identity and fields

- `productId` = `PROD_<MFR>_<sanitized part code>`, same convention as
  every other Product in this project - keep it well under the `type="id"`
  `VARCHAR(40)` limit; a few real Danfoss part numbers in this domain are
  already 40 characters on their own, so a mnemonic short id (e.g.
  `PROD_DAN_FC102_3K0`) plus the full code in `pseudoId` is the fix, not a
  truncated/hashed id.
- `pseudoId` = the real manufacturer part number (`text-short`,
  `VARCHAR(63)` - long enough for the full code even when `productId`
  can't hold it).
- `productTypeEnumId="PtAsset" assetTypeEnumId="AstTpEquipment"
  assetClassEnumId="AsClsMfgEquip"` for a real physical BOM component -
  same convention as every Product already in this project's HVAC-cell
  case.
- `productName`/`description`: derive `productName` from the parsed,
  cleaned description (truncated for readability, not just
  `"<manufacturer> <part number>"` - a mfr+code pair is unique but not
  informative on its own), keep the full parsed text in `description`.
- **Before creating a new Product, check whether the part already exists**
  under a different case's seed data in this same file (matched by
  `pseudoId`/real part number) - reuse the existing `productId` in the
  `ProductAssoc` line rather than creating a duplicate Product record.

## 3. BOM structure via ProductAssoc

A BOM is a **product structure**, not an asset fact - model the
assembly (panel/machine) itself as its own `mantle.product.Product`
with `productTypeEnumId="PtPickAssembly"` ("Pick Assembly", real
`ProductType` value - verified in `ProductDefinitionEntities.xml`), separate
from the physical `Asset` instance it corresponds to. Link the two by
setting `productId` on the `Asset` record - the `Asset` is "this specific
installed instance," the `Product` is "the design/BOM it was built from,"
same distinction Silverston's *Data Model Resource Book* Vol.1 draws
between a product and an actual/tracked item.

One `mantle.product.ProductAssoc` row per distinct component, from the
assembly `Product` to the component `Product`,
`productAssocTypeEnumId="PatMfgBom"` (Manufacturing BOM - real value, child
of the parent `PatComponent` type; `PatEngBom` is the sibling "as-designed"
variant, use it instead if the source document is explicitly an
engineering, not manufacturing, BOM). `quantity` = the aggregated real
total (see §1); `reason` can carry the aggregated device tags for
traceability back to the schematic - short, non-identifying reference
designators (`F1, F11, F12`), not a violation of this project's
anonymization rule.

## 4. ProductCategory: derive from real function, not source codes

EPLAN's own `P_ARTICLE_PRODUCTGROUP`/`PRODUCTSUBGROUP`/`PRODUCTTOPGROUP`
codes are internal numeric IDs with no public meaning - use them only as
an internal grouping key while building the mapping, never as the
`ProductCategory` name or description shown to a user. Derive the real
category from what the parts actually are (read the parsed description),
grouped at a level useful for the norm-crosswalk work this feeds into
(`norm-product-classification`) - e.g. `Circuit Protection`, `Terminal
Blocks`, `Control Relays & Contactors`, `Enclosure & Wiring Accessories`,
not a 1:1 mirror of the source's internal taxonomy.

If a real, already-existing category fits (e.g. a fuse holder module for
an already-modeled Remote I/O station belongs in the same `PRODCAT_REMOTE_IO`
category as the station itself), reuse it - don't create a near-duplicate
category per BOM import.

**Reserve, don't populate, categories for scope you don't have data for
yet.** A `PRODCAT_MECHANICAL_ACTUATOR` category can exist as an empty
bucket ahead of a real mechanical BOM being available - a category
definition asserts a taxonomy slot, not a fact about any specific product,
so this doesn't violate the "don't invent data" rule the way a fabricated
`ProductCategoryMember` or `ProductFeature` value would.

## 4.5. Classification: refine the generic default against norm vocabulary

§2's default (`assetClassEnumId="AsClsMfgEquip"`, and no `deviceTypeEnumId`
at all) is a placeholder, not a finished classification. **This step is
mandatory, not optional** - a product left on the generic default when
better norm-derived vocabulary genuinely exists is an unfinished import,
not an acceptable shortcut (the user has explicitly said they don't
expect to classify better than the agent, so silently skipping this is a
regression). Run it right after §4, for every product just imported:

1. Call `cyber_find_classification_vocabulary` (optionally with a keyword
   drawn from the part's description) to see the real candidate
   `DeviceTypeEnumId`/`AssetClassEnumId` trees and norm-derived
   `ProductCategory` list.
2. Classify hierarchically, most-specific-first:
   - Only attempt `deviceTypeEnumId` if the component is genuinely
     electronic/automation - in practice, only for the subset of BOM lines
     that get (or already have) their own `moqui.device.Device` row
     (network gear, controllers, sensors with a communication interface).
     Most BOM lines (breakers, terminal blocks, mechanical hardware) never
     reach this branch, and that's expected, not a gap.
   - Always attempt `assetClassEnumId` - every real physical component has
     one; this is the branch that actually replaces `AsClsMfgEquip` for
     most BOM items.
   - Independently, always attempt matching against norm-derived
     `ProductCategory` records too (a component can be both a specific
     `AssetClassEnumId` value and a member of a regulatory
     `ProductCategory` - see `norm-product-classification`).
3. If the evidence (BOM description, already-attached datasheet/
   certificate) gives no confident match for a component that plausibly
   has one, **ask the user explicitly** rather than guessing or silently
   leaving the generic default - same mandatory-question discipline as
   `product-content-attachment`'s single-product-vs-family rule. It is
   fine, and expected, for many BOM items to legitimately end at the
   generic default when no more specific vocabulary applies - the
   mandatory question is for genuine ambiguity, not for every item.
4. Call `cyber_classify_product` to apply the decision once made.

Full detail (why this order, what to do with the evidence, how it feeds
back into `check#ProductCategoryCompliance`): `norm-product-classification`
Workflow B.

## 5. ProductFeature: selective, grounded in the actual source text

Add a `ProductFeature` (`productFeatureTypeEnumId="PftHardware"` for a
general technical spec, `PftSafetyFunction` for the EPLAN safety-related
columns from §1) only when the parsed description or a dedicated BOM
column states a real, differentiating technical value (pole count, current
rating, power rating, channel count). Do not add one for every part just
for uniform coverage - a cable duct or DIN rail has no differentiating
technical spec in a typical BOM export, and inventing one to "complete"
the model would be exactly the kind of fabricated data this project
avoids. The judgment call is the same one already used in
`norm-product-classification`: model what the real source actually states,
surface the absence as a real gap rather than papering over it.

## 6. Document checklist for a complete OT risk assessment

A real IEC 62443-style risk/impact assessment needs more than the
electrical BOM this skill directly imports - electrical+software tells you
*how* an attacker gets in, not the *consequence* of what they can do once
inside, and not the *procedural* attack surface. Before treating a new
locale/machine's document set as complete, check for all of:

1. **Network topology** - cables, switches, IP/VLAN plan (often not in the
   electrical schematic at all).
2. **Electrical BOM/schematics** - what this skill directly imports.
3. **SBOM** - firmware/OS versions, PLC/HMI project versions.
4. **Mechanical layout / P&ID / mechanical BOM** - what a given electrical
   output *physically drives* (mass, speed, temperature) determines the
   real consequence severity of forcing it; without this, a risk/Security
   Level assignment is a guess, not an assessment.
5. **Safety risk analysis (ISO 12100)** - physical guards/interlocks that
   an attacker would have to defeat mechanically even after a successful
   cyber intrusion; **do not import an ISO 12100 hazard-category taxonomy
   from memory** - only from a real, loaded copy of the standard's text,
   same discipline already used for IEC 62443/ISO 24882 (PDF extraction →
   verified quotes → `Enumeration`), never from training-data recall.
6. **Remote-access/teleassistenza architecture** - statistically the most
   common real intrusion vector; already modelable with existing
   `moqui.device.DeviceConnection` (`purposeEnumId="DcpMaintenance"/
   "DcpDiagnostics"`, `userId` explicitly designed for externally
   authenticated accounts) plus a `DeviceGroupMember
   purposeEnumId="DgmpZoneBoundary"` conduit, per `device-group-zone-modeling`
   - no new schema needed for this one.
7. **Communication matrix** (who talks to whom, on which port/protocol) -
   `org.moqui.cyber.CyberDeviceCommunicationFlow`.
8. **Operating/maintenance manuals** - `AssetContent`/`ProductContent`/
   `DeviceContent` with `contentTypeEnumId="AcntOperatingManual"` (etc.) -
   procedural findings (documented default credentials, USB-based recipe
   loading) become `ThreatScenario`/`CyberVulnerability` once a real manual
   is read, no new schema needed for the content pointer itself.
9. **RBAC / roles-and-access matrix** -
   `org.moqui.cyber.CyberDeviceAccount`.

Items 7 and 9 above are new, deliberately empty entities in this project
(`entity/CyberDeviceProcessEntities.xml`) - schema ready, populated only
from a real document, never fabricated ahead of one.

## Related

- `norm-product-classification` - §4.5 above triggers its Workflow B for
  every imported product; the categories this skill creates in §4 are
  also a join key that crosswalk consumes independently.
- `device-group-zone-modeling` - zone/conduit and remote-access modeling,
  reused as-is for item 6 above, not duplicated here.
- `mantle-usl/data/ZcaProductDemoData.xml` - the canonical, complete
  worked example of the underlying Moqui Product/ProductAssoc/
  ProductCategory/ProductFeature entities this skill targets.
- Silverston, *The Data Model Resource Book* Vol.1, PRODUCT chapter - the
  underlying conceptual model (product vs. actual item, product
  structure/BOM) Moqui's `mantle.product` package implements.
