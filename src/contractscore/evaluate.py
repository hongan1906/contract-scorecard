"""Field-level extraction evaluation against the gold labels."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import FIELDS, norm


def load_gold(gold_dir: str | Path) -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted(Path(gold_dir).glob("*.json"))}


def outcome(field: str, pred, gold) -> str:
    p, g = norm(field, pred), norm(field, gold)
    if g is None:
        return "absent_correct" if p is None else "hallucinated"
    if p is None:
        return "missed"
    return "correct" if p == g else "wrong"


def long_outcomes(preds: dict, gold: dict) -> pd.DataFrame:
    rows = []
    for cid, g in gold.items():
        pt = (preds.get(cid) or {})
        for f in FIELDS:
            rows.append({"contract_id": cid, "field": f, "gold": g["terms"].get(f), "pred": pt.get(f),
                         "outcome": outcome(f, pt.get(f), g["terms"].get(f))})
    return pd.DataFrame(rows)


def _prf(c, w, m, h):
    prec = c / (c + w + h) if (c + w + h) else np.nan
    rec = c / (c + w + m) if (c + w + m) else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec == prec and rec == rec and (prec + rec) else np.nan
    return prec, rec, f1


def field_table(long: pd.DataFrame) -> pd.DataFrame:
    cnt = long.pivot_table(index="field", columns="outcome", values="contract_id", aggfunc="count", fill_value=0)
    for o in ["correct", "wrong", "missed", "hallucinated", "absent_correct"]:
        if o not in cnt:
            cnt[o] = 0
    cnt = cnt.reindex(list(FIELDS))
    micro = cnt.sum().to_frame("ALL (micro)").T
    t = pd.concat([cnt, micro])
    t[["precision", "recall", "F1"]] = [_prf(r.correct, r.wrong, r.missed, r.hallucinated) for r in t.itertuples()]
    t["not_found_acc"] = t.absent_correct / (t.absent_correct + t.hallucinated).replace(0, np.nan)
    return t[["correct", "wrong", "missed", "hallucinated", "absent_correct", "precision", "recall", "F1", "not_found_acc"]].round(3)


def error_analysis(long: pd.DataFrame, gold: dict) -> pd.DataFrame:
    """For each hard-case flag: accuracy on fields whose gold exists, with vs without the flag."""
    present = long[long.gold.notna()].copy()
    present["ok"] = present.outcome == "correct"
    flags = ["words_only", "lead_in_weeks", "annex_price", "distractor", "expiry_term_only", "amend_lead", "amend_payment"]
    for fl in flags:
        present[fl] = present.contract_id.map(lambda c: bool(gold[c]["flags"].get(fl)))
    rel = {"words_only": ["lead_time_days", "payment_terms_days", "termination_notice_days"],
           "lead_in_weeks": ["lead_time_days"], "annex_price": ["unit_price_eur"],
           "distractor": ["lead_time_days"], "expiry_term_only": ["expiry_date"],
           "amend_lead": ["lead_time_days"], "amend_payment": ["payment_terms_days"]}
    rows = []
    for fl, fields in rel.items():
        for f in fields:
            sub = present[present.field == f]
            w, wo = sub[sub[fl]], sub[~sub[fl]]
            if len(w):
                rows.append({"hard_case": fl, "field": f, "n_with": len(w), "acc_with": w.ok.mean(),
                             "n_without": len(wo), "acc_without": wo.ok.mean() if len(wo) else np.nan})
    return pd.DataFrame(rows).round(3)
