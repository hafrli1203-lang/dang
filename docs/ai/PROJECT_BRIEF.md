# PROJECT_BRIEF — daangn_ad_reporter

## 한 줄 요약
당근마켓 비즈프로필 소식글 + 광고 기획서·성과보고서·운영제안서를 AI(Claude/GPT CLI 우선)로 자동 생성하는 Python·NiceGUI 데스크톱/웹앱.

## 감지된 스택 (실제 파일 근거)
- 런타임: Python 3.11+ (`main.py`, `__version__ = "1.2.0"`)
- UI: NiceGUI (Quasar/Vue 기반), Paperlogy 폰트 (`app/theme.py`, dg- 클래스)
- AI: anthropic / openai SDK + CLI(claude, codex, gti) 우선 (`app/ai/providers.py`, `coordination.py`)
- DB: SQLite `daangn_ads.db` 4테이블 (projects, generated_content, performance_rows, report_content) (`app/database.py`)
- 보고서: python-docx + matplotlib(Agg, 한글 Malgun Gothic) (`app/reporting/`), 선택적 docx2pdf
- 리서치: requests + beautifulsoup4 + readability-lxml + lxml, 선택적 playwright
- 빌드: PyInstaller + Inno Setup (`build.py`, `daangn.spec`, `installer.iss`)
- 테스트: pytest (`app/test_*.py`, 374개 통과)

## 구조 메모
- 페이지는 import side-effect로 등록(`main.py`): project / planning / report / thumbnail / analysis / research.
- 광고 기획은 `planning_wizard.py` 4단계 위자드(전략분석 → 콘텐츠생성 → 광고세팅 → 운영제안서).
- 성과 분석은 `report.py`(퍼널·MAX CPA·소재 ON/OFF·기간 비교) + `funnel_widget.py`.
- AI 호출은 `get_provider("claude"/"gpt")` / `coordination.py`(조율 종합) 경유 권장.
- 텍스트·이미지 모두 CLI 구독 기본 → API 키 불필요(API 모드는 옵션).

## 아직 모르는 것 (확인 필요)
- 당근 CSV 파서(`app/reporting/parsers.py`) 입력 포맷 케이스 범위
- MAX CPA·소재 ON/OFF 판단 산식의 정합성/엣지케이스
- `app/research/` 수집 파이프라인의 실패/폴백 동작

## 다음 행동
`TASKS.md`의 최우선 1개부터. 기존 `CLAUDE.md` 규칙(회귀 방지·5단계 플로우) 우선.
