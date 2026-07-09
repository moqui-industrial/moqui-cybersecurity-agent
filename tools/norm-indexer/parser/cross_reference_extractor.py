from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExtractedReference:
    matched_text: str
    relation_type: str
    confidence: float
    rationale: str
    resolved_document_id: str | None


# Designator patterns for standards/regulations commonly cross-referenced by
# OT cybersecurity norms. Kept intentionally small and explicit for v1 -- this
# is a first-pass regex extraction, not a full citation parser, so every
# match is marked provenanceClass=INFERRED downstream and is meant for human
# review, per the norm graph provenance policy.
_STANDARD_DESIGNATOR_RE = re.compile(
    r"\b(?:CEI\s+)?(?:EN\s+)?(?:IEC\s+)?(?:ISO/IEC\s+|ISO\s+)?"
    # Require 5+ digits for the standard number itself, not 4-5: every real
    # designator configured for this corpus (62443, 40000, 24882, 50742) is
    # 5 digits, while a bare 4-digit match after "IEC"/"ISO" in body text is
    # almost always a bibliography year (e.g. "IEC 2019", "ISO 2025:...")
    # rather than a standard number, and was verified to be the single
    # largest source of unresolved-reference noise before this fix.
    r"(?:EN[\s-]?IEC|IEC|EN|ISO)\s?[\s-]?(\d{5}(?:-\d+)*(?:-\d+)?)",
    re.IGNORECASE,
)
_ARTICLE_REF_RE = re.compile(r"\b[Aa]rticolo\s+(\d+)\b")
_ANNEX_REF_RE = re.compile(r"\b(?:[Aa]llegato|[Aa]nnex)\s+([IVXLC]+)\b")
_HARMONIZE_CUE_RE = re.compile(
    r"\b(in\s+accordance\s+with|conform(?:e|i)\s+a|ai\s+sensi\s+(?:dell|della|del)|as\s+defined\s+in)\b",
    re.IGNORECASE,
)

_CONTEXT_WINDOW = 60


def _context(text: str, start: int, end: int) -> str:
    lo = max(0, start - _CONTEXT_WINDOW)
    hi = min(len(text), end + _CONTEXT_WINDOW)
    return text[lo:hi].replace("\n", " ").strip()


def normalize_designator(raw: str) -> str:
    """Normalize a matched standard designator like 'EN IEC 62443-3-3',
    'CEI EN IEC 62443-3-3', 'EN 40000-1-2', or 'ISO 24882' to a canonical form
    used to resolve against known document ids, e.g. 'IEC-62443-3-3' or
    'EN-40000-1-2'. The governing body prefix is picked in the order
    IEC > EN > ISO (an IEC designator is used even when written as 'EN IEC ...'
    or 'CEI EN IEC ...', since that is how the 62443 series is referenced in
    practice), so this must run before dropping any part of the raw match.
    """
    digits_match = re.search(r"\d{4,5}(?:-\d+)*", raw)
    number = digits_match.group(0) if digits_match else re.sub(r"[^0-9A-Za-z-]", "", raw)
    upper = raw.upper()
    if "IEC" in upper:
        body = "IEC"
    elif "EN" in upper:
        body = "EN"
    elif "ISO" in upper:
        body = "ISO"
    else:
        body = "STD"
    return f"{body}-{number}"


def extract_cross_references(
    clause_text: str,
    self_designator: str | None,
    known_designators: dict[str, str],
) -> list[ExtractedReference]:
    """Find candidate cross-references inside one clause's text.

    known_designators maps a normalized designator (see normalize_designator)
    to the documentId already present in this corpus, so a reference can be
    resolved to a real NormDocument vertex when possible; otherwise the
    reference is still emitted, unresolved, so nothing found by the regex is
    silently dropped.
    """
    references: list[ExtractedReference] = []
    seen: set[tuple[str, str]] = set()

    for match in _STANDARD_DESIGNATOR_RE.finditer(clause_text):
        designator = normalize_designator(match.group(0))
        if self_designator and designator == self_designator:
            continue
        key = (designator, "designator")
        if key in seen:
            continue
        seen.add(key)
        window = _context(clause_text, match.start(), match.end())
        relation_type = "HARMONIZES_WITH" if _HARMONIZE_CUE_RE.search(window) else "REFERENCES"
        references.append(
            ExtractedReference(
                matched_text=match.group(0).strip(),
                relation_type=relation_type,
                confidence=0.6 if designator in known_designators else 0.3,
                rationale=window,
                resolved_document_id=known_designators.get(designator),
            )
        )

    for match in _ARTICLE_REF_RE.finditer(clause_text):
        key = (match.group(0), "article")
        if key in seen:
            continue
        seen.add(key)
        references.append(
            ExtractedReference(
                matched_text=match.group(0),
                relation_type="REFERENCES",
                confidence=0.5,
                rationale=_context(clause_text, match.start(), match.end()),
                resolved_document_id=None,
            )
        )

    for match in _ANNEX_REF_RE.finditer(clause_text):
        key = (match.group(0), "annex")
        if key in seen:
            continue
        seen.add(key)
        references.append(
            ExtractedReference(
                matched_text=match.group(0),
                relation_type="REFERENCES",
                confidence=0.4,
                rationale=_context(clause_text, match.start(), match.end()),
                resolved_document_id=None,
            )
        )

    return references
