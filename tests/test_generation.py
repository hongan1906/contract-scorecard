import hashlib
import json
from datetime import date

import pandas as pd

from contractscore.generate import generate
from contractscore.pdftext import pdf_text


def test_files_and_gold_consistency(small_data):
    pdfs = sorted((small_data / "contracts").glob("*.pdf"))
    golds = sorted((small_data / "gold").glob("*.json"))
    assert len(pdfs) == len(golds) >= 7
    for p in pdfs:
        g = json.loads((small_data / "gold" / f"{p.stem}.json").read_text())
        assert g["terms"]["supplier_name"] in " ".join(pdf_text(p).split())
        # current terms = original terms with amendments applied
        exp = dict(g["terms_original"])
        for a in g["amendments"]:
            assert a["old"] == g["terms_original"][a["field"]] and a["new"] != a["old"]
            exp[a["field"]] = a["new"]
        assert exp == g["terms"]


def test_missing_clause_means_absent_in_pdf_and_gold(small_data):
    for p in (small_data / "gold").glob("*.json"):
        g = json.loads(p.read_text())
        text = pdf_text(small_data / g["file"]).lower()
        if g["terms"]["late_penalty_pct_per_day"] is None:
            assert "liquidated damages" not in text and "penalty of" not in text
            assert g["terms"]["penalty_cap_pct"] is None


def test_orders_are_consistent_with_contracts(small_data):
    o = pd.read_csv(small_data / "orders.csv", parse_dates=["order_date", "delivery_date", "erp_due_date"])
    assert (o.delivery_date > o.order_date).all() and (o.defects <= o.qty).all() and (o.qty > 0).all()
    assert o.order_date.min() >= pd.Timestamp("2023-01-01")
    assert o.delivery_date.max() <= pd.Timestamp("2026-03-31")
    truth = pd.read_csv(small_data / "suppliers_truth.csv")
    assert set(truth.profile) == {"reliable", "slightly_late", "chronic_late", "erratic", "price_creep",
                                  "quality_drift", "ignores_amendment"}
    # a supplier with a lead-time amendment has an ERP due date that is stale after the amendment date
    for _, s in truth[truth.has_lead_amendment].iterrows():
        g = json.loads((small_data / "gold" / f"{s.contract_id}.json").read_text())
        a = next(x for x in g["amendments"] if x["field"] == "lead_time_days")
        after = o[(o.contract_id == s.contract_id) & (o.order_date >= pd.Timestamp(a["effective_date"]))]
        assert ((after.erp_due_date - after.order_date).dt.days == a["old"]).all()


def _digest(d):
    return hashlib.sha256(b"".join(p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file())).hexdigest()


def test_deterministic(tmp_path, cfg):
    generate(tmp_path / "a", cfg, seed=11, n_scale=0.15)
    generate(tmp_path / "b", cfg, seed=11, n_scale=0.15)
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")
    generate(tmp_path / "c", cfg, seed=12, n_scale=0.15)
    assert _digest(tmp_path / "a") != _digest(tmp_path / "c")
