"""온보딩 체크리스트 — 첫 사용자가 핵심 흐름을 끝까지 밟도록 안내.

완료 여부는 실제 DB 상태(프로젝트 존재, 단계별 생성물 존재)에서 도출한다.
순수 로직만 두고(테스트 가능), 렌더는 project.py가 담당한다.
"""
from __future__ import annotations

from dataclasses import dataclass

# (key, 라벨, 설명, 이동 경로, flags 키)
_STEP_DEFS: tuple[tuple[str, str, str, str, str], ...] = (
    ("project", "프로젝트 만들기", "광고할 가게 정보를 등록해요", "/", "has_project"),
    ("strategy", "전략 분석", "타겟·경쟁·전략 방향을 AI가 잡아줘요", "/plan/strategy", "has_strategy"),
    ("planning", "기획 콘텐츠 생성", "소식글·카피·썸네일 가이드를 만들어요", "/plan/content", "has_planning"),
    ("ad_settings", "광고 세팅", "캠페인 구조·타겟팅·예산을 설계해요", "/plan/adset", "has_ad_settings"),
    ("proposal", "운영 제안서", "광고주에게 줄 종합 제안서를 뽑아요", "/plan/proposal", "has_proposal"),
    ("report", "성과 분석", "집행 결과를 올려 퍼널·CPA를 분석해요", "/report", "has_report"),
)


@dataclass(frozen=True)
class OnboardingStep:
    key: str
    label: str
    desc: str
    route: str
    done: bool


def compute_onboarding_steps(flags: dict) -> list[OnboardingStep]:
    """완료 플래그 dict로 단계 목록을 만든다.

    flags 키: has_project / has_strategy / has_planning / has_ad_settings /
    has_proposal / has_report (없으면 미완료로 본다).
    """
    return [
        OnboardingStep(key, label, desc, route, bool(flags.get(flag)))
        for key, label, desc, route, flag in _STEP_DEFS
    ]


def onboarding_progress(steps: list[OnboardingStep]) -> tuple[int, int]:
    """(완료 수, 전체 수)."""
    return sum(1 for s in steps if s.done), len(steps)


def is_onboarding_complete(steps: list[OnboardingStep]) -> bool:
    return all(s.done for s in steps)
