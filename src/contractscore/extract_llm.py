"""LLM extractor: prompt + schema + strict parsing. Model access is injected as `complete(prompt) -> str`.

NOT YET RUN against a real model in this repo's results. Everything here except `anthropic_completer`
is covered by unit tests with a fake completer (plumbing only, not accuracy).
"""
from __future__ import annotations

import json
import os
import re

from .schema import DESCRIPTIONS, FIELDS, norm

SYSTEM = ("You extract commercial terms from supplier contracts. Answer with one JSON object and nothing else. "
          "Never guess: if a term is not stated in the contract, use null.")


def build_prompt(pages: list[str]) -> str:
    fields = "\n".join(f'- "{f}" ({t}): {DESCRIPTIONS[f]}' for f, t in FIELDS.items())
    doc = "\n".join(f"[[PAGE {i}]]\n{p}" for i, p in enumerate(pages, 1))
    return f"""{SYSTEM}

Extract these fields. Report the value currently in force: if an amendment changes a term, return the amended value
and also list the amendment. Convert weeks to days. Dates as ISO YYYY-MM-DD.
{fields}

Return JSON with this shape:
{{"terms": {{<field>: value or null, ...all fields...}},
  "evidence": {{<field>: {{"quote": "<short verbatim quote>", "page": <int>}}, ...}},
  "amendments": [{{"field": "<field>", "new": <value>, "effective_date": "YYYY-MM-DD"}}]}}

CONTRACT:
{doc}
"""


def parse_response(raw: str) -> dict:
    """Parse and validate. Unknown/invalid values become None; the raw model output is never trusted."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    data = json.loads(s)
    terms = {}
    for f, typ in FIELDS.items():
        v = (data.get("terms") or {}).get(f)
        v = norm(f, v) if typ != "str" else (None if v in (None, "") else " ".join(str(v).split()))
        if typ == "int" and v is not None:
            v = int(round(v))
        terms[f] = v
    return {"terms": terms, "evidence": data.get("evidence") or {}, "amendments": data.get("amendments") or []}


def extract_llm(pages: list[str], complete) -> dict:
    return parse_response(complete(build_prompt(pages)))


def anthropic_completer(model: str = "claude-sonnet-5-5", max_tokens: int = 2000):
    """Adapter for the Anthropic SDK (`pip install anthropic`, ANTHROPIC_API_KEY set). Untested here."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(prompt: str) -> str:
        r = client.messages.create(model=model, max_tokens=max_tokens, temperature=0,
                                   messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if b.type == "text")

    return complete
