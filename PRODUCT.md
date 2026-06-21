# PRODUCT.md — daangn_ad_reporter

> 기존 `CLAUDE.md`·코드 구조 기준 정리.

## 무엇인가
- 당근마켓 광고 기획 도우미. Python 3.11+ / NiceGUI(Quasar·Vue) 데스크톱·웹앱.
- 비즈프로필 소식글 + 광고 기획서·성과보고서·운영제안서를 Claude/GPT(CLI 구독 우선)로 자동 생성.
- 산출물 내보내기: DOCX(python-docx), 차트(matplotlib), 선택적 PDF(docx2pdf).

## 누구를 위한 것인가
- 당근마켓에 광고를 집행하는 로컬 매장 사장님 및 이를 대행하는 마케터.

## 핵심 가치
- 실행 가능한 광고안(카피 9종·타겟팅·예산·소재·쿠폰)과 신뢰할 수 있는 성과 보고서를 빠르게 만든다.
- 보고서는 데이터에 정직한 판단(퍼널 전환·MAX CPA·소재 ON/OFF)을 제공한다.

## 핵심 화면(페이지)
- `/` 프로젝트 관리(project.py)
- `/planning` 광고 기획 4단계 위자드(전략분석 → 콘텐츠생성 → 광고세팅 → 운영제안서)
- `/report` 성과 보고서(퍼널 시각화, MAX CPA, 소재 ON/OFF, 기간 비교)
- `/thumbnail` 썸네일 생성(자연 실사 비광고 프롬프트)
- `/analysis` 분석
- `/research` 커뮤니티 리서치(검색 → 본문/댓글 수집 → AI 분석)

## 산출물/자산
- 성과보고서·기획서 DOCX/PDF, 운영 제안서(7섹션), 썸네일 이미지.
- SQLite `daangn_ads.db` (projects / generated_content / performance_rows / report_content).
- 빌드: PyInstaller + Inno Setup(`build.py`, `daangn.spec`, `installer.iss`).

## 확인 필요 항목
- `app/ai/` provider/coordination 호출 경로와 CLI/API 폴백 분기
- 당근 CSV 파서(`app/reporting/parsers.py`) 입력 포맷 케이스
- report.py의 MAX CPA·소재 판단 산식 정합성

## 비고
고객 매장/광고계정/개인정보(보고서·DB 내) 열람·출력 금지. `.env`·API 키 미출력.
