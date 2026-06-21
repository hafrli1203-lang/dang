# UI_TASKS — daangn_ad_reporter

> 화면별 UI 개선 TASK 후보. 한 번에 하나씩. 상태: [ ] 대기 · [~] 진행 · [x] 완료
> 디자인 변경은 기존 theme.py·taste-skill 규칙 준수.

## 후보
- [ ] U1. (광고 기획 위자드) 4단계 진행 상태/단계 이동 가시성 점검
- [ ] U2. (AI 생성 화면) 로딩 skeleton·실패 오류 상태 일관화
- [ ] U3. (성과 보고서) 퍼널·KPI·소재 ON/OFF 색상 코딩 정직성 점검
- [ ] U4. (프로젝트 관리) 목록·빈 상태·진입 동선 정리
- [ ] U5. (보고서 산출물 DOCX/PDF) document_spec.md 부합 + 한글 렌더 확인
- [ ] U6. (공통) 반응형/접근성·dg- 클래스 일관성 점검

## 품질 스캔 발견 UI 후보 (2026-06-20 /agency-quality-sweep)
> 이모지 위반 0·dg- 클래스 일관·CTA 명확은 양호. 아래만 결점.
- [ ] QU-1 [P1] `analysis.py` xlsx 분석 실행 중 **로딩 상태 없음**(spinner/progress 부재) → 분석 시작 시 진행 표시.
- [ ] QU-2 [P2] `planning_wizard.py:738-741` 오류 메시지에 **기술 예외(`오류: {exc}`) 노출** → 사용자용 문구로 교체.
- [ ] QU-3 [P2] `planning_wizard.py:225-230` **4단계 진행 표시("Step X/4") 없음** → 현재 단계 시각화(QS-1 메뉴 단순화와 함께 검토).
- [ ] QU-4 [P2] `planning.py` 프로젝트 미선택 시 빈상태 배너 없이 위자드 렌더 / 저장 중 로딩 부재.
- [ ] QU-5 [P2] `thumbnail.py` 생성 실패 시 result_card 미정리 / `analysis.py` xlsx 미업로드 빈상태 안내 없음.
- [ ] QU-6 [P3] `report.py`·`thumbnail.py` 업로드 필요/선택사항 안내 문구 추가.

## 진행 규칙
- 한 번에 한 화면만. 수정 후 실행 렌더(또는 산출물) 확인으로 검수 → `DESIGN_AUDIT.md` 갱신.
