# -*- coding: utf-8 -*-
"""성과 보고서 — 데모그래픽 업로드 시 세그먼트 요약(슬라이드용) 추출 (Stage C)."""
import io
import unittest

import openpyxl

from app.pages.report import _rows_from_daangn_breakdown


def _demographic_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "breakdown"
    ws.append(["기간", "캠페인 이름", "캠페인 ID", "연령", "비용 (VAT 포함)",
               "노출 수", "클릭 수", "단골 수", "쿠폰 다운로드 수", "채팅 문의 수"])
    for r in [
        ("2026-04-01", "진해_2030여성_누진_수동", "C1", "20-29", 50000, 12000, 160, 8, 12, 2),
        ("2026-04-01", "진해_5060남성_변색_수동", "C3", "50-59", 80000, 15000, 70, 1, 1, 0),
        ("2026-04-02", "진해_2030여성_누진_수동", "C1", "20-29", 52000, 12500, 170, 9, 14, 3),
    ]:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestReportSegments(unittest.TestCase):
    def test_breakdown_yields_segment_rows(self):
        res = _rows_from_daangn_breakdown(_demographic_xlsx())
        self.assertIsNotNone(res)
        _rows, info = res
        segs = info.get("segment_rows")
        self.assertTrue(segs, "세그먼트 요약이 비면 안 됨")
        first = segs[0]
        self.assertIn("label", first)
        self.assertIn("cost", first)
        self.assertIn("cpa", first)
        self.assertIn("verdict", first)
        # 비용 내림차순 정렬(주력 먼저)
        self.assertGreaterEqual(segs[0]["cost"], segs[-1]["cost"])

    def test_non_demographic_returns_none(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["기간", "비용", "노출", "클릭", "문의", "단골", "쿠폰"])
        ws.append(["D1", 1000, 100, 5, 0, 0, 1])
        buf = io.BytesIO()
        wb.save(buf)
        # 7열 단순 템플릿은 timeseries 없음 → None(폴백)
        self.assertIsNone(_rows_from_daangn_breakdown(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
