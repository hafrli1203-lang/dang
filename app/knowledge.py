"""전문 지식 베이스 — 광고 실전 교재(당근·메타 퍼포먼스, 윤익 세팅/쿠폰)를 정제해 주입.

LLM Wiki 3계층: raw(app/knowledge/raw/*.txt 원문) → distilled(app/knowledge/distilled_*.md 정제)
→ 주입(system 프롬프트). 매장 위키(이 매장 실측)와 합쳐져 '교재 + 실측'으로 기획한다.
정제 절차는 교재 원문을 Claude로 압축한 것이며, 출처에 충실하게 원칙·체크리스트·벤치마크만 담았다.
"""
import os
from pathlib import Path

_DIR = Path(__file__).parent / "knowledge"
_RAW_DIR = _DIR / "raw"

# 교재 원문(raw) 매핑 — 정제 요약이 아니라 전문(full text)을 주입한다(사용자 지시: "요약하지 말고 다 읽어라").
# raw가 없으면(패키징 빌드 등) 정제본 distilled_*.md로 폴백한다.
_RAW_SOURCES = {
    "daangn": ["daangn_text_perf.txt"],
    "meta": ["meta_perf.txt", "meta_campaign_strategy.txt", "meta_viral_content.txt"],
    "setting": ["yunik_2_setting.txt"],
    "coupon": ["yunik_4_coupon.txt"],
    "performance": ["benchmark_simgok.txt", "ref_real_ads.txt"],
}

# 교재 주입 모드(env KNOWLEDGE_MODE):
#   distilled(기본) — 정제 요약(~9K/콜). 라이브 비교 결과 core(53K)와 품질·속도 동일한데 6배 싸고 안전.
#                     (플레이북·벤치마크가 핵심이고 그건 어느 모드든 들어감 → 교재 전문은 죽은 무게로 판명)
#   core            — 당근 교재 전문 + 메타 요약(~53K). 더 깊지만 이득 없음(증거상). 필요 시 env로.
#   full            — 메타 강의까지 전부 원문(~144K). 가장 무겁고 조율서 한계 초과 위험.
_MODE = os.getenv("KNOWLEDGE_MODE", "distilled").strip().lower()


def _load(name: str) -> str:
    # core 모드에서 메타(대형 강의 전사록)는 원문 대신 정제본을 쓴다(토큰 절약).
    use_raw = _MODE != "distilled" and not (_MODE == "core" and name == "meta")
    # 1) 교재 원문 전문 주입(요약 금지)
    if use_raw:
        parts = []
        for fn in _RAW_SOURCES.get(name, []):
            try:
                parts.append((_RAW_DIR / fn).read_text(encoding="utf-8").strip())
            except OSError:
                pass
        if parts:
            return "\n\n".join(parts)
    # 2) 폴백: 정제본(raw가 .gitignore라 패키징 빌드엔 없을 수 있음)
    try:
        return (_DIR / f"distilled_{name}.md").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _load_playbook() -> str:
    try:
        return (_DIR / "operator_playbook.md").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# 모듈 로드 시 1회 읽어 캐시 (system 프롬프트 = 캐시 친화)
_PLAYBOOK = _load_playbook()  # 실전 고수 운영 플레이북(연령 찢기·자동수동 페어·변수통제) — 최우선
# 교재(권준성·윤익)는 '참고'다 — 일반 원칙·카피·콘텐츠 기법만 빌려 쓰고, 운영 판단은 플레이북/위키가 이긴다.
_DAANGN = _load("daangn")    # [참고] 당근 본질·비즈프로필·소식 3유형·쿠폰 (권준성)
_META = _load("meta")        # [참고] 메타 퍼포먼스 → 일부 원리만 이식 (머신러닝·ABO/CBO는 당근에 무효)
_SETTING = _load("setting")  # [참고] 윤익 세팅 — '타겟 넓혀라/머신러닝' 주장은 당근에서 무시(플레이북이 덮음)
_COUPON = _load("coupon")    # [참고] 윤익 쿠폰 다운율 기법
_PERF = _load("performance")  # 실제 성과 패턴(심곡 벤치마크·터지는 콘텐츠 — 후크·골격·트리거)

# 교재 주입 직전에 박는 우선순위 지침 — 교재가 플레이북과 충돌하면 플레이북이 이긴다.
_PRIORITY_DIRECTIVE = (
    "\n[지식 우선순위 — 충돌 시 위가 이긴다] "
    "①실전 운영 플레이북(위) → ②매장 위키(이 매장 실측) → ③아래 교재(권준성·윤익 등)는 '참고'. "
    "특히 교재의 '연령 타겟을 넓혀라', '머신러닝/알고리즘이 알아서 효율 타겟을 찾아준다', 메타 ABO/CBO는 "
    "당근에 무효다(당근은 머신러닝 없음). 연령을 찢어 직접 끄고, 자동·수동을 똑같이 페어로 운영한다. "
    "교재에선 소식 3유형·9종 카피·쿠폰 설계·원천 콘텐츠·커뮤니티 LMF·MAX CPA만 빌려 쓴다.\n"
)

_HEADER = (
    "━━ 광고 실전 자료 (실전 운영 플레이북 + 참고 교재 — 운영 판단은 플레이북을 최우선으로 따르고, "
    "교재는 원칙·카피·콘텐츠 기법 참고용으로만 쓴다. 매장 위키의 실측과 충돌하면 매장 위키를 우선) ━━\n"
)
_FOOTER = "\n━━ (교재 지식 끝) ━━\n"

# 환각·사실 왜곡 차단 — 모든 생성에 공통 적용(가짜 숫자가 가장 큰 품질 킬러).
_FACT_LOCK = (
    "\n\n━━ [사실관계 락 — 위반 시 출력 무효] ━━\n"
    "- 입력 자료(매장 정보·행사·성과 데이터)에 있는 숫자·가격·기간·조건·상품명은 그대로 인용한다. "
    "추정·반올림·재해석·창작 금지. 입력에 없는 가격/수치를 새로 지어내지 않는다.\n"
    "- 입력에 없는 일별·소재별·캠페인별 수치(예: 특정 날짜 CTR)는 절대 생성·인용하지 않는다. "
    "필요하면 '[매장 확인 필요]'로 표기한다.\n"
    "- 매장 위키·데이터에 없는 추정치(객단가·마진·MAX CPA 등)는 반드시 '[가정]' 라벨 + 근거를 붙이고 사장님 확인을 권한다.\n"
    "- 비교 기준치는 입력 벤치마크 또는 '광역시 표준'이라 명시한 값만 쓴다. 출처 없는 단정 수치 금지.\n"
    "- 시즌·시점은 입력된 집행 기간/이벤트를 따른다. 다른 월·시즌을 임의 추정하지 않는다.\n"
    "- '소재 N개 운영' 식으로 선언했으면 실제 산출물(카피 문구 등)을 N개 전량 제출한다. 골격·구조 설명만 하고 실물을 빼면 무효.\n"
)


def domain_knowledge(scope: str = "full") -> str:
    """주입용 전문 지식 블록. scope로 필요한 부분만 골라 토큰 절약."""
    # 교재(참고)는 scope별로 고른다. _PERF(실제 성과 패턴)가 교재 중 맨 앞('이게 실제로 클릭·전환을 냈다').
    if scope == "setting":
        textbook = [_PERF, _SETTING, _DAANGN, _META, _COUPON]
    elif scope == "report":
        textbook = [_PERF, _DAANGN, _META]
    elif scope == "content":
        textbook = [_PERF, _DAANGN, _COUPON, _META]
    else:  # full / strategy
        textbook = [_PERF, _DAANGN, _META, _SETTING, _COUPON]
    textbook_body = "\n\n".join(p for p in textbook if p)
    # 항상 ①플레이북(최우선) → ②우선순위 지침 → ③참고 교재 순으로 쌓는다.
    blocks = []
    if _PLAYBOOK:
        blocks.append(_PLAYBOOK)
    blocks.append(_PRIORITY_DIRECTIVE)
    if textbook_body:
        blocks.append(f"{_HEADER}{textbook_body}{_FOOTER}")
    return "\n\n" + "\n\n".join(blocks) + _FACT_LOCK
