"""Entry point — 당근 광고 기획 도우미."""
import os
import sys

__version__ = "1.2.0"

# ── Centralized paths (platformdirs-based) ────────────────────────────────────
from app.paths import IS_FROZEN, BUNDLE_DIR, APP_DIR, DATA_DIR, STORAGE_DIR, get_env_path, migrate_legacy_files, ensure_dirs

# ── Ensure all data directories exist before anything else ────────────────────
ensure_dirs()

# ── Load .env ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv

_env = get_env_path()
if _env:
    load_dotenv(_env)

migrate_legacy_files()

# ── NiceGUI storage path (must be set before nicegui import) ──────────────────
os.environ.setdefault("NICEGUI_STORAGE_PATH", str(STORAGE_DIR))

# ── Init DB ───────────────────────────────────────────────────────────────────
from app.database import init_db

init_db()

# ── Register pages (side-effect of import) ────────────────────────────────────
import app.pages.project   # noqa: F401
import app.pages.planning  # noqa: F401
import app.pages.report    # noqa: F401
import app.pages.thumbnail  # noqa: F401
import app.pages.analysis  # noqa: F401

# ── Run ───────────────────────────────────────────────────────────────────────
from nicegui import ui, app as nicegui_app

# ── Static files (fonts, images) ──────────────────────────────────────────────
_static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
if os.path.isdir(_static_dir):
    nicegui_app.add_static_files("/static", _static_dir)

storage_secret = os.getenv("STORAGE_SECRET", "daangn-reporter-default-secret")


# ── Startup update check (background, non-blocking) ──────────────────────────
@nicegui_app.on_startup
async def _startup_update_check() -> None:
    """Check for updates in a background thread at startup."""
    import asyncio
    from app.updater import check_for_update, show_update_notification

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, check_for_update, __version__)
    if info:
        show_update_notification(ui, info)


if __name__ in ("__main__", "__mp_main__"):
    # Try native desktop window; fall back to browser if pywebview is unavailable.
    native_available = False
    try:
        import webview  # noqa: F401
        native_available = True
    except ImportError:
        pass

    if native_available:
        try:
            sys._nicegui_native = True
            nicegui_app.native.settings['ALLOW_DOWNLOADS'] = True
            ui.run(
                native=True,
                title="당근 광고 기획 도우미",
                window_size=(1320, 900),
                storage_secret=storage_secret,
                reload=False,
            )
        except Exception as native_err:
            native_available = False
            print(f"\n[경고] 데스크톱 창 실패: {native_err}", file=sys.stderr)

    if not native_available:
        import socket

        def _pick_free_port(preferred: int = 8000, max_tries: int = 10) -> int:
            """127.0.0.1 기준으로 비어 있는 포트를 찾는다.

            다른 앱(예: 다른 프로젝트의 uvicorn)이 127.0.0.1:8000을 선점하면
            0.0.0.0 바인딩은 성공해도 localhost 접속이 그 앱으로 가버린다.
            그래서 127.0.0.1에 직접 바인딩해 보고 실패하면 다음 포트를 쓴다.
            """
            for port in range(preferred, preferred + max_tries):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    try:
                        s.bind(("127.0.0.1", port))
                    except OSError:
                        continue
                return port
            return preferred

        _port = _pick_free_port(8000)
        if _port != 8000:
            print(f"\n[안내] 8000 포트를 다른 프로그램이 사용 중이라 {_port} 포트로 실행합니다.", file=sys.stderr)
        print("\n[안내] 브라우저 모드로 실행합니다.", file=sys.stderr)
        print(f"브라우저에서  http://localhost:{_port}  을 열어주세요.\n", file=sys.stderr)
        ui.run(
            native=False,
            port=_port,
            show=True,
            title="당근 광고 기획 도우미",
            storage_secret=storage_secret,
            reload=False,
        )
