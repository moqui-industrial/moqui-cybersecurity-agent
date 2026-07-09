---
name: math-model-run-tracking
description: Use when a service or script computes a result worth tracking over time (a score, a check, a classification, a simulation) and the question "what was the result last time, and what changed" needs to be answerable later. Prefer this over inventing a bespoke result/finding/assessment entity -- moqui-math already has the entities for tracking any calculated result's history, inputs, and outputs.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# MathModel Run Tracking

Before creating a new entity to store "the result of running X", check
whether `moqui-math`'s existing `MathModelDef`/`MathModel`/`MathModelRun`/
`MathModelData`/`MathModelPerf` already covers it. In this project they
already have covered every case checked so far. Do not invent a new
result-tracking entity (e.g. a `*Assessment`/`*Finding`/`*Report` table)
without first confirming these don't fit — check by reading the actual
entity definitions in `moqui-math/entity/MathEntities.xml`, not by
assuming from field names alone.

## Why this, not a bespoke entity

A one-off "result" entity typically ends up needing: an identifier for the
input, the computed output, when it ran, who/what ran it, whether it
errored, and (eventually) performance/cost data. `moqui-math` already has
exactly this, generically, already wired to `Graph`/`Vector`/`Matrix`/
`Tensor` for structured results:

- `MathModelDef` — the abstract definition of the calculation
  (`modelTypeEnumId`; use `MmtCodeDefinedFunction` for a plain
  rule-based/service-implemented calculation, not a trained/learned model).
- `MathModel` — one concrete, invokable instance of that definition.
  `MathModel.graphId` connects it to a `Graph` when the calculation
  operates on graph data.
- `MathModelRun` — one row per invocation: `startTime`/`endDate`,
  `parameters` (the input, as JSON), `results` (the output, as JSON),
  `hasError`/`errors`, `userId`. This is the history: list `MathModelRun`
  rows for a `MathModel` to see every past result, compare consecutive runs
  to see what changed, filter by `hasError` to find failures.
- `MathModelData` — links a `MathModel` to structured outputs
  (`Vector`/`Matrix`/`Tensor`/`GraphVertex`/`GraphEdge`), tagged with
  `generatedByRunId` so a specific run's structured output can be found.
  Use when the result is naturally multi-dimensional (e.g. a whole
  product-by-requirement compliance matrix), not just a list serialized as
  JSON text.
- `Parameter.mathModelId` — a scalar value attached directly to a
  `MathModel` (e.g. a current/latest summary score), reusing the same
  `Parameter`/`ParameterDef` EAV pattern already used for graph vertex/edge
  metadata elsewhere in this project.
- `MathModelPerf` — performance metrics per run (wall clock, CPU, memory,
  and ML-specific metrics like loss/F1/ROC-AUC if the calculation is ever
  swapped for a trained model instead of a hand-written rule).

## Workflow

1. Register the calculation once, as seed data: one `MathModelDef`
   (`modelTypeEnumId="MmtCodeDefinedFunction"` for a rule-based service) and
   one `MathModel` instance.
2. In the service that performs the calculation, at the start of the
   action, create a `MathModelRun` row referencing that `MathModel`, with
   `parameters` set to the input serialized as JSON (e.g.
   `groovy.json.JsonOutput.toJson([...])`), `startTime` set to now,
   `hasError="N"`.
3. Run the actual calculation as normal, wrapped in a `try`/`catch`.
4. On success, update the same `MathModelRun` row: `endDate`, `results` set
   to the output serialized as JSON. On failure, update it with `endDate`,
   `hasError="Y"`, `errors` set to the exception, then re-throw — a failed
   run is still a run worth recording, not a silently lost one.
5. If the result is naturally structured/multi-dimensional (a matrix, not
   just a flat list), also create the appropriate `Vector`/`Matrix`/`Tensor`
   record and a `MathModelData` row linking it to the `MathModel` with
   `generatedByRunId` set to the run that produced it.
6. Once results are persisted this way, define a `DataDocument` (see
   `moqui-datadocument-datafeed`, below) rooted at `MathModelRun` (or a
   view-entity joining it to whatever business context matters — the
   product/asset/device the calculation was run for) to make the run
   history searchable/dashboardable, instead of writing an ad hoc
   indexing script.

## Related

- `moqui-mcp/skills/moqui-datadocument-datafeed/SKILL.md` (same project) —
  use for the projection step in workflow point 6: prefer a declarative
  `DataDocument`/`DataFeed` over a custom indexing script whenever the
  source data already lives in Moqui entities, which it does once step 2-5
  above are in place.
- `norm-product-classification` (same project, `moqui-cybersecurity-agent/
  skills/`) — the input side for one concrete calculation this pattern
  applies to (checking a product's classified requirements against its
  actual features); this skill is about tracking and reporting on *any*
  calculation's results, not specific to that one.
