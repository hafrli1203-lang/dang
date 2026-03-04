"""Native OS dialogs — pywebview 기반 Save-As / 폴더 열기.

pywebview가 없거나 NiceGUI native 모드가 아닌 경우 모든 함수가
안전하게 None/False를 반환한다. 앱이 죽지 않도록 전체 try/except 처리.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path


def is_native_available() -> bool:
    """pywebview가 import 가능하고 NiceGUI native 모드인지 확인."""
    try:
        import webview  # noqa: F401
        return getattr(sys, "_nicegui_native", False)
    except Exception:
        return False


async def ask_save_path(
    suggested_filename: str,
    file_types: list[tuple[str, str]] | None = None,
) -> Path | None:
    """Native Save-As 다이얼로그.

    Parameters
    ----------
    suggested_filename : str
        기본 파일명 (예: "기획서_맛집.docx")
    file_types : list[tuple[str, str]] | None
        파일 유형 필터. 기본값 [("Word", "*.docx")].
        각 튜플은 (설명, 패턴) — pywebview 형식으로 변환됨.

    Returns
    -------
    Path | None
        선택된 경로. 취소하거나 native 모드가 아니면 None.
    """
    if not is_native_available():
        return None

    if file_types is None:
        file_types = [("Word", "*.docx")]

    try:
        import webview
        from nicegui import app as nicegui_app

        # pywebview file_types: tuple of "Description (*.ext)" strings
        wv_types = tuple(f"{desc} ({pat})" for desc, pat in file_types)

        window = nicegui_app.native.main_window
        result = await window.create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            file_types=wv_types,
            save_filename=suggested_filename,
        )
    except Exception:
        return None

    if not result:
        return None

    chosen = result[0] if isinstance(result, (list, tuple)) else result
    if not chosen:
        return None

    path = Path(str(chosen))

    # 첫 번째 file_type의 확장자를 기본 확장자로 보장
    if file_types:
        # "*.docx" → ".docx"
        default_ext = file_types[0][1].lstrip("*")
        if default_ext and path.suffix.lower() != default_ext.lower():
            path = path.with_suffix(default_ext)

    return path


def open_folder(path: Path) -> None:
    """OS 기본 파일 탐색기로 폴더(또는 파일의 부모 폴더) 열기.

    path가 파일이면 부모 폴더를 연다. 실패해도 예외를 발생시키지 않는다.
    """
    try:
        target = path if path.is_dir() else path.parent

        system = platform.system()
        if system == "Windows":
            os.startfile(str(target))
        elif system == "Darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except Exception:
        pass
