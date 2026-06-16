# TASKS — daangn_ad_reporter

작업은 **위에서부터 1개씩**. 완료 기준 통과 + 350 tests 통과 전엔 완료 처리 금지.
설계 근거: `_ops/AI_OPERATING_FRAME.md`.

---

## [완료] TASK-0 · 성과보고서 프롬프트 품질
- 시장 보정(지역 규모 판단) + 퍼널 병목 인과 진단 + 업종·추적 환경 반영 + 근거 기반 실행 + 판단기준.
- 섹션/JSON 스키마 유지(DOCX 안전). 실데이터(공주신관점 13일)로 생성 검증 완료.
- 변경: `app/ai_engine.py` SYSTEM_GUIDE_REPORT / _REPORT_PROMPT.

## [완료] TASK-1 · 매장 위키 계층 신설
- `app/store_wiki.py` 신설(저장/로드/주입/정제). 전략·소식글·세팅·보고서 4프롬프트 + 8호출부 배선.
- 프로젝트 상세에 위키 편집 UI. 라이브 검증: 전략이 위키 패턴(검증 미끼·안 먹힌 것·계절성·추적한계) 재사용 확인. test_store_wiki 16개.

## [완료] TASK-3 · 위키 자동 갱신 (누적 루프 완성)
- 보고서 생성 후 병목·가설·검증 패턴을 기간 마커와 함께 위키에 자동 append(`update_wiki_from_report`). 기존 내용 보존.
- report.py save 직후 배선. 라이브 검증: 2회차(6월)가 1회차(5월) 진단을 이어받아 누적 확인.
- 부수 버그 수정: `get_latest_content` 정렬에 `id DESC` 추가(같은 초 다중 저장 시 최신본 누락). ERROR_LOG 기록.

## [완료] TASK-2 · 전략/기획 프롬프트 v4 프레임워크 주입
- SYSTEM_GUIDE_STRATEGY에 운영 프레임워크(단일 미끼·미끼평가·시나리오·변수통제·데이터 의사결정) 추가.
- _STRATEGY_PROMPT 섹션3을 ### 하위(미끼 적합도 평가표 ⭐ / 시나리오 A·B 비교표+권장 / 메시지·소구 / 의사결정 기준)로,
  섹션4에 변수통제(자동·수동 1쌍, 입찰만 다름) 명시. 파서는 `## `만 분리하므로 ### 안전(4섹션 유지).
- 라이브 검증: 미끼평가표(변색렌즈⭐⭐⭐/블루라이트⭐ 제외)·시나리오 A/B 비교·Case별 의사결정·자동수동 페어 전부 출력 + 위키 검증자산 재사용 확인. 366 tests.

## TASK-4 · 완료 기준 루프 확장
- 출력별 완료 기준 스키마(`AI_OPERATING_FRAME.md` 3절)로 output_validator 확장.
- 완료 기준: 미달 항목만 보정, 통과 시 종료, 악화 시 원본 유지.

## [완료] TASK-4 · 전문 지식 위키(도메인 코퍼스) + 엔진 역할 분담
- 교재 4종(메타 137KB·당근 38KB·윤익 세팅·쿠폰) raw 추출 → Claude로 정제(distilled_*.md, 총 24KB 밀도 지식).
- `app/knowledge.py` `domain_knowledge(scope)` — 전략/소식글/세팅/보고서 system 가이드에 scope별 주입(매장 위키와 충돌 시 위키 우선).
- 엔진 분담: 기획·세팅·제안서 기본 '조율'(Claude+GPT→Claude 종합), 소식글 기본 'Claude'. planning.py 스텝별 기본값. GPT(codex) 동작 검증 완료.
- 라이브 검증: 소식글 생성이 소식 3유형(의심해소+가성비)·쿠폰 우선 CTA·의심제거 FAQ·상대성(투박 실사) 썸네일·매장 방문 추적까지 교재 깊이 반영 + 위키 재사용 확인. 366 tests.
- raw 원문은 .gitignore(저작권), distilled만 커밋.

## [완료] TASK-5 · 단계 축소 — 원클릭 통합 기획
- `app/planning_pipeline.py` `generate_full_plan()`: 위키·교재 주입된 빌더로 전략→소식글→세팅→제안서 순차 생성,
  앞 단계를 뒤 단계 컨텍스트로 흘림. 각 단계 content_type(strategy/content/ad_settings/wizard_proposal) 저장 →
  개별 /plan/* 페이지가 그대로 이어받아 편집 가능. 조율/both 엔진은 과비용이라 claude로 collapse.
- 전략 페이지에 "전체 기획 한 번에 생성" 버튼(원클릭 우선, "전략만" 보조) + 진행 표시 → 완료 시 /plan/proposal 이동.
- 라이브 검증: 4단계(전략 4.3K·소식글[소식3유형]·세팅 6.5K·제안서 5.2K) 전부 생성·저장·진행메시지 정상. 366 tests.

## (남음) UI 메뉴 단순화 (메타 툴식 4메뉴)는 사용자 피드백 대기 — 기능 자동화(원클릭)가 더 급해 우선 처리함.
