"""Native Save-As dialog utility for DOCX export."""
import sys
from pathlib import Path


async def choose_save_folder() -> Path | None:
    """Native folder selection dialog. Returns None in browser mode or on cancel."""
    if not getattr(sys, "_nicegui_native", False):
        return None
    try:
        import webview
        from nicegui import app as nicegui_app

        result = await nicegui_app.native.main_window.create_file_dialog(
            dialog_type=webview.FOLDER_DIALOG,
        )
    except Exception:
        return None
    if not result:
        return None
    chosen = result[0] if isinstance(result, (list, tuple)) else result
    return Path(str(chosen)) if chosen else None


async def choose_save_path_docx(default_name: str) -> Path | None:
    """Open a native Save-As dialog and return the chosen Path, or None on cancel.

    Only works in NiceGUI native (pywebview) mode.  In browser mode returns None
    immediately so the caller can fall back to ``ui.download()``.
    """
    if not getattr(sys, "_nicegui_native", False):
        return None

    try:
        import webview
        from nicegui import app as nicegui_app

        window = nicegui_app.native.main_window
        result = await window.create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            file_types=("Word Document (*.docx)",),
            save_filename=default_name,
        )
    except Exception:
        return None

    if not result:
        return None

    # pywebview may return str, tuple, or list depending on platform/version.
    if isinstance(result, (list, tuple)):
        chosen = result[0] if result else None
    else:
        chosen = result

    if not chosen:
        return None

    path = Path(str(chosen))

    # Ensure .docx extension
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")

    return path
