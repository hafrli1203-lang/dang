# TASKS — daangn_ad_reporter

> 현재 코드 구조 기준 TASK 후보. 작은 단위. 상태: [ ] 대기 · [~] 진행 · [x] 완료

## 기능 TASK 후보
- [ ] T1. 페이지 라우트 ↔ `app/pages/` 매핑 정리 → `WIKI_INDEX.md` (project/planning/report/thumbnail/analysis/research)
- [ ] T2. 4단계 위자드(`planning_wizard.py`) 각 단계 입력/출력/실패복구 정리
- [ ] T3. 성과 보고서(`report.py`) 퍼널·MAX CPA·소재 ON/OFF 산식 정합성 점검
- [ ] T4. 당근 CSV 파서(`app/reporting/parsers.py`) 입력 포맷 케이스 문서화
- [ ] T5. AI provider/coordination 호출 경로(CLI 우선, API 폴백) 정리
- [ ] T6. 보고서 산출물(DOCX/PDF) 생성 절차와 `document_spec.md` 부합 확인

## 품질 스캔 발견 TASK 후보 (2026-06-20 /agency-quality-sweep)
> P0 없음. 아래는 P1~P3. 실제 수정은 /agency-next-task·/agency-improve-feature로 분리.
- [x] QS-1 [완료 2026-06-20] **커뮤니티 리서치 → 기획 연결 + 동선 간소화** — (구현됨) ① 리서치 결과를 매장별 DB 저장(content_type="research")→전략/소식글 빌더에 `research_block` 주입(`saved_research.py`, `insight.format_research_insight`, `build_strategy_prompt`/`build_planning_prompt`, 원클릭 파이프라인+위자드 단독 생성 모두). ② 워크플로우 9단계→6단계(기획 4단계를 '광고 기획' 1개로 통합), 리서치를 기획 '앞' 선행 단계로 재배치(`common.py`). 라이브 렌더 검증(6스텝, 리서치 선행, /plan/* 매핑) + 374 tests(신규 8). 아래는 원 진단: — 사용자 지적(2026-06-20): "기획 뒤에 리서치 있으면 뭐하러 쓰냐". 사이드바/워크플로우(`common.py`)상 리서치는 전략분석 앞(step2)에 있으나, `build_strategy_prompt(project,current_ad,wiki,competitor_ads)`에 **리서치 인사이트 인자 없음** + `planning_pipeline.py:90`은 `competitor_context`만 끌어옴 → 리서치 산출물(고충·욕구·실제표현·앵글·후크)이 기획/소식글 입력으로 안 흐름. 수정 방향: ① 리서치 결과를 DB content_type으로 저장→전략/소식글 빌더에 `research_block` 인자 주입, ② 원클릭 파이프라인이 리서치를 1단계로 선행 실행(또는 최신 리서치 재사용). 메뉴 개수 단순화(메타 4메뉴)는 별건으로 분리.
- [x] QS-2 [완료 2026-06-20] `app/test_planning_pipeline.py` 신설 — AI·DB 가짜 대체(비용0)로 4단계 저장(strategy/content/ad_settings/wizard_proposal) + 선행 리서치 주입 + 프로젝트 없음 ValueError 검증(2 tests).
- [x] QS-3 [종결 2026-06-21·오탐] `demographic.py:162,175` ZeroDivision — **실제로는 이미 가드됨**: `:136 active=[s ... if s.cost>0]` + `:141 if total_cost<=0: return []`, 314줄도 `:304 active=[c ... if c.cost>0]`로 total_cost>0 보장. report.py 델타/게이지도 가드 확인. 수정 불필요(ERROR_LOG 참고 기록).
- [~] QS-4 [진행 P3·유지보수] 800줄 초과 파일 분리.
  - **theme.py 완료(2026-06-21)**: BRAND_CSS(~920줄)→`app/theme_css.py` 분리 + 재import, theme.py 956→36줄. (theme_css.py 924줄은 순수 CSS 데이터라 단일 유지.)
  - **ai_engine.py 부분 분리(2026-06-21)**: `app/ai_craft.py`(_CRAFT_BLOCK) + `app/ai_categories.py`(카테고리 가이드+CATEGORIES) 분리, 재import. 2810→2510줄. 순환 방지 위해 default 가이드는 ai_engine서 주입. 동작 불변, 402 통과, harness PASS.
  - **잔여**: ai_engine 2510(나머지 SYSTEM_GUIDE_* 상호참조 많음)·planning_wizard 2752·docx_report 1930·demographic 1382·report 1352·analysis 1256 — 각각 별도 TASK(파일별 신중히).
- [x] QS-5 [완료 2026-06-21] **침묵 삼킴 로깅 보강** — 실live 경로 6곳(report.py:88 파싱폴백 `_report_log.debug`; planning_wizard 이미지·썸네일·내보내기2·예산설계 `_log.exception`). 생성 경로는 이미 _log+notify 양호. 죽은 코드(exporting/analysis_docx, 사용처 0) 제외. 동작 불변, 402 통과, harness PASS. (ERROR_LOG·HARNESS_RESULTS 기록.)
- [x] QS-6 [완료 2026-06-21] **내보내기 파일명 sanitize** — `ExportManager` save_default/save_as/save_as_multi 경계에 `sanitize_filename` 적용. 매장/캠페인명의 `/`(하위폴더로 조용히 흩어짐)·`\:*?`(OSError) 방어. report.py:1455 즉석 sanitize→헬퍼 교체(중복 제거). 신규 test_export_manager.py 6 tests, 402 통과. harness PASS. (ERROR_LOG·HARNESS_RESULTS 기록.)
- [x] QS-7 [완료 2026-06-20] PROJECT_BRIEF·RULES·WORKFLOW·RAW_NOTES·CLAUDE.md·AGENTS.md의 "152개"→"374개"(현 376) 일괄 갱신.

## 후속 발견/작업 (2026-06-20 대화)
- [x] QS-8 [완료 2026-06-20] **성과보고서 '이렇게 하겠다' 액션 카드** — 사용자 피드백("퍼널은 있는데 뭘 하겠다가 없다, 중간 보고서엔 어떻게 하겠다가 들어가야"). /report 결과가 7섹션 마크다운 한 덩어리로만 떠서 액션이 묻힘. `_render_action_plan()` 추가: 이미 파싱된 next_actions + 다음실험(순위·변경·성공기준·일정)을 본문 **위에** "다음 기간 운영 계획 — 이렇게 하겠습니다" 카드로 노출(`report.py`). 라이브 렌더 검증(카드가 본문 앞, 표·번호 액션 표시) + 376 tests.
- [~] QS-9 **성과보고서 ↔ 고급분석 완전 병합** (사용자 선택: 완전 병합). 단계적 진행:
  - [x] Stage A [완료 2026-06-20] 화면·라우트 병합. report.py `render_report_body()`·analysis.py `render_analysis_body()`로 본문 추출 → `/report`가 탭 2개([성과 요약 | 세그먼트 심화])로 둘 다 렌더. `/analysis`→`/report` 리다이렉트. 워크플로우 6→5단계("성과 보고서"+"고급 분석"→"성과 분석"), `_STEP_INDEX`/`_PAGE_TITLES` /analysis 매핑. 라이브 검증(탭 전환·본문 렌더·리다이렉트·콘솔 에러 0) + 376 tests.
  - [~] Stage B 통합 보고서 산출물. 사용자 요구: "문서 말고 슬라이드로, 글 덜고 보기 좋게".
    - [x] Stage B-HTML [완료 2026-06-20] `app/reporting/slides_html.py` `build_slides_html()`(순수, stdlib) — 표지·핵심지표·퍼널·진단·세그먼트·"이렇게 하겠습니다" 액션·판단기준을 자체완결 HTML 슬라이드로(당근 오렌지, @media print A4 가로→PDF). /report 성과 요약 탭에 "슬라이드 보고서(HTML)" 버튼(설치 0, jinja 불필요). 라이브 렌더 검증(표지·액션 슬라이드) + 5 tests. 381 total.
    - [x] Stage B-PPTX [완료 2026-06-20, 설치 승인됨] 편집 가능한 .pptx. `python-pptx 1.0.2` 설치(requirements.txt + daangn.spec collect_data/hiddenimports + build.py 반영). `app/reporting/slides_pptx.py` `build_slides_pptx()`(16:9, HTML과 동일 7슬라이드, 당근 오렌지, _gather_slide_data 공용). /report에 "슬라이드 보고서(PPT)" 버튼. 3 tests(생성·재오픈 7슬라이드·최소입력 2슬라이드). 384 total.
  - [x] Stage C [완료 2026-06-20] 세그먼트 실데이터 연결. `_rows_from_daangn_breakdown`이 `judge_campaigns`로 세그먼트 요약(label·cost·cpa·verdict, 비용 desc top8) 생성→page_state["segment_rows"]→슬라이드(HTML/PPT) `segment_rows`로 주입. 업로드마다 리셋(데모그래픽만 재충전). 검증(데모 xlsx→3세그먼트 판정) + test_report_segments 2 tests. 386 total. (공용 집계 완전 중복제거는 후순위 — report/analysis가 각자 parse_demographic_xlsx 호출하나 회귀 위험 대비 가치 낮음.)

## UX 최적화 (2026-06-20 새 기능 구조 점검)
- [x] QS-11 [완료 2026-06-20] **2단 탭 평탄화 + 세그먼트 탭 DOCX 정리** — ① 성과 요약 탭 내부 (파일 업로드|수기 입력) 중첩 탭 제거: 파일 업로드를 기본 노출, 수기 입력은 `ui.expansion("직접 수기 입력")` 접이식(컨테이너만 교체, 본문 무변경). ② 세그먼트 심화 탭의 DOCX 2버튼 + 죽은 `_export_docx` 핸들러 제거 → 통합 내보내기(슬라이드) 안내 배너로 교체. 죽은 import 3개(build_analysis_docx·ExportManager·CHARTS_DIR) 정리(build_analysis_docx 함수·analysis_docx.py·test_report_honesty는 보존). 라이브 검증(최상위 탭 2개·업로드 직접·DOCX버튼 0·콘솔에러0) + 386 tests.
- [x] QS-10 [완료 2026-06-20] **내보내기 버튼 과밀 해소** — 신규 슬라이드 2버튼 추가로 export 행이 5버튼(보고서생성+DOCX기본+DOCX다른위치+HTML+PPT)이 됨 → "내보내기 ▾" 메뉴 1개로 통합(보고서 생성 + 내보내기 = 2버튼). 메뉴 순서: 슬라이드 PPT(추천)·슬라이드 HTML·문서DOCX 2종(사용자 슬라이드 선호 반영). 라이브 검증(2버튼·메뉴 4항목) + 386 tests.

## 메모
- 1차는 파악/문서 중심. 기존 테스트(현재 **402개**) 회귀 방지가 최우선.
- 고객/광고계정/개인정보·.env 열람 금지.
