import json

import pytest

from contractscore.evaluate import field_table, long_outcomes, outcome
from contractscore.extract_llm import build_prompt, extract_llm, parse_response
from contractscore.extract_rules import extract_rules


def test_rules_on_clean_text():
    text = '''Karhu Metals Oy (the "Supplier") and Nordvik Industrial Oy (the "Buyer") enter into this Supply Agreement.
    This Agreement enters into force on 1 March 2023 (the "Effective Date") and remains in force until 1 March 2026, unless terminated earlier.
    The Supplier shall deliver the Goods within 28 days of the date of each Purchase Order.
    The unit price for the Goods is EUR 12,50 per unit, exclusive of VAT.
    Payment term: net 45 days from the invoice date.
    The Goods shall be delivered DAP Turku (Incoterms 2020).
    Late delivery shall give rise to a penalty of 0.5% of the order value per day, capped at 10 percent of the order value.
    Any price adjustment shall not exceed 3% per contract year.
    The maximum acceptable defect rate is 2% per delivery lot.
    The minimum annual purchase volume is 22 000 units.
    Liability of the Supplier is limited to EUR 500,000 in the aggregate.
    A notice period of sixty (60) days applies to any termination without cause.'''
    r = extract_rules(text)
    assert r["supplier_name"] == "Karhu Metals Oy"
    assert (r["effective_date"], r["expiry_date"]) == ("2023-03-01", "2026-03-01")
    assert (r["lead_time_days"], r["unit_price_eur"], r["payment_terms_days"], r["incoterm"]) == (28, 12.5, 45, "DAP")
    assert (r["late_penalty_pct_per_day"], r["penalty_cap_pct"], r["price_adjustment_cap_pct"]) == (0.5, 10.0, 3.0)
    assert (r["defect_threshold_pct"], r["min_annual_volume_units"], r["liability_cap_eur"]) == (2.0, 22000, 500000)
    assert r["termination_notice_days"] == 60


def test_rules_known_limits():
    r = extract_rules("The Supplier shall deliver the Goods within thirty (30) days of each order.")
    assert r["lead_time_days"] == 30  # digits in parentheses are read
    r = extract_rules("The Supplier shall deliver the Goods within thirty days of each order.")
    assert r["lead_time_days"] is None  # spelled-out numbers are not
    r = extract_rules("Goods shall be delivered within 3 weeks.")
    assert r["lead_time_days"] is None


def test_outcome_categories_and_scores():
    assert outcome("lead_time_days", 21, 21.0) == "correct"
    assert outcome("lead_time_days", 14, 21) == "wrong"
    assert outcome("lead_time_days", None, 21) == "missed"
    assert outcome("defect_threshold_pct", 2.0, None) == "hallucinated"
    assert outcome("defect_threshold_pct", None, None) == "absent_correct"
    assert outcome("incoterm", "dap", "DAP") == "correct"
    gold = {"C1": {"terms": {"lead_time_days": 21, "defect_threshold_pct": None}},
            "C2": {"terms": {"lead_time_days": 28, "defect_threshold_pct": 2.0}}}
    preds = {"C1": {"lead_time_days": 21, "defect_threshold_pct": 1.0}, "C2": {"lead_time_days": 14}}
    ft = field_table(long_outcomes(preds, gold))
    lt = ft.loc["lead_time_days"]
    assert (lt.correct, lt.wrong) == (1, 1) and lt.precision == 0.5 and lt.recall == 0.5
    d = ft.loc["defect_threshold_pct"]
    assert (d.hallucinated, d.missed) == (1, 1) and d.not_found_acc == 0.0


def test_llm_plumbing_with_fake_completer():
    fake = lambda prompt: "```json\n" + json.dumps({"terms": {"lead_time_days": "21", "incoterm": "DAP",
                                                          "unit_price_eur": 9.5, "bogus": 1},
                                                    "amendments": []}) + "\n```"
    out = extract_llm(["page one text"], fake)
    assert out["terms"]["lead_time_days"] == 21 and out["terms"]["incoterm"] == "DAP"
    assert out["terms"]["defect_threshold_pct"] is None and "bogus" not in out["terms"]
    assert "[[PAGE 1]]" in build_prompt(["page one text"])
    with pytest.raises(json.JSONDecodeError):
        parse_response("not json")
