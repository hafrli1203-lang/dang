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

# ── App favicon (브라우저 탭 + 네이티브 창 아이콘) ──────────────────────────────
# app_icon.ico는 빌드/인스톨러뿐 아니라 실행 중인 앱에도 favicon으로 배선한다.
_favicon_path = os.path.join(str(BUNDLE_DIR), "app_icon.ico")
_favicon = _favicon_path if os.path.isfile(_favicon_path) else None


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
                favicon=_favicon,
                window_size=(1320, 900),
                storage_secret=storage_secret,
                reload=False,
            )
        except Exception as native_err:
            native_available = False
            print(f"\n[경고] 데스크톱 창 실패: {native_err}", file=sys.stderr)

    if not native_available:
        import socket

        def _port_free(port: int) -> bool:
            """0.0.0.0 과 127.0.0.1 양쪽 모두 바인딩 가능할 때만 비어 있다고 본다.

            ui.run은 0.0.0.0에 바인딩하므로 0.0.0.0 점유자(다른 인스턴스)를 잡아야 하고,
            동시에 127.0.0.1만 선점한 앱(다른 uvicorn)이 localhost 접속을 가로채는 것도
            막아야 한다. 한쪽만 검사하면 둘 중 하나를 놓친다(과거 버그).
            """
            for host in ("0.0.0.0", "127.0.0.1"):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    try:
                        s.bind((host, port))
                    except OSError:
                        return False
            return True

        def _pick_free_port(preferred: int = 8080, max_tries: int = 10) -> int:
            """비어 있는 첫 포트를 찾는다 (양쪽 주소 모두 비어 있어야 함)."""
            for port in range(preferred, preferred + max_tries):
                if _port_free(port):
                    return port
            return preferred

        # 기본 포트 8080 고정 — DAANGN_PORT 환경변수로 덮어쓰기 가능. 점유 시에만 자동 대체.
        try:
            _preferred = int(os.getenv("DAANGN_PORT", "8080"))
        except ValueError:
            _preferred = 8080
        _port = _pick_free_port(_preferred)
        if _port != _preferred:
            print(f"\n[안내] {_preferred} 포트를 다른 프로그램이 사용 중이라 {_port} 포트로 실행합니다.", file=sys.stderr)
        print("\n[안내] 브라우저 모드로 실행합니다.", file=sys.stderr)
        print(f"브라우저에서  http://localhost:{_port}  을 열어주세요.\n", file=sys.stderr)
        ui.run(
            native=False,
            port=_port,
            show=True,
            title="당근 광고 기획 도우미",
            favicon=_favicon,
            storage_secret=storage_secret,
            reload=False,
        )
