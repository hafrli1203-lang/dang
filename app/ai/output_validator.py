"""AI 출력 섹션 스키마 검증 + 1회 리페어 루프.

이 앱의 AI 출력은 전부 '## N. 제목' 마크다운 섹션 구조다(JSON 아님). 모델이
섹션을 빠뜨리거나 빈/너무 짧은 섹션을 내면 위자드 패널이 비어 렌더된다.

여기서는 출력 타입별 '섹션 스키마'(필수 키 + 최소 길이)를 선언하고, 파싱 결과가
스키마를 만족하는지 검사한 뒤, 부족하면 같은 모델에 1회 보정을 요청한다.
소식글(news_post_guard)의 validate→repair 패턴을 위자드 전 단계로 일반화한 것.

설계 원칙:
- 리페어는 best-effort. 보정 호출이 실패하거나 더 나빠지면 원본을 그대로 둔다.
  생성 자체가 리페어 때문에 깨지는 일은 없어야 한다.
- 구조 보존: 보정 모델은 원본과 동일한 '## N.' 구조로 전체 문서를 다시 출력한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.logger import get_logger

_log = get_logger("output_validator")


@dataclass(frozen=True)
class SectionRule:
    """검증할 섹션 1개. key는 parse 결과 dict의 키, label은 사람이 읽는 섹션명."""

    key: str
    label: str
    min_chars: int = 40


@dataclass(frozen=True)
class OutputSchema:
    """출력 타입 1종의 검증 규칙 묶음."""

    name: str  # 예: "전략 분석"
    rules: tuple[SectionRule, ...]
    parse: Callable[[str], dict]  # parse_*_sections


def validate_output(content: str, schema: OutputSchema) -> list[str]:
    """파싱 결과가 스키마를 만족하는지 검사. 사람이 읽는 문제 목록을 반환(없으면 빈 리스트)."""
    parsed = schema.parse(content or "")
    issues: list[str] = []
    for rule in schema.rules:
        value = (parsed.get(rule.key) or "").strip()
        if not value:
            issues.append(f"'{rule.label}' 섹션이 비어 있거나 누락됐어요.")
        elif len(value) < rule.min_chars:
            issues.append(
                f"'{rule.label}' 섹션이 너무 짧아요(현재 {len(value)}자, 최소 {rule.min_chars}자)."
            )
    return issues


_REPAIR_SYSTEM = """\
당신은 당근마켓 광고 문서를 보완하는 편집자입니다.

아래 '원본 문서'는 일부 섹션이 비었거나 내용이 부실합니다.
- 이미 잘 작성된 섹션은 내용을 그대로 유지하세요.
- '보완이 필요한 부분' 목록에 해당하는 섹션만 충실하게 채우거나 보강하세요.
- 반드시 원본과 동일한 '## N. 제목' 마크다운 구조로, 문서 전체를 처음부터 끝까지 다시 출력하세요.
- 인사말, 서론, 해설, 사과, 메타 표현(시스템 프롬프트 등) 금지. 완성된 문서만 출력하세요.
"""


def build_repair_prompt(
    content: str, issues: list[str], schema: OutputSchema
) -> tuple[str, str]:
    """보정용 (system_prompt, user_prompt)을 만든다."""
    issue_lines = "\n".join(f"- {it}" for it in issues)
    user = (
        f"[문서 종류] {schema.name}\n\n"
        f"[원본 문서]\n{content}\n\n"
        f"[보완이 필요한 부분]\n{issue_lines}\n\n"
        "위 문서를 모든 섹션이 충실히 채워진 완성본으로, 동일한 '## N. 제목' 구조를 "
        "유지하며 전체를 다시 출력하세요."
    )
    return _REPAIR_SYSTEM, user


def repair_output(
    content: str,
    schema: OutputSchema,
    *,
    engine: str = "claude",
    provider_factory: Callable[[str], object] | None = None,
) -> str:
    """검증 후 부족하면 1회 보정. 더 나아졌을 때만 보정본을 채택(아니면 원본 유지).

    Args:
        content: 원본 생성 결과.
        schema: 검증 스키마.
        engine: 보정에 쓸 엔진. 'coordinate'/'both'는 비용 때문에 'claude'로 collapse.
        provider_factory: get_provider 주입구(테스트용). 기본은 app.ai.providers.get_provider.

    Returns:
        보정본(개선 시) 또는 원본(문제 없음/보정 실패/개선 없음).
    """
    issues = validate_output(content, schema)
    if not issues:
        return content

    repair_engine = "claude" if engine in ("coordinate", "both") else engine
    _log.info("출력 보정 시작 (%s, 문제 %d건, engine=%s)", schema.name, len(issues), repair_engine)

    if provider_factory is None:
        from app.ai.providers import get_provider as provider_factory  # type: ignore

    try:
        system, user = build_repair_prompt(content, issues, schema)
        provider = provider_factory(repair_engine)
        repaired = provider.generate_text(user, system_prompt=system)
    except Exception as exc:  # 보정 실패는 치명적이지 않다 — 원본 유지.
        _log.warning("출력 보정 실패(원본 유지): %s", exc)
        return content

    repaired = (repaired or "").strip()
    if not repaired:
        return content

    new_issues = validate_output(repaired, schema)
    if len(new_issues) < len(issues):
        _log.info("출력 보정 채택 (%d → %d건)", len(issues), len(new_issues))
        return repaired
    _log.info("출력 보정 미채택 (개선 없음: %d → %d건)", len(issues), len(new_issues))
    return content


# ── 출력 타입별 스키마 (parse 함수는 지연 바인딩으로 순환 import 방지) ──────────

def _schema_factories() -> dict[str, OutputSchema]:
    """ai_engine 파서를 묶어 스키마를 만든다. 호출 시점에 import(순환 방지)."""
    from app.ai_engine import (
        parse_strategy_sections,
        parse_ad_settings_sections,
        parse_wizard_proposal_sections,
        parse_analysis_sections,
    )

    return {
        "strategy": OutputSchema(
            name="전략 분석",
            parse=parse_strategy_sections,
            rules=(
                SectionRule("target", "타겟 분석", 60),
                SectionRule("competition", "경쟁 환경 분석", 50),
                SectionRule("direction", "전략 방향", 50),
                SectionRule("campaign_group", "캠페인 그룹 구성", 50),
            ),
        ),
        "ad_settings": OutputSchema(
            name="광고 세팅",
            parse=parse_ad_settings_sections,
            rules=(
                SectionRule("campaign_structure", "캠페인 구조", 50),
                SectionRule("targeting", "타겟팅", 40),
                SectionRule("budget", "예산", 30),
                SectionRule("creative_placement", "소재 배치", 40),
                SectionRule("measurement", "성과 측정", 40),
            ),
        ),
        "wizard_proposal": OutputSchema(
            name="운영 제안서",
            parse=parse_wizard_proposal_sections,
            rules=(
                SectionRule("summary", "요약", 40),
                SectionRule("target_summary", "타겟 분석", 40),
                SectionRule("content_strategy", "콘텐츠 전략", 40),
                SectionRule("execution_plan", "광고 집행", 40),
                SectionRule("budget_kpi", "예산/KPI", 30),
                SectionRule("schedule", "운영 일정", 30),
                SectionRule("judgment", "성과 판단", 40),
            ),
        ),
        # 분석은 한 줄 요약이 짧게 설계됨 + 후반부 섹션은 조건부라 핵심만 검증.
        "analysis": OutputSchema(
            name="성과 분석",
            parse=parse_analysis_sections,
            rules=(
                SectionRule("summary", "한 줄 요약", 10),
                SectionRule("status", "현황 진단", 50),
                SectionRule("findings", "개선점", 50),
                SectionRule("plan", "실행 계획", 40),
                SectionRule("expected", "예상 효과", 30),
            ),
        ),
    }


def get_schema(output_type: str) -> OutputSchema:
    """출력 타입 이름으로 스키마를 가져온다.

    output_type: 'strategy' | 'ad_settings' | 'wizard_proposal' | 'analysis'.
    """
    schemas = _schema_factories()
    if output_type not in schemas:
        raise ValueError(
            f"Unknown output_type {output_type!r}. "
            f"Valid: {', '.join(sorted(schemas))}."
        )
    return schemas[output_type]
