from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: str) -> str:
    """Deterministic id, same technique used by moqui-source-knowledge's PLC graph
    generator: a truncated SHA-256 hex digest, so re-running the pipeline on
    unchanged input produces unchanged vertex/edge ids."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            handle.write("\n")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows
