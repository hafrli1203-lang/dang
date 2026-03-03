# HANDOFF — daangn_ad_reporter

## 파일 트리

```
daangn_ad_reporter/
├── main.py                      # 진입점 — native→browser 자동 폴백, __version__, IS_FROZEN
├── requirements.txt
├── .env / .env.example          # API 키 설정
├── build.py                     # PyInstaller 빌드 스크립트
├── daangn.spec                  # PyInstaller spec (고급 설정용)
├── installer.iss                # Inno Setup 인스톨러 스크립트
├── start_windows.bat
├── start_mac.sh
├── verify_sample.py             # API 키 없이 DOCX 구조 확인
├── daangn_ads.db                # SQLite DB (첫 실행 시 자동 생성)
│
└── app/
    ├── database.py              # SQLite CRUD (4 tables)
    ├── ai_engine.py             # 프롬프트 빌더 + calc_kpi() + SYSTEM_GUIDE_*
    │                            #   SYSTEM_GUIDE_REPORT / SYSTEM_GUIDE_PLANNING:
    │                            #   내부 운영 가이드 (system 메시지 전용, 문서 노출 금지)
    ├── export.py                # 기획서 DOCX + 차트 미리보기용 make_charts()
    ├── common.py                # 공통 내비게이션 바
    ├── updater.py               # GitHub Releases 자동 업데이트 체크
    ├── test_updater.py          # updater 모킹 테스트 (8개)
    │
    ├── ai/                      # AI 공급자 추상화
    │   ├── __init__.py
    │   ├── providers.py         # BaseProvider / ClaudeProvider / GeminiProvider
    │   │                        #   generate_text(prompt, *, system_prompt=None)
    │   │                        #   Claude: system 파라미터 / Gemini: system_instruction
    │   └── test_providers.py    # providers 모킹 테스트 (15개)
    │
    ├── reporting/               # 독립 보고서 DOCX 모듈
    │   ├── __init__.py
    │   ├── docx_report.py       # make_charts() + build_report_docx() + build_planning_docx()
    │   ├── document_spec.md     # 섹션 순서 + 입력 필드 설계 명세 (v1.0)
    │   └── test_docx_report.py  # DOCX 테스트 (19개)
    │
    ├── templates/               # 기준 DOCX 템플릿 (v1.0 레이아웃)
    │   ├── sample_report.docx
    │   └── sample_plan.docx
    │
    └── pages/
        ├── project.py           # 화면 1: 프로젝트 관리
        ├── planning.py          # 화면 2: 광고 기획 (+ SYSTEM_GUIDE_PLANNING)
        └── report.py            # 화면 3: 성과 보고서 (+ SYSTEM_GUIDE_REPORT)
```

---

## 실행 방법

### Windows

```bat
cd daangn_ad_reporter
start_windows.bat
```

또는 수동:

```bat
cd daangn_ad_reporter
venv\Scripts\activate
python main.py
```

### macOS / Linux

```bash
cd daangn_ad_reporter
./start_mac.sh
# 또는
source venv/bin/activate && python main.py
```

브라우저가 자동으로 열립니다. 열리지 않으면 `http://localhost:8080` 을 수동으로 접속하세요.

> **Windows 네이티브 모드**: `native=True` 는 WebView2(Edge) 런타임이 필요합니다.
> 없거나 .NET 런타임 문제가 있으면 앱이 **자동으로 브라우저 모드로 폴백**합니다.
> 브라우저 모드에서 기능 차이는 없습니다.

---

## 테스트 방법

### 단위 테스트 (API 키 불필요, ~3초)

```bash
# Windows
venv\Scripts\activate
python -m unittest app.reporting.test_docx_report -v

# macOS / Linux
source venv/bin/activate
python -m unittest app.reporting.test_docx_report -v
```

기대 결과:
```
Ran 10 tests in 2.976s
OK
```

### DOCX 구조 육안 확인

```bash
python verify_sample.py
# → sample_기획서.docx, sample_성과보고서.docx 생성

python -c "
from pathlib import Path
from app.reporting.docx_report import build_report_docx
build_report_docx(
    project_meta={'name':'테스트카페','period':'2024.06','goal':'방문증가'},
    kpi={'total_spend':300000,'total_clicks':2050,'total_chats':80,'ctr':3.98,'cpc':146.0,'cpa':3750.0},
    timeseries=[
        {'date':'1주차','spend':75000,'clicks':480,'chats':18,'impressions':12000},
        {'date':'2주차','spend':80000,'clicks':540,'chats':21,'impressions':13500},
    ],
    insights={'summary':'양호한 성과','insights':['CTR 높음'],'actions':['소재 유지']},
    output_path=Path('verify_reporting.docx'),
)
print('OK')
"
# → verify_reporting.docx 생성 후 열어서 표지/KPI표/차트/인사이트 확인
```

---

## 보고서 생성 흐름 (화면 3 /report)

```
사용자: 성과 데이터 입력 (엑셀 업로드 or 수기)
        ↓ KPI 자동 계산 + 차트 미리보기
사용자: AI 엔진 선택 (Claude / Gemini / 둘 다)
사용자: "📊 보고서 생성" 클릭
        ↓ SYSTEM_GUIDE_REPORT (내부 운영 가이드) → system 메시지로 전달
        ↓   Claude: messages.create(system=guide, messages=[...])
        ↓   Gemini: generate_content(config=GenerateContentConfig(system_instruction=guide))
        ↓ providers.py → API 호출 (run_in_executor)
        ↓ 마크다운 분석 결과 → UI 프리뷰 표시
        ↓ _parse_ai_insights() → Insights 구조화
        ↓ build_report_docx() → DOCX 바이트 생성
        → ui.download() → 브라우저 자동 다운로드 + 상태 피드백
(재다운로드) "📄 DOCX 저장" 버튼도 동일 로직
```

### 내부 운영 가이드 (system_prompt 구조)

가이드는 `app/ai_engine.py`에 `SYSTEM_GUIDE_REPORT` / `SYSTEM_GUIDE_PLANNING`으로 정의되며,
**AI API의 system 채널로만 전달**되어 사용자 프롬프트나 문서 출력물에 절대 노출되지 않는다.

| 규칙 | 내용 |
|------|------|
| 톤 | 광고주(사장님)가 1분 안에 핵심 파악 가능한 쉬운 말투 |
| 전문용어 | 첫 등장 시 한국어 병기 (예: CTR(클릭률)), 이후 약어 허용 |
| 성과 요약 | 3~5줄, 각 1~2문장, 핵심 수치 포함 |
| 인사이트 | 정확히 3개, 각 1~2문장, 데이터 근거 필수, 과장 금지 |
| Next Actions | 3~7개, "누가/무엇을/어떻게" 실행 문장 |
| 민감 업종 | 의료·건강·금융·법률: 효과 단정·과장 금지 |
| 메타 노출 금지 | "시스템 프롬프트", "운영 가이드" 등 언급 불가 |

### 필드명 매핑 (DB ↔ docx_report)

| DB / legacy | docx_report 신규 |
|---|---|
| `period_label` | `date` |
| `cost` | `spend` |
| `inquiries` | `chats` |
| `regulars` | `followers` |
| `total_cost` | `total_spend` |
| `total_inquiries` | `total_chats` |
| `total_regulars` | `total_followers` |

---

## TODO 완료 현황

### 기능
- [x] **"both" 엔진 시 Insights 파싱**: Claude + Gemini 각각의 텍스트를 따로 파싱해
      DOCX 2개(`_Claude.docx`, `_Gemini.docx`)를 생성하도록 수정됨.
- [x] **기획서 화면 DOCX**: `planning.py`의 "DOCX 저장"이 `app/reporting/docx_report.build_planning_docx()`
      로 마이그레이션됨. 브라우저 자동 다운로드(`ui.download()`) 방식으로 동작.
- [x] **다운로드 피드백**: 버튼 disabled+loading 상태, 상태 레이블 ("DOCX 파일 준비 중..." → "✅ 파일명 다운로드 시작됨"),
      ui.notify에 close_button="확인" 추가. report.py + planning.py 모두 적용.

### 인프라 / 배포
- [x] **PyInstaller 패키징**: `build.py` + `daangn.spec` 작성.
      `python build.py` (onedir) / `python build.py --onefile` (단일 exe).
      nicegui·matplotlib·docx 데이터 자동 수집, templates/ 포함.
      main.py에 `IS_FROZEN`/`BUNDLE_DIR`/`APP_DIR` 감지 로직 추가.
      빌드 확인됨: `dist/당근광고도우미/당근광고도우미.exe` (186 MB).
- [x] **Windows 인스톨러 (Inno Setup)**: `installer.iss` 작성.
      API 키 입력 커스텀 페이지 포함, .env 자동 생성.
      빌드: `ISCC installer.iss` → `installer_output/당근광고도우미_Setup_1.0.0.exe`.
- [x] **자동 업데이트**: `app/updater.py` — GitHub Releases API 기반.
      `GITHUB_REPO` 변수 설정 시 활성화. main.py `@nicegui_app.on_startup`에서
      백그라운드 체크 후 NiceGUI 알림 표시. 네트워크 오류 시 조용히 무시.

### 품질
- [x] `planning.py` 에도 `app.ai.providers` 직접 연결 완료.
- [x] `ai_engine.py`의 `_call_claude` / `_call_gemini` / `generate()` 제거 완료.
- [x] `providers.py` 모킹 테스트 추가 — `app/ai/test_providers.py` (11 tests).
- [x] `updater.py` 모킹 테스트 추가 — `app/test_updater.py` (8 tests).
- [x] `_annotate_bars()` 버그 수정 — callable fmt 지원 추가.
- [x] `_save_chart()` MemoryError 핸들링 — bbox_inches="tight" 실패 시 fallback.
- [x] **전체 38/38 테스트 통과** (docx 19 + providers 11 + updater 8).

### 남은 TODO
- [x] `app/updater.py`의 `GITHUB_REPO` 변수에 실제 저장소 경로 설정 → `hafrli1203-lang/dang`
- [x] 앱 아이콘 파일 (`app_icon.ico`) 제작 후 build.py / installer.iss 연결 → Pillow로 생성, 멀티사이즈 ICO
- [x] `installer.iss`의 AppId GUID를 실제 고유값으로 변경 → `{B226DDC9-CC73-42D2-BB7C-5643C7E24005}`

---

## 2026-03-03: Save 버튼 분리 (기본 폴더 / Save As)

### 변경 파일 및 함수

| 파일 | 변경 유형 | 함수/항목 |
|------|-----------|-----------|
| `app/exporting.py` | 신규 | `choose_save_path_docx()` — pywebview SAVE_DIALOG 래퍼 |
| `app/common.py` | 수정 | `safe_download()` — 로깅 추가 |
| `app/common.py` | 추가 | `save_as_download()` — Save As 다이얼로그 + browser fallback |
| `app/pages/planning.py` | 수정 | 버튼 분리 + `_build_docx_bytes()`, `_export_default()`, `_export_saveas()` |
| `app/pages/report.py` | 수정 | 버튼 분리 + `_validate_export()`, `_build_report_pairs()`, `_export_default()`, `_export_saveas()` |

### 버튼 동작

| 버튼 | Native 모드 | Browser 모드 |
|------|-------------|--------------|
| 기본 폴더에 저장 (권장) | EXPORTS_DIR 자동 저장 + 파일/폴더 열기 다이얼로그 | `ui.download()` |
| 다른 위치로 저장... | pywebview SAVE_DIALOG → 사용자 선택 경로에 저장 | `ui.download()` |

### 경로 진단

- 모든 저장 이벤트가 `app.log`에 기록됨 (경로, 바이트 수)
- UI "최근 로그 보기" 패널에서 실시간 확인 가능
- `EXPORTS_DIR = %LOCALAPPDATA%/daangn_ad_reporter/exports` → 설치 폴더 쓰기 권한 무관

### 테스트 결과

```
docx_report:  19/19 OK
providers:    18/18 OK
updater:       8/8  OK
합계:         45/45 OK

verify_reports.py:
  verify_성과보고서.docx  207.1 KB — OK
  verify_기획서.docx       36.7 KB — OK
```

### 남은 TODO
- [ ] **Native Save As E2E 테스트**: pywebview 설치 환경에서 `native=True` 실행 후 "다른 위치로 저장..." 클릭 → 파일 다이얼로그 실제 동작 확인
- [ ] **"both" 엔진 Save As UX**: Claude+Gemini 시 Save As 다이얼로그 2회 연속 호출됨. 폴더 선택 방식으로 개선 검토
