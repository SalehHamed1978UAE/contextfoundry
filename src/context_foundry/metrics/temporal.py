from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
import calendar
from typing import Optional, Tuple, Dict, Callable


@dataclass(frozen=True)
class NormalizedPeriod:
    start: date
    end: date
    label: str


def _year_from_str(value: str) -> int:
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def quarter_to_range(q: int, year: int) -> NormalizedPeriod:
    start_month = 1 + (q - 1) * 3
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return NormalizedPeriod(start=start, end=end, label=f"Q{q} {year}")


def half_to_range(h: int, year: int) -> NormalizedPeriod:
    if h == 1:
        start = date(year, 1, 1)
        end = date(year, 6, 30)
    else:
        start = date(year, 7, 1)
        end = date(year, 12, 31)
    return NormalizedPeriod(start=start, end=end, label=f"H{h} {year}")


def month_range(start_mon: str, end_mon: str, year: int) -> NormalizedPeriod:
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    sm = month_map[start_mon.lower()[:3]]
    em = month_map[end_mon.lower()[:3]]
    start = date(year, sm, 1)
    end = date(year, em, calendar.monthrange(year, em)[1])
    label = f"{start_mon}-{end_mon} {year}"
    return NormalizedPeriod(start=start, end=end, label=label)


TEMPORAL_PATTERNS: Dict[str, Callable[[re.Match], NormalizedPeriod]] = {
    r"Q([1-4])\s*(\d{2,4})": lambda m: quarter_to_range(int(m[1]), _year_from_str(m[2])),
    r"([1-4])Q\s*(\d{2,4})": lambda m: quarter_to_range(int(m[1]), _year_from_str(m[2])),
    r"first quarter(?:\s+of)?\s*(\d{4})": lambda m: quarter_to_range(1, int(m[1])),
    r"second quarter(?:\s+of)?\s*(\d{4})": lambda m: quarter_to_range(2, int(m[1])),
    r"third quarter(?:\s+of)?\s*(\d{4})": lambda m: quarter_to_range(3, int(m[1])),
    r"fourth quarter(?:\s+of)?\s*(\d{4})": lambda m: quarter_to_range(4, int(m[1])),
    r"FY\s*(\d{2,4})": lambda m: NormalizedPeriod(
        start=date(_year_from_str(m[1]), 1, 1),
        end=date(_year_from_str(m[1]), 12, 31),
        label=f"FY{_year_from_str(m[1])}",
    ),
    r"(\d{4})\s*annual": lambda m: NormalizedPeriod(
        start=date(int(m[1]), 1, 1),
        end=date(int(m[1]), 12, 31),
        label=f"{m[1]} annual",
    ),
    r"CY\s*(\d{4})": lambda m: NormalizedPeriod(
        start=date(int(m[1]), 1, 1),
        end=date(int(m[1]), 12, 31),
        label=f"CY{m[1]}",
    ),
    r"H([12])\s*(\d{4})": lambda m: half_to_range(int(m[1]), int(m[2])),
    r"([12])H\s*(\d{4})": lambda m: half_to_range(int(m[1]), int(m[2])),
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-–](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{4})":
        lambda m: month_range(m[1], m[2], int(m[3])),
    r"^(\d{4})$": lambda m: NormalizedPeriod(
        start=date(int(m[1]), 1, 1),
        end=date(int(m[1]), 12, 31),
        label=m[1],
    ),
}


def normalize_period(text: str) -> Optional[NormalizedPeriod]:
    if not text:
        return None
    raw = text.strip()
    for pattern, handler in TEMPORAL_PATTERNS.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return handler(match)
    return None


def temporal_relationship(p1: NormalizedPeriod, p2: NormalizedPeriod) -> str:
    if p1.start == p2.start and p1.end == p2.end:
        return "IDENTICAL"
    if p1.end <= p2.start or p2.end <= p1.start:
        gap = min(abs((p2.start - p1.end).days), abs((p1.start - p2.end).days))
        return "ADJACENT" if gap < 5 else "DISJOINT"
    if p1.start >= p2.start and p1.end <= p2.end:
        return "CONTAINED_IN"
    if p2.start >= p1.start and p2.end <= p1.end:
        return "CONTAINS"
    return "OVERLAPPING"
