"""Draw the terms of one contract (the ground truth) before any text is written."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .clauses import Style
from .dates import add_years
from .timeline import in_force

LEADS = [14, 21, 28, 35, 42]
PAYMENTS = [30, 45, 60, 90]
INCOTERMS = ["EXW", "FCA", "CPT", "DAP", "DDP"]
NAME_A = ["Karhu", "Aalto", "Nordic", "Baltic", "Lumi", "Taiga", "Polar", "Vuoksi", "Saimaa", "Kallio",
          "Helmi", "Tuuli", "Rauta", "Koski", "Meri", "Selkä", "Pohja", "Kuura", "Laine", "Vaara"]
NAME_B = ["Metals", "Fastenings", "Components", "Plastics", "Castings", "Electronics", "Logistics",
          "Tooling", "Polymers", "Bearings", "Cables", "Hydraulics"]
SUFFIX = ["Oy", "Oyj", "AB", "GmbH", "Ltd", "A/S"]
MISSING_GROUPS = {"penalty": ["late_penalty_pct_per_day", "penalty_cap_pct"], "defect": ["defect_threshold_pct"],
                  "price_cap": ["price_adjustment_cap_pct"], "volume": ["min_annual_volume_units"],
                  "liability": ["liability_cap_eur"]}


@dataclass
class Contract:
    contract_id: str
    supplier_id: str
    supplier_name: str
    terms: dict            # original terms (before amendments); None = clause absent
    amendments: list[dict]
    style: Style
    flags: dict
    monthly_order_rate: float
    term_years: int

    def current_terms(self) -> dict:
        far = date(2100, 1, 1)
        t = dict(self.terms)
        for f in {a["field"] for a in self.amendments}:
            t[f] = in_force(f, self.terms, self.amendments, far)
        return t


def _name(rng: random.Random, used: set) -> str:
    while True:
        n = f"{rng.choice(NAME_A)} {rng.choice(NAME_B)} {rng.choice(SUFFIX)}"
        if n not in used:
            used.add(n)
            return n


def build_contract(idx: int, supplier_id: str, pcfg: dict, cfg: dict, rng: random.Random, used: set) -> Contract:
    c = cfg["contract"]
    forced = bool(pcfg.get("ignores_amendment"))
    eff = date(2023, 1, 1) + timedelta(days=rng.randint(0, 270))
    eff = eff.replace(day=min(eff.day, 28))
    years = rng.choice([2, 3, 3, 4])
    lead = rng.choice([x for x in LEADS if x >= 21] if forced else LEADS)
    rate = rng.uniform(cfg["orders"]["monthly_rate_min"], cfg["orders"]["monthly_rate_max"])
    price = round(rng.uniform(2, 60), 2)
    annual_units = rate * 12 * 460
    terms = {
        "supplier_name": _name(rng, used),
        "effective_date": eff.isoformat(),
        "expiry_date": add_years(eff, years).isoformat(),
        "lead_time_days": lead,
        "unit_price_eur": price,
        "price_adjustment_cap_pct": rng.choice([0.0, 2.0, 3.0, 5.0]),
        "payment_terms_days": rng.choice(PAYMENTS),
        "incoterm": rng.choice(INCOTERMS),
        "late_penalty_pct_per_day": rng.choice([0.25, 0.5, 1.0]),
        "penalty_cap_pct": rng.choice([5.0, 10.0, 15.0]),
        "defect_threshold_pct": rng.choice([1.0, 1.5, 2.0, 3.0]),
        "min_annual_volume_units": int(round(rng.uniform(0.6, 0.9) * annual_units, -3)),
        "liability_cap_eur": int(max(50_000, 50_000 * round(rng.uniform(0.5, 1.5) * annual_units * price / 50_000))),
        "termination_notice_days": rng.choice([30, 60, 90]),
    }
    missing = [g for g, p in [("penalty", c["p_missing_penalty"]), ("defect", c["p_missing_defect"]),
                              ("price_cap", c["p_missing_price_cap"]), ("volume", c["p_missing_volume"]),
                              ("liability", c["p_missing_liability"])] if rng.random() < p]
    for g in missing:
        for f in MISSING_GROUPS[g]:
            terms[f] = None

    amendments = []
    if forced or rng.random() < c["p_amendment"]:
        fld = "lead_time_days" if (forced or rng.random() < 0.5) else "payment_terms_days"
        if fld == "lead_time_days" and lead <= 14:
            fld = "payment_terms_days"
        old = terms[fld]
        new = rng.choice([x for x in (LEADS if fld == "lead_time_days" else PAYMENTS) if (x < old if fld == "lead_time_days" else x != old)])
        amendments.append({"field": fld, "old": old, "new": new,
                           "effective_date": (eff + timedelta(days=rng.randint(180, 540))).isoformat()})

    st = Style(words_only=rng.random() < c["p_words_only"], lead_in_weeks=rng.random() < c["p_lead_in_weeks"],
               annex_price=rng.random() < c["p_annex_price"], price_comma=rng.random() < 0.3,
               distractor=rng.random() < c["p_distractor"], date_style=rng.choice(["dmy", "mdy", "iso"]),
               numbering=rng.choice(["decimal", "article", "section"]), num_style=rng.randint(0, 2),
               term_variant=rng.choice([1, 2, 3]))
    flags = {
        "words_only": st.words_only, "lead_in_weeks": st.lead_in_weeks and lead % 7 == 0,
        "annex_price": st.annex_price, "distractor": st.distractor,
        "expiry_term_only": st.term_variant == 3,
        "amend_lead": any(a["field"] == "lead_time_days" for a in amendments),
        "amend_payment": any(a["field"] == "payment_terms_days" for a in amendments),
        "missing": missing,
    }
    return Contract(f"C{idx:03d}", supplier_id, terms["supplier_name"], terms, amendments, st, flags, rate, years)
