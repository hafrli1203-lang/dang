# IMPLEMENTATION_NOTES — 2026-06-12 업그레이드

## 변경 파일

| 파일 | 변경 |
|------|------|
| `app/engine/budget_planner.py` | 신규 — 예산 기반 캠페인 설계 룰 엔진 |
| `app/engine/test_budget_planner.py` | 신규 — 21개 테스트 |
| `app/pages/planning_wizard.py` | Step 3에 예산 설계 카드 + AI 프롬프트 주입 |
| `app/ai_engine.py` | `build_ad_settings_prompt(budget_plan_context=)` 추가, 캠페인 구조 변형 금지 계약 |
| `app/pages/report.py` | KPI 증감 카드 + ECharts 퍼널 + 추이 차트, `on_value_change` 버그 수정, `kpi_container` NameError 수정 |
| `app/pages/planning.py` | `on_value_change` 버그 수정 (프로젝트/카테고리 select) |
| `app/theme.py` | `.dg-stat-*` 대시보드 카드 스타일 |
| `main.py` | 127.0.0.1 포트 충돌 감지 + 자동 대체 포트 |

## 설계 원칙: 룰 엔진 + AI 분리

- **코드가 계산**: 필요 예산, 페어 가능 여부, 캠페인 구조/네이밍/예산 배분,
  누적지출 기반 판단 규칙. (`app/engine/budget_planner.py`, `app/reporting/demographic.py`)
- **AI는 문장화만**: 룰 엔진이 만든 세팅표를 프롬프트로 받아 설명/가이드를 작성.
  "임의 변형 금지" 지시로 AI가 캠페인 구조를 멋대로 바꾸지 못하게 함.

## 예산별 추천 구조 (budget_planner 룰)

| 일예산 | 구조 | 비고 |
|---|---|---|
| <1만 | 운영 불가 경고 | 캠페인 최소 예산 미달 |
| 1만대 | 단일 캠페인 1개 | 신규=자동(넓은 타겟 20-59), 검증됨=수동(핵심 연령) |
| 2만대 | 핵심 연령 1개 자동+수동 페어 | 진짜 최소 페어 |
| 3~4만 | 주력 페어 + 실험 1개(1만) | 실험은 연령만 다르게 (변수 1개) |
| 5~9만 | 연령 2개 자동+수동 | |
| 10만+ | 연령 5개 풀 페어 | 고수 전략 풀버전 |

## 실행/확인 방법

```bash
cd daangn_ad_reporter
venv\Scripts\activate
python main.py        # 8000이 막혀 있으면 8001~ 자동 선택, 콘솔에 주소 표시
python -m pytest app/ -q --tb=short   # 203 passed
```

- 성과 보고서: 프로젝트 선택 → 저장 데이터 자동 로드 → KPI 카드/퍼널/추이 렌더
- 광고 기획 Step 3: 일예산 입력 → [설계 계산] → 세팅표 확인 → [광고 세팅 가이드 생성]

## 검증 결과

- 203 tests passed (기존 182 + 신규 21)
- Playwright 실화면 검증: 진해하나로마트점 43행 실데이터로
  KPI 카드(▲102% 등 증감 배지), 퍼널(단계별 건수/전환율/단가), 추이 차트 렌더 확인
- 스크린샷: `C:\project\dang\report-kpi-funnel.png`, `report-dashboard-final.png`

## 남은 리스크

- 포트 자동 선택 시 사용자가 기존 북마크(8000)로 접속하면 다른 앱이 보임 —
  콘솔 안내 메시지 확인 필요. 근본 해결은 8000 점유 중인 다른 uvicorn 종료.
- 예산 설계 카드는 Step 3 결과 생성 전 화면에만 노출 (재생성 시에는 기존 설계 텍스트 재사용)
- ECharts는 NiceGUI 내장이라 오프라인 PyInstaller 빌드에 추가 의존성 없음 (빌드 재검증 권장)

---

## Gemini → OpenAI(GPT) 전환 + 조율 엔진 (2026-06-13)

### 변경 요약
- **Gemini 완전 제거**: `GeminiProvider`/`GeminiImageProvider` 삭제, `google-genai` 의존성 제거.
- **OpenAI 신설**: `OpenAIProvider`(chat.completions + Images API), `OpenAIImageProvider`(gpt-image-2).
- **이미지**: 썸네일이 `gpt-image-2`(공식 최신, b64_json) 사용. env `OPENAI_IMAGE_MODEL`로 교체 가능.
- **조율(coordinate)**: `app/ai/coordination.py` — Claude·GPT 병렬 초안 → 종합 모델(Claude)이 1개로 병합.
  엔진 선택지 `{Claude / GPT / Claude+GPT 조율}`, 기본 Claude(단일). 위자드 4스텝·분석·보고서·제안서 적용.
- 빌드/설치 갱신: `requirements.txt`(openai), `daangn.spec`·`build.py` hiddenimports, `installer.iss` 키 입력란.

### 필요 환경변수 (.env — 직접 추가 필요, 코드가 .env 안 건드림)
- `OPENAI_API_KEY` (필수). `OPENAI_MODEL`(기본 gpt-4o), `OPENAI_IMAGE_MODEL`(기본 gpt-image-2),
  `OPENAI_SYNTHESIS_ENGINE`(기본 claude) 선택.
- gpt-image는 OpenAI 콘솔에서 조직 인증(Organization Verification)이 필요할 수 있음.

### 검증
- 214 tests passed (Gemini 테스트 → OpenAI/coordination 테스트로 교체, 순증 4).
- Playwright: /planning 엔진 옵션 [Claude/GPT/조율] 확인, Gemini 잔존 0,
  키 없는 상태에서 GPT 생성 시 "OPENAI_API_KEY가 없어요" 안내(크래시 없음) 확인.
- 미검증(키 필요): 실제 GPT 텍스트 생성·gpt-image-2 이미지 생성·조율 종합 품질. OPENAI_API_KEY 추가 후 점검 필요.
