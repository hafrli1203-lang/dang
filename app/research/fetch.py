# -*- coding: utf-8 -*-
"""본문 + 댓글 수집 — readability.ts / comments.ts / pipeline.ts 충실 포팅.

전략: FETCH_FIRST = HTTP(requests)+readability 우선, 실패 시 Playwright 폴백.
PLAYWRIGHT_FIRST = Playwright 우선, 실패 시 HTTP 폴백. Playwright 미설치면
모두 HTTP만 사용한다(폴백 없음). 네이버 블로그/카페는 모바일 URL로 변환해
로그인/iframe 없이 본문에 접근한다. 한글 레거시 인코딩(cp949) 자동 복원.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from readability import Document

FETCH_TIMEOUT_S = 15
MIN_CONTENT_LENGTH = 50
MAX_CONTENT_PER_DOC = 2000
MAX_COMMENTS_PER_DOC = 1000

_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)

# 사이트별 댓글 CSS 선택자 (comments.ts 그대로).
_COMMENT_SELECTORS: dict[str, list[str]] = {
    "dc_inside": [".reply_body .usertxt", ".comment_box .usertxt"],
    "theqoo": [".comment-content", ".xe_content .comment"],
    "ruliweb": [".comment_view .text_wrapper", ".comment_content"],
    "ppomppu": [".han_comm_content", ".comment_content"],
    "clien": [".comment_view .comment_content", ".reply_content"],
    "fm_korea": [".comment-content", ".xe_content .comment", ".fdb_lst_ul .xe_content"],
    "inven": [".comment-item .content", ".commentContent"],
    "todayhumor": [".comment_content", ".memo_content"],
    "ilbe": [".comment-content", ".cmt_content"],
    "bobaedream": [".comment_content", ".cmtContent"],
    "humoruniv": [".comment_content", ".re_body"],
    "nate_pann": [".comment-content", ".usertxt"],
    "nv_blog": [".u_cbox_comment_box .u_cbox_contents", ".comment_area .text"],
    "nv_cafe": [".comment_content", ".u_cbox_contents"],
    "nv_kin": [".answer_area .se_textarea", ".answer-content"],
}
_GENERIC_SELECTORS = (
    ".comment-content", ".comment_content", ".comments .content",
    ".comment-body", ".comment-text",
    '[class*="comment"] [class*="content"]',
    '[class*="comment"] [class*="text"]',
    '[class*="reply"] [class*="content"]',
)


@dataclass
class FetchResult:
    title: str = ""
    content: str = ""
    content_length: int = 0
    comments: str = ""
    comment_count: int = 0
    fetched_via: str | None = None     # "http" | "playwright"
    fail_reason: str | None = None     # BLOCKED_403 / TIMEOUT / NETWORK / PARSE_FAIL / ...

    @property
    def ok(self) -> bool:
        return self.fail_reason is None and self.content_length >= MIN_CONTENT_LENGTH


def classify_http_status(status: int) -> str | None:
    if 200 <= status < 300:
        return None
    if status == 403:
        return "BLOCKED_403"
    if status == 429:
        return "RATE_LIMIT_429"
    if status == 408:
        return "TIMEOUT"
    if status >= 500:
        return "NETWORK"
    return "UNKNOWN"


def _to_mobile(url: str) -> str:
    """네이버 블로그/카페 → 모바일 호스트(로그인/iframe 회피)."""
    try:
        p = urlparse(url)
        host = {"blog.naver.com": "m.blog.naver.com",
                "cafe.naver.com": "m.cafe.naver.com"}.get(p.netloc)
        if host:
            return urlunparse(p._replace(netloc=host))
    except Exception:  # noqa: BLE001
        pass
    return url


def _decode(content: bytes, declared: str | None) -> str:
    """선언된 charset 우선. utf-8로 깨지면(U+FFFD 다수) cp949로 복원.

    utf-8 strict 디코드가 성공하면 그대로, 실패하면 cp949 strict를 시도한다.
    둘 다 실패하면 깨짐이 더 적은 쪽을 errors='replace'로 반환한다.
    """
    if declared and declared.lower() not in ("utf-8", "utf8"):
        try:
            return content.decode(declared)
        except (LookupError, ValueError):
            pass
    # 1) utf-8 strict 성공이면 채택
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # 2) cp949(euc-kr 상위호환) strict 성공이면 채택 (한글 레거시 페이지)
    try:
        return content.decode("cp949")
    except UnicodeDecodeError:
        pass
    # 3) 둘 다 실패 → 깨짐 적은 쪽
    utf = content.decode("utf-8", errors="replace")
    cp = content.decode("cp949", errors="replace")
    return cp if cp.count("�") < utf.count("�") else utf


def extract_comments(html: str, source_policy_id: str) -> tuple[str, int]:
    """본문 HTML에서 사이트별/일반 선택자로 댓글 텍스트 수집."""
    soup = BeautifulSoup(html, "lxml")
    selector_sets = [_COMMENT_SELECTORS.get(source_policy_id, [])] if source_policy_id in _COMMENT_SELECTORS else []
    selector_sets.append(list(_GENERIC_SELECTORS))
    for selectors in selector_sets:
        for sel in selectors:
            try:
                els = soup.select(sel)
            except Exception:  # noqa: BLE001 — 잘못된 선택자 방어
                continue
            if els:
                texts = [e.get_text(strip=True) for e in els]
                texts = [t for t in texts if t][:MAX_COMMENTS_PER_DOC]
                if texts:
                    return "\n".join(texts), len(texts)
    return "", 0


def _fetch_http(url: str, source_policy_id: str) -> FetchResult:
    fetch_url = _to_mobile(url)
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        resp = requests.get(fetch_url, headers=headers, timeout=FETCH_TIMEOUT_S,
                            allow_redirects=True)
    except requests.Timeout:
        return FetchResult(fail_reason="TIMEOUT")
    except requests.RequestException:
        return FetchResult(fail_reason="NETWORK")

    fail = classify_http_status(resp.status_code)
    if fail:
        return FetchResult(fail_reason=fail)

    declared = None
    ctype = resp.headers.get("content-type", "")
    m = re.search(r"charset=([^\s;]+)", ctype, re.IGNORECASE)
    if m:
        declared = m.group(1).strip()
    html = _decode(resp.content, declared)

    try:
        doc = Document(html)
        title = (doc.short_title() or "").strip()
        summary_html = doc.summary(html_partial=True)
        text = BeautifulSoup(summary_html, "lxml").get_text("\n", strip=True)
    except Exception:  # noqa: BLE001
        return FetchResult(fail_reason="PARSE_FAIL", title="")

    text = text.strip()
    comments, ccount = extract_comments(html, source_policy_id)
    if len(text) < MIN_CONTENT_LENGTH:
        return FetchResult(title=title, content=text, content_length=len(text),
                          comments=comments, comment_count=ccount,
                          fail_reason="PARSE_FAIL")
    return FetchResult(
        title=title, content=text[:MAX_CONTENT_PER_DOC], content_length=len(text),
        comments=comments, comment_count=ccount, fetched_via="http",
    )


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _fetch_playwright(url: str, source_policy_id: str) -> FetchResult:
    """Playwright 설치 시에만. 미설치면 NETWORK로 처리(폴백 유도)."""
    if not playwright_available():
        return FetchResult(fail_reason="NETWORK")
    try:
        from playwright.sync_api import sync_playwright
        fetch_url = _to_mobile(url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=random.choice(_USER_AGENTS),
                                    locale="ko-KR")
            try:
                page.goto(fetch_url, timeout=FETCH_TIMEOUT_S * 1000,
                          wait_until="domcontentloaded")
                html = page.content()
            finally:
                browser.close()
    except Exception:  # noqa: BLE001
        return FetchResult(fail_reason="NETWORK")

    try:
        doc = Document(html)
        title = (doc.short_title() or "").strip()
        text = BeautifulSoup(doc.summary(html_partial=True), "lxml").get_text("\n", strip=True).strip()
    except Exception:  # noqa: BLE001
        return FetchResult(fail_reason="PARSE_FAIL")
    comments, ccount = extract_comments(html, source_policy_id)
    if len(text) < MIN_CONTENT_LENGTH:
        return FetchResult(title=title, content=text, content_length=len(text),
                          comments=comments, comment_count=ccount, fail_reason="PARSE_FAIL")
    return FetchResult(title=title, content=text[:MAX_CONTENT_PER_DOC],
                      content_length=len(text), comments=comments,
                      comment_count=ccount, fetched_via="playwright")


def fetch_document(url: str, source_policy_id: str, fetch_mode: str) -> FetchResult:
    """pipeline.ts executeFetchPipeline 포팅: 1차 전략 → 실패 시 폴백."""
    if fetch_mode == "PLAYWRIGHT_FIRST" and playwright_available():
        result = _fetch_playwright(url, source_policy_id)
        if result.ok:
            return result
        http = _fetch_http(url, source_policy_id)
        return http if http.ok else result
    # FETCH_FIRST (또는 Playwright 미설치)
    result = _fetch_http(url, source_policy_id)
    if result.ok:
        return result
    if playwright_available():
        pw = _fetch_playwright(url, source_policy_id)
        if pw.ok:
            return pw
    return result
