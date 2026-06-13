"""output_validator 테스트 — 섹션 검증 + 1회 리페어 루프 (AI 호출 mock)."""
from __future__ import annotations

from unittest import TestCase

from app.ai.output_validator import (
    OutputSchema,
    SectionRule,
    build_repair_prompt,
    get_schema,
    repair_output,
    validate_output,
)


def _fake_parse(content: str) -> dict:
    """'## key: body' 라인을 키별로 모으는 단순 파서."""
    out = {"a": "", "b": ""}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("a:"):
            out["a"] = line[2:].strip()
        elif line.startswith("b:"):
            out["b"] = line[2:].strip()
    return out


_SCHEMA = OutputSchema(
    name="테스트 문서",
    parse=_fake_parse,
    rules=(SectionRule("a", "에이", 5), SectionRule("b", "비", 5)),
)


class _FakeProvider:
    def __init__(self, text: str):
        self._text = text

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return self._text


class TestValidateOutput(TestCase):
    def test_no_issues_when_all_sections_full(self):
        content = "a: 충분한 내용입니다\nb: 이것도 충분합니다"
        self.assertEqual(validate_output(content, _SCHEMA), [])

    def test_missing_section_flagged(self):
        content = "a: 충분한 내용입니다"
        issues = validate_output(content, _SCHEMA)
        self.assertEqual(len(issues), 1)
        self.assertIn("비", issues[0])

    def test_too_short_section_flagged(self):
        content = "a: 짧\nb: 충분한 내용입니다"
        issues = validate_output(content, _SCHEMA)
        self.assertEqual(len(issues), 1)
        self.assertIn("너무 짧", issues[0])


class TestBuildRepairPrompt(TestCase):
    def test_includes_original_and_issues(self):
        system, user = build_repair_prompt("a: 원본", ["'비' 섹션이 비어 있거나 누락됐어요."], _SCHEMA)
        self.assertIn("편집자", system)
        self.assertIn("a: 원본", user)
        self.assertIn("비' 섹션", user)
        self.assertIn("테스트 문서", user)


class TestRepairOutput(TestCase):
    def test_returns_original_when_valid(self):
        content = "a: 충분한 내용입니다\nb: 이것도 충분합니다"
        # provider_factory가 호출되면 안 됨 (검증 통과 시 보정 생략).
        def _boom(_engine):
            raise AssertionError("provider should not be called when valid")

        self.assertEqual(repair_output(content, _SCHEMA, provider_factory=_boom), content)

    def test_adopts_repair_when_better(self):
        bad = "a: 충분한 내용입니다"  # b 누락
        fixed = "a: 충분한 내용입니다\nb: 이제 충분합니다"
        result = repair_output(
            bad, _SCHEMA, provider_factory=lambda _e: _FakeProvider(fixed)
        )
        self.assertEqual(result, fixed)

    def test_keeps_original_when_repair_not_better(self):
        bad = "a: 충분한 내용입니다"
        still_bad = "a: 여전히 b가 없네요"  # b 여전히 누락
        result = repair_output(
            bad, _SCHEMA, provider_factory=lambda _e: _FakeProvider(still_bad)
        )
        self.assertEqual(result, bad)

    def test_keeps_original_when_provider_raises(self):
        bad = "a: 충분한 내용입니다"

        def _raise(_engine):
            raise RuntimeError("provider down")

        self.assertEqual(repair_output(bad, _SCHEMA, provider_factory=_raise), bad)

    def test_coordinate_engine_collapses_to_claude(self):
        bad = "a: 충분한 내용입니다"
        captured = {}

        def _factory(engine):
            captured["engine"] = engine
            return _FakeProvider("a: 충분한 내용입니다\nb: 채워졌어요 충분히")

        repair_output(bad, _SCHEMA, engine="coordinate", provider_factory=_factory)
        self.assertEqual(captured["engine"], "claude")


class TestRealSchemas(TestCase):
    def test_known_schema_types_load(self):
        for t in ("strategy", "ad_settings", "wizard_proposal", "analysis"):
            schema = get_schema(t)
            self.assertTrue(schema.rules)
            self.assertTrue(callable(schema.parse))

    def test_unknown_schema_raises(self):
        with self.assertRaises(ValueError):
            get_schema("nope")

    def test_strategy_schema_catches_empty_output(self):
        schema = get_schema("strategy")
        issues = validate_output("완전 무관한 텍스트", schema)
        self.assertEqual(len(issues), len(schema.rules))

    def test_strategy_schema_passes_full_output(self):
        schema = get_schema("strategy")
        content = (
            "## 1. 타겟 분석\n" + "가" * 80 + "\n\n"
            "## 2. 경쟁 환경 분석\n" + "나" * 80 + "\n\n"
            "## 3. 전략 방향\n" + "다" * 80 + "\n\n"
            "## 4. 캠페인 그룹 구성\n" + "라" * 80 + "\n"
        )
        self.assertEqual(validate_output(content, schema), [])
