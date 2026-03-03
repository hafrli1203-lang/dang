"""SQLite database layer for daangn_ad_reporter."""
import csv
import io
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from app.paths import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
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
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                engine     TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
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
        """)


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

def save_generated_content(project_id: int, engine: str, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO generated_content (project_id, engine, content) VALUES (?,?,?)",
            (project_id, engine, content),
        )
        return cur.lastrowid


def get_latest_content(project_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM generated_content WHERE project_id=?
               ORDER BY created_at DESC LIMIT 1""",
            (project_id,),
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
    dest_dir = dest_dir or DB_PATH.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"daangn_ads_backup_{ts}.db"
    shutil.copy2(DB_PATH, dest)
    return dest
