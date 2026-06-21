# TRIGGERS — 하네스 실행 지점

공통: `C:\project\_AGENCY_OS\HARNESS_STANDARD.md`.
> 주의: 아래는 **에이전트가 따르는 절차 게이트**다. Claude Code 실제 hook 자동화는 현재 **문서화만**(미활성). 활성화는 사용자 승인 후 별도.

| Trigger | 시점 | 할 일 | 자동 hook 후보 |
|---|---|---|---|
| BeforeTaskStart | 작업 시작 전 | PROJECT_BRIEF / WORKFLOW / TASKS / HARNESS 확인 | UserPromptSubmit 리마인더 |
| BeforeImplementation | 구현 직전 | 관련 파일·완료 기준 확인 | - |
| AfterEdit | 코드 수정 후 | build/test/lint(또는 가능한 검수) 실행 | **PostToolUse(Edit/Write)** |
| BeforeComplete | 완료 직전 | QUALITY_GATES 통과/실패 판정(harness-reviewer + metrics-auditor) | Stop 리마인더 |
| BeforeDesignComplete | UI 완료 직전 | UIUX_RULES / DESIGN_AUDIT / UI_TASKS 검수(ux-harness-reviewer) | - |
| BeforeReportExport | 보고서 출력 전 | 필수 섹션·수치 구분·실행안 개수·과장 표현 검수 | - |
| BeforePR | PR 직전 | CODE_REVIEW 내부 리뷰 후 Codex 리뷰 준비 | - |

## hooks 자동화 (계획, 미활성)
- AfterEdit → PostToolUse 훅으로 build/lint 자동 실행: 프로젝트별 명령 확정 + 사용자 승인 후 `settings` 적용.
- BeforeComplete/BeforeReportExport 등은 hook 이벤트가 없어 **subagent + 문서로 강제**.
- 현재는 어떤 자동 hook도 켜지 않았다(문서화만).
