"""Date formatting/parsing helpers and number-to-words."""
from __future__ import annotations

import re
from datetime import date

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
_M = "|".join(MONTHS)
DATE_RE = rf"(?:\d{{1,2}}\s+(?:{_M})\s+\d{{4}}|(?:{_M})\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
         "fifteen sixteen seventeen eighteen nineteen").split()
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


def words(n: int) -> str:
    if not 0 <= n < 100:
        raise ValueError(n)
    if n < 20:
        return _ONES[n]
    t, o = divmod(n, 10)
    return _TENS[t] + (f"-{_ONES[o]}" if o else "")


def fmt_date(d: date, style: str) -> str:
    if style == "dmy":
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    if style == "mdy":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    return d.isoformat()


def parse_date(s: str) -> str | None:
    """Return ISO date for any of the three formats above, else None."""
    s = " ".join(str(s).split())
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return date.fromisoformat(s).isoformat()
        m = re.fullmatch(rf"(\d{{1,2}}) ({_M}) (\d{{4}})", s)
        if m:
            return date(int(m[3]), MONTHS.index(m[2]) + 1, int(m[1])).isoformat()
        m = re.fullmatch(rf"({_M}) (\d{{1,2}}), (\d{{4}})", s)
        if m:
            return date(int(m[3]), MONTHS.index(m[1]) + 1, int(m[2])).isoformat()
    except ValueError:
        return None
    return None


def add_years(d: date, n: int) -> date:
    return d.replace(year=d.year + n)
