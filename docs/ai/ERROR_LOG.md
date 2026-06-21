# ERROR_LOG — daangn_ad_reporter

> 오류 발생 시 아래 형식으로 기록. 비어 있어도 템플릿 유지.

## 형식
```
### [날짜] 제목
- 증상:
- 재현 방법:
- 원인:
- 해결:
- 재발 방지:
```

## 기록

### [2026-06-21] 실패가 로그 없이 삼켜짐 — 진단 불가 (QS-5, 하드닝)
- 증상: 일부 except가 실패를 로그/알림 없이 삼켜, "됐다는데 결과물이 빈/틀린" 상황의 원인 추적이 불가. (생성 경로는 이미 _log.exception+notify로 양호했음 — 갭은 일부 산출물/업로드 경로에 한정.)
- 원인: ① `report.py:_rows_from_daangn_breakdown`이 long-format 파싱 실패를 로그 없이 `return None`(폴백) → 잘못된 파일이 조용히 기본 파서로 넘어감. ② `planning_wizard.py` 5곳(참고이미지 읽기·썸네일 생성·내보내기2·예산설계)이 사용자 알림(ui.notify)은 하나 `_log` 누락 → 서버 로그에 흔적 없음.
- 해결: 동작 변경 없이 로깅만 보강 — report.py 폴백에 `_report_log.debug`(정상 폴백이라 debug), planning_wizard 5곳에 `_log.exception`(기존 notify 유지). 로그는 `%s` 지연포맷+exc만(민감정보 없음).
- 재발 방지: 죽은 코드(exporting.py·analysis_docx.py, 사용처 0)는 제외. 향후 except는 graceful 폴백이라도 최소 debug 로그 남길 것. 402 tests 유지(동작 불변, 로깅 전용이라 신규 테스트 없음). harness-reviewer PASS.

### [2026-06-21] 내보내기 파일명 sanitize 누락 — 산출물 조용히 흩어지거나 저장 실패 (QS-6)
- 증상: 성과보고서·기획서·제안서 DOCX 내보내기 시, 매장/캠페인명에 경로 금지문자가 있으면 저장이 어긋남. `/`면 `target_dir / "성과보고서_6월/신규.docx"`가 pathlib에서 경로 구분자로 처리돼 **엉뚱한 하위폴더에 조용히 저장**(에러도 안 남), `\ : * ? " < > |`면 **OSError로 저장 실패**.
- 재현: `ExportManager.save_default(b"x", "성과보고서_6월/신규.docx", dest_dir=tmp)` → tmp 아래 "성과보고서_6월/" 하위폴더 생성 + "신규.docx" 저장(평탄 경로 아님).
- 원인: `export_manager.py:save_default`이 `saved = target_dir / filename`인데, 호출부(report.py·planning_wizard.py)가 파일명을 `f"성과보고서_{project_name}.docx"` 등 **사용자 자유입력값으로 sanitize 없이** 생성. 슬라이드 내보내기(report.py:1455)는 이미 즉석 sanitize를 했으나 DOCX 3종만 누락된 일관성 결함. `app/paths.sanitize_filename`(Windows 금지문자·예약어·끝점·빈값→"unnamed")은 이미 존재했음.
- 해결: **경계 1곳 방어** — `ExportManager.save_default`/`save_as`/`save_as_multi` 진입부에서 `filename = sanitize_filename(filename)` 적용(재할당돼 native 파일쓰기 + browser `ui.download` 폴백 + Save As 추천명 전부 보호). 멱등이라 이미 깨끗한 슬라이드·썸네일 호출 무영향. report.py:1455 즉석 sanitize는 헬퍼로 교체(중복 제거).
- 재발 방지: `app/test_export_manager.py` 신규 6 tests — `/`·`: * ?`·금지문자뿐·멱등·save_as/save_as_multi 추천명 각각 잠금. 402 tests(396→402). harness-reviewer PASS.

### [2026-06-21 참고] QS-3(성과분석 ZeroDivision)은 오탐
- TASKS QS-3가 `demographic.py:162,175 share_pct = s.cost/total_cost`의 0division 가능성을 "추정"으로 지목했으나, 실제로는 `:136 active=[s for s in ... if s.cost>0]` + `:141 if total_cost<=0: return []`로 이미 가드됨. 314줄(`judge_campaigns`)도 `:304 active=[c ... if c.cost>0]`로 total_cost>0 보장. report.py 델타(:485 `if prev<=0`)·게이지(:693/716 `max(.., 상수)`)도 전부 가드 확인. → 수정 불필요.

### [2026-06-20] 교재 주입(53K+) 시 Claude CLI 생성 전부 실패 — WinError 206 (치명적)
- 증상: 라이브 전략 생성 시 `FileNotFoundError: [WinError 206] 파일 이름이나 확장명이 너무 깁니다`로 모든 생성 실패. (라이브로 안 돌렸으면 못 잡았을 버그 — "출력을 봐라"가 옳았음)
- 원인: `providers.py` ClaudeCliProvider가 system_prompt를 `--append-system-prompt <전체>` **명령줄 인자**로 전달. 교재 전문 주입으로 guide가 109,198자(~54.6K토큰)가 되자 **Windows 명령줄 길이 한계(~32KB) 초과**. distilled(9K) 땐 한계 아래라 작동했음.
- 해결: system_prompt가 6,000자 초과면 인자 대신 **stdin에 prompt와 합쳐 전달**(`{guide}\n━━[작업 요청]━━\n{prompt}`). stdin은 길이 한계 없음. 작은 건 기존대로 --append-system-prompt.
- 재발 방지: 큰 시스템 프롬프트는 절대 명령줄 인자로 넘기지 말 것. (codex/OpenAI CLI provider도 동일 패턴 점검 필요 — 조율 쓸 때.) 396 tests.
- 검증: 수정 후 프로젝트14(지니스 공주신관) 전략 생성 성공(156.9초, 출력 4,274자, 연령 찢기·페어·예산현실·벤치마크 화법·추적한계 전부 반영).

### [2026-06-20] 프로젝트 입력 자료가 원클릭 기획 프롬프트에 절반만 반영됨
- 증상: 사용자가 "프로젝트에 넣은 자료가 기획·분석·보고서에 제대로 반영 안 되는 것 같다". 마커 추적 결과 원클릭 기획에서 16필드 중 8개만 반영(name·industry·region·goal·budget·period·benefits·reference_url), **타게팅(반경·성별·연령)·현재광고(ad_titles)·쿠폰(coupon_info)·입찰·일예산·캠페인명 8개 누락**.
- 재현: build_strategy_prompt/build_planning_prompt를 current_ad 없이(원클릭 경로처럼) 호출 → 타게팅·쿠폰 마커 미포함.
- 원인: 타게팅/현재광고/쿠폰은 프롬프트 본문 템플릿(_STRATEGY_PROMPT 등)이 직접 안 쓰고, 위자드 UI의 `_collect_current_ad()`가 모아 current_ad로만 전달. **원클릭 `generate_full_plan`은 current_ad를 안 넘김** → 자료 누락.
- 해결: `ai_engine.project_setting_block(project)` 순수 헬퍼 신설(반경/성별/연령/입찰/일예산/제목/쿠폰/캠페인명 → 주입 블록). 전략·소식글·세팅·제안서 빌더에 `prompt += project_setting_block(project)` 주입(위자드/원클릭 무관 자동 반영). 보고서엔 매장 배경(목표·예산·혜택)+설정 추가. 마커 재추적: 전략·소식글 16/16, 세팅·제안서 15/16(reference_url만), 보고서 14/16(period는 실데이터서 산출). test_project_data_flow 5 tests. 391 total.
- 재발 방지: test_project_data_flow가 타게팅 8토큰의 프롬프트 포함을 잠금.

### [2026-06-20 참고] 리서치 0건 = 고장 아님
- 증상 의심: 매장들 research_context 0자.
- 확인: save_research_insight→research_context 실DB 라운드트립 정상(239자 저장·로드·삭제 검증). 기존 매장이 리서치 저장 기능(이번 세션 신설) 이전 생성이라 0건일 뿐. 매장 선택 후 /research 실행하면 저장·반영됨.

### [2026-06-20 참고/한계] 교재 지식은 '요약본'만 주입(원문 아님)
- 사실: raw 교재 ~700KB(meta_perf 309KB 등) → distilled 5파일 ~30KB → domain_knowledge가 scope당 10~15KB 주입(압축 ~23:1). "모든 자료를 통째로 읽는다"가 아니라 정제 요약 주입(토큰상 의도된 설계). 더 깊은 반영이 필요하면 distilled 보강 또는 주입량 확대 필요(별도 결정).
