"""Centralized path resolution for daangn_ad_reporter."""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir

IS_FROZEN = getattr(sys, "frozen", False)
BUNDLE_DIR = Path(sys._MEIPASS) if IS_FROZEN else Path(__file__).resolve().parent.parent
APP_DIR = Path(sys.executable).parent.resolve() if IS_FROZEN else BUNDLE_DIR

DATA_DIR = Path(user_data_dir("daangn_ad_reporter", appauthor=False, ensure_exists=True))
DB_PATH = DATA_DIR / "daangn_ads.db"
LOG_PATH = DATA_DIR / "app.log"
EXPORTS_DIR = DATA_DIR / "exports"
CHARTS_DIR = DATA_DIR / "charts"
STORAGE_DIR = DATA_DIR / "storage"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"

for _d in (EXPORTS_DIR, CHARTS_DIR, STORAGE_DIR, THUMBNAILS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Windows 금지 문자 + 제어 문자 패턴
_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)


# ── 기존 유틸 함수 ─────────────────────────────────────────────────────


def get_env_path() -> Path | None:
    """Return the first .env file found: DATA_DIR first, then APP_DIR."""
    for candidate in (DATA_DIR / ".env", APP_DIR / ".env"):
        if candidate.exists():
            return candidate
    return None


def migrate_legacy_files() -> list[str]:
    """APP_DIR -> DATA_DIR 1회 복사. 기존 DATA_DIR 파일 절대 덮어쓰지 않음."""
    import shutil
    import logging

    log = logging.getLogger("daangn.paths")
    migrated: list[str] = []
    for filename, desc in [("daangn_ads.db", "DB"), (".env", "환경설정")]:
        src, dst = APP_DIR / filename, DATA_DIR / filename
        if src.exists() and not dst.exists() and src != dst:
            shutil.copy2(src, dst)
            log.info("마이그레이션: %s → %s", src, dst)
            migrated.append(f"{desc}: {src} → {dst}")
    return migrated


# ── 신규 경로 헬퍼 ─────────────────────────────────────────────────────


def get_app_root() -> Path:
    """앱 데이터 루트 (= DATA_DIR). Windows: %LOCALAPPDATA%/daangn_ad_reporter"""
    return DATA_DIR


def get_db_path() -> Path:
    """SQLite DB 경로."""
    return DB_PATH


def get_exports_dir() -> Path:
    """내보내기 기본 폴더."""
    return EXPORTS_DIR


def get_run_dir(project_name: str, yyyymm: str | None = None) -> Path:
    """프로젝트별 실행 결과 폴더.

    구조: EXPORTS_DIR / <sanitized_project_name> / <YYYYMM>
    yyyymm이 None이면 오늘 기준 자동 생성.
    """
    safe_name = sanitize_filename(project_name) or "unnamed"
    month = yyyymm or datetime.now().strftime("%Y%m")
    run_dir = EXPORTS_DIR / safe_name / month
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def ensure_dirs() -> None:
    """모든 주요 디렉터리가 존재하는지 확인하고 없으면 생성."""
    for d in (DATA_DIR, EXPORTS_DIR, CHARTS_DIR, STORAGE_DIR, THUMBNAILS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Windows 파일명 금지 문자 및 예약어를 제거/치환.

    - <, >, :, ", /, \\, |, ?, *, 제어 문자 → 제거
    - 예약 이름(CON, PRN, AUX, NUL, COM1~9, LPT1~9) → 접미사 "_" 추가
    - 앞뒤 공백/점 제거
    - 빈 문자열이면 "unnamed" 반환
    """
    cleaned = _UNSAFE_RE.sub("", name).strip().strip(".")
    if cleaned.upper() in _RESERVED_NAMES:
        cleaned = cleaned + "_"
    return cleaned or "unnamed"
