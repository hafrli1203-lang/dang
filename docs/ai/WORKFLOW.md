# WORKFLOW — daangn_ad_reporter

기준: `C:\project\_AGENCY_OS\WORKFLOW_RULES.md` + 기존 `bot_created_rule` 5단계 플로우.

## 작업 순서
1. 기존 `CLAUDE.md`·`AGENTS.md`·`docs/ai/` 읽기.
2. `TASKS.md`/`UI_TASKS.md`에서 최우선 1개 선택.
3. 5단계 플로우(설계 → 스펙 테스트 → 아웃풋 체크 → 인풋 체크 → 모듈화)로 스프린트 계약(스코프·테스트 행동·엣지케이스).
4. 작은 단위 구현(한 기능 / 한 페이지).
5. 실행 확인:
   - 테스트: `python -m pytest app/ -q --tb=short` (374개 통과 유지)
   - 앱: `python main.py` → 네이티브 창 또는 http://localhost:8080
6. 기준 충족까지 Loop 반복(오류 → 원인 → 수정 → 재실행).
7. 문서 갱신(`TASKS.md`, `ERROR_LOG.md`, `DECISIONS.md`, UI면 `DESIGN_AUDIT.md`).
8. 결과 보고.

## 실행 메모
- 개발: `python main.py` (포트 8080 기본, `DAANGN_PORT`로 override, 점유 시 자동 대체)
- 테스트: `python -m pytest app/ -q --tb=short`
- 빌드: `python build.py` (PyInstaller + Inno Setup)
- 새 페이지: `main.py`에 `import app.pages.<name>` 등록 필요(side-effect 등록).
