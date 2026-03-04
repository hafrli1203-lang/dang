# -*- coding: utf-8 -*-
"""소식글 강제 출력 — Type B(긴급성) / Type C(가성비) 검증 + repair 프롬프트."""

from __future__ import annotations

import re
from typing import Dict, List

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  상수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIN_BODY_LENGTH = 900

SECTION_TYPES: Dict[str, str] = {
    "type_c": "Type C(가성비)",
    "type_b": "Type B(긴급성)",
}

REQUIRED_SUBSECTIONS = ["제목", "본문", "CTA", "FAQ", "고지"]

CTA_KEYWORDS = ["채팅", "문의", "쿠폰", "단골", "예약"]

FORBIDDEN_WORDS = ["무조건", "전부", "절대 추가금 없음", "100%"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  정규식
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SECTION_HEADER_RE = {
    key: re.compile(rf"\[소식글\s*{re.escape(label)}\]", re.IGNORECASE)
    for key, label in SECTION_TYPES.items()
}

_SUBSECTION_RE = {
    sub: re.compile(rf"(?:^|\n)\s*{re.escape(sub)}\s*[:：]", re.MULTILINE)
    for sub in REQUIRED_SUBSECTIONS
}

_FAQ_QA_RE = re.compile(r"Q\d+\s*[.．:：]\s*.+\n\s*A\d+\s*[.．:：]\s*.+", re.MULTILINE)

_NOTICE_RE = re.compile(r"※|고지")

_SECTION_SPLIT_RE = re.compile(
    r"(\[소식글\s*Type\s*[A-Z]\([^)]+\)\])", re.IGNORECASE
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  내부 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _split_sections(text: str) -> Dict[str, str]:
    """텍스트를 [소식글 Type X(...)] 헤더 기준으로 분리."""
    parts = _SECTION_SPLIT_RE.split(text)
    sections: Dict[str, str] = {}
    for i, part in enumerate(parts):
        for key, rx in _SECTION_HEADER_RE.items():
            if rx.search(part):
                body = parts[i + 1] if i + 1 < len(parts) else ""
                sections[key] = body
    return sections


def _extract_subsection_text(block: str, subsection: str) -> str:
    """블록에서 특정 하위 섹션의 텍스트를 추출."""
    pattern = re.compile(
        rf"(?:^|\n)\s*{re.escape(subsection)}\s*[:：]\s*(.*?)(?=\n\s*(?:{'|'.join(re.escape(s) for s in REQUIRED_SUBSECTIONS)})\s*[:：]|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(block)
    return match.group(1).strip() if match else ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  검증
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_news_post(text: str) -> List[str]:
    """소식글 출력 검증. 빈 리스트 반환 시 통과."""
    errors: List[str] = []
    raw = text or ""

    # ── 섹션 헤더 존재 ──
    for key, rx in _SECTION_HEADER_RE.items():
        if not rx.search(raw):
            label = SECTION_TYPES[key]
            errors.append(f"섹션 헤더 누락: [소식글 {label}]")

    sections = _split_sections(raw)

    for key, label in SECTION_TYPES.items():
        block = sections.get(key, "")
        prefix = f"[{label}]"

        if not block:
            if not any(label in e for e in errors):
                errors.append(f"{prefix} 블록 본문 없음")
            continue

        # ── 하위 섹션 존재 ──
        for sub in REQUIRED_SUBSECTIONS:
            if not _SUBSECTION_RE[sub].search(block):
                errors.append(f"{prefix} '{sub}:' 하위 섹션 누락")

        # ── 본문 길이 ──
        body_text = _extract_subsection_text(block, "본문")
        body_len = len(body_text.replace(" ", "").replace("\n", ""))
        if body_len < MIN_BODY_LENGTH:
            errors.append(
                f"{prefix} 본문 너무 짧음 (최소 {MIN_BODY_LENGTH}자 필요, 현재 {body_len}자)"
            )

        # ── CTA 키워드 ──
        cta_text = _extract_subsection_text(block, "CTA")
        if cta_text and not any(kw in cta_text for kw in CTA_KEYWORDS):
            errors.append(
                f"{prefix} CTA에 핵심 키워드 누락 (필요: {'/'.join(CTA_KEYWORDS)} 중 1개)"
            )

        # ── FAQ 최소 3쌍 ──
        faq_text = _extract_subsection_text(block, "FAQ")
        qa_pairs = _FAQ_QA_RE.findall(faq_text) if faq_text else []
        if len(qa_pairs) < 3:
            errors.append(
                f"{prefix} FAQ 부족 (최소 3쌍 필요, 현재 {len(qa_pairs)}쌍)"
            )

        # ── 고지 ──
        notice_text = _extract_subsection_text(block, "고지")
        if notice_text and not _NOTICE_RE.search(notice_text):
            errors.append(f"{prefix} 고지에 '※' 또는 '고지' 문구 누락")

    # ── 금지어 ──
    for word in FORBIDDEN_WORDS:
        if word in raw:
            errors.append(f"금지어 감지: \"{word}\"")

    return errors


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  repair 프롬프트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_REPAIR_TEMPLATE = """\
[REPAIR INSTRUCTION]
당신의 이전 출력이 아래 조건을 만족하지 못했습니다.
처음부터 전체를 재작성하여, 아래 [출력 포맷]을 100% 준수한 최종본만 출력하세요.
설명/해설/사과 금지. 결과물만 출력.

[실패 사유]
{fail_reasons}

[컨텍스트]
- 상호명: {store_name}
- 업종: {industry}
- 지역: {region}
- 혜택: {offer}
- 기간: {period}
- 추가 요청: {extra}

[스타일 가이드]
- 훅 강한 1~2줄 도입 (반문/충격/공감 중 택1, 예: '0원? 계산 맞나요?')
- 줄바꿈 자주 (모바일 가독성: 2~4줄마다)
- 과장/허위 금지, 옵션별 추가금 가능성 고지 포함
- 각 버전 본문 최소 {min_body}자

[출력 포맷 — 반드시 이 구조 그대로]
[소식글 Type C(가성비)]
제목: (15~30자)
본문: (최소 {min_body}자, 구성/혜택/비교 포인트 중심)
CTA: (채팅/문의/쿠폰/단골/예약 중 1개 키워드 포함)
FAQ:
Q1. ...
A1. ...
Q2. ...
A2. ...
Q3. ...
A3. ...
고지: ※ (유의사항/추가금 가능성 포함)

[소식글 Type B(긴급성)]
제목: (15~30자)
본문: (최소 {min_body}자, 긴급성/한정/시간 압박 중심)
CTA: (채팅/문의/쿠폰/단골/예약 중 1개 키워드 포함)
FAQ:
Q1. ...
A1. ...
Q2. ...
A2. ...
Q3. ...
A3. ...
고지: ※ (유의사항/추가금 가능성 포함)
"""


def build_news_repair_prompt(
    original_text: str,
    errors: List[str],
    context: dict,
) -> str:
    """검증 실패 시 repair 프롬프트 생성."""
    fail_reasons = "\n".join(f"- {e}" for e in errors)
    return _REPAIR_TEMPLATE.format(
        fail_reasons=fail_reasons,
        store_name=context.get("name", "[[미입력]]"),
        industry=context.get("industry", "[[미입력]]"),
        region=context.get("region", "[[미입력]]"),
        offer=context.get("benefits", "") or context.get("goal", "[[미입력]]"),
        period=context.get("period", "[[미입력]]"),
        extra=context.get("extra", ""),
        min_body=MIN_BODY_LENGTH,
    ).strip()
