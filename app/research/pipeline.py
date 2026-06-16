# -*- coding: utf-8 -*-
"""리서치 파이프라인 — 워커(search-discover/fetch-document/analyze-job)를
Redis/BullMQ 없이 in-process로 합친 포팅. discover → fetch → analyze.

AI 텍스트 생성은 generate_text(prompt, system_prompt=...) 콜러블로 주입한다
(UI는 get_provider("claude").generate_text, 테스트는 가짜 함수). 그래서 이 모듈은
네트워크/AI 없이도 단위 테스트가 가능하다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from app.research import connectors as C
from app.research import fetch as F
from app.research import insight as I
from app.research.sources import get_source, SourcePolicy

_log = __import__("logging").getLogger("research")


@dataclass
class ResearchRun:
    keyword: str
    documents: list[dict] = field(default_factory=list)   # 본문/댓글 수집 성공분
    insight: dict = field(default_factory=dict)
    sources_used: list[str] = field(default_factory=list)
    key_missing: list[str] = field(default_factory=list)   # 키 없어 건너뛴 소스 label
    discovered: int = 0
    fetched: int = 0
    failed: int = 0


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        return urlunparse(p._replace(fragment="", query=p.query)).rstrip("/").lower()
    except Exception:  # noqa: BLE001
        return (url or "").rstrip("/").lower()


def discover(
    keyword: str, source_ids, limit_per_source: int = 8,
) -> tuple[list[C.DiscoveryResult], list[str]]:
    """선택 소스별로 발견. (결과, 키없음_label) 반환. 키 없는 소스는 건너뛴다."""
    results: list[C.DiscoveryResult] = []
    key_missing: list[str] = []
    seen: set[str] = set()
    for sid in source_ids:
        sp: SourcePolicy | None = get_source(sid)
        if sp is None or not sp.enabled:
            continue
        try:
            if sp.discovery_method == "NAVER_API":
                found = C.discover_naver(keyword, sp.id, sp.naver_api_type or "blog", limit_per_source)
            else:
                found = C.discover_google_cse(keyword, sp.id, sp.cse_site_domain, limit_per_source)
        except C.ResearchKeyMissing:
            key_missing.append(sp.label)
            continue
        except C.ResearchAPIError:
            continue
        for r in found:
            key = _normalize_url(r.url)
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(r)
    return results, key_missing


def fetch_documents(
    results: list[C.DiscoveryResult], max_docs: int = 12, progress=None,
) -> tuple[list[dict], int]:
    """발견 결과의 본문+댓글 수집. (문서 list, 실패수)."""
    docs: list[dict] = []
    failed = 0
    for i, r in enumerate(results[: max_docs * 2]):  # 실패 감안 여유분
        if len(docs) >= max_docs:
            break
        sp = get_source(r.source_policy_id)
        fetch_mode = sp.fetch_mode if sp else "FETCH_FIRST"
        if progress:
            progress(f"본문 수집 {len(docs) + 1}/{max_docs} — {r.title[:24]}")
        res = F.fetch_document(r.url, r.source_policy_id, fetch_mode)
        if not res.ok:
            failed += 1
            continue
        docs.append({
            "title": res.title or r.title,
            "url": r.url,
            "content": res.content,
            "comments": res.comments,
            "comment_count": res.comment_count,
            "source_label": sp.label if sp else r.source_policy_id,
            "fetched_via": res.fetched_via,
        })
    return docs, failed


def analyze(keyword: str, documents: list[dict], generate_text) -> dict:
    """문서를 AI에 넣어 인사이트 JSON 파싱. generate_text는 주입."""
    if not documents:
        return dict(I._EMPTY)
    prompt = I.build_research_prompt(keyword, documents)
    text = generate_text(prompt, system_prompt=I.SYSTEM_GUIDE_RESEARCH)
    return I.parse_research_result(text or "")


def run_research(
    keyword: str, source_ids, generate_text,
    *, limit_per_source: int = 8, max_docs: int = 12, progress=None,
) -> ResearchRun:
    """전체 파이프라인. progress(msg) 콜백으로 진행 상황 보고."""
    run = ResearchRun(keyword=keyword)
    if progress:
        progress("커뮤니티 검색 중...")
    results, key_missing = discover(keyword, source_ids, limit_per_source)
    run.discovered = len(results)
    run.key_missing = key_missing
    run.sources_used = sorted({r.source_policy_id for r in results})
    if not results:
        return run

    docs, failed = fetch_documents(results, max_docs, progress)
    run.documents = docs
    run.fetched = len(docs)
    run.failed = failed
    if not docs:
        return run

    if progress:
        progress("AI가 커뮤니티 반응을 분석하고 있어요...")
    run.insight = analyze(keyword, docs, generate_text)
    return run


# ───────────────────────── 경쟁 광고 관측 (observe-ads 포팅) ─────────────────────────

def observe_ads(keyword: str, engines=("GOOGLE", "NAVER", "META"), progress=None) -> list:
    """google→naver→meta 순차 관측(observe-ads.worker.ts 포팅). Playwright 필수.

    엔진별로 에러를 격리해(하나 실패해도 나머지 진행) AdObservation 리스트를 모은다.
    Playwright 미설치면 PlaywrightMissing을 그대로 올린다(UI가 안내).
    """
    import time
    from app.research.stealth import StealthBrowser, random_delay_seconds
    from app.research import ads as A

    observations: list = []
    with StealthBrowser() as context:
        steps = [
            ("GOOGLE", "구글 검색광고 관측 중...", A.extract_google_ads),
            ("NAVER", "네이버 파워링크·브랜드검색 관측 중...", A.extract_naver_ads),
            ("META", "메타 광고 라이브러리 관측 중...", A.extract_meta_ads),
        ]
        for i, (engine, msg, extractor) in enumerate(steps):
            if engine not in engines:
                continue
            if progress:
                progress(msg)
            page = context.new_page()
            try:
                observations.extend(extractor(page, keyword))
            except Exception as exc:  # noqa: BLE001 — 엔진별 격리
                _log.warning("ad observation failed (%s): %s", engine, exc)
            finally:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
            if i < len(steps) - 1:
                time.sleep(random_delay_seconds(1500, 3500))
    return observations
