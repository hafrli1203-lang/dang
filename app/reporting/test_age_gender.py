"""연령 × 성별 조인 집계(히트맵 데이터) 테스트."""
from __future__ import annotations

import io
from unittest import TestCase

import openpyxl

from app.reporting.demographic import (
    AgeGenderCell,
    aggregate_age_gender_cells,
    parse_demographic_xlsx,
)

# 기간, 캠페인 이름, 연령, 성별, 비용, 노출, 클릭 수, 단골(=행동)
_HEADER = ["기간", "캠페인 이름", "연령", "성별", "비용", "노출", "클릭 수", "단골"]
_ROWS = [
    ("2026-06-01", "유성_비즈_A", "20-24", "남성", 10000, 1000, 50, 5),
    ("2026-06-01", "유성_비즈_A", "20-24", "여성", 20000, 1000, 40, 10),
    ("2026-06-01", "유성_비즈_A", "25-29", "남성", 30000, 2000, 60, 3),
    ("2026-06-02", "유성_비즈_A", "20-24", "남성", 10000, 1000, 50, 5),  # 같은 셀 누적
    ("2026-06-02", "유성_비즈_A", "합계", "전체", 999, 999, 999, 999),    # 스킵
]


class TestAggregateAgeGender(TestCase):
    def test_builds_joint_cells_and_accumulates(self):
        out = aggregate_age_gender_cells(_HEADER, _ROWS)
        cells = {(c.age, c.gender): c for c in out["cells"]}
        self.assertEqual(set(cells), {("20-24", "남성"), ("20-24", "여성"), ("25-29", "남성")})
        # (20-24, 남성)은 두 행이 누적 → 비용 20000, 행동 10
        male_2024 = cells[("20-24", "남성")]
        self.assertEqual(male_2024.cost, 20000)
        self.assertEqual(male_2024.actions, 10)
        self.assertEqual(male_2024.cpa, 2000.0)  # 20000 / 10

    def test_axes_sorted_male_first(self):
        out = aggregate_age_gender_cells(_HEADER, _ROWS)
        self.assertEqual(out["ages"], ["20-24", "25-29"])
        self.assertEqual(out["genders"], ["남성", "여성"])

    def test_ctr_computed(self):
        out = aggregate_age_gender_cells(_HEADER, _ROWS)
        male_2024 = next(c for c in out["cells"] if c.age == "20-24" and c.gender == "남성")
        # 클릭 100 / 노출 2000 * 100 = 5.0
        self.assertAlmostEqual(male_2024.ctr, 5.0)

    def test_skips_totals(self):
        out = aggregate_age_gender_cells(_HEADER, _ROWS)
        self.assertNotIn("합계", out["ages"])
        self.assertNotIn("전체", out["genders"])

    def test_no_gender_column_returns_empty(self):
        header = ["기간", "캠페인 이름", "연령", "비용", "노출", "클릭 수", "단골"]
        rows = [("2026-06-01", "A", "20-24", 10000, 1000, 50, 5)]
        out = aggregate_age_gender_cells(header, rows)
        self.assertEqual(out["cells"], [])
        self.assertEqual(out["ages"], [])
        self.assertEqual(out["genders"], [])


class TestParsePipelineJoint(TestCase):
    def _xlsx(self, header, rows) -> bytes:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "breakdown"
        ws.append(header)
        for r in rows:
            ws.append(list(r))
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_parse_populates_age_gender_cells(self):
        data = self._xlsx(_HEADER, _ROWS)
        parsed = parse_demographic_xlsx(data)
        self.assertIn("age_gender_cells", parsed)
        agc = parsed["age_gender_cells"]
        self.assertTrue(agc["cells"])
        self.assertEqual(agc["genders"], ["남성", "여성"])
        # 기존 키도 보존
        self.assertIn("ages", parsed)
        self.assertIn("campaigns", parsed)

    def test_parse_without_gender_leaves_cells_empty(self):
        header = ["기간", "캠페인 이름", "연령", "비용", "노출", "클릭 수", "단골"]
        rows = [("2026-06-01", "A", "20-24", 10000, 1000, 50, 5)]
        parsed = parse_demographic_xlsx(self._xlsx(header, rows))
        self.assertEqual(parsed["age_gender_cells"]["cells"], [])
        # 연령 집계는 정상 동작
        self.assertTrue(parsed["ages"])
