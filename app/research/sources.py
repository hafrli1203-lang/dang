# -*- coding: utf-8 -*-
"""소스 정책 레지스트리 — C:/project/search prisma/seed.ts의 충실 포팅.

23개 커뮤니티/검색 소스. 네이버 5종은 네이버 검색 API, 나머지는 Google CSE의
site: 제한 검색으로 발견(discover)한다. fetch_mode는 본문 수집 전략(HTTP 우선 /
Playwright 우선)을 가리키며, Playwright 미설치 시 모두 HTTP로 폴백한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DiscoveryMethod = Literal["NAVER_API", "GOOGLE_CSE"]
FetchMode = Literal["FETCH_FIRST", "PLAYWRIGHT_FIRST"]
AuthRequirement = Literal["NONE", "LOGIN_OPTIONAL", "LOGIN_REQUIRED"]


@dataclass(frozen=True)
class SourcePolicy:
    id: str
    label: str
    discovery_method: DiscoveryMethod
    fetch_mode: FetchMode = "FETCH_FIRST"
    auth_requirement: AuthRequirement = "NONE"
    naver_api_type: str | None = None     # blog, cafearticle, kin, news, webkr
    cse_site_domain: str | None = None    # e.g. "theqoo.net"
    enabled: bool = True


# 순서/값은 search 프로젝트 seed.ts와 1:1 대응.
SOURCE_POLICIES: tuple[SourcePolicy, ...] = (
    SourcePolicy("nv_blog", "네이버 블로그", "NAVER_API", "FETCH_FIRST", "NONE", naver_api_type="blog"),
    SourcePolicy("nv_cafe", "네이버 카페", "NAVER_API", "PLAYWRIGHT_FIRST", "LOGIN_OPTIONAL", naver_api_type="cafearticle"),
    SourcePolicy("nv_kin", "네이버 지식인", "NAVER_API", "FETCH_FIRST", "NONE", naver_api_type="kin"),
    SourcePolicy("nv_news", "네이버 뉴스", "NAVER_API", "FETCH_FIRST", "NONE", naver_api_type="news"),
    SourcePolicy("nv_post", "네이버 포스트", "NAVER_API", "FETCH_FIRST", "NONE", naver_api_type="webkr"),
    SourcePolicy("dc_inside", "DCinside", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="dcinside.com"),
    SourcePolicy("theqoo", "더쿠", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="theqoo.net"),
    SourcePolicy("instiz", "인스티즈", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="instiz.net"),
    SourcePolicy("ruliweb", "루리웹", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="ruliweb.com"),
    SourcePolicy("ppomppu", "뽐뿌", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="ppomppu.co.kr"),
    SourcePolicy("clien", "클리앙", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="clien.net"),
    SourcePolicy("mlbpark", "MLBPark", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="mlbpark.donga.com"),
    SourcePolicy("fm_korea", "에펨코리아", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="fmkorea.com"),
    SourcePolicy("daum_cafe", "다음 카페", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "LOGIN_OPTIONAL", cse_site_domain="cafe.daum.net"),
    SourcePolicy("tistory", "티스토리", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="tistory.com"),
    SourcePolicy("reddit_kr", "Reddit Korea", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="reddit.com"),
    SourcePolicy("google", "Google 일반검색", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain=None),
    SourcePolicy("inven", "인벤", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="inven.co.kr"),
    SourcePolicy("todayhumor", "오늘의유머", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="todayhumor.co.kr"),
    SourcePolicy("ilbe", "일베", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="ilbe.com"),
    SourcePolicy("bobaedream", "보배드림", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="bobaedream.co.kr"),
    SourcePolicy("humoruniv", "웃긴대학", "GOOGLE_CSE", "FETCH_FIRST", "NONE", cse_site_domain="humoruniv.com"),
    SourcePolicy("nate_pann", "네이트판", "GOOGLE_CSE", "PLAYWRIGHT_FIRST", "NONE", cse_site_domain="pann.nate.com"),
)

SOURCES_BY_ID: dict[str, SourcePolicy] = {s.id: s for s in SOURCE_POLICIES}

# 자영업 광고 콘텐츠 리서치 기본값: 네이버 블로그/카페/지식인 (키 1개로 가장 풍부).
DEFAULT_SOURCE_IDS: tuple[str, ...] = ("nv_blog", "nv_cafe", "nv_kin")


def get_source(source_id: str) -> SourcePolicy | None:
    return SOURCES_BY_ID.get(source_id)


def naver_sources() -> list[SourcePolicy]:
    return [s for s in SOURCE_POLICIES if s.discovery_method == "NAVER_API"]


def cse_sources() -> list[SourcePolicy]:
    return [s for s in SOURCE_POLICIES if s.discovery_method == "GOOGLE_CSE"]
