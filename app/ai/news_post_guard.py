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
- 반드시 아래 "출력 포맷"을 100% 그대로 지키세요. (섹션명/이모지/순서 고정)
- 반드시 2개 버전을 모두 출력하세요:
  - (1) 의심해소형: '정말 0원이냐' 의심 제거 + 조건/제외/추가금 가능 항목을 투명하게 안내
  - (2) 가성비형: '이 가격에 이 구성?' 논리적 이득 납득 + 구성/혜택/비교 포인트 강조
- 확인 불가한 사실(상세 주소/영업시간/주차/가격 범위 등)은 절대 임의로 만들지 말고
  반드시 [[확인 필요: ...]] 형태로 표시하세요.
- 과장/단정 금지: "무조건", "전부", "절대 추가금 없음", "100%" 같은 단정은 금지.
  대신 "기본 범위 내", "케이스별 안내", "특수옵션은 추가금 가능" 형태로 안전하게 작성.
- 본문은 모바일 가독성: 2~4줄마다 줄바꿈.
- 각 버전마다 CTA는 반드시 3회(상/중/하) 들어가야 합니다.
- 각 버전마다 FAQ는 최소 4문항(Q/A)로 작성.
- 각 버전마다 고지(유의사항) 섹션에 "특수옵션/추가금 가능" 문구를 반드시 포함.

[INPUT DATA]
- 상호명: {{store_name}}
- 위치(동네/구): {{region}}
- 업종/카테고리: {{industry}}
- 행사/핵심 혜택(오퍼): {{offer}}
- 적용 조건(있으면): {{offer_condition}}
- 기간: {{period}}
- 추가 혜택(있으면): {{extra_benefit}}
- 문의 유도(기본): "채팅으로 문의 주시면 1분 내 안내"
- 영업시간: {{hours}}
- 주차: {{parking}}
- 제외/추가금 가능 항목(있으면): {{extra_cost_items}}

[OUTPUT FORMAT - MUST FOLLOW EXACTLY]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 1 | 의심해소형】
제목: (15~30자, 문장부호 1개 이상)

(상단 훅 2~4줄: 의심을 먼저 인정하고 멈칫하게 만들기)

💬 빠른 문의 (상단 CTA)
- (딱 1~2줄, 문의 유도)

(본문 1: 오퍼를 1문장으로 확정 + 조건을 짧게)
(본문 2: "왜 의심해도 되는지 → 그래서 이렇게 투명하게 안내한다" 흐름)
(본문 3: 고객이 걱정하는 포인트 3개를 '먼저' 꺼내서 해소)
(본문 4: 추가 혜택/당근 보고 왔다 혜택/단골·쿠폰 유도 중 1~2개만)

💬 빠른 문의 (중단 CTA)
- (딱 1~2줄, 지금 바로 채팅 유도)

❓ 자주 묻는 질문(FAQ)
Q1. …
A1. …
Q2. …
A2. …
Q3. …
A3. …
Q4. …
A4. …

※ 꼭 읽어주세요 (고지/유의사항)
- 기본 혜택 범위: …
- 특수옵션은 케이스별 추가금이 있을 수 있음
- 정확한 적용 범위/비용은 상담 후 최종 안내

📍 매장 정보
- 위치: {{region}} / [[확인 필요: 상세 주소]]
- 영업시간: {{hours}} / [[확인 필요: 정확한 시간]]
- 주차: {{parking}} / [[확인 필요: 주차 안내]]
- 문의: 채팅

💬 빠른 문의 (하단 CTA)
- (핵심 키워드 1개를 넣어서 한 줄로 마무리)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【소식글 2 | 가성비형】
제목: (15~30자, 문장부호 1개 이상)

(상단 훅 2~4줄: "이 가격에 이 구성?" 충격/독백/팩트형 중 택1)

💬 빠른 문의 (상단 CTA)
- (딱 1~2줄)

(본문 1: '구성/혜택' 목록을 "짧은 줄"로 툭툭 나열)
(본문 2: 왜 이렇게 하는지(철학/명분) 2~4줄)
(본문 3: 현장 반응 2~4줄)
(본문 4: 방문 장벽 제거(위치/주차/예약) 안내)

💬 빠른 문의 (중단 CTA)
- (딱 1~2줄)

❓ 자주 묻는 질문(FAQ)
Q1. …
A1. …
Q2. …
A2. …
Q3. …
A3. …
Q4. …
A4. …

※ 꼭 읽어주세요 (고지/유의사항)
- 기본 혜택 범위: …
- 특수옵션은 케이스별 추가금이 있을 수 있음
- 정확한 적용 범위/비용은 상담 후 최종 안내

📍 매장 정보
- 위치: {{region}} / [[확인 필요: 상세 주소]]
- 영업시간: {{hours}} / [[확인 필요: 정확한 시간]]
- 주차: {{parking}} / [[확인 필요: 주차 안내]]
- 문의: 채팅

💬 빠른 문의 (하단 CTA)
- (한 줄 마무리)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2) VALIDATION RULES (참고용 dict + 실제 검증 함수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VALIDATION_RULES: Dict[str, str] = {
    "block_headers": '【소식글 1 | 의심해소형】 + 【소식글 2 | 가성비형】 모두 존재',
    "title": '각 블록에 "제목: .+" 존재',
    "cta_3x": '각 블록에 💬 빠른 문의 (상단/중단/하단 CTA) 3회',
    "faq_4q": '각 블록에 ❓ FAQ + Q1~Q4/A1~A4',
    "notice": '※ 꼭 읽어주세요 + "추가금" 키워드',
    "store_info": '📍 매장 정보 존재',
    "body_length": '각 블록 본문 최소 900자',
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

_CTA_RE = {
    "상단": re.compile(r"💬\s*빠른 문의\s*\(상단 CTA\)"),
    "중단": re.compile(r"💬\s*빠른 문의\s*\(중단 CTA\)"),
    "하단": re.compile(r"💬\s*빠른 문의\s*\(하단 CTA\)"),
}

_FAQ_HEADER_RE = re.compile(r"❓\s*자주 묻는 질문\s*\(?FAQ\)?")
_FAQ_QA_RE = {
    i: re.compile(rf"Q{i}\.\s*.+\nA{i}\.\s*.+", re.MULTILINE)
    for i in range(1, 5)
}

_NOTICE_HEADER_RE = re.compile(r"※\s*꼭 읽어주세요\s*\(고지/유의사항\)")
_NOTICE_EXTRA_RE = re.compile(r"추가금")

_STORE_INFO_RE = re.compile(r"📍\s*매장 정보")

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
    """블록에서 헤더/FAQ/고지/매장정보/CTA 라인을 제외한 순수 본문."""
    lines = block.splitlines()
    body_lines: list[str] = []
    skip_section = False
    for line in lines:
        stripped = line.strip()
        # 섹션 헤더 감지 → skip
        if any(p.search(stripped) for p in [
            _FAQ_HEADER_RE, _NOTICE_HEADER_RE, _STORE_INFO_RE,
        ]):
            skip_section = True
            continue
        if any(p.search(stripped) for p in _CTA_RE.values()):
            skip_section = True
            continue
        if _TITLE_RE.match(stripped):
            continue
        # 새 섹션이 아닌 빈 줄은 skip 해제
        if skip_section:
            if stripped == "" or stripped.startswith("-") or stripped.startswith("Q") or stripped.startswith("A"):
                continue
            # 본문처럼 보이는 줄이면 skip 해제
            if not stripped.startswith("━"):
                skip_section = False
        if not skip_section and stripped and not stripped.startswith("━"):
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

        # ── CTA 3회 ──
        for pos, rx in _CTA_RE.items():
            if not rx.search(block):
                errors.append(f"{prefix} 💬 빠른 문의 ({pos} CTA) 누락")

        # ── FAQ ──
        if not _FAQ_HEADER_RE.search(block):
            errors.append(f"{prefix} ❓ FAQ 섹션 누락")
        else:
            for i in range(1, 5):
                if not _FAQ_QA_RE[i].search(block):
                    errors.append(f"{prefix} FAQ Q{i}/A{i} 누락")

        # ── 고지 ──
        if not _NOTICE_HEADER_RE.search(block):
            errors.append(f"{prefix} ※ 고지/유의사항 섹션 누락")
        elif not _NOTICE_EXTRA_RE.search(block):
            errors.append(f"{prefix} 고지에 '추가금' 키워드 누락")

        # ── 매장 정보 ──
        if not _STORE_INFO_RE.search(block):
            errors.append(f"{prefix} 📍 매장 정보 섹션 누락")

        # ── 본문 길이 (헤더/FAQ/고지/매장/CTA 제외) ──
        body_text = _extract_body_text(block)
        body_len = len(body_text.replace(" ", "").replace("\n", ""))
        if body_len < 900:
            errors.append(f"{prefix} 본문 너무 짧음 (최소 900자 필요, 현재 {body_len}자)")

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
        "{{store_name}}": project.get("name", "[[확인 필요: 상호명]]"),
        "{{region}}": project.get("region", "[[확인 필요: 지역]]"),
        "{{industry}}": project.get("industry", "[[확인 필요: 업종]]"),
        "{{offer}}": offer or "[[확인 필요: 핵심 혜택]]",
        "{{offer_condition}}": extra.strip() if extra.strip() else "[[확인 필요: 적용 조건]]",
        "{{period}}": project.get("period", "[[확인 필요: 기간]]"),
        "{{extra_benefit}}": benefits or "[[확인 필요: 추가 혜택]]",
        "{{hours}}": "[[확인 필요: 영업시간]]",
        "{{parking}}": "[[확인 필요: 주차]]",
        "{{extra_cost_items}}": "[[확인 필요: 제외/추가금 항목]]",
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
        f"- 적용 조건: {extra.strip() or '[[확인 필요]]'}\n"
        f"- 기간: {project.get('period', '')}\n"
        f"- 추가 혜택: {benefits or '[[확인 필요]]'}\n"
        f"- 영업시간: [[확인 필요]]\n"
        f"- 주차: [[확인 필요]]\n"
        f"- 제외/추가금: [[확인 필요]]"
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
