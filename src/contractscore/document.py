"""Turn a Contract into an ordered list of document blocks, then into a PDF."""
from __future__ import annotations

import random
from datetime import date
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import clauses as C
from .contracts import Contract
from .dates import fmt_date

rl_config.invariant = 1  # byte-identical PDFs for the same input


def _heading(i: int, title: str, numbering: str) -> str:
    return {"decimal": f"{i}. {title}", "article": f"Article {i} - {title}",
            "section": f"Section {i}. {title}"}[numbering]


def build_blocks(ct: Contract, buyer: str, rng: random.Random) -> list[tuple]:
    st, t = ct.style, ct.terms
    blocks: list[tuple] = [("title", rng.choice(["SUPPLY AGREEMENT", "MASTER SUPPLY AGREEMENT"])),
                           ("center", f"Contract No. {ct.contract_id}"),
                           ("para", C.preamble(buyer, ct.supplier_name, rng))]
    eff, exp = date.fromisoformat(t["effective_date"]), date.fromisoformat(t["expiry_date"])
    sections: list[tuple[str, list[str]]] = [("Term", [C.term_clause(eff, exp, ct.term_years, st, rng)])]
    groups = [g for g, req in C.REQUIRES.items() if all(t.get(f) is not None for f in req)]
    body = [(g, C.RENDER[g](t, st, rng)) for g in groups]
    if st.distractor:
        body.append(("samples", C.r_samples(rng.choice([5, 7, 10]), st, rng)))
    rng.shuffle(body)
    sections += [(rng.choice(C.HEADINGS[g]), paras) for g, paras in body]
    extras = rng.sample(C.BOILERPLATE, rng.randint(2, 4))
    sections += [(h, [txt]) for h, txt in extras]
    for i, (h, paras) in enumerate(sections, 1):
        blocks.append(("heading", _heading(i, h, st.numbering)))
        blocks += [("para", p) for p in paras]
    for n, a in enumerate(ct.amendments, 1):
        blocks.append(("heading", f"AMENDMENT NO. {n}"))
        blocks.append(("para", C.amendment_clause(a, st, rng)))
    if st.annex_price:
        blocks.append(("heading", "ANNEX A - PRICE SCHEDULE"))
        blocks.append(("table", [["Item", "Description", "Unit price (EUR)"],
                                 ["G-100", "Standard goods, per unit",
                                  (f"{t['unit_price_eur']:.2f}".replace(".", ",") if st.price_comma else f"{t['unit_price_eur']:.2f}")]]))
    blocks.append(("sign", [["For the Buyer", "For the Supplier"], ["______________________", "______________________"],
                            ["Name:", "Name:"], [f"Date: {fmt_date(eff, st.date_style)}", f"Date: {fmt_date(eff, st.date_style)}"]]))
    return blocks


def render_pdf(blocks: list[tuple], path, contract_id: str) -> None:
    ss = getSampleStyleSheet()
    sty = {"title": ParagraphStyle("t", parent=ss["Title"], fontSize=16, spaceAfter=6),
           "center": ParagraphStyle("c", parent=ss["Normal"], alignment=1, spaceAfter=12),
           "heading": ParagraphStyle("h", parent=ss["Heading3"], spaceBefore=10, spaceAfter=3),
           "para": ParagraphStyle("p", parent=ss["Normal"], leading=14, spaceAfter=4)}

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(20 * mm, 12 * mm, f"{contract_id}")
        canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")

    flow = []
    for kind, content in blocks:
        if kind in sty:
            flow.append(Paragraph(escape(content), sty[kind]))
        elif kind == "table":
            tb = Table(content, colWidths=[30 * mm, 90 * mm, 40 * mm])
            tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                                    ("FONTSIZE", (0, 0), (-1, -1), 9)]))
            flow += [Spacer(1, 4), tb]
        elif kind == "sign":
            flow += [Spacer(1, 24), Table(content, colWidths=[80 * mm, 80 * mm])]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=20 * mm, bottomMargin=20 * mm, title=contract_id).build(
        flow, onFirstPage=footer, onLaterPages=footer)
