# 🥕 당근 광고 기획 도우미

로컬 1인용 **당근마켓 광고 기획 + 성과 보고서 자동 작성** 앱.
Claude / Gemini AI를 사용해 기획서와 성과 분석 보고서를 자동 생성하고 DOCX로 저장합니다.

---

## 빠른 시작

### Windows

```bat
cd daangn_ad_reporter
start_windows.bat
```

> 최초 실행 시 가상환경 생성 + 패키지 설치가 자동으로 진행됩니다.
> `.env` 파일이 없으면 `.env.example` 을 복사해 주므로, API 키를 입력 후 재실행하세요.

### macOS / Linux

```bash
cd daangn_ad_reporter
chmod +x start_mac.sh
./start_mac.sh
```

### 수동 실행

```bash
cd daangn_ad_reporter
python -m venv venv
# Windows: venv\Scripts\activate  / macOS: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API 키 입력
python main.py
```

---

## API 키 설정

`.env` 파일을 열어 아래 값을 입력하세요.

```dotenv
ANTHROPIC_API_KEY=sk-ant-...        # Anthropic Console에서 발급
GEMINI_API_KEY=AIza...              # Google AI Studio에서 발급

# 선택: 모델 ID 재정의 (기본값은 아래와 같음)
CLAUDE_MODEL=claude-opus-4-6
GEMINI_MODEL=gemini-3.1-pro-preview
```

> 둘 중 하나만 입력해도 해당 엔진만 사용할 수 있습니다.

---

## 화면 구성

| 화면 | URL | 설명 |
|---|---|---|
| 프로젝트 관리 | `/` | 광고주 정보 입력·저장·수정 |
| 광고 기획 | `/planning` | AI 기획서 + 소식글 + 카피 생성, DOCX 저장 |
| 성과 보고서 | `/report` | 엑셀/수기 성과 입력, KPI 계산, AI 분석, DOCX 저장 |

---

## 파일 구조

```
daangn_ad_reporter/
├── main.py                      # 진입점 (python main.py)
├── requirements.txt
├── .env.example
├── start_windows.bat
├── start_mac.sh
├── verify_sample.py             # DOCX 생성 검증 스크립트
├── daangn_ads.db                # SQLite DB (첫 실행 시 자동 생성)
└── app/
    ├── database.py              # SQLite CRUD
    ├── ai_engine.py             # 프롬프트 빌더 + KPI 계산
    ├── export.py                # 기획서 DOCX + 차트 미리보기
    ├── common.py                # 공통 UI 컴포넌트
    ├── ai/
    │   ├── __init__.py
    │   └── providers.py         # ClaudeProvider / GeminiProvider 추상화
    ├── reporting/
    │   ├── __init__.py
    │   ├── docx_report.py       # 독립 보고서 DOCX 생성 모듈
    │   └── test_docx_report.py  # 단위 테스트 (API 키 불필요)
    └── pages/
        ├── project.py           # 화면 1: 프로젝트 관리
        ├── planning.py          # 화면 2: 광고 기획
        └── report.py            # 화면 3: 성과 보고서
```

---

## DOCX 다운로드

- **성과 보고서 화면**: "📊 보고서 생성" 클릭 → AI 분석 후 **브라우저 자동 다운로드**
- "📄 DOCX 저장" 버튼으로 기존 보고서를 재다운로드 가능
- **기획서 화면**: 생성 후 "📄 DOCX 저장" 버튼 → `~/Downloads/` 에 저장
- 파일명: `기획서_{광고주명}.docx` / `성과보고서_{광고주명}.docx`

---

## 테스트 방법

### 단위 테스트 — API 키 불필요

```bash
cd daangn_ad_reporter
# Windows
venv\Scripts\activate
python -m unittest app.reporting.test_docx_report -v

# macOS / Linux
source venv/bin/activate
python -m unittest app.reporting.test_docx_report -v
```

10개 테스트가 모두 통과하면 정상입니다 (약 3–5초 소요).

### 샘플 DOCX 생성 검증

API 키 없이도 DOCX 출력 구조를 확인할 수 있습니다.

```bash
python verify_sample.py
```

실행 후 현재 폴더에 두 파일이 생성됩니다:
- `sample_기획서.docx`
- `sample_성과보고서.docx`

### 신규 보고서 모듈 빠른 확인

```bash
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
print('OK: verify_reporting.docx 생성됨')
"
```

---

## 성과 엑셀 업로드 형식

| 기간 | 비용(원) | 노출 | 클릭 | 문의 | 단골 | 쿠폰 |
|---|---|---|---|---|---|---|
| 1주차 | 75000 | 12000 | 480 | 18 | 3 | 5 |
| 2주차 | 75000 | 13500 | 540 | 21 | 4 | 7 |

- 1행 = 헤더 (자동 스킵)
- 열 순서 고정: A=기간, B=비용, C=노출, D=클릭, E=문의, F=단골, G=쿠폰
- 성과 보고서 화면의 **"샘플 템플릿 생성"** 버튼으로 양식 파일을 받을 수 있습니다

---

## 자주 묻는 질문

**Q. 앱 창이 안 뜨고 브라우저로 열려요.**
A. `main.py`는 `pywebview`가 없거나 실패할 때 자동으로 브라우저 모드로 전환합니다.
브라우저에서 `http://localhost:8080` 을 열면 기능은 완전히 동일합니다.

> **Windows 네이티브 모드 알림**: 네이티브 창(`native=True`)은 내부적으로
> WebView2(Edge) 런타임을 사용합니다. WebView2가 설치되지 않았거나
> .NET 런타임 구성 문제가 있으면 창이 열리지 않을 수 있습니다.
> 이 경우 앱은 자동으로 브라우저 모드로 폴백하므로 별도 조치 없이 사용 가능합니다.

**Q. 한글이 깨진 차트가 나와요.**
A. Windows는 "맑은 고딕"이 자동 적용됩니다. 다른 OS에서는 `NanumGothic` 설치를 권장합니다.

**Q. 데이터는 어디에 저장되나요?**
A. `daangn_ads.db` (SQLite) 한 파일에 모두 저장됩니다. 백업은 이 파일 복사로 충분합니다.
