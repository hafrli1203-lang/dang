# -*- coding: utf-8 -*-
"""발견(discovery) connectors — naver.ts / google-cse.ts의 충실 포팅.

NaverSearchConnector: 네이버 검색 API(blog/cafearticle/kin/news/webkr).
GoogleCseConnector: Google Custom Search(site: 제한으로 커뮤니티 도메인 한정).
키는 env에서 읽고, 없으면 ResearchKeyMissing을 던진다(UI가 안내).
HTTP는 _http_get_json으로 분리해 테스트에서 주입 가능.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_TAG_RE = re.compile(r"<[^>]*>")
_ENT_RE = re.compile(r"&[a-z]+;", re.IGNORECASE)


def _cutoff_date(period_months: int | None) -> date | None:
    """기간(개월) → 그보다 오래된 글을 자르는 컷오프 날짜. None/0이면 제한 없음.

    달력 월 경계의 복잡함을 피하려 1개월=30일 근사로 본다(리서치 목적엔 충분).
    """
    if not period_months or period_months <= 0:
        return None
    return date.today() - timedelta(days=int(period_months) * 30)


def _naver_item_date(item: dict, naver_api_type: str) -> date | None:
    """네이버 검색 결과 1건의 작성일. 날짜를 주는 타입(blog/news)만 파싱, 나머진 None.

    blog: postdate=YYYYMMDD, news: pubDate=RFC822. cafearticle/kin/webkr는 날짜 미제공.
    """
    if naver_api_type == "blog":
        pd = str(item.get("postdate", "")).strip()
        if len(pd) == 8 and pd.isdigit():
            try:
                return date(int(pd[:4]), int(pd[4:6]), int(pd[6:8]))
            except ValueError:
                return None
    elif naver_api_type == "news":
        pub = str(item.get("pubDate", "")).strip()
        if pub:
            try:
                return datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z").date()
            except ValueError:
                return None
    return None


@dataclass(frozen=True)
class DiscoveryResult:
    title: str
    url: str
    snippet: str
    rank: int
    source_policy_id: str


class ResearchKeyMissing(Exception):
    """검색 API 키가 .env에 없을 때."""


class ResearchAPIError(Exception):
    """검색 API HTTP 오류."""


def _strip_html(s: str) -> str:
    return _ENT_RE.sub(" ", _TAG_RE.sub("", s or "")).strip()


def _http_get_json(url: str, headers: dict | None = None, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", 200)
        if status and status >= 400:
            raise ResearchAPIError(f"HTTP {status}")
        return json.loads(resp.read().decode("utf-8"))


# ───────────────────────── Naver ─────────────────────────

_NAVER_API_MAP = {
    "blog": "/v1/search/blog.json",
    "cafearticle": "/v1/search/cafearticle.json",
    "kin": "/v1/search/kin.json",
    "news": "/v1/search/news.json",
    "webkr": "/v1/search/webkr.json",
}


def naver_credentials() -> tuple[str, str]:
    return (os.getenv("NAVER_CLIENT_ID", ""), os.getenv("NAVER_CLIENT_SECRET", ""))


def discover_naver(
    keyword: str,
    source_policy_id: str,
    naver_api_type: str,
    limit: int = 10,
    period_months: int | None = None,
    *,
    sort: str = "sim",
    http_get_json=_http_get_json,
) -> list[DiscoveryResult]:
    """네이버 검색. 리서치는 적합성이 핵심이라 기본 sort='sim'(정확도순).

    실측: sort='date'(최신순)는 키워드와 무관한 최신 글(퀴즈정답·잡담)을 긁어 노이즈가 큼.
    sort='sim'은 키워드 적합 글을 줘서 고객 목소리 품질이 훨씬 높음.

    period_months가 있으면 그 기간보다 오래된 글을 제외한다.
    - sort='date'(최신순)면 기간 밖 글을 만나는 순간 이후는 모두 더 오래됨 → 조기 중단.
    - sort='sim'면 순서가 날짜와 무관하므로 오래된 글은 '건너뛰고' 계속 페이징.
    날짜를 안 주는 타입(cafearticle/kin/webkr)은 필터 불가 → 적합도 상위 건수로 동작(정직).
    """
    if naver_api_type not in _NAVER_API_MAP:
        raise ResearchAPIError(f"Unknown Naver API type: {naver_api_type}")
    cid, csecret = naver_credentials()
    if not cid or not csecret:
        raise ResearchKeyMissing("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET")

    endpoint = _NAVER_API_MAP[naver_api_type]
    cutoff = _cutoff_date(period_months)
    results: list[DiscoveryResult] = []
    display = min(limit, 100)
    start = 1
    stop = False
    while len(results) < limit and start <= 1000 and not stop:
        qs = urllib.parse.urlencode({
            "query": keyword, "display": display, "start": start, "sort": sort,
        })
        data = http_get_json(
            f"https://openapi.naver.com{endpoint}?{qs}",
            {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csecret},
        )
        items = data.get("items") or []
        if not items:
            break
        for item in items:
            if len(results) >= limit:
                break
            if cutoff is not None:
                item_date = _naver_item_date(item, naver_api_type)
                if item_date is not None and item_date < cutoff:
                    # date 정렬이면 이후 전부 더 오래됨 → 중단. sim 정렬이면 건너뛰고 계속.
                    if sort == "date":
                        stop = True
                        break
                    continue
            results.append(DiscoveryResult(
                title=_strip_html(item.get("title", "")),
                url=item.get("link") or item.get("originallink") or "",
                snippet=_strip_html(item.get("description", "")),
                rank=len(results) + 1,
                source_policy_id=source_policy_id,
            ))
        start += display
        if len(items) < display:
            break
    return results


# ───────────────────────── Google CSE ─────────────────────────

_TIME_MAP = {"1d": "d1", "1w": "w1", "1m": "m1", "3m": "m3", "6m": "m6", "1y": "y1"}


def google_cse_credentials() -> tuple[str, str]:
    return (os.getenv("GOOGLE_CSE_API_KEY", ""), os.getenv("GOOGLE_CSE_CX", ""))


def discover_google_cse(
    keyword: str,
    source_policy_id: str,
    cse_site_domain: str | None = None,
    limit: int = 10,
    time_filter: str | None = None,
    period_months: int | None = None,
    *,
    http_get_json=_http_get_json,
) -> list[DiscoveryResult]:
    api_key, cx = google_cse_credentials()
    if not api_key or not cx:
        raise ResearchKeyMissing("GOOGLE_CSE_API_KEY / GOOGLE_CSE_CX")

    results: list[DiscoveryResult] = []
    start_index = 1
    # 기간(개월)이 오면 그대로 dateRestrict=m{N}. 없으면 기존 time_filter 버킷 매핑.
    if period_months and period_months > 0:
        date_restrict = f"m{int(period_months)}"
    else:
        date_restrict = _TIME_MAP.get(time_filter or "")
    while len(results) < limit and start_index <= 91:
        query = f"site:{cse_site_domain} {keyword}" if cse_site_domain else keyword
        params = {
            "key": api_key, "cx": cx, "q": query,
            "num": min(10, limit - len(results)), "start": start_index,
        }
        if date_restrict:
            params["dateRestrict"] = date_restrict
        data = http_get_json(
            "https://customsearch.googleapis.com/customsearch/v1?"
            + urllib.parse.urlencode(params)
        )
        items = data.get("items") or []
        if not items:
            break
        for item in items:
            if len(results) >= limit:
                break
            results.append(DiscoveryResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                rank=len(results) + 1,
                source_policy_id=source_policy_id,
            ))
        start_index += 10
        if len(items) < 10:
            break
    return results
