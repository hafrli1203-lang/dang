# ERROR LOG — daangn_ad_reporter

작업 중 발생한 오류/함정과 해결. 같은 실수 반복 방지용.

| 날짜 | 증상 | 원인 | 해결 |
|---|---|---|---|
| 2026-06-16 | 검증 스크립트 `ModuleNotFoundError: No module named 'app'` | /tmp에서 실행돼 sys.path에 프로젝트 루트 없음 | `PYTHONPATH=<repo>`로 실행 |
| 2026-06-16 | 전략·세팅 결과에 AI가 만든 `## 0. 현재 광고 점검`이 화면에 안 뜸 | 결과 렌더러가 고정 섹션만 그림 | `_extract_checkup`/`_render_checkup_card`로 상단 surface |
| (참고) | 보고서 섹션명/JSON 스키마 변경 위험 | DOCX는 마크다운 제목이 아니라 JSON dict로 생성 | 섹션명·JSON 키 유지하고 **내용 품질만** 갈아엎기 |
| 2026-06-16 | 매장 위키 누적이 안 되고 초기본만 로드됨 | `get_latest_content`가 `created_at DESC`만 정렬 → 같은 초 다중 저장 시 동률이라 최신본 못 집음(created_at 초 단위) | `ORDER BY created_at DESC, id DESC`로 id 보조정렬 추가 (get_latest_project_for_store는 이미 그랬음) |
