---
name: cyber-project-template
description: Use when starting a new OT cybersecurity assessment case (a new machine/locale) - instantiate a real project (milestones, tasks, WikiSpace) from the reusable TEMPLATE_OT_CYBER_ASSESSMENT project instead of hand-writing a new WorkEffort seed-data file per case. Also documents how the generic project/task structure maps to this project's other skills, so a new assessment can be driven task-by-task.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Cyber Project Template

Every earlier case (Smoking Cell 1) got a hand-written, case-specific
`WorkEffort` seed-data file modeled loosely on the previous one - workable
once, not a repeatable process. `data/CyberProjectTemplateSeedData.xml`
(`type="seed-initial"`, always loaded) is the fix: one reusable
project (`TEMPLATE_OT_CYBER_ASSESSMENT`, 5 milestones, 21 tasks) plus a
`WikiSpace` (`TEMPLATE_OT_CYBER`) with placeholder pages for every
deliverable this project's other skills produce. **Never edit this
template's rows directly** - it is reference data shared by every future
case, the same principle already used for the ATT&amp;CK taxonomy and
`AssetClass`.

## 1. Instantiate a new case: clone, don't hand-write

Use the real, already-existing, generic
`mantle.work.WorkEffortServices.clone#WorkEffort` service
(`mantle-usl/service/mantle/work/WorkEffortServices.xml`) - it was
built for exactly this (deep-clone a `WorkEffort` tree with a
consistent id-prefix scheme), not something this project had to invent.

```
clone#WorkEffort(
    baseWorkEffortId: "TEMPLATE_OT_CYBER_ASSESSMENT",
    workEffortId: "CYBER_<CASE>",          // e.g. CYBER_NEWLOCALE1
    deepClone: true,
    deepIdIsPrefix: true,
    idPrefix: "<CASE>-",                    // e.g. "NL1-" -> NL1-MS-01, NL1-T-01, ...
    clearDates: true,                       // template has no real dates to inherit
    copyAssoc: true,                        // REQUIRED - WorkEffortAssoc (task->milestone
                                             // links) defaults to false; without this every
                                             // task clones as an orphan, disconnected from
                                             // its milestone
    workEffortName: "<real case name>",
    description: "<real case description>"
)
```

Then, separately (the clone service only clones the `WorkEffort` tree,
not the `WikiSpace`):
1. Create a new case `WikiSpace` (a new `wikiSpaceId`, `rootPageLocation`
   pointing at a new `component://.../WikiSpace/<CASE>.md` file, copied
   from `WikiSpace/TEMPLATE_OT_CYBER.md` with the placeholders replaced
   by real content as the case progresses).
2. Create matching `WikiPage` rows and physical `.md` files under
   `WikiSpace/<CASE>/`, one per real deliverable (start from the 4
   template placeholder pages, don't invent new ones unless the case
   genuinely produces something the template didn't anticipate).
3. Link each real deliverable page to the cloned project via
   `mantle.work.effort.WikiPageWorkEffort`, same pattern as
   `CyberSmoking1ProjectSeedData.xml`.

**Verify the clone before relying on it - a real gap was found and
confirmed while building this skill, not a hypothetical one**:
`copyAssoc=true` does copy the 21 `WorkEffortAssoc` rows, but the
generic `clone#WorkEffort` only remaps the `workEffortId` (FROM) side to
the new id - the `toWorkEffortId` (the task each association points at)
is copied verbatim, still pointing at the **template's own** `TPL-T-*`
tasks, not the newly-cloned ones (confirmed: cloning
`TEMPLATE_OT_CYBER_ASSESSMENT` produces real new task ids like
`CYBER_TESTCLONE-100000`, but every `WorkEffortAssoc.toWorkEffortId`
still reads `TPL-T-01` etc.). This is a real limitation of the generic
service for a deep project-tree clone, not something `copyAssoc` alone
fixes.

Fix-up after every clone, before using the new project: for each
cloned milestone (`rootWorkEffortId = <new project>`,
`workEffortTypeEnumId = WetMilestone`), match it to its template
counterpart by `workEffortName` (preserved verbatim by the clone), then
for each `WorkEffortAssoc` row now dangling on that milestone, replace
`toWorkEffortId` with the cloned task that has the same `workEffortName`
as the template task the row currently points at. Do this via a short
script/service keyed on `workEffortName`, not by assuming any id
pattern (`deepIdIsPrefix`/`idPrefix` did not produce the prefixed ids
this skill originally assumed either - verify the real ids generated
before writing any fix-up logic, don't guess the scheme). A dedicated
`fix#ClonedProjectAssoc` service would be the natural next step if this
template gets used often enough to justify it - not yet built.

## 2. What each milestone actually drives (cross-reference to skills)

The template's tasks are not busywork - each one is the real trigger
for a specific mechanism already built in this project. Work the tasks
in order; skipping MS-01's document-acquisition tasks means the later
milestones' checks will honestly (and correctly) report "no data on
record" rather than a false positive:

- **MS-01** (document acquisition) - the checklist is `plm-bom-import`
  §6 in full: not just electrical BOM/schematics (T-02) and PLC/C
  sources (T-03), but also mechanical/P&amp;ID/ISO 12100 (T-04) and
  remote-access/comms-matrix/manuals/RBAC (T-05) - the two gaps a prior
  case (Smoking Cell 1) never had documents for.
- **MS-02** (graph construction + crosswalk) - `plm-bom-import` (T-08),
  `plc-code-security-analysis` (T-09, T-12),
  `norm-product-classification`/`device-group-zone-modeling` (T-10),
  `mechanical-safety-crosswalk` (T-11).
- **MS-03** (TARA) - `iso24882-risk-assessment`, unchanged from the
  original 7-step methodology.
- **MS-04** (threat/vulnerability taxonomy) - `cyber-vulnerability-intelligence`.
- **MS-05** (finalize) - T-19 is new and deliberately first: verify
  every `cyber_*` MCP tool the case will need actually works against
  this case's real data (see `moqui-mcp/service/org/moqui/mcp/
  McpServices.xml` for the current registered set) before writing the
  report, not after.

## Related

- `math-model-run-tracking`, `norm-product-classification`,
  `device-group-zone-modeling`, `iso24882-risk-assessment`,
  `cyber-vulnerability-intelligence`, `plm-bom-import`,
  `mechanical-safety-crosswalk`, `plc-code-security-analysis` - every
  task in this template exists to drive one of these.
