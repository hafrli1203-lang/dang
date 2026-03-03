"""Lightweight auto-update checker — GitHub Releases 기반.

사용법:
    from app.updater import check_for_update

    info = check_for_update()
    if info:
        print(f"새 버전 {info['version']} 사용 가능: {info['url']}")

동작:
    1. GitHub API로 latest release 조회 (tag_name → 버전)
    2. 현재 __version__ 과 비교
    3. 더 높으면 {'version', 'url', 'notes'} 반환, 아니면 None
    4. 네트워크 오류 시 조용히 None 반환 (앱 실행에 영향 없음)
"""
from __future__ import annotations

from typing import Optional

from app.logger import get_logger

_log = get_logger("updater")

# ── Configuration ─────────────────────────────────────────────────────────────
# GitHub 저장소를 설정하세요. 예: "your-org/daangn-ad-reporter"
GITHUB_REPO = "hafrli1203-lang/dang"
CHECK_TIMEOUT = 5  # seconds


def _parse_version(v: str) -> tuple:
    """'v1.2.3' or '1.2.3' → (1, 2, 3)."""
    v = v.lstrip("vV").strip()
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) or (0,)


def check_for_update(current_version: str | None = None) -> Optional[dict]:
    """Check GitHub Releases for a newer version.

    Returns:
        dict with keys {version, url, notes} if a newer version exists.
        None if up-to-date, repo not configured, or network error.
    """
    if not GITHUB_REPO:
        return None

    if current_version is None:
        try:
            from main import __version__
            current_version = __version__
        except (ImportError, AttributeError):
            current_version = "0.0.0"

    try:
        import urllib.request
        import json

        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "DaangnAdReporter-Updater",
            },
        )
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        remote_tag = data.get("tag_name", "")
        if not remote_tag:
            return None

        remote_ver = _parse_version(remote_tag)
        local_ver = _parse_version(current_version)

        if remote_ver > local_ver:
            return {
                "version": remote_tag.lstrip("vV"),
                "url": data.get("html_url", ""),
                "notes": data.get("body", "")[:500],
            }
        return None

    except Exception as exc:
        _log.debug("Update check failed (non-critical): %s", exc)
        return None


def show_update_notification(ui_module, update_info: dict) -> None:
    """NiceGUI 알림으로 업데이트 안내 표시.

    Args:
        ui_module: nicegui.ui 모듈
        update_info: check_for_update() 반환값
    """
    version = update_info["version"]
    url = update_info["url"]
    ui_module.notify(
        f"새 버전 {version} 이 있습니다! 업데이트를 확인하세요.",
        type="info",
        timeout=15000,
        close_button="닫기",
        actions=[{"label": "다운로드", "handler": lambda: ui_module.navigate.to(url, new_tab=True)}]
        if url else [],
    )
