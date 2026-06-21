# CODE_REVIEW — 이 프로젝트 코드 리뷰 기준

워크스페이스 공통 기준 `C:\project\_AGENCY_OS\CODE_REVIEW_STANDARD.md`를 따른다. 아래는 이 프로젝트 적용 요약.

## 내부 검수 루프 (Claude subagent)
1. TASKS.md(또는 UI_TASKS.md) 최우선 1개 구현
2. `test-runner` 호출 → 빌드/테스트/실행 확인(안전 실행만, 파일 수정·배포·DB·설치 금지)
3. `code-reviewer` 호출 → 아래 6대 항목 읽기전용 검수
4. **P0/P1 반드시 수정** 후 2번부터 재검수
5. 테스트 통과 + P0/P1 없음 → 문서 갱신(TASKS/ERROR_LOG/DECISIONS/DESIGN_AUDIT)

## 점검 6대 항목
1. 보안 회귀  2. 데이터 흐름 손상  3. 리포트/산출물 생성 오류
4. 테스트 누락  5. UI/UX 회귀  6. 기존 기능의 의도치 않은 삭제/축소
> 이 프로젝트의 구체 위험은 `docs/ai/RULES.md`·`docs/ai/RAW_NOTES.md`를 함께 본다
> (예: 민감정보 열람 금지, DB 마이그레이션 금지, 외부 API 비용, 산출물/리포트 품질, 기존 디자인 시스템 준수 등).

## 심각도
- P0 블로커(보안 노출/데이터 손상/핵심 기능 파괴/실행 불가) — 반드시 수정
- P1 필수(명백한 버그/회귀/위험 변경/산출물 오류) — 반드시 수정
- P2 권장 / P3 제안

## Codex 외부 리뷰 (GitHub PR)
Codex는 Claude 내부에서 자동 실행되지 않는다 → GitHub PR 또는 Codex 앱에서 별도 실행.
전제 조건·흐름: `_AGENCY_OS/CODEX_REVIEW.md` (GitHub 원격 + Codex GitHub App + PR 필요).

PR 코멘트에 붙여넣을 문구:
```
@codex review
Please review this PR for security regressions, broken data flow, report generation errors, missing tests, UI/UX regressions, and accidental deletion of existing features. Follow AGENTS.md and docs/ai/CODE_REVIEW.md.
```

## 안전
- 리뷰/실행 중 `.env`/키/토큰/쿠키/고객·광고계정 정보 미열람·미출력.
- 기존 기능 삭제 금지. 검수자(subagent)는 코드 수정 금지 — 수정은 메인 작업자(Claude)가 한다.


---

## 하네스 연계 (2026-06-18 추가)

Codex 외부 리뷰와 내부 검수는 **하네스 게이트**(`docs/ai/QUALITY_GATES.md` + `_AGENCY_OS/HARNESS_STANDARD.md`)를 함께 본다.
- BeforePR: 내부 `code-reviewer` + `harness-reviewer` 통과(P0/P1 0) 후 PR.
- Codex PR 리뷰 요청 문구(하네스 포함):
```
@codex review
Please review this PR for security regressions, broken data flow, report generation errors, missing tests, UI/UX regressions, accidental deletion of existing features, and violations of AGENTS.md / docs/ai/HARNESS.md / docs/ai/CODE_REVIEW.md.
```
