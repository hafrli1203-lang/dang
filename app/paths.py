"""Centralized path resolution for daangn_ad_reporter."""
import os
import sys
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

for _d in (EXPORTS_DIR, CHARTS_DIR, STORAGE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


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
