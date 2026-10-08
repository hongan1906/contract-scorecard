"""Experiments RQ2 and RQ3 on the synthetic data: generic vs contract-aware, and sensitivity to extraction errors."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .scoring import contract_scorecard, generic_scorecard

RELEVANT = {"slightly_late": "delivery", "chronic_late": "delivery", "erratic": "delivery",
            "ignores_amendment": "delivery", "price_creep": "price", "quality_drift": "quality"}


def auc_low_is_bad(problem: pd.Series, reliable: pd.Series) -> float:
    """P(a random problem supplier scores lower than a random reliable one); ties count half."""
    a, b = problem.dropna().to_numpy(), reliable.dropna().to_numpy()
    if not len(a) or not len(b):
        return np.nan
    lt = (a[:, None] < b[None, :]).mean()
    eq = (a[:, None] == b[None, :]).mean()
    return float(lt + 0.5 * eq)


def run_comparison(orders: pd.DataFrame, truth: pd.DataFrame, gold: dict, extracted: dict, cfg: dict):
    thr = cfg["scoring"]["flag_threshold"]
    orig = {c: g["terms_original"] for c, g in gold.items()}
    am = {c: g["amendments"] for c, g in gold.items()}
    generic = generic_scorecard(orders, cfg)
    oracle = contract_scorecard(orders, orig, am, cfg)
    ext = contract_scorecard(orders, extracted, {}, cfg)
    tr = truth.set_index("supplier_id")
    prof = tr["profile"]

    sc = pd.DataFrame({"profile": prof, "generic": generic.composite, "aware_gold_terms": oracle.composite,
                       "aware_extracted_terms": ext.composite, "penalty_eur_gold": oracle.penalty_exposure_eur})
    by_profile = sc.groupby("profile").agg(n=("generic", "size"), generic=("generic", "mean"),
                                           aware_gold_terms=("aware_gold_terms", "mean"),
                                           aware_extracted_terms=("aware_extracted_terms", "mean"),
                                           penalty_eur_gold=("penalty_eur_gold", "mean")).round(1)

    det = []
    for p in [x for x in prof.unique() if x != "reliable"]:
        ids = prof.index[prof == p]
        rel = prof.index[prof == "reliable"]
        comp = RELEVANT[p]
        row = {"profile": p, "n": len(ids), "relevant_component": comp}
        for name, card, col in [("generic", generic, None), ("aware_gold", oracle, None), ("aware_extracted", ext, None)]:
            row[f"{name}_flagged_composite"] = float((card.loc[ids, "composite"] < thr).mean())
            row[f"{name}_flagged_component"] = float((card.loc[ids, comp] < thr).mean())
            row[f"{name}_AUC_vs_reliable"] = auc_low_is_bad(card.loc[ids, "composite"], card.loc[rel, "composite"])
        det.append(row)
    rel = prof.index[prof == "reliable"]
    allp = prof.index[prof != "reliable"]
    summary = {"reliable_false_flag_rate_" + n: float((c.loc[rel, "composite"] < thr).mean())
               for n, c in [("generic", generic), ("aware_gold", oracle), ("aware_extracted", ext)]}
    summary.update({"AUC_all_problems_vs_reliable_" + n: auc_low_is_bad(c.loc[allp, "composite"], c.loc[rel, "composite"])
                    for n, c in [("generic", generic), ("aware_gold", oracle), ("aware_extracted", ext)]})
    sens = {
        "spearman_gold_vs_extracted": float(oracle.composite.corr(ext.composite, method="spearman")),
        "same_flag_decision_share": float(((oracle.composite < thr) == (ext.composite < thr)).mean()),
        "mean_abs_composite_diff": float((oracle.composite - ext.composite).abs().mean()),
        "suppliers_with_unscorable_component_extracted": int((ext.n_components < oracle.n_components).sum()),
        "spearman_generic_vs_aware_gold": float(generic.composite.corr(oracle.composite, method="spearman")),
    }
    return sc.round(2), by_profile, pd.DataFrame(det).round(3), pd.Series(summary).round(3), pd.Series(sens).round(3)
