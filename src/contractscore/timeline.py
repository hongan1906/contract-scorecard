"""Which contract terms are in force on a given date (amendments change them)."""
from __future__ import annotations

from datetime import date


def _d(x) -> date:
    return x.date() if hasattr(x, "date") else x


def in_force(field: str, terms: dict, amendments: list[dict] | None, when):
    """Value of `field` on `when`, starting from the original `terms` and applying amendments."""
    when = _d(when)
    v = terms.get(field)
    for a in sorted(amendments or [], key=lambda a: a["effective_date"]):
        if a["field"] == field and when >= date.fromisoformat(a["effective_date"]):
            v = a["new"]
    return v
