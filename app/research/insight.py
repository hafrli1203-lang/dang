# -*- coding: utf-8 -*-
"""커뮤니티 반응 → 콘텐츠 인사이트 — prompts.ts / schema.ts의 당근화 포팅.

검색 프로젝트는 본문+댓글을 AI에 넣어 pain_points·desires·creative_insights 등을
JSON으로 뽑는다. 여기서는 동일 구조에 '실제 표현(real_expressions)'과
'콘텐츠 앵글(content_angles)·후크(hook_ideas)'를 더해 당근 소식글/광고 콘텐츠
다양화 재료로 쓴다. (AI 호출은 페이지의 async 레이어가 담당 — 여기는 프롬프트
빌드 + 파싱만, ai_engine.py 패턴과 동일.)
"""
from __future__ import annotations

import json
import re

MAX_TOTAL_CHARS = 120_000

SYSTEM_GUIDE_RESEARCH = """\
당신은 한국 자영업 광고를 돕는 마케팅 리서치 분석가입니다. 네이버 블로그·카페·
지식인과 커뮤니티에서 수집한 글 본문과 댓글(실제 고객의 목소리)을 분석해, 당근
비즈프로필 소식글·광고 콘텐츠를 '다양화'할 재료를 뽑습니다.

[원칙]
- 추측 금지. 수집된 본문·댓글에 실제로 나타난 표현·감정·맥락만 사용합니다.
- 특히 '댓글'은 가장 솔직한 반응입니다. 사람들이 실제로 쓰는 단어·말투·불만·환호를 그대로 포착하세요.
- 광고처럼 매끈한 말 대신, 커뮤니티에서 통하는 날것의 표현을 우선합니다.

반드시 아래 JSON 스키마에 정확히 맞는 유효한 JSON만 출력합니다(코드블록 없이, 설명 없이):
{
  "verdict": "수집 내용 한 줄 종합",
  "pain_points": ["고객이 겪는 불편·고민(구체적으로)"],
  "desires": ["고객이 원하는 것·기대"],
  "real_expressions": ["커뮤니티에서 실제로 쓰는 표현·말투·단어 (그대로 인용)"],
  "offer_signals": ["혜택·가격·프로모션에 반응하는 신호"],
  "competitors": [{"name": "경쟁 브랜드/매장", "mention_count": 0, "sentiment": "positive|neutral|negative"}],
  "content_angles": ["당근 소식글/광고로 풀 수 있는 서로 다른 콘텐츠 앵글 (다양하게)"],
  "hook_ideas": ["썸네일·제목으로 쓸 후크 문장 후보 (각 30자 내외)"],
  "next_actions": ["광고주가 바로 할 수 있는 다음 행동"]
}
모든 텍스트는 한국어. 구체적이고 실행 가능하게.
"""

# 빈 결과 골격(파싱 실패 시 degrade).
_EMPTY = {
    "verdict": "", "pain_points": [], "desires": [], "real_expressions": [],
    "offer_signals": [], "competitors": [], "content_angles": [],
    "hook_ideas": [], "next_actions": [],
}
_LIST_KEYS = ("pain_points", "desires", "real_expressions", "offer_signals",
              "content_angles", "hook_ideas", "next_actions")


def build_research_prompt(keyword: str, documents: list[dict]) -> str:
    """documents: [{title, content, comments, comment_count, source_label}]."""
    blocks: list[str] = []
    total = 0
    for i, d in enumerate(documents, 1):
        src = d.get("source_label", "")
        head = f"--- 문서 {i} [{src}]: {d.get('title', '')} ---\n{d.get('content', '')}"
        cc = int(d.get("comment_count", 0) or 0)
        if d.get("comments") and cc > 0:
            head += f"\n\n[댓글 {cc}개]\n{d['comments']}"
        if total + len(head) > MAX_TOTAL_CHARS:
            break
        total += len(head)
        blocks.append(head)
    joined = "\n\n".join(blocks) if blocks else "(수집된 문서가 없습니다)"
    return (
        f'검색 키워드: "{keyword}"\n\n'
        "다음은 한국 커뮤니티에서 수집한 문서와 댓글입니다. 종합 분석해 위 JSON 스키마로만 답하세요.\n\n"
        f"{joined}"
    )


def parse_research_result(text: str) -> dict:
    """AI 응답 텍스트에서 JSON을 견고하게 추출 → 스키마 정규화. 실패 시 빈 골격."""
    raw = _extract_json_object(text)
    if not isinstance(raw, dict):
        result = dict(_EMPTY)
        result["verdict"] = (text or "").strip()[:300]
        return result

    result = dict(_EMPTY)
    if isinstance(raw.get("verdict"), str):
        result["verdict"] = raw["verdict"].strip()
    for key in _LIST_KEYS:
        val = raw.get(key)
        if isinstance(val, list):
            result[key] = [str(x).strip() for x in val if str(x).strip()]
    comps = raw.get("competitors")
    if isinstance(comps, list):
        norm = []
        for c in comps:
            if not isinstance(c, dict):
                continue
            sent = str(c.get("sentiment", "neutral")).lower()
            if sent not in ("positive", "neutral", "negative"):
                sent = "neutral"
            try:
                cnt = int(c.get("mention_count", 0) or 0)
            except (ValueError, TypeError):
                cnt = 0
            norm.append({"name": str(c.get("name", "")).strip(),
                         "mention_count": cnt, "sentiment": sent})
        result["competitors"] = [c for c in norm if c["name"]]
    return result


def format_research_insight(insight: dict, keyword: str = "") -> str:
    """리서치 인사이트 dict → 사람이 읽고 기획 프롬프트에 주입 가능한 마크다운 요약.

    /research 결과를 매장별로 저장하고, 전략·소식글 빌더가 '실제 고객의 목소리'
    근거로 재사용한다(리서치 선행 → 기획 연결). 빈 결과면 '' 반환.
    """
    if not isinstance(insight, dict):
        return ""
    labels = (
        ("pain_points", "고충"), ("desires", "욕구"), ("real_expressions", "실제 표현"),
        ("offer_signals", "혜택 반응 신호"), ("content_angles", "콘텐츠 앵글"),
        ("hook_ideas", "후크 후보"),
    )
    lines: list[str] = []
    for key, name in labels:
        vals = insight.get(key)
        if isinstance(vals, list):
            items = [str(v).strip() for v in vals if str(v).strip()]
            if items:
                lines.append(f"- {name}: " + " / ".join(items[:6]))
    verdict = str(insight.get("verdict", "")).strip()
    if not lines and not verdict:
        return ""
    kw = (keyword or "").strip()
    out = ["커뮤니티 리서치 요약" + (f" — '{kw}'" if kw else "")]
    if verdict:
        out.append(f"- 종합: {verdict}")
    out.extend(lines)
    return "\n".join(out)


def _extract_json_object(text: str):
    if not text:
        return None
    # ```json ... ``` 우선
    m = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else None
    if candidate is None:
        # 첫 { 부터 마지막 } 까지
        start, end = text.find("{"), text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end > start else text
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
