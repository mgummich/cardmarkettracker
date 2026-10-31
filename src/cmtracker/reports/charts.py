"""Schlanke SVG-Liniendiagramme ohne externe Abhängigkeiten."""

from __future__ import annotations

from datetime import datetime
from html import escape

from ..formatting import eur

Series = list[tuple[datetime, float | None]]

SERIES_STYLE = {
    "Tiefstpreis (gefiltert)": ("var(--c1)", ""),
    "Preistrend": ("var(--c2)", "5 4"),
    "30-Tage-Ø": ("var(--c3)", "2 3"),
}


def line_chart(
    series: dict[str, Series],
    width: int = 640,
    height: int = 220,
    hover_series: str | None = None,
    reference_line: tuple[str, float] | None = None,
) -> str:
    """Liniendiagramm. ``hover_series`` erhält Punkte mit Tooltip, ``reference_line``
    zeichnet eine waagrechte Linie (z.B. Zielpreis)."""
    points = [(t, v) for s in series.values() for t, v in s if v is not None]
    if len(points) < 2:
        return '<p class="muted">Noch zu wenige Datenpunkte für ein Diagramm.</p>'

    pad_l, pad_r, pad_t, pad_b = 64, 12, 12, 28
    t_min = min(t for t, _ in points).timestamp()
    t_max = max(t for t, _ in points).timestamp()
    v_min = min(v for _, v in points)
    v_max = max(v for _, v in points)
    if reference_line:
        v_min = min(v_min, reference_line[1])
        v_max = max(v_max, reference_line[1])
    if v_max == v_min:
        v_min, v_max = v_min * 0.95, v_max * 1.05 or 1
    span_t = (t_max - t_min) or 1
    span_v = v_max - v_min
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def x(t: datetime) -> float:
        return pad_l + (t.timestamp() - t_min) / span_t * plot_w

    def y(v: float) -> float:
        return pad_t + (1 - (v - v_min) / span_v) * plot_h

    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="Preisverlauf">'
    ]
    for i in range(5):
        v = v_min + span_v * i / 4
        yy = y(v)
        parts.append(
            f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid"/>'
            f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" class="axis" text-anchor="end">'
            f"{escape(eur(v))}</text>"
        )
    start = min(t for t, _ in points)
    end = max(t for t, _ in points)
    parts.append(
        f'<text x="{pad_l}" y="{height - 8}" class="axis">{start:%d.%m.}</text>'
        f'<text x="{width - pad_r}" y="{height - 8}" class="axis" text-anchor="end">'
        f"{end:%d.%m.}</text>"
    )
    for name, data in series.items():
        pts = [(t, v) for t, v in data if v is not None]
        if not pts:
            continue
        color, dash = SERIES_STYLE.get(name, ("currentColor", ""))
        coords = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"'
            f' stroke-linejoin="round" stroke-linecap="round"{dash_attr}>'
            f"<title>{escape(name)}</title></polyline>"
        )
    if reference_line:
        label, value = reference_line
        yy = y(value)
        parts.append(
            f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" class="ref"/>'
            f'<text x="{width - pad_r - 4}" y="{yy - 5:.1f}" class="ref-label" text-anchor="end">'
            f"{escape(label)} {escape(eur(value))}</text>"
        )
    if hover_series and hover_series in series:
        for t, v in series[hover_series]:
            if v is None:
                continue
            parts.append(
                f'<circle cx="{x(t):.1f}" cy="{y(v):.1f}" r="5" class="pt">'
                f"<title>{t:%d.%m.%Y %H:%M} · {escape(eur(v))}</title></circle>"
            )
    parts.append("</svg>")
    return "".join(parts)


def sparkline(values: list[float | None], width: int = 120, height: int = 32) -> str:
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return '<span class="muted">–</span>'
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    step = (width - 4) / (len(pts) - 1)
    coords = [(2 + i * step, 2 + (1 - (v - lo) / span) * (height - 4)) for i, v in enumerate(pts)]
    trend = "down" if pts[-1] < pts[0] else ("up" if pts[-1] > pts[0] else "flat")
    line = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in coords)
    lx, ly = coords[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'class="spark spark-{trend}" aria-hidden="true">'
        f'<polyline points="{line}" fill="none" stroke-width="1.6"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2"/></svg>'
    )
