"""Generate the full synthetic dataset: contract PDFs, gold labels, order history, hidden truth."""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

from .contracts import build_contract
from .document import build_blocks, render_pdf
from .history import generate_history


def generate(out: str | Path, cfg: dict, seed: int | None = None, n_scale: float | None = None) -> dict:
    out = Path(out)
    for sub in ("contracts", "gold"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    seed = cfg["run"]["seed"] if seed is None else seed
    scale = cfg["run"]["n_suppliers_scale"] if n_scale is None else n_scale
    rng, nrng = random.Random(seed), np.random.default_rng(seed)

    plan = []
    for name, p in cfg["profiles"].items():
        plan += [(name, p)] * max(1, round(p["count"] * scale))
    rng.shuffle(plan)

    used: set = set()
    truth, orders = [], []
    for i, (pname, pcfg) in enumerate(plan, 1):
        sid = f"S{i:03d}"
        ct = build_contract(i, sid, pcfg, cfg, rng, used)
        blocks = build_blocks(ct, cfg["run"]["buyer_name"], rng)
        render_pdf(blocks, out / "contracts" / f"{ct.contract_id}.pdf", ct.contract_id)
        gold = {"contract_id": ct.contract_id, "file": f"contracts/{ct.contract_id}.pdf",
                "terms": ct.current_terms(), "terms_original": ct.terms,
                "amendments": ct.amendments, "flags": ct.flags}
        (out / "gold" / f"{ct.contract_id}.json").write_text(json.dumps(gold, indent=2))
        applies_cap = nrng.random() < pcfg["applies_cap_increase_prob"]
        h = generate_history(ct, pcfg, applies_cap, cfg, nrng)
        orders.append(h)
        truth.append({"supplier_id": sid, "supplier_name": ct.supplier_name, "contract_id": ct.contract_id,
                      "profile": pname, "applies_cap_increase": applies_cap,
                      "has_lead_amendment": ct.flags["amend_lead"], "n_orders": len(h)})
    df = pd.concat(orders, ignore_index=True)
    df.to_csv(out / "orders.csv", index=False)
    pd.DataFrame(truth).to_csv(out / "suppliers_truth.csv", index=False)
    return {"suppliers": len(plan), "orders": len(df)}
