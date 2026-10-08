"""Repeat generate -> extract (rules) -> score over several seeds to see how stable the headline numbers are."""
import sys
import tempfile
from pathlib import Path

import pandas as pd

from contractscore.compare import run_comparison
from contractscore.config import load_config
from contractscore.evaluate import field_table, load_gold, long_outcomes
from contractscore.extract_rules import extract_rules
from contractscore.generate import generate
from contractscore.pdftext import pdf_text

cfg = load_config()
seeds = [int(s) for s in sys.argv[1:]] or [1, 2, 3, 4, 5]
rows = []
for sd in seeds:
    d = Path(tempfile.mkdtemp())
    generate(d, cfg, seed=sd)
    gold = load_gold(d / "gold")
    ex = {c: extract_rules(pdf_text(d / "contracts" / f"{c}.pdf")) for c in gold}
    micro = field_table(long_outcomes(ex, gold)).loc["ALL (micro)"]
    _, _, det, summ, sens = run_comparison(pd.read_csv(d / "orders.csv"), pd.read_csv(d / "suppliers_truth.csv"), gold, ex, cfg)
    rows.append({"seed": sd, "extraction_F1_micro": micro.F1,
                 "AUC_generic": summ["AUC_all_problems_vs_reliable_generic"],
                 "AUC_aware_gold": summ["AUC_all_problems_vs_reliable_aware_gold"],
                 "AUC_aware_extracted": summ["AUC_all_problems_vs_reliable_aware_extracted"],
                 "false_flag_generic": summ["reliable_false_flag_rate_generic"],
                 "false_flag_aware_gold": summ["reliable_false_flag_rate_aware_gold"],
                 "false_flag_aware_extracted": summ["reliable_false_flag_rate_aware_extracted"],
                 "ignores_amend_flagged_generic": det.set_index("profile").loc["ignores_amendment", "generic_flagged_composite"],
                 "ignores_amend_flagged_aware_gold": det.set_index("profile").loc["ignores_amendment", "aware_gold_flagged_composite"]})
df = pd.DataFrame(rows).round(3)
print(df.to_string(index=False))
print("\nmean:\n", df.drop(columns="seed").mean().round(3).to_string())
df.to_csv("reports/seed_sweep.csv", index=False)
