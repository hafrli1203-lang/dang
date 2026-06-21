# DECISIONS — daangn_ad_reporter

> 의사결정 기록. 왜 그렇게 했는지 남긴다.

## 형식
```
### [날짜] 결정 제목
- 배경:
- 결정:
- 이유:
- 영향:
```

## 기록
### [2026-06-20] 커뮤니티 리서치를 기획의 '선행 입력'으로 연결 + 워크플로우 단계 통합
- 배경: 사용자 지적 — "리서치가 기획 뒤에 애매하게 붙어있다, 기획 뒤에 있으면 뭐하러 쓰냐". 점검 결과 리서치는 독립 페이지로 산출만 하고 DB 저장도 안 돼 기획(전략·소식글)이 그 결과를 전혀 받지 않았음(competitor_ads만 주입).
- 결정: ① 리서치 인사이트를 매장별 DB(content_type="research")에 저장하고 `research_context()`로 로드해 `build_strategy_prompt`/`build_planning_prompt`에 `research_block`으로 주입(경쟁광고 주입과 동일 best-effort 패턴). 원클릭 파이프라인·위자드 단독 생성 양쪽 배선. ② 단계 과다 해소: 가로 워크플로우 9→6단계(기획 4단계를 '광고 기획' 1개로 통합), 리서치를 기획 앞 선행 단계로 재배치. 4개 /plan/* 하위경로는 _STEP_INDEX에서 '광고 기획'으로 매핑(고립 없음, 위자드 내부 네비가 단계 이동 담당).
- 이유: 리서치가 '먼저' 의미를 가지려면 데이터가 기획으로 흘러야 함. 메뉴 개수도 줄여 흐름 단순화(사용자 요구).
- 영향: common.py·ai_engine.py·planning_pipeline.py·planning_wizard.py·research.py + 신규 saved_research.py·insight.format_research_insight. 374 tests 통과(신규 8). 라우팅/기존 기능 회귀 0. 비용 증가 없음(리서치는 사용자가 한 것을 재사용, 원클릭이 새로 호출 안 함).

### [2026-06-18] 운영 문서 구조 도입(기존 규칙 보존)
- 배경: 워크스페이스 전체 LLM Wiki/Workflow/Loop 구조 적용.
- 결정: 기존 `CLAUDE.md`는 백업(`CLAUDE.md.bak`) 후 원문 보존 + 끝에 연결 섹션만 추가. AGENTS/PRODUCT/DESIGN + docs/ai 12종 + agency-ui-ux 스킬 신규 생성.
- 이유: 기존 핵심 규칙(NiceGUI/CLI AI, 152 테스트 회귀 방지, 5단계 플로우, dg-/Paperlogy, 7섹션 품질) 손실 없이 운영구조 표준화.
- 영향: 코드/테스트 변경 없음. 기존 디자인·AI 파이프라인 우선 유지.
