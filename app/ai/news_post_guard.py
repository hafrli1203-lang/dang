# -*- coding: utf-8 -*-
"""
Commit 3 — Asset Pack v1.0: 소식글 강제 출력 포맷 + 검증 + repair.

세 상수:
  FORCED_TEMPLATE   — LLM user prompt 끝에 부착 (모델 출력 포맷 강제)
  VALIDATION_RULES  — (참고용 dict) 정규식 + 추가 조건 설명
  REPAIR_PROMPT_TPL — 검증 실패 시 재요청 프롬프트 템플릿

함수:
  format_forced_template(project, extra="") → str
  validate_news_post(text) → (bool, list[str])
  build_news_post_repair_prompt(fail_reasons, input_data) → str
"""

from __future__ import annotations
import re
from typing import Dict, List, Tuple

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1) FORCED_TEMPLATE (모델 입력용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORCED_TEMPLATE = r"""
[INSTRUCTION]
- 당신의 출력은 "당근 비즈프로필 소식글" 최종본입니다. 설명/해설/사과/추가 제안 금지.
- 반드시 2개 버전을 모두 출력하세요:
  - (1) 의심해소형: 소비자의 의심/불안을 먼저 꺼내고 → 사실/경험으로 해소
  - (2) 가성비형: "이 가격에 이 구성?" 경제적 이득을 논리적으로 납득시킴
- 소식글은 '광고'가 아니라 '이웃에게 보내는 진심 어린 소식'이어야 합니다.
  읽는 사람이 "오, 한번 가봐야겠다"라고 느끼도록 매력적으로 작성하세요.
- 과장/단정 금지: "무조건", "전부", "100%" 같은 단정은 금지.
  대신 구체적 사실, 숫자, 경험으로 설득하세요.
- 본문은 모바일 가독성: 2~4줄마다 줄바꿈.
- 각 버전 제목 위에 쿠폰/혜택 훅 문구를 배치. 예: "쿠폰부터 받고 읽어주세요!"
- 각 버전마다 CTA를 2~3회 자연스럽게 배치 (본문 흐름 속에).
  CTA는 "채팅 주세요", "문의 주세요" 등 부드러운 표현 사용.
- 법적 면책 조항, 유의사항, 고지 섹션은 넣지 마세요.
  소식글은 고객을 끌어들이는 글입니다. 딱딱한 안내문이 아닙니다.
- 매장 위치는 본문 마무리에 자연스럽게 1줄로 녹이세요.

[INPUT DATA]
- 상호명: {{store_name}}
- 위치(동네/구): {{region}}
- 업종/카테고리: {{industry}}
- 행사/핵심 혜택(오퍼): {{offer}}
- 적용 조건(있으면): {{offer_condition}}
- 기간: {{period}}
- 추가 혜택(있으면): {{extra_benefit}}

[OUTPUT FORMAT - MUST FOLLOW EXACTLY]

【소식글 1 | 의심해소형】
쿠폰/혜택 훅 문구 1줄

제목: (15~30자, 궁금증/혜택/숫자 포함)

(상단 훅 2~4줄: 의심을 먼저 인정하고 멈칫하게 만들기)

(본문: 의심 포인트 제시 → 구체적 사실/숫자/경험으로 해소 → 추가 신뢰 근거)
(총 15~25줄, 2~4줄마다 빈 줄로 구분)
(CTA를 본문 중간과 끝에 자연스럽게 배치)

{{region}} 에서 만나요!


【소식글 2 | 가성비형】
쿠폰/혜택 훅 문구 1줄

제목: (15~30자, 가격/구성 충격 포함)

(상단 훅 2~4줄: "이 가격에 이 구성?" 충격/팩트형)

(본문: 구성/혜택 구체 나열 → 왜 이 가격인지 이유 → 현장 반응/후기)
(총 15~25줄, 2~4줄마다 빈 줄로 구분)
(CTA를 본문 중간과 끝에 자연스럽게 배치)

{{region}} 에서 만나요!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2) VALIDATION RULES (참고용 dict + 실제 검증 함수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VALIDATION_RULES: Dict[str, str] = {
    "block_headers": '【소식글 1 | 의심해소형】 + 【소식글 2 | 가성비형】 모두 존재',
    "title": '각 블록에 "제목: .+" 존재',
    "coupon_hook": '각 블록에 쿠폰/혜택 훅 키워드 존재 (👆, 쿠폰)',
    "cta_2x": '각 블록에 CTA 2회 이상 (채팅/문의/확인 등)',
    "body_length": '각 블록 본문 최소 500자',
    "line_breaks": '각 블록 최소 14개 줄바꿈',
    "forbidden": '"무조건", "전부", "절대 추가금 없음", "100%" 금지',
}

# ── 컴파일된 정규식 ──

_BLOCK_RE = {
    "의심해소": re.compile(r"【소식글\s*1\s*\|\s*의심해소형】"),
    "가성비": re.compile(r"【소식글\s*2\s*\|\s*가성비형】"),
}

_BLOCK_SPLIT_RE = re.compile(
    r"(【소식글\s*\d+\s*\|\s*(?:의심해소형|가성비형)】)"
)

_TITLE_RE = re.compile(r"제목:\s*(.+)")

_CTA_RE = re.compile(
    r"채팅|문의|확인해\s*보세요|상담|예약|방문",
)

_FORBIDDEN_WORDS = ["무조건", "전부", "절대 추가금 없음", "100%"]

_GREETING_RE = re.compile(r"^\s*안녕하세요")


def _split_blocks(text: str) -> Dict[str, str]:
    """텍스트를 블록 헤더 기준으로 분리. {블록명: 본문}"""
    parts = _BLOCK_SPLIT_RE.split(text)
    blocks: Dict[str, str] = {}
    for i, part in enumerate(parts):
        if "의심해소형" in part:
            body = parts[i + 1] if i + 1 < len(parts) else ""
            blocks["의심해소"] = body
        elif "가성비형" in part:
            body = parts[i + 1] if i + 1 < len(parts) else ""
            blocks["가성비"] = body
    return blocks


def _extract_body_text(block: str) -> str:
    """블록에서 제목 라인을 제외한 순수 본문."""
    lines = block.splitlines()
    body_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _TITLE_RE.match(stripped):
            continue
        if stripped and not stripped.startswith("━"):
            body_lines.append(line)
    return "\n".join(body_lines)


def validate_news_post(text: str) -> Tuple[bool, List[str]]:
    """소식글 출력 검증.

    Returns:
        (ok, errors) — ok=True이면 통과, errors는 실패 사유 리스트
    """
    errors: List[str] = []
    raw = text or ""

    # ── 블록 헤더 존재 ──
    for name, rx in _BLOCK_RE.items():
        if not rx.search(raw):
            errors.append(f"블록 헤더 누락: 【소식글 {'1' if name == '의심해소' else '2'} | {name}형】")

    blocks = _split_blocks(raw)

    for name in ["의심해소", "가성비"]:
        block = blocks.get(name, "")
        prefix = f"[{name}형]"

        if not block:
            if not any(name in e for e in errors):
                errors.append(f"{prefix} 블록 본문 없음")
            continue

        # ── 제목 ──
        if not _TITLE_RE.search(block):
            errors.append(f"{prefix} 제목 누락 (\"제목: ...\" 형식 필요)")

        # ── 쿠폰/혜택 훅 ──
        if "👆" not in block and "쿠폰" not in block:
            errors.append(f"{prefix} 쿠폰/혜택 훅 문구 누락 (👆 또는 쿠폰 키워드 필요)")

        # ── CTA 2회 ──
        cta_count = len(_CTA_RE.findall(block))
        if cta_count < 2:
            errors.append(f"{prefix} CTA 부족 (최소 2회 필요, 현재 {cta_count}회)")

        # ── 본문 길이 (헤더/고지/매장/CTA 제외) ──
        body_text = _extract_body_text(block)
        body_len = len(body_text.replace(" ", "").replace("\n", ""))
        if body_len < 500:
            errors.append(f"{prefix} 본문 너무 짧음 (최소 500자 필요, 현재 {body_len}자)")

        # ── 줄바꿈 (모바일 가독성) ──
        newline_count = block.count("\n")
        if newline_count < 14:
            errors.append(f"{prefix} 줄바꿈 부족 (최소 14개 필요, 현재 {newline_count}개)")

        # ── 첫 줄 인사말 금지 (제목 제외한 첫 3줄) ──
        content_lines = [
            ln.strip() for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith("제목:")
        ][:3]
        for cl in content_lines:
            if _GREETING_RE.search(cl):
                errors.append(f"{prefix} 본문이 '안녕하세요'로 시작 (훅/CTA로 시작해야 함)")
                break

    # ── 금지어 (전체 텍스트 대상) ──
    for word in _FORBIDDEN_WORDS:
        if word in raw:
            errors.append(f"금지어 감지: \"{word}\"")

    return (len(errors) == 0, errors)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3) REPAIR PROMPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REPAIR_PROMPT_TPL = """\
[REPAIR INSTRUCTION]
당신의 이전 출력은 "포맷/필수 섹션/길이/금지어" 검증에 실패했습니다.
아래 [실패 사유]를 해결하여, [OUTPUT FORMAT - MUST FOLLOW EXACTLY]를 100% 준수한 최종본을 다시 작성하세요.

- 부분 수정 금지: 처음부터 "전체 재작성"
- 설명/해설 금지: 결과물만 출력
- 2개 버전(의심해소형 + 가성비형) 모두 필수

[실패 사유]
{fail_reasons}

[INPUT DATA]
{input_data}

이제 [OUTPUT FORMAT - MUST FOLLOW EXACTLY] 그대로 출력하세요.

{forced_template_output_section}
"""


def format_forced_template(project: dict, extra: str = "") -> str:
    """FORCED_TEMPLATE의 {{placeholder}}를 프로젝트 데이터로 채운다."""
    benefits = project.get("benefits", "")
    goal = project.get("goal", "")
    offer = benefits if benefits else goal

    replacements = {
        "{{store_name}}": project.get("name", "(상호명)"),
        "{{region}}": project.get("region", "(지역)"),
        "{{industry}}": project.get("industry", "(업종)"),
        "{{offer}}": offer or "(핵심 혜택)",
        "{{offer_condition}}": extra.strip() if extra.strip() else "(조건 없음)",
        "{{period}}": project.get("period", "(기간 미정)"),
        "{{extra_benefit}}": benefits or "(없음)",
    }

    result = FORCED_TEMPLATE
    for key, val in replacements.items():
        result = result.replace(key, val)
    return result


def _build_input_data_block(project: dict, extra: str = "") -> str:
    """repair 프롬프트용 INPUT DATA 블록 생성."""
    benefits = project.get("benefits", "")
    goal = project.get("goal", "")
    return (
        f"- 상호명: {project.get('name', '')}\n"
        f"- 위치(동네/구): {project.get('region', '')}\n"
        f"- 업종/카테고리: {project.get('industry', '')}\n"
        f"- 행사/핵심 혜택(오퍼): {benefits or goal}\n"
        f"- 적용 조건: {extra.strip() or '(조건 없음)'}\n"
        f"- 기간: {project.get('period', '')}\n"
        f"- 추가 혜택: {benefits or '(없음)'}"
    )


def _get_output_format_section() -> str:
    """FORCED_TEMPLATE에서 [OUTPUT FORMAT...] 이후만 추출."""
    marker = "[OUTPUT FORMAT - MUST FOLLOW EXACTLY]"
    idx = FORCED_TEMPLATE.find(marker)
    if idx >= 0:
        return FORCED_TEMPLATE[idx:]
    return FORCED_TEMPLATE


def build_news_post_repair_prompt(
    *,
    errors: List[str],
    project: dict,
    extra: str = "",
) -> str:
    """검증 실패 시 repair 프롬프트 생성."""
    fail_reasons = "\n".join(f"- {e}" for e in errors)
    input_data = _build_input_data_block(project, extra)
    output_section = _get_output_format_section()

    return REPAIR_PROMPT_TPL.format(
        fail_reasons=fail_reasons,
        input_data=input_data,
        forced_template_output_section=output_section,
    ).strip()
