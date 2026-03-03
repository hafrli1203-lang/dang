# GPT Pro 코드 리뷰 요청서 — 당근 광고 기획 도우미

> **프로젝트**: daangn_ad_reporter (당근 광고 기획 도우미)
> **버전**: 1.0.0
> **작성일**: 2026-03-03
> **목적**: 전체 구현의 정합성·품질·보안을 검증받기 위한 문서

---

## 1. 프로젝트 개요

당근마켓(지역 중고거래·비즈니스 플랫폼)에서 광고를 집행하는 소상공인을 위한 **광고 기획서 + 성과 보고서 자동 생성 도구**입니다.

### 핵심 기능
| 화면 | 경로 | 기능 |
|------|------|------|
| 프로젝트 관리 | `/` | 광고주 정보 CRUD (상호명, 업종, 지역, 예산 등) |
| 광고 기획 | `/planning` | AI가 기획 요약 + 소식글 + 광고 카피 9개 생성 → DOCX 내보내기 |
| 성과 보고서 | `/report` | 성과 데이터 입력(수기/엑셀) → KPI 계산 → AI 분석 → DOCX+차트 내보내기 |

### 기술 스택
- **언어**: Python 3.11+
- **UI**: NiceGUI >=2.0 (웹 기반, 선택적 네이티브 데스크톱)
- **DB**: SQLite (daangn_ads.db, 4 테이블)
- **AI**: Claude (anthropic SDK) / Gemini (google-genai SDK) — 택1 또는 양쪽 동시
- **문서**: python-docx + matplotlib 차트 → DOCX 자동 생성
- **배포**: PyInstaller (Windows exe) + Inno Setup (인스톨러)

---

## 2. 파일 트리 및 역할

```
daangn_ad_reporter/
├── main.py                          # 진입점 (87줄)
│   - __version__ = "1.0.0"
│   - IS_FROZEN/BUNDLE_DIR/APP_DIR: PyInstaller 번들 감지
│   - .env 로딩 → DB 초기화 → 페이지 등록 → ui.run()
│   - @on_startup: 백그라운드 업데이트 체크
│
├── app/
│   ├── database.py                  # SQLite CRUD (173줄)
│   │   - 4 테이블: projects, generated_content, performance_rows, report_content
│   │   - get_conn(), init_db(), save/get/delete 함수들
│   │
│   ├── ai_engine.py                 # 프롬프트 빌더 + KPI 계산 (222줄)
│   │   - SYSTEM_GUIDE_REPORT: 성과보고서 AI 시스템 프롬프트
│   │   - SYSTEM_GUIDE_PLANNING: 기획서 AI 시스템 프롬프트
│   │   - build_planning_prompt(), build_report_prompt()
│   │   - calc_kpi(): CTR/CPC/CPA 등 KPI 집계
│   │   ※ API 호출 코드 없음 (providers.py로 이관 완료)
│   │
│   ├── common.py                    # 공통 UI (44줄)
│   │   - NAV_PAGES 정의, create_nav(), project_selector()
│   │
│   ├── export.py                    # 레거시 DOCX (293줄, planning 페이지에서 사용)
│   │
│   ├── updater.py                   # 자동 업데이트 (110줄)
│   │   - GITHUB_REPO = "hafrli1203-lang/dang"
│   │   - check_for_update(): GitHub Releases API 조회
│   │   - show_update_notification(): NiceGUI 알림 표시
│   │
│   ├── ai/
│   │   ├── providers.py             # AI 공급자 추상화 (122줄)
│   │   │   - BaseProvider(ABC): generate_text(prompt, system_prompt=None)
│   │   │   - ClaudeProvider: anthropic.Anthropic → messages.create()
│   │   │   - GeminiProvider: genai.Client → models.generate_content()
│   │   │   - get_provider("claude"|"gemini") → 인스턴스 팩토리
│   │   │
│   │   └── test_providers.py        # 15개 모킹 테스트 (238줄)
│   │
│   ├── pages/
│   │   ├── project.py               # 화면1: 프로젝트 관리 (169줄)
│   │   ├── planning.py              # 화면2: 광고 기획 (208줄)
│   │   └── report.py                # 화면3: 성과 보고서 (597줄)
│   │
│   ├── reporting/
│   │   ├── docx_report.py           # v2.2 DOCX 생성기 (1165줄)
│   │   │   - make_charts(): matplotlib 차트 3종 생성
│   │   │   - build_report_docx(): 성과보고서 DOCX 빌드
│   │   │   - build_planning_docx(): 기획서 DOCX 빌드
│   │   │
│   │   ├── test_docx_report.py      # 19개 테스트 (302줄)
│   │   └── document_spec.md         # 문서 설계 명세
│   │
│   └── test_updater.py              # 8개 모킹 테스트 (77줄)
│
├── build.py                         # PyInstaller 빌드 스크립트 (103줄)
├── daangn.spec                      # PyInstaller spec (고급 설정)
├── installer.iss                    # Inno Setup 인스톨러 (163줄)
├── app_icon.ico                     # 앱 아이콘 (16~256px, 7 사이즈)
├── app_icon.png                     # PNG 아이콘 (256x256)
├── requirements.txt                 # 의존성 목록
├── .env.example                     # 환경변수 템플릿
├── verify_reports.py                # DOCX 검증 스크립트 (172줄)
├── verify_sample.py                 # 샘플 검증 스크립트 (123줄)
├── start_windows.bat / start_mac.sh # 시작 스크립트
├── README.md / HANDOFF.md           # 문서
└── templates/                       # DOCX 기준 템플릿
```

---

## 3. 아키텍처 데이터 흐름

### 3-1. 기획서 생성 흐름 (화면 2: /planning)

```
사용자 → 프로젝트 선택 + AI 엔진 선택 (Claude/Gemini/둘다)
    → "기획서 생성" 클릭
    → ai_engine.build_planning_prompt(project) → user prompt 생성
    → ai_engine.SYSTEM_GUIDE_PLANNING → system prompt
    → providers.get_provider(engine).generate_text(prompt, system_prompt=guide)
       ├─ Claude: anthropic.messages.create(system=guide, messages=[...])
       └─ Gemini: genai.generate_content(config=GenerateContentConfig(system_instruction=guide))
    → AI 응답 텍스트 → UI 마크다운 프리뷰
    → "DOCX 저장" 클릭
    → reporting.docx_report.build_planning_docx() → DOCX 바이트
    → ui.download() → 브라우저 자동 다운로드
```

### 3-2. 성과보고서 생성 흐름 (화면 3: /report)

```
사용자 → 프로젝트 선택 + 성과 데이터 입력(수기 or 엑셀)
    → KPI 자동 계산 (ai_engine.calc_kpi) + 차트 미리보기
    → AI 엔진 선택 + "보고서 생성" 클릭
    → ai_engine.build_report_prompt(project, rows, kpi)
    → ai_engine.SYSTEM_GUIDE_REPORT → system prompt
    → providers.get_provider(engine).generate_text(...)
    → _parse_ai_insights(content) → 구조화된 인사이트
    → reporting.docx_report.build_report_docx(meta, kpi, timeseries, insights)
       → make_charts() → 3개 PNG 차트 생성 (_charts/ 디렉토리)
       → DOCX에 표지 + KPI 테이블 + 차트 + 인사이트 삽입
    → ui.download() → 브라우저 다운로드
    ※ "둘 다" 선택 시: 2개 DOCX (_Claude.docx + _Gemini.docx) 별도 생성
```

### 3-3. AI Provider 추상화

```python
# app/ai/providers.py — 동기 인터페이스, async는 호출자 책임

class BaseProvider(ABC):
    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str: ...

class ClaudeProvider(BaseProvider):
    # anthropic.Anthropic → messages.create(model, max_tokens, messages, system?)

class GeminiProvider(BaseProvider):
    # genai.Client → models.generate_content(model, contents, config?)

# 팩토리
get_provider("claude") → ClaudeProvider()
get_provider("gemini") → GeminiProvider()
```

**핵심 설계**: system_prompt(내부 운영 가이드)는 각 SDK의 system 채널로만 전달되어 **사용자 출력물에 절대 노출되지 않음**.

---

## 4. 데이터베이스 스키마

```sql
-- projects: 광고주(프로젝트) 정보
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,          -- 상호명
    industry TEXT DEFAULT '',    -- 업종
    region TEXT DEFAULT '',      -- 지역
    goal TEXT DEFAULT '',        -- 광고 목표
    budget TEXT DEFAULT '',      -- 예산
    period TEXT DEFAULT '',      -- 집행 기간
    benefits TEXT DEFAULT '',    -- 주요 혜택
    reference_url TEXT DEFAULT '',-- 참고 링크
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- generated_content: 기획서 AI 생성 결과
CREATE TABLE generated_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,        -- 'claude' | 'gemini'
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- performance_rows: 기간별 성과 데이터
CREATE TABLE performance_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    period_label TEXT DEFAULT '',  -- '1주차', '2월' 등
    cost INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    inquiries INTEGER DEFAULT 0,
    regulars INTEGER DEFAULT 0,
    coupons INTEGER DEFAULT 0
);

-- report_content: 성과보고서 AI 분석 결과
CREATE TABLE report_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 5. 핵심 코드 전문 (검증 대상)

### 5-1. AI Provider (app/ai/providers.py — 122줄)

```python
"""AI provider abstractions — 동기 인터페이스, async wrapping은 호출자 책임."""
from __future__ import annotations
import os
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Send prompt to model and return generated text.
        system_prompt → provider의 system 채널로 전달 (출력물 미노출)"""

class ClaudeProvider(BaseProvider):
    DEFAULT_MODEL = "claude-opus-4-6"

    def __init__(self, api_key=None, model=None, max_tokens=4096):
        import anthropic
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        self._model = model or os.getenv("CLAUDE_MODEL", self.DEFAULT_MODEL)
        self._max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def generate_text(self, prompt, *, system_prompt=None):
        kwargs = dict(model=self._model, max_tokens=self._max_tokens,
                      messages=[{"role": "user", "content": prompt}])
        if system_prompt:
            kwargs["system"] = system_prompt
        response = self._client.messages.create(**kwargs)
        return response.content[0].text

class GeminiProvider(BaseProvider):
    DEFAULT_MODEL = "gemini-2.5-pro-preview-05-06"

    def __init__(self, api_key=None, model=None):
        from google import genai
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self._model = model or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self._client = genai.Client(api_key=self._api_key)

    def generate_text(self, prompt, *, system_prompt=None):
        kwargs = dict(model=self._model, contents=prompt)
        if system_prompt:
            from google.genai import types
            kwargs["config"] = types.GenerateContentConfig(system_instruction=system_prompt)
        response = self._client.models.generate_content(**kwargs)
        return response.text

def get_provider(engine: str) -> BaseProvider:
    if engine == "claude":    return ClaudeProvider()
    elif engine == "gemini":  return GeminiProvider()
    else: raise ValueError(f"Unknown engine {engine!r}. Valid: 'claude', 'gemini'.")
```

### 5-2. 자동 업데이트 (app/updater.py — 110줄)

```python
"""GitHub Releases 기반 자동 업데이트 체커."""
import logging
from typing import Optional

GITHUB_REPO = "hafrli1203-lang/dang"
CHECK_TIMEOUT = 5

def _parse_version(v: str) -> tuple:
    """'v1.2.3' → (1, 2, 3)"""
    v = v.lstrip("vV").strip()
    parts = []
    for p in v.split("."):
        try: parts.append(int(p))
        except ValueError: break
    return tuple(parts) or (0,)

def check_for_update(current_version=None) -> Optional[dict]:
    if not GITHUB_REPO: return None
    if current_version is None:
        try: from main import __version__; current_version = __version__
        except: current_version = "0.0.0"
    try:
        import urllib.request, json
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(api_url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DaangnAdReporter-Updater",
        })
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        remote_tag = data.get("tag_name", "")
        if not remote_tag: return None
        if _parse_version(remote_tag) > _parse_version(current_version):
            return {"version": remote_tag.lstrip("vV"),
                    "url": data.get("html_url", ""),
                    "notes": data.get("body", "")[:500]}
        return None
    except Exception as exc:
        logging.getLogger(__name__).debug("Update check failed: %s", exc)
        return None

def show_update_notification(ui_module, update_info: dict):
    version, url = update_info["version"], update_info["url"]
    ui_module.notify(
        f"새 버전 {version} 이 있습니다! 업데이트를 확인하세요.",
        type="info", timeout=15000, close_button="닫기",
        actions=[{"label": "다운로드",
                  "handler": lambda: ui_module.navigate.to(url, new_tab=True)}] if url else [],
    )
```

### 5-3. KPI 계산 (app/ai_engine.py 발췌)

```python
def calc_kpi(rows: List[Dict]) -> dict:
    total_cost = sum(r.get("cost", 0) for r in rows)
    total_imp = sum(r.get("impressions", 0) for r in rows)
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    total_inq = sum(r.get("inquiries", 0) for r in rows)
    total_reg = sum(r.get("regulars", 0) for r in rows)
    total_coup = sum(r.get("coupons", 0) for r in rows)
    ctr = (total_clicks / total_imp * 100) if total_imp > 0 else 0.0
    cpc = (total_cost / total_clicks) if total_clicks > 0 else 0.0
    cpa = (total_cost / total_inq) if total_inq > 0 else 0.0
    return {
        "total_cost": total_cost, "total_impressions": total_imp,
        "total_clicks": total_clicks, "total_inquiries": total_inq,
        "total_regulars": total_reg, "total_coupons": total_coup,
        "ctr": ctr, "cpc": cpc, "cpa": cpa,
    }
```

### 5-4. 진입점 (main.py — 87줄)

```python
"""Entry point — 당근 광고 기획 도우미."""
import os, sys
from pathlib import Path

__version__ = "1.0.0"

# PyInstaller 번들 감지
IS_FROZEN = getattr(sys, "frozen", False)
if IS_FROZEN:
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    BUNDLE_DIR = Path(__file__).parent.resolve()
    APP_DIR = BUNDLE_DIR

from dotenv import load_dotenv
load_dotenv(APP_DIR / ".env")
os.chdir(APP_DIR)

from app.database import init_db
init_db()

import app.pages.project, app.pages.planning, app.pages.report  # 페이지 등록

from nicegui import ui, app as nicegui_app
storage_secret = os.getenv("STORAGE_SECRET", "daangn-reporter-default-secret")

@nicegui_app.on_startup
async def _startup_update_check():
    import asyncio
    from app.updater import check_for_update, show_update_notification
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, check_for_update, __version__)
    if info:
        show_update_notification(ui, info)

if __name__ in ("__main__", "__mp_main__"):
    # native(pywebview) 시도 → 실패 시 browser 모드 폴백
    native_available = False
    try:
        import webview; native_available = True
    except ImportError: pass

    if native_available:
        try:
            ui.run(native=True, title="당근 광고 기획 도우미",
                   window_size=(1320, 900), storage_secret=storage_secret, reload=False)
        except Exception:
            native_available = False

    if not native_available:
        ui.run(native=False, port=8080, title="당근 광고 기획 도우미",
               storage_secret=storage_secret, reload=False)
```

---

## 6. 인스톨러 / 빌드 설정

### 6-1. installer.iss (Inno Setup) 핵심 설정

```ini
AppId={{B226DDC9-CC73-42D2-BB7C-5643C7E24005}
AppName=당근 광고 기획 도우미
AppVersion=1.0.0
AppPublisher=이프컴퍼니
AppPublisherURL=https://github.com/hafrli1203-lang/dang
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
PrivilegesRequired=lowest
```

- 커스텀 "API 키 설정" 페이지: 설치 시 Anthropic/Gemini 키 입력 → .env 자동 생성
- 바로가기 아이콘: `app_icon.ico` 연결 완료

### 6-2. build.py (PyInstaller)

```
python build.py              # onedir 모드 (기본)
python build.py --onefile    # 단일 exe
python build.py --clean      # 캐시 초기화

출력: dist/당근광고도우미/ (186 MB)
```

- `app_icon.ico` 존재 시 자동 사용
- NiceGUI, matplotlib, docx 데이터 자동 수집
- hidden imports: anthropic, google.genai, openpyxl, dotenv, 앱 모듈들

---

## 7. 테스트 현황

### 실행 방법

```bash
cd daangn_ad_reporter
python -m unittest app.reporting.test_docx_report app.ai.test_providers app.test_updater -v
```

### 테스트 목록 (총 42개, 통과 36/42)

#### DOCX 보고서 테스트 — 19/19 통과 ✅

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | TestMakeCharts.test_creates_three_charts | 차트 3개 PNG 생성 확인 |
| 2 | TestMakeCharts.test_landing_mode_charts | 랜딩 모드 차트 확인 |
| 3 | TestMakeCharts.test_reaction_mode_charts | 반응 모드 차트 확인 |
| 4 | TestMakeCharts.test_no_impressions_still_generates | 노출 데이터 없어도 차트 생성 |
| 5 | TestMakeCharts.test_empty_input_returns_empty | 빈 입력 시 빈 목록 반환 |
| 6 | TestBuildReportDocx.test_creates_file_above_20kb | 보고서 파일 크기 검증 |
| 7 | TestBuildReportDocx.test_returns_output_path | 출력 경로 반환 검증 |
| 8 | TestBuildReportDocx.test_creates_parent_dirs | 상위 디렉토리 자동 생성 |
| 9 | TestBuildReportDocx.test_custom_chart_dir | 커스텀 차트 경로 |
| 10 | TestBuildReportDocx.test_landing_mode_report | 랜딩 모드 보고서 |
| 11 | TestBuildReportDocx.test_reaction_mode_report | 반응 모드 보고서 |
| 12-19 | TestBuildPlanningDocx + TestMissingOrNoneFields | 기획서 + 에지 케이스 |

#### AI Provider 테스트 — 9/15 (Claude 7✅, Gemini 5❌, Factory 1✅+1❌)

| # | 테스트 | 상태 | 비고 |
|---|--------|------|------|
| 1 | ClaudeProvider.test_generate_text_returns_content | ✅ | |
| 2 | ClaudeProvider.test_respects_model_env_var | ✅ | |
| 3 | ClaudeProvider.test_explicit_model_overrides_env | ✅ | |
| 4 | ClaudeProvider.test_raises_without_api_key | ✅ | |
| 5 | ClaudeProvider.test_custom_max_tokens | ✅ | |
| 6 | ClaudeProvider.test_system_prompt_passed_to_api | ✅ | |
| 7 | ClaudeProvider.test_no_system_key_when_none | ✅ | |
| 8-12 | GeminiProvider.* (5개) | ❌ | `google-genai` 미설치 환경 |
| 13 | GetProvider.test_returns_claude_provider | ✅ | |
| 14 | GetProvider.test_returns_gemini_provider | ❌ | `google` import 실패 |
| 15 | GetProvider.test_raises_on_unknown_engine | ✅ | |

> **Gemini 테스트 실패 원인**: 현재 개발 환경에 `google-genai` 패키지 미설치.
> `pip install google-genai` 후 재실행하면 전부 통과 예상됨.

#### Updater 테스트 — 8/8 통과 ✅

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | TestParseVersion.test_standard_version | "1.2.3" → (1,2,3) |
| 2 | TestParseVersion.test_v_prefix | "v2.0.1" → (2,0,1) |
| 3 | TestParseVersion.test_two_parts | "1.5" → (1,5) |
| 4 | TestParseVersion.test_empty_string | "" → (0,) |
| 5 | TestCheckForUpdate.test_disabled_when_no_repo | REPO="" → None |
| 6 | TestCheckForUpdate.test_newer_version_available | 새 버전 감지 |
| 7 | TestCheckForUpdate.test_same_version_returns_none | 동일 버전 → None |
| 8 | TestCheckForUpdate.test_network_error_returns_none | 네트워크 오류 → None |

---

## 8. 환경 설정

### requirements.txt
```
nicegui>=2.0.0
anthropic>=0.40.0
google-genai>=1.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
openpyxl>=3.1.0
python-docx>=1.1.0
matplotlib>=3.8.0
# pywebview — optional (네이티브 데스크톱)
# docx2pdf — optional (PDF 변환)
```

### .env (필수 환경변수)
```
ANTHROPIC_API_KEY=sk-ant-...    # Claude 사용 시 필수
GEMINI_API_KEY=AIza...          # Gemini 사용 시 필수
CLAUDE_MODEL=claude-opus-4-6    # 선택 (기본값 있음)
GEMINI_MODEL=gemini-2.5-pro-preview-05-06  # 선택 (기본값 있음)
STORAGE_SECRET=any-secret-string  # NiceGUI 저장소 암호
```

---

## 9. 최근 완료된 작업 (최종 세션)

| # | 작업 | 변경 파일 | 내용 |
|---|------|-----------|------|
| 1 | GITHUB_REPO 설정 | `app/updater.py:25` | `""` → `"hafrli1203-lang/dang"` |
| 2 | 앱 아이콘 제작 | `app_icon.ico` (신규) | Pillow로 생성, 7 사이즈 (16~256px), 주황 배경+당근+AD |
| 3 | 아이콘 연결 | `installer.iss:36,55,58,60` | SetupIconFile + 바로가기 IconFilename 연결 |
| 4 | AppId GUID 변경 | `installer.iss:21` | 임시값 → `{B226DDC9-CC73-42D2-BB7C-5643C7E24005}` |
| 5 | URL 업데이트 | `installer.iss:16` | 플레이스홀더 → 실제 GitHub 저장소 URL |
| 6 | HANDOFF 갱신 | `HANDOFF.md` | 남은 TODO 3개 → 모두 [x] 완료 |

---

## 10. 검증 요청 항목

GPT Pro에게 아래 항목들을 검증받고 싶습니다:

### 코드 품질
- [ ] Provider 패턴(BaseProvider → Claude/Gemini)의 설계가 적절한가?
- [ ] system_prompt 분리 방식이 보안상 안전한가?
- [ ] calc_kpi() 의 0 나누기 처리가 충분한가?
- [ ] SQLite CRUD 함수들의 SQL 인젝션 방어가 적절한가?

### 아키텍처
- [ ] ai_engine.py(프롬프트) ↔ providers.py(API 호출) 분리가 적절한가?
- [ ] NiceGUI 페이지 구조 (main에서 import로 등록)가 관례에 맞는가?
- [ ] PyInstaller 번들 감지 (IS_FROZEN/BUNDLE_DIR/APP_DIR) 로직이 견고한가?

### 보안
- [ ] API 키가 코드에 하드코딩되어 있지 않은가?
- [ ] .env 파일이 실수로 배포되지 않도록 방어되어 있는가?
- [ ] Inno Setup의 .env 생성 로직에 보안 이슈가 없는가?
- [ ] updater의 GitHub API 호출에 MITM 방어가 필요한가?

### 배포
- [ ] PyInstaller hidden imports 목록이 충분한가?
- [ ] Inno Setup AppId GUID가 올바르게 설정되었는가?
- [ ] 자동 업데이트 체커가 프로덕션 레벨로 충분한가?

### 테스트
- [ ] 테스트 커버리지가 핵심 로직을 충분히 다루는가?
- [ ] 에지 케이스 (빈 입력, None 값, 네트워크 오류) 처리가 적절한가?
- [ ] Gemini 테스트가 환경 미설치 시에도 skip 처리가 필요한가?

---

## 11. 실행 및 검증 명령어

```bash
# 1. 앱 실행
cd daangn_ad_reporter
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python main.py

# 2. 단위 테스트
python -m unittest app.reporting.test_docx_report -v
python -m unittest app.test_updater -v
python -m unittest app.ai.test_providers -v  # google-genai 설치 필요

# 3. DOCX 샘플 검증
python verify_reports.py          # → verify_성과보고서.docx + verify_기획서.docx
python verify_reports.py --pdf    # → PDF 변환 (docx2pdf + MS Word 필요)

# 4. PyInstaller 빌드
python build.py                   # → dist/당근광고도우미/
python build.py --onefile         # → dist/당근광고도우미.exe

# 5. Inno Setup 인스톨러
ISCC installer.iss                # → installer_output/당근광고도우미_Setup_1.0.0.exe
```
