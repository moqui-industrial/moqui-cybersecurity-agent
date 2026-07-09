import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser.clause_segmenter import (
    segment_en_iec_hierarchical,
    segment_eu_regulation_article,
    segment_line_numbered_draft,
    segment_numbered_list,
)


class NumberedListSegmenterTest(unittest.TestCase):
    def test_sequential_headings_are_split(self):
        text = (
            "1.     Modularize PLC Code\n"
            "     Split PLC code into modules.\n"
            "\n"
            "2.     Track operating modes\n"
            "     Keep the PLC in RUN mode.\n"
        )
        clauses, diagnostics = segment_numbered_list(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(clauses))
        self.assertEqual("1", clauses[0].clause_number)
        self.assertEqual("Modularize PLC Code", clauses[0].title)
        self.assertIn("Split PLC code into modules.", clauses[0].text)
        self.assertEqual("2", clauses[1].clause_number)

    def test_out_of_sequence_number_is_not_a_new_heading(self):
        text = (
            "1.     First Practice\n"
            "     See also item 5. in the appendix for details.\n"
            "2.     Second Practice\n"
            "     Body text.\n"
        )
        clauses, _ = segment_numbered_list(text)
        self.assertEqual(2, len(clauses))
        self.assertIn("item 5. in the appendix", clauses[0].text)

    def test_no_heading_reports_diagnostic(self):
        clauses, diagnostics = segment_numbered_list("just some prose with no numbered headings")
        self.assertEqual([], clauses)
        self.assertEqual(1, len(diagnostics))


class EnIecHierarchicalSegmenterTest(unittest.TestCase):
    def test_toc_lines_are_excluded(self):
        text = (
            "  4.2     ZCR 1: Identify the SUC ........................................ 13\n"
            "  4.2.1     ZCR 1.1: Identify the SUC perimeter .......................... 13\n"
        )
        clauses, diagnostics = segment_en_iec_hierarchical(text)
        self.assertEqual([], clauses)
        self.assertEqual(1, len(diagnostics))

    def test_real_headings_are_captured_with_parent_link(self):
        text = (
            "4.2     ZCR 1: Identify the SUC\n"
            "Body text for the top clause.\n"
            "4.2.1     ZCR 1.1: Identify the SUC perimeter and access points\n"
            "Body text for the sub clause.\n"
            "4.3     ZCR 2: Initial cyber security risk assessment\n"
            "More body text.\n"
        )
        clauses, diagnostics = segment_en_iec_hierarchical(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(3, len(clauses))
        self.assertEqual("4.2", clauses[0].clause_number)
        # "4.2"'s algebraic parent is "4", which is correct even though "4"
        # was never itself segmented as a heading in this fixture; the
        # downstream loader falls back to a document-level CONTAINS edge
        # when the parent clause number does not resolve to a real vertex.
        self.assertEqual("4", clauses[0].parent_clause_number)
        self.assertEqual("4.2.1", clauses[1].clause_number)
        self.assertEqual("4.2", clauses[1].parent_clause_number)
        self.assertIn("Body text for the top clause.", clauses[0].text)

    def test_annex_heading_and_sub_clause_parent_link(self):
        # Real body-heading format confirmed via pdftotext on IEC 62443-4-2/3-3:
        # a bare "Annex A" line, sub-clauses numbered "A.1" underneath.
        text = (
            "Annex A\n"
            "Intro text for the annex.\n"
            "A.1     Device categories\n"
            "Body text for the sub clause.\n"
        )
        clauses, diagnostics = segment_en_iec_hierarchical(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(clauses))
        self.assertEqual("A", clauses[0].clause_number)
        self.assertIn("Intro text for the annex.", clauses[0].text)
        self.assertEqual("A.1", clauses[1].clause_number)
        self.assertEqual("A", clauses[1].parent_clause_number)

    def test_ocr_annex_heading_with_no_space_is_still_captured(self):
        # Real artifact confirmed via pdftotext on both EN 40000-1-2/1-3 (ocrSource=true
        # in norm-sources.json): the OCR drops the space between "Annex" and the
        # designator ("AnnexZA", "AnnexA") that every other (non-OCR) document has.
        text = (
            "AnnexZA\n"
            "Correspondence table body text.\n"
        )
        clauses, diagnostics = segment_en_iec_hierarchical(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(1, len(clauses))
        self.assertEqual("ZA", clauses[0].clause_number)

    def test_word_starting_with_annex_is_not_a_false_positive_heading(self):
        text = (
            "4.2     ZCR 1: Identify the SUC\n"
            "Annexation of legacy subsystems is out of scope for this clause.\n"
            "4.3     ZCR 2: Initial cyber security risk assessment\n"
            "More body text.\n"
        )
        clauses, diagnostics = segment_en_iec_hierarchical(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(clauses))
        self.assertIn("Annexation of legacy subsystems", clauses[0].text)


class EuRegulationArticleSegmenterTest(unittest.TestCase):
    def test_inline_article_reference_is_not_a_heading(self):
        text = (
            "                    Articolo 1\n"
            "Ambito di applicazione.\n"
            "Il presente regolamento si applica fatto salvo l'articolo 24.\n"
            "                    Articolo 2\n"
            "Definizioni.\n"
        )
        clauses, diagnostics = segment_eu_regulation_article(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(clauses))
        self.assertEqual("1", clauses[0].clause_number)
        self.assertIn("articolo 24", clauses[0].text)
        self.assertEqual("2", clauses[1].clause_number)

    def test_annex_heading_is_captured_and_inline_reference_is_not(self):
        # Real body-heading format confirmed via pdftotext on the Machinery Regulation/
        # CRA/NIS2 PDFs: a bare, properly-spaced "ALLEGATO I"/"ANNEX I" line - unlike
        # the OCR'd en-iec-hierarchical documents, none of these 3 has a no-space artifact.
        text = (
            "                    Articolo 24\n"
            "Procedure di valutazione della conformita di cui all'allegato I.\n"
            "                    ALLEGATO I\n"
            "Categorie di macchine elencate di seguito.\n"
            "1. Prima categoria.\n"
        )
        clauses, diagnostics = segment_eu_regulation_article(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(2, len(clauses))
        self.assertEqual("24", clauses[0].clause_number)
        self.assertEqual("Annex I", clauses[1].clause_number)
        self.assertIn("Prima categoria", clauses[1].text)
        # the inline "all'allegato I" reference inside Article 24's own body must not
        # itself be treated as a second, spurious Annex heading
        self.assertIn("all'allegato I", clauses[0].text)


class LineNumberedDraftSegmenterTest(unittest.TestCase):
    def test_dpc_line_prefix_is_stripped_and_real_headings_captured(self):
        # Real format confirmed via pdftotext on BS EN 50742-2025 (a BSI "Draft for
        # Public Comment"): every physical line, including body text, carries its own
        # independent running line-number ('266', '267', '268'...) that has nothing
        # to do with the real clause numbers ('7.2', '7.2.1') that follow it.
        text = (
            "266   7.2     Security measures\n"
            "\n"
            "267   7.2.1    General\n"
            "\n"
            "268   Security measures shall be selected on a risk-based approach.\n"
            "269   This risk-based approach shall consider both safety and security.\n"
            "273   7.2.2    Cryptography\n"
            "\n"
            "274   Only state of the art algorithms should be selected.\n"
        )
        clauses, diagnostics = segment_line_numbered_draft(text)
        self.assertEqual([], diagnostics)
        self.assertEqual(3, len(clauses))
        self.assertEqual("7.2", clauses[0].clause_number)
        self.assertEqual("7.2.1", clauses[1].clause_number)
        self.assertEqual("7.2", clauses[1].parent_clause_number)
        self.assertIn("risk-based approach", clauses[1].text)
        self.assertEqual("7.2.2", clauses[2].clause_number)
        self.assertIn("state of the art", clauses[2].text)

    def test_dpc_toc_dot_leader_lines_are_still_excluded(self):
        text = (
            "10   4.3         General process requirements ....................................8\n"
            "17   7.2.1       General.........................................................................11\n"
        )
        clauses, diagnostics = segment_line_numbered_draft(text)
        self.assertEqual([], clauses)
        self.assertEqual(1, len(diagnostics))


if __name__ == "__main__":
    unittest.main()
