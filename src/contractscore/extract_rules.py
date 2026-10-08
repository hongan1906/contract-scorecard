"""Rule-based baseline: regular expressions, first match wins.

Deliberately simple and honest: it reads digits next to keywords, so it cannot read
spelled-out numbers, weeks, annex tables, expiry terms in years, or amendments. That is
exactly what the LLM extractor is supposed to be compared against.
"""
from __future__ import annotations

import re

from .dates import DATE_RE, parse_date
from .schema import FIELDS

_NUM = r"(\d+(?:[.,]\d+)?)"
_PCT = r"\s*(?:%|percent|per cent)"
_DAYS = r"(\d+)\)?\s*(?:calendar\s+)?days"
_BIG = r"(\d[\d,\s]*\d)"


def _first(pattern: str, text: str, flags=re.I):
    m = re.search(pattern, text, flags)
    return next((g for g in m.groups() if g is not None), None) if m else None


def _f(s):
    return None if s is None else float(s.replace(",", "."))


def _i(s):
    return None if s is None else int(re.sub(r"\D", "", s))


def extract_rules(text: str) -> dict:
    t = " ".join(text.split())
    out = dict.fromkeys(FIELDS)
    m = re.search(r"((?:[A-Z][^\W\d_]+\s+){1,3}(?:Oyj|Oy|AB|GmbH|Ltd|A/S))\s*\((?:the\s+)?\"Supplier\"\)", t)
    out["supplier_name"] = m.group(1).strip() if m else None
    eff = _first(rf"(?:enters into force on|commences on|is effective from)\s+({DATE_RE})", t)
    exp = _first(rf"(?:remains in force until|expiring on)\s+({DATE_RE})", t)
    out["effective_date"] = parse_date(eff) if eff else None
    out["expiry_date"] = parse_date(exp) if exp else None
    out["lead_time_days"] = _i(_first(rf"(?:deliver\w*|lead time)[^.]{{0,120}}?{_DAYS}", t))
    price = _first(rf"EUR\s*(\d+[.,]\d{{2}})", t) or _first(rf"(\d+[.,]\d{{2}})\s*EUR", t)
    out["unit_price_eur"] = _f(price)
    cap = _first(rf"(?:maximum of|shall not exceed)\s+{_NUM}{_PCT}", t)
    if cap is None and re.search(r"(?:firm and fixed|remain fixed)", t, re.I):
        cap = "0"
    out["price_adjustment_cap_pct"] = _f(cap)
    out["payment_terms_days"] = _i(_first(rf"\b(?:net|pay\w*)\b[^.]{{0,80}}?{_DAYS}", t))
    out["incoterm"] = _first(r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP)\b", t, 0)
    out["late_penalty_pct_per_day"] = _f(_first(rf"{_NUM}{_PCT}\s+of\s+the[^.]{{0,40}}?\b(?:per|each)\s+day", t))
    out["penalty_cap_pct"] = _f(_first(rf"(?:capped at|maximum of)\s+{_NUM}{_PCT}\s+of\s+(?:such|the)\s+(?:order\s+)?value", t))
    out["defect_threshold_pct"] = _f(_first(rf"(?:more than|defect rate (?:is|of))\s+{_NUM}{_PCT}", t))
    out["min_annual_volume_units"] = _i(_first(rf"(?:at least|minimum annual purchase volume is)\s+{_BIG}\s+units", t))
    out["liability_cap_eur"] = _i(_first(rf"liabilit\w*[^.]{{0,100}}?EUR\s*{_BIG}", t))
    out["termination_notice_days"] = _i(_first(rf"terminat\w*[^.]{{0,100}}?{_DAYS}", t)
                                        or _first(rf"notice period of[^.]{{0,30}}?{_DAYS}", t))
    return out
