"""Unit tests for app.reporting.parsers.

Run:
    python -m unittest app.reporting.test_parsers -v
"""

import unittest

from app.reporting.parsers import parse_daangn_csv


class TestParseDaangnCsv(unittest.TestCase):
    def test_utf8_bom_csv_parses(self):
        csv_text = (
            "날짜,광고비,노출,클릭,문의,단골,쿠폰\n"
            "2026-03-01,1000,200,30,4,1,2\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-03-01")
        self.assertEqual(rows[0]["cost"], 1000)
        self.assertEqual(rows[0]["impressions"], 200)
        self.assertEqual(rows[0]["clicks"], 30)
        self.assertEqual(rows[0]["inquiries"], 4)
        self.assertEqual(rows[0]["regulars"], 1)
        self.assertEqual(rows[0]["coupons"], 2)
        self.assertEqual(warnings, [])

    def test_cp949_csv_parses(self):
        csv_text = (
            "일자,비용,노출수,클릭수,채팅,팔로워,쿠폰사용\n"
            "2026/03/01,1200,340,22,5,2,1\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("cp949"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-03-01")
        self.assertEqual(rows[0]["cost"], 1200)
        self.assertEqual(rows[0]["impressions"], 340)
        self.assertEqual(rows[0]["clicks"], 22)
        self.assertEqual(rows[0]["inquiries"], 5)
        self.assertEqual(rows[0]["regulars"], 2)
        self.assertEqual(rows[0]["coupons"], 1)
        self.assertEqual(warnings, [])

    def test_numeric_with_comma_won_space(self):
        csv_text = (
            "날짜,광고비,노출수,클릭수,문의\n"
            "2026-03-01,\"1,200원\",\" 3,400 \",\" 20 회 \",\"  5건\"\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cost"], 1200)
        self.assertEqual(rows[0]["impressions"], 3400)
        self.assertEqual(rows[0]["clicks"], 20)
        self.assertEqual(rows[0]["inquiries"], 5)
        self.assertEqual(warnings, [])

    def test_header_variation_mapping(self):
        csv_text = (
            "date,집행금액(원),총노출수,클릭수,대화,단골수,쿠폰수\n"
            "2026.03.01,2100,999,12,3,4,5\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["date"], "2026-03-01")
        self.assertEqual(row["cost"], 2100)
        self.assertEqual(row["impressions"], 999)
        self.assertEqual(row["clicks"], 12)
        self.assertEqual(row["inquiries"], 3)
        self.assertEqual(row["regulars"], 4)
        self.assertEqual(row["coupons"], 5)
        self.assertEqual(warnings, [])

    def test_skip_invalid_rows_and_return_warnings(self):
        csv_text = (
            "날짜,광고비,노출,클릭\n"
            "\n"
            "2026-03-01,1000,100,10\n"
            "잘못된날짜,1000,100,10\n"
            "2026-03-03,abc,100,10\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-03-01")
        self.assertTrue(any("empty row" in warning for warning in warnings))
        self.assertTrue(any("skipped" in warning for warning in warnings))
        self.assertTrue(any("skipped rows: 3" in warning for warning in warnings))

    def test_flexible_date_formats(self):
        csv_text = (
            "날짜,광고비,노출,클릭\n"
            "2026/03/01,100,200,10\n"
            "2026.03.02,100,200,10\n"
            "2026년 3월 3일,100,200,10\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual([row["date"] for row in rows], ["2026-03-01", "2026-03-02", "2026-03-03"])
        self.assertEqual(warnings, [])

    def test_empty_bytes_returns_empty(self):
        rows, warnings = parse_daangn_csv(b"")
        self.assertEqual(rows, [])
        self.assertEqual(warnings, [])

    def test_missing_optional_columns_default_to_zero(self):
        csv_text = (
            "날짜,광고비,노출,클릭\n"
            "2026-03-01,1000,200,30\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["inquiries"], 0)
        self.assertEqual(row["regulars"], 0)
        self.assertEqual(row["coupons"], 0)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()

