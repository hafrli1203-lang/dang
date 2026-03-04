"""CSV parsers for reporting inputs."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime


HEADER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "date": ("날짜", "일자", "date", "일시", "기간"),
    "cost": ("비용", "광고비", "집행금액", "광고비용", "spend", "cost"),
    "impressions": ("노출", "노출수", "impression", "impressions"),
    "clicks": ("클릭", "클릭수", "click", "clicks"),
    "inquiries": ("채팅", "문의", "대화", "상담", "문의수", "채팅수", "inquiries"),
    "regulars": ("단골", "단골수", "팔로워", "팔로우", "follower", "followers"),
    "coupons": ("쿠폰", "쿠폰사용", "쿠폰사용수", "쿠폰수", "coupon", "coupons"),
    "reach": ("도달", "도달수", "reach"),
    "campaign_name": ("캠페인", "캠페인이름", "campaign"),
}

REQUIRED_FIELDS = ("date", "cost", "impressions", "clicks")
OPTIONAL_FIELDS = ("inquiries", "regulars", "coupons", "reach")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS


def _normalize_header(value: str) -> str:
    lowered = value.strip().lower()
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", lowered)


def _looks_like_rate_header(value: str) -> bool:
    normalized = _normalize_header(value)
    return "률" in normalized or "rate" in normalized or "ratio" in normalized


def _build_header_map(headers: list[str]) -> dict[str, int]:
    """Map CSV headers to internal field names.

    Uses candidate-priority matching: for each field, tries the most specific
    candidate first across ALL headers before falling back to broader candidates.
    This prevents e.g. '문의' matching '전화 문의 수' when '채팅 문의 수' exists.
    """
    header_map: dict[str, int] = {}
    used_cols: set[int] = set()
    _numeric_fields = {"impressions", "clicks", "inquiries", "regulars", "coupons", "reach"}
    normalized_headers = [(idx, _normalize_header(h), h) for idx, h in enumerate(headers)]

    for field, candidates in HEADER_CANDIDATES.items():
        if field in header_map:
            continue
        for candidate in candidates:
            matched = False
            for idx, normalized, raw in normalized_headers:
                if idx in used_cols:
                    continue
                if field in _numeric_fields and _looks_like_rate_header(raw):
                    continue
                if normalized == candidate or candidate in normalized:
                    header_map[field] = idx
                    used_cols.add(idx)
                    matched = True
                    break
            if matched:
                break
    return header_map


def _parse_int(value: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError("empty numeric value")
    cleaned = re.sub(r"[^\d-]", "", text)
    if cleaned in {"", "-"}:
        raise ValueError(f"invalid numeric value: {value!r}")
    return int(cleaned)


def _parse_date(value: str) -> date:
    text = value.strip()
    if not text:
        raise ValueError("empty date value")

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    normalized = (
        text.replace("년", "-")
        .replace("월", "-")
        .replace("일", "")
        .replace(".", "-")
        .replace("/", "-")
    )
    normalized = re.sub(r"\s+", "", normalized)
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if match:
        year, month, day = (int(group) for group in match.groups())
        return date(year, month, day)

    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if match:
        year, month, day = (int(group) for group in match.groups())
        return date(year, month, day)

    raise ValueError(f"invalid date value: {value!r}")


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-16"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: charset-normalizer for unknown encodings
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(data).best()
        if result:
            return str(result)
    except ImportError:
        pass
    return data.decode("utf-8-sig", errors="replace")


def parse_daangn_csv(data: bytes) -> tuple[list[dict], list[str]]:
    """Parse Daangn daily-performance CSV bytes to internal rows."""
    if not data:
        return [], []

    text = _decode_csv_bytes(data)
    reader = csv.reader(io.StringIO(text))
    all_rows = list(reader)

    if not all_rows:
        return [], []

    header_index = -1
    header_row: list[str] = []
    for idx, row in enumerate(all_rows):
        if any(cell.strip() for cell in row):
            header_index = idx
            header_row = row
            break

    if header_index < 0:
        return [], ["header row not found"]

    header_map = _build_header_map(header_row)
    warnings: list[str] = []
    missing_required = [field for field in REQUIRED_FIELDS if field not in header_map]
    if missing_required:
        warnings.append(f"missing required headers: {', '.join(missing_required)}")
        return [], warnings

    parsed_rows: list[dict] = []
    skipped = 0
    for offset, row in enumerate(all_rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            skipped += 1
            warnings.append(f"line {offset}: empty row")
            continue

        try:
            date_value = _parse_date(row[header_map["date"]] if header_map["date"] < len(row) else "")
            parsed: dict[str, int | str] = {
                "date": date_value.isoformat(),
                "cost": _parse_int(row[header_map["cost"]] if header_map["cost"] < len(row) else ""),
                "impressions": _parse_int(
                    row[header_map["impressions"]] if header_map["impressions"] < len(row) else ""
                ),
                "clicks": _parse_int(row[header_map["clicks"]] if header_map["clicks"] < len(row) else ""),
                "inquiries": 0,
                "regulars": 0,
                "coupons": 0,
                "reach": 0,
            }
            # String field: campaign_name
            cn_col = header_map.get("campaign_name")
            if cn_col is not None and cn_col < len(row):
                parsed["campaign_name"] = row[cn_col].strip()
            else:
                parsed["campaign_name"] = ""
        except (ValueError, OverflowError) as exc:
            skipped += 1
            warnings.append(f"line {offset}: skipped ({exc})")
            continue

        for optional in OPTIONAL_FIELDS:
            column = header_map.get(optional)
            if column is None:
                continue
            raw_value = row[column] if column < len(row) else ""
            if not raw_value.strip():
                parsed[optional] = 0
                continue
            try:
                parsed[optional] = _parse_int(raw_value)
            except (ValueError, OverflowError):
                parsed[optional] = 0
                warnings.append(f"line {offset}: invalid {optional} value, defaulted to 0")

        parsed_rows.append(parsed)

    if skipped:
        warnings.append(f"skipped rows: {skipped}")
    return parsed_rows, warnings

