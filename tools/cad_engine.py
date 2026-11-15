"""Standalone 2D & 3D Parametric CAD SVG Drafting Engine for BRG Books.

Pure-Python geometric kernel (zero external workspace dependencies) generating:
  - Publication-grade parametric SVGs (`<book>/figures/<stem>.svg`) in the BRG
    Equilibrium / CAS Library palette.
  - Structured JSON CAD scene graphs (`<book>/cad/<stem>.json`).

Supports:
  - Exact 2D intersections (`intersect_lines_2d`, `intersect_rays_2d`,
    `line_circle_intersect`, `circle_circle_intersect`)
  - Lines, polylines, polygons, rectangles, circles, circular & elliptical arcs,
    parabolas, Catmull-Rom smooth splines (`smooth_curve`), and analytic function
    plotting (`plot_func`, `fill_between_funcs`)
  - Exact arbitrary closed-polygon parallel hatching (`hatch_polygon`)
  - Swept CAD arrowheads (`arrow`, `mid_arrow`, `arc_arrow`), right-angle markers
    with optional dot (`right_angle`), angle arcs (`angle_arc`), ISO/DIN dimensions
    (`dim`), structural supports (`pin_support`, `roller_support`, `ground_hatch_line`),
    distributed loads (`udl`), and linear stress diagrams (`linear_diagram`)
  - Crisp haloed SVG typography (`label`, `frac`) with `*italic*`, `_sub`, `^sup`,
    and true vector over-arrows (`vec{r}` or Unicode `\u20d7`) and overbars
    (`bar{x}` or Unicode `\u0304`) — zero `<tspan dy=...>` tags and zero glyph-shift bugs
  - 3D axonometric / isometric / cavalier projections (`IsoProj`, `box3d`,
    `extrude_poly_2d`)
"""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from typing import Callable, Iterable, Sequence

# BRG Equilibrium + Math CAD Palette
PAL: dict[str, str] = {
    "structure": "#18181b",
    "thin": "#3f3f46",
    "compression": "#1a1eb2",
    "compression_fill": "#bdbfe8",
    "blue": "#1a1eb2",
    "blue_fill": "#dbeafe",
    "tension": "#ce4095",
    "tension_fill": "#f0bcdb",
    "magenta": "#ce4095",
    "magenta_fill": "#fce7f3",
    "crimson": "#9f1239",
    "crimson_fill": "#ffe4e6",
    "load": "#2d8a14",
    "load_fill": "#dcfce7",
    "green": "#2d8a14",
    "green_fill": "#dcfce7",
    "amber": "#b45309",
    "amber_fill": "#fef3c7",
    "teal": "#0d7490",
    "teal_fill": "#cffafe",
    "purple": "#6d28d9",
    "purple_fill": "#ede9fe",
    "vertex": "#fde047",
    "resultant": "#1a1eb2",
    "guide": "#8a8a94",
    "ray": "#8a8a94",
    "axis": "#52525b",
    "dim": "#52525b",
    "hatch": "#9ca3af",
    "concrete": "#f3f4f6",
    "masonry": "#f4f1ea",
    "soil": "#f5f0e6",
    "water": "#dbeafe",
    "wood": "#f8f4ec",
    "slate_top": "#f8fafc",
    "slate_left": "#e2e8f0",
    "slate_right": "#cbd5e1",
    "text": "#18181b",
    "muted": "#52525b",
    "white": "#ffffff",
    "bg": "#ffffff",
}

STYLES: dict[str, tuple[str, float, str | None]] = {
    "structure": (PAL["structure"], 1.85, None),
    "heavy": (PAL["structure"], 2.35, None),
    "thin": (PAL["thin"], 1.10, None),
    "dashed": (PAL["thin"], 1.20, "5.5,3.5"),
    "dotted": (PAL["thin"], 1.10, "2.0,3.0"),
    "axis": (PAL["axis"], 1.25, None),
    "center": (PAL["axis"], 1.10, "9,3.5,2,3.5"),
    "neutral": (PAL["axis"], 1.25, "9,3.5,2,3.5"),
    "compression": (PAL["compression"], 2.10, None),
    "compression_dash": (PAL["compression"], 1.70, "6,3.5"),
    "compression_thin": (PAL["compression"], 1.15, None),
    "blue": (PAL["blue"], 2.05, None),
    "blue_dash": (PAL["blue"], 1.55, "5.5,3.5"),
    "tension": (PAL["tension"], 2.05, None),
    "tension_dash": (PAL["tension"], 1.65, "6,3.5"),
    "tension_thin": (PAL["tension"], 1.15, None),
    "magenta": (PAL["magenta"], 2.00, None),
    "magenta_dash": (PAL["magenta"], 1.55, "5.5,3.5"),
    "crimson": (PAL["crimson"], 1.95, None),
    "crimson_dash": (PAL["crimson"], 1.50, "5.5,3.5"),
    "load": (PAL["load"], 1.90, None),
    "load_thin": (PAL["load"], 1.10, None),
    "load_dash": (PAL["load"], 1.55, "6,3.5"),
    "green": (PAL["green"], 1.95, None),
    "green_dash": (PAL["green"], 1.50, "5.5,3.5"),
    "amber": (PAL["amber"], 1.95, None),
    "amber_dash": (PAL["amber"], 1.50, "5.5,3.5"),
    "teal": (PAL["teal"], 1.95, None),
    "teal_dash": (PAL["teal"], 1.50, "5.5,3.5"),
    "purple": (PAL["purple"], 1.95, None),
    "resultant": (PAL["load"], 2.20, "7,3.5"),
    "guide": (PAL["guide"], 0.95, None),
    "guide_dash": (PAL["guide"], 0.95, "4.5,3.2"),
    "ray": (PAL["ray"], 1.00, None),
    "trial": (PAL["muted"], 1.35, "6,3.5"),
    "dim": (PAL["dim"], 0.95, None),
    "dim_dash": (PAL["dim"], 0.95, "5,3.5"),
    "hatch": (PAL["hatch"], 0.85, None),
}

FONT_FAMILY = "'Inter', 'Helvetica Neue', 'Segoe UI', Arial, sans-serif"


# ---------------------------------------------------------------------------
# Exact 2D Geometry Primitives
# ---------------------------------------------------------------------------
def unit_tangent_normal(
    p0: tuple[float, float],
    p1: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Return unit tangent (tx, ty), left-hand unit normal (-ty, tx), and Euclidean length."""
    dx = float(p1[0]) - float(p0[0])
    dy = float(p1[1]) - float(p0[1])
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return (1.0, 0.0), (0.0, 1.0), 0.0
    tx, ty = dx / length, dy / length
    return (tx, ty), (-ty, tx), length


def intersect_lines_2d(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> tuple[float, float]:
    """Exact infinite 2D line-line intersection."""
    x1, y1 = float(a0[0]), float(a0[1])
    x2, y2 = float(a1[0]), float(a1[1])
    x3, y3 = float(b0[0]), float(b0[1])
    x4, y4 = float(b1[0]), float(b1[1])
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        raise ValueError(f"Parallel lines cannot intersect: {a0}->{a1} vs {b0}->{b1}")
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def intersect_rays_2d(
    p0: tuple[float, float],
    d0: tuple[float, float],
    p1: tuple[float, float],
    d1: tuple[float, float],
) -> tuple[float, float]:
    return intersect_lines_2d(p0, (p0[0] + d0[0], p0[1] + d0[1]), p1, (p1[0] + d1[0], p1[1] + d1[1]))


def circle_circle_intersect(
    c0: tuple[float, float],
    r0: float,
    c1: tuple[float, float],
    r1: float,
    pick: str = "upper",
) -> tuple[float, float]:
    dx, dy = c1[0] - c0[0], c1[1] - c0[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-12 or dist > r0 + r1 + 1e-9 or dist < abs(r0 - r1) - 1e-9:
        raise ValueError(f"Circles do not intersect: c0={c0} r0={r0}, c1={c1} r1={r1}")
    a = (r0 * r0 - r1 * r1 + dist * dist) / (2.0 * dist)
    h = math.sqrt(max(0.0, r0 * r0 - a * a))
    mx = c0[0] + a * dx / dist
    my = c0[1] + a * dy / dist
    rx, ry = -dy * (h / dist), dx * (h / dist)
    pa, pb = (mx + rx, my + ry), (mx - rx, my - ry)
    if pick == "upper":
        return pa if pa[1] >= pb[1] else pb
    if pick == "lower":
        return pa if pa[1] <= pb[1] else pb
    if pick == "left":
        return pa if pa[0] <= pb[0] else pb
    return pa if pa[0] >= pb[0] else pb


def line_circle_intersect(
    p0: tuple[float, float],
    p1: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> list[tuple[float, float]]:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    fx, fy = p0[0] - center[0], p0[1] - center[1]
    a = dx * dx + dy * dy
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * c
    if disc < -1e-9 or a < 1e-12:
        return []
    disc = max(0.0, disc)
    sd = math.sqrt(disc)
    t1 = (-b - sd) / (2.0 * a)
    t2 = (-b + sd) / (2.0 * a)
    if abs(t1 - t2) < 1e-9:
        return [(p0[0] + t1 * dx, p0[1] + t1 * dy)]
    return [(p0[0] + t1 * dx, p0[1] + t1 * dy), (p0[0] + t2 * dx, p0[1] + t2 * dy)]


def _point_in_poly(pt: tuple[float, float], poly: Sequence[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test for arbitrary closed simple polygon."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                inside = not inside
    return inside


def _clip_line_against_polygon(
    a: tuple[float, float],
    b: tuple[float, float],
    poly: Sequence[tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Clip open segment a->b against arbitrary (convex or non-convex) closed polygon."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ts = [0.0, 1.0]
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((x1 - ax) * ey - (y1 - ay) * ex) / den
        u = ((x1 - ax) * dy - (y1 - ay) * dx) / den
        if -1e-9 <= t <= 1.0 + 1e-9 and -1e-9 <= u <= 1.0 + 1e-9:
            ts.append(max(0.0, min(1.0, t)))
    ts.sort()
    uniq = [ts[0]]
    for t in ts[1:]:
        if t - uniq[-1] > 1e-7:
            uniq.append(t)
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in range(len(uniq) - 1):
        t0, t1 = uniq[i], uniq[i + 1]
        tm = 0.5 * (t0 + t1)
        mid = (ax + tm * dx, ay + tm * dy)
        if _point_in_poly(mid, poly):
            segs.append(((ax + t0 * dx, ay + t0 * dy), (ax + t1 * dx, ay + t1 * dy)))
    return segs


# ---------------------------------------------------------------------------
# 3D Axonometric / Isometric / Cavalier Projection
# ---------------------------------------------------------------------------
class IsoProj:
    """Configurable 3D-to-2D CAD projection in world coordinates (world Y up, 3D Z up)."""

    def __init__(
        self,
        ox: float = 0.0,
        oy: float = 0.0,
        ax_deg: float = -135.0,
        ay_deg: float = 0.0,
        sx: float = 0.65,
        sy: float = 1.0,
        sz: float = 1.0,
    ) -> None:
        self.ox = ox
        self.oy = oy
        ax = math.radians(ax_deg)
        ay = math.radians(ay_deg)
        self.ux = (math.cos(ax) * sx, math.sin(ax) * sx)
        self.uy = (math.cos(ay) * sy, math.sin(ay) * sy)
        self.uz = (0.0, sz)

    @classmethod
    def math_cabinet(cls, ox: float = 0.0, oy: float = 0.0, scale: float = 1.0) -> "IsoProj":
        """European math textbook axes: +x forward-left (-135°, 0.55), +y right (0°, 1.0), +z vertical up."""
        return cls(ox, oy, ax_deg=-135.0, ay_deg=0.0, sx=0.55 * scale, sy=scale, sz=scale)

    @classmethod
    def isometric(cls, ox: float = 0.0, oy: float = 0.0, scale: float = 1.0) -> "IsoProj":
        """Standard isometric in world (y-up) coordinates: +x down-left (-150°), +y down-right (-30°), +z up."""
        return cls(ox, oy, ax_deg=-150.0, ay_deg=-30.0, sx=scale, sy=scale, sz=scale)

    @classmethod
    def cavalier(cls, ox: float = 0.0, oy: float = 0.0, depth_deg: float = 35.0, depth_scale: float = 0.5, scale: float = 1.0) -> "IsoProj":
        """Front face unwarped (+x right 0°, +z up), +y receding up-right at depth_deg."""
        return cls(ox, oy, ax_deg=0.0, ay_deg=depth_deg, sx=scale, sy=depth_scale * scale, sz=scale)

    def pt(self, x: float, y: float, z: float) -> tuple[float, float]:
        return (
            self.ox + x * self.ux[0] + y * self.uy[0] + z * self.uz[0],
            self.oy + x * self.ux[1] + y * self.uy[1] + z * self.uz[1],
        )

    def pts(self, coords: Iterable[tuple[float, float, float]]) -> list[tuple[float, float]]:
        return [self.pt(x, y, z) for (x, y, z) in coords]


# ---------------------------------------------------------------------------
# Rich Text Tokenizer (supports *italic*, _sub, ^sup, vec{x}/x\u20d7, bar{x}/x\u0304)
# ---------------------------------------------------------------------------
_SUB_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎", "0123456789+-=()")
_SUP_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_UNI_SUB_SET = set("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎∥")
_UNI_SUP_SET = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def _normalize_combining_accents(text: str) -> str:
    """Convert combining over-arrow (\u20d7) and overbar (\u0304/\u0305) into explicit vec{X} / bar{X} markup."""
    # e.g. AB\u20d7 or r\u20d7 -> vec{r}, x\u0304 -> bar{x}, x\u0303 -> tilde{x}
    out = re.sub(r"([A-Za-z0-9α-ωΑ-Ω]+)\u20d7", r"\\vec{\1}", text)
    out = re.sub(r"([A-Za-z0-9α-ωΑ-Ω]+)[̄̅]", r"\\bar{\1}", out)
    out = re.sub(r"([A-Za-z0-9α-ωΑ-Ω]+)̃", r"\\tilde{\1}", out)
    return out


_TOKEN_RE = re.compile(
    r"\\vec\{([^}]+)\}"          # \vec{...}
    r"|\\bar\{([^}]+)\}"         # \bar{...}
    r"|\\tilde\{([^}]+)\}"       # \tilde{...}
    r"|\*([^*]+)\*"              # *italic*
    r"|_\*([^*]+)\*"             # _*italic_sub*
    r"|_\{([^}]+)\}"             # _{sub}
    r"|_([A-Za-z0-9'′+-]+)"      # _sub
    r"|\^\*([^*]+)\*"            # ^*italic_sup*
    r"|\^\{([^}]+)\}"            # ^{sup}
    r"|\^([A-Za-z0-9'′+#°\"-]+)" # ^sup
)


def _char_width_factor(ch: str) -> float:
    if ch == " ":
        return 0.38
    if ch in "ilI.,:;|!'":
        return 0.33
    if ch in "()[]/fj′":
        return 0.44
    if ch in "+−-=":
        return 0.64
    if ch in "MWm@%":
        return 0.88
    if ch in "×÷⅛⅜⅝⅞¼½¾⇒⇔≤≥≈≠±∩∪":
        return 0.76
    if ch.isdigit():
        return 0.63
    if ch == "□" or ch.isupper() or ch in "ℝℤℚℕℂΔΦΨΩΣΠ":
        return 0.69
    return 0.59


def _split_unicode_sub_sup(plain: str, is_it: bool) -> list[tuple[str, str, bool]]:
    segs: list[tuple[str, str, bool]] = []
    i, n = 0, len(plain)
    while i < n:
        ch = plain[i]
        if ch == "□":
            segs.append(("box", "□", False))
            i += 1
        elif ch in _UNI_SUB_SET:
            j = i
            while j < n and plain[j] in _UNI_SUB_SET:
                j += 1
            segs.append(("sub", plain[i:j].translate(_SUB_MAP), False))
            i = j
        elif ch in _UNI_SUP_SET:
            j = i
            while j < n and plain[j] in _UNI_SUP_SET:
                j += 1
            segs.append(("sup", plain[i:j].translate(_SUP_MAP), False))
            i = j
        else:
            j = i
            while j < n and plain[j] not in _UNI_SUB_SET and plain[j] not in _UNI_SUP_SET and plain[j] != "□":
                j += 1
            segs.append(("norm", plain[i:j], is_it))
            i = j
    return segs


def _tokenize_rich_text(text: str, default_italic: bool = False) -> list[tuple[str, str, bool]]:
    """Tokenize into (kind, content, is_italic) where kind in ('norm','sub','sup','box','vec','bar','tilde')."""
    text = _normalize_combining_accents(text)
    segs: list[tuple[str, str, bool]] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > pos:
            segs.extend(_split_unicode_sub_sup(text[pos : m.start()], default_italic))
        vec_t, bar_t, tilde_t, it, sub_it, sub_b, sub_s, sup_it, sup_b, sup_s = m.groups()
        if vec_t is not None:
            inner = vec_t.strip("*")
            segs.append(("vec", inner, True if ("*" in vec_t or len(inner) == 1) else default_italic))
        elif bar_t is not None:
            inner = bar_t.strip("*")
            segs.append(("bar", inner, True if ("*" in bar_t or inner.islower()) else default_italic))
        elif tilde_t is not None:
            inner = tilde_t.strip("*")
            segs.append(("tilde", inner, True if ("*" in tilde_t or inner.islower()) else default_italic))
        elif it is not None:
            if any(k in it for k in ("_", "^", "\\vec", "\\bar", "\\tilde")):
                segs.extend(_tokenize_rich_text(it, default_italic=True))
            else:
                segs.extend(_split_unicode_sub_sup(it, True))
        elif sub_it is not None:
            segs.append(("sub", sub_it.translate(_SUB_MAP), True))
        elif sub_b is not None or sub_s is not None:
            s = sub_b if sub_b is not None else sub_s
            segs.append(("sub", s.translate(_SUB_MAP), False))
        elif sup_it is not None:
            segs.append(("sup", sup_it.translate(_SUP_MAP), True))
        elif sup_b is not None or sup_s is not None:
            s = sup_b if sup_b is not None else sup_s
            segs.append(("sup", s.translate(_SUP_MAP), False))
        pos = m.end()
    if pos < len(text):
        segs.extend(_split_unicode_sub_sup(text[pos:], default_italic))
    return [s for s in segs if s[1]]


def format_rich_tspan(text: str) -> tuple[str, float]:
    segs = _tokenize_rich_text(text, False)
    approx_chars = 0.0
    parts: list[str] = []
    for kind, s_txt, _ in segs:
        parts.append(html.escape(s_txt))
        approx_chars += len(s_txt) * (0.95 if kind in ("norm", "vec", "bar", "tilde") else 0.68)
    return "".join(parts), max(approx_chars, 1.0)


def _dashed_screen_path(spts: Sequence[tuple[float, float]], dash_str: str) -> str:
    """Subdivide screen polyline `spts` along `dash_str` (e.g. '5.5,3.5') into a crisp SVG <path d='...'>.

    Guarantees identical dash rendering across all browsers AND PyMuPDF (fitz) PNG previews.
    """
    parts = [float(x) for x in re.split(r"[,\s]+", dash_str.strip()) if x]
    if not parts or len(spts) < 2:
        return ""
    if len(parts) % 2 == 1:
        parts = parts * 2
    pat_idx = 0
    rem = parts[0]
    draw_on = True
    cmds: list[str] = []
    for i in range(len(spts) - 1):
        x0, y0 = spts[i]
        x1, y1 = spts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            continue
        ux, uy = dx / seg_len, dy / seg_len
        pos = 0.0
        while pos < seg_len - 1e-6:
            step = min(rem, seg_len - pos)
            if draw_on and step > 0.15:
                xa, ya = x0 + ux * pos, y0 + uy * pos
                xb, yb = x0 + ux * (pos + step), y0 + uy * (pos + step)
                cmds.append(f"M{xa:.2f},{ya:.2f}L{xb:.2f},{yb:.2f}")
            pos += step
            rem -= step
            if rem <= 1e-6:
                pat_idx = (pat_idx + 1) % len(parts)
                rem = parts[pat_idx]
                draw_on = (pat_idx % 2 == 0)
    return " ".join(cmds)


# ---------------------------------------------------------------------------
# Main CadDrawing Class
# ---------------------------------------------------------------------------
class CadDrawing:
    """2D/3D parametric CAD drawing in world coordinates (y up)."""

    def __init__(
        self,
        name: str,
        scale: float = 100.0,
        pad: float = 14.0,
        title: str = "",
    ) -> None:
        self.name = name
        self.scale = float(scale)
        self.pad = float(pad)
        self.title = title
        self._bg_elems: list[str] = []
        self._geom_elems: list[str] = []
        self._node_elems: list[str] = []
        self._text_elems: list[str] = []
        self._bounds_pts: list[tuple[float, float]] = []
        self._scene_items: list[dict] = []

    def sx(self, x: float) -> float:
        return float(x) * self.scale

    def sy(self, y: float) -> float:
        return -float(y) * self.scale

    def sxy(self, p: tuple[float, float]) -> tuple[float, float]:
        return (float(p[0]) * self.scale, -float(p[1]) * self.scale)

    def _include_screen_pt(self, sx: float, sy: float, r: float = 2.0) -> None:
        self._bounds_pts.append((sx - r, sy - r))
        self._bounds_pts.append((sx + r, sy + r))

    def include_world_pt(self, p: tuple[float, float], pad_px: float = 4.0) -> None:
        sx, sy = self.sxy(p)
        self._include_screen_pt(sx, sy, pad_px)

    # ------------------------------------------------------------------ lines & polygons
    def line(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        name: str = "line",
        layer: str = "geom",
    ) -> None:
        st_col, st_w, st_dash = STYLES.get(style, STYLES["structure"])
        col = color or st_col
        w = width if width is not None else st_w
        da = dash if dash is not None else st_dash
        self._scene_items.append({"type": "line", "name": name, "p0": [round(p0[0], 4), round(p0[1], 4)], "p1": [round(p1[0], 4), round(p1[1], 4)], "color": col, "width": w})
        x0, y0 = self.sxy(p0)
        x1, y1 = self.sxy(p1)
        self._include_screen_pt(x0, y0, w)
        self._include_screen_pt(x1, y1, w)
        if da:
            d_str = _dashed_screen_path([(x0, y0), (x1, y1)], da)
            el = f'<path d="{d_str}" fill="none" stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
        else:
            el = (
                f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                f'stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
            )
        (self._bg_elems if layer == "bg" else self._geom_elems).append(el)

    def polyline(
        self,
        pts: Sequence[tuple[float, float]],
        style: str = "structure",
        closed: bool = False,
        fill: str | None = None,
        fill_opacity: float = 1.0,
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        stroke: bool = True,
        name: str = "polyline",
        layer: str = "geom",
    ) -> None:
        if len(pts) < 2:
            return
        st_col, st_w, st_dash = STYLES.get(style, STYLES["structure"])
        col = (color or st_col) if stroke else "none"
        w = (width if width is not None else st_w) if stroke else 0.0
        da = dash if dash is not None else st_dash
        self._scene_items.append({"type": "polyline", "name": name, "closed": closed, "n_pts": len(pts), "color": col, "fill": fill})
        spts = [self.sxy(p) for p in pts]
        if closed and len(spts) >= 3 and math.hypot(spts[0][0] - spts[-1][0], spts[0][1] - spts[-1][1]) > 1e-6:
            spts.append(spts[0])
        for sx, sy in spts:
            self._include_screen_pt(sx, sy, max(w, 1.5))
        pts_attr = " ".join(f"{sx:.2f},{sy:.2f}" for sx, sy in spts)
        fill_attr = f' fill="{fill}"' if fill else ' fill="none"'
        if fill and fill_opacity < 0.999:
            fill_attr += f' fill-opacity="{fill_opacity:.2f}"'
        if da and stroke:
            if fill:
                self._bg_elems.append(f'<polygon points="{pts_attr}"{fill_attr} stroke="none"/>')
            d_str = _dashed_screen_path(spts, da)
            el = f'<path d="{d_str}" fill="none" stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
            (self._bg_elems if layer == "bg" else self._geom_elems).append(el)
            return
        stroke_attr = (
            f' stroke="{col}" stroke-width="{w:.2f}" stroke-linejoin="round" stroke-linecap="round"'
            if stroke
            else ' stroke="none"'
        )
        tag = "polygon" if closed else "polyline"
        el = f'<{tag} points="{pts_attr}"{fill_attr}{stroke_attr}/>'
        if layer == "bg" or (fill and not stroke):
            self._bg_elems.append(el)
        else:
            self._geom_elems.append(el)

    def fill_poly(self, pts: Sequence[tuple[float, float]], fill: str, opacity: float = 1.0) -> None:
        self.polyline(pts, closed=True, fill=fill, fill_opacity=opacity, stroke=False, layer="bg")

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        fill: str | None = None,
        fill_opacity: float = 1.0,
        stroke: bool = True,
        dash: str | None = None,
        rx_px: float = 0.0,
        layer: str = "geom",
    ) -> None:
        if rx_px > 0:
            st_col, st_w, st_dash = STYLES.get(style, STYLES["structure"])
            col = (color or st_col) if stroke else "none"
            sw = (width if width is not None else st_w) if stroke else 0.0
            da = dash if dash is not None else st_dash
            sx0, sy0 = self.sxy((x, y + h))
            sw_px, sh_px = w * self.scale, h * self.scale
            self._include_screen_pt(sx0, sy0, sw)
            self._include_screen_pt(sx0 + sw_px, sy0 + sh_px, sw)
            f_attr = f' fill="{fill}"' if fill else ' fill="none"'
            if fill and fill_opacity < 0.999:
                f_attr += f' fill-opacity="{fill_opacity:.2f}"'
            s_attr = f' stroke="{col}" stroke-width="{sw:.2f}"' if stroke else ' stroke="none"'
            if da and stroke:
                s_attr += f' stroke-dasharray="{da}"'
            el = f'<rect x="{sx0:.2f}" y="{sy0:.2f}" width="{sw_px:.2f}" height="{sh_px:.2f}" rx="{rx_px:.2f}"{f_attr}{s_attr}/>'
            (self._bg_elems if layer == "bg" else self._geom_elems).append(el)
            return
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        if fill:
            self.fill_poly(pts, fill, fill_opacity)
        if stroke:
            self.polyline(pts, style=style, color=color, width=width, closed=True, stroke=True, dash=dash, layer=layer)

    # ------------------------------------------------------------------ circles, ellipses, arcs & curves
    def circle(
        self,
        center: tuple[float, float],
        radius: float,
        style: str = "structure",
        fill: str | None = None,
        fill_opacity: float = 1.0,
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        layer: str = "geom",
    ) -> None:
        st_col, st_w, st_dash = STYLES.get(style, STYLES["structure"])
        col = color or st_col
        w = width if width is not None else st_w
        da = dash if dash is not None else st_dash
        self._scene_items.append({"type": "circle", "center": [round(center[0], 4), round(center[1], 4)], "r": round(radius, 4), "color": col})
        cx, cy = self.sxy(center)
        sr = radius * self.scale
        self._include_screen_pt(cx, cy, sr + w)
        f_attr = f' fill="{fill}"' if fill else ' fill="none"'
        if fill and fill_opacity < 0.999:
            f_attr += f' fill-opacity="{fill_opacity:.2f}"'
        da_attr = f' stroke-dasharray="{da}"' if da else ""
        el = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{sr:.2f}"{f_attr} stroke="{col}" stroke-width="{w:.2f}"{da_attr}/>'
        (self._node_elems if layer == "node" else self._bg_elems if layer == "bg" else self._geom_elems).append(el)

    def ellipse(
        self,
        center: tuple[float, float],
        rx: float,
        ry: float,
        angle_deg: float = 0.0,
        style: str = "structure",
        fill: str | None = None,
        fill_opacity: float = 1.0,
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        stroke: bool = True,
        layer: str = "geom",
    ) -> None:
        ang = math.radians(angle_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        n = 72
        pts = []
        for i in range(n):
            t = 2.0 * math.pi * i / n
            lx, ly = rx * math.cos(t), ry * math.sin(t)
            pts.append((center[0] + lx * ca - ly * sa, center[1] + lx * sa + ly * ca))
        if fill:
            self.fill_poly(pts, fill, fill_opacity)
        if stroke:
            self.polyline(pts, style=style, color=color, width=width, dash=dash, closed=True, layer=layer, name="ellipse")

    def elliptical_arc(
        self,
        center: tuple[float, float],
        rx: float,
        ry: float,
        deg_start: float,
        deg_end: float,
        angle_deg: float = 0.0,
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        n_samples: int = 48,
    ) -> list[tuple[float, float]]:
        ang = math.radians(angle_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        pts = []
        for i in range(n_samples + 1):
            t = math.radians(deg_start + (deg_end - deg_start) * i / n_samples)
            lx, ly = rx * math.cos(t), ry * math.sin(t)
            pts.append((center[0] + lx * ca - ly * sa, center[1] + lx * sa + ly * ca))
        self.polyline(pts, style=style, color=color, width=width, dash=dash, name="elliptical_arc")
        return pts

    def arc(
        self,
        center: tuple[float, float],
        radius: float,
        deg_start: float,
        deg_end: float,
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        n_samples: int = 48,
    ) -> list[tuple[float, float]]:
        pts = [
            (
                center[0] + radius * math.cos(math.radians(deg_start + (deg_end - deg_start) * i / n_samples)),
                center[1] + radius * math.sin(math.radians(deg_start + (deg_end - deg_start) * i / n_samples)),
            )
            for i in range(n_samples + 1)
        ]
        self.polyline(pts, style=style, color=color, width=width, dash=dash, name="arc")
        return pts

    def sector_fill(
        self,
        center: tuple[float, float],
        radius: float,
        deg_start: float,
        deg_end: float,
        fill: str,
        opacity: float = 0.35,
        n_samples: int = 36,
    ) -> None:
        pts = [center] + [
            (
                center[0] + radius * math.cos(math.radians(deg_start + (deg_end - deg_start) * i / n_samples)),
                center[1] + radius * math.sin(math.radians(deg_start + (deg_end - deg_start) * i / n_samples)),
            )
            for i in range(n_samples + 1)
        ]
        self.fill_poly(pts, fill, opacity=opacity)

    def smooth_curve(
        self,
        pts: Sequence[tuple[float, float]],
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        samples_per_seg: int = 18,
        alpha: float = 0.5,
    ) -> list[tuple[float, float]]:
        if len(pts) < 2:
            return list(pts)
        if len(pts) == 2:
            self.line(pts[0], pts[1], style=style, color=color, width=width, dash=dash)
            return list(pts)
        p_start = (2.0 * pts[0][0] - pts[1][0], 2.0 * pts[0][1] - pts[1][1])
        p_end = (2.0 * pts[-1][0] - pts[-2][0], 2.0 * pts[-1][1] - pts[-2][1])
        ext = [p_start] + list(pts) + [p_end]

        def tj(ti: float, pi: tuple[float, float], pj: tuple[float, float]) -> float:
            return ti + max(math.hypot(pj[0] - pi[0], pj[1] - pi[1]), 1e-6) ** alpha

        sampled: list[tuple[float, float]] = []
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
            t0 = 0.0
            t1 = tj(t0, p0, p1)
            t2 = tj(t1, p1, p2)
            t3 = tj(t2, p2, p3)
            for k in range(samples_per_seg + (1 if i == len(pts) - 2 else 0)):
                t = t1 + (t2 - t1) * (k / samples_per_seg)
                a1 = ((t1 - t) / (t1 - t0) * p0[0] + (t - t0) / (t1 - t0) * p1[0], (t1 - t) / (t1 - t0) * p0[1] + (t - t0) / (t1 - t0) * p1[1])
                a2 = ((t2 - t) / (t2 - t1) * p1[0] + (t - t1) / (t2 - t1) * p2[0], (t2 - t) / (t2 - t1) * p1[1] + (t - t1) / (t2 - t1) * p2[1])
                a3 = ((t3 - t) / (t3 - t2) * p2[0] + (t - t2) / (t3 - t2) * p3[0], (t3 - t) / (t3 - t2) * p2[1] + (t - t2) / (t3 - t2) * p3[1])
                b1 = ((t2 - t) / (t2 - t0) * a1[0] + (t - t0) / (t2 - t0) * a2[0], (t2 - t) / (t2 - t0) * a1[1] + (t - t0) / (t2 - t0) * a2[1])
                b2 = ((t3 - t) / (t3 - t1) * a2[0] + (t - t1) / (t3 - t1) * a3[0], (t3 - t) / (t3 - t1) * a2[1] + (t - t1) / (t3 - t1) * a3[1])
                c = ((t2 - t) / (t2 - t1) * b1[0] + (t - t1) / (t2 - t1) * b2[0], (t2 - t) / (t2 - t1) * b1[1] + (t - t1) / (t2 - t1) * b2[1])
                sampled.append(c)
        self.polyline(sampled, style=style, color=color, width=width, dash=dash, name="spline")
        return sampled

    def plot_func(
        self,
        fn: Callable[[float], float],
        x0: float,
        x1: float,
        n_samples: int = 120,
        y_clip: tuple[float, float] | None = None,
        style: str = "blue",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
    ) -> list[list[tuple[float, float]]]:
        """Plot y = fn(x) over [x0, x1], automatically splitting branches at poles / y_clip."""
        branches: list[list[tuple[float, float]]] = []
        cur: list[tuple[float, float]] = []
        for i in range(n_samples + 1):
            x = x0 + (x1 - x0) * i / n_samples
            try:
                y = float(fn(x))
            except Exception:
                y = float("nan")
            if not math.isfinite(y) or (y_clip and (y < y_clip[0] or y > y_clip[1])):
                if len(cur) >= 2:
                    branches.append(cur)
                cur = []
                continue
            if cur and y_clip and abs(y - cur[-1][1]) > 0.65 * (y_clip[1] - y_clip[0]):
                if len(cur) >= 2:
                    branches.append(cur)
                cur = []
            cur.append((x, y))
        if len(cur) >= 2:
            branches.append(cur)
        for br in branches:
            self.polyline(br, style=style, color=color, width=width, dash=dash, name="func")
        return branches

    def fill_under_func(
        self,
        fn: Callable[[float], float],
        x0: float,
        x1: float,
        y_base: float = 0.0,
        fill: str = PAL["blue_fill"],
        opacity: float = 0.45,
        n_samples: int = 80,
    ) -> None:
        pts = [(x0, y_base)]
        for i in range(n_samples + 1):
            x = x0 + (x1 - x0) * i / n_samples
            pts.append((x, float(fn(x))))
        pts.append((x1, y_base))
        self.fill_poly(pts, fill, opacity=opacity)

    def fill_between_funcs(
        self,
        fn1: Callable[[float], float],
        fn2: Callable[[float], float],
        x0: float,
        x1: float,
        fill: str = PAL["blue_fill"],
        opacity: float = 0.45,
        n_samples: int = 80,
    ) -> None:
        top = [(x0 + (x1 - x0) * i / n_samples, float(fn1(x0 + (x1 - x0) * i / n_samples))) for i in range(n_samples + 1)]
        bot = [(x0 + (x1 - x0) * i / n_samples, float(fn2(x0 + (x1 - x0) * i / n_samples))) for i in range(n_samples, -1, -1)]
        self.fill_poly(top + bot, fill, opacity=opacity)

    # ------------------------------------------------------------------ exact polygon hatching
    def hatch_polygon(
        self,
        poly_pts: Sequence[tuple[float, float]],
        spacing_px: float = 7.5,
        angle_deg: float = 45.0,
        color: str = PAL["hatch"],
        width: float = 0.85,
        fill: str | None = None,
        fill_opacity: float = 1.0,
    ) -> None:
        if fill:
            self.fill_poly(poly_pts, fill, fill_opacity)
        if len(poly_pts) < 3:
            return
        step = spacing_px / self.scale
        ang = math.radians(angle_deg)
        dx, dy = math.cos(ang), math.sin(ang)
        nx, ny = -dy, dx
        xs = [p[0] for p in poly_pts]
        ys = [p[1] for p in poly_pts]
        cx, cy = 0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) + 2.0 * step
        n_steps = int(math.ceil(diag / step))
        for k in range(-n_steps, n_steps + 1):
            ox, oy = cx + k * step * nx, cy + k * step * ny
            a = (ox - diag * dx, oy - diag * dy)
            b = (ox + diag * dx, oy + diag * dy)
            for s0, s1 in _clip_line_against_polygon(a, b, poly_pts):
                if math.hypot(s1[0] - s0[0], s1[1] - s0[1]) * self.scale > 1.2:
                    self.line(s0, s1, color=color, width=width, name="hatch", layer="bg")

    # ------------------------------------------------------------------ arrows, axes, markers & geometry widgets
    def _arrowhead_svg(
        self,
        tip_s: tuple[float, float],
        dir_s: tuple[float, float],
        head_len: float,
        head_w: float,
        color: str,
        open_head: bool = False,
    ) -> None:
        tx, ty = tip_s
        ux, uy = dir_s
        bx, by = tx - ux * head_len, ty - uy * head_len
        px, py = -uy * (head_w * 0.5), ux * (head_w * 0.5)
        p1, p2 = (bx + px, by + py), (bx - px, by - py)
        self._include_screen_pt(p1[0], p1[1], 1.5)
        self._include_screen_pt(p2[0], p2[1], 1.5)
        if open_head:
            self._geom_elems.append(
                f'<polyline points="{p1[0]:.2f},{p1[1]:.2f} {tx:.2f},{ty:.2f} {p2[0]:.2f},{p2[1]:.2f}" '
                f'fill="none" stroke="{color}" stroke-width="1.20" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        else:
            ix, iy = tx - ux * (head_len * 0.84), ty - uy * (head_len * 0.84)
            self._geom_elems.append(
                f'<polygon points="{tx:.2f},{ty:.2f} {p1[0]:.2f},{p1[1]:.2f} {ix:.2f},{iy:.2f} {p2[0]:.2f},{p2[1]:.2f}" '
                f'fill="{color}" stroke="none"/>'
            )

    def arrow(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        style: str = "structure",
        color: str | None = None,
        width: float | None = None,
        dash: str | None = None,
        head_len: float = 9.0,
        head_w: float = 5.8,
        double: bool = False,
        head_at_start: bool = False,
        open_head: bool = False,
        start_gap_px: float = 0.0,
        end_gap_px: float = 0.0,
        name: str = "arrow",
    ) -> None:
        st_col, st_w, st_dash = STYLES.get(style, STYLES["structure"])
        col = color or st_col
        w = width if width is not None else st_w
        da = dash if dash is not None else st_dash
        self._scene_items.append({"type": "arrow", "name": name, "p0": [round(p0[0], 4), round(p0[1], 4)], "p1": [round(p1[0], 4), round(p1[1], 4)], "color": col})
        s0_raw, s1_raw = self.sxy(p0), self.sxy(p1)
        dx, dy = s1_raw[0] - s0_raw[0], s1_raw[1] - s0_raw[1]
        slen_raw = math.hypot(dx, dy)
        if slen_raw < 1e-6:
            return
        ux, uy = dx / slen_raw, dy / slen_raw
        s0 = (s0_raw[0] + ux * start_gap_px, s0_raw[1] + uy * start_gap_px)
        s1 = (s1_raw[0] - ux * end_gap_px, s1_raw[1] - uy * end_gap_px)
        slen = max(1.0, slen_raw - start_gap_px - end_gap_px)
        hl = min(head_len, slen * 0.46)
        hw = head_w * (hl / max(head_len, 1e-6))
        trim_end = 0.0 if open_head else (hl * 0.65 if (not head_at_start or double) else 0.0)
        trim_start = (0.0 if open_head else hl * 0.65) if (double or head_at_start) else 0.0
        xa, ya = s0[0] + ux * trim_start, s0[1] + uy * trim_start
        xb, yb = s1[0] - ux * trim_end, s1[1] - uy * trim_end
        if da:
            d_str = _dashed_screen_path([(xa, ya), (xb, yb)], da)
            self._geom_elems.append(
                f'<path d="{d_str}" fill="none" stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
            )
        else:
            self._geom_elems.append(
                f'<line x1="{xa:.2f}" y1="{ya:.2f}" x2="{xb:.2f}" y2="{yb:.2f}" '
                f'stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round"/>'
            )
        self._include_screen_pt(s0_raw[0], s0_raw[1], w + 2)
        self._include_screen_pt(s1_raw[0], s1_raw[1], w + 2)
        if not head_at_start or double:
            self._arrowhead_svg(s1, (ux, uy), hl, hw, col, open_head=open_head)
        if double or head_at_start:
            self._arrowhead_svg(s0, (-ux, -uy), hl, hw, col, open_head=open_head)

    def arc_arrow(
        self,
        center: tuple[float, float],
        radius: float,
        deg_start: float,
        deg_end: float,
        style: str = "thin",
        color: str | None = None,
        width: float | None = None,
        head_len: float = 7.5,
        head_w: float = 5.0,
        n_samples: int = 36,
    ) -> list[tuple[float, float]]:
        """Circular arc from deg_start to deg_end with an arrowhead at deg_end."""
        st_col, st_w, _ = STYLES.get(style, STYLES["thin"])
        col = color or st_col
        pts = self.arc(center, radius, deg_start, deg_end, style=style, color=col, width=width, n_samples=n_samples)
        if len(pts) >= 2:
            s_prev = self.sxy(pts[-2])
            s_tip = self.sxy(pts[-1])
            dx, dy = s_tip[0] - s_prev[0], s_tip[1] - s_prev[1]
            L = math.hypot(dx, dy)
            if L > 1e-6:
                self._arrowhead_svg(s_tip, (dx / L, dy / L), head_len, head_w, col)
        return pts

    def axes(
        self,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        origin: tuple[float, float] = (0.0, 0.0),
        x_label: str = "*x*",
        y_label: str = "*y*",
        x_ticks: Sequence[tuple[float, str]] = (),
        y_ticks: Sequence[tuple[float, str]] = (),
        tick_px: float = 4.0,
        grid: bool = False,
        x_step: float | None = None,
        y_step: float | None = None,
        label_size: float = 13.0,
    ) -> None:
        """Draw crisp Cartesian coordinate axes with arrowheads, optional grid, and ticks."""
        ox, oy = origin
        if grid and x_step and y_step:
            gx = math.ceil(x_range[0] / x_step) * x_step
            while gx <= x_range[1] + 1e-9:
                self.line((gx, y_range[0]), (gx, y_range[1]), color="#e4e4e7", width=0.75, layer="bg")
                gx += x_step
            gy = math.ceil(y_range[0] / y_step) * y_step
            while gy <= y_range[1] + 1e-9:
                self.line((x_range[0], gy), (x_range[1], gy), color="#e4e4e7", width=0.75, layer="bg")
                gy += y_step
        self.arrow((x_range[0], oy), (x_range[1], oy), style="axis", head_len=8.5, head_w=5.4)
        self.arrow((ox, y_range[0]), (ox, y_range[1]), style="axis", head_len=8.5, head_w=5.4)
        if x_label:
            self.label((x_range[1], oy), x_label, dx_px=12.0, dy_px=1.0, size=label_size, anchor="start")
        if y_label:
            self.label((ox, y_range[1]), y_label, dx_px=0.0, dy_px=-12.0, size=label_size, anchor="middle")
        th = tick_px / self.scale
        for xv, xlbl in x_ticks:
            self.line((xv, oy - th), (xv, oy + th), style="axis", width=1.05)
            if xlbl:
                self.label((xv, oy), xlbl, dy_px=15.0, size=label_size - 1.0, anchor="middle")
        for yv, ylbl in y_ticks:
            self.line((ox - th, yv), (ox + th, yv), style="axis", width=1.05)
            if ylbl:
                self.label((ox, yv), ylbl, dx_px=-9.0, size=label_size - 1.0, anchor="end")

    def right_angle(
        self,
        vertex: tuple[float, float],
        p_dir1: tuple[float, float],
        p_dir2: tuple[float, float],
        r_px: float = 14.0,
        dot: bool = True,
        square: bool = False,
        color: str = PAL["thin"],
        fill: str | None = None,
    ) -> None:
        """Draw a European arc+dot right-angle symbol (or square corner when square=True)."""
        (u1x, u1y), _, l1 = unit_tangent_normal(vertex, p_dir1)
        (u2x, u2y), _, l2 = unit_tangent_normal(vertex, p_dir2)
        if l1 < 1e-9 or l2 < 1e-9:
            return
        r = r_px / self.scale
        if square:
            q1 = (vertex[0] + u1x * r, vertex[1] + u1y * r)
            q2 = (vertex[0] + (u1x + u2x) * r, vertex[1] + (u1y + u2y) * r)
            q3 = (vertex[0] + u2x * r, vertex[1] + u2y * r)
            if fill:
                self.fill_poly([vertex, q1, q2, q3], fill, opacity=0.35)
            self.polyline([q1, q2, q3], color=color, width=1.05)
            return
        a1 = math.degrees(math.atan2(u1y, u1x))
        a2 = math.degrees(math.atan2(u2y, u2x))
        diff = (a2 - a1 + 180.0) % 360.0 - 180.0
        if fill:
            self.sector_fill(vertex, r, a1, a1 + diff, fill, opacity=0.32, n_samples=18)
        self.arc(vertex, r, a1, a1 + diff, color=color, width=1.05, n_samples=18)
        if dot:
            amid = math.radians(a1 + 0.5 * diff)
            dp = (vertex[0] + 0.44 * r * math.cos(amid), vertex[1] + 0.44 * r * math.sin(amid))
            self.dot(dp, r_px=1.65, color=color)

    def angle_arc(
        self,
        vertex: tuple[float, float],
        deg0: float,
        deg1: float,
        r_px: float = 24.0,
        label_text: str = "",
        label_r_extra_px: float = 11.0,
        color: str = PAL["thin"],
        fill: str | None = None,
        arrow: bool = False,
        label_size: float = 12.5,
    ) -> None:
        r = r_px / self.scale
        if fill:
            self.sector_fill(vertex, r, deg0, deg1, fill, opacity=0.28, n_samples=24)
        if arrow:
            self.arc_arrow(vertex, r, deg0, deg1, color=color, width=1.05, head_len=6.5, head_w=4.4, n_samples=24)
        else:
            self.arc(vertex, r, deg0, deg1, color=color, width=1.05, n_samples=24)
        if label_text:
            amid = math.radians(0.5 * (deg0 + deg1))
            rl = (r_px + label_r_extra_px) / self.scale
            lp = (vertex[0] + rl * math.cos(amid), vertex[1] + rl * math.sin(amid))
            self.label(lp, label_text, size=label_size, color=color if color != PAL["thin"] else PAL["text"], anchor="middle", valign="middle")

    def hinge(self, p: tuple[float, float], r_px: float = 3.3, color: str = PAL["structure"], fill: str = PAL["white"]) -> None:
        cx, cy = self.sxy(p)
        self._include_screen_pt(cx, cy, r_px + 2)
        self._node_elems.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_px:.2f}" fill="{fill}" stroke="{color}" stroke-width="1.5"/>')

    def vertex(self, p: tuple[float, float], r_px: float = 3.3, fill: str = PAL["vertex"], color: str = PAL["structure"]) -> None:
        """Geometry vertex disk (yellow fill with crisp dark border, matching textbook diagrams)."""
        self.hinge(p, r_px=r_px, color=color, fill=fill)

    def dot(self, p: tuple[float, float], r_px: float = 2.8, color: str = PAL["structure"]) -> None:
        cx, cy = self.sxy(p)
        self._include_screen_pt(cx, cy, r_px + 1.5)
        self._node_elems.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_px:.2f}" fill="{color}" stroke="none"/>')

    def edge_ticks(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        count: int = 1,
        tick_px: float = 7.5,
        gap_px: float = 3.2,
        color: str = PAL["structure"],
        width: float = 1.25,
    ) -> None:
        """Draw 1, 2, or 3 perpendicular congruence tick marks at the midpoint of segment p0->p1."""
        (tx, ty), (nx, ny), length = unit_tangent_normal(p0, p1)
        if length < 1e-9 or count < 1:
            return
        mx, my = 0.5 * (p0[0] + p1[0]), 0.5 * (p0[1] + p1[1])
        half_t = (0.5 * tick_px) / self.scale
        step = gap_px / self.scale
        for k in range(count):
            off = (k - 0.5 * (count - 1)) * step
            cx, cy = mx + tx * off, my + ty * off
            self.line((cx - nx * half_t, cy - ny * half_t), (cx + nx * half_t, cy + ny * half_t), color=color, width=width)

    def box3d(
        self,
        proj: IsoProj,
        x0: float,
        y0: float,
        z0: float,
        dx: float,
        dy: float,
        dz: float,
        fill_front: str | None = PAL["slate_left"],
        fill_right: str | None = PAL["slate_right"],
        fill_top: str | None = PAL["slate_top"],
        fill_opacity: float = 0.75,
        style: str = "structure",
        hidden: bool = True,
    ) -> dict[str, tuple[float, float]]:
        """Draw a projected 3D box (cavalier or math_cabinet) with optional dashed hidden edges.

        Returns projected 2D vertices keyed by '000'..'111' (bits x, y, z).
        """
        v = {
            f"{ix}{iy}{iz}": proj.pt(x0 + ix * dx, y0 + iy * dy, z0 + iz * dz)
            for ix in (0, 1)
            for iy in (0, 1)
            for iz in (0, 1)
        }
        # Determine whether +x goes forward-left (math_cabinet: ux[1] < 0) or right (cavalier: ux[0] > 0, uy[1] > 0)
        if proj.ux[0] >= 0.5 and proj.uy[1] >= 0.0:
            # Cavalier (+x right, +y receding back-right, +z up): front y=0, right x=1, top z=1; hidden origin at 010
            if fill_front:
                self.fill_poly([v["000"], v["100"], v["101"], v["001"]], fill_front, fill_opacity)
            if fill_right:
                self.fill_poly([v["100"], v["110"], v["111"], v["101"]], fill_right, fill_opacity)
            if fill_top:
                self.fill_poly([v["001"], v["101"], v["111"], v["011"]], fill_top, fill_opacity)
            if hidden:
                for a, b in (("000", "010"), ("010", "110"), ("010", "011")):
                    self.line(v[a], v[b], style="dashed")
            for a, b in (
                ("000", "100"), ("100", "101"), ("101", "001"), ("001", "000"),
                ("100", "110"), ("110", "111"), ("111", "101"),
                ("001", "011"), ("011", "111"),
            ):
                self.line(v[a], v[b], style=style)
        else:
            # Math cabinet (+x forward-left, +y right, +z up): front x=1, right y=1, top z=1; hidden origin at 000
            if fill_front:
                self.fill_poly([v["100"], v["110"], v["111"], v["101"]], fill_front, fill_opacity)
            if fill_right:
                self.fill_poly([v["010"], v["110"], v["111"], v["011"]], fill_right, fill_opacity)
            if fill_top:
                self.fill_poly([v["001"], v["101"], v["111"], v["011"]], fill_top, fill_opacity)
            if hidden:
                for a, b in (("000", "100"), ("000", "010"), ("000", "001")):
                    self.line(v[a], v[b], style="dashed")
            for a, b in (
                ("100", "110"), ("110", "111"), ("111", "101"), ("101", "100"),
                ("010", "110"), ("010", "011"), ("011", "111"),
                ("001", "101"), ("001", "011"),
            ):
                self.line(v[a], v[b], style=style)
        return v

    def raw_svg(self, element_svg: str, world_bounds: Sequence[tuple[float, float]] = (), layer: str = "geom") -> None:
        """Append a raw SVG element string while registering world bounding points."""
        for pt in world_bounds:
            self.include_world_pt(pt, pad_px=2.0)
        (self._bg_elems if layer == "bg" else self._geom_elems).append(element_svg)

    def dim(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        offset_px: float,
        text: str = "",
        witness: bool = True,
        witness_gap_px: float = 3.0,
        witness_over_px: float = 4.5,
        dashed: bool = False,
        font_size: float = 12.5,
        text_along: bool = True,
        text_shift_px: float = 0.0,
        outside_arrows: bool | None = None,
        color: str | None = None,
    ) -> tuple[float, float]:
        (tx, ty), (nx, ny), length = unit_tangent_normal(p0, p1)
        sgn = 1.0 if offset_px >= 0 else -1.0
        off = offset_px / self.scale
        gap = (witness_gap_px / self.scale) * sgn
        over = (witness_over_px / self.scale) * sgn
        d0 = (p0[0] + nx * off, p0[1] + ny * off)
        d1 = (p1[0] + nx * off, p1[1] + ny * off)
        col = color or PAL["dim"]
        if witness and abs(offset_px) > 5.0:
            self.line((p0[0] + nx * gap, p0[1] + ny * gap), (d0[0] + nx * over, d0[1] + ny * over), style="guide", width=0.85)
            self.line((p1[0] + nx * gap, p1[1] + ny * gap), (d1[0] + nx * over, d1[1] + ny * over), style="guide", width=0.85)
        slen = length * self.scale
        _, approx_chars = format_rich_tspan(text) if text else ("", 0.0)
        ang_deg = math.degrees(math.atan2(ty, tx)) if text_along else 0.0
        if ang_deg > 90.0:
            ang_deg -= 180.0
        elif ang_deg <= -90.0:
            ang_deg += 180.0
        along_px = (approx_chars * font_size * 0.58 + 8.0) if (text and (text_along or abs(tx) > 0.7)) else ((font_size * 1.25 + 6.0) if text else 0.0)
        use_outside = (slen < max(28.0, along_px + 16.0)) if outside_arrows is None else outside_arrows
        st = "dim_dash" if dashed else "dim"
        mid = ((d0[0] + d1[0]) * 0.5, (d0[1] + d1[1]) * 0.5)
        if use_outside:
            ext = 14.0 / self.scale
            if not text or abs(text_shift_px) >= 8.0:
                self.line(d0, d1, style="dim", color=col, width=0.9)
            self.arrow((d0[0] - tx * ext, d0[1] - ty * ext), d0, style="dim", color=col, head_len=6.5, head_w=4.4)
            self.arrow((d1[0] + tx * ext, d1[1] + ty * ext), d1, style="dim", color=col, head_len=6.5, head_w=4.4)
        else:
            if text and abs(text_shift_px) < 8.0 and slen > along_px + 16.0:
                half_gap = (0.5 * along_px) / self.scale
                g0 = (mid[0] - tx * half_gap, mid[1] - ty * half_gap)
                g1 = (mid[0] + tx * half_gap, mid[1] + ty * half_gap)
                self.arrow(g0, d0, style=st, color=col, dash="5,3.5" if dashed else None, width=0.95, head_len=6.8, head_w=4.6)
                self.arrow(g1, d1, style=st, color=col, dash="5,3.5" if dashed else None, width=0.95, head_len=6.8, head_w=4.6)
            else:
                self.arrow(d0, d1, style=st, color=col, dash="5,3.5" if dashed else None, width=0.95, head_len=6.8, head_w=4.6, double=True)
        if text:
            perp_x, perp_y = -math.sin(math.radians(ang_deg)), math.cos(math.radians(ang_deg))
            tp = (mid[0] + perp_x * (text_shift_px / self.scale), mid[1] + perp_y * (text_shift_px / self.scale))
            self.label(tp, text, size=font_size, color=col if color else PAL["text"], anchor="middle", valign="middle", angle_deg=ang_deg, halo=True, halo_width=5.0)
        return mid

    # ------------------------------------------------------------------ stacked fraction & rich typography
    def frac(
        self,
        p: tuple[float, float],
        num: str,
        den: str,
        dx_px: float = 0.0,
        dy_px: float = 0.0,
        size: float = 12.0,
        color: str = PAL["text"],
        italic_num: bool = False,
        italic_den: bool = False,
    ) -> None:
        """Draw a crisp stacked mathematical fraction num / den centered at world p + (dx_px, dy_px)."""
        sx, sy = self.sxy(p)
        sx += dx_px
        sy += dy_px
        _, nw = format_rich_tspan(num)
        _, dw = format_rich_tspan(den)
        bw = max(nw, dw) * size * 0.56 + 6.0
        self._node_elems.append(
            f'<line x1="{sx - bw * 0.5:.2f}" y1="{sy:.2f}" x2="{sx + bw * 0.5:.2f}" y2="{sy:.2f}" '
            f'stroke="#ffffff" stroke-width="4.0" stroke-linecap="round"/>'
        )
        self._text_elems.append(
            f'<line x1="{sx - bw * 0.5:.2f}" y1="{sy:.2f}" x2="{sx + bw * 0.5:.2f}" y2="{sy:.2f}" '
            f'stroke="{color}" stroke-width="1.15" stroke-linecap="round"/>'
        )
        self.label(p, num, dx_px=dx_px, dy_px=dy_px - size * 0.66, size=size * 0.92, color=color, italic=italic_num, anchor="middle", valign="middle")
        self.label(p, den, dx_px=dx_px, dy_px=dy_px + size * 0.72, size=size * 0.92, color=color, italic=italic_den, anchor="middle", valign="middle")

    def label(
        self,
        p: tuple[float, float],
        text: str,
        dx_px: float = 0.0,
        dy_px: float = 0.0,
        size: float = 13.0,
        color: str = PAL["text"],
        anchor: str = "middle",
        valign: str = "middle",
        weight: str | int = 500,
        italic: bool = False,
        angle_deg: float = 0.0,
        halo: bool = True,
        halo_width: float = 4.2,
    ) -> None:
        """Place crisp SVG text at world p + screen pixel offset (dx_px right, dy_px down)."""
        if not text:
            return
        if "*" in text and "\n" in text:
            text = re.sub(
                r"\*([^*]+)\*",
                lambda m: "\n".join(f"*{ln}*" if ln else "" for ln in m.group(1).split("\n")),
                text,
            )
        sx, sy = self.sxy(p)
        sx += dx_px
        sy += dy_px

        lines = text.split("\n")
        line_h = size * 1.25
        total_h = line_h * len(lines)
        if valign == "middle":
            start_y = sy - total_h * 0.5 + size * 0.82
        elif valign == "bottom":
            start_y = sy - total_h + size * 0.88
        else:
            start_y = sy + (size * 0.88 if valign == "top" else 0.0)

        rot_attr = f' transform="rotate({-angle_deg:.2f} {sx:.2f} {sy:.2f})"' if abs(angle_deg) > 0.05 else ""
        max_w = 0.0
        has_over = False
        halo_elems: list[str] = []
        fill_elems: list[str] = []

        for idx, ln_txt in enumerate(lines):
            ly = start_y + idx * line_h
            segs = _tokenize_rich_text(ln_txt, default_italic=italic)
            if not segs:
                continue
            if len(segs) == 1 and segs[0][0] == "norm":
                _, s_txt, seg_it = segs[0]
                est_w = sum(_char_width_factor(c) for c in s_txt) * size + 6.0
                max_w = max(max_w, est_w)
                esc = html.escape(s_txt)
                it_attr = ' font-style="italic"' if seg_it else ""
                if halo:
                    halo_elems.append(
                        f'<text data-halo="1" x="{sx:.2f}" y="{ly:.2f}" font-family="{FONT_FAMILY}" '
                        f'font-size="{size:.1f}" font-weight="{weight}" fill="none" stroke="#ffffff" '
                        f'stroke-width="{halo_width:.1f}" stroke-linejoin="round" stroke-linecap="round" '
                        f'text-anchor="{anchor}"{it_attr}{rot_attr}>{esc}</text>'
                    )
                fill_elems.append(
                    f'<text x="{sx:.2f}" y="{ly:.2f}" font-family="{FONT_FAMILY}" font-size="{size:.1f}" '
                    f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{it_attr}{rot_attr}>{esc}</text>'
                )
            else:
                w_mult = 1.04 if (isinstance(weight, int) and weight >= 600) or str(weight) in ("bold", "600", "700") else 1.0
                seg_layout: list[tuple[str, str, bool, float, float, float, float]] = []
                total_w = 0.0
                for kind, s_txt, seg_it in segs:
                    if kind in ("vec", "bar", "tilde"):
                        has_over = True
                    seg_fs = size if kind in ("norm", "box", "vec", "bar", "tilde") else round(size * 0.75, 1)
                    seg_dy = 0.0 if kind in ("norm", "box", "vec", "bar", "tilde") else (size * 0.25 if kind == "sub" else -size * 0.30)
                    n_lead = len(s_txt) - len(s_txt.lstrip(" "))
                    n_trail = len(s_txt) - len(s_txt.rstrip(" "))
                    core = s_txt.strip(" ")
                    lead_w = n_lead * 0.36 * seg_fs
                    if not core:
                        seg_w = lead_w
                    else:
                        core_w = sum(_char_width_factor(c) for c in core) * seg_fs * w_mult + (1.2 if seg_it else 0.8)
                        seg_w = lead_w + core_w + n_trail * 0.38 * seg_fs
                    seg_layout.append((kind, core, seg_it, seg_fs, seg_dy, lead_w, seg_w))
                    total_w += seg_w
                max_w = max(max_w, total_w + 6.0)
                cur_x = sx - 0.5 * total_w if anchor == "middle" else (sx - total_w if anchor == "end" else sx)
                for kind, core, seg_it, seg_fs, seg_dy, lead_w, seg_w in seg_layout:
                    if not core:
                        cur_x += seg_w
                        continue
                    seg_x = cur_x + lead_w
                    seg_y = ly + seg_dy
                    if kind == "box":
                        bx, by, bsz = seg_x + 0.08 * seg_fs, seg_y - 0.64 * seg_fs, 0.54 * seg_fs
                        if halo:
                            halo_elems.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bsz:.2f}" height="{bsz:.2f}" fill="none" stroke="#ffffff" stroke-width="{halo_width:.1f}" stroke-linejoin="round"{rot_attr}/>')
                        fill_elems.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{bsz:.2f}" height="{bsz:.2f}" fill="none" stroke="{color}" stroke-width="1.15"{rot_attr}/>')
                        cur_x += seg_w
                        continue
                    esc = html.escape(core)
                    it_attr = ' font-style="italic"' if seg_it else ""
                    if halo:
                        halo_elems.append(
                            f'<text data-halo="1" x="{seg_x:.2f}" y="{seg_y:.2f}" font-family="{FONT_FAMILY}" '
                            f'font-size="{seg_fs:.1f}" font-weight="{weight}" fill="none" stroke="#ffffff" '
                            f'stroke-width="{halo_width:.1f}" stroke-linejoin="round" stroke-linecap="round" '
                            f'text-anchor="start"{it_attr}{rot_attr}>{esc}</text>'
                        )
                    fill_elems.append(
                        f'<text x="{seg_x:.2f}" y="{seg_y:.2f}" font-family="{FONT_FAMILY}" font-size="{seg_fs:.1f}" '
                        f'font-weight="{weight}" fill="{color}" text-anchor="start"{it_attr}{rot_attr}>{esc}</text>'
                    )
                    # Draw true SVG over-arrow, over-bar, or tilde centered above `core`
                    if kind in ("vec", "bar", "tilde"):
                        core_w_only = sum(_char_width_factor(c) for c in core) * seg_fs * w_mult
                        is_tall = any(c.isupper() or c in "bdfhklt" for c in core)
                        oy_top = seg_y - seg_fs * (0.86 if is_tall else 0.68)
                        ax0 = seg_x + (1.2 if seg_it else 0.3)
                        ax1 = seg_x + core_w_only + (1.8 if seg_it else 0.6)
                        if kind == "bar":
                            if halo:
                                halo_elems.append(f'<line x1="{ax0:.2f}" y1="{oy_top:.2f}" x2="{ax1:.2f}" y2="{oy_top:.2f}" stroke="#ffffff" stroke-width="3.2" stroke-linecap="round"{rot_attr}/>')
                            fill_elems.append(f'<line x1="{ax0:.2f}" y1="{oy_top:.2f}" x2="{ax1:.2f}" y2="{oy_top:.2f}" stroke="{color}" stroke-width="1.15" stroke-linecap="round"{rot_attr}/>')
                        elif kind == "vec":
                            tip_x = ax1 + 1.4
                            if halo:
                                halo_elems.append(f'<line x1="{ax0:.2f}" y1="{oy_top:.2f}" x2="{tip_x:.2f}" y2="{oy_top:.2f}" stroke="#ffffff" stroke-width="3.4" stroke-linecap="round"{rot_attr}/>')
                            fill_elems.append(f'<line x1="{ax0:.2f}" y1="{oy_top:.2f}" x2="{tip_x - 1.2:.2f}" y2="{oy_top:.2f}" stroke="{color}" stroke-width="1.10" stroke-linecap="round"{rot_attr}/>')
                            fill_elems.append(f'<polyline points="{tip_x - 3.3:.2f},{oy_top - 2.0:.2f} {tip_x:.2f},{oy_top:.2f} {tip_x - 3.3:.2f},{oy_top + 2.0:.2f}" fill="none" stroke="{color}" stroke-width="1.05" stroke-linecap="round" stroke-linejoin="round"{rot_attr}/>')
                        elif kind == "tilde":
                            mx = 0.5 * (ax0 + ax1)
                            pts_t = f"{ax0:.2f},{oy_top + 0.8:.2f} {0.5*(ax0+mx):.2f},{oy_top - 1.1:.2f} {mx:.2f},{oy_top:.2f} {0.5*(mx+ax1):.2f},{oy_top + 1.1:.2f} {ax1:.2f},{oy_top - 0.8:.2f}"
                            if halo:
                                halo_elems.append(f'<polyline points="{pts_t}" fill="none" stroke="#ffffff" stroke-width="3.0" stroke-linecap="round"{rot_attr}/>')
                            fill_elems.append(f'<polyline points="{pts_t}" fill="none" stroke="{color}" stroke-width="1.05" stroke-linecap="round"{rot_attr}/>')
                    cur_x += seg_w

        if anchor == "middle":
            lx0, lx1 = -max_w * 0.52, max_w * 0.52
        elif anchor == "end":
            lx0, lx1 = -max_w * 1.04, 4.0
        else:
            lx0, lx1 = -4.0, max_w * 1.04
        ly0 = (start_y - size * (1.28 if (has_over or "⌀" in text) else 0.96)) - sy
        ly1 = (start_y + (len(lines) - 1) * line_h + size * 0.35) - sy
        ang_screen = -math.radians(angle_deg)
        ca, sa = math.cos(ang_screen), math.sin(ang_screen)
        for bx in (lx0, lx1):
            for by in (ly0, ly1):
                self._include_screen_pt(sx + bx * ca - by * sa, sy + bx * sa + by * ca, 3.5)
        self._node_elems.extend(halo_elems)
        self._text_elems.extend(fill_elems)

    # ------------------------------------------------------------------ SVG & JSON Serialization
    def to_svg(self) -> str:
        if not self._bounds_pts:
            self._bounds_pts = [(0.0, 0.0), (200.0, 100.0)]
        xs = [p[0] for p in self._bounds_pts]
        ys = [p[1] for p in self._bounds_pts]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        raw_w = max(1.0, x_max - x_min)
        raw_h = max(1.0, y_max - y_min)
        pad = max(6.0, min(float(self.pad), 18.0))
        vx0 = round(x_min - pad, 2)
        vy0 = round(y_min - pad, 2)
        vw = round(raw_w + 2.0 * pad, 2)
        vh = round(raw_h + 2.0 * pad, 2)
        vx_s, vy_s, vw_s, vh_s = f"{vx0:g}", f"{vy0:g}", f"{vw:g}", f"{vh:g}"
        title_el = f"<title>{html.escape(self.title or self.name)}</title>"
        bg_rect = f'<rect x="{vx_s}" y="{vy_s}" width="{vw_s}" height="{vh_s}" fill="#ffffff"/>'
        body = "\n  ".join([title_el, bg_rect] + self._bg_elems + self._geom_elems + self._node_elems + self._text_elems)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx_s} {vy_s} {vw_s} {vh_s}" '
            f'width="{vw_s}" height="{vh_s}" role="img">\n  {body}\n</svg>\n'
        )

    def save(self, book_dir: Path | str) -> tuple[Path, Path]:
        root = Path(book_dir)
        svg_dir = root / "figures"
        cad_dir = root / "cad"
        svg_dir.mkdir(parents=True, exist_ok=True)
        cad_dir.mkdir(parents=True, exist_ok=True)
        svg_path = svg_dir / f"{self.name}.svg"
        svg_path.write_text(self.to_svg(), encoding="utf-8")
        cad_path = cad_dir / f"{self.name}.json"
        cad_path.write_text(
            json.dumps({"name": self.name, "title": self.title, "scale": self.scale, "elements": self._scene_items}, indent=2),
            encoding="utf-8",
        )
        return svg_path, cad_path
