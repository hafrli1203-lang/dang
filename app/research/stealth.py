# -*- coding: utf-8 -*-
"""Playwright stealth 헬퍼 — browser/stealth.ts 포팅.

playwright-extra/StealthPlugin은 파이썬에 없으므로, 동등한 효과를 위해
--disable-blink-features=AutomationControlled + navigator.webdriver 제거
init script로 자동화 탐지를 줄인다. Playwright 미설치면 PlaywrightMissing.
"""
from __future__ import annotations

import random

_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
)
_VIEWPORTS = (
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
)

# navigator.webdriver 등 자동화 흔적 제거 (StealthPlugin의 핵심 효과 일부).
_STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""


class PlaywrightMissing(Exception):
    """Playwright 미설치 — 광고 관측은 브라우저 자동화가 필수."""


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _apply_playwright_stealth(context) -> bool:
    """playwright-stealth(있으면)를 컨텍스트에 적용. 성공 시 True.

    한국어 로케일 유지(navigator.languages = ko-KR). 미설치/실패 시 False →
    호출부가 기본 init script로 폴백한다.
    """
    try:
        from playwright_stealth import Stealth
    except ImportError:
        return False
    try:
        Stealth(navigator_languages_override=("ko-KR", "ko")).apply_stealth_sync(context)
        return True
    except Exception:  # noqa: BLE001
        return False


def stealth_context_options() -> dict:
    """stealthContextOptions() 포팅."""
    return {
        "user_agent": random.choice(_USER_AGENTS),
        "viewport": random.choice(_VIEWPORTS),
        "locale": "ko-KR",
        "timezone_id": "Asia/Seoul",
        "extra_http_headers": {
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }


def random_delay_seconds(min_ms: int, max_ms: int) -> float:
    return (random.randint(min_ms, max_ms)) / 1000.0


class StealthBrowser:
    """sync Playwright 브라우저 컨텍스트 매니저. 광고 관측 전용(블로킹).

    with StealthBrowser() as ctx:
        page = ctx.new_page(); ...
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self):
        if not playwright_available():
            raise PlaywrightMissing()
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(**stealth_context_options())
        # playwright-stealth가 있으면 강력한 봇 우회(navigator/webgl/chrome 등) 적용,
        # 없으면 기본 init script로 폴백. (네이버는 폴백으로도 충분, 메타는 stealth 필요.)
        if not _apply_playwright_stealth(self._context):
            self._context.add_init_script(_STEALTH_INIT_JS)
        return self._context

    def __exit__(self, *exc):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()
        return False
