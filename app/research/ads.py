# -*- coding: utf-8 -*-
"""경쟁 광고 관측 — google-ads.ts / naver-ads.ts / meta-ads.ts 충실 포팅.

각 extractor는 Playwright page에서 검색결과/광고라이브러리를 렌더한 뒤
page.evaluate(JS)로 광고를 긁는다(원본 JS 스크립트를 그대로 재사용). 휴리스틱
점수(compute_*_score)는 순수 함수라 네트워크 없이 단위 테스트한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

from app.research.stealth import random_delay_seconds


@dataclass
class AdObservation:
    engine: str                     # GOOGLE | NAVER | META
    keyword: str
    headline: str
    description: str | None
    display_url: str | None
    landing_url: str | None
    position: int
    heuristic_score: float
    ad_type: str | None = None      # naver: powerlink|brand_search
    raw: dict = field(default_factory=dict)


# ───────────────────────── 휴리스틱 점수 (순수) ─────────────────────────

def compute_search_ad_score(headline: str, description: str | None,
                            position: int, keyword: str) -> int:
    """google/naver 공통 점수(computeScore/computeNaverScore의 공통부)."""
    score = max(0, 10 - position) * 2
    if headline and keyword and keyword.lower() in headline.lower():
        score += 5
    if description:
        score += 3
    return score


def compute_naver_ad_score(headline: str, description: str | None,
                           ad_type: str, position: int, keyword: str) -> int:
    score = compute_search_ad_score(headline, description, position, keyword)
    if ad_type == "brand_search":
        score += 5
    return score


def compute_meta_ad_score(platforms: list, body: str | None, is_active: bool) -> int:
    """meta-ads.ts computeScore 포팅."""
    score = 0
    if is_active:
        score += 3
    if len(platforms) > 1:
        score += 2
    if len(platforms) > 2:
        score += 1
    if body and len(body) > 50:
        score += 2
    if body and len(body) > 150:
        score += 1
    if "instagram" in platforms:
        score += 1
    return score


# ───────────────────────── extract JS (원본 그대로) ─────────────────────────

_GOOGLE_JS = r"""
(() => {
  const results = [];
  const seen = new Set();
  function tryAdd(headline, description, displayUrl, landingUrl) {
    const key = headline + '|' + (landingUrl || '');
    if (!headline || seen.has(key)) return;
    seen.add(key);
    results.push({ headline, description, displayUrl, landingUrl });
  }
  var adBlocks = document.querySelectorAll('#tads, #bottomads');
  for (var b = 0; b < adBlocks.length; b++) {
    var adDivs = adBlocks[b].querySelectorAll(':scope > div');
    for (var i = 0; i < adDivs.length; i++) {
      var ad = adDivs[i];
      var headlineEl = ad.querySelector('div[role="heading"], h3');
      var linkEl = ad.querySelector('a[href^="http"]');
      var descEl = ad.querySelector('.MUxGbd, [data-content-feature]');
      var citeEl = ad.querySelector('cite, .x2VHCd, span.VuuXrf');
      tryAdd(
        headlineEl ? headlineEl.textContent.trim() : '',
        descEl ? descEl.textContent.trim() : null,
        citeEl ? citeEl.textContent.trim() : null,
        linkEl ? linkEl.getAttribute('href') : null
      );
    }
  }
  if (results.length === 0) {
    var adElements = document.querySelectorAll('[data-text-ad]');
    for (var j = 0; j < adElements.length; j++) {
      var el = adElements[j];
      var linkEl2 = el.querySelector('a');
      var headlineEl2 = el.querySelector('div[role="heading"], h3');
      tryAdd(
        headlineEl2 ? headlineEl2.textContent.trim() : '',
        el.querySelector('.MUxGbd') ? el.querySelector('.MUxGbd').textContent.trim() : null,
        el.querySelector('.x2VHCd') ? el.querySelector('.x2VHCd').textContent.trim() : null,
        linkEl2 ? linkEl2.getAttribute('href') : null
      );
    }
  }
  if (results.length === 0) {
    var spans = document.querySelectorAll('span');
    for (var k = 0; k < spans.length; k++) {
      var text = (spans[k].textContent || '').trim().toLowerCase();
      if (text === 'sponsored' || text === '스폰서' || text === '광고') {
        var container = spans[k];
        for (var n = 0; n < 8 && container; n++) {
          container = container.parentElement;
          if (!container) break;
          var heading = container.querySelector('div[role="heading"], h3');
          var link = container.querySelector('a[href^="http"]');
          if (heading && link) {
            tryAdd(
              heading.textContent.trim(),
              (container.querySelector('.MUxGbd, [data-content-feature]') || {}).textContent ? container.querySelector('.MUxGbd, [data-content-feature]').textContent.trim() : null,
              (container.querySelector('cite, span.VuuXrf') || {}).textContent ? container.querySelector('cite, span.VuuXrf').textContent.trim() : null,
              link.getAttribute('href')
            );
            break;
          }
        }
      }
    }
  }
  return results;
})()
"""

_NAVER_JS = r"""
(() => {
  const results = [];
  const powerLinkSection = document.querySelector('#sp_keyword, .sp_keyword, #power_link_body, .keyword_ad_wrap');
  if (powerLinkSection) {
    const items = powerLinkSection.querySelectorAll('li, .lst_type > li');
    for (const li of items) {
      const anchor = li.querySelector('a.link_tit, a.lnk_head, a.tit, a[class*="tit"]');
      const desc = li.querySelector('.link_desc, .ad_dsc, .dsc, [class*="desc"]');
      const urlEl = li.querySelector('.url, cite');
      if (anchor) {
        results.push({
          headline: (anchor.textContent || '').trim(),
          description: desc ? (desc.textContent || '').trim() : null,
          displayUrl: urlEl ? (urlEl.textContent || '').trim() : null,
          landingUrl: anchor.getAttribute('href'),
          adType: 'powerlink',
        });
      }
    }
  }
  const brandSection = document.querySelector('.brand_area, ._brand_ad, .sc_brand, #brand_ad');
  if (brandSection) {
    const anchor = brandSection.querySelector('a.link_tit, a.lnk_head, a.tit, a[class*="tit"]');
    const desc = brandSection.querySelector('.link_desc, .desc, .dsc, [class*="desc"]');
    if (anchor) {
      results.push({
        headline: (anchor.textContent || '').trim(),
        description: desc ? (desc.textContent || '').trim() : null,
        displayUrl: null,
        landingUrl: anchor.getAttribute('href'),
        adType: 'brand_search',
      });
    }
  }
  return results;
})()
"""

# meta-ads.ts EXTRACT_SCRIPT 그대로(이스케이프 \\d 등은 원문 유지).
_META_JS = r"""
(function() {
  var results = [];
  var adLinks = document.querySelectorAll('a[href*="/ads/library/?id="]');
  var processedIds = new Set();
  for (var i = 0; i < adLinks.length; i++) {
    var link = adLinks[i];
    var href = link.getAttribute('href') || '';
    var idMatch = href.match(/id=(\d+)/);
    if (!idMatch) continue;
    var adId = idMatch[1];
    if (processedIds.has(adId)) continue;
    processedIds.add(adId);
    var card = link;
    for (var j = 0; j < 15; j++) {
      if (!card.parentElement) break;
      card = card.parentElement;
      var rect = card.getBoundingClientRect();
      if (rect.width > 300 && rect.height > 150) break;
    }
    var text = card.innerText || '';
    var lines = text.split('\n').map(function(l) { return l.trim(); }).filter(Boolean);
    var pageName = '';
    for (var k = 0; k < Math.min(lines.length, 5); k++) {
      var line = lines[k];
      if (line.length > 2 && !line.match(/^(Ad Library|광고 라이브러리|See ad|광고 보기|Active|Inactive|활성|비활성)/i)) {
        pageName = line; break;
      }
    }
    var startDate = '';
    var datePatterns = [
      /Started running on (.+?)(?:\n|$)/i,
      /시작한 날짜[:\s]*(.+?)(?:\n|$)/,
      /(\d{4}[.\-\/]\s*\d{1,2}[.\-\/]\s*\d{1,2})/,
      /(\w+ \d{1,2},? \d{4})/,
    ];
    for (var p = 0; p < datePatterns.length; p++) {
      var dm = text.match(datePatterns[p]);
      if (dm) { startDate = dm[1].trim(); break; }
    }
    var platforms = [];
    if (text.match(/Facebook/i)) platforms.push('facebook');
    if (text.match(/Instagram/i)) platforms.push('instagram');
    if (text.match(/Messenger/i)) platforms.push('messenger');
    if (text.match(/Audience Network/i)) platforms.push('audience_network');
    var bodyLines = [];
    var afterDate = false;
    for (var m = 0; m < lines.length; m++) {
      var l = lines[m];
      if (l.match(/Started running|시작한 날짜|Platforms?:|플랫폼/i)) { afterDate = true; continue; }
      if (afterDate) {
        if (l.match(/^(See ad|광고 보기|See summary|요약 보기|Ad Library|광고 라이브러리)/i)) break;
        if (l === pageName) continue;
        if (l.length > 5) bodyLines.push(l);
      }
    }
    var images = card.querySelectorAll('img');
    var thumbnailUrl = '';
    for (var im = 0; im < images.length; im++) {
      var src = images[im].src || '';
      if (src && !src.includes('emoji') && !src.includes('icon') && (images[im].width > 50 || src.includes('scontent'))) {
        thumbnailUrl = src; break;
      }
    }
    results.push({
      adId: adId, pageName: pageName,
      body: bodyLines.join(' ').substring(0, 500),
      startDate: startDate, platforms: platforms,
      snapshotUrl: 'https://www.facebook.com/ads/library/?id=' + adId,
      thumbnailUrl: thumbnailUrl,
      isActive: !text.match(/Inactive|비활성/i),
    });
  }
  if (results.length === 0) {
    var bodyText = document.body.innerText;
    // 한국어/영문 라이브러리 ID 모두 매칭 (KR 광고 라이브러리는 '라이브러리 ID:').
    var libIdPattern = /(?:Library ID|라이브러리 ID)[:\s]+(\d+)/gi;
    var match; var idx = 0;
    while ((match = libIdPattern.exec(bodyText)) !== null && idx < 25) {
      var adId2 = match[1];
      if (processedIds.has(adId2)) continue;
      processedIds.add(adId2);
      // ID 이후 텍스트에서 광고 카드 정보를 파싱(다음 라이브러리 ID 전까지).
      var after = bodyText.substring(match.index, match.index + 900);
      var nextId = after.search(/(?:Library ID|라이브러리 ID)[:\s]+\d/i);
      if (nextId > 20) after = after.substring(0, nextId);
      var aLines = after.split('\n').map(function(l){return l.trim();}).filter(Boolean);

      // 게재 시작일: 'YYYY. M. D.에 게재 시작함' 또는 영문.
      var sd = '';
      var sdm = after.match(/(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?)\s*에 게재 시작/) ||
                after.match(/Started running on (.+?)(?:\n|$)/i) ||
                after.match(/시작한 날짜[:\s]*(.+?)(?:\n|$)/);
      if (sdm) sd = sdm[1].trim();

      // 플랫폼
      var plats = [];
      if (after.match(/Facebook|페이스북/i)) plats.push('facebook');
      if (after.match(/Instagram|인스타그램/i)) plats.push('instagram');
      if (after.match(/Messenger|메신저/i)) plats.push('messenger');
      if (after.match(/Audience Network/i)) plats.push('audience_network');

      // 페이지명 = '광고' 라벨 바로 앞 줄 (KR: 광고주명\n광고\n본문). 없으면 '광고 상세 정보 보기' 다음 줄.
      var pName = '';
      for (var q = 0; q < aLines.length; q++) {
        if (aLines[q] === '광고' && q > 0) { pName = aLines[q-1]; break; }
      }
      if (!pName) {
        for (var q2 = 0; q2 < aLines.length; q2++) {
          if (aLines[q2].match(/광고 상세 정보 보기|See ad details/i) && q2+1 < aLines.length) {
            pName = aLines[q2+1]; break;
          }
        }
      }

      // 본문 = '광고' 라벨(또는 페이지명) 이후 의미있는 줄들. UI 잡음 제외.
      var bodyLines2 = [];
      var started = false;
      var JUNK = /^(광고$|광고 상세 정보 보기|See ad details|드롭다운 열기|여러 버전|플랫폼|활성|활동 상태|결과 |필터|정렬|삭제|이 결과에는|자세히 보기|더 알아보기|See more)/;
      for (var r = 0; r < aLines.length; r++) {
        var ln = aLines[r];
        if (ln === '광고') { started = true; continue; }
        if (!started) continue;
        // 다음 광고 경계(라이브러리 ID / 게재 시작)를 만나면 본문 종료.
        if (ln.match(/라이브러리 ID|Library ID|에 게재 시작/)) break;
        if (ln === pName) continue;
        if (JUNK.test(ln)) continue;
        if (ln.replace(/[​\s]/g,'').length < 4) continue;
        bodyLines2.push(ln);
        if (bodyLines2.join(' ').length > 350) break;
      }

      results.push({
        adId: adId2, pageName: pName || '(광고주 미상)',
        body: bodyLines2.join(' ').substring(0, 400),
        startDate: sd, platforms: plats,
        snapshotUrl: 'https://www.facebook.com/ads/library/?id=' + adId2,
        thumbnailUrl: '',
        isActive: !after.match(/Inactive|비활성/i),
      });
      idx++;
    }
  }
  return results.slice(0, 25);
})()
"""

_META_WAIT_JS = (
    "document.body.innerText.includes('Started running on') || "
    "document.body.innerText.includes('시작한 날짜') || "
    "document.body.innerText.includes('게재 시작') || "
    "document.body.innerText.includes('라이브러리 ID') || "
    "document.body.innerText.includes('Library ID') || "
    "document.body.innerText.includes('개의 결과') || "
    "document.querySelectorAll('a[href*=\"/ads/library/?id=\"]').length > 0"
)

_META_POPUP_SELECTORS = (
    'button:has-text("Allow all cookies")', 'button:has-text("모든 쿠키 허용")',
    'button:has-text("Allow essential")', 'button:has-text("필수 쿠키만 허용")',
    'button:has-text("Close")', 'button:has-text("닫기")',
    '[aria-label="Close"]', '[aria-label="닫기"]',
)


# ───────────────────────── extractors (Playwright page) ─────────────────────────

def extract_google_ads(page, keyword: str) -> list[AdObservation]:
    import time
    page.goto(
        f"https://www.google.com/search?q={quote(keyword)}&hl=ko&gl=kr",
        wait_until="domcontentloaded", timeout=15000,
    )
    time.sleep(random_delay_seconds(2000, 4000))
    raw = page.evaluate(_GOOGLE_JS) or []
    out = []
    for idx, ad in enumerate(raw):
        head = ad.get("headline", "")
        desc = ad.get("description")
        out.append(AdObservation(
            engine="GOOGLE", keyword=keyword, headline=head, description=desc,
            display_url=ad.get("displayUrl"), landing_url=ad.get("landingUrl"),
            position=idx + 1,
            heuristic_score=compute_search_ad_score(head, desc, idx + 1, keyword),
        ))
    return out


def extract_naver_ads(page, keyword: str) -> list[AdObservation]:
    page.goto(
        f"https://search.naver.com/search.naver?query={quote(keyword)}",
        wait_until="domcontentloaded", timeout=15000,
    )
    raw = page.evaluate(_NAVER_JS) or []
    out = []
    for idx, ad in enumerate(raw):
        head = ad.get("headline", "")
        desc = ad.get("description")
        at = ad.get("adType", "powerlink")
        out.append(AdObservation(
            engine="NAVER", keyword=keyword, headline=head, description=desc,
            display_url=ad.get("displayUrl"), landing_url=ad.get("landingUrl"),
            position=idx + 1, ad_type=at,
            heuristic_score=compute_naver_ad_score(head, desc, at, idx + 1, keyword),
        ))
    return out


def extract_meta_ads(page, keyword: str) -> list[AdObservation]:
    import time
    params = {
        "active_status": "active", "ad_type": "all", "country": "KR",
        "q": keyword, "search_type": "keyword_unordered",
        "sort_data[direction]": "desc", "sort_data[mode]": "total_impressions",
    }
    page.goto("https://www.facebook.com/ads/library/?" + urlencode(params),
              wait_until="domcontentloaded", timeout=30000)
    # 팝업 닫기
    for sel in _META_POPUP_SELECTORS:
        try:
            page.locator(sel).first.click(timeout=2000)
            time.sleep(random_delay_seconds(500, 1000))
        except Exception:  # noqa: BLE001
            pass
    try:
        page.wait_for_function(_META_WAIT_JS, timeout=15000)
    except Exception:  # noqa: BLE001
        return []
    time.sleep(random_delay_seconds(1500, 2500))
    for _ in range(3):
        page.evaluate("window.scrollBy(0, 1500)")
        time.sleep(random_delay_seconds(800, 1500))
    raw = page.evaluate(_META_JS) or []
    out = []
    for idx, ad in enumerate(raw):
        platforms = ad.get("platforms", []) or []
        body = ad.get("body") or None
        out.append(AdObservation(
            engine="META", keyword=keyword,
            headline=ad.get("pageName") or "Unknown", description=body,
            display_url=ad.get("snapshotUrl"), landing_url=None,
            position=idx + 1,
            heuristic_score=compute_meta_ad_score(platforms, body, ad.get("isActive", True)),
            raw={
                "ad_id": ad.get("adId"), "page_name": ad.get("pageName"),
                "ad_snapshot_url": ad.get("snapshotUrl"),
                "ad_delivery_start_time": ad.get("startDate"),
                "publisher_platforms": platforms,
                "thumbnail_url": ad.get("thumbnailUrl"),
                "is_active": ad.get("isActive", True),
            },
        ))
    return out
