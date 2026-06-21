# RULES — daangn_ad_reporter

상위: `C:\project\_AGENCY_OS\MASTER_RULES.md` + **기존 `CLAUDE.md`(최우선)**.

## 반드시 지킬 기존 규칙
- 기존 374개 pytest **전부 통과** 유지(`python -m pytest app/ -q --tb=short`).
- `asyncio.ensure_future` 사용 **절대 금지** → `lambda: func()` / `background_tasks.create()` 패턴.
- bot_created_rule 5단계 플로우 준수(설계→스펙 테스트→아웃풋 체크→인풋 체크→모듈화).
- 모든 UI 요소에 `dg-` 접두사 클래스, Paperlogy/당근 #FF6F0F, 이모지 금지.
- 버전은 소수점 관리(v1.2 → v1.3 …), 버그는 번호 부여 후 버전 올려 기록.
- AI 기획 콘텐츠는 7섹션 품질 기준 충족.

## 하면 안 되는 것
- 패키지 설치, 배포, 파일/테스트/페이지 삭제, git push.
- 대량 리팩토링, 임의 디자인/색상 결정.
- `.env`/API 키(ANTHROPIC/OPENAI)/STORAGE_SECRET/고객·광고계정·매장 개인정보/DB 실데이터 열람·출력(보이면 마스킹).
- SQLite 스키마 변경 시 기존 데이터 마이그레이션 없이 진행.

## 검수 기준
- `python -m pytest app/ -q --tb=short` 통과(회귀 없음).
- 변경 화면이 의도대로 렌더(또는 보고서 산출물 정상 생성)됨을 직접 확인.
- 기존 기능/페이지 회귀 없음.
