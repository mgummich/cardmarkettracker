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


def line_chart(series: dict[str, Series], width: int = 640, height: int = 220) -> str:
    points = [(t, v) for s in series.values() for t, v in s if v is not None]
    if len(points) < 2:
        return '<p class="muted">Noch zu wenige Datenpunkte für ein Diagramm.</p>'

    pad_l, pad_r, pad_t, pad_b = 64, 12, 12, 28
    t_min = min(t for t, _ in points).timestamp()
    t_max = max(t for t, _ in points).timestamp()
    v_min = min(v for _, v in points)
    v_max = max(v for _, v in points)
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
    parts.append("</svg>")
    return "".join(parts)
