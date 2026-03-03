# Document Spec v1.0 — 당근마켓 광고 문서

> 기준 파일: `templates/sample_report.docx`, `templates/sample_plan.docx`
> 본 스펙은 두 DOCX 템플릿을 파이썬으로 재현하기 위한 설계 문서입니다.

---

## 공통 스타일 (두 문서 동일)

| 스타일    | 색상     | 크기   | 굵기 | 비고 |
|-----------|----------|--------|------|------|
| Title     | #17365D  | 26 pt  | -    | 가운데 정렬, 하단 여백 15 pt |
| Heading 1 | #365F91  | 14 pt  | Bold | 단락 전 여백 24 pt |
| Heading 2 | #4F81BD  | 13 pt  | Bold | 단락 전 여백 10 pt |
| Normal    | 기본(흑) | 기본   | -    | |

### 표 색상 팔레트

| 상수          | HEX     | 용도 |
|---------------|---------|------|
| `_C_ORANGE`   | FF6F00  | 시계열 표 헤더 행 배경, 요약카드 지표명 |
| `_C_ORANGE_L` | FFF3E0  | KPI/정보 표 항목명 열 배경 |
| `_C_ORANGE_S` | FFF8F0  | 요약 카드 값 행 배경 |

### 페이지 설정
- 크기: A4 (8.27 in × 11.69 in)
- 여백: 상하 1.0 in, 좌우 1.25 in
- 푸터: 표지 제외 전 페이지 — 문서명 | 페이지 번호

---

## 성과보고서 — 레이아웃 확정안 v1.0 (10개 섹션)

### 섹션 순서

```
Sec 0: 표지
  └─ Title        : "당근마켓 광고 성과 보고서"
  └─ Normal 13pt  : "{name}  |  {region}"
  └─ Normal 11pt  : "캠페인: {campaign_name}" (있을 때만)
  └─ Normal 11pt  : "작성자: {author}" (있을 때만)
  └─ Normal       : "보고서 작성일: YYYY년 MM월 DD일"
  └─ Normal 8pt   : 신뢰 안내문 2줄 (gray)
── page break ──

Sec 1: 목차
  └─ Heading 1    : "목차"
  └─ TOC 필드 코드 (Word에서 Ctrl+A → F9로 갱신)
── page break ──

Sec 2: 한 페이지 요약 (Heading 1)
  (A) 요약 카드        ← _build_summary_card()
      2행×4열, 모드별 핵심 KPI 4개
  (B) 메타 박스         ← _build_meta_box()
      2×2 borderless: 목표 / 판단KPI / 타겟·지역 / 주요혜택
  (C) 결론              ← _build_conclusion()
      Heading 2 + Normal 단락들
  (D) Next Actions      ← _build_next_actions()
      Heading 2 + ☐ 체크박스 항목 (최대 7개)
── page break ──

Sec 3: 캠페인 개요 (Heading 1)
  └─ 5행×2열 Table Grid ← _build_campaign_overview()
     목적 / 기간 / 예산 / 운영방식 / 추적모드

Sec 4: 성과 요약 (Heading 1)
  └─ KPI 상세 표        ← _build_kpi_table()
     2열 (항목명 FFF3E0·Bold | 값), 모드별 행

Sec 5: 성과 차트 (Heading 1)
  └─ 차트 3개           ← _build_charts_section()
     chart_spend_action / chart_cpa / chart_funnel

Sec 6: 인사이트 (Heading 1)
  └─ 잘 된 것 (Heading 2) + 막힌 것 (Heading 2) + 가설 (Heading 2)
     ← _build_insights_section()
     fallback: 레거시 insights 리스트

Sec 7: 다음 실험 · 개선안 (Heading 1)
  └─ 5열 Table Grid     ← _build_experiments_table()
     우선순위 / 변경내용 / 성공기준 / 담당 / 일정
     오렌지 헤더, fallback: 레거시 actions

Sec 8: 판단 기준 (Heading 1)
  └─ 3행×2열 Table Grid ← _build_judgment_criteria()
     확대 / 검토 / 중단

Sec 9: 부록 (Heading 1)
  └─ 기간별 원본 데이터 (Heading 2) ← _build_timeseries_table() (최대 10행)
  └─ 지표 정의 (Heading 2)          ← 모드별 약어 정의 표
```

### tracking_mode별 차이

| 항목 | db_funnel | landing | reaction |
|------|-----------|---------|----------|
| 요약카드 KPI | 광고비/CTR/CPC/문의 | 광고비/CTR/CVR/CPA | 광고비/노출/반응/CPE |
| KPI 상세 표 | 9행 | 8행 | 8행 |
| 차트 행동지표 | 클릭·문의 | 클릭·전환 | 반응 |
| 퍼널 단계 | 노출→클릭→문의→단골 | 노출→클릭→전환 | 노출→반응 분해 |
| 지표 정의 | CTR/CPC/CPA/단골 | CTR/CPC/CVR/CPA | 노출/반응/ER/CPE |

### AI 분석 입력 (ReportInsights TypedDict)

| 필드 | 대상 섹션 | 설명 |
|------|-----------|------|
| `conclusion` | Sec 2(C) | 결론 3~5줄 |
| `next_actions` | Sec 2(D) | Next Actions 리스트 (3~7개) |
| `good` | Sec 6 | 잘 된 것 (1~3줄) |
| `blocked` | Sec 6 | 막힌 것 (1~3줄) |
| `hypothesis` | Sec 6 | 가설 (1~3줄) |
| `experiments` | Sec 7 | Experiment 리스트 (priority/change/success_criteria/owner/schedule) |
| `judgment` | Sec 8 | JudgmentCriteria (expand/review/stop) |
| `summary` | (레거시) | _normalize_insights() 폴백용 |
| `insights` | (레거시) | _normalize_insights() 폴백용 |
| `actions` | (레거시) | _normalize_insights() 폴백용 |

---

## 기획서 (sample_plan.docx)

### 섹션 순서

```
표지
  └─ Title        : "당근마켓 광고 기획서"
  └─ Normal 13pt #757575 : "{name}  |  {industry}  |  {region}"
  └─ Normal       : "작성일: YYYY년 MM월 DD일"
  └─ (빈 단락)
── page break ──
광고주 정보       (Heading 1)
  └─ (빈 단락)
  └─ 표: 8행 × 2열  ← 광고주 정보 표
── page break ──
AI 생성 기획 내용 (Heading 1)
  └─ 1. 기획 요약   (Heading 2)
       └─ AI 마크다운 파싱 결과 (_render_md_body)
  └─ 2. 당근 소식글 (Heading 2)
       └─ Normal 단락들
  └─ 3. 광고 카피 9개 (Heading 2)
       └─ Normal: "1. …", "2. …", …
```

### Placeholder 필드

#### 표지
| 필드 | 소스 | 비고 |
|------|------|------|
| 제목 | `"당근마켓 광고 기획서"` | Title 스타일 |
| 부제 | `name \| industry \| region` | Normal, 13pt, color=#757575, 가운데 |
| 날짜 | `datetime.now()` | `"작성일: …"` |

#### 광고주 정보 표 (2열: 항목명 \| 값)
| 행 | 항목명 | 소스 필드 | 비고 |
|----|--------|-----------|------|
| 1 | 광고주명 | `project_meta.name` | |
| 2 | 업종     | `project_meta.industry` | |
| 3 | 지역     | `project_meta.region` | |
| 4 | 광고 목표 | `project_meta.goal` | |
| 5 | 예산     | `project_meta.budget` | |
| 6 | 집행 기간 | `project_meta.period` | |
| 7 | 주요 혜택 | `project_meta.benefits` | 선택, 없으면 "-" |
| 8 | 참고 링크 | `project_meta.link` | 선택, 없으면 "-" |

- 항목명 열: 배경 `FFF3E0`, Bold
- 값 열: 배경 없음

#### AI 생성 기획 내용
AI 반환 마크다운을 `## ` 기준으로 분리 후 섹션별 처리:

| 섹션 키워드 | Heading 2 레이블 | 렌더링 방식 |
|-------------|-----------------|-------------|
| `기획 요약` | 원본 그대로    | `_render_md_body()` — `###`→bold, `-`→bullet, `\|`→Normal |
| `소식글`    | 원본 그대로    | 줄 단위 Normal 단락 |
| `카피`      | 원본 그대로    | 줄 단위 Normal 단락 (번호 포함) |

---

## 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| v1.0 | 2026-03-03 | 최초 스펙 확정 — sample_report/plan.docx 기반 |
| v1.0 layout | 2026-03-03 | 레이아웃 확정안 v1.0 — 성과보고서 10개 섹션 구조 |
