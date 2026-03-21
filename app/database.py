"""SQLite database layer for daangn_ad_reporter."""
import csv
import io
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from app.paths import get_db_path, APP_DIR

_log = logging.getLogger("daangn.database")

_db_path = get_db_path()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_legacy_db() -> None:
    """APP_DIR 내 레거시 DB를 DATA_DIR로 1회 마이그레이션.

    - DATA_DIR에 DB가 없으면: 단순 복사
    - DATA_DIR에 이미 있으면: 레거시 파일을 .bak으로 이름 변경 (충돌 방지)
    """
    legacy = APP_DIR / "daangn_ads.db"
    if not legacy.exists() or legacy == _db_path:
        return
    if not _db_path.exists():
        shutil.copy2(legacy, _db_path)
        _log.info("레거시 DB 마이그레이션: %s → %s", legacy, _db_path)
    else:
        bak = legacy.with_suffix(".db.bak")
        if not bak.exists():
            legacy.rename(bak)
            _log.info("레거시 DB 백업: %s → %s (DATA_DIR에 이미 존재)", legacy, bak)


def init_db() -> None:
    _migrate_legacy_db()
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                industry      TEXT DEFAULT '',
                region        TEXT DEFAULT '',
                goal          TEXT DEFAULT '',
                budget        TEXT DEFAULT '',
                period        TEXT DEFAULT '',
                benefits      TEXT DEFAULT '',
                reference_url TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS generated_content (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id   INTEGER NOT NULL,
                engine       TEXT NOT NULL,
                content      TEXT NOT NULL,
                content_type TEXT DEFAULT 'planning',
                created_at   TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS performance_rows (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id   INTEGER NOT NULL,
                period_label TEXT DEFAULT '',
                cost         INTEGER DEFAULT 0,
                impressions  INTEGER DEFAULT 0,
                clicks       INTEGER DEFAULT 0,
                inquiries    INTEGER DEFAULT 0,
                regulars     INTEGER DEFAULT 0,
                coupons      INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS report_content (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                engine     TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        # Migration for existing DBs: add content_type column if missing
        try:
            conn.execute("ALTER TABLE generated_content ADD COLUMN content_type TEXT DEFAULT 'planning'")
        except sqlite3.OperationalError:
            pass  # column already exists


# ── Projects ────────────────────────────────────────────────────────────────

def save_project(data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO projects
               (name, industry, region, goal, budget, period, benefits, reference_url)
               VALUES (:name,:industry,:region,:goal,:budget,:period,:benefits,:reference_url)""",
            data,
        )
        return cur.lastrowid


def update_project(project_id: int, data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE projects SET name=:name, industry=:industry, region=:region,
               goal=:goal, budget=:budget, period=:period, benefits=:benefits,
               reference_url=:reference_url WHERE id=:id""",
            {**data, "id": project_id},
        )


def get_projects() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_project(project_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))


# ── Generated Content ────────────────────────────────────────────────────────

def save_generated_content(
    project_id: int, engine: str, content: str, content_type: str = "planning"
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO generated_content (project_id, engine, content, content_type) VALUES (?,?,?,?)",
            (project_id, engine, content, content_type),
        )
        return cur.lastrowid


def get_latest_content(
    project_id: int, content_type: str = "planning"
) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM generated_content WHERE project_id=? AND content_type=?
               ORDER BY created_at DESC LIMIT 1""",
            (project_id, content_type),
        ).fetchone()
        return dict(row) if row else None


# ── Performance Rows ─────────────────────────────────────────────────────────

def save_performance_rows(project_id: int, rows: List[Dict]) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM performance_rows WHERE project_id=?", (project_id,)
        )
        conn.executemany(
            """INSERT INTO performance_rows
               (project_id, period_label, cost, impressions, clicks, inquiries, regulars, coupons)
               VALUES (:project_id,:period_label,:cost,:impressions,:clicks,:inquiries,:regulars,:coupons)""",
            [{**r, "project_id": project_id} for r in rows],
        )


def get_performance_rows(project_id: int) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM performance_rows WHERE project_id=? ORDER BY id",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Report Content ───────────────────────────────────────────────────────────

def save_report_content(project_id: int, engine: str, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO report_content (project_id, engine, content) VALUES (?,?,?)",
            (project_id, engine, content),
        )
        return cur.lastrowid


def get_latest_report(project_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM report_content WHERE project_id=?
               ORDER BY created_at DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None


# ── App Settings ───────────────────────────────────────────────────────────

def get_setting(key: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None


def save_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value),
        )


def delete_setting(key: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM app_settings WHERE key=?", (key,))


# ── Export / Backup ─────────────────────────────────────────────────────────

def export_projects_csv() -> bytes:
    """Export all projects as UTF-8 CSV bytes."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, industry, region, goal, budget, period, benefits, reference_url, created_at FROM projects ORDER BY id"
        ).fetchall()
    writer.writerow(["id", "광고주명", "업종", "지역", "목표", "예산", "기간", "혜택", "참고링크", "생성일"])
    for r in rows:
        writer.writerow(list(r))
    return buf.getvalue().encode("utf-8-sig")


def export_performance_csv(project_id: int | None = None) -> bytes:
    """Export performance rows as UTF-8 CSV bytes. If project_id is None, export all."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    with get_conn() as conn:
        if project_id:
            rows = conn.execute(
                """SELECT pr.project_id, p.name, pr.period_label, pr.cost,
                          pr.impressions, pr.clicks, pr.inquiries, pr.regulars, pr.coupons
                   FROM performance_rows pr JOIN projects p ON p.id = pr.project_id
                   WHERE pr.project_id=? ORDER BY pr.id""",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT pr.project_id, p.name, pr.period_label, pr.cost,
                          pr.impressions, pr.clicks, pr.inquiries, pr.regulars, pr.coupons
                   FROM performance_rows pr JOIN projects p ON p.id = pr.project_id
                   ORDER BY pr.project_id, pr.id"""
            ).fetchall()
    writer.writerow(["프로젝트ID", "광고주명", "기간", "비용", "노출", "클릭", "문의", "단골", "쿠폰"])
    for r in rows:
        writer.writerow(list(r))
    return buf.getvalue().encode("utf-8-sig")


def backup_db(dest_dir: Path | None = None) -> Path:
    """Copy the DB file to dest_dir (or same dir) with timestamp suffix."""
    dest_dir = dest_dir or _db_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"daangn_ads_backup_{ts}.db"
    shutil.copy2(_db_path, dest)
    return dest
