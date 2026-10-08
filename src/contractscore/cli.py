from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .compare import run_comparison
from .config import load_config
from .evaluate import error_analysis, field_table, load_gold, long_outcomes
from .extract_rules import extract_rules
from .generate import generate
from .pdftext import pdf_pages, pdf_text

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


def _extract(data: Path, method: str, model: str) -> dict:
    gold = load_gold(data / "gold")
    out = {}
    if method == "rules":
        for c in gold:
            out[c] = extract_rules(pdf_text(data / "contracts" / f"{c}.pdf"))
    else:
        from .extract_llm import anthropic_completer, extract_llm
        complete = anthropic_completer(model)
        for c in gold:
            out[c] = extract_llm(pdf_pages(data / "contracts" / f"{c}.pdf"), complete)["terms"]
    d = data / "extracted"
    d.mkdir(exist_ok=True)
    (d / f"{method}.json").write_text(json.dumps(out, indent=1))
    return out


def _load_extracted(data: Path, method: str) -> dict:
    p = data / "extracted" / f"{method}.json"
    return json.loads(p.read_text()) if p.exists() else _extract(data, method, "claude-sonnet-5-5")


def main(argv=None):
    p = argparse.ArgumentParser(prog="contractscore")
    p.add_argument("command", choices=["generate", "extract", "evaluate", "score", "all"])
    p.add_argument("--data", default="data")
    p.add_argument("--reports", default="reports")
    p.add_argument("--config", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--scale", type=float, default=None, help="multiply supplier counts (0.2 = quick run)")
    p.add_argument("--method", choices=["rules", "llm"], default="rules")
    p.add_argument("--model", default="claude-sonnet-5-5")
    a = p.parse_args(argv)
    cfg, data, rep = load_config(a.config), Path(a.data), Path(a.reports)
    rep.mkdir(exist_ok=True)

    if a.command in ("generate", "all"):
        print("generate:", generate(data, cfg, a.seed, a.scale))
    if a.command in ("extract", "all"):
        _extract(data, a.method, a.model)
        print(f"extract: wrote {data}/extracted/{a.method}.json")
    gold = load_gold(data / "gold") if a.command in ("evaluate", "score", "all") else None
    if a.command in ("evaluate", "all"):
        ex = _load_extracted(data, a.method)
        long = long_outcomes(ex, gold)
        ft, ea = field_table(long), error_analysis(long, gold)
        ft.to_csv(rep / f"extraction_{a.method}_fields.csv")
        ea.to_csv(rep / f"extraction_{a.method}_hard_cases.csv", index=False)
        print(f"\n=== RQ1: field-level extraction ({a.method}) ===\n{ft}\n\n=== accuracy on hard cases ===\n{ea}")
    if a.command in ("score", "all"):
        ex = _load_extracted(data, a.method)
        orders = pd.read_csv(data / "orders.csv")
        truth = pd.read_csv(data / "suppliers_truth.csv")
        sc, byp, det, summ, sens = run_comparison(orders, truth, gold, ex, cfg)
        sc.to_csv(rep / "supplier_scores.csv")
        byp.to_csv(rep / "scores_by_profile.csv")
        det.to_csv(rep / "detection_by_profile.csv", index=False)
        summ.to_csv(rep / "detection_summary.csv", header=["value"])
        sens.to_csv(rep / f"sensitivity_{a.method}.csv", header=["value"])
        print(f"\n=== RQ2: mean composite score by planted profile ===\n{byp}")
        print(f"\n=== RQ2: detection (flag threshold {cfg['scoring']['flag_threshold']}) ===\n{det.T}")
        print(f"\n{summ}\n\n=== RQ3: sensitivity to extraction errors ({a.method}) ===\n{sens}")
