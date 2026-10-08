"""The fields extracted from a contract, and normalisation for comparison."""
from __future__ import annotations

FIELDS: dict[str, str] = {
    "supplier_name": "str",
    "effective_date": "date",
    "expiry_date": "date",
    "lead_time_days": "int",
    "unit_price_eur": "float",
    "price_adjustment_cap_pct": "float",   # 0 = fixed price; None = clause absent
    "payment_terms_days": "int",
    "incoterm": "str",
    "late_penalty_pct_per_day": "float",   # % of order value per day late
    "penalty_cap_pct": "float",            # max total penalty, % of order value
    "defect_threshold_pct": "float",       # max acceptable defect rate per delivery lot
    "min_annual_volume_units": "int",
    "liability_cap_eur": "float",
    "termination_notice_days": "int",
}

DESCRIPTIONS = {
    "supplier_name": "legal name of the supplier (the seller)",
    "effective_date": "date the agreement takes effect, ISO YYYY-MM-DD",
    "expiry_date": "date the agreement expires, ISO YYYY-MM-DD (compute it if only a term in years is given)",
    "lead_time_days": "delivery lead time in calendar days from purchase order (convert weeks to days)",
    "unit_price_eur": "unit price of the goods in EUR",
    "price_adjustment_cap_pct": "maximum yearly price increase in percent; 0 if prices are fixed",
    "payment_terms_days": "days from invoice to payment",
    "incoterm": "three-letter Incoterms 2020 code",
    "late_penalty_pct_per_day": "late-delivery penalty, percent of order value per day of delay",
    "penalty_cap_pct": "maximum total late-delivery penalty, percent of order value",
    "defect_threshold_pct": "maximum acceptable defect rate per delivery lot, percent",
    "min_annual_volume_units": "buyer's minimum annual purchase commitment in units",
    "liability_cap_eur": "supplier's aggregate liability cap in EUR",
    "termination_notice_days": "notice period for termination without cause, in days",
}


def norm(field: str, v):
    """Normalise a value so predictions and gold can be compared exactly."""
    if v is None or v == "":
        return None
    t = FIELDS[field]
    try:
        if t == "str":
            return " ".join(str(v).split()).lower()
        if t == "date":
            return str(v)[:10]
        return round(float(v), 6)
    except (TypeError, ValueError):
        return None
