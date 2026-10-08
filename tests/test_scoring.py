import numpy as np
import pandas as pd

from contractscore.compare import auc_low_is_bad
from contractscore.scoring import contract_scorecard, generic_scorecard
from contractscore.timeline import in_force


def mk(rows):
    base = dict(supplier_id="S1", contract_id="C1", qty=100, erp_unit_price=10.0, defects=0, invoice_price=10.0)
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["erp_due_date"] = df.get("erp_due_date", df["order_date"])
    return df


TERMS = {"effective_date": "2023-01-01", "unit_price_eur": 10.0, "price_adjustment_cap_pct": 3.0,
         "lead_time_days": 30, "defect_threshold_pct": 2.0, "late_penalty_pct_per_day": 1.0, "penalty_cap_pct": 5.0}


def test_timeline_amendment():
    am = [{"field": "lead_time_days", "old": 30, "new": 21, "effective_date": "2024-01-01"}]
    assert in_force("lead_time_days", TERMS, am, pd.Timestamp("2023-12-31")) == 30
    assert in_force("lead_time_days", TERMS, am, pd.Timestamp("2024-01-01")) == 21


def test_contract_aware_uses_terms_in_force():
    am = {"C1": [{"field": "lead_time_days", "old": 30, "new": 21, "effective_date": "2024-01-01"}]}
    o = mk([
        dict(order_date="2023-06-01", delivery_date="2023-06-29", erp_due_date="2023-07-01"),   # 28d <= 30: ok
        dict(order_date="2024-02-01", delivery_date="2024-02-29", erp_due_date="2024-03-02"),   # 28d > 21: late 7d
    ])
    cfg = __import__("contractscore.config", fromlist=["x"]).load_config()
    r = contract_scorecard(o, {"C1": TERMS}, am, cfg).loc["S1"]
    assert r.delivery == 50.0
    # penalty: 7 days * 1% = 7% -> capped at 5% of order value (100 * 10 = 1000)
    assert abs(r.penalty_exposure_eur - 50.0) < 1e-9
    g = generic_scorecard(o, cfg).loc["S1"]
    assert g.delivery == 100.0  # stale ERP date hides the breach


def test_price_cap_quality_and_not_applicable():
    cfg = __import__("contractscore.config", fromlist=["x"]).load_config()
    o = mk([
        dict(order_date="2023-03-01", delivery_date="2023-03-10", invoice_price=10.0, defects=1),
        dict(order_date="2024-03-01", delivery_date="2024-03-10", invoice_price=10.30, defects=3),  # +3% ok; 3% defects > 2%
        dict(order_date="2024-04-01", delivery_date="2024-04-10", invoice_price=10.31, defects=0),  # over the cap
    ])
    r = contract_scorecard(o, {"C1": TERMS}, {}, cfg).loc["S1"]
    assert abs(r.price - 100 * 2 / 3) < 1e-9 and abs(r.quality - 100 * 2 / 3) < 1e-9
    no_defect = {**TERMS, "defect_threshold_pct": None, "price_adjustment_cap_pct": None}
    r2 = contract_scorecard(o, {"C1": no_defect}, {}, cfg).loc["S1"]
    assert np.isnan(r2.quality) and np.isnan(r2.price) and r2.n_components == 1
    assert r2.composite == r2.delivery  # weights renormalised to the one scorable component


def test_auc():
    assert auc_low_is_bad(pd.Series([1, 2]), pd.Series([5, 6])) == 1.0
    assert auc_low_is_bad(pd.Series([5, 6]), pd.Series([1, 2])) == 0.0
    assert auc_low_is_bad(pd.Series([3]), pd.Series([3])) == 0.5
