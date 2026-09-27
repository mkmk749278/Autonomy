"""Reusable on-screen elements: text, callouts, pills, chapter tags, icons."""
from __future__ import annotations

import numpy as np
from manim import (
    BOLD,
    DL,
    DOWN,
    LEFT,
    NORMAL,
    RIGHT,
    UL,
    UP,
    Dot,
    Line,
    RoundedRectangle,
    Text,
    VGroup,
    VMobject,
)

from . import style


def T(text, size=30, color=style.INK, bold=False, **kw):
    return Text(text, font=style.FONT, font_size=size, color=color,
                weight=BOLD if bold else NORMAL, **kw)


def callout(text, target, label_at, size=24, color=style.INK, line_color=style.MUSCLE_DARK):
    """Label at ``label_at`` with a leader line to ``target``.

    The line attaches to the side of the label facing the target.
    """
    target, label_at = np.asarray(target, float), np.asarray(label_at, float)
    label = T(text, size=size, color=color)
    label.move_to(label_at)
    side = RIGHT if target[0] > label_at[0] else LEFT
    anchor = label.get_edge_center(side) + side * 0.1
    line = Line(anchor, target, stroke_width=2.5, color=style.INK).set_opacity(0.75)
    dot = Dot(target, radius=0.055, color=style.INK)
    g = VGroup(line, dot, label)
    g.label, g.line, g.dot = label, line, dot
    return g


def pill(text, fill, size=22, text_color=style.BG, pad=0.18):
    t = T(text, size=size, color=text_color, bold=True)
    box = RoundedRectangle(corner_radius=(t.height + 2 * pad) / 2, width=t.width + 3 * pad,
                           height=t.height + 2 * pad, stroke_width=0).set_fill(fill, 1)
    return VGroup(box, t.move_to(box))


def panel(width, height, fill=style.PANEL, opacity=0.92):
    return RoundedRectangle(corner_radius=0.2, width=width, height=height, stroke_width=1.5,
                            stroke_color=style.MUTED, stroke_opacity=0.35).set_fill(fill, opacity)


def chapter_tag(number, title):
    """Small top-left marker so viewers always know where they are."""
    num = T(f"{number:02d}", size=20, color=style.ACCENT, bold=True)
    name = T(title.upper(), size=20, color=style.MUTED)
    g = VGroup(num, name).arrange(RIGHT, buff=0.2)
    g.to_corner(UL, buff=0.35)
    return g


def heart_icon(height=2.0, color=style.O2_RICH):
    t = np.linspace(0, 2 * np.pi, 200)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    pts = np.stack([x, y, np.zeros_like(x)], axis=1)
    m = VMobject().set_points_smoothly(list(pts))
    m.set_fill(color, 1).set_stroke(width=0)
    m.scale_to_fit_height(height)
    return m.move_to([0, 0, 0])


def bullet_list(items, size=30, icon_color=style.ACCENT, buff=0.35):
    rows = []
    for it in items:
        dot = Dot(radius=0.08, color=icon_color)
        rows.append(VGroup(dot, T(it, size=size)).arrange(RIGHT, buff=0.3))
    g = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=buff)
    return g


def rounded_path(points, radius=0.5):
    """Open polyline through ``points`` with each corner rounded off."""
    pts = [np.array([*p[:2], 0.0], dtype=float) for p in points]
    m = VMobject()
    m.start_new_path(pts[0])
    for prev, cur, nxt in zip(pts, pts[1:], pts[2:]):
        d_in = (cur - prev) / np.linalg.norm(cur - prev)
        d_out = (nxt - cur) / np.linalg.norm(nxt - cur)
        r = min(radius, np.linalg.norm(cur - prev) / 2, np.linalg.norm(nxt - cur) / 2)
        m.add_line_to(cur - d_in * r)
        m.add_quadratic_bezier_curve_to(cur, cur + d_out * r)
    m.add_line_to(pts[-1])
    return m
