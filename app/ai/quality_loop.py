"""품질 루프 — 생성물을 100점 루브릭으로 채점하고 미달이면 자동 보정(루프).

'한 번에 완성'을 버리고 '기준 통과까지 반복'한다. 생성 → 채점 → (미달 시) 약점만
지목해 재작성 → 재채점. 임계점 이상이거나 더 안 오르면 멈춘다. 비용보다 품질 우선.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Tuple

from app.logger import get_logger

_log = get_logger("quality")

# 산출물 유형별 100점 채점 기준 (성과 관점 — 실제 클릭·전환을 낼 수 있는가).
_RUBRICS = {
    "strategy": (
        "1) 미끼 적합도 평가(⭐)가 구체적이고 입력 혜택 전수 평가 (20)"
        " 2) 예산 현실 반영 — 작은 예산이면 단일 캠페인, 억지 분리 없음 (20)"
        " 3) 타겟이 인구통계가 아니라 '장면 속 한 사람'으로 (15)"
        " 4) 핵심 후크가 성과 패턴(의심·숫자갭·결핍)에 부합 (25)"
        " 5) 운영 의사결정 기준이 숫자로 (20)"
    ),
    "content": (
        "1) 후크가 성과 패턴(고객 의심 인용/숫자갭/결핍 직격)을 실제로 사용 (25)"
        " 2) 소식글이 8단 골격(의심인용→공감→숫자등식→철학→반박→체크박스→채팅트리거→매장정보) 완결 (25)"
        " 3) 카피 9종이 실물로 존재(선언만 금지)+글자수+트리거 (20)"
        " 4) 쿠폰 스펙(명/혜택/기간/수량) 실물 (15)"
        " 5) 광고 티 없이 동네 사람 말투 + 단서로 분쟁 예방, 과장·허위 0 (15)"
    ),
    "ad_settings": (
        "1) 예산 현실 — 캠페인당 일1만↑, 작으면 단일(쪼개기 금지) (30)"
        " 2) 변수통제(자동/수동 입찰만 다름) + 캠페인명 규칙 (20)"
        " 3) 소도시 시작가 100원·Day점검 등 실전 수치 (20)"
        " 4) KPI 우선순위(쿠폰당·단골당 최우선) + 0건 정상 해석 (15)"
        " 5) 사장님이 그대로 따라할 수 있는 구체성 (15)"
    ),
    "wizard_proposal": (
        "1) 요약→전략→세팅→KPI→의사결정트리(Case별)→실행체크리스트 완결 (30)"
        " 2) Day별 의사결정(언제 끄고 켜나) 구체 (20)"
        " 3) KPI가 소도시·업종 추적한계 반영 (15)"
        " 4) 앞 단계와 일관 (15)"
        " 5) 광고주가 신뢰할 완성도, 빈말 0 (20)"
    ),
    "report": (
        "1) 시장(소도시) 보정 먼저 (15)"
        " 2) 퍼널 최저 구간을 인과로 (25)"
        " 3) 숫자 정확(입력값 그대로, 산식 일치) + 환각 0 (25)"
        " 4) 정직성(추적한계를 실패로 단정 안 함) (15)"
        " 5) 실행안이 왜+기대효과 근거 (20)"
    ),
}

_SCORE_RE = re.compile(r"점수\s*[:：]?\s*(\d{1,3})")


def _score_prompt(output_type: str, content: str) -> str:
    rubric = _RUBRICS.get(output_type, _RUBRICS["content"])
    return (
        "너는 당근 광고 결과물을 채점하는 가혹한 심사관이다. 아래 [채점 기준](합계 100점)으로 "
        "[결과물]을 채점하라.\n\n"
        f"[채점 기준]\n{rubric}\n\n"
        "출력 형식(이것만):\n"
        "점수: <0~100 정수>\n"
        "약점: <감점 사유를 항목별로 짧게. 무엇을 어떻게 고쳐야 100점인지 구체적으로>\n\n"
        f"[결과물]\n{content}"
    )


def _refine_prompt(weakness: str, content: str, guide_hint: str = "") -> str:
    return (
        "아래 [결과물]을 [지적된 약점]만 고쳐 더 높은 품질로 다시 써라. "
        "구조·형식은 유지하고, 잘 된 부분은 보존하며, 약점만 보강한다. "
        "전체를 다시 완성본으로 출력한다(설명·메타발언 금지).\n\n"
        f"{guide_hint}\n\n[지적된 약점]\n{weakness}\n\n[결과물]\n{content}"
    )


def _parse_score(text: str) -> Tuple[int, str]:
    m = _SCORE_RE.search(text or "")
    score = int(m.group(1)) if m else 0
    score = max(0, min(score, 100))
    wm = re.search(r"약점\s*[:：]?\s*(.+)", text or "", re.DOTALL)
    weakness = wm.group(1).strip() if wm else text.strip()
    return score, weakness


def refine_until_good(
    content: str,
    output_type: str,
    *,
    generate: Callable[[str], str],
    guide: str = "",
    target: int = 90,
    max_iters: int = 2,
    on_progress: Optional[Callable[[str], None]] = None,
) -> str:
    """채점→보정 루프. target 이상이거나 더 안 오르면 멈춘다. 항상 최고 점수본을 반환.

    generate(prompt)->str: 채점·보정에 쓸 단일 LLM 호출 (동기). 호출부에서 엔진 고정해 주입.
    """
    best, best_score = content, -1
    for i in range(max_iters + 1):
        try:
            judged = generate(_score_prompt(output_type, best if i == 0 else content))
        except Exception:
            _log.exception("채점 실패 — 현재본 유지")
            break
        # 채점 대상은 직전 결과(content). i==0이면 content==best==원본.
        target_text = best if i == 0 else content
        score, weakness = _parse_score(judged)
        if on_progress:
            on_progress(f"{output_type} 품질 {score}점")
        if score > best_score:
            best, best_score = target_text, score
        if score >= target or i == max_iters:
            break
        # 보정 1회
        try:
            content = generate(_refine_prompt(weakness, target_text, guide))
        except Exception:
            _log.exception("보정 실패 — 최고본 유지")
            break
    return best
