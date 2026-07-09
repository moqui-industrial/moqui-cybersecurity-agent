from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from parser import stable_hash, write_json, write_jsonl
from parser.clause_segmenter import segment_by_family
from parser.cross_reference_extractor import extract_cross_references
from parser.text_extractor import TextExtractionError, extract_pdf_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse configured norm PDF sources into vendor-neutral IR JSONL.")
    parser.add_argument("--config", required=True, help="Path to norm-sources.json")
    parser.add_argument("--source-root", required=True, help="Root directory that sourceFile paths in the config are relative to")
    parser.add_argument("--output-dir", required=True, help="Directory where IR JSONL/JSON files will be written")
    return parser.parse_args()


def document_logical_id(document_id: str) -> str:
    return f"norm-document://{document_id}"


def clause_logical_id(document_id: str, clause_number: str) -> str:
    return f"norm-clause://{document_id}/{clause_number}"


def main() -> int:
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()

    documents: list[dict] = []
    clauses: list[dict] = []
    relations: list[dict] = []
    diagnostics: list[dict] = []

    # First pass: known designators, so cross-references between configured
    # documents can be resolved even if document B is processed before the
    # designator of document A that it points back to has been recorded.
    known_designators: dict[str, str] = {}
    for doc_config in config["documents"]:
        if doc_config.get("designator"):
            known_designators[doc_config["designator"]] = doc_config["documentId"]

    clause_id_by_number: dict[tuple[str, str], str] = {}

    for doc_config in config["documents"]:
        document_id = doc_config["documentId"]
        # sourceFile=null is a real, intentional state (not a config error): a document with
        # only manually-transcribed partial clauses (provenanceClass=MANUAL_PARTIAL, see
        # tools/norm-indexer/work/ir-manual/ and the mechanical-safety-crosswalk skill) has no
        # PDF yet - this pipeline has nothing to parse for it until one is added.
        if not doc_config.get("sourceFile"):
            print(f"Skipping {document_id}: sourceFile is null (no PDF yet, manually-transcribed partial coverage only).")
            continue
        source_path = source_root / doc_config["sourceFile"]
        doc_logical_id = document_logical_id(document_id)
        doc_id_hash = stable_hash(doc_logical_id)

        documents.append(
            {
                "id": doc_id_hash,
                "documentId": document_id,
                "logicalId": doc_logical_id,
                "title": doc_config["title"],
                "documentFamily": doc_config["documentFamily"],
                "edition": doc_config.get("edition", "unknown"),
                "sourceFile": doc_config["sourceFile"],
                "designator": doc_config.get("designator"),
            }
        )

        try:
            text = extract_pdf_text(source_path, ocr_source=bool(doc_config.get("ocrSource")))
        except TextExtractionError as error:
            diagnostics.append(
                {
                    "id": stable_hash(f"diagnostic::{document_id}::extract-failed"),
                    "documentId": document_id,
                    "severity": "error",
                    "message": str(error),
                }
            )
            continue

        segmented, seg_diagnostics = segment_by_family(text, doc_config["documentFamily"])
        for message in seg_diagnostics:
            diagnostics.append(
                {
                    "id": stable_hash(f"diagnostic::{document_id}::{message}"),
                    "documentId": document_id,
                    "severity": "warning",
                    "message": message,
                }
            )

        if doc_config.get("ocrSource"):
            diagnostics.append(
                {
                    "id": stable_hash(f"diagnostic::{document_id}::ocr-source"),
                    "documentId": document_id,
                    "severity": "warning",
                    "message": "Source document was OCR-derived; segmentation error rate is expected to be higher and clauses should be spot-checked.",
                }
            )

        for clause in segmented:
            clause_logical = clause_logical_id(document_id, clause.clause_number)
            clause_id = stable_hash(clause_logical)
            clause_id_by_number[(document_id, clause.clause_number)] = clause_id
            provenance = clause.provenance_class
            clauses.append(
                {
                    "id": clause_id,
                    "clauseId": clause_id,
                    "logicalId": clause_logical,
                    "documentId": document_id,
                    "clauseNumber": clause.clause_number,
                    "title": clause.title,
                    "text": clause.text,
                    "startLine": clause.start_line,
                    "endLine": clause.end_line,
                    "parentClauseNumber": clause.parent_clause_number,
                    "provenanceClass": provenance,
                }
            )
            if len(clause.text) < 5:
                diagnostics.append(
                    {
                        "id": stable_hash(f"diagnostic::{document_id}::{clause.clause_number}::empty-body"),
                        "documentId": document_id,
                        "severity": "warning",
                        "message": f"Clause {clause.clause_number} has little or no extracted body text; needs manual review.",
                    }
                )

    # Second pass: structural CONTAINS (document->clause, clause->child clause)
    # and cross-reference relations, now that all clause ids are known.
    for clause in clauses:
        document_id = clause["documentId"]
        doc_logical = document_logical_id(document_id)
        doc_hash = stable_hash(doc_logical)
        parent_number = clause["parentClauseNumber"]
        if parent_number and (document_id, parent_number) in clause_id_by_number:
            relations.append(
                {
                    "id": stable_hash(f"relation::CONTAINS::{clause_id_by_number[(document_id, parent_number)]}::{clause['id']}"),
                    "fromClauseId": clause_id_by_number[(document_id, parent_number)],
                    "fromDocumentId": None,
                    "relationType": "CONTAINS",
                    "toClauseId": clause["id"],
                    "toDocumentId": None,
                    "unresolvedReferenceText": None,
                    "confidence": 1.0,
                    "rationale": "Derived from hierarchical clause numbering.",
                    "provenanceClass": "DERIVED",
                }
            )
        else:
            relations.append(
                {
                    "id": stable_hash(f"relation::CONTAINS::{doc_hash}::{clause['id']}"),
                    "fromClauseId": None,
                    "fromDocumentId": document_id,
                    "relationType": "CONTAINS",
                    "toClauseId": clause["id"],
                    "toDocumentId": None,
                    "unresolvedReferenceText": None,
                    "confidence": 1.0,
                    "rationale": "Top-level clause of the document.",
                    "provenanceClass": "DERIVED",
                }
            )

        self_designator = next((d["designator"] for d in documents if d["documentId"] == document_id), None)
        for reference in extract_cross_references(clause["text"], self_designator, known_designators):
            relations.append(
                {
                    "id": stable_hash(
                        f"relation::{reference.relation_type}::{clause['id']}::{reference.matched_text}"
                    ),
                    "fromClauseId": clause["id"],
                    "fromDocumentId": None,
                    "relationType": reference.relation_type,
                    "toClauseId": None,
                    "toDocumentId": reference.resolved_document_id,
                    "unresolvedReferenceText": None if reference.resolved_document_id else reference.matched_text,
                    "confidence": reference.confidence,
                    "rationale": reference.rationale,
                    "provenanceClass": "INFERRED",
                }
            )

    summary = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "documentCount": len(documents),
        "clauseCount": len(clauses),
        "relationCount": len(relations),
        "diagnosticCount": len(diagnostics),
    }
    project_payload = {
        "projectId": "OtCyberNorms",
        "documentCount": len(documents),
    }

    write_json(output_dir / "project.json", project_payload)
    write_json(output_dir / "summary.json", summary)
    write_jsonl(output_dir / "documents.jsonl", documents)
    write_jsonl(output_dir / "clauses.jsonl", clauses)
    write_jsonl(output_dir / "relations.jsonl", relations)
    write_jsonl(output_dir / "diagnostics.jsonl", diagnostics)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
