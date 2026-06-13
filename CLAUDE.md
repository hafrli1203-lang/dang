# 당근 광고 기획 도우미 (daangn_ad_reporter)

## Overview
당근마켓 비즈프로필 소식글 + 광고 기획서 자동 생성 도구.
NiceGUI 기반 웹앱으로, Claude/Gemini AI를 활용하여 광고 콘텐츠를 생성한다.

## Tech Stack
- **Runtime**: Python 3.11+
- **UI**: NiceGUI 3.8.0 (Quasar/Vue 기반), Paperlogy 폰트
- **AI**: anthropic (Claude), google-genai (Gemini)
- **DB**: SQLite (daangn_ads.db) -- 4 tables (projects, generated_content, performance_rows, report_content)
- **Export**: python-docx + matplotlib (Agg backend, Korean font: Malgun Gothic)
- **Build**: PyInstaller + Inno Setup

## Architecture
```
main.py                          # Entry point (v1.2.0)
app/
  ai_engine.py                   # 프롬프트 빌더 + 시스템 가이드 + KPI 계산
  database.py                    # SQLite CRUD
  common.py                      # 공유 nav bar + ExportManager delegates
  theme.py                       # CSS 디자인 시스템 (dg-* 클래스, Paperlogy 폰트)
  logger.py                      # 로깅 (파일 + 메모리 버퍼 + stderr)
  paths.py                       # 플랫폼 경로 관리
  export_manager.py              # 통합 내보내기 (save_default/save_as/save_as_multi)
  updater.py                     # GitHub Releases 자동 업데이트
  chart_preview.py               # matplotlib 차트 생성
  ai/
    providers.py                 # ClaudeProvider / GeminiProvider + retry_api_call()
    image_provider.py            # GeminiImageProvider (썸네일)
    news_post_guard.py           # 소식글 검증 + 자동 보정
    text_overlay.py              # PIL 텍스트 오버레이
    nanobanana_prompt.py         # Style Fusion / Image Mapping 프롬프트
  content/
    news_post_rules.py           # Type B/C 소식글 검증 (restaurant)
  pages/
    project.py                   # Page 1: /           프로젝트 관리
    planning.py                  # Page 2: /planning   광고 기획 (4단계 위자드)
    planning_wizard.py           # 4단계 위자드 구현 (전략분석 > 콘텐츠생성 > 광고세팅 > 운영제안서)
    report.py                    # Page 3: /report     성과 보고서 (퍼널 시각화, MAX CPA, 소재 ON/OFF)
    thumbnail.py                 # Page 4: /thumbnail  썸네일 생성
    proposal_tab.py              # 운영 제안서 (독립 모드, Step 4와 병행)
  reporting/
    docx_report.py               # DOCX 생성 (성과보고서 + 기획서)
    parsers.py                   # 당근 CSV 파서
    document_spec.md             # 문서 디자인 스펙
```

## Workflow: 4단계 위자드 (planning_wizard.py)
광고 기획 페이지는 4단계 위자드 구조로 운영된다:
1. **전략 분석** (Step 1) -- 타겟/경쟁환경/전략방향/캠페인그룹 자동 분석
2. **콘텐츠 생성** (Step 2) -- 소식글 2버전(의심해소+가성비) + 썸네일 생성 통합
3. **광고 세팅** (Step 3) -- 캠페인 구조/타겟팅/예산/소재 가이드
4. **운영 제안서** (Step 4) -- 7섹션 종합 제안서 (proposal_tab 독립모드 대체)

## 성과 분석 (report.py)
- **퍼널 시각화**: 노출 > 클릭 > 문의 > 단골 > 쿠폰 단계별 전환율
- **MAX CPA 계산**: 수익성 기반 최대 허용 CPA
- **소재 ON/OFF 판단**: 효율 기반 소재 유지/중단 가이드
- **기간별 효율 비교**: 색상 코딩(효율/비효율/중립)

## 윤익 프레임워크
- **CTR 체크리스트**: 광고 카피 9종 프레임워크 (소셜프루프/호기심/권위)
- **뉴로마케팅 썸네일**: Gemini AI 기반 Style Fusion / Image Mapping
- **쿠폰 설계**: 쿠폰명/혜택/유효기간/수량 자동 스펙

## Run
```bash
cd daangn_ad_reporter
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python main.py   # http://localhost:8000
```

## Environment (.env)
```
# 텍스트는 기본 CLI(구독) — 아래 키들은 API 모드로 쓸 때만 필요
ANTHROPIC_API_KEY=sk-ant-...          # CLAUDE_BACKEND=api 일 때만
OPENAI_API_KEY=sk-...                 # OPENAI_BACKEND=api 또는 이미지 생성에 필요
CLAUDE_MODEL=claude-opus-4-6          # default
OPENAI_MODEL=gpt-4o                   # API 모드 텍스트 모델
OPENAI_CLI_MODEL=                     # codex 모델 override (비우면 codex 기본)
OPENAI_IMAGE_MODEL=gpt-image-2        # default (이미지)
OPENAI_SYNTHESIS_ENGINE=claude        # 조율 종합 엔진 (default: claude)
STORAGE_SECRET=...
```

## AI 엔진 (Gemini 제거됨 / CLI 우선, 2026-06-13)
- **텍스트는 CLI 구독이 기본 — API 키 불필요**:
  - Claude → `claude` CLI (ClaudeCliProvider). `CLAUDE_BACKEND=api`면 API.
  - GPT → `codex exec` CLI (OpenAICliProvider, ChatGPT 구독). `OPENAI_BACKEND=api`면 API.
- 엔진 선택: Claude / GPT / **Claude+GPT 조율**(병렬 초안→Claude 종합). 둘 다 CLI라 조율도 키 불필요.
- **이미지(gpt-image-2)는 CLI 경로 없음 → OPENAI_API_KEY 필요** (썸네일). codex는 이미지 생성 못 함.
- 조율: `app/ai/coordination.py` (`synthesize` / `coordinate_generate`). 위자드 4스텝·분석·보고서·제안서.
- 새 텍스트 호출부는 `get_provider("claude")`/`get_provider("gpt")` 사용 (직접 Provider() 인스턴스화 지양).

## Tests
```bash
python -m pytest app/ -q --tb=short
# 152 tests pass (19s)
```

## Critical Rules

### Regression Prevention [ABSOLUTE]
- 수정 시 기존 152개 테스트 **전부 통과** 유지
- 기존에 잘 되는 기능을 망치는 코딩 **절대 금지**
- 매 작업 후 `python -m pytest app/ -q --tb=short` 실행하여 확인

### asyncio.ensure_future 금지 [ABSOLUTE]
- `asyncio.ensure_future` 사용 **절대 금지**
- NiceGUI async 핸들러는 `lambda: func()` 또는 직접 async 함수 전달 패턴 사용
- 함수가 버튼보다 뒤에 정의된 경우 `lambda: func()` 패턴 사용 (UnboundLocalError 방지)
- 페이지 로드 시 초기 async 호출은 `nicegui.background_tasks.create()` 사용

### bot_created_rule 5단계 플로우
모든 기능 개발은 아래 순서를 반드시 따른다:
1. **설계 문서** -- 목적/트리거/실패복구/상태경계/아웃풋 정의
2. **스펙 테스트** -- 정상 케이스 검증, 최단경로 구현
3. **아웃풋 체크** -- 결과물 포맷/구조/전달경로 확인
4. **인풋 체크** -- 엣지케이스/예외/빈값 검증
5. **모듈화** -- 기능 단위 독립 모듈 분리

### 코딩 원칙
- 보수적/수동적 방법을 디폴트로 제안하지 않는다
- 기존 인프라(NiceGUI, Claude API, Gemini API, SQLite) 활용 최단경로로 구현
- 버전은 소수점으로 관리 (v1.0 -> v1.1 -> v1.2 -> v2.0)
- 버그 발견 시 번호 부여 후 버전 올려서 수정 기록

## UI/UX Guidelines (taste-skill)
이 프로젝트의 UI는 design-taste-frontend 스킬 지침을 따른다:
- **Typography**: Paperlogy 폰트 기반, display text `tracking-tighter`, body `text-base leading-relaxed`
- **Color**: 당근 브랜드 (#FF6F0F primary), max 1 accent color, Zinc/Slate neutral base
- **Layout**: CSS Grid 우선, `max-w-[1200px] mx-auto`, `min-h-[100dvh]` for full-height
- **Interaction**: Loading skeleton, empty states, error states 필수 구현
- **Motion**: `transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1)`, transform/opacity만 애니메이션
- **Cards**: elevation이 hierarchy를 소통할 때만 사용, 그림자는 배경 hue에 tint
- **Forms**: Label above input, helper text optional, error below input, `gap-2`
- **No Emoji**: 코드/마크업/텍스트에 이모지 사용 금지 (아이콘 라이브러리 사용)
- **CSS Classes**: 모든 UI 요소에 `dg-*` 접두사 클래스 일관 사용
- **Tactile Feedback**: 버튼 클릭 시 `scale(0.98) translateY(1px)` 트랜스폼

## Reference Materials (프롬프트 품질 기준)
- `C:\project\dang\심곡점.docx` -- Claude Opus 4.6 생성 품질 벤치마크
- `C:\project\dang\당근 텍스트 퍼포먼스.docx` -- 4종 프롬프트 + 9종 카피 프레임워크
- `C:\project\dang\당근광고 레퍼런스.docx` -- 실제 당근 광고 레퍼런스 URL
- `C:\project\dang\당근 성과 보고서.xlsx` -- 성과 리포트 양식 3종

## AI Output Quality Standard
기획 콘텐츠 생성 시 아래 7개 섹션을 모두 포함해야 한다:
1. 기획 요약 (3-5줄)
2. 광고 카피 9종 (소셜프루프 3 + 호기심 3 + 권위/구체성 3) + 글자수/트리거
3. 캠페인 그룹 (나이대별 2+ 그룹 + 배치 가이드)
4. 소식글 본문 2 versions (900-1400자, CTA + 위치정보)
5. 썸네일/이미지 촬영 가이드 (2+ 컨셉)
6. 쿠폰 스펙 (쿠폰명/혜택/유효기간/수량)
7. 캠페인 네이밍 규칙 (예: `지역_비즈타겟_키워드`)

## Version
- Current: v1.2.0 (main.py `__version__`)
