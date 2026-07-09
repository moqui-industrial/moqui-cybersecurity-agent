from __future__ import annotations

import argparse
import json
from pathlib import Path

from parser import stable_hash, write_json, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Graph/GraphVertex/GraphEdge exports from validated norm IR.")
    parser.add_argument("--ir-dir", required=True, help="Directory containing IR JSON and JSONL files.")
    parser.add_argument("--output-dir", required=True, help="Directory where graph exports will be written.")
    parser.add_argument("--graph-id", required=True, help="Graph id to assign to the generated graph.")
    parser.add_argument("--graph-name", default="OT Cybersecurity Normative Graph", help="Graph label.")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    payloads: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payloads.append(json.loads(line))
    return payloads


def graph_vertex_id(logical_id: str) -> str:
    return stable_hash(f"graph-vertex::{logical_id}")


def graph_edge_id(graph_id: str, relation_type: str, from_vertex_id: str, to_vertex_id: str) -> str:
    return stable_hash(f"graph-edge::{graph_id}::{relation_type}::{from_vertex_id}::{to_vertex_id}")


def add_vertex(vertices, metadata, seen, graph_id, logical_id, label, vertex_type, attributes) -> str:
    vertex_id = graph_vertex_id(logical_id)
    if vertex_id in seen:
        return vertex_id
    seen.add(vertex_id)
    vertices.append({"graphVertexId": vertex_id, "graphId": graph_id, "label": label[:255], "notBelongToEdge": "N"})
    metadata.append(
        {
            "graphId": graph_id,
            "graphVertexId": vertex_id,
            "logicalId": logical_id,
            "vertexType": vertex_type,
            "attributes": attributes,
        }
    )
    return vertex_id


def add_edge(edges, metadata, seen, graph_id, relation_type, from_vertex_id, to_vertex_id, attributes=None) -> str | None:
    if not from_vertex_id or not to_vertex_id:
        return None
    edge_id = graph_edge_id(graph_id, relation_type, from_vertex_id, to_vertex_id)
    if edge_id in seen:
        return edge_id
    seen.add(edge_id)
    edges.append(
        {
            "graphEdgeId": edge_id,
            "graphId": graph_id,
            "edgeTypeEnumId": "GetDirected",
            "fromVertexId": from_vertex_id,
            "toVertexId": to_vertex_id,
            "isDirected": "Y",
            "isLoop": "Y" if from_vertex_id == to_vertex_id else "N",
            "label": relation_type[:255],
        }
    )
    metadata.append({"graphId": graph_id, "graphEdgeId": edge_id, "relationType": relation_type, "attributes": attributes or {}})
    return edge_id


def main() -> int:
    args = parse_args()
    ir_dir = Path(args.ir_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    graph_id = args.graph_id

    documents = load_jsonl(ir_dir / "documents.jsonl")
    clauses = load_jsonl(ir_dir / "clauses.jsonl")
    relations = load_jsonl(ir_dir / "relations.jsonl")

    vertices: list[dict] = []
    edges: list[dict] = []
    vertex_metadata: list[dict] = []
    edge_metadata: list[dict] = []
    vertex_evidence: list[dict] = []
    edge_evidence: list[dict] = []
    seen_vertices: set[str] = set()
    seen_edges: set[str] = set()

    document_vertex_id_by_document_id: dict[str, str] = {}
    for document in documents:
        vertex_id = add_vertex(
            vertices,
            vertex_metadata,
            seen_vertices,
            graph_id,
            document["logicalId"],
            document["title"],
            "NormDocument",
            {
                "vertexType": "NormDocument",
                "logicalId": document["logicalId"],
                "documentId": document["documentId"],
                "documentFamily": document["documentFamily"],
                "documentTitle": document["title"],
                "edition": document.get("edition") or "unknown",
                "sourceFile": document["sourceFile"],
                "provenanceClass": "EXTRACTED",
            },
        )
        document_vertex_id_by_document_id[document["documentId"]] = vertex_id
        vertex_evidence.append(
            {
                "graphId": graph_id,
                "graphVertexId": vertex_id,
                "logicalId": document["logicalId"],
                "sourceFile": document["sourceFile"],
                "evidenceType": "DocumentSource",
            }
        )

    clause_vertex_id_by_clause_id: dict[str, str] = {}
    clause_by_id = {clause["id"]: clause for clause in clauses}
    for clause in clauses:
        vertex_id = add_vertex(
            vertices,
            vertex_metadata,
            seen_vertices,
            graph_id,
            clause["logicalId"],
            clause.get("title") or clause["clauseNumber"],
            "NormClause",
            {
                "vertexType": "NormClause",
                "logicalId": clause["logicalId"],
                "documentId": clause["documentId"],
                "clauseNumber": clause["clauseNumber"],
                "clauseTitle": clause.get("title") or "",
                "clauseText": (clause.get("text") or "")[:4000],
                "sourceFile": next((d["sourceFile"] for d in documents if d["documentId"] == clause["documentId"]), ""),
                "provenanceClass": clause["provenanceClass"],
            },
        )
        clause_vertex_id_by_clause_id[clause["id"]] = vertex_id
        vertex_evidence.append(
            {
                "graphId": graph_id,
                "graphVertexId": vertex_id,
                "logicalId": clause["logicalId"],
                "sourceFile": next((d["sourceFile"] for d in documents if d["documentId"] == clause["documentId"]), ""),
                "startLine": clause.get("startLine"),
                "endLine": clause.get("endLine"),
                "evidenceType": "ClauseOccurrence",
            }
        )

    unresolved_vertex_id_by_text: dict[str, str] = {}

    def unresolved_vertex(text: str) -> str:
        if text in unresolved_vertex_id_by_text:
            return unresolved_vertex_id_by_text[text]
        logical_id = f"norm-external-reference://{text}"
        vertex_id = add_vertex(
            vertices,
            vertex_metadata,
            seen_vertices,
            graph_id,
            logical_id,
            text,
            "NormDocument",
            {
                "vertexType": "NormDocument",
                "logicalId": logical_id,
                "documentFamily": "external-unresolved",
                "documentTitle": text,
                "provenanceClass": "INFERRED",
            },
        )
        unresolved_vertex_id_by_text[text] = vertex_id
        return vertex_id

    for relation in relations:
        relation_type = relation["relationType"]
        if relation.get("fromClauseId"):
            from_vertex_id = clause_vertex_id_by_clause_id.get(relation["fromClauseId"])
        else:
            from_vertex_id = document_vertex_id_by_document_id.get(relation.get("fromDocumentId"))

        if relation.get("toClauseId"):
            to_vertex_id = clause_vertex_id_by_clause_id.get(relation["toClauseId"])
        elif relation.get("toDocumentId"):
            to_vertex_id = document_vertex_id_by_document_id.get(relation["toDocumentId"])
        elif relation.get("unresolvedReferenceText"):
            to_vertex_id = unresolved_vertex(relation["unresolvedReferenceText"])
        else:
            to_vertex_id = None

        edge_id = add_edge(
            edges,
            edge_metadata,
            seen_edges,
            graph_id,
            relation_type,
            from_vertex_id,
            to_vertex_id,
            {
                "provenanceClass": relation.get("provenanceClass"),
                "confidence": relation.get("confidence"),
                "rationale": relation.get("rationale"),
            },
        )
        if edge_id:
            edge_evidence.append(
                {
                    "graphId": graph_id,
                    "graphEdgeId": edge_id,
                    "relationType": relation_type,
                    "rationale": relation.get("rationale"),
                }
            )

    graph_payload = {
        "graphId": graph_id,
        "graphTypeEnumId": "GtDirected",
        "graphOrder": len(vertices),
        "size": len(edges),
        "loopsAllowed": "N",
        "isWeighted": "N",
        "name": args.graph_name,
        "description": "OT cybersecurity normative graph generated from norm PDF sources.",
    }
    graph_summary = {
        "graphId": graph_id,
        "emittedVertexCount": len(vertices),
        "emittedEdgeCount": len(edges),
        "documentVertexCount": len(document_vertex_id_by_document_id),
        "clauseVertexCount": len(clause_vertex_id_by_clause_id),
        "unresolvedExternalVertexCount": len(unresolved_vertex_id_by_text),
        "vertexEvidenceCount": len(vertex_evidence),
        "edgeEvidenceCount": len(edge_evidence),
    }

    write_json(output_dir / "graph.json", graph_payload)
    write_json(output_dir / "summary.json", graph_summary)
    write_jsonl(output_dir / "vertices.jsonl", vertices)
    write_jsonl(output_dir / "edges.jsonl", edges)
    write_jsonl(output_dir / "vertex-metadata.jsonl", vertex_metadata)
    write_jsonl(output_dir / "edge-metadata.jsonl", edge_metadata)
    write_jsonl(output_dir / "vertex-evidence.jsonl", vertex_evidence)
    write_jsonl(output_dir / "edge-evidence.jsonl", edge_evidence)

    print(json.dumps(graph_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
