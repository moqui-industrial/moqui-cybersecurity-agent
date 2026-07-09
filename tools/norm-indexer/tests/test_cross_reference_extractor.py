import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser.cross_reference_extractor import extract_cross_references, normalize_designator


class NormalizeDesignatorTest(unittest.TestCase):
    def test_variants_normalize_to_the_same_id(self):
        self.assertEqual("IEC-62443-3-3", normalize_designator("EN IEC 62443-3-3"))
        self.assertEqual("IEC-62443-3-3", normalize_designator("CEI EN IEC 62443-3-3"))
        self.assertEqual("IEC-62443-3-3", normalize_designator("IEC 62443-3-3"))

    def test_en_only_designator_is_not_forced_to_iec(self):
        # Regression: an earlier version hardcoded the "IEC-" prefix for every
        # designator, which silently broke resolution of EN-only references
        # such as EN 40000-1-2 / EN 50742 (no "IEC" in the source text).
        self.assertEqual("EN-40000-1-2", normalize_designator("EN 40000-1-2"))
        self.assertEqual("ISO-24882", normalize_designator("ISO 24882"))


class ExtractCrossReferencesTest(unittest.TestCase):
    def test_resolved_reference_to_known_document(self):
        known = {"IEC-62443-3-3": "IEC-62443-3-3"}
        refs = extract_cross_references("in accordance with EN IEC 62443-3-3 for system security levels", None, known)
        self.assertEqual(1, len(refs))
        self.assertEqual("IEC-62443-3-3", refs[0].resolved_document_id)
        self.assertEqual("HARMONIZES_WITH", refs[0].relation_type)
        self.assertGreater(refs[0].confidence, 0.5)

    def test_unresolved_reference_is_still_emitted(self):
        refs = extract_cross_references("as required by IEC 62443-4-2", None, {})
        self.assertEqual(1, len(refs))
        self.assertIsNone(refs[0].resolved_document_id)
        self.assertEqual("REFERENCES", refs[0].relation_type)

    def test_self_reference_is_skipped(self):
        refs = extract_cross_references("this clause of IEC 62443-3-3 defines...", "IEC-62443-3-3", {})
        self.assertEqual(0, len(refs))

    def test_article_and_annex_references(self):
        refs = extract_cross_references("conformemente all'articolo 24 e all'allegato I", None, {})
        relation_types = {r.matched_text for r in refs}
        self.assertIn("articolo 24", relation_types)
        self.assertTrue(any("allegato" in text.lower() for text in relation_types))


if __name__ == "__main__":
    unittest.main()
