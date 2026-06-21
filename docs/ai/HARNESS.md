# HARNESS — 이 프로젝트 검문소

공통 기준 `C:\project\_AGENCY_OS\HARNESS_STANDARD.md`를 따른다. 아래는 이 프로젝트 적용 요약.
> 기존 `docs/HARNESS.md`(있으면)도 함께 참조한다.

## 적용 프로파일
이 프로젝트 성격에 맞는 하네스만 적용한다(코드 / UI·UX / 보고서 / 제안서·기획서 / 마케팅 콘텐츠).
어떤 프로파일이 해당되는지는 `docs/ai/PROJECT_BRIEF.md`·`RULES.md`·`RAW_NOTES.md`의 성격으로 판단한다.
- 코드 하네스: 빌드/실행이 있는 모든 작업.
- UI/UX 하네스: 화면/디자인 변경.
- 보고서·제안서·콘텐츠 하네스: 해당 산출물 생성 작업.

## 동작
1. Trigger 지점(`TRIGGERS.md`)에서 하네스 실행.
2. `QUALITY_GATES.md`의 게이트를 `METRICS.md`의 숫자로 측정(harness-reviewer / metrics-auditor / ux-harness-reviewer).
3. P0/P1 실패 → **완료 불가**, 수정 후 재검문(Loop Pattern).
4. 결과를 `HARNESS_RESULTS.md`에 기록.

## 원칙
- 숫자로 증명 못 하면 "판단 필요"(승인) 또는 "미검증"(미실행)으로 표시. 추정 통과 금지.
- 테스트/검수 통과 전 "완료"라고 하지 않는다.
- 민감정보 미열람·미출력. 기존 기능 삭제 금지.
