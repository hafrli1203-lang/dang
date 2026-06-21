"""ExportManager 파일명 sanitize 회귀 잠금.

매장/캠페인명(사용자 자유 입력)이 파일명에 들어가므로, 경로 금지문자가
하위폴더로 흩어지거나(OSError 없이 조용히) 저장 실패하지 않도록 경계에서
sanitize_filename을 적용한다. (QS-6)
"""
import asyncio
from unittest.mock import MagicMock

import app.export_manager as em
from app.export_manager import ExportManager


def _mock_ui(monkeypatch):
    """save_default가 쓰는 ui.dialog/ui.download/ui.notify를 무력화(헤드리스)."""
    monkeypatch.setattr(em, "ui", MagicMock())
    # native 모드로 간주해 브라우저 download 분기를 타지 않게 한다.
    monkeypatch.setattr(em, "is_native_available", lambda: True)


def test_save_default_sanitizes_slash(tmp_path, monkeypatch):
    """파일명에 '/'가 있어도 하위폴더가 아닌 평탄 경로에 저장된다."""
    _mock_ui(monkeypatch)
    ExportManager.save_default(b"x", "성과보고서_6월/신규.docx", dest_dir=tmp_path)

    expected = tmp_path / "성과보고서_6월신규.docx"
    assert expected.exists(), f"sanitize된 평탄 경로에 저장돼야 함: {list(tmp_path.iterdir())}"
    assert expected.read_bytes() == b"x"
    # '/'가 하위폴더로 새지 않았는지: 디렉터리가 생기면 안 됨
    assert not (tmp_path / "성과보고서_6월").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["성과보고서_6월신규.docx"]


def test_save_default_blocks_windows_illegal_chars(tmp_path, monkeypatch):
    """Windows 금지문자(: * ? " < > |)가 제거된다."""
    _mock_ui(monkeypatch)
    ExportManager.save_default(b"y", '제안서_A:B*C?.docx', dest_dir=tmp_path)
    assert (tmp_path / "제안서_ABC.docx").exists()


def test_save_default_idempotent_on_clean_name(tmp_path, monkeypatch):
    """이미 깨끗한 이름은 그대로(멱등) — 슬라이드/썸네일 호출 무영향 보장."""
    _mock_ui(monkeypatch)
    ExportManager.save_default(b"z", "report_2026.docx", dest_dir=tmp_path)
    assert (tmp_path / "report_2026.docx").exists()


def test_save_default_empty_after_sanitize_falls_back(tmp_path, monkeypatch):
    """금지문자뿐이면 'unnamed'으로 폴백(저장 실패 방지)."""
    _mock_ui(monkeypatch)
    ExportManager.save_default(b"w", '???', dest_dir=tmp_path)
    assert (tmp_path / "unnamed").exists()


def test_save_as_sanitizes_suggested_name(tmp_path, monkeypatch):
    """save_as가 다이얼로그에 넘기는 추천 파일명도 sanitize된다."""
    _mock_ui(monkeypatch)
    captured = {}

    async def fake_ask_save_path(filename):
        captured["filename"] = filename
        target = tmp_path / filename
        return target

    monkeypatch.setattr(em, "ask_save_path", fake_ask_save_path)
    ok = asyncio.run(ExportManager.save_as(b"d", "기획서_매장/이름.docx"))
    assert ok is True
    assert captured["filename"] == "기획서_매장이름.docx"
    assert (tmp_path / "기획서_매장이름.docx").exists()


def test_save_as_multi_sanitizes_each(tmp_path, monkeypatch):
    """복수 저장에서도 각 파일명이 sanitize된다(native 경로)."""
    _mock_ui(monkeypatch)
    seen = []

    async def fake_ask_save_path(filename):
        seen.append(filename)
        return tmp_path / filename

    monkeypatch.setattr(em, "ask_save_path", fake_ask_save_path)
    pairs = [(b"a", "성과보고서_X/1.docx"), (b"b", "성과보고서_Y*2.docx")]
    ok = asyncio.run(ExportManager.save_as_multi(pairs))
    assert ok is True
    assert seen == ["성과보고서_X1.docx", "성과보고서_Y2.docx"]
    assert (tmp_path / "성과보고서_X1.docx").exists()
    assert (tmp_path / "성과보고서_Y2.docx").exists()
