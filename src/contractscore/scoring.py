"""Two supplier scorecards over the same order history.

generic          : what a scorecard without contract knowledge can do. On-time vs the ERP due date,
                   defect rate vs ONE company-wide limit, price vs the ERP standard price.
contract-aware   : each supplier is judged against ITS OWN contract terms in force on the order date.
                   Components a contract does not define are n/a and the weights are renormalised.

Scores are deterministic formulas (0-100). The LLM only supplies the terms, never the score.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .timeline import in_force


def _composite(comp: dict, cfg: dict) -> float:
    w = {"delivery": cfg["scoring"]["weight_delivery"], "quality": cfg["scoring"]["weight_quality"],
         "price": cfg["scoring"]["weight_price"]}
    use = {k: v for k, v in comp.items() if v is not None and not np.isnan(v)}
    tw = sum(w[k] for k in use)
    return float(sum(w[k] * v for k, v in use.items()) / tw) if tw else np.nan


def _prep(orders: pd.DataFrame) -> pd.DataFrame:
    o = orders.copy()
    for c in ["order_date", "erp_due_date", "delivery_date", "invoice_date", "paid_date"]:
        if c in o:
            o[c] = pd.to_datetime(o[c])
    return o


def generic_scorecard(orders: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    s, rows = cfg["scoring"], []
    for sid, o in _prep(orders).groupby("supplier_id"):
        late = (o.delivery_date - o.erp_due_date).dt.days.clip(lower=0)
        delivery = 100 * float((late == 0).mean())
        quality = 100 * float(((o.defects / o.qty * 100) <= s["generic_defect_limit_pct"]).mean())
        ppv = float(((o.invoice_price / o.erp_unit_price - 1) * 100).mean())
        price = float(100 - np.clip(ppv * s["generic_ppv_scale"], 0, 100))
        comp = {"delivery": delivery, "quality": quality, "price": price}
        rows.append({"supplier_id": sid, "n_orders": len(o), **comp, "composite": _composite(comp, cfg),
                     "mean_lead_dev_days": float((o.delivery_date - o.erp_due_date).dt.days.mean())})
    return pd.DataFrame(rows).set_index("supplier_id")


def contract_scorecard(orders: pd.DataFrame, terms: dict, amendments: dict, cfg: dict) -> pd.DataFrame:
    """terms[contract_id] = term dict (original values if `amendments` given, extracted values otherwise)."""
    rows = []
    for sid, o in _prep(orders).groupby("supplier_id"):
        cid = o.contract_id.iloc[0]
        t, am = terms.get(cid) or {}, amendments.get(cid) or []
        comp = {"delivery": np.nan, "quality": np.nan, "price": np.nan}
        penalty = np.nan
        lead = o.order_date.map(lambda d: in_force("lead_time_days", t, am, d))
        late = None
        if lead.notna().all():
            due = o.order_date + pd.to_timedelta(lead.astype(float), unit="D")
            late = (o.delivery_date - due).dt.days.clip(lower=0)
            comp["delivery"] = 100 * float((late == 0).mean())
        thr = t.get("defect_threshold_pct")
        if thr is not None:
            comp["quality"] = 100 * float(((o.defects / o.qty * 100) <= thr + 1e-9).mean())
        eff, base, cap = t.get("effective_date"), t.get("unit_price_eur"), t.get("price_adjustment_cap_pct")
        if eff and base is not None and cap is not None:
            yrs = ((o.order_date - pd.Timestamp(eff)).dt.days / 365.25).astype(int)
            allowed = (base * (1 + cap / 100) ** yrs).round(2)
            comp["price"] = 100 * float((o.invoice_price <= allowed + 1e-9).mean())
        pct, capp = t.get("late_penalty_pct_per_day"), t.get("penalty_cap_pct")
        if late is not None and pct is not None and capp is not None:
            value = o.qty * o.invoice_price
            penalty = float((value * np.minimum(pct * late, capp) / 100).sum())
        rows.append({"supplier_id": sid, "contract_id": cid, "n_orders": len(o), **comp,
                     "composite": _composite(comp, cfg), "penalty_exposure_eur": penalty,
                     "n_components": sum(not np.isnan(v) for v in comp.values())})
    return pd.DataFrame(rows).set_index("supplier_id")
