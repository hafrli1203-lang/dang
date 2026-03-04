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
    │   ├── news_post_guard.py   # 소식글 검증 (의심해소/가성비) — default 카테고리
    │   ├── image_provider.py    # GeminiImageProvider (Nano Banana 썸네일) + get_image_failure_guide()
    │   ├── nanobanana_prompt.py # Style Fusion / Image Mapping 프롬프트
    │   ├── text_overlay.py     # PIL 텍스트 오버레이 (한국어 폰트 + 그림자 + CTA 배지)
    │   └── test_providers.py    # providers 모킹 테스트 (35개)
    │
    ├── content/                 # 콘텐츠 검증 모듈
    │   ├── __init__.py
    │   ├── news_post_rules.py   # 소식글 검증 (Type B/C) — restaurant 카테고리
    │   └── test_news_post_rules.py  # 18개 테스트
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
        ├── planning.py          # 화면 2: 광고 기획 (+ SYSTEM_GUIDE_PLANNING + 썸네일 패널)
        ├── report.py            # 화면 3: 성과 보고서 (+ SYSTEM_GUIDE_REPORT)
        └── thumbnail.py         # 화면 4: 썸네일 이미지 생성 (Gemini + 히스토리)
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
- [x] **전체 133/133 테스트 통과** (docx 19 + providers 35 + guard 34 + rules 18 + parsers 9 + paths 13 + updater 8).

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

---

## 2026-03-04: P0 통합 — AppData 경로 + ExportManager + Nano Banana

### 데이터 경로 (AppData)

모든 사용자 데이터는 `%LOCALAPPDATA%\daangn_ad_reporter`에 저장된다:

| 용도 | 경로 |
|------|------|
| DB | `%LOCALAPPDATA%\daangn_ad_reporter\daangn_ads.db` |
| DOCX 내보내기 | `...\exports\` |
| 차트 PNG | `...\charts\` |
| 썸네일 PNG | `...\thumbnails\` |
| NiceGUI 스토리지 | `...\storage\` |
| 로그 | `...\app.log` |

- `app/paths.py`: `platformdirs.user_data_dir()` 기반, `sanitize_filename()`, `ensure_dirs()` 포함
- `app/database.py`: `_migrate_legacy_db()` — 앱 폴더의 레거시 DB를 AppData로 1회 마이그레이션
- `main.py`: `ensure_dirs()` 호출 + `migrate_legacy_files()`로 .env 마이그레이션

### 내보내기 UX (네이티브 vs 브라우저)

`app/export_manager.py` → `ExportManager` 클래스가 모든 저장 로직 통합:

| 메서드 | 네이티브 모드 (pywebview) | 브라우저 모드 |
|--------|---------------------------|---------------|
| `save_default()` | AppData에 파일 저장 + "폴더 열기" 다이얼로그 | AppData 저장 + `ui.download()` 브라우저 다운로드 |
| `save_as()` | pywebview SAVE_DIALOG → 사용자 선택 경로 | `ui.download()` fallback |
| `save_as_multi()` | 파일마다 SAVE_DIALOG | 파일마다 `ui.download()` |

- `app/native_dialogs.py`: `is_native_available()`, `ask_save_path()`, `open_folder()`
- `app/common.py`: backward-compat wrapper (`safe_download` → `ExportManager.save_default` delegate)
- 페이지 파일: `planning.py`, `report.py`, `thumbnail.py` 모두 `ExportManager` 직접 사용

### Gemini 모델 설정

| 용도 | env var | 기본값 |
|------|---------|--------|
| 텍스트 생성 | `GEMINI_MODEL` | `gemini-3.1-pro-preview` |
| providers.py 이미지 | `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` |
| image_provider.py 썸네일 | `GEMINI_IMAGE_MODEL` | `gemini-3-pro-image-preview` (Nano Banana) |

### 테스트 결과

```
docx_report:  19/19 OK
providers:    26/26 OK
parsers:       8/8  OK
updater:       8/8  OK
합계:         82/82 OK (15 skipped)
```

### 남은 TODO

**P0-1: 업로드/에러 안정화** — 모두 완료
- [x] CSV/XLSX 업로드 시 인코딩 자동 감지 개선 (cp949 이외 EUC-KR 등) → euc-kr, utf-16 추가 + charset-normalizer fallback
- [x] 대용량 파일 업로드 시 프로그레스 표시 → spinner + max_file_size=50MB + run_in_executor
- [x] AI API 타임아웃/네트워크 오류 시 재시도 UX → `retry_api_call()` 유틸리티 (지수 백오프 + Retry-After 파싱)

**P1: 소식글 강제 출력 포맷** — 모두 완료
- [x] 검증 실패 시 사용자에게 누락 항목 시각적 표시 → 검증 배너 (초록/빨강) + ui.notify
- [x] 자동 보정 2회 이상 재시도 옵션 → "재보정 시도" 버튼 (수동 재시도, default + restaurant 모두 지원)
- [x] 카테고리별 검증 규칙 분리 → default(news_post_guard) + restaurant(news_post_rules)

**P1: Gemini 안정화** — 모두 완료
- [x] Gemini API rate limit 대응 (429 → 자동 대기/재시도) → `retry_api_call()` + `_is_transient()` + `_parse_retry_after()`
- [x] 이미지 생성 실패 시 프롬프트 가이드라인 자동 제안 → `get_image_failure_guide()` (safety/empty/rate/timeout/server 분류)

**P2: Nano Banana 썸네일** — 모두 완료
- [x] 생성된 이미지 히스토리 관리 (세션 내 되돌리기) → 최대 10장, 클릭으로 복원 (planning + thumbnail 페이지)
- [x] 텍스트 오버레이 후처리 (PIL/Pillow로 카피 합성) → `app/ai/text_overlay.py` (한국어 폰트 + 그림자 + CTA 배지)
- [x] 다중 비율 동시 생성 (1:1 + 4:5 + 9:16 한번에) → multi-select UI + 순차 생성 + 그리드 표시

---

## 2026-03-04: Commit 3 — 소식글 강제 출력 + 검증/리페어 루프

### 완료 항목

**Commit 3-1 ~ 3-4 (이전 세션)**
- `app/ai/news_post_guard.py` — FORCED_TEMPLATE, validate_news_post(), build_news_post_repair_prompt()
- `app/ai_engine.py` — build_planning_prompt()에서 format_forced_template() 호출
- `app/pages/planning.py` — 검증 + 자동 보정 루프 (최대 2회 retry)
- `app/ai/test_news_post_guard.py` — 15개 기본 테스트

**Commit 3-5: UI 표시 개선 + "both" 엔진 버그 수정**
- 탭 UI: 전체 보기 / 소식글 1 (의심해소) / 소식글 2 (가성비) 탭 분리
- 복사 버튼: 각 소식글 탭에 클립보드 복사 버튼 (`navigator.clipboard.writeText`)
- 검증 배너: 상단에 초록(통과) / 빨강(미달 N건) 배너 표시
- "both" 버그 수정: `engine == "both"` 시 검증 건너뛰기 (비교 용도)
- 파싱 헬퍼: `_parse_planning_sections()` — 의심해소/가성비/기획요약/카피 분리

**Commit 3-6: 테스트 보강 (15 → 25개)**
- `TestSplitBlocks` (3개): 정상 분리, 빈 입력, 단일 블록
- `TestExtractBodyText` (3개): FAQ/고지 제거, CTA 제거, 제목 제거
- `TestValidateNewsPost` 추가 (4개): 금지어 "전부"/"절대 추가금 없음", 제목 누락, 줄바꿈 부족

### 변경 파일

| 파일 | 변경 |
|------|------|
| `app/pages/planning.py` | 탭 UI, 복사, 검증 배너, "both" 버그 수정 |
| `app/ai/test_news_post_guard.py` | 10개 테스트 추가 |
| `HANDOFF.md` | Commit 3 섹션 추가 |

### 검증 결과
```
전체 테스트: 102/102 OK
  news_post_guard: 29/29
  providers:       26/26
  docx_report:     19/19
  parsers:          8/8
  paths:           13/13 (5 skipped)
  updater:          8/8 (1 skipped)

통합 스모크 테스트:
  format_forced_template: OK (placeholder 치환)
  _parse_planning_sections: OK (양쪽 버전 + 빈 입력)
  validate_news_post: OK (금지어 4종 감지)
```

### 알려진 이슈 (해결됨)
- ~~`news_post_guard.py` 내부 repair 루프의 `if engine == "both"` 분기가 dead code~~ → 제거됨
- ~~저장된 콘텐츠 로드 시 검증 배너 미표시~~ → 저장 콘텐츠 로드 시 재검증 추가

---

## 2026-03-04: Commit 3-7 — Type B/C 검증기 통합 (restaurant 카테고리)

### 개요

`restaurant` 카테고리(오프라인 음식점)에 Type B(긴급성) / Type C(가성비) 소식글 검증 + 자동 보정 루프를 연결.

### 신규 파일

| 파일 | 설명 |
|------|------|
| `app/content/__init__.py` | 콘텐츠 검증 패키지 |
| `app/content/news_post_rules.py` | Type B/C 검증기 — `validate_news_post()`, `build_news_repair_prompt()` |
| `app/content/test_news_post_rules.py` | 18개 테스트 (pass/fail/split/repair) |

### 변경 파일

| 파일 | 변경 |
|------|------|
| `app/pages/planning.py` | Type B/C 검증 import + restaurant 카테고리 검증/보정 루프 + 저장 콘텐츠 자동 감지 |

### 검증 규칙 (news_post_rules.py)

- `[소식글 Type C(가성비)]` + `[소식글 Type B(긴급성)]` 헤더 필수
- 각 블록: 제목/본문/CTA/FAQ/고지 하위 섹션 필수
- 본문 최소 900자, CTA 키워드(채팅/문의/쿠폰/단골/예약) 포함
- FAQ 최소 3쌍 (Q1-A1, Q2-A2, Q3-A3)
- 금지어: "무조건", "전부", "절대 추가금 없음", "100%"

### 검증 분기 로직

| 카테고리 | 엔진 | 검증기 | 동작 |
|----------|------|--------|------|
| `default` | claude/gemini | `news_post_guard` | 의심해소 + 가성비 검증 |
| `restaurant` | claude/gemini | `news_post_rules` | Type B + Type C 검증 |
| any | `both` | — | 검증 건너뛰기 (비교 용도) |
| 기타 | any | — | 검증 없음 |

저장 콘텐츠 로드 시: `[소식글 Type B/C` 헤더 감지 → `news_post_rules`, 그 외 → `news_post_guard`

### 검증 결과
```
전체 테스트: 125/125 OK
  news_post_guard:  34/34
  news_post_rules:  18/18
  providers:        26/26
  docx_report:      19/19
  parsers:           8/8
  paths:            13/13
  updater:           8/8 (1 skipped)
```

### 다음 커밋
- ~~**Commit 4**: Gemini 텍스트 연동 강화~~ (완료)
- ~~**Commit 5**: 나노바나나 썸네일 플로우~~ (완료)

---

## 2026-03-04: 광고 운영 제안서 생성기 + 스트리밍 (커밋 1~5)

### 개요

7섹션 구조의 전문 광고 운영 제안서를 AI로 자동 생성하는 기능 추가.
Claude/Gemini 스트리밍 지원, 섹션별 재생성/편집, DOCX 내보내기 포함.

### 커밋 1: Proposal Prompt Engine (`ai_engine.py`)

**추가된 상수/함수:**

| 항목 | 설명 |
|------|------|
| `SYSTEM_GUIDE_PROPOSAL` | 7섹션 구조 시스템 가이드 (system 메시지 전용) |
| `_PROPOSAL_PROMPT` | 제안서 생성 프롬프트 템플릿 |
| `_PROPOSAL_SECTION_NAMES` | 7개 섹션 한국어 이름 dict |
| `_PROPOSAL_SECTION_KEYS` | 7개 섹션 키 리스트 (순서 보장) |
| `build_proposal_prompt()` | (shop_info, promo_text, target_age, prev_csv_rows, prev_summary) → (system, user) 튜플 |
| `parse_proposal_sections()` | 마크다운 → {section_key: section_text} dict (7개 키) |
| `build_proposal_section_prompt()` | 단일 섹션 재생성 프롬프트 |

**7섹션 구조:**
1. 요약 (summary)
2. 이전 캠페인 성과 분석 (prev_performance)
3. 병목 진단 (bottleneck)
4. KPI 목표 (kpi_goals)
5. 전략 제안 (strategy)
6. 집행 설계 (execution)
7. 소재/소식글 방향 (creative)

**이전 성과 데이터 처리:**
- CSV rows 전달 시: `calc_kpi()` → KPI 테이블 자동 주입
- prev_summary만 전달 시: 텍스트 그대로 주입
- 둘 다 없으면: "신규 캠페인 — 이전 집행 데이터 없음" 폴백

### 커밋 2: DB content_type 필터 + Proposal DOCX

**`database.py` 변경:**

```python
# 기존 함수에 content_type 파라미터 추가 (기본값: "planning" → 하위호환)
save_generated_content(project_id, engine, content, content_type="planning")
get_latest_content(project_id, content_type="planning")

# 마이그레이션 (init_db)
ALTER TABLE generated_content ADD COLUMN content_type TEXT DEFAULT 'planning'
```

- `content_type="proposal"` 로 저장/조회하면 planning 콘텐츠와 분리
- 기존 코드는 기본값 "planning"으로 변경 없이 동작

**`docx_report.py` 추가:**

```python
def build_proposal_docx(
    shop_info: dict,          # shop_name, industry, location
    sections: dict[str, str], # parse_proposal_sections() 결과
    output_path: Path,
    kpi: dict | None = None,  # calc_kpi() 결과 (선택)
) -> Path:
```

- 표지: 점포명 + 업종 + 위치 + 생성일
- 7개 섹션을 Heading 1 + 본문으로 렌더링
- KPI 데이터 전달 시 섹션 2에 테이블 삽입

### 커밋 3: Planning 페이지 탭 구조

**`planning.py` 변경:**

```
/planning 페이지 구조:
├── 프로젝트 선택 바 (기존)
├── ui.tabs
│   ├── "소식글 기획" 탭 → 기존 코드 전체 (inline 래핑)
│   └── "운영 제안서" 탭 → proposal_tab.build_proposal_tab()
└── 진단 패널 (기존)
```

- 기존 소식글 코드를 `with ui.tab_panel(tab_news):` 안에 그대로 래핑
- 로직 변경 없음 — 순수 구조적 래핑만 적용
- `proposal_tab.py`는 lazy import

### 커밋 4: Proposal Tab UI (`proposal_tab.py`)

**파일: `app/pages/proposal_tab.py` (~512줄)**

```
build_proposal_tab()
├── 입력 폼
│   ├── 점포명 / 업종 / 위치 (프로젝트에서 자동 채움)
│   ├── 프로모션/상품 정보 (textarea)
│   ├── 타겟 연령대 (select: 전연령~60대 이상)
│   ├── CSV 업로드 → parse_daangn_csv() 자동 파싱
│   └── 수동 요약 (CSV 없을 때)
├── AI 엔진 선택 (claude / gemini / both)
├── "제안서 생성" 버튼
│   ├── both: asyncio.gather로 Claude+Gemini 동시 호출
│   └── 단일: queue.Queue + ui.timer(0.2) 스트리밍 브릿지
├── 결과 표시
│   ├── "전체 보기" 탭: 마크다운 전문
│   └── "섹션별 보기" 탭: 7개 ui.expansion 패널
│       ├── 편집 토글 (마크다운 ↔ textarea)
│       ├── 편집 완료 → DB 자동 저장
│       └── 재생성 버튼 → _regen_section()
├── DOCX 내보내기
│   ├── "기본 폴더에 저장" → ExportManager.save_default()
│   └── "다른 위치로 저장" → ExportManager.save_as()
└── DB 저장/로드 (content_type="proposal")
```

**핵심 패턴:**
- `run_in_executor`로 동기 provider 호출을 async 래핑
- `_render_sections(container, state, full_md, gen_btn, progress_label, regen_fn)` — 외부 함수
- 저장된 콘텐츠 로드는 모든 핸들러 정의 후 실행 (closure 안정성)

### 커밋 5: 스트리밍 강화 (`providers.py` + `proposal_tab.py`)

**`providers.py` 추가:**

```python
class BaseProvider:
    def generate_text_stream(self, prompt, *, system_prompt=None):
        """NON-abstract. 기본: generate_text() 결과를 단일 chunk로 yield."""
        yield self.generate_text(prompt, system_prompt=system_prompt)

class ClaudeProvider:
    def generate_text_stream(self, prompt, *, system_prompt=None):
        """SDK messages.stream() 사용."""
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

class GeminiProvider:
    def generate_text_stream(self, prompt, *, system_prompt=None):
        """SDK generate_content_stream() 사용."""
        for chunk in self._client.models.generate_content_stream(**kwargs):
            if chunk.text:
                yield chunk.text
```

- `generate_text()` 완전 불변 (기존 코드 영향 없음)
- 스트리밍 미지원 provider는 자동 폴백 (단일 chunk yield)

**스트리밍 브릿지 패턴 (`proposal_tab.py`):**

```
Background thread:                    UI thread:
  provider.generate_text_stream()  →  queue.Queue  →  ui.timer(0.2)
  chunk → queue.put(chunk)                             _poll_chunks()
  None  → queue.put(None) sentinel                     stream_md.set_content()
                                                       progress: "섹션 N/7"
```

- `queue.Queue` + `ui.timer(0.2)`로 NiceGUI 이벤트 루프와 동기화
- 섹션 진행률 표시: `## ` 패턴 카운트 → "섹션 N/7 생성 중..."
- 에러 전파: Exception 객체를 queue에 넣어 UI 스레드에서 re-raise

### 변경 파일 요약

| 파일 | 커밋 | 변경 |
|------|------|------|
| `app/ai_engine.py` | 1 | SYSTEM_GUIDE_PROPOSAL + 프롬프트 빌더 3개 |
| `app/database.py` | 2 | content_type 파라미터 + ALTER TABLE 마이그레이션 |
| `app/reporting/docx_report.py` | 2 | build_proposal_docx() 추가 (~100줄) |
| `app/reporting/test_docx_report.py` | 2 | TestBuildProposalDocx 5개 테스트 |
| `app/pages/planning.py` | 3 | 탭 구조 래핑 (소식글/제안서) |
| `app/pages/proposal_tab.py` | 4,5 | **신규** — 전체 제안서 UI + 스트리밍 (~512줄) |
| `app/ai/providers.py` | 5 | generate_text_stream() 3개 클래스 |
| `app/ai/test_providers.py` | 5 | 스트리밍 테스트 5개 추가 |

### 검증 결과

```
전체 테스트: 147/147 OK (21초)
  providers:        31/31  (기존 26 + 스트리밍 5)
  docx_report:      24/24  (기존 19 + 제안서 5)
  news_post_guard:  34/34
  news_post_rules:  18/18
  parsers:           9/9
  paths:            13/13
  updater:           8/8
  chart:             8/8
```

### 알려진 이슈

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| `.env`의 `GEMINI_IMAGE_MODEL=gemini-2.0-flash-preview-image-generation` 모델 404 | P1 | `.env`에서 해당 줄 삭제 또는 `gemini-2.5-flash-image`로 변경 필요 |
| `_poll_chunks` 에러 시 timer 미해제 | P3 | 로깅은 추가됨, timer.deactivate() 추가 권장 |

### 아키텍처 다이어그램 (최종)

```
main.py (entry)
  ↓
NiceGUI app (port 8080)
  ├─ /project    → project.py
  ├─ /planning   → planning.py
  │    ├─ [소식글 기획] 탭
  │    │    ├─ AI 생성 (Claude/Gemini/both)
  │    │    ├─ 소식글 검증 (news_post_guard / news_post_rules)
  │    │    ├─ 자동 보정 루프 (최대 2회)
  │    │    └─ 썸네일 생성 (Nano Banana + text_overlay)
  │    └─ [운영 제안서] 탭
  │         └─ proposal_tab.py
  │              ├─ 입력 → build_proposal_prompt()
  │              ├─ generate_text_stream() → queue+timer 브릿지
  │              ├─ parse_proposal_sections() → 7섹션 패널
  │              ├─ 섹션별 편집/재생성
  │              └─ build_proposal_docx() → ExportManager
  ├─ /report     → report.py (CSV/XLSX → 성과보고서)
  └─ /thumbnail  → thumbnail.py (Gemini 이미지)

AI Layer
  ├─ providers.py
  │    ├─ ClaudeProvider  (generate_text + generate_text_stream)
  │    ├─ GeminiProvider  (generate_text + generate_text_stream + generate_image)
  │    └─ retry_api_call() (지수 백오프)
  ├─ ai_engine.py (프롬프트 빌더 + KPI 계산)
  ├─ image_provider.py (Nano Banana 썸네일)
  └─ news_post_guard.py / news_post_rules.py (검증)

Data Layer
  ├─ database.py → SQLite (content_type 필터)
  ├─ parsers.py → CSV 파서 (당근 광고 데이터)
  └─ docx_report.py → DOCX 생성 (성과보고서 + 기획서 + 제안서)
```

---

## 2026-03-04: TODO 전체 완료 — 안정화 + 썸네일 기능 강화

### 개요

HANDOFF.md의 남은 TODO 9건을 전부 구현 완료.

### 변경 파일

| 파일 | 변경 |
|------|------|
| `app/reporting/parsers.py` | EUC-KR/UTF-16 인코딩 추가 + charset-normalizer fallback |
| `app/reporting/test_parsers.py` | `test_euc_kr_csv_parses` 추가 (8→9개) |
| `app/pages/report.py` | 업로드 spinner + max_file_size=50MB + run_in_executor |
| `app/ai/providers.py` | `retry_api_call()`, `_is_transient()`, `_parse_retry_after()` 유틸리티 |
| `app/ai/test_providers.py` | 9개 테스트 추가 (26→35개) + time.sleep 모킹 |
| `app/ai/image_provider.py` | `retry_api_call()` 통합 + `get_image_failure_guide()` 함수 |
| `app/ai/text_overlay.py` | **신규** — PIL 텍스트 오버레이 (한국어 폰트 + 그림자 + CTA 배지) |
| `app/pages/planning.py` | 재보정 버튼 + 이미지 히스토리 + 텍스트 오버레이 체크박스 + 다중 비율 |
| `app/pages/thumbnail.py` | 이미지 히스토리 + 실패 가이드 |
| `HANDOFF.md` | TODO 항목 전체 완료 표시 |

### 신규 기능 상세

**1. CSV 인코딩 자동 감지** — `parsers.py`
- 기존: utf-8-sig, cp949
- 추가: euc-kr, utf-16 + charset-normalizer 라이브러리 fallback (선택 의존성)

**2. 업로드 프로그레스** — `report.py`
- `max_file_size=50_000_000` 제한
- spinner + label 표시
- CSV/XLSX 파싱을 `run_in_executor`로 비동기 처리

**3. API 재시도 유틸리티** — `providers.py`
- `retry_api_call(fn, max_retries=3, base_delay=2.0)` — 지수 백오프
- `_is_transient(exc)` — 429/503/timeout/overloaded 분류
- `_parse_retry_after(exc)` — Retry-After 헤더 파싱
- ClaudeProvider, GeminiProvider (text+image), GeminiImageProvider 모두 통합

**4. 검증 재보정 버튼** — `planning.py`
- "재보정 시도" 버튼 (자동 보정 2회 후 수동 트리거)
- default(news_post_guard) + restaurant(news_post_rules) 모두 지원

**5. 이미지 실패 가이드** — `image_provider.py`
- `get_image_failure_guide(error_msg)` — 에러 메시지 분류 후 한국어 안내
- safety filter / empty response / rate limit / timeout / server overload 5종

**6. 이미지 히스토리** — `planning.py` + `thumbnail.py`
- 세션 내 최대 10장 저장
- 스크롤 가능한 미니 썸네일 스트립
- 클릭으로 이전 이미지 복원

**7. PIL 텍스트 오버레이** — `text_overlay.py`
- 한국어 폰트 자동 탐색 (Malgun Gothic / NanumGothic / AppleGothic)
- 메인 텍스트 (상단 25%) + 서브 텍스트 (중앙 50%) + CTA 배지 (하단 82%)
- 그림자 렌더링 + 반투명 CTA 배경 (alpha compositing)
- planning.py 썸네일 패널에 체크박스 토글로 연동

**8. 다중 비율 동시 생성** — `planning.py`
- `thumb_ratio_sel` → `multiple=True` (멀티 선택)
- 선택한 비율별 순차 생성 (rate limit 방지)
- 그리드 레이아웃으로 결과 표시
- 모든 결과 히스토리에 자동 저장

### 검증 결과

```
전체 테스트: 133/133 OK (24초)
  news_post_guard:  34/34
  news_post_rules:  18/18
  providers:        35/35
  docx_report:      19/19
  parsers:           9/9
  paths:            13/13
  updater:           8/8 (1 skipped)
```
