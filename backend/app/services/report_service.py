"""CYBERPULSE AI — investigation report generation (PDF via reportlab).

Produces a professional, multi-section PDF report from database-backed
data: case summary, prediction, risk, explanation, linked entities,
timeline, interventions, and audit metadata.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Investigation
from ..services.investigation_service import build_timeline

DARK = colors.HexColor("#0B1220")
ACCENT = colors.HexColor("#22D3EE")
GRID = colors.HexColor("#1E293B")
TEXT = colors.HexColor("#E2E8F0")
MUTED = colors.HexColor("#94A3B8")


def _styles():
    base = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle("t", parent=base["Title"], textColor=TEXT, fontSize=20, spaceAfter=4)
    s["subtitle"] = ParagraphStyle("st", parent=base["Normal"], textColor=ACCENT, fontSize=11)
    s["h1"] = ParagraphStyle("h1", parent=base["Heading1"], textColor=TEXT, fontSize=13, spaceBefore=10, spaceAfter=4)
    s["body"] = ParagraphStyle("b", parent=base["Normal"], textColor=TEXT, fontSize=9.5, leading=14)
    s["small"] = ParagraphStyle("sm", parent=base["Normal"], textColor=MUTED, fontSize=8, leading=11)
    s["cell"] = ParagraphStyle("c", parent=base["Normal"], textColor=TEXT, fontSize=9, leading=12)
    return s


def _kv_table(pairs: list[tuple[str, str]], st: dict) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", st["cell"]), Paragraph(str(v), st["cell"])] for k, v in pairs]
    t = Table(data, colWidths=[45 * mm, 125 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _section_table(headers: list[str], rows: list[list[str]], st: dict, widths: list[float]) -> Table:
    data = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), st["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111C2E")),
        ("BACKGROUND", (0, 1), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def generate_investigation_pdf(inv: Investigation, prediction: dict | None,
                               factors: list[dict] | None,
                               graph: dict | None,
                               interventions: list,
                               audit_rows: list[dict]) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"CYBERPULSE AI — {inv.case_id}",
        author="CYBERPULSE AI",
    )
    doc.title = f"CYBERPULSE AI — {inv.case_id}"
    story = []

    # header
    story.append(Paragraph("CYBERPULSE AI", st["title"]))
    story.append(Paragraph("Investigation Report — Proactive Cybercrime Intelligence", st["subtitle"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "SYNTHETIC DATA — PROTOTYPE. AI-assisted decision support; not a determination of guilt.",
        st["small"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))

    # case summary
    story.append(Paragraph("1. Case Summary", st["h1"]))
    story.append(_kv_table([
        ("Case ID", inv.case_id),
        ("Title", inv.title),
        ("Status", inv.status.value),
        ("Priority", inv.priority),
        ("Assigned to", inv.assigned_to or "—"),
        ("Created by", inv.created_by or "—"),
        ("Created at", inv.created_at.isoformat() if inv.created_at else "—"),
        ("District", inv.district or "—"),
        ("Linked alert", inv.alert_id or "—"),
        ("Linked prediction", inv.prediction_id or "—"),
        ("Outcome", inv.outcome or "—"),
    ], st))
    if inv.summary:
        story.append(Spacer(1, 4))
        story.append(Paragraph(inv.summary, st["body"]))

    # prediction
    story.append(Paragraph("2. Prediction & Risk", st["h1"]))
    if prediction:
        story.append(_kv_table([
            ("Prediction ID", prediction.get("prediction_id", "—")),
            ("ATM", prediction.get("atm_id", "—")),
            ("Window", f'{prediction.get("window_start", "")} → {prediction.get("window_end", "")}'),
            ("Risk score", f'{prediction.get("risk_score", "—")}/100'),
            ("Probability", f'{float(prediction.get("probability", 0)):.3f}'),
            ("Confidence", f'{float(prediction.get("confidence", 0)):.2f}'),
            ("Model version", prediction.get("model_version", "—")),
            ("Recommended action", prediction.get("recommended_action", "—")),
        ], st))
    else:
        story.append(Paragraph("No linked prediction.", st["body"]))

    # explanation
    story.append(Paragraph("3. Explanation (WHY HERE? WHY NOW?)", st["h1"]))
    if factors:
        story.append(_section_table(
            ["#", "Factor", "Impact", "Direction"],
            [[i + 1, f.get("label", f.get("feature", "")), f"{f.get('impact', 0):+.4f}", f.get("direction", "")]
             for i, f in enumerate(factors)],
            st, [10 * mm, 100 * mm, 30 * mm, 30 * mm]))
    else:
        story.append(Paragraph("No factor data available.", st["body"]))

    # graph
    story.append(Paragraph("4. Linked Entities (Graph)", st["h1"]))
    if graph:
        story.append(_kv_table([
            ("Center", graph.get("center", "—")),
            ("Nodes (2-hop)", str(graph.get("n_nodes", 0))),
            ("Edges (2-hop)", str(graph.get("n_edges", 0))),
            ("Backend", graph.get("backend", "—")),
        ], st))
        story.append(Spacer(1, 3))
        story.append(_section_table(
            ["Entity", "Type", "Identifier", "Degree"],
            [[n.get("entity_id", ""), n.get("entity_type", ""), n.get("masked_identifier", ""), n.get("degree", "")]
             for n in graph.get("nodes", [])[:15]],
            st, [40 * mm, 35 * mm, 70 * mm, 25 * mm]))
    else:
        story.append(Paragraph("No graph data available.", st["body"]))

    # timeline
    story.append(Paragraph("5. Timeline", st["h1"]))
    tl = _timeline(inv)
    if tl:
        story.append(_section_table(
            ["Time (UTC)", "Event", "Detail"],
            [[e["occurred_at"] or "", e["title"], e.get("detail") or ""] for e in tl],
            st, [45 * mm, 45 * mm, 80 * mm]))
    else:
        story.append(Paragraph("No timeline events.", st["body"]))

    # interventions
    story.append(Paragraph("6. Interventions", st["h1"]))
    if interventions:
        story.append(_section_table(
            ["Type", "Description", "By", "Outcome"],
            [[i.action_type, i.description, i.performed_by, i.outcome or ""] for i in interventions],
            st, [35 * mm, 85 * mm, 30 * mm, 20 * mm]))
    else:
        story.append(Paragraph("No interventions recorded.", st["body"]))

    # audit
    story.append(Paragraph("7. Audit Metadata", st["h1"]))
    if audit_rows:
        story.append(_section_table(
            ["Time (UTC)", "User", "Action", "Resource", "Result"],
            [[a.get("timestamp", ""), a.get("username", ""), a.get("action", ""),
              a.get("resource") or "", a.get("result", "")] for a in audit_rows[:20]],
            st, [40 * mm, 35 * mm, 45 * mm, 40 * mm, 10 * mm]))
    else:
        story.append(Paragraph("No audit records.", st["body"]))

    # footer
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRID))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).isoformat()} by CYBERPULSE AI. "
        "Prototype validated using synthetic data. Architecture designed for integration "
        "with authorized data sources.",
        st["small"]))

    doc.build(story, onFirstPage=_dark_bg, onLaterPages=_dark_bg)
    return buf.getvalue()


def _timeline(inv: Investigation) -> list[dict]:
    events = sorted(inv.timeline, key=lambda e: e.occurred_at)
    return [
        {"event_type": e.event_type, "title": e.title, "detail": e.detail,
         "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None}
        for e in events
    ]


def _dark_bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.restoreState()