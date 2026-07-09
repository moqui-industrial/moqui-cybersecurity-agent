# moqui-cybersecurity-agent

OT cybersecurity knowledge base and risk-assessment component for Moqui, built
using `moqui-mcp`'s method (Graph on `moqui-math`, DataDocument/DataFeed → OpenSearch,
MCP tool exposure) and reusing `moqui-source-knowledge`'s parser → IR → graph
pipeline pattern for structured extraction from source documents.

Full design rationale and decision history:
`/home/igor/development/projects/cybersecurity/design-session/SESSION.md`.

## Status: fully verified end-to-end against a live server (2026-07-03)

Real Moqui server run on port **8081** (8080 was occupied by another project's
instance), real Docker OpenSearch on port **9201** (9200 was occupied), real
OpenAI embedding calls. Auth: `john.doe`/`moqui` (needs `ADMIN` group —
load `moqui-mcp`'s `data/McpDemoSeedData.xml` via
`./gradlew load -Ptypes=demo` if not already loaded).

Verified working end-to-end:
- `load#NormGraph`: 1844 vertices / 2237 edges loaded into `moqui.math.Graph`.
- `search#NormClauses` (direct entity, literal substring): correct results.
- `index#NormDocuments`: 1671/1672 clauses embedded (OpenAI
  `text-embedding-3-large`) and indexed into OpenSearch (1 unexplained
  singleton failure, not investigated further).
- `search#NormClausesSemantic` (hybrid BM25+kNN): excellent real-world
  results, e.g. "network segmentation into zones and conduits" correctly
  surfaces IEC 62443-4-2 §9.3.1, IEC 62443-3-3 §9.1, IEC 62443-3-2 §4.4.1 in
  that order.
- MCP tools `cyber_search_norms` and `cyber_search_norms_semantic` (new),
  both wired into moqui-mcp's dispatcher, tested through the real
  `/mcp/message` transport with a real session handshake.

### Six real bugs found and fixed while getting this working

1. `GraphVertex.label` is `VARCHAR(63)` (`text-short`), not 255 as first
   assumed — added truncation (63 chars, first 60 + `...`) in `load#NormGraph`,
   matching moqui-mcp's own `load#ArtifactGraph` convention (truncate at load
   time in Groovy, keep full labels in the Python-generated JSONL).
2. `data/CyberNormGraphMetadataSeedData.xml` is `type="seed-initial"`, which
   is *not* loaded automatically by `./gradlew run` if the database already
   has data (only fires on a genuinely empty DB via `entity_empty_db_load`) —
   must run `./gradlew load -Ptypes=seed,seed-initial` explicitly after
   adding new `ParameterDef` records, with the server stopped first (a
   separate `load` JVM cannot run concurrently with a live server: both the
   H2 file lock and the Bitronix transaction log lock conflict).
3. `search#NormClauses` and `index#NormDocuments` originally used declarative
   `<entity-find>`/`<limit-range max="${limit}"/>` — wrong attribute name
   (should be `size`/`start`, not `max`) and GString interpolation inside
   `value="%${queryText}%"` doesn't parse in xml-actions. Rewrote both as
   plain Groovy `ec.entity.find(...)` calls.
4. `documentId` was referenced in both search services and in results but
   was never actually captured as vertex metadata — added
   `CyberNormDocumentIdParam`, a view-entity join/alias, and the attribute in
   `generate_norm_graph.py`.
5. `index#NormDocuments`'s per-clause embedding loop ran inside one shared
   transaction; a single `ArtifactQueryEmbeddingCache` write conflict (likely
   two clauses across different documents sharing byte-identical boilerplate
   text, and thus the same cache key) marked the *whole* transaction
   rollback-only, cascading failure to every remaining clause. Fixed with
   `.requireNewTransaction(true)` on the embedding call so one bad clause
   can't poison the batch.
6. moqui-mcp's `get#QueryEmbedding` rejects `<`/`>` in `queryText` (HTML-safety
   validation) — real standard clauses legitimately contain these (inequality
   text, ranges). Strip them before embedding (only affects what gets
   embedded, not the stored `clauseText`).

Also found while investigating: the native `runtime/opensearch` install's
`bin/opensearch-plugin install opensearch-knn` fails in this environment
(network to `artifacts.opensearch.org` blocked; `docker pull` and
`api.openai.com` both work) — this is why Docker was used instead. Also,
`./gradlew run` auto-starts the project's own native `runtime/opensearch` as
a side effect regardless of the external `elasticsearch_url` override; it's
harmless (unused) but wastes resources — consider `no-run-es` if this
matters.

## Phase 1 scope (implemented)

Normative graph: parse OT cybersecurity norm PDFs (IEC 62443 series, EU Machinery
Regulation, Top 20 Secure PLC Coding Practices, ...) into a vendor-neutral IR, then
into a deterministic `Graph`/`GraphVertex`/`GraphEdge` export, loadable into Moqui.

- `entity/CyberNormGraphExtensions.xml` — `CyberNormVertexMeta`/`CyberNormEdgeMeta`
  pivot view-entities over `moqui.math.Parameter` (EAV pattern, reusing the
  `Parameter.graphId/graphVertexId/graphEdgeId/textValue` extension already
  provided by the `moqui-mcp` dependency — not redeclared here).
- `data/CyberNormGraphMetadataSeedData.xml` — `ParameterDef` catalog for
  vertex/edge metadata (vertex type, clause number/title/text, document family,
  provenance class, relation confidence/rationale).
- `tools/norm-indexer/` — the actual pipeline:
  - `parser/text_extractor.py` — PDF → text via `pdftotext -layout`
  - `parser/clause_segmenter.py` — three pluggable per-family segmenters:
    `numbered-list`, `en-iec-hierarchical`, `eu-regulation-article`
  - `parser/cross_reference_extractor.py` — regex-based cross-reference detection
    between standard designators/articles/annexes
  - `parse_norm_sources.py` — orchestrator, config → IR JSONL
  - `validate_norm_ir.py` — hand-rolled JSON Schema validation (no external
    dependency), same approach as moqui-source-knowledge's `validate_ir.py`
  - `generate_norm_graph.py` — IR → deterministic graph JSONL export
    (`stable_hash`-based vertex/edge ids), same technique as
    moqui-source-knowledge's `generate_plc_graph.py`
  - `config/norm-sources.json` — per-document family/edition/designator config
- `service/org/moqui/cyber/CyberNormServices.xml`:
  - `load#NormGraph` — loads the graph JSONL into
    `moqui.math.Graph`/`GraphVertex`/`GraphEdge`/`Parameter`
  - `search#NormClauses` — direct entity-based clause search over
    `CyberNormVertexMeta` (functional without OpenSearch; OpenSearch/DataDocument
    projection and semantic/embedding search are Phase 6, not yet built)
- MCP tool `cyber_search_norms` wired into `moqui-mcp`'s existing dispatcher
  (`McpServices.xml`), since this component depends on `moqui-mcp` to reuse its
  `EnhancedMcpServlet`/tool-dispatch infrastructure instead of building a new one.

### Verified (standalone, no live Moqui/OpenSearch server available in this session)

```
cd tools/norm-indexer
python3 -m unittest discover -s tests -p 'test_*.py'   # 11 tests, all pass
python3 parse_norm_sources.py --config config/norm-sources.json \
    --source-root <cybersecurity-project-root> --output-dir work/ir
python3 validate_norm_ir.py --ir-dir work/ir --schema-dir ir/schema
python3 generate_norm_graph.py --ir-dir work/ir --output-dir work/graph --graph-id OtCyberNormGraph
```

Run against the 6 documents configured in `config/norm-sources.json`:
1097 clauses, 1535 relations, 6 documents, 1238 graph vertices, 1534 graph edges.
A real cross-standard reference was correctly extracted and resolved (e.g. IEC
62443-3-2 clause 4.6.7.2 → IEC 62443-3-3, and Top 20 Secure PLC Coding Practices
item 20 → IEC 62443-4-1).

Known limitation found during verification: one duplicate clause number
(`IEC-62443-4-1` clause `11.4`, appearing twice in the source) collapses to a
single graph vertex — affects 1 of 1097 clauses; documented, not yet fixed.

### Not yet verified (needs a running Moqui server + OpenSearch, unavailable in
this session)

- `load#NormGraph` and `search#NormClauses` are written following the exact
  patterns already proven in `moqui-mcp` (`load#ArtifactGraph`,
  `AgentArtifactVertexMeta`) but have not been executed against a live database.
- The `cyber_search_norms` MCP tool wiring is static/reviewed, not exercised
  end-to-end through the MCP transport.
- OpenSearch/DataDocument projection and embeddings (Phase 6) are not built yet.

## OpenSearch and semantic search (added, partially verified)

- `tools/norm-indexer/opensearch-mapping-cyber-norms.json` — index mapping with
  a `knn_vector` embedding field (3072 dims, hnsw/lucene/cosinesimil — same
  settings moqui-mcp uses).
- `service/org/moqui/cyber/CyberNormServices.xml`:
  - `index#NormDocuments` — reads `CyberNormVertexMeta` clause rows, calls
    moqui-mcp's existing `AgentDocumentServices.get#QueryEmbedding` (same
    provider/model/cache, not duplicated), bulk-indexes via moqui-mcp's
    existing `ElasticBackendAdapter`.
  - `search#NormClausesSemantic` — hybrid BM25 + kNN query (`bool`/`should` of
    `match` + `knn`) against the index built above.
  - Both are written and reviewed but **not runtime-verified** (no live Moqui
    server this session) — same limitation as `load#NormGraph`.

**Environment finding**: the native `runtime/opensearch` install has an empty
`plugins/` directory (no `opensearch-knn`), and `bin/opensearch-plugin install
opensearch-knn` fails in this environment (network access to
`artifacts.opensearch.org` is blocked, confirmed via direct test — `docker
pull` works fine, `curl` to the OpenSearch artifact host returns 403). The
official `opensearchproject/opensearch` Docker image bundles `opensearch-knn`
out of the box. **Recommendation for this project: use Docker for
OpenSearch**, not the native `runtime/opensearch` install, unless the knn
plugin is installed there through some other channel.

**Verified for real** (own throwaway harness, not part of the shipped
component — see
`/tmp/claude-1000/.../scratchpad/verify_semantic_search.py` from the session
that did this, not committed here): started
`opensearchproject/opensearch:2.19.0` via `docker run -d --name
cyber-norms-opensearch -p 9200:9200 -p 9600:9600 -e
"discovery.type=single-node" -e "DISABLE_SECURITY_PLUGIN=true"
opensearchproject/opensearch:2.19.0`; confirmed `opensearch-knn` plugin
present and cluster green; created the real mapping above; embedded 25 sample
clauses with the real OpenAI `text-embedding-3-large` API (negligible cost,
well under $0.01); ran 3 hybrid queries. Best result: querying "validate
timers and counters in PLC code" correctly returned `TOP20-SECURE-PLC-CODING-V1`
clause 6 ("Validate timers and counters") as the top hit with a much higher
score than any other candidate — proof the embedding+knn+BM25 hybrid path
genuinely retrieves the right clause, not just structurally executes. A
network-segmentation query returned less precise results, but that is a
sampling artifact of the tiny 25-clause throwaway test index, not a flaw in
the approach — the full 1682-clause corpus was not indexed in this test to
keep it a cheap, quick sanity check rather than a production population run.

Next step to actually go live: start a real Moqui server against this
Docker OpenSearch (`elasticsearch_url` pointing at `http://localhost:9200`),
run `load#NormGraph`, then `index#NormDocuments` for the full corpus.

## Roadmap (Phases 2-7, not yet implemented)

See `/home/igor/.claude/plans/sharded-crafting-stallman.md` and
`design-session/SESSION.md` for the full 7-phase plan: PLM/BOM machine
acquisition, PLC/software graph (fork of `moqui-source-knowledge`), norm↔product
crosswalk, risk scoring & remediation, OpenSearch/embeddings, and MCP
orchestration of the guided workflow.
