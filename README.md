# contractscore: contract-aware supplier scorecards from PDF contracts

Thesis prototype. Idea: an LLM reads supplier contract PDFs and extracts the commercial terms
(lead time, price and price cap, payment, penalties, defect limit, ...). Those terms are joined to
order and delivery history, and each supplier is rated **against what it actually committed to**.

This repository contains the parts that do not need real company data:

1. a **generator** for synthetic contract PDFs, exact gold labels and supplier order history,
2. a **rule-based baseline extractor** and a **field-level evaluator** (RQ1),
3. a **generic vs contract-aware scorecard** comparison (RQ2) and a **sensitivity** check (RQ3),
4. an **LLM extractor interface** (prompt, schema, strict parser). **It has not been run against a model yet.**

## Research questions

| | Question | Where |
|---|---|---|
| RQ1 | How accurately can terms be extracted from contract PDFs, and where does extraction fail? | `evaluate.py`, `extract_rules.py`, `extract_llm.py` |
| RQ2 | Does a contract-aware score reveal problems a generic scorecard misses (and avoid false alarms)? | `scoring.py`, `compare.py` |
| RQ3 | How sensitive is the rating to extraction errors? | `compare.py` (`sensitivity_*.csv`) |

## Quick start

```bash
pip install -e ".[dev]"          # add ".[llm]" for the Anthropic SDK
python -m contractscore all      # generate data, extract (rules), evaluate, score -> data/, reports/
pytest -q                        # 14 tests
python scripts/seed_sweep.py 1 2 3 4 5   # stability over seeds
```

Commands: `generate`, `extract`, `evaluate`, `score`, `all`. Options: `--scale 0.25` (small run),
`--seed`, `--config my.toml` (copy `src/contractscore/default_config.toml`), `--method llm --model ...`
(needs `ANTHROPIC_API_KEY`; untested).

## What is generated

`python -m contractscore generate` writes to `data/` (git-ignored; deterministic for a seed):

- `contracts/C001.pdf ...` 40 supplier agreements, 1-2 pages. Samples are in `examples/`.
- `gold/C001.json` the true terms (current and original), amendments, and which hard cases are present.
- `orders.csv` about 4,700 orders: order/delivery/invoice/paid dates, quantity, defects, invoice price,
  plus the ERP due date and ERP standard price a buyer system would hold.
- `suppliers_truth.csv` the hidden behaviour profile of each supplier (never shown to extractor or scorer).

**Contracts** are built from a clause library with 2-3 wordings per clause, shuffled clause order, three heading
styles, three date formats, three number formats. Hard cases, each with a configurable probability:
numbers spelled out without digits, lead time in weeks, price only in an annex table, expiry given as a term in
years, an amendment that changes lead time or payment terms, a distractor sentence ("samples shall be delivered
within 5 days"), and missing clauses (penalty, defect limit, price cap, volume, liability).

**Supplier behaviour** (`[profiles.*]` in the config; these are design parameters, not findings):
`reliable`, `slightly_late`, `chronic_late`, `erratic` (late and early orders cancel, so the *average* lead time
looks fine), `price_creep` (7 %/yr regardless of the contract), `quality_drift`, and `ignores_amendment`
(keeps delivering on the old lead time after an amendment shortens it). 40 suppliers: 14 reliable, 26 with a planted problem.

## Scorecards

Both are deterministic formulas, 0-100, weights 0.5 delivery / 0.3 quality / 0.2 price. The LLM never produces a score.

- **Generic**: on-time vs the ERP due date; share of lots under one company-wide 2 % defect limit; price vs ERP standard price.
- **Contract-aware**: on-time vs the lead time **in force on the order date** (amendments applied); defect rate vs the
  supplier's own threshold; invoice price vs the price allowed by its own cap. A term the contract does not
  define makes that component n/a and the weights are renormalised. Late-penalty exposure in EUR is reported separately.

A supplier is "flagged" if its composite is below 90. That threshold was fixed before looking at results; AUC is also
reported because it needs no threshold.

## Results (seed 7, `python -m contractscore all`)

### RQ1: extraction with the rule-based baseline

Micro-averaged over 14 fields x 40 contracts: precision 0.91, recall 0.82, **F1 0.86**.

| field | correct | wrong | missed | halluc. | F1 |
|---|---|---|---|---|---|
| supplier, effective date, incoterm | 40/40 | 0 | 0 | 0 | 1.00 |
| penalty, penalty cap, defect limit, volume, liability | all present ones | 0 | 0 | 0 | 1.00 |
| termination notice | 31 | 0 | 9 | 0 | 0.87 |
| payment terms | 27 | 4 | 9 | 0 | 0.76 |
| expiry date | 25 | 0 | 15 | 0 | 0.77 |
| price cap | 21 | 6 | 0 | 8 | 0.68 |
| unit price | 15 | 8 | 17 | 0 | 0.48 |
| **lead time** | 12 | 17 | 11 | 0 | **0.35** |

Accuracy on the hard cases (from `reports/extraction_rules_hard_cases.csv`):

| hard case | field | accuracy with | without |
|---|---|---|---|
| spelled-out numbers | lead time | 0 % (n=9) | 39 % |
| lead time in weeks | lead time | 0 % (n=10) | 40 % |
| amendment | lead time | 0 % (n=8) | 38 % |
| distractor sentence | lead time | 8 % (n=13) | 41 % |
| price only in annex | unit price | 0 % (n=21) | 79 % |
| expiry as years only | expiry date | 0 % (n=15) | 100 % |

The baseline is perfect on the clauses that have one regular wording and fails completely on exactly the hard cases.
**Lead time, the field that matters most for the scorecard, is where it is worst.** This is the gap an LLM is expected to close.
The LLM has not been tested here, so no claim is made about how well it does.

### RQ2: generic vs contract-aware scorecard (with the *true* terms)

Mean composite score by planted profile, and share of suppliers flagged (composite < 90):

| profile | n | generic score | aware score | generic flagged | aware flagged |
|---|---|---|---|---|---|
| reliable | 14 | 96.3 | 97.3 | 7 % (false alarm) | 0 % |
| slightly_late | 6 | 85.9 | 81.6 | 100 % | 100 % |
| chronic_late | 4 | 67.3 | 63.3 | 100 % | 100 % |
| erratic | 5 | 82.1 | 81.3 | 100 % | 100 % |
| price_creep | 4 | 81.1 | 81.2 | 100 % | 75 % |
| quality_drift | 4 | 85.0 | 83.7 | 100 % | 50 % |
| **ignores_amendment** | 3 | 97.9 | 56.8 | **0 %** | **100 %** |

AUC (problem supplier scores lower than a reliable one): generic 0.92, contract-aware 0.97.

Reading it honestly:
- **The one clear win is `ignores_amendment`.** The ERP still holds the old lead time, so the generic scorecard
  sees on-time deliveries (AUC for this group 0.32, i.e. *worse* than random, they look better than reliable
  suppliers) while the contract-aware score sees breaches of the amended term (about EUR 58k penalty exposure per supplier).
- The contract-aware score also avoids the false alarm on a reliable supplier that makes a price increase
  its contract permits, which the generic price-variance metric penalises.
- **The contract-aware score is *worse* at `price_creep` and `quality_drift`.** When the contract has no price cap or
  no defect limit, that component is n/a and the problem is invisible to it, while the generic scorecard still catches it.
  A real system should fall back to generic metrics when a term is missing.
- Delivery-related problems (late, chronic, erratic) are caught equally well by both.

### RQ3: sensitivity to extraction errors (rule baseline terms fed to the scorer)

| | value |
|---|---|
| AUC, aware with extracted terms | 0.57 (vs 0.97 with true terms) |
| reliable suppliers falsely flagged | 36 % (vs 0 %) |
| Spearman, composite from true vs extracted terms | 0.04 |
| suppliers with a component lost to a missed term | 18 of 40 |

Extraction errors on lead time propagate straight into the rating, and the damage is large:
**with the baseline's terms the contract-aware scorecard is worse than the generic one.** Extraction quality on
a few critical fields (lead time, price, price cap, amendments) decides whether the approach is worth using at all.

### Stability across seeds

Five other seeds (`reports/seed_sweep.csv`): extraction F1 0.88-0.90; AUC generic 0.89-0.94 (mean 0.92),
contract-aware 0.95-1.00 (mean 0.97), contract-aware with baseline-extracted terms 0.57-0.84 (mean 0.69);
`ignores_amendment` flagged 0 % by generic and 100 % by contract-aware in every seed. The ordering holds in all seeds.
Each profile has only 3-6 suppliers per run, so per-profile percentages move in steps of 17-33 points.

## Limitations

- **Everything here is synthetic.** The results show the method works when the world behaves the way the generator says,
  not how real contracts or suppliers behave. Real contracts are messier (scans, tables, mixed languages, cross-references).
- **The comparison is partly built in.** The stale-ERP assumption (`erp_stale`), legitimate price increases within
  the cap, and the `ignores_amendment` profile are scenarios I chose, and they are the ones that favour the
  contract-aware scorecard. The generic scorecard is my construction and could be made smarter (e.g. keep ERP lead times current).
  The result shows the mechanism, not the size of the advantage in practice.
- **The baseline and the generator share an author.** The regex baseline was written and adjusted while looking at
  seed-7 contracts; the wording of the clause library is the wording it is tuned for. Seeds 1-5 use the same
  rules and give the same picture, but wording outside the library would hurt it more.
- **No scanned PDFs / OCR noise.** The PDFs have a clean text layer.
- **The LLM extractor is unrun.** `extract_llm.py` is tested only for prompt building and parsing, with a fake model.
  Amendment extraction from the LLM output is returned but not yet scored, and extracted terms are scored without amendments.
- Hyper-parameters (weights, threshold, 2 % company limit, price-variance scale) are fixed design choices, not tuned.
- Volume commitments and payment terms are extracted but not scored; they are buyer obligations, not supplier performance.

## Next steps

1. Run `--method llm` and report RQ1 and RQ3 for it next to the baseline (also try a few prompt variants and long-document handling).
2. Score extracted amendments and let the scorer use them.
3. Add scan/OCR noise and a handful of real public contracts (CUAD, EDGAR) as a reality check.
4. Make the generic scorecard stronger and add a fallback to generic metrics for missing terms.
5. Try real data from a company if you can get it.

## Layout

```
src/contractscore/  config(.toml) dates schema clauses contracts document history generate
                    pdftext extract_rules extract_llm evaluate timeline scoring compare cli
tests/              dates, generation consistency + determinism, extraction, scoring (hand-computed cases)
scripts/            seed_sweep.py
reports/            CSV tables written by the commands above
examples/           three sample contract PDFs with their gold labels
```
