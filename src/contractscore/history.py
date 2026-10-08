"""Simulate order / delivery / invoice history for one supplier from its hidden behaviour profile."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .contracts import Contract
from .timeline import in_force


def generate_history(ct: Contract, pcfg: dict, applies_cap: bool, cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    t = ct.terms
    eff, exp = date.fromisoformat(t["effective_date"]), date.fromisoformat(t["expiry_date"])
    end = min(exp, date.fromisoformat(cfg["run"]["history_end"])) - timedelta(days=75)  # leave room to deliver
    span = (end - eff).days
    n = int(rng.poisson(ct.monthly_order_rate * span / 30.4375))
    offsets = np.sort(rng.integers(0, span, n))
    o = cfg["orders"]
    rows = []
    amend_lead = [a for a in ct.amendments if a["field"] == "lead_time_days"]
    cap = t.get("price_adjustment_cap_pct")
    for k, off in enumerate(offsets):
        od = eff + timedelta(days=int(off))
        years = (od - eff).days / 365.25
        lead_now = in_force("lead_time_days", t, ct.amendments, od)
        if pcfg.get("ignores_amendment") and amend_lead:
            lead_now = t["lead_time_days"]  # keeps delivering on the old lead time
        if rng.random() < pcfg["p_late"]:
            shift = int(rng.integers(pcfg["late_min"], pcfg["late_max"] + 1))
        else:
            shift = -int(rng.integers(pcfg["early_min"], pcfg["early_max"] + 1))
        actual = max(1, lead_now + shift)
        qty = int(np.clip(round(rng.lognormal(6.0, 0.5)), 20, 3000))
        p_def = max(0.0, pcfg["base_defect"] + pcfg["defect_drift_per_year"] * years)
        defects = int(rng.binomial(qty, min(p_def, 0.5)))
        base = t["unit_price_eur"]
        factor = (1 + pcfg["price_drift_per_year"]) ** years
        if applies_cap and cap:
            factor = max(factor, (1 + cap / 100) ** int(years))
        delivery = od + timedelta(days=actual)
        pay_days = in_force("payment_terms_days", t, ct.amendments, delivery)
        rows.append({
            "order_id": f"{ct.contract_id}-{k + 1:04d}", "supplier_id": ct.supplier_id, "contract_id": ct.contract_id,
            "order_date": od, "qty": qty,
            "erp_due_date": od + timedelta(days=t["lead_time_days"] if o["erp_stale"] else lead_now),
            "erp_unit_price": base, "delivery_date": delivery, "defects": defects,
            "invoice_price": round(base * factor, 2), "invoice_date": delivery,
            "paid_date": delivery + timedelta(days=int(pay_days + rng.integers(o["payment_noise_min"], o["payment_noise_max"] + 1))),
        })
    return pd.DataFrame(rows)
