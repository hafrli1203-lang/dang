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

_TAG_RE = re.compile(r"<[^>]*>")
_ENT_RE = re.compile(r"&[a-z]+;", re.IGNORECASE)


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
    *,
    http_get_json=_http_get_json,
) -> list[DiscoveryResult]:
    if naver_api_type not in _NAVER_API_MAP:
        raise ResearchAPIError(f"Unknown Naver API type: {naver_api_type}")
    cid, csecret = naver_credentials()
    if not cid or not csecret:
        raise ResearchKeyMissing("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET")

    endpoint = _NAVER_API_MAP[naver_api_type]
    results: list[DiscoveryResult] = []
    display = min(limit, 100)
    start = 1
    while len(results) < limit and start <= 1000:
        qs = urllib.parse.urlencode({
            "query": keyword, "display": display, "start": start, "sort": "date",
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
    *,
    http_get_json=_http_get_json,
) -> list[DiscoveryResult]:
    api_key, cx = google_cse_credentials()
    if not api_key or not cx:
        raise ResearchKeyMissing("GOOGLE_CSE_API_KEY / GOOGLE_CSE_CX")

    results: list[DiscoveryResult] = []
    start_index = 1
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
