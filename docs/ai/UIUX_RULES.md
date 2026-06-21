# UIUX_RULES — daangn_ad_reporter (보조)

> 최우선은 기존 `CLAUDE.md` UI 가이드(taste-skill)와 `app/theme.py`(dg- 클래스). 이 문서는 보조.

기준: `C:\project\_AGENCY_OS\UIUX_RULES.md`.

## 이 프로젝트(업무형 광고 기획/보고 SaaS) 적용
- 업무형 신뢰감: 위자드·보고서는 정보 위계와 진행 상태가 분명해야 한다.
- 4단계 위자드는 현재 단계/완료 여부가 한눈에 보이고, 단계 이동이 명확해야 한다.
- 성과 보고서는 퍼널·KPI·소재 판단(효율/비효율/중립)을 절제된 색상 코딩으로 구분.
- 로딩 skeleton / 빈 상태 / 오류 상태를 반드시 처리(AI 생성 대기·실패 포함).
- 당근 #FF6F0F primary + accent 최대 1개, 과한 그라데이션·이모지 금지(AI Tells 회피).
- 모든 요소 `dg-` 접두사 클래스, Paperlogy, 버튼 촉각 피드백(`scale(0.98) translateY(1px)`).
- 디자인 작업도 렌더 확인(또는 보고서 산출물 확인) 없이 완료라고 말하지 않는다.
- 색상/레이아웃 임의 결정 금지 → 기존 theme.py·taste-skill 우선.

## 보고서 산출물(DOCX/PDF)도 디자인 대상
- `app/reporting/document_spec.md` 스펙을 따른다.
- 표지 → 요약 → 근거(표·차트) → 제안 순 위계, 한글 렌더(Malgun Gothic) 정상 확인.
