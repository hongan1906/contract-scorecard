"""Clause library: several wordings per clause, so extraction cannot rely on one template."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .dates import fmt_date, words

INCOTERM_NAMES = {"EXW": "Ex Works", "FCA": "Free Carrier", "CPT": "Carriage Paid To",
                  "DAP": "Delivered at Place", "DDP": "Delivered Duty Paid"}
PLACES = ["Helsinki", "Tampere", "Turku", "Oulu", "the Buyer's Vantaa warehouse", "the Supplier's works"]


@dataclass
class Style:
    words_only: bool = False
    lead_in_weeks: bool = False
    annex_price: bool = False
    price_comma: bool = False
    distractor: bool = False
    date_style: str = "dmy"      # dmy | mdy | iso
    numbering: str = "decimal"   # decimal | article | section
    num_style: int = 0           # thousands separator style
    term_variant: int = 1        # 1 explicit expiry | 2 term + expiry | 3 term in years only


def dur(n: int, st: Style, rng: random.Random, unit: str = "days") -> str:
    if st.words_only:
        return f"{words(n)} {unit}"
    opts = [f"{n} {unit}", f"{words(n)} ({n}) {unit}"]
    if unit == "days":
        opts.append(f"{n} calendar days")
    return rng.choice(opts)


def lead_dur(n: int, st: Style, rng: random.Random) -> str:
    if st.lead_in_weeks and n % 7 == 0:
        return dur(n // 7, st, rng, "weeks")
    return dur(n, st, rng)


def pct(x: float, rng: random.Random) -> str:
    return rng.choice([f"{x:g}%", f"{x:g} percent", f"{x:g} per cent"])


def thousands(n: int, st: Style) -> str:
    return [f"{n:,}", f"{n:,}".replace(",", " "), str(n)][st.num_style % 3]


def eur(n: int, st: Style) -> str:
    return f"EUR {thousands(n, st)}"


HEADINGS = {
    "delivery": ["Delivery", "Delivery Lead Time"],
    "price": ["Prices", "Price"],
    "price_adjustment": ["Price Adjustment", "Price Changes"],
    "payment": ["Payment Terms", "Payment"],
    "incoterm": ["Delivery Terms", "Incoterms"],
    "penalty": ["Late Delivery", "Delay Penalties"],
    "quality": ["Quality", "Quality and Acceptance"],
    "volume": ["Volume Commitment", "Minimum Volume"],
    "liability": ["Limitation of Liability", "Liability"],
    "termination": ["Termination"],
    "samples": ["Samples and First Articles"],
}


def r_delivery(t, st, rng):
    D = lead_dur(t["lead_time_days"], st, rng)
    return [rng.choice([
        f"The Supplier shall deliver the Goods within {D} of the date of each Purchase Order.",
        f"Goods shall be delivered no later than {D} after the Supplier receives the Purchase Order. Time is of the essence.",
        f"The delivery lead time for all Purchase Orders is {D} from order placement.",
    ])]


def r_price(t, st, rng):
    if st.annex_price:
        return ["The prices for the Goods are set out in Annex A and apply to all Purchase Orders, exclusive of VAT."]
    p = f"{t['unit_price_eur']:.2f}"
    if st.price_comma:
        p = p.replace(".", ",")
    return [rng.choice([
        f"The unit price for the Goods is EUR {p} per unit, exclusive of VAT.",
        f"The Buyer shall pay the Supplier {p} EUR per unit of Goods delivered, exclusive of VAT.",
    ])]


def r_price_adjustment(t, st, rng):
    c = t["price_adjustment_cap_pct"]
    if c == 0:
        return [rng.choice(["Prices are firm and fixed for the entire Term of this Agreement.",
                            "The prices remain fixed for the entire Term and are not subject to adjustment."])]
    return [rng.choice([
        f"Prices are fixed for the first twelve (12) months. Thereafter the Supplier may increase prices once per year by a maximum of {pct(c, rng)} of the then-current price.",
        f"Any price adjustment shall not exceed {pct(c, rng)} per contract year and requires prior written notice.",
    ])]


def r_payment(t, st, rng):
    D = dur(t["payment_terms_days"], st, rng)
    return [rng.choice([
        f"Payment term: net {D} from the invoice date.",
        f"The Buyer shall pay each undisputed invoice within {D} of receipt.",
        f"Invoices are payable {D} after the invoice date.",
    ])]


def r_incoterm(t, st, rng):
    code, place = t["incoterm"], rng.choice(PLACES)
    return [rng.choice([
        f"Delivery terms: {code} ({INCOTERM_NAMES[code]}) Incoterms 2020, {place}.",
        f"The Goods shall be delivered {code} {place} (Incoterms 2020).",
    ])]


def r_penalty(t, st, rng):
    x, c = t["late_penalty_pct_per_day"], t["penalty_cap_pct"]
    return [rng.choice([
        f"If the Supplier fails to deliver by the agreed date, the Supplier shall pay liquidated damages of {pct(x, rng)} of the value of the delayed Goods for each day of delay, up to a maximum of {pct(c, rng)} of such value.",
        f"Late delivery shall give rise to a penalty of {pct(x, rng)} of the order value per day, capped at {pct(c, rng)} of the order value.",
    ])]


def r_quality(t, st, rng):
    x = pct(t["defect_threshold_pct"], rng)
    return [rng.choice([
        f"The Buyer may reject any delivery lot in which more than {x} of the units are defective.",
        f"The maximum acceptable defect rate is {x} per delivery lot.",
    ])]


def r_volume(t, st, rng):
    N = thousands(t["min_annual_volume_units"], st)
    return [rng.choice([
        f"The Buyer commits to purchase at least {N} units of Goods per contract year.",
        f"The minimum annual purchase volume is {N} units.",
    ])]


def r_liability(t, st, rng):
    N = eur(t["liability_cap_eur"], st)
    return [rng.choice([
        f"The Supplier's total aggregate liability under this Agreement shall not exceed {N}.",
        f"Liability of the Supplier is limited to {N} in the aggregate.",
    ])]


def r_termination(t, st, rng):
    D = dur(t["termination_notice_days"], st, rng)
    return [rng.choice([
        f"Either party may terminate this Agreement for convenience by giving {D} prior written notice.",
        f"A notice period of {D} applies to any termination without cause.",
    ])]


def r_samples(n: int, st, rng):
    return [f"Samples and first articles shall be delivered within {n} days of the Buyer's request."]


RENDER = {"delivery": r_delivery, "price": r_price, "price_adjustment": r_price_adjustment,
          "payment": r_payment, "incoterm": r_incoterm, "penalty": r_penalty, "quality": r_quality,
          "volume": r_volume, "liability": r_liability, "termination": r_termination}

# which gold fields must be present for a clause group to be written
REQUIRES = {"delivery": ["lead_time_days"], "price": ["unit_price_eur"],
            "price_adjustment": ["price_adjustment_cap_pct"], "payment": ["payment_terms_days"],
            "incoterm": ["incoterm"], "penalty": ["late_penalty_pct_per_day", "penalty_cap_pct"],
            "quality": ["defect_threshold_pct"], "volume": ["min_annual_volume_units"],
            "liability": ["liability_cap_eur"], "termination": ["termination_notice_days"]}

BOILERPLATE = [
    ("Confidentiality", "Each party shall keep the terms of this Agreement and all non-public information of the other party confidential and shall not disclose it to third parties without prior written consent."),
    ("Governing Law", "This Agreement is governed by the laws of Finland. Disputes shall be settled by the District Court of Helsinki."),
    ("Force Majeure", "Neither party is liable for delay caused by events beyond its reasonable control, provided that it notifies the other party without undue delay."),
    ("Entire Agreement", "This Agreement constitutes the entire agreement between the parties on its subject matter and supersedes all prior understandings."),
    ("Assignment", "Neither party may assign its rights or obligations under this Agreement without the prior written consent of the other party."),
]


def preamble(buyer: str, supplier: str, rng: random.Random) -> str:
    if rng.random() < 0.5:
        return (f'This Supply Agreement (the "Agreement") is made between {buyer} (the "Buyer") '
                f'and {supplier} (the "Supplier"), together the "Parties".')
    return (f'{supplier} (the "Supplier") and {buyer} (the "Buyer") enter into this Supply Agreement '
            f'(the "Agreement") on the terms set out below.')


def term_clause(eff, exp, years: int, st: Style, rng) -> str:
    e, x = fmt_date(eff, st.date_style), fmt_date(exp, st.date_style)
    Y = f"{words(years)} ({years}) years" if not st.words_only else f"{words(years)} years"
    if st.term_variant == 1:
        return f'This Agreement enters into force on {e} (the "Effective Date") and remains in force until {x}, unless terminated earlier.'
    if st.term_variant == 2:
        return f'This Agreement commences on {e} (the "Effective Date") and continues for a term of {Y}, expiring on {x}.'
    return f'This Agreement is effective from {e} (the "Effective Date") and shall remain in force for {Y} from the Effective Date.'


def amendment_clause(a: dict, st: Style, rng: random.Random) -> str:
    when = fmt_date(__import__("datetime").date.fromisoformat(a["effective_date"]), st.date_style)
    if a["field"] == "lead_time_days":
        D = lead_dur(a["new"], st, rng)
        return (f"The Parties agree that, with effect from {when}, the delivery lead time under this "
                f"Agreement shall be {D}. All other terms of the Agreement remain unchanged.")
    D = dur(a["new"], st, rng)
    return (f"The Parties agree that, with effect from {when}, the payment term under this Agreement "
            f"shall be net {D} from the invoice date. All other terms of the Agreement remain unchanged.")
