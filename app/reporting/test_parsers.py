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

    def test_euc_kr_csv_parses(self):
        csv_text = (
            "날짜,광고비,노출,클릭,문의\n"
            "2026-03-01,1500,300,25,3\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("euc-kr"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cost"], 1500)
        self.assertEqual(rows[0]["clicks"], 25)
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

    # ── 당근 실제 CSV 포맷 테스트 ──────────────────────────────────────

    def test_daangn_format_a_with_ad_group(self):
        """Format A: 12컬럼 (광고그룹 포함)."""
        csv_text = (
            "기간,캠페인 이름,캠페인 ID,광고그룹 이름,광고그룹 ID,"
            "비용 (VAT 포함),노출 수,도달 수,클릭 수,클릭률,클릭당 비용(CPC),노출당 비용(CPM)\n"
            "2025.12.01.,테스트 캠페인,12345,광고그룹A,67890,"
            "\"50,000\",\"10,000\",\"8,000\",150,1.50%,\"333\",\"5,000\"\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["date"], "2025-12-01")
        self.assertEqual(row["cost"], 50000)
        self.assertEqual(row["impressions"], 10000)
        self.assertEqual(row["clicks"], 150)
        self.assertEqual(row["reach"], 8000)
        self.assertEqual(row["campaign_name"], "테스트 캠페인")
        # No warnings on required fields
        required_warnings = [w for w in warnings if "missing required" in w]
        self.assertEqual(required_warnings, [])

    def test_daangn_format_b_with_engagement(self):
        """Format B: 18컬럼 (engagement 포함)."""
        csv_text = (
            "기간,캠페인 이름,캠페인 ID,비용 (VAT 포함),노출 수,도달 수,"
            "클릭 수,클릭률,클릭당 비용(CPC),노출당 비용(CPM),"
            "단골 수,후기 수,쿠폰 다운로드 수,관심 수,댓글 수,"
            "전화 문의 수,채팅 문의 수,잠재고객 수집 수\n"
            "2025.12.01.,부천심곡점,99999,\"120,000\",\"25,000\",\"20,000\","
            "380,1.52%,\"315\",\"4,800\","
            "12,3,45,8,2,15,22,5\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["date"], "2025-12-01")
        self.assertEqual(row["cost"], 120000)
        self.assertEqual(row["impressions"], 25000)
        self.assertEqual(row["clicks"], 380)
        self.assertEqual(row["reach"], 20000)
        self.assertEqual(row["regulars"], 12)
        self.assertEqual(row["coupons"], 45)
        self.assertEqual(row["inquiries"], 22)  # 채팅 문의 수
        self.assertEqual(row["campaign_name"], "부천심곡점")
        required_warnings = [w for w in warnings if "missing required" in w]
        self.assertEqual(required_warnings, [])

    def test_daangn_trailing_period_date(self):
        """당근 CSV 날짜 형식 '2025.12.01.' (trailing period) 파싱."""
        csv_text = (
            "기간,비용,노출 수,클릭 수\n"
            "2025.12.01.,1000,200,30\n"
            "2025.12.15.,2000,400,50\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "2025-12-01")
        self.assertEqual(rows[1]["date"], "2025-12-15")

    def test_gigan_header_maps_to_date(self):
        """'기간' 헤더가 date 필드로 정상 매핑."""
        csv_text = (
            "기간,비용,노출,클릭\n"
            "2026-01-01,5000,1000,50\n"
        )
        rows, warnings = parse_daangn_csv(csv_text.encode("utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-01-01")
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()

