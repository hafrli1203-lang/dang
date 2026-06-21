# AGENTS.md — daangn_ad_reporter (당근 광고 기획 도우미)

이 프로젝트는 **LLM Wiki / Workflow / Loop Pattern** 방식으로 운영한다.
워크스페이스 공통 규칙은 `C:\project\_AGENCY_OS\MASTER_RULES.md`를 따른다.

## 가장 먼저 읽을 것 (우선순위)
1. **기존 `CLAUDE.md`** — 이 프로젝트의 핵심 규칙(NiceGUI/CLI 우선 AI, SQLite 4테이블, 374개 테스트 회귀 방지, asyncio.ensure_future 금지, bot_created_rule 5단계, dg- 클래스, AI 출력 7섹션 품질 기준). **최우선.**
2. `docs/ai/` — 운영 문서(PROJECT_BRIEF, RULES, WORKFLOW, TASKS, ERROR_LOG, DECISIONS, WIKI_INDEX 등).
3. UI 작업이면 `docs/ai/UIUX_RULES.md`·`DESIGN_AUDIT.md`·`UI_TASKS.md`.

## 작업 원칙
- TASK 하나씩만 처리한다. 첫 세션은 구조 파악/문서만.
- 테스트 없이 완료라고 말하지 않는다 → `python -m pytest app/ -q --tb=short` (374개 통과 유지).
- 기존에 잘 되던 기능/페이지/테스트를 삭제하거나 망가뜨리지 않는다. 대량 리팩토링 금지.
- 민감정보(`.env`, ANTHROPIC/OPENAI API 키, STORAGE_SECRET, 고객·광고계정·매장 개인정보, SQLite DB 내 실데이터)를 읽거나 출력하지 않는다(보이면 마스킹).
- 디자인/색상 임의 결정 금지. 기존 `app/theme.py`(dg- 클래스, Paperlogy, 당근 #FF6F0F) 및 taste-skill 규칙 우선.

## 이 프로젝트 성격 (광고/마케팅 SaaS)
- 당근마켓 비즈프로필 소식글 + 광고 기획서·성과보고서·운영제안서를 AI로 자동 생성하는 데스크톱/웹앱.
- 따라서 **실행 가능한 광고안(카피·타겟팅·예산·소재)과 보고서 산출물의 품질·정확성**을 가장 중요하게 본다.
  - 기획 콘텐츠는 7섹션 품질 기준(기존 `CLAUDE.md`) 충족.
  - 성과 보고서는 퍼널·MAX CPA·소재 ON/OFF 판단이 데이터에 정직해야 한다(과장 금지).
- UI 작업이면 한 화면(페이지: project/planning/report/thumbnail/analysis/research)씩 수정·검수한다.

## 작업 후
`docs/ai/TASKS.md`, `ERROR_LOG.md`, `DECISIONS.md`를 갱신한다. UI 작업이면 `DESIGN_AUDIT.md`도 갱신하고 결과를 보고한다.


<!-- ===== 검수 구조 연결 (2026-06-18 추가) ===== -->

## 내부 검수 + 외부 리뷰 (Workflow의 검수 단계)

구현 후 아래 검수를 거친다. 자세한 운영: `C:\project\_AGENCY_OS\SUBAGENT_GUIDE.md`.

- **test-runner subagent**: 빌드/테스트/실행을 안전하게 확인(파일 수정·삭제·배포·DB 마이그레이션·패키지 설치 금지).
- **code-reviewer subagent**: 코드 품질/보안 회귀/기존 기능 회귀/데이터 흐름/리포트 오류/테스트 누락/UI 영향을 **읽기 전용**으로 검수, P0~P3 리포트(코드 수정 금지).
- **P0/P1은 반드시 수정** 후 재검수. 테스트 통과 전 "완료"라고 하지 않는다.
- **Codex 외부 리뷰(GitHub PR)**: `docs/ai/CODE_REVIEW.md` + `_AGENCY_OS/CODEX_REVIEW.md` 참조(Claude 내부 자동 실행 아님).
- 공통 리뷰 기준: `_AGENCY_OS/CODE_REVIEW_STANDARD.md`(6대 항목 + P0~P3).


<!-- ===== 하네스 레이어 연결 (2026-06-18 추가) ===== -->

## 하네스(검문소) 규칙

자세한 기준: `docs/ai/HARNESS.md`, `QUALITY_GATES.md`, `METRICS.md`, `TRIGGERS.md` + `C:\project\_AGENCY_OS\HARNESS_STANDARD.md`.

- 모든 작업은 `HARNESS.md`와 `QUALITY_GATES.md`를 확인해야 한다.
- 완료 전 반드시 **BeforeComplete 하네스**를 통과해야 한다(P0/P1 FAIL = 완료 불가).
- 하네스 실패 시 "완료"라고 하지 말고 수정 루프(Loop Pattern)를 진행한다.
- 숫자로 증명할 수 없는 판단은 **"판단 필요"**로 표시하고 사용자 승인을 요청한다.
- 테스트를 실행하지 못했으면 **"미검증"**으로 표시한다.
- 하네스 결과는 `docs/ai/HARNESS_RESULTS.md`에 기록한다.
- 검수 subagent: `harness-reviewer`(게이트 판정), `metrics-auditor`(숫자 측정), `ux-harness-reviewer`(UI), `test-runner`/`code-reviewer`. 모두 읽기/안전실행만.
