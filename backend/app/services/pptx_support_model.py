"""Support model PPT export (spec 10.6.2, real python-pptx, not mocked).

16:9, five slides: (1) title, (2) landscape (central app circle, radial rounded rectangles,
arrowed connectors per ``relation``, right-hand vendor text box), (3) support flow L1 -> L2 -> L3,
(4) contacts & SLA table, (5) open questions & sources. Footer "Confidential" on every slide.
Neutral template: dark-teal header bar, white background. Colours and fonts come ONLY from
``theme()`` so the client's real template can be swapped in later.
"""

from __future__ import annotations

import io
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

TEMPLATE_NAME = "PTIV ORB (placeholder)"

SLIDE_W = 13.333
SLIDE_H = 7.5
HEADER_H = 0.9
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def theme() -> dict[str, Any]:
    """Single source for colours and fonts."""
    return {
        "header_bg": "0F4C5C",
        "header_fg": "FFFFFF",
        "accent": "1B998B",
        "text": "1F2933",
        "muted": "6B7780",
        "central_fill": "0F4C5C",
        "central_fg": "FFFFFF",
        "node_fill": "E6F2F1",
        "node_line": "1B998B",
        "line": "4A5A63",
        "background": "FFFFFF",
        "font_title": "Calibri",
        "font_body": "Calibri",
        "footer": "Confidential",
    }


# ------------------------------------------------------------------ helpers


def _clean(value: Any) -> str:
    return _CONTROL.sub("", "" if value is None else str(value))


def _short(value: Any, limit: int) -> str:
    text = " ".join(_clean(value).split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def _style_run(run: Any, *, size: float, color: str, bold: bool = False, font: str | None = None):
    t = theme()
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font or t["font_body"]
    run.font.color.rgb = _rgb(color)


def _textbox(
    slide: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    paragraphs: Sequence[tuple[str, float, str, bool]],
    *,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    name: str | None = None,
) -> Any:
    """Text box with (text, size, colour, bold) paragraphs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    frame = box.text_frame
    frame.word_wrap = True
    for i, (text, size, color, bold) in enumerate(paragraphs):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = _clean(text)
        _style_run(run, size=size, color=color, bold=bold)
    return box


def _shape_text(shape: Any, lines: Sequence[tuple[str, float, str, bool]]) -> None:
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = frame.margin_right = Inches(0.06)
    frame.margin_top = frame.margin_bottom = Inches(0.03)
    for i, (text, size, color, bold) in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        para.alignment = PP_ALIGN.CENTER
        run = para.add_run()
        run.text = _clean(text)
        _style_run(run, size=size, color=color, bold=bold)


def _base_slide(prs: Any, title: str, slide_no: int) -> Any:
    t = theme()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(t["background"])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(HEADER_H))
    bar.name = "Header bar"
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(t["header_bg"])
    bar.line.fill.background()
    _textbox(
        slide,
        0.5,
        0.15,
        12.3,
        0.6,
        [(_short(title, 90), 28, t["header_fg"], True)],
        name="Title",
    )
    _textbox(
        slide,
        0.5,
        SLIDE_H - 0.45,
        6.0,
        0.35,
        [(t["footer"], 11, t["muted"], False)],
        name="Footer",
    )
    _textbox(
        slide,
        7.3,
        SLIDE_H - 0.45,
        5.55,
        0.35,
        [(f"{TEMPLATE_NAME}  |  {slide_no}", 10, t["muted"], False)],
        align=PP_ALIGN.RIGHT,
        name="Template",
    )
    return slide


def _add_arrow_ends(connector: Any, *, head: bool, tail: bool) -> None:
    """Arrowheads via the line XML: ``a:headEnd`` at the begin point, ``a:tailEnd`` at the end."""
    ln = connector.line._get_or_add_ln()
    for tag in ("a:headEnd", "a:tailEnd"):
        for old in ln.findall(qn(tag)):
            ln.remove(old)
    if head:
        etree.SubElement(ln, qn("a:headEnd"), type="triangle", w="med", len="med")
    if tail:
        etree.SubElement(ln, qn("a:tailEnd"), type="triangle", w="med", len="med")


def _edge_point(
    centre: tuple[float, float],
    half: tuple[float, float],
    toward: tuple[float, float],
    ellipse: bool,
) -> tuple[float, float]:
    """Point where the ray from ``centre`` to ``toward`` leaves the shape outline."""
    dx, dy = toward[0] - centre[0], toward[1] - centre[1]
    if dx == 0 and dy == 0:
        return centre
    hw, hh = half
    if ellipse:
        scale = 1.0 / math.sqrt((dx / hw) ** 2 + (dy / hh) ** 2)
    else:
        scale = min(
            hw / abs(dx) if dx else math.inf,
            hh / abs(dy) if dy else math.inf,
        )
    return centre[0] + dx * scale, centre[1] + dy * scale


def _connect(
    slide: Any,
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    *,
    head: bool,
    tail: bool,
    dashed: bool = False,
) -> None:
    """Connector from node ``a`` to node ``b`` (dicts with cx, cy, hw, hh, ellipse)."""
    t = theme()
    start = _edge_point((a["cx"], a["cy"]), (a["hw"], a["hh"]), (b["cx"], b["cy"]), a["ellipse"])
    end = _edge_point((b["cx"], b["cy"]), (b["hw"], b["hh"]), (a["cx"], a["cy"]), b["ellipse"])
    conn = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(start[0]), Inches(start[1]), Inches(end[0]), Inches(end[1])
    )
    conn.line.color.rgb = _rgb(t["line"])
    conn.line.width = Pt(1.5)
    if dashed:
        conn.line.dash_style = MSO_LINE.DASH
    _add_arrow_ends(conn, head=head, tail=tail)


# ------------------------------------------------------------------ slides


def _slide_title(prs: Any, landscape: Mapping[str, Any], meta: Mapping[str, Any]) -> None:
    t = theme()
    app = _clean(landscape.get("central_app", ""))
    slide = _base_slide(prs, f"Support model - {app}", 1)
    reviewed_by = _clean(meta.get("reviewed_by") or "the reviewer")
    lines = [
        (f"Transition: {_clean(meta.get('transition_name', ''))}", 24, t["text"], True),
        (f"Portfolio: {_clean(meta.get('portfolio', ''))}", 18, t["text"], False),
        (f"Version: {meta.get('version', 1)}", 18, t["text"], False),
        (f"Date: {_clean(meta.get('date', ''))}", 18, t["text"], False),
    ]
    if meta.get("status"):
        lines.append((f"Status: {_clean(meta['status'])}", 18, t["text"], False))
    lines.append((f"Draft - generated by Orion, reviewed by {reviewed_by}", 16, t["accent"], True))
    _textbox(slide, 0.8, 1.7, 11.5, 4.5, lines, name="Details")


def _free_spot(
    nodes: Mapping[str, Mapping[str, Any]],
    parent: Mapping[str, Any],
    unit: tuple[float, float],
    perp: tuple[float, float],
    spread: float,
    area: tuple[float, float, float, float],
    centre: tuple[float, float],
) -> tuple[float, float]:
    """First position near the parent that stays inside the area and overlaps no placed node or
    the central circle; falls back to the plain offset when nothing is free."""
    node_w, node_h = 1.65, 0.62
    want_x = parent["cx"] + unit[0] * 1.15 + perp[0] * spread
    want_y = parent["cy"] + unit[1] * 0.95 + perp[1] * spread * 0.9
    want_x = min(max(want_x, area[0] + node_w / 2), area[2] - node_w / 2)
    want_y = min(max(want_y, area[1] + node_h / 2), area[3] - node_h / 2)

    def clear(x: float, y: float) -> bool:
        if math.hypot(x - centre[0], y - centre[1]) < 1.05 + node_h:
            return False
        return all(
            abs(x - n["cx"]) >= node_w + 0.08 or abs(y - n["cy"]) >= node_h + 0.08
            for n in nodes.values()
        )

    if clear(want_x, want_y):
        return want_x, want_y
    # Otherwise the free grid position (0.2 inch steps inside the area) closest to the wish.
    xs = [
        area[0] + node_w / 2 + 0.2 * i for i in range(int((area[2] - area[0] - node_w) / 0.2) + 1)
    ]
    ys = [
        area[1] + node_h / 2 + 0.2 * i for i in range(int((area[3] - area[1] - node_h) / 0.2) + 1)
    ]
    spots = sorted(
        ((x, y) for x in xs for y in ys),
        key=lambda xy: (xy[0] - want_x) ** 2 + (xy[1] - want_y) ** 2,
    )
    return next((xy for xy in spots if clear(*xy)), (want_x, want_y))


def _radial_layout(
    components: list[Mapping[str, Any]], cx: float, cy: float
) -> dict[str, dict[str, Any]]:
    """Node geometry per component name (first wins). Children sit next to their parent."""
    node_w, node_h = 1.65, 0.62
    area = (0.35, HEADER_H + 0.2, 9.0, SLIDE_H - 0.7)
    names = {_clean(c.get("name")) for c in components}
    ring = [
        c
        for c in components
        if not str(c.get("relation", "")).startswith("child_of:")
        or str(c["relation"]).split(":", 1)[1] not in names
    ]
    nodes: dict[str, dict[str, Any]] = {}
    rx, ry = 3.0, 2.15
    for i, comp in enumerate(ring):
        angle = -math.pi / 2 + 2 * math.pi * i / max(len(ring), 1)
        nodes.setdefault(
            _clean(comp.get("name")),
            {
                "comp": comp,
                "cx": cx + rx * math.cos(angle),
                "cy": cy + ry * math.sin(angle),
                "angle": angle,
                "hw": node_w / 2,
                "hh": node_h / 2,
                "ellipse": False,
            },
        )
    ring_ids = {id(n["comp"]) for n in nodes.values()}
    children: dict[str, list[Mapping[str, Any]]] = {}
    for comp in components:
        rel = str(comp.get("relation", ""))
        if id(comp) not in ring_ids and rel.startswith("child_of:"):
            children.setdefault(rel.split(":", 1)[1], []).append(comp)
    for parent_name, kids in children.items():
        parent = nodes.get(parent_name)
        if parent is None:
            continue
        ux, uy = math.cos(parent["angle"]), math.sin(parent["angle"])
        px, py = -uy, ux
        for j, comp in enumerate(kids):
            spread = (j - (len(kids) - 1) / 2) * (node_w + 0.1) * 0.62
            x, y = _free_spot(nodes, parent, (ux, uy), (px, py), spread, area, (cx, cy))
            nodes.setdefault(
                _clean(comp.get("name")),
                {
                    "comp": comp,
                    "cx": x,
                    "cy": y,
                    "angle": parent["angle"],
                    "hw": node_w / 2,
                    "hh": node_h / 2,
                    "ellipse": False,
                },
            )
    return nodes


def _slide_landscape(prs: Any, landscape: Mapping[str, Any]) -> None:
    t = theme()
    app = _clean(landscape.get("central_app", ""))
    slide = _base_slide(prs, f"Landscape - {app}", 2)
    cx, cy = 4.75, 4.0
    components = list(landscape.get("components") or [])
    centre = {"cx": cx, "cy": cy, "hw": 1.05, "hh": 1.05, "ellipse": True}
    nodes = _radial_layout(components, cx, cy)

    # connectors first so the filled shapes sit on top of the line ends
    for name, node in nodes.items():
        comp = node["comp"]
        relation = str(comp.get("relation", "bidirectional"))
        target_name = _clean(comp.get("target") or "")
        if relation.startswith("child_of:"):
            parent = nodes.get(relation.split(":", 1)[1])
            if parent is not None:
                _connect(slide, parent, node, head=False, tail=False, dashed=True)
            continue
        other = nodes.get(target_name) if target_name and target_name != name else None
        other = other or centre
        if relation == "inbound":  # points to the target / centre
            _connect(slide, node, other, head=False, tail=True)
        elif relation == "outbound":  # points away from the target / centre
            _connect(slide, other, node, head=False, tail=True)
        else:
            _connect(slide, node, other, head=True, tail=True)

    circle = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(cx - centre["hw"]),
        Inches(cy - centre["hh"]),
        Inches(2 * centre["hw"]),
        Inches(2 * centre["hh"]),
    )
    circle.name = "Central app"
    circle.fill.solid()
    circle.fill.fore_color.rgb = _rgb(t["central_fill"])
    circle.line.fill.background()
    _shape_text(circle, [(_short(app, 60), 15, t["central_fg"], True)])

    for name, node in nodes.items():
        comp = node["comp"]
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(node["cx"] - node["hw"]),
            Inches(node["cy"] - node["hh"]),
            Inches(2 * node["hw"]),
            Inches(2 * node["hh"]),
        )
        box.name = f"Component {_short(name, 40)}"
        box.fill.solid()
        box.fill.fore_color.rgb = _rgb(t["node_fill"])
        box.line.color.rgb = _rgb(t["node_line"])
        box.line.width = Pt(1.25)
        _shape_text(
            box,
            [
                (_short(name, 38), 11, t["text"], True),
                (_short(comp.get("type", ""), 24), 9, t["muted"], False),
            ],
        )

    vendor = _clean(landscape.get("vendor", "")).strip()
    supplier = _clean(landscape.get("supplier", "")).strip()
    parties = " + ".join(p for p in (vendor, supplier) if p) or "Vendor"
    paragraphs: list[tuple[str, float, str, bool]] = [(f"{parties}:", 14, t["header_bg"], True)]
    responsibilities = [_clean(r) for r in landscape.get("vendor_responsibilities") or []]
    paragraphs += [(f"• {_short(r, 50)}", 12, t["text"], False) for r in responsibilities]
    paragraphs.append(("", 8, t["text"], False))
    paragraphs.append((f"{vendor or 'Vendor'} is:", 14, t["header_bg"], True))
    paragraphs.append(
        (
            f"• {_short(landscape.get('hosting', '') or 'to be confirmed', 120)}",
            12,
            t["text"],
            False,
        )
    )
    _textbox(slide, 9.55, 1.3, 3.4, 5.2, paragraphs, name="Vendor responsibilities")


def _slide_flow(prs: Any, landscape: Mapping[str, Any]) -> None:
    t = theme()
    slide = _base_slide(prs, "Support flow", 3)
    tiers = landscape.get("support_tiers") or {}
    labels = (
        ("L1", "L1 - First line"),
        ("L2", "L2 - Application support"),
        ("L3", "L3 - Engineering"),
    )
    box_w, box_h, gap = 3.4, 2.2, 0.85
    x0 = (SLIDE_W - (3 * box_w + 2 * gap)) / 2
    y = 1.9
    nodes = []
    for i, (key, label) in enumerate(labels):
        x = x0 + i * (box_w + gap)
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(box_w), Inches(box_h)
        )
        box.name = f"Support tier {key}"
        box.fill.solid()
        box.fill.fore_color.rgb = _rgb(t["node_fill"])
        box.line.color.rgb = _rgb(t["node_line"])
        box.line.width = Pt(1.5)
        owner = _short(tiers.get(key, "") or "Owner to be confirmed", 110)
        _shape_text(
            box,
            [(label, 16, t["header_bg"], True), (f"Owner: {owner}", 13, t["text"], False)],
        )
        nodes.append(
            {
                "cx": x + box_w / 2,
                "cy": y + box_h / 2,
                "hw": box_w / 2,
                "hh": box_h / 2,
                "ellipse": False,
            }
        )
    _connect(slide, nodes[0], nodes[1], head=False, tail=True)
    _connect(slide, nodes[1], nodes[2], head=False, tail=True)
    app = _short(landscape.get("central_app", ""), 80)
    _textbox(
        slide,
        x0,
        4.6,
        3 * box_w + 2 * gap,
        1.6,
        [
            ("Escalation", 14, t["header_bg"], True),
            (
                f"Incidents for {app} start at L1. If L1 cannot resolve them they are escalated "
                "to L2 and, when a code or configuration change is needed, to L3. "
                "Escalation contacts and hours are listed on the next slide.",
                13,
                t["text"],
                False,
            ),
        ],
        name="Escalation note",
    )


def _slide_contacts(prs: Any, landscape: Mapping[str, Any]) -> None:
    t = theme()
    slide = _base_slide(prs, "Contacts and SLA", 4)
    contacts = list(landscape.get("contacts") or [])[:12]
    rows = max(len(contacts), 1) + 1
    shape = slide.shapes.add_table(
        rows, 4, Inches(0.5), Inches(1.3), Inches(12.3), Inches(0.45 * rows)
    )
    shape.name = "Contacts table"
    table = shape.table
    for col, width in enumerate((3.0, 3.0, 3.5, 2.8)):
        table.columns[col].width = Inches(width)

    def fill(cell: Any, text: str, *, header: bool) -> None:
        cell.text = ""
        para = cell.text_frame.paragraphs[0]
        run = para.add_run()
        run.text = _short(text, 90)
        _style_run(
            run,
            size=13 if header else 12,
            color=t["header_fg"] if header else t["text"],
            bold=header,
        )
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(t["header_bg"] if header else t["node_fill"])

    for col, head in enumerate(("Party", "Role", "Email", "SLA")):
        fill(table.cell(0, col), head, header=True)
    if not contacts:
        contacts = [{"party": "No contacts recorded yet", "role": "", "email": "", "sla": ""}]
    for r, contact in enumerate(contacts, start=1):
        for col, key in enumerate(("party", "role", "email", "sla")):
            fill(table.cell(r, col), str(contact.get(key, "")), header=False)


def _question_parts(raw: Any) -> tuple[str, str]:
    """(question, answer) of a landscape entry; a plain string is an unanswered question."""
    if isinstance(raw, Mapping):
        return _clean(raw.get("question", "")), _clean(raw.get("answer", "")).strip()
    return _clean(raw), ""


def _slide_questions(prs: Any, landscape: Mapping[str, Any]) -> None:
    t = theme()
    slide = _base_slide(prs, "Open questions and sources", 5)
    questions = [_question_parts(q) for q in landscape.get("open_questions") or []][:10]
    answered = [(q, a) for q, a in questions if a]
    open_ones = [q for q, a in questions if not a]
    sources = list(landscape.get("sources") or [])[:12]
    left: list[tuple[str, float, str, bool]] = []
    if answered:
        left.append(("Answered questions", 16, t["header_bg"], True))
        for q, a in answered:
            left.append((f"Q: {_short(q, 120)}", 12, t["text"], True))
            left.append((f"A: {_short(a, 200)}", 12, t["text"], False))
    left.append(("Open questions", 16, t["header_bg"], True))
    left += [(f"{i}. {_short(q, 140)}", 13, t["text"], False) for i, q in enumerate(open_ones, 1)]
    if not open_ones:
        left.append(("No open questions", 13, t["muted"], False))
    right: list[tuple[str, float, str, bool]] = [("Sources", 16, t["header_bg"], True)]
    right += [
        (
            f"• {_clean(s.get('type', '')).capitalize()}: {_short(s.get('ref', ''), 80)}",
            13,
            t["text"],
            False,
        )
        for s in sources
    ]
    if not sources:
        right.append(("No sources recorded", 13, t["muted"], False))
    _textbox(slide, 0.5, 1.2, 6.9, 5.4, left, name="Open questions")
    _textbox(slide, 7.7, 1.2, 5.1, 5.4, right, name="Sources")


# ------------------------------------------------------------------ public API


def build_support_model_pptx(landscape: Mapping[str, Any], meta: Mapping[str, Any]) -> bytes:
    """Build the .pptx and return its bytes.

    ``landscape`` is the spec 8.8 JSON. ``meta`` keys: transition_name, portfolio, version (int),
    date (ISO str), reviewed_by (user name) and optionally status. Slide 1 reads "Support model -
    {central_app}", transition, portfolio, version, date and "Draft - generated by Orion, reviewed
    by {reviewed_by}". Components with ``relation`` "child_of:<name>" are placed next to the named
    component; "inbound" arrows point to the centre, "outbound" away, "bidirectional" both ways.
    Must open in PowerPoint with exactly 5 slides.
    """
    prs = Presentation()
    prs.slide_width = Emu(12192000)  # exactly 16:9
    prs.slide_height = Emu(6858000)
    prs.core_properties.title = _short(f"Support model - {landscape.get('central_app', '')}", 120)
    prs.core_properties.author = "Orion agent"
    prs.core_properties.subject = TEMPLATE_NAME
    _slide_title(prs, landscape, meta)
    _slide_landscape(prs, landscape)
    _slide_flow(prs, landscape)
    _slide_contacts(prs, landscape)
    _slide_questions(prs, landscape)
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
