# UPGRADE_AUDIT — 당근광고 로컬 SaaS 업그레이드 감사 (2026-06-12)

## 현재 구조 요약

- Python 3.11 + NiceGUI 3.8 + SQLite + Claude/Gemini. PyInstaller/Inno Setup 배포.
- 페이지: 프로젝트 관리(/) > 광고 기획(/planning, 4단계 위자드) > 성과 보고서(/report) > 고급 분석(/analysis) > 썸네일(/thumbnail)
- 룰 엔진은 이미 상당 부분 존재: `app/reporting/demographic.py`
  (연령 묶기 k-means, 캠페인 OFF/증액 판정, 예산 재배분 시뮬레이션,
  자동/수동 페어 체크, 변수 통제 검사, 3종 시트 파서, MAX CPA 역산)
- AI 프롬프트(`ai_engine.py`)에 당근 고수 운영 원칙(연령 분리, 자동/수동, 머신러닝 부재)이 이미 반영됨.

## 발견한 버그 (이번에 수정)

1. **[치명] 프로젝트 전환 핸들러 전멸** — `report.py`, `planning.py`에서
   `select.on("update:model-value", handler)` + `e.value` 패턴 사용.
   NiceGUI 3.x의 GenericEventArguments에는 `.value`가 없어 핸들러가
   `AttributeError`로 죽고 있었음. 페이지 안에서 프로젝트를 바꾸면
   저장 데이터 로드가 전혀 안 됐음. → `on_value_change()`로 교체.
2. **[치명] `kpi_container` 미정의 NameError** — `report.py`의
   `_load_saved_data()`가 존재하지 않는 변수를 참조해서, 핸들러가 살아
   있었어도 저장된 성과 데이터 로드가 죽었을 것. → 실제 카드/컨테이너
   초기화 코드로 교체.
3. **[치명] localhost:8000 포트 가로채기** — 다른 프로젝트의 uvicorn 서버
   (`python -m uvicorn app.main:app --port 8000`, 시스템 Python)가
   127.0.0.1:8000을 선점. 우리 앱은 0.0.0.0에 바인딩되어 에러 없이 뜨지만
   localhost 접속은 전부 그 서버로 가서 `{"detail":"Not Found"}`만 보임.
   → `main.py`에 포트 충돌 감지 + 자동 대체 포트(8001~8009) 로직 추가.
   (현재 이 PC에서는 8002로 뜸. 8000을 쓰려면 다른 uvicorn 서버를 꺼야 함.)

## 깨진/허접했던 사용자 플로우

- 성과 보고서 페이지에서 프로젝트 선택 → 아무 일도 안 일어남 (버그 1+2)
- KPI가 14개 숫자 나열 grid → 증감/맥락 없음
- 퍼널이 색칠한 div 5개 → 단가/이탈 정보 빈약
- 추이 시각화 없음 (matplotlib 정적 미리보기뿐)

## 반드시 보존한 기능

- 203개 테스트 전부 통과 유지 (기존 182 + 신규 21)
- DOCX 내보내기, CSV/XLSX 파서, 고급 분석 페이지, 위자드 전체 흐름
- DB 스키마 변경 없음 (마이그레이션 불필요)

## 이번에 구현한 것

1. `app/engine/budget_planner.py` — 예산 기반 캠페인 설계 룰 엔진
   - 필요 예산 = 최소예산 x 연령 x 성별 x 입찰 x 소재
   - 예산별 구조: <2만 단일 / 2만대 페어 / 3~4만 페어+실험 / 5~9만 2페어 / 10만+ 풀페어
   - 예산 제한 모드 (부족하면 순차 운영 5단계 제시)
   - 누적 지출 기반 판단 규칙 (3만 보류 / 3~5만 1차 / 5만+문의0 OFF / 목표CPA 2배 강한 OFF)
   - 캠페인 네이밍: `지역_성별연령_소구_자동|수동`
2. 위자드 Step 3에 룰 엔진 카드 — 세팅표 즉시 계산 + AI 프롬프트에 그대로 주입
   (AI가 캠페인 구조를 임의 설계하지 못하게 "임의 변형 금지" 계약 포함)
3. 성과 보고서 대시보드 개편 — KPI 증감 카드 / ECharts 퍼널 / 기간별 추이 2종

## 수정 우선순위 (남은 작업)

- P1: 진단 결과를 "캠페인 수정표" 표 형식으로 출력 (우선순위|문제|근거|조치|수정값)
- P1: AI 출력 JSON 스키마 검증 + 리페어 루프 (소식글 500자 미만 재생성 등 —
  news_post_guard에 일부 존재, 전 출력으로 확대 필요)
- P2: 연령x성별 히트맵 (demographic.py 데이터 기반, 고급 분석 페이지)
- P2: 자동/수동 페어 나란히 비교 화면 (check_auto_manual_pairing 활용)
- P2: 온보딩 체크리스트 페이지 (전문가모드 계정 + 비즈프로필 권한)
- P3: 목표별 1차 KPI 선택 UI (채팅/단골/쿠폰/DB/방문)
- P3: DB 모델 확장 (CampaignPlan, BudgetReallocation 등 — 마이그레이션 동반)

## 위험한 변경 지점

- `ai_engine.py` 프롬프트 템플릿: `{budget_plan}` 플레이스홀더 추가됨 —
  템플릿 수정 시 format() 키 누락 주의
- `report.py` `_load_saved_data`: 카드 초기화 목록이 카드 추가 시 같이 늘어야 함
- 포트 자동 선택: 사용자가 8000을 기대하면 콘솔 안내 메시지를 봐야 함
