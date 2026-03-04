"""Screen 3 – 성과 입력 + 보고서 생성."""
import asyncio
import io
from pathlib import Path
from typing import List, Dict

from nicegui import ui, app as nicegui_app

from app.common import create_nav, create_log_panel, create_path_info_panel
from app.export_manager import ExportManager
from app.paths import CHARTS_DIR
from app.database import (
    get_project,
    get_projects,
    get_performance_rows,
    save_performance_rows,
    get_latest_report,
    save_report_content,
)
from app.ai_engine import build_report_prompt, calc_kpi, SYSTEM_GUIDE_REPORT
from app.ai.providers import get_provider, ClaudeProvider, GeminiProvider
from app.reporting.docx_report import build_report_docx
from app.reporting.parsers import parse_daangn_csv
from app.chart_preview import make_charts  # chart preview only


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_int(val) -> int:
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


_EXPECTED_COLS = ("기간", "비용", "노출", "클릭", "문의", "단골", "쿠폰")


def _validate_excel_header(header_row: tuple) -> str | None:
    """헤더 행 검증. 문제가 있으면 경고 메시지 반환, 없으면 None."""
    if not header_row or len(header_row) < 7:
        return f"열이 7개 미만입니다 (발견: {len(header_row) if header_row else 0}개). 순서: 기간|비용|노출|클릭|문의|단골|쿠폰"
    # 핵심 열 이름 검증 (부분 매칭)
    h = [str(c or "").strip().replace("(원)", "").replace("(명)", "").replace("(건)", "").replace("(회)", "") for c in header_row[:7]]
    for idx, expected in enumerate(_EXPECTED_COLS):
        if expected not in h[idx]:
            return f"열 {idx+1} 이름이 '{h[idx]}'인데 '{expected}'이 포함되어야 합니다."
    return None


def _parse_excel(content: bytes) -> tuple[List[Dict], str | None]:
    """Parse uploaded Excel file. Returns (rows, warning_or_none).

    Expected columns (row 1 = header):
    기간 | 비용 | 노출 | 클릭 | 문의 | 단골 | 쿠폰
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    rows_out = []
    warning = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            warning = _validate_excel_header(row)
            continue  # skip header
        if not any(row):
            continue
        rows_out.append(
            {
                "period_label": str(row[0]) if row[0] is not None else f"기간{i}",
                "cost": _parse_int(row[1]),
                "impressions": _parse_int(row[2]),
                "clicks": _parse_int(row[3]),
                "inquiries": _parse_int(row[4]),
                "regulars": _parse_int(row[5] if len(row) > 5 else 0),
                "coupons": _parse_int(row[6] if len(row) > 6 else 0),
            }
        )
    return rows_out, warning


def _blank_row(idx: int) -> Dict:
    return {
        "period_label": f"기간{idx}",
        "cost": 0,
        "impressions": 0,
        "clicks": 0,
        "inquiries": 0,
        "regulars": 0,
        "coupons": 0,
    }


# ── docx_report bridge helpers ────────────────────────────────────────────────

def _rows_to_timeseries(rows: List[Dict]) -> List[Dict]:
    """Convert DB/legacy row format → TimeseriesRow (new field names)."""
    return [
        {
            "date": r.get("period_label", ""),
            "spend": r.get("cost", 0),
            "clicks": r.get("clicks", 0),
            "chats": r.get("inquiries", 0),
            "impressions": r.get("impressions", 0),
            "followers": r.get("regulars", 0),
            "coupons": r.get("coupons", 0),
        }
        for r in rows
    ]


def _kpi_to_new(kpi: dict) -> dict:
    """Convert legacy KPI keys → new KPI format used by docx_report."""
    return {
        "total_spend": kpi.get("total_cost", 0),
        "total_impressions": kpi.get("total_impressions", 0),
        "total_clicks": kpi.get("total_clicks", 0),
        "total_chats": kpi.get("total_inquiries", 0),
        "total_followers": kpi.get("total_regulars", 0),
        "total_coupons": kpi.get("total_coupons", 0),
        "ctr": kpi.get("ctr", 0.0),
        "cpc": kpi.get("cpc", 0.0),
        "cpa": kpi.get("cpa", 0.0),
        "cpm": kpi.get("cpm", 0.0),
        "cpr": kpi.get("cpr", 0.0),
        "cp_coupon": kpi.get("cp_coupon", 0.0),
        "cvr_click_inquiry": kpi.get("cvr_click_inquiry", 0.0),
        "cvr_click_regular": kpi.get("cvr_click_regular", 0.0),
        "cvr_inquiry_regular": kpi.get("cvr_inquiry_regular", 0.0),
    }


def _extract_list_items(text: str) -> List[str]:
    """Extract numbered / bullet list items from a markdown text block."""
    import re
    items: List[str] = []
    current: List[str] = []
    for line in text.split("\n"):
        m = re.match(r"^\s*(?:\d+[.)]\s+|\*\s+|-\s+|•\s+)(.+)", line)
        if m:
            if current:
                items.append(" ".join(current))
            current = [m.group(1).strip()]
        elif line.strip() and current:
            current.append(line.strip())
        elif not line.strip() and current:
            items.append(" ".join(current))
            current = []
    if current:
        items.append(" ".join(current))
    return [i for i in items if i]


def _parse_ai_insights(content: str) -> dict:
    """Parse AI-generated markdown report → ReportInsights dict for docx_report.

    Supports: (1) embedded JSON block, (2) new 7-section markdown, (3) legacy 3-section.
    """
    import re
    import json

    result = {
        "conclusion": "",
        "next_actions": [],
        "good": "",
        "blocked": "",
        "hypothesis": "",
        "experiments": [],
        "judgment": {},
        # legacy compat
        "summary": "",
        "insights": [],
        "actions": [],
    }

    # ── Fast path: try to extract a JSON block if AI returned structured output ──
    json_match = re.search(r"```json\s*\n(.*?)\n\s*```", content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, dict):
                for key in result:
                    if key in parsed:
                        result[key] = parsed[key]
                # populate cross-refs
                if not result["summary"]:
                    result["summary"] = result["conclusion"]
                if not result["actions"] and result["next_actions"]:
                    result["actions"] = result["next_actions"]
                if not result["next_actions"] and result["actions"]:
                    result["next_actions"] = result["actions"]
                return result
        except (json.JSONDecodeError, TypeError):
            pass  # fall through to markdown parsing

    # ── Markdown parsing ──
    parts = re.split(r"(?m)^## ", content)

    is_legacy = False

    for part in parts:
        if not part.strip():
            continue
        first_line, _, body = part.partition("\n")
        header = first_line.strip().lower()
        body = body.strip()

        # ── new 7-section format ──
        if "결론" in header:
            result["conclusion"] = body
        elif "next action" in header or "다음 액션" in header:
            items = _extract_list_items(body)
            result["next_actions"] = items if items else ([body] if body else [])
        elif "잘 된" in header:
            result["good"] = body
        elif "막힌" in header:
            result["blocked"] = body
        elif "가설" in header:
            result["hypothesis"] = body
        elif "실험" in header:
            experiments = []
            for line in body.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Remove leading numbering
                line = re.sub(r"^\s*\d+[.)]\s*", "", line)
                if "|" in line:
                    parts_pipe = [p.strip() for p in line.split("|")]
                    if len(parts_pipe) >= 5:
                        experiments.append({
                            "priority": parts_pipe[0],
                            "change": parts_pipe[1],
                            "success_criteria": parts_pipe[2],
                            "owner": parts_pipe[3],
                            "schedule": parts_pipe[4],
                        })
                    else:
                        experiments.append({
                            "priority": "-", "change": line,
                            "success_criteria": "-", "owner": "-", "schedule": "-",
                        })
                elif line:
                    experiments.append({
                        "priority": "-", "change": line,
                        "success_criteria": "-", "owner": "-", "schedule": "-",
                    })
            result["experiments"] = experiments
        elif "판단" in header:
            judgment = {}
            for line in body.split("\n"):
                line = line.strip()
                m = re.match(r"(확대|검토|중단)\s*[:：]\s*(.+)", line)
                if m:
                    key_map = {"확대": "expand", "검토": "review", "중단": "stop"}
                    judgment[key_map[m.group(1)]] = m.group(2).strip()
            result["judgment"] = judgment

        # ── legacy 3-section format detection ──
        elif "요약" in header and "인사이트" not in header:
            is_legacy = True
            result["summary"] = body
            if not result["conclusion"]:
                result["conclusion"] = body
        elif "인사이트" in header:
            is_legacy = True
            items = _extract_list_items(body)
            result["insights"] = items if items else ([body] if body else [])
        elif "액션" in header or "action" in header:
            is_legacy = True
            items = _extract_list_items(body)
            result["actions"] = items if items else ([body] if body else [])
            if not result["next_actions"]:
                result["next_actions"] = result["actions"]

    # fallback: if no conclusion was parsed, use first 600 chars
    if not result["conclusion"]:
        result["conclusion"] = result.get("summary") or content[:600]

    # legacy compat: populate summary/actions if not set
    if not result["summary"]:
        result["summary"] = result["conclusion"]
    if not result["actions"] and result["next_actions"]:
        result["actions"] = result["next_actions"]

    return result


def _make_report_docx_bytes(project: dict, rows: List[Dict], kpi: dict, content: str) -> bytes:
    """Build DOCX in a temp file and return its bytes."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        out = Path(tmp_dir) / "report.docx"
        meta_keys = (
            "name", "period", "goal", "industry", "region", "budget",
            "campaign_name", "author", "target", "operation_method", "benefits",
        )
        build_report_docx(
            project_meta={k: project.get(k, "") for k in meta_keys},
            kpi=_kpi_to_new(kpi),
            timeseries=_rows_to_timeseries(rows),
            insights=_parse_ai_insights(content),
            output_path=out,
            chart_dir=CHARTS_DIR,
        )
        return out.read_bytes()


def _create_sample_excel() -> None:
    """Generate a sample Excel template."""
    try:
        import openpyxl
    except ImportError:
        ui.notify("openpyxl이 설치되지 않았습니다: pip install openpyxl", type="negative")
        return

    try:
        from app.paths import EXPORTS_DIR

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "성과데이터"
        headers = ["기간", "비용(원)", "노출", "클릭", "문의", "단골", "쿠폰"]
        ws.append(headers)
        sample_rows = [
            ["1주차", 75000, 12000, 480, 18, 3, 5],
            ["2주차", 75000, 13500, 540, 21, 4, 7],
            ["3주차", 75000, 11800, 420, 16, 2, 4],
            ["4주차", 75000, 14200, 610, 25, 5, 9],
        ]
        for r in sample_rows:
            ws.append(r)

        downloads = Path.home() / "Downloads"
        out_dir = downloads if downloads.exists() else EXPORTS_DIR
        out = out_dir / "당근광고_성과템플릿.xlsx"
        wb.save(out)
        ui.notify(f"템플릿 저장: {out}", type="positive")
    except Exception as exc:
        ui.notify(f"템플릿 생성 오류: {exc}", type="negative")


# ── Page ─────────────────────────────────────────────────────────────────────

@ui.page("/report")
def report_page() -> None:
    create_nav("/report")

    page_state: dict = {"rows": [], "kpi": {}, "report_content": "", "engine": "claude", "c_text": "", "g_text": "", "cancelled": False}

    with ui.column().classes("w-full p-6 gap-4"):

        # ── Project selector ───────────────────────────────────────────────
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-4"):
                ui.label("프로젝트").classes("font-bold text-gray-600 w-20")
                projects = get_projects()
                options = {p["id"]: f"{p['name']} ({p.get('region','')})" for p in projects}
                saved_pid = nicegui_app.storage.user.get("current_project_id")
                project_sel = ui.select(
                    options,
                    label="프로젝트 선택",
                    value=saved_pid if saved_pid in options else None,
                ).classes("flex-1")
                project_sel.on(
                    "update:model-value",
                    lambda e: (
                        nicegui_app.storage.user.__setitem__(
                            "current_project_id", e.value
                        ),
                        _load_saved_data(),
                    ),
                )

        # ── Data Input ────────────────────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("성과 데이터 입력").classes("font-bold text-gray-700 mb-3")

            with ui.tabs().classes("w-full") as tabs:
                tab_upload = ui.tab("📊 파일 업로드")
                tab_manual = ui.tab("✏️ 수기 입력")

            with ui.tab_panels(tabs, value=tab_upload).classes("w-full"):

                # ── File upload panel (CSV + XLSX) ─────────────────────────
                with ui.tab_panel(tab_upload):
                    ui.label(
                        "CSV: 당근 광고관리자 내려받기 파일 (헤더 자동 매핑)  |  "
                        "XLSX: 기간|비용|노출|클릭|문의|단골|쿠폰 (1행=헤더)"
                    ).classes("text-xs text-gray-400 mb-2")

                    with ui.row().classes("gap-3 items-center"):
                        ui.upload(
                            label="파일 선택 (.csv / .xlsx)",
                            auto_upload=True,
                            on_upload=lambda e: asyncio.ensure_future(_handle_upload(e)),
                        ).classes("max-w-xs").props('accept=".csv,.xlsx"')

                        ui.button(
                            "샘플 템플릿 생성",
                            on_click=lambda: _create_sample_excel(),
                        ).classes("bg-gray-200 text-gray-700 text-sm")

                    # ── 업로드 결과 요약 ──
                    upload_summary = ui.column().classes("w-full mt-2 hidden")
                    # ── 업로드 미리보기 ──
                    upload_preview = ui.column().classes("w-full mt-3 hidden")

                # ── Manual input panel ─────────────────────────────────────
                with ui.tab_panel(tab_manual):
                    manual_rows_container = ui.column().classes("w-full gap-2")
                    _manual_inputs: List[dict] = []  # list of {period, cost, imp, clk, inq, reg, coup}

                    def _build_manual_row(idx: int, defaults: dict | None = None) -> dict:
                        d = defaults or _blank_row(idx)
                        with manual_rows_container:
                            with ui.row().classes("w-full gap-2 items-center"):
                                p = ui.input(value=d["period_label"]).props(
                                    'placeholder="기간" outlined dense'
                                ).classes("w-28")
                                c = ui.input(value=str(d["cost"])).props(
                                    'placeholder="비용" outlined dense type=number'
                                ).classes("w-24")
                                im = ui.input(value=str(d["impressions"])).props(
                                    'placeholder="노출" outlined dense type=number'
                                ).classes("w-24")
                                cl = ui.input(value=str(d["clicks"])).props(
                                    'placeholder="클릭" outlined dense type=number'
                                ).classes("w-24")
                                inq = ui.input(value=str(d["inquiries"])).props(
                                    'placeholder="문의" outlined dense type=number'
                                ).classes("w-24")
                                reg = ui.input(value=str(d["regulars"])).props(
                                    'placeholder="단골" outlined dense type=number'
                                ).classes("w-20")
                                coup = ui.input(value=str(d["coupons"])).props(
                                    'placeholder="쿠폰" outlined dense type=number'
                                ).classes("w-20")
                        return {"p": p, "c": c, "im": im, "cl": cl, "inq": inq, "reg": reg, "coup": coup}

                    with ui.row().classes("w-full gap-1 text-xs text-gray-400 font-medium px-1"):
                        for lbl, w in [("기간", "w-28"), ("비용(원)", "w-24"), ("노출", "w-24"),
                                       ("클릭", "w-24"), ("문의", "w-24"), ("단골", "w-20"), ("쿠폰", "w-20")]:
                            ui.label(lbl).classes(w)

                    for i in range(4):
                        _manual_inputs.append(_build_manual_row(i + 1))

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button(
                            "+ 행 추가",
                            on_click=lambda: _manual_inputs.append(
                                _build_manual_row(len(_manual_inputs) + 1)
                            ),
                        ).classes("text-sm bg-gray-100")

                        ui.button(
                            "데이터 적용",
                            on_click=lambda: _apply_manual_inputs(_manual_inputs),
                        ).classes("bg-orange-500 text-white text-sm")

        # ── KPI display ────────────────────────────────────────────────────
        kpi_card = ui.card().classes("w-full hidden")
        kpi_row = ui.row().classes("w-full gap-4 flex-wrap")

        with kpi_card:
            ui.label("KPI 자동 계산").classes("font-bold text-gray-700 mb-2")
            kpi_row

        def _show_kpi(kpi: dict) -> None:
            kpi_row.clear()
            with kpi_row:
                basic = [
                    ("총 비용", f"{kpi.get('total_cost',0):,} 원"),
                    ("총 노출", f"{kpi.get('total_impressions',0):,} 회"),
                    ("총 클릭", f"{kpi.get('total_clicks',0):,} 회"),
                    ("CTR", f"{kpi.get('ctr',0):.2f} %"),
                    ("CPC", f"{kpi.get('cpc',0):,.0f} 원"),
                    ("CPM", f"{kpi.get('cpm',0):,.0f} 원"),
                    ("총 문의", f"{kpi.get('total_inquiries',0):,} 건"),
                    ("CPA", f"{kpi.get('cpa',0):,.0f} 원"),
                    ("클릭→문의", f"{kpi.get('cvr_click_inquiry',0):.1f} %"),
                    ("단골 전환", f"{kpi.get('total_regulars',0):,} 명"),
                    ("CPR(단골당)", f"{kpi.get('cpr',0):,.0f} 원"),
                    ("클릭→단골", f"{kpi.get('cvr_click_regular',0):.1f} %"),
                    ("쿠폰 사용", f"{kpi.get('total_coupons',0):,} 건"),
                    ("쿠폰당 비용", f"{kpi.get('cp_coupon',0):,.0f} 원"),
                ]
                for label, val in basic:
                    with ui.card().classes("items-center px-5 py-3 bg-orange-50"):
                        ui.label(label).classes("text-xs text-gray-500")
                        ui.label(val).classes("text-base font-bold text-orange-700 mt-1")
            kpi_card.classes(remove="hidden")

        # ── Chart preview ──────────────────────────────────────────────────
        chart_card = ui.card().classes("w-full hidden")
        chart_row = ui.row().classes("w-full gap-4 flex-wrap")

        with chart_card:
            ui.label("성과 차트 미리보기").classes("font-bold text-gray-700 mb-2")
            chart_row

        # ── AI report generation ───────────────────────────────────────────
        with ui.card().classes("w-full"):
            ui.label("AI 보고서 생성").classes("font-bold text-gray-700 mb-3")
            with ui.row().classes("items-start gap-8"):
                with ui.column().classes("gap-1"):
                    ui.label("AI 엔진").classes("text-sm font-medium text-gray-500")
                    engine_radio = ui.radio(
                        {"claude": "Claude", "gemini": "Gemini", "both": "둘 다 (비교)"},
                        value="claude",
                    ).props("inline")
                with ui.column().classes("flex-1 gap-1"):
                    ui.label("추가 요청 사항 (선택)").classes(
                        "text-sm font-medium text-gray-500"
                    )
                    extra_input = ui.textarea(
                        placeholder="예: 다음 달 예산 20% 증가 검토 중, ROI 중심으로 분석 등"
                    ).classes("w-full").props("rows=2 outlined")

        with ui.row().classes("gap-3 items-center"):
            gen_btn = ui.button(
                "📊 보고서 생성",
                on_click=lambda: asyncio.ensure_future(_generate_report()),
            ).classes("bg-orange-500 text-white text-base px-6")
            export_default_btn = ui.button(
                "기본 폴더에 저장 (권장)",
                on_click=lambda: asyncio.ensure_future(_export_default()),
            ).classes("bg-green-600 text-white text-base px-6")
            export_saveas_btn = ui.button(
                "다른 위치로 저장...",
                on_click=lambda: asyncio.ensure_future(_export_saveas()),
            ).classes("bg-green-700 text-white text-base px-6").props("outline")
            cancel_btn = ui.button(
                "중단",
                on_click=lambda: _cancel_generation(),
            ).classes("bg-red-500 text-white text-sm px-4 hidden")
            spinner = ui.spinner(size="32px").classes("hidden")
            step_label = ui.label("").classes("text-sm text-gray-500 hidden")
            download_status = ui.label("").classes("text-sm text-green-600 font-medium hidden")

        def _cancel_generation() -> None:
            page_state["cancelled"] = True
            step_label.set_text("⚠️ 중단 요청됨...")

        def _set_step(text: str) -> None:
            step_label.classes(remove="hidden")
            step_label.set_text(text)

        # ── Report preview ─────────────────────────────────────────────────
        report_card = ui.card().classes("w-full hidden")
        report_md = ui.markdown("").classes("w-full prose max-w-none")

        with report_card:
            report_md

        # ── Data handlers ──────────────────────────────────────────────────

        def _set_rows(rows: List[Dict]) -> None:
            page_state["rows"] = rows
            kpi = calc_kpi(rows)
            page_state["kpi"] = kpi
            _show_kpi(kpi)
            _render_charts(rows)
            pid = nicegui_app.storage.user.get("current_project_id")
            if pid:
                save_performance_rows(pid, rows)
                ui.notify(f"{len(rows)}개 행 저장됨.", type="positive")

        def _show_upload_preview(rows: List[Dict]) -> None:
            upload_preview.clear()
            upload_preview.classes(remove="hidden")
            with upload_preview:
                ui.label(f"업로드 데이터 미리보기 ({len(rows)}행)").classes(
                    "font-medium text-sm text-gray-700"
                )
                columns = [
                    {"name": "period_label", "label": "기간", "field": "period_label"},
                    {"name": "cost", "label": "비용", "field": "cost"},
                    {"name": "impressions", "label": "노출", "field": "impressions"},
                    {"name": "clicks", "label": "클릭", "field": "clicks"},
                    {"name": "inquiries", "label": "문의", "field": "inquiries"},
                    {"name": "regulars", "label": "단골", "field": "regulars"},
                    {"name": "coupons", "label": "쿠폰", "field": "coupons"},
                ]
                ui.table(columns=columns, rows=rows).classes("w-full").props(
                    "dense flat bordered"
                )

        async def _handle_upload(e) -> None:
            try:
                file_bytes = await e.file.read()
                filename = e.file.name or ""
                ext = Path(filename).suffix.lower()

                upload_summary.clear()
                upload_summary.classes(remove="hidden")

                if ext == ".csv":
                    csv_rows, warnings = parse_daangn_csv(file_bytes)
                    # CSV 결과를 내부 row 포맷으로 변환 (date → period_label)
                    rows = [
                        {
                            "period_label": r["date"],
                            "cost": r["cost"],
                            "impressions": r["impressions"],
                            "clicks": r["clicks"],
                            "inquiries": r["inquiries"],
                            "regulars": r["regulars"],
                            "coupons": r["coupons"],
                        }
                        for r in csv_rows
                    ]
                    # 매핑 요약 표시
                    with upload_summary:
                        with ui.card().classes("w-full bg-blue-50 p-3"):
                            ui.label(f"CSV 파싱 결과: {len(rows)}행 매핑됨").classes(
                                "font-medium text-sm text-blue-700"
                            )
                            mapped_cols = [
                                k for k in ("date", "cost", "impressions", "clicks",
                                            "inquiries", "regulars", "coupons")
                                if csv_rows and k in csv_rows[0]
                            ]
                            ui.label(
                                f"매핑 컬럼: {', '.join(mapped_cols)}"
                            ).classes("text-xs text-blue-600")
                            if warnings:
                                skip_count = sum(1 for w in warnings if "skipped" in w.lower() or "empty" in w.lower())
                                ui.label(
                                    f"경고 {len(warnings)}건 (스킵 행: {skip_count})"
                                ).classes("text-xs text-orange-600")
                                for w in warnings[:5]:
                                    ui.label(f"  - {w}").classes("text-xs text-gray-500")
                                if len(warnings) > 5:
                                    ui.label(f"  ... 외 {len(warnings) - 5}건").classes("text-xs text-gray-400")
                    if not rows:
                        ui.notify("CSV에서 유효한 데이터를 찾을 수 없습니다.", type="warning")
                        return
                elif ext == ".xlsx":
                    rows, warning = _parse_excel(file_bytes)
                    with upload_summary:
                        with ui.card().classes("w-full bg-blue-50 p-3"):
                            ui.label(f"XLSX 파싱 결과: {len(rows)}행 로드됨").classes(
                                "font-medium text-sm text-blue-700"
                            )
                            ui.label(
                                "컬럼: 기간, 비용, 노출, 클릭, 문의, 단골, 쿠폰"
                            ).classes("text-xs text-blue-600")
                            if warning:
                                ui.label(f"경고: {warning}").classes("text-xs text-orange-600")
                    if warning:
                        ui.notify(f"⚠️ {warning}", type="warning", timeout=8000)
                    if not rows:
                        ui.notify("데이터를 찾을 수 없습니다. 헤더 행을 확인해주세요.", type="warning")
                        return
                else:
                    ui.notify(f"지원하지 않는 파일 형식입니다: {ext}", type="negative")
                    return

                _set_rows(rows)
                _show_upload_preview(rows)
            except Exception as exc:
                ui.notify(f"파일 파싱 오류: {exc}", type="negative")

        def _apply_manual_inputs(inputs: List[dict]) -> None:
            rows = []
            for inp in inputs:
                rows.append(
                    {
                        "period_label": inp["p"].value.strip() or f"기간{len(rows)+1}",
                        "cost": _parse_int(inp["c"].value),
                        "impressions": _parse_int(inp["im"].value),
                        "clicks": _parse_int(inp["cl"].value),
                        "inquiries": _parse_int(inp["inq"].value),
                        "regulars": _parse_int(inp["reg"].value),
                        "coupons": _parse_int(inp["coup"].value),
                    }
                )
            rows = [r for r in rows if any(r[k] > 0 for k in ("cost","impressions","clicks","inquiries"))]
            if not rows:
                ui.notify("유효한 데이터 행이 없습니다.", type="warning")
                return
            _set_rows(rows)

        def _render_charts(rows: List[Dict]) -> None:
            chart_row.clear()
            paths = make_charts(rows, CHARTS_DIR)
            if not paths:
                return
            chart_card.classes(remove="hidden")
            with chart_row:
                for p in paths:
                    if p.exists():
                        ui.image(str(p)).classes("max-w-sm rounded shadow")

        def _load_saved_data() -> None:
            pid = nicegui_app.storage.user.get("current_project_id")
            if not pid:
                return
            rows = get_performance_rows(pid)
            if rows:
                page_state["rows"] = rows
                kpi = calc_kpi(rows)
                page_state["kpi"] = kpi
                _show_kpi(kpi)
                _render_charts(rows)
            rpt = get_latest_report(pid)
            if rpt:
                page_state["report_content"] = rpt["content"]
                report_md.set_content(rpt["content"])
                report_card.classes(remove="hidden")

        async def _generate_report() -> None:
            pid = nicegui_app.storage.user.get("current_project_id")
            if not pid:
                ui.notify("프로젝트를 먼저 선택해주세요.", type="warning")
                return
            rows = page_state.get("rows", [])
            if not rows:
                ui.notify("성과 데이터를 먼저 입력/업로드 해주세요.", type="warning")
                return

            project = get_project(pid)
            if not project:
                ui.notify("프로젝트를 찾을 수 없습니다.", type="negative")
                return

            engine = engine_radio.value
            extra = extra_input.value
            kpi = page_state.get("kpi", calc_kpi(rows))

            page_state["cancelled"] = False
            spinner.classes(remove="hidden")
            gen_btn.props("disabled")
            cancel_btn.classes(remove="hidden")

            try:
                _set_step("1/4 프롬프트 생성 중...")
                prompt = build_report_prompt(project, rows, kpi, extra)
                loop = asyncio.get_event_loop()

                if page_state["cancelled"]:
                    ui.notify("생성이 중단되었습니다.", type="warning")
                    return

                # ── AI text generation via providers ──────────────────────────
                guide = SYSTEM_GUIDE_REPORT
                if engine == "both":
                    _set_step("2/4 Claude + Gemini 동시 호출 중...")
                    claude_p = ClaudeProvider()
                    gemini_p = GeminiProvider()
                    c_text, g_text = await asyncio.gather(
                        loop.run_in_executor(None, lambda: claude_p.generate_text(prompt, system_prompt=guide)),
                        loop.run_in_executor(None, lambda: gemini_p.generate_text(prompt, system_prompt=guide)),
                    )
                    if page_state["cancelled"]:
                        ui.notify("생성이 중단되었습니다.", type="warning")
                        return
                    content = (
                        f"## [Claude 결과]\n\n{c_text}\n\n"
                        f"---\n\n## [Gemini 결과]\n\n{g_text}"
                    )
                    page_state["c_text"] = c_text
                    page_state["g_text"] = g_text
                else:
                    _set_step(f"2/4 {engine.capitalize()} 호출 중...")
                    provider = get_provider(engine)
                    content = await loop.run_in_executor(None, lambda: provider.generate_text(prompt, system_prompt=guide))
                    if page_state["cancelled"]:
                        ui.notify("생성이 중단되었습니다.", type="warning")
                        return
                    page_state["c_text"] = ""
                    page_state["g_text"] = ""

                _set_step("3/4 결과 저장 중...")
                page_state["report_content"] = content
                page_state["engine"] = engine
                save_report_content(pid, engine, content)
                report_md.set_content(content)
                report_card.classes(remove="hidden")

                # ── Auto-generate DOCX + browser download ─────────────────────
                try:
                    _set_step("4/4 DOCX 파일 생성 중...")
                    project_name = project.get('name', 'report')
                    download_status.classes(remove="hidden")
                    download_status.set_text("DOCX 파일 준비 중...")
                    if engine == "both":
                        c_bytes, g_bytes = await asyncio.gather(
                            loop.run_in_executor(None, _make_report_docx_bytes, project, rows, kpi, c_text),
                            loop.run_in_executor(None, _make_report_docx_bytes, project, rows, kpi, g_text),
                        )
                        c_fname = f"성과보고서_{project_name}_Claude.docx"
                        g_fname = f"성과보고서_{project_name}_Gemini.docx"
                        ExportManager.save_default(c_bytes, filename=c_fname)
                        ExportManager.save_default(g_bytes, filename=g_fname)
                        download_status.set_text(f"✅ {c_fname}, {g_fname} 다운로드 시작됨")
                        ui.notify(
                            f"보고서 생성 완료!\n📥 {c_fname}\n📥 {g_fname}",
                            type="positive", timeout=10000, close_button="확인",
                        )
                    else:
                        docx_bytes = await loop.run_in_executor(
                            None, _make_report_docx_bytes, project, rows, kpi, content
                        )
                        fname = f"성과보고서_{project_name}.docx"
                        ExportManager.save_default(docx_bytes, filename=fname)
                        download_status.set_text(f"✅ {fname} 다운로드 시작됨")
                        ui.notify(
                            f"보고서 생성 완료!\n📥 {fname}",
                            type="positive", timeout=8000, close_button="확인",
                        )
                except Exception as docx_err:
                    download_status.set_text("⚠️ DOCX 생성 오류")
                    ui.notify(f"보고서 생성 완료 (DOCX 오류: {docx_err})", type="warning", timeout=8000)

            except Exception as exc:
                ui.notify(f"오류: {exc}", type="negative", timeout=8000)
            finally:
                spinner.classes("hidden")
                cancel_btn.classes("hidden")
                step_label.classes("hidden")
                gen_btn.props(remove="disabled")

        def _validate_export() -> tuple:
            """Validate state for export. Returns (project, project_name, rows, kpi, content, engine)."""
            content = page_state.get("report_content", "")
            if not content:
                raise ValueError("먼저 보고서를 생성해주세요.")
            rows = page_state.get("rows", [])
            kpi = page_state.get("kpi", {})
            pid = nicegui_app.storage.user.get("current_project_id")
            project = get_project(pid) if pid else None
            if not project:
                raise ValueError("프로젝트를 선택해주세요.")
            project_name = project.get('name', 'report')
            engine = page_state.get("engine", "claude")
            return project, project_name, rows, kpi, content, engine

        async def _build_report_pairs() -> list[tuple[bytes, str]]:
            """Build DOCX byte pairs: [(bytes, filename), ...]"""
            project, project_name, rows, kpi, content, engine = _validate_export()
            loop = asyncio.get_event_loop()
            if engine == "both" and page_state.get("c_text") and page_state.get("g_text"):
                c_bytes, g_bytes = await asyncio.gather(
                    loop.run_in_executor(None, _make_report_docx_bytes, project, rows, kpi, page_state["c_text"]),
                    loop.run_in_executor(None, _make_report_docx_bytes, project, rows, kpi, page_state["g_text"]),
                )
                return [
                    (c_bytes, f"성과보고서_{project_name}_Claude.docx"),
                    (g_bytes, f"성과보고서_{project_name}_Gemini.docx"),
                ]
            else:
                docx_bytes = await loop.run_in_executor(
                    None, _make_report_docx_bytes, project, rows, kpi, content
                )
                return [(docx_bytes, f"성과보고서_{project_name}.docx")]

        async def _export_default() -> None:
            export_default_btn.props("disabled loading")
            download_status.classes(remove="hidden")
            download_status.set_text("DOCX 파일 준비 중...")
            try:
                pairs = await _build_report_pairs()
                names = []
                for docx_bytes, fname in pairs:
                    ExportManager.save_default(docx_bytes, filename=fname)
                    names.append(fname)
                download_status.set_text(f"✅ {', '.join(names)} 저장 완료")
                ui.notify(
                    "\n".join(f"📥 {n}" for n in names),
                    type="positive", timeout=8000, close_button="확인",
                )
            except ValueError as ve:
                ui.notify(str(ve), type="warning")
            except Exception as exc:
                download_status.set_text("⚠️ 내보내기 오류")
                ui.notify(f"내보내기 오류: {exc}", type="negative")
            finally:
                export_default_btn.props(remove="disabled loading")

        async def _export_saveas() -> None:
            export_saveas_btn.props("disabled loading")
            download_status.classes(remove="hidden")
            download_status.set_text("DOCX 파일 준비 중...")
            try:
                pairs = await _build_report_pairs()
                ok = await ExportManager.save_as_multi(pairs)
                if ok:
                    names = [f for _, f in pairs]
                    download_status.set_text(f"✅ {', '.join(names)} 저장 완료")
                else:
                    download_status.set_text("저장 취소됨")
            except ValueError as ve:
                ui.notify(str(ve), type="warning")
            except Exception as exc:
                download_status.set_text("⚠️ 내보내기 오류")
                ui.notify(f"내보내기 오류: {exc}", type="negative")
            finally:
                export_saveas_btn.props(remove="disabled loading")

        # ── Diagnostic log panel ──────────────────────────────────────────
        create_log_panel()
        create_path_info_panel()

        # initial load
        _load_saved_data()
