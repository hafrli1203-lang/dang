"""Build script — PyInstaller 패키징.

Usage:
    python build.py              # --onedir (기본, 빠른 빌드)
    python build.py --onefile    # 단일 .exe 파일 (느리지만 배포 간편)
    python build.py --clean      # 캐시 초기화 후 빌드

Output:
    dist/당근광고도우미/         (onedir 모드)
    dist/당근광고도우미.exe      (onefile 모드)
"""
import os
import subprocess
import sys
import shutil
from pathlib import Path

APP_NAME = "당근광고도우미"
MAIN_SCRIPT = "main.py"
ICON_FILE = "app_icon.ico"  # 있으면 사용, 없으면 생략

# 프로젝트 루트 기준
ROOT = Path(__file__).parent.resolve()


def build(onefile: bool = False, clean: bool = False) -> None:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--windowed",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if clean:
        cmd.append("--clean")

    # Icon (optional)
    icon_path = ROOT / ICON_FILE
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    # ── Data files ──────────────────────────────────────────────────────
    # Templates (DOCX 기준 템플릿)
    cmd.extend(["--add-data", f"{ROOT / 'templates'}{os.pathsep}templates"])
    # .env.example (사용자가 .env로 복사)
    cmd.extend(["--add-data", f"{ROOT / '.env.example'}{os.pathsep}."])
    # 교재 지식(정제본 + 운영 플레이북 + raw 원문) — domain_knowledge가 frozen에서도 읽도록
    cmd.extend(["--add-data", f"{ROOT / 'app' / 'knowledge'}{os.pathsep}app/knowledge"])

    # ── Collect packages with data files ────────────────────────────────
    cmd.extend(["--collect-all", "nicegui"])
    cmd.extend(["--collect-data", "matplotlib"])
    cmd.extend(["--collect-data", "docx"])
    cmd.extend(["--collect-data", "pptx"])

    # ── Hidden imports ──────────────────────────────────────────────────
    hidden = [
        "anthropic",
        "openai",
        "openpyxl",
        "dotenv",
        "pptx",
        "platformdirs",
        "app.paths",
        "app.pages.project",
        "app.pages.planning",
        "app.pages.report",
        "app.ai.providers",
        "app.reporting.docx_report",
        "app.reporting.slides_html",
        "app.reporting.slides_pptx",
    ]
    for h in hidden:
        cmd.extend(["--hidden-import", h])

    # ── Main script ─────────────────────────────────────────────────────
    cmd.append(str(ROOT / MAIN_SCRIPT))

    print(f"\n{'='*60}")
    print(f"Building {APP_NAME} ({'onefile' if onefile else 'onedir'} mode)")
    print(f"{'='*60}")
    print("Command:", " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        if onefile:
            exe_path = ROOT / "dist" / f"{APP_NAME}.exe"
        else:
            exe_path = ROOT / "dist" / APP_NAME
        print(f"\n{'='*60}")
        print(f"Build SUCCESS!")
        print(f"Output: {exe_path}")
        print(f"{'='*60}")
    else:
        print(f"\nBuild FAILED (exit code {result.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    onefile = "--onefile" in args
    clean = "--clean" in args
    build(onefile=onefile, clean=clean)
