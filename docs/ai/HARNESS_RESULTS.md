# HARNESS_RESULTS — 검문 결과 기록

공통: `C:\project\_AGENCY_OS\HARNESS_STANDARD.md`. 매 검문마다 아래 형식으로 기록(메인 작업자).

## 형식
```
### [날짜] TASK/작업 — Trigger
- 프로파일: 코드 / UI / 보고서 / 제안서 / 콘텐츠
- 게이트 결과:
  - <게이트> | 기준 | 측정값 | 판정(PASS/P0/P1/P2/미검증)
- 종합 판정: PASS / FAIL
- P0/P1 조치:
- 검수자: harness-reviewer / metrics-auditor / ux-harness-reviewer / test-runner / code-reviewer
```

## 기록

### [2026-06-20] /agency-run-local 오늘 내부 사용 점검 — Trigger: 로컬 실사용 점검
- 프로파일: 코드 (+ 보고서 산출물 스모크)
- Change-Fingerprint: 코드 변경 없음(읽기/실행만). 산출물: verify_성과보고서.docx(207KB)·verify_기획서.docx(37KB)·_charts/*.png 3종 재생성
- 게이트 결과:
  - 빌드/스모크 | 실행 성공 | main.py 기동 OK(:8099, 브라우저 모드) | PASS
  - 첫 화면/라우트 | HTTP 200 | `/` 200(title 당근 광고 기획 도우미) + planning/report/analysis/thumbnail/research 전부 200 | PASS
  - 핵심 흐름(입력→처리→export) | 1회 통과 | verify_reports.py 무비용 DOCX+차트 생성 OK | PASS
  - 테스트 | fail 0 | 366 passed, 3 subtests, 26.9s | PASS
  - 타입/컴파일 에러 | 0 | import·실행 에러 0 | PASS
  - 외부/비용 호출 | 0 | AI/이미지 생성 미호출(fixture·룰엔진 경로만) | PASS
  - 민감정보 접근/출력 | 0 | .env/DB 실데이터/키 미열람 | PASS
- 종합 판정: PASS (READY)
- P0/P1 조치: 없음
- 비고: venv Python 3.14.2 / requests urllib3·charset_normalizer 버전 불일치 경고(비차단, 기능 영향 없음 — P3)
- 검수자: 메인 작업자(test 실행·HTTP 스모크 직접), subagent 미호출

### [2026-06-20] /agency-quality-sweep 전체 품질 스캔(읽기 전용) — Trigger: 품질 스캔
- 프로파일: 코드 + UI + 테스트 + 문서 (수정 없음, 결점 발견·TASK 후보화만)
- 스캔 차원별 결점 수: 기능 4 / 디자인·UX 6 / 보안 1(+양호 3) / 테스트 1 / 문서 2 → 총 **P0 0, P1 2, P2 6, P3 6**
- 측정 근거:
  - 테스트 | fail 0 | 366 passed, skip/xfail 0 | PASS
  - 컴파일 | 에러 0 | compileall exit 0 | PASS
  - 이모지(UI 금지) | 0 | pages/theme grep 0건 | PASS
  - 추적 민감파일 | 0 | git ls-files(.env/db/key) 0건 | PASS
  - CLI 인자 주입 | 위험 없음 | providers stdin 전달(input=prompt), shell=True 0 | PASS
  - lint | 미측정 | ruff 미설치 | 미검증
  - 커버리지 % | 미측정 | coverage 미설치 | 미검증
- 핵심 P1: ① **작동흐름(UI 메뉴) 간소화 미반영**(QS-1, _ops/TASKS.md:46 "사용자 피드백 대기"로 보류) ② analysis.py 분석 로딩 상태 없음(QU-1)
- 종합 판정: 스캔 완료(PASS). 수정은 후속 명령으로 분리.
- 추가 TASK 후보: TASKS.md QS-1~7, UI_TASKS.md QU-1~6
- 검수자: 메인 작업자 + ux Explore subagent(UI 상태 커버리지) + 정적 측정. (code-reviewer subagent는 최종 보고 릴레이 실패로 메인이 직접 보안/산식 점검)

### [2026-06-20] QS-1 구현 — 리서치→기획 연결 + 워크플로우 6단계 — Trigger: BeforeComplete
- 프로파일: 코드 + UI
- 게이트 결과:
  - 빌드/컴파일 | 에러 0 | compileall exit 0 | PASS
  - 테스트 | fail 0 | 374 passed(신규 8 test_saved_research), 26s | PASS
  - 기존 기능 삭제 | 0 | /plan/* 라우트·위자드 내부 네비 유지, 워크플로우 통합만 | PASS
  - UI 라우팅 영향 | 0 | 라이브 렌더: 6스텝, 리서치 선행, /plan/strategy·/plan/content 모두 '광고 기획' 활성·prev/next 정상 | PASS
  - 신규 입력 검증 | OK | 빈 인사이트 미저장, 없으면 빈블록(best-effort, 기획 차단 없음) | PASS
  - 민감정보 | 0 | .env/키 미열람 | PASS
  - 비용 호출 | 0 | 리서치 재사용(원클릭이 새 검색/AI 호출 안 함), 라이브 AI 생성 미실행 | PASS
- 종합 판정: PASS
- 증거: verify_simplified_workflow.png (6스텝 워크플로우 바)
- 검수자: 메인 작업자(test+Playwright 라이브 렌더 직접)

### [2026-06-20] QS-2/QS-7/QS-8 — 파이프라인 테스트·문서수치·성과보고서 액션카드 — Trigger: BeforeComplete
- 프로파일: 코드 + UI + 보고서
- 게이트 결과:
  - 테스트 | fail 0 | 376 passed(신규 test_planning_pipeline 2) | PASS
  - 컴파일 | 에러 0 | report.py compile OK | PASS
  - 보고서 액션성(실행안 노출) | 통과 | /report 결과에 'Next Actions+다음실험' 카드 본문 위 노출(라이브 렌더) | PASS
  - UI 라우팅/기존기능 | 영향 0 | 기존 마크다운·판단표 유지, 액션카드만 추가 | PASS
  - 민감정보/실데이터 | 보호 | 검증용 주입 보고서(id29) 삭제로 원복 | PASS
- 종합 판정: PASS
- 증거: verify_report_action_plan.png(액션카드 본문 위), QS-7(152→374 일괄)
- 검수자: 메인 작업자(test+Playwright 직접)

### [2026-06-20] QS-9 Stage A — 성과보고서+고급분석 화면/라우트 병합 — Trigger: BeforeComplete
- 프로파일: 코드 + UI
- 게이트 결과:
  - 테스트 | fail 0 | 376 passed | PASS
  - 컴파일 | 0 | compileall app OK | PASS
  - 라우팅/기존기능 | 영향 0 | 본문 추출(render_*_body)만, 로직 그대로. /report 탭2개 렌더, /analysis→/report 리다이렉트 | PASS
  - 콘솔 에러 | 0 | Playwright 콘솔 error 0 | PASS
  - 탭 본문 렌더 | OK | 성과 요약(KPI·퍼널) + 세그먼트 심화(업로드·진단) 둘 다 표시, 탭 전환 정상 | PASS
  - 워크플로우 단계 | 6→5 | "성과 분석" 1개로 통합 확인 | PASS
- 종합 판정: PASS (Stage A)
- 증거: verify_merged_report_analysis.png
- 남음: Stage B(DOCX 통합), Stage C(중복 집계 제거)
- 검수자: 메인 작업자(test+Playwright 직접)

### [2026-06-20] QS-9 Stage B-HTML — 슬라이드 통합 보고서(HTML) — Trigger: BeforeReportExport
- 프로파일: 코드 + 보고서
- 게이트 결과:
  - 테스트 | fail 0 | 381 passed(신규 slides_html 5) | PASS
  - 컴파일 | 0 | report.py compile OK | PASS
  - 보고서 산출물 생성 | OK | build_slides_html 자체완결 HTML(표지·지표·퍼널·진단·액션·판단) 생성, 라이브 렌더 검증 | PASS
  - 입력 검증/이스케이프 | OK | html.escape(XSS 테스트 포함), 보고서 없으면 안내 후 중단 | PASS
  - 설치/의존 | 추가 0 | stdlib only(jinja 불필요), python-pptx 미설치 유지 | PASS
  - 기존 export 영향 | 0 | DOCX 버튼·핸들러 그대로, 슬라이드 버튼만 추가 | PASS
- 종합 판정: PASS (Stage B-HTML)
- 증거: 표지·"이렇게 하겠습니다" 액션 슬라이드 라이브 렌더(검증 후 임시파일 삭제)
- 남음: Stage B-PPTX(python-pptx 설치 승인 대기), Stage C(세그먼트 실데이터 연결·중복 제거)
- 검수자: 메인 작업자(test+Playwright 직접)

### [2026-06-20] QS-9 Stage B-PPTX — 편집 가능한 PPT 보고서 — Trigger: BeforeReportExport
- 프로파일: 코드 + 보고서
- 게이트 결과:
  - 패키지 추가 | 승인됨 | python-pptx 1.0.2 사용자 승인 후 설치, requirements/spec/build.py 반영 | PASS(승인)
  - 테스트 | fail 0 | 384 passed(신규 slides_pptx 3: 생성·재오픈7슬라이드·최소2) | PASS
  - 컴파일 | 0 | report.py·slides_pptx.py OK | PASS
  - 산출물 생성 | OK | build_slides_pptx → 유효 .pptx(PK), Presentation 재오픈 7슬라이드 | PASS
  - 기존 export 영향 | 0 | DOCX·HTML 버튼/핸들러 유지, _gather_slide_data 공용화로 중복 제거 | PASS
  - 빌드 반영 | OK | daangn.spec collect_data('pptx')+hiddenimports, build.py --collect-data pptx | PASS
- 종합 판정: PASS (Stage B 완료 — HTML+PPTX)
- 남음: Stage C(세그먼트 실데이터 연결, 공용 집계 중복 제거)
- 검수자: 메인 작업자(test 직접)

### [2026-06-20] QS-9 Stage C + QS-10 UX 점검/최적화 — Trigger: BeforeComplete + BeforeDesignComplete
- 프로파일: 코드 + UI
- 게이트 결과:
  - 테스트 | fail 0 | 386 passed(신규 test_report_segments 2) | PASS
  - 컴파일/런타임 | 에러 0 | compileall OK + 앱 기동 전 10라우트 HTTP 200(/, planning, plan/*, report, analysis, thumbnail, research) | PASS
  - 콘솔 에러 | 0 | /report Playwright 콘솔 error 0 | PASS
  - 세그먼트 데이터 연결 | OK | 데모 xlsx→judge_campaigns→segment_rows(판정 포함)→슬라이드 주입, 비-데모 None 폴백 | PASS
  - UI 버튼 과밀(주요 CTA) | 개선 | export 5버튼→"내보내기 ▾" 메뉴(상단 2버튼), 메뉴 4항목 라이브 확인 | PASS
  - 기존 라우팅/기능 | 영향 0 | 모든 export 핸들러 동작 유지(버튼 변수만 export_btn로 통합) | PASS
- 종합 판정: PASS
- UX 검토 결론: 워크플로우 5단계(리서치 선행·기획 통합) 일관·양호 / 성과 분석 2탭 적절 / 잔여 권고: 성과요약 탭 내부 (업로드|수기) 중첩 탭 = 2단 탭(후순위 평탄화 고려), 세그먼트 심화 탭 자체 DOCX export는 슬라이드 통합 deliverable과 별개로 잔존
- 검수자: 메인 작업자(test+Playwright 직접)

### [2026-06-20] QS-11 — 2단 탭 평탄화 + 세그먼트 DOCX 정리 — Trigger: BeforeDesignComplete
- 프로파일: UI + 코드
- 게이트 결과:
  - 테스트 | fail 0 | 386 passed | PASS
  - 컴파일/import | 0 | report·analysis compile + import OK | PASS
  - 기존 기능 영향 | 0 | 입력 컨테이너만 교체(업로드/수기 로직 무변경), build_analysis_docx 함수·테스트 보존 | PASS
  - 중첩 탭 제거 | OK | 라이브: 최상위 탭 2개만, 파일 업로드 직접 노출 + 수기 접이식 | PASS
  - 세그먼트 DOCX 정리 | OK | DOCX 버튼 0, 죽은 _export_docx·import 3개 제거, 통합 안내 배너로 대체 | PASS
  - 콘솔 에러 | 0 | Playwright error 0 | PASS
- 종합 판정: PASS (잔여 UX 권고 2건 모두 해소)
- 검수자: 메인 작업자(test+Playwright 직접)

### [2026-06-20] 자료 반영 강화 — 프로젝트 16필드 + 교재 원문 + 고수 플레이북 — Trigger: 사용자("자료 완벽 구현")
- 프로파일: 코드 + 콘텐츠(지식)
- 게이트 결과:
  - 테스트 | fail 0 | 396 passed(신규 test_project_data_flow 5·test_knowledge_injection 5·test_report_segments 2 등) | PASS
  - 프로젝트 자료 반영 | 개선 | 마커 추적 전략·소식글 8/16→**16/16**(타게팅·쿠폰·현재광고 주입) | PASS
  - 교재 주입 | 강화 | 정제 요약(~9K)→원문 전문(core ~53K, full ~144K), 고수 플레이북 최우선 주입(전 scope) | PASS
  - 출처/사실 | 보존 | _FACT_LOCK 유지, 플레이북은 사용자 1차 자료(검증된 실전) | PASS
  - 빌드 반영 | OK | daangn.spec/build.py에 app/knowledge 번들 추가(frozen서도 교재·플레이북 로드) | PASS
- 종합 판정: PASS
- 정직 고지: 교재 full(144K토큰/콜)은 조율 2~3콜서 한계·지연 위험 → 기본 core(당근 전문+메타 요약). AI가 자료를 '잘 쓰는지'(출력 품질)는 라이브 생성(비용) 미검증 — 주입(배선)까지 검증.
- 검수자: 메인 작업자(마커 추적·크기 측정·test 직접)

### [2026-06-20] 교재 정독 + 플레이북이 교재 덮어쓰기(윤익=참고) — Trigger: 사용자 지시
- 프로파일: 콘텐츠(지식)
- 조치: 교재 전문 정독(당근4종+메타). 사장님 플레이북 vs 윤익 교재의 핵심 모순(연령 넓혀라/머신러닝 vs 연령 찢어라/머신러닝 없음) 확인. operator_playbook.md에 "교재 충돌 시 플레이북 우선" 명시 + knowledge.py `_PRIORITY_DIRECTIVE`(①플레이북→②위키→③교재[참고]) 주입 + 교재 [참고] 라벨.
- 게이트: 396 passed. 주입 순서(플레이북<지침<교재) 검증 통과. "넓혀라 무효·머신러닝 없음" 지침 포함 확인.
- 종합 판정: PASS. (출력 품질 라이브 검증은 미실시)
- 검수자: 메인 작업자(test+주입 검증 직접)

### [2026-06-21] 라이브 출력 검증 — 4단계 + 조율 전 경로 (지니스 공주신관 pid14) — Trigger: 사용자 "출력 봐라"
- 프로파일: 코드 + 콘텐츠 (실제 AI 생성, 구독 CLI)
- 발견·수정한 치명적 버그: **WinError 206** — 교재 주입(53K+)이 system_prompt를 명령줄 인자로 넘겨 Windows 32KB 한계 초과 → 모든 생성 실패. claude CLI 2경로(일반+멀티모달) stdin-fold로 수정. (codex provider는 원래 stdin 방식이라 안전.) ERROR_LOG 기록.
- 설정 변경: 교재 기본 모드 core(53K)→**distilled(9K)**. 라이브 비교상 품질·속도 동일한데 6배 쌈(둘 다 ~3분/단계, 병목은 생성).
- 예산 근거: budget_planner 룰엔진을 Step1(전략)에도 주입(전엔 세팅만) → 예산 시나리오가 AI 추론이 아닌 결정론적 룰 기반.
- 검증 결과(claude 단독 distilled): 전략·소식글(2버전, 벤치마크 화법·쿠폰우선·FAQ)·세팅(룰엔진 근거·소도시 100원·실지리)·제안서 전부 운영자급. 연령 찢기·자동수동 페어·변수통제·"머신러닝 없음"·연령 묶음 모두 적용. 윤익 "넓혀라" 0회(override 유지). 데이터 불일치(캠페인명) 자동 지적. [가정] 라벨 정직. 4단계 ~8분.
- 조율(Claude+GPT) 경로: codex 작동·종합 일관성 확인(314초/단계, 출력 6,791자, Phase1/2 구조, override 유지). 조율 전체 ~16-18분 추정.
- 종합 판정: PASS — 토대+출력 양쪽 검증 완료. 396 tests 유지.
- 남은 한계: 속도(조율 16-18분, UI 안내 필요). MAX CPA 등은 [가정](사장님이 객단가·마진 입력해야 실값).
- 검수자: 메인 작업자(라이브 4단계+조율 직접 생성·평가)

### [2026-06-21] 후속 마무리 — 조율 4단계 풀 검증 + 시간안내 UI + MAX CPA 입력란 — Trigger: 사용자 "다 해라/이어서 해"
- 프로파일: 코드 + 콘텐츠
- ① 조율(Claude+GPT) 4단계 풀 라이브: 1015초(~17분), 4단계 정상 생성(claude단독보다 풍부, Phase1/2·override 유지). 마지막 미검증 경로 해소 → 모든 생성 경로 검증 완료.
- ② 소요시간 UI: planning_wizard.py "전체 기획 한 번에 생성" 아래 동적 라벨(`_full_time_hint`) + engine_radio.on_value_change. 조율="약 16~18분"/단독="약 8분".
- ③ MAX CPA 손익기준: projects에 unit_price·margin_pct 컬럼(마이그레이션·DEFAULTS 자동). ai_engine._max_cpa_line=객단가×(1-마진%) → project_setting_block 주입(없으면 라인 생략=[가정] 유지). project.py 입력2칸+프리필+저장.
- 게이트: 396 passed. 단위검증 — MAX CPA 10만×(1-0.4)=6만, 마진없음=객단가, 미입력=라인생략, DB 왕복 OK. compile OK.
- 종합 판정: PASS. 세 숙제 전부 처리. (③ UI 렌더는 라이브 미확인 — 컴파일+로직 검증까지.)
- 검수자: 메인 작업자(test+단위검증+조율 풀 직접 실행)

### [2026-06-21] 기능 개선 — 내보내기 파일명 sanitize (QS-6) — Trigger: /agency-improve-feature
- 프로파일: 코드(기능 결함 수정)
- 선택 근거: 문서화 P0/P1 전부 해결됨 + QS-3(ZeroDivision)은 오탐 확인 → 남은 실질 결함 중 최우선. 내보내기(핵심 산출물) 파일명을 사용자 자유입력(매장/캠페인명)으로 sanitize 없이 생성 → `/`는 하위폴더로 조용히 흩어짐, `\:*?`는 OSError 저장 실패.
- 수정: ExportManager save_default/save_as/save_as_multi 경계에 `sanitize_filename` 적용(모든 저장 경로 1곳 방어). report.py:1455 즉석 sanitize→헬퍼 교체(중복 제거). 기능 삭제 없음, DB/권한/외부연동/패키지 무관.
- 게이트: **402 passed**(396→6 신규 test_export_manager.py). compile OK. 직접 재확인 — OSError 폴백·성공 ui.download·Save As 추천명 모두 sanitized filename 사용, 멱등(슬라이드·썸네일 무영향).
- 검수: harness-reviewer=**PASS**, code-reviewer=P0/P1 미제기(파일 정독 후), metrics-auditor=완료.
- 종합 판정: PASS. P0/P1 잔여 없음.
- 검수자: 메인 작업자 + harness-reviewer/code-reviewer/metrics-auditor subagent

### [2026-06-21] 기능 개선 — 실패 진단성 보강(침묵 삼킴 로깅) (QS-5) — Trigger: /agency-improve-feature
- 프로파일: 코드(하드닝, 동작 불변)
- 선택 근거: QS-6 다음 추천 결함. 생성 경로는 이미 양호 → 갭은 산출물/업로드 경로 6곳(로그 없이 삼킴).
- 수정: report.py:88 파싱 폴백 `_report_log.debug`; planning_wizard 5곳(이미지·썸네일·내보내기2·예산설계) `_log.exception` 추가(notify 유지). 죽은 코드(exporting/analysis_docx) 제외.
- 게이트: **402 passed**(회귀 0, 로깅 전용이라 신규 테스트 없음). compile OK. 스모크: `_rows_from_daangn_breakdown(b'bad')`→None(전방참조 NameError 없음). 민감정보 로깅 없음(%s+exc).
- 검수: harness-reviewer=**PASS**(P0/P1 0건), code-reviewer=차단 사항 미제기.
- 종합 판정: PASS. P0/P1 잔여 없음.
- 검수자: 메인 작업자 + harness-reviewer/code-reviewer subagent

### [2026-06-21] 기능 개선 — theme.py 파일 분리 (QS-4, 안전 추출) — Trigger: /agency-improve-feature
- 프로파일: 코드(리팩토링, 동작 불변·순수 데이터 추출)
- 선택 근거: QS-4(800줄 초과 7파일) 중 가장 안전·완결적인 한 파일. theme.py는 CSS 문자열 1개(BRAND_CSS, ~920줄) + inject_theme/section_header 구조라 데이터 분리가 zero-risk.
- 수정: `app/theme_css.py` 신설로 BRAND_CSS 이동, theme.py는 `from app.theme_css import BRAND_CSS` 재import. theme.py 956→**36줄**. 외부 import(inject_theme/section_header) 무영향, BRAND_CSS 외부 미사용.
- 게이트: **402 passed**(회귀 0). compile OK. 스모크: `theme.BRAND_CSS is theme_css.BRAND_CSS`=True, 길이 35050 동일(바이트 동일이라 렌더 동일). 동작 불변이라 신규 테스트 없음.
- 정직 고지: theme_css.py(924줄)는 800줄 초과이나 **순수 CSS 데이터 모듈**(로직 0). 임의 분할은 유지보수 악화라 단일 유지 — 800줄 규칙의 취지(로직 파일 복잡도)는 theme.py 36줄로 해소.
- 검수: harness-reviewer=**PASS**.
- 종합 판정: PASS. P0/P1 잔여 없음. (QS-4 잔여 6파일은 후순위 — ai_engine 등은 상수/함수 혼재라 더 큰 작업.)
- 검수자: 메인 작업자 + harness-reviewer subagent

### [2026-06-21] 기능 개선 — ai_engine.py 부분 분리(craft+categories) (QS-4 후속) — Trigger: /agency-improve-feature
- 프로파일: 코드(데이터 추출, 동작 불변)
- 수정: `app/ai_craft.py`(_CRAFT_BLOCK leaf 상수, 9곳 공유) + `app/ai_categories.py`(카테고리 가이드/프롬프트 + CATEGORIES, _CRAFT_BLOCK은 ai_craft서 import) 분리. ai_engine은 재import(noqa F401). 2810→**2510줄**(-300).
- 발견·해결: CATEGORIES["default"]가 SYSTEM_GUIDE_PLANNING(ai_engine 잔류) 참조 → 순환 import 위험. **default placeholder(None) + ai_engine import 직후 주입**으로 해소(의존 그래프 ai_craft←ai_categories←ai_engine, 순환 0).
- 게이트: **402 passed**(회귀 0). compile OK. 스모크 — 양쪽 import 순서 정상, default 가이드 주입 확인(is SYSTEM_GUIDE_PLANNING), default/restaurant 빌드 정상. 외부 import 재export 유지.
- 정직 고지: ai_engine 여전히 2510줄(>800). 잔여 상수(SYSTEM_GUIDE_PLANNING/CLAUDE/GEMINI·PROPOSAL·STRATEGY·AD_SETTINGS·WIZARD 등)는 상호참조 많아 별도 작업으로 분리해야 함 — incremental 진행.
- 검수: harness-reviewer=**PASS**.
- 종합 판정: PASS. P0/P1 잔여 없음.
- 검수자: 메인 작업자 + harness-reviewer subagent
