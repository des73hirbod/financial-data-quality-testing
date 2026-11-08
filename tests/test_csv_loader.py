"""Known-answer tests for Stage 11. Run: python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path

from csv_loader import CSVLoadError, load_csv


HEADER = "security_id,ticker,security_name,security_type,currency,market_value,as_of_date\n"


class LoadCSVTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / "example.csv"

    def test_clean_file_loads_two_rows_without_changing_types(self):
        self.file.write_text(
            HEADER
            + "1,T0001,Security 0001,EQUITY,USD,100.00,2026-09-23\n"
            + "2,T0002,Security 0002,BOND,EUR,200.00,2026-09-23\n",
            encoding="utf-8",
        )
        result = load_csv(self.file)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[0].values["security_id"], "1")
        self.assertEqual(result.records[0].values["market_value"], "100.00")
        self.assertEqual(result.records[1].line_start, 3)

    def test_quoted_comma_stays_inside_one_field(self):
        self.file.write_text(
            HEADER + '1,"T,0001",Security 0001,EQUITY,USD,100.00,2026-09-23\n',
            encoding="utf-8",
        )
        result = load_csv(self.file)
        self.assertEqual(result.records[0].values["ticker"], "T,0001")
        self.assertEqual(len(result.records[0].values), 7)

    def test_wrong_width_fails_and_reports_physical_line(self):
        self.file.write_text(
            HEADER
            + "1,T0001,Security 0001,EQUITY,USD,100.00,2026-09-23\n"
            + "2,T0002,Security 0002,BOND,EUR,200.00\n",
            encoding="utf-8",
        )
        with self.assertRaises(CSVLoadError) as caught:
            load_csv(self.file)
        self.assertIn("line 3", str(caught.exception))
        self.assertIn("expected 7", str(caught.exception))
        self.assertIn("found 6", str(caught.exception))

    def test_invalid_utf8_rejected(self):
        self.file.write_bytes(HEADER.encode("utf-8") + b"1,T0001,\xff,EQUITY,USD,100.00,2026-09-23\n")
        with self.assertRaises(CSVLoadError) as caught:
            load_csv(self.file)
        self.assertIn("UTF-8", str(caught.exception))

    def test_multiline_quoted_field_has_accurate_physical_lines(self):
        self.file.write_text(
            HEADER
            + '1,T0001,"Security\nOne",EQUITY,USD,100.00,2026-09-23\n'
            + "2,T0002,Security 0002,BOND,EUR,200.00,2026-09-23\n",
            encoding="utf-8",
        )
        result = load_csv(self.file)
        self.assertEqual((result.records[0].line_start, result.records[0].line_end), (2, 3))
        self.assertEqual((result.records[1].line_start, result.records[1].line_end), (4, 4))

    def test_blank_row_is_not_silently_skipped(self):
        self.file.write_text(
            HEADER + "1,T0001,Security 0001,EQUITY,USD,100.00,2026-09-23\n\n",
            encoding="utf-8",
        )
        with self.assertRaises(CSVLoadError) as caught:
            load_csv(self.file)
        self.assertIn("line 3", str(caught.exception))

    def test_unclosed_quoted_field_is_rejected(self):
        self.file.write_text(HEADER + '1,T0001,"Unclosed,EQUITY,USD,100.00,2026-09-23\n', encoding="utf-8")
        with self.assertRaises(CSVLoadError) as caught:
            load_csv(self.file)
        self.assertIn("CSV syntax", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
