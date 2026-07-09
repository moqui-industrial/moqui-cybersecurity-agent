---
name: product-content-attachment
description: Use whenever the user wants to attach a document (datasheet, catalog, CE/PED/UL-CSA certificate, manual) to one or more Products already modeled via plm-bom-import - e.g. after uploading a file in LibreChat. MANDATORY - always ask the user first whether the document is specific to a single product or covers an entire product family; never assume either way.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Product Content Attachment

A real BOM import (`plm-bom-import`) gives a machine's Products and
categories; it never attaches the actual documents (datasheets,
catalogs, certificates) a user uploads afterward. This skill is that
missing step - and it has one binding behavioral rule that comes before
any tool call.

## 0. Ask before attaching - always, no exception

Before calling either tool below, ask the user explicitly which case
applies - phrase it however is natural, but the substance must always
be asked, never inferred from context or the file itself:

> "Questo documento è specifico per un singolo prodotto, oppure vale
> per un'intera famiglia di prodotti (es. un catalogo che copre più
> taglie)?"

Do not guess from the filename, from how many products are in the
current conversation, or from anything else. This is reinforced (not
replaced) by the tool design itself: `cyber_attach_product_content` and
`cyber_attach_product_family_content` are two separate MCP tools, not
one tool with a `scope` parameter - naming the tool call is itself the
decision point, so the question cannot be silently skipped by picking a
convenient default.

## 1. How a file actually reaches Moqui (real architecture, not FileItem)

The real mantle-usl content services
(`mantle.product.ProductServices.create#ProductContent`/
`create#ProductCategoryContent`) expect a genuine multipart-upload
`FileItem`, which an MCP JSON-RPC tool call does not naturally carry.
This project's real transport is a **bind mount**, not base64 and not a
named Docker volume: LibreChat runs from a separate, already-deployed
stack in `/home/igor/development/projects/moqui/moqui-industrial/
moqui-deploy/ai/` (compose file `librechat-compose.yml`, kept outside
`moqui-mcp` and outside this project entirely - not
`moqui-deploy/ai/docker-compose.yml` in this repo, which is dead/never
started). It writes uploads to a host path also readable by the Moqui
process: `moqui-deploy/ai/librechat/uploads/` bind-mounted to
`/app/uploads` in the container, with `fileStrategy: "local"` set in
that same stack's `librechat.yaml`. Both new services
(`moqui-cybersecurity-agent/service/org/moqui/cyber/
CyberProductContentServices.xml`) take a `sourceFilePath` parameter and
read it directly via `ec.resource.getLocationReference(...)`, never raw
bytes.

**Do not expect the calling agent to know the real absolute path** -
pass just the plain filename as shown in the chat attachment. A
file-capable LLM endpoint (e.g. GPT-4.1 via LibreChat's OpenAI
integration) reports an attached file using its *own provider's*
sandbox convention (`/mnt/data/<filename>` for OpenAI), not LibreChat's
real bind-mount path - LibreChat never surfaces that real path to the
model at all, so this is not something a better prompt or a config
change can fix. Both services handle this by design: `sourceFilePath` is
tried as a literal path first, and if that doesn't exist, its *basename*
is searched recursively under `cyber.librechat.uploads.root`
(`moqui-cybersecurity-agent/MoquiConf.xml`, defaults to the real host
uploads path) against LibreChat's real on-disk naming convention
(`<fileId>__<original filename>`) - most recently modified match wins.
So whether the agent passes `/mnt/data/x.pdf`, a bare `x.pdf`, or the
real absolute path, all three resolve correctly - no need to coach the
agent into producing a specific path format.

## 2. Case 1: single product → `cyber_attach_product_content`

Wraps `create#mantle.product.ProductContent` (entity-auto) plus the
same `dbresource://mantle/content/product/${productId}/...` path
convention the real `save#ProductContentFile` uses, adapted to a local
path source. Pick `productContentTypeEnumId` from the real, specific
values already in this project - prefer the specific certification
scheme over the generic bucket when the document says which one it is:
`PcntCeCertificate`/`PcntPedCertificate`/`PcntUlCsaCertificate` (added
alongside this skill - a PED certificate does not satisfy a CE
requirement or vice versa, worth distinguishing at the enum level, not
folded into one generic `PcntCertificate`), `PcntCertificate` (generic/
unspecified), `PcntDatasheet`, `PcntCatalog` (a catalog page for one
specific product), `PcntOperatingManual`, `PcntElectricalSchematic`,
`PcntBillOfMaterials`.

## 3. Case 2: product family → `cyber_attach_product_family_content`

Three things happen in one call, always in this order, never as
separate manual steps:
1. **Find-or-create the family `ProductCategory`** - exact
   `categoryName` match first (never duplicate a family category that
   already exists, same discipline as `plm-bom-import`'s category
   derivation); create on the fly (`create#mantle.product.category.
   ProductCategory`) only if genuinely none matches.
2. **Ensure `ProductCategoryMember` for every given `productId`** -
   idempotent (skips products already members), but never skipped
   entirely: a family document attached to an empty or partially-
   populated category is a real modeling gap, not an acceptable
   shortcut. The product list usually comes directly from the same BOM
   import this family belongs to (`plm-bom-import`) - if it's not
   obvious which real products belong to the family from context, ask
   the user rather than guessing from naming similarity alone.
3. **Attach the content** via `create#mantle.product.category.
   ProductCategoryContent`, same local-path-read pattern as Case 1.

`categoryContentTypeEnumId` uses a **different enum type**
(`ProductCategoryContentType`, not `ProductContentType` -
`ProductCategoryContent.categoryContentTypeEnumId`'s real relationship,
verified via the entity definition) - mirrored value-for-value with
Case 1's set: `PcctCeCertificate`/`PcctPedCertificate`/
`PcctUlCsaCertificate`/`PcctCertificate`/`PcctDatasheet`/`PcctCatalog`/
`PcctOperatingManual`. Do not reuse `Pcnt*` values here - the FK target
is a different Enumeration set.

## Related

- `plm-bom-import` - source of the Products/ProductCategory this skill
  attaches documents to; its category-derivation discipline ("derive
  from real function, never duplicate an existing category") applies
  identically to family lookup here.
- `math-model-run-tracking` - both new services log a `MathModelRun`
  (which document, which product/family, when).
- `norm-product-classification` - a certificate/datasheet attached here
  is exactly the kind of evidence that later grounds a real (not
  assumed) compliance classification.
