"""Claude + GPT 의견 조율 (병렬→종합).

사용자가 '조율' 엔진을 선택하면 Claude와 GPT가 각자 초안을 만들고(병렬은 호출
페이지가 asyncio로 처리), 종합 모델이 두 초안을 비교해 하나로 병합한다.

설계 의도:
- 두 모델의 독립 관점을 확보한 뒤, 모순은 데이터 우선으로 해소하고 누락을 보완.
- 종합 결과는 '초안 합본'이 아니라 더 정확하고 구체적인 단일 결과물이어야 한다.

이 모듈은 순수 프롬프트 빌더(build_synthesis_prompt)와 1회 종합 호출(synthesize)만
제공한다. 초안 2개의 병렬 실행과 진행 표시는 호출 페이지의 책임이다.
"""
from __future__ import annotations

import os

from app.ai.providers import get_provider
from app.logger import get_logger

_log = get_logger("coordination")

SYNTHESIS_SYSTEM = """\
당신은 두 명의 전문가가 작성한 초안을 하나로 통합하는 수석 편집자입니다.
서로 다른 두 초안(A, B)을 받아, 더 정확하고 실행 가능한 단일 결과물로 병합합니다.

원칙:
- 두 초안의 좋은 점을 모두 살리되, 단순히 이어 붙이지 않는다. 하나의 일관된 글로 다시 쓴다.
- 두 초안이 충돌하면 구체적 수치·근거가 있는 쪽을 택한다. 근거 없는 단정은 버린다.
- 한쪽에만 있는 유용한 정보는 빠짐없이 반영한다.
- 원본 초안이 요구한 출력 구조(섹션 제목, 표, 개수 등)를 그대로 유지한다.
- 메타 설명("두 초안을 합쳤습니다" 같은 말) 없이 최종 결과물만 출력한다.
"""

_SYNTHESIS_USER = """\
[작업] {task_label}

아래는 같은 작업에 대한 두 전문가의 초안입니다. 위 원칙에 따라 하나로 통합해 주세요.

━━━━━━━━ 초안 A ━━━━━━━━
{draft_a}

━━━━━━━━ 초안 B ━━━━━━━━
{draft_b}

━━━━━━━━━━━━━━━━━━━━━
위 두 초안을 통합한 최종 결과물만 출력하세요.
"""


def build_synthesis_prompt(task_label: str, draft_a: str, draft_b: str) -> tuple[str, str]:
    """두 초안을 병합하는 (system_prompt, user_prompt)를 만든다 (순수 함수)."""
    user = _SYNTHESIS_USER.format(
        task_label=task_label or "결과물 통합",
        draft_a=(draft_a or "(초안 없음)").strip(),
        draft_b=(draft_b or "(초안 없음)").strip(),
    )
    return SYNTHESIS_SYSTEM, user


def synthesize(
    draft_a: str,
    draft_b: str,
    task_label: str,
    *,
    engine: str | None = None,
) -> str:
    """두 초안을 1회 종합 호출로 병합한다 (블로킹).

    engine 미지정 시 OPENAI_SYNTHESIS_ENGINE env, 없으면 'claude'(주력)로 종합.
    한쪽 초안이 비어 있으면 종합 없이 나머지를 그대로 반환(부분 실패 흡수).
    """
    a, b = (draft_a or "").strip(), (draft_b or "").strip()
    if not a and not b:
        raise ValueError("종합할 초안이 없습니다.")
    if not a:
        return b
    if not b:
        return a

    syn_engine = engine or os.getenv("OPENAI_SYNTHESIS_ENGINE", "claude")
    system, user = build_synthesis_prompt(task_label, a, b)
    _log.info("조율 종합 시작 (engine=%s, label=%s)", syn_engine, task_label)
    provider = get_provider(syn_engine)
    result = provider.generate_text(user, system_prompt=system)
    _log.info("조율 종합 완료 (%d자)", len(result))
    return result


async def coordinate_generate(
    loop,
    prompt: str,
    system_prompt: str,
    task_label: str,
    *,
    on_drafts=None,
    on_synth=None,
) -> str:
    """병렬 초안(Claude+GPT) → 종합을 한 번에 수행하는 비동기 헬퍼.

    두 모델에 동일한 prompt/system_prompt를 주어 각자 초안을 만들고(병렬),
    종합 모델이 하나로 병합한다. 위자드 각 스텝/보고서에서 재사용.

    on_drafts/on_synth: 진행 표시용 콜백(선택).
    """
    import asyncio

    from app.ai.providers import OpenAIProvider

    if on_drafts:
        on_drafts()
    claude_p = get_provider("claude")
    gpt_p = OpenAIProvider()
    c_text, g_text = await asyncio.gather(
        loop.run_in_executor(None, lambda: claude_p.generate_text(prompt, system_prompt=system_prompt)),
        loop.run_in_executor(None, lambda: gpt_p.generate_text(prompt, system_prompt=system_prompt)),
    )
    if on_synth:
        on_synth()
    return await loop.run_in_executor(None, lambda: synthesize(c_text, g_text, task_label))
