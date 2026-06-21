# DESIGN.md — daangn_ad_reporter

> 중요: 이 프로젝트는 **이미 확립된 디자인 체계**(`app/theme.py`, dg- 클래스, Paperlogy, 당근 #FF6F0F)가 있다. 아래 기존 규칙이 **최우선**이며, AGENCY_OS 공통 시스템은 충돌하지 않는 선에서 보조로만 적용한다.

## 기존 디자인 규칙 (최우선, `CLAUDE.md`·`app/theme.py`)
- 폰트: **Paperlogy** (NiceGUI), matplotlib 한글은 Malgun Gothic.
- CSS: 모든 UI 요소에 **`dg-` 접두사** 클래스 일관 사용. 인라인 스타일 지양.
- 색상: 당근 브랜드 **#FF6F0F primary**, accent 최대 1개, Zinc/Slate neutral base.
- 레이아웃: CSS Grid 우선, `max-w-[1200px] mx-auto`, full-height는 `min-h-[100dvh]`.
- 모션: `transition: all 0.3s cubic-bezier(0.16,1,0.3,1)`, transform/opacity만.
- 버튼 촉각 피드백: 클릭 시 `scale(0.98) translateY(1px)`.
- 이모지 금지(아이콘 라이브러리 사용). taste-skill의 AI Tells 회피.

## 이 프로젝트의 성격 (업무형 + 산출물형)
- 랜딩 홈페이지가 아니라 **내부 업무용 광고 기획/보고 데스크톱 SaaS**.
- 두 종류의 디자인 대상이 있다:
  1. **화면 UI** — 4단계 위자드, 성과 보고서 대시보드, 프로젝트/리서치 화면.
  2. **보고서 산출물(DOCX/PDF)** — 기획서·성과보고서·운영제안서. `app/reporting/document_spec.md` 스펙을 따른다. UI와 별개로 **문서 레이아웃·표·차트의 신뢰감과 가독성**이 디자인 대상이다.

## 방향성 (한전ON형 업무 신뢰감 + rightpeople형 정돈)
- 업무형 신뢰감: 정보 위계가 분명하고, 숫자·표·퍼널이 한눈에 읽히는 차분한 톤.
- 과한 색·장식·그라데이션 지양. KPI/판단(효율·비효율·중립)은 절제된 색상 코딩으로 구분.
- 보고서 산출물은 표지 → 요약 → 근거(표·차트) → 제안 순의 위계.

## 피할 것
- 흔한 AI 그라데이션·의미 없는 이모지·제네릭 카드 패턴.
- dg- 클래스 없는 일회성 인라인 스타일.
- 데이터를 과장하는 시각화(보고서 정직성 훼손).

## 완료 기준
- 화면: 로딩 skeleton·빈 상태·오류 상태 처리, 반응형, dg- 일관성.
- 보고서: `document_spec.md` 부합, 표/차트 한글 렌더 정상, 산출물 열어 확인.
- 기존 페이지/스타일/테스트 회귀 없음. 렌더(또는 산출물) 확인 없이 완료 보고 금지.
