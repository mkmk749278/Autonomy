"""Particle streams that follow a path: used for blood, air and food."""
from __future__ import annotations

import numpy as np
from manim import Dot, ValueTracker, VGroup, VMobject


def sample_path(path: VMobject, n: int = 500) -> tuple[np.ndarray, float]:
    """Points spaced evenly by arc length, plus the path length."""
    raw = np.array([path.point_from_proportion(a) for a in np.linspace(0, 1, n * 3)])
    seg = np.linalg.norm(np.diff(raw, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    target = np.linspace(0, cum[-1], n)
    pts = np.stack([np.interp(target, cum, raw[:, k]) for k in range(3)], axis=1)
    return pts, float(cum[-1])


class Flow(VGroup):
    """``n`` dots travelling along ``path`` at ``speed`` units/second.

    ``rate`` is a ValueTracker multiplier (0 = frozen) so flow can pulse
    with the heartbeat. ``color_fn(alpha)`` recolours dots by how far along
    the path they are, e.g. blue before the lungs and red after.
    """

    def __init__(self, path, n=18, speed=1.2, radius=0.06, color=None, color_fn=None,
                 fade_ends=True, start=0.0, **kw):
        super().__init__(**kw)
        self.pts, self.length = sample_path(path)
        self.n, self.speed, self.color_fn, self.fade_ends = n, speed, color_fn, fade_ends
        self.offset = start
        self.rate = ValueTracker(1.0)
        self.jitter = np.random.default_rng(len(self.pts) + n).uniform(-0.35, 0.35, n) / n
        for _ in range(n):
            d = Dot(radius=radius, stroke_width=0)
            if color is not None:
                d.set_fill(color, 1)
            self.add(d)
        self._place()
        self.add_updater(lambda m, dt: m._advance(dt))

    def _advance(self, dt):
        self.offset = (self.offset + dt * self.speed * self.rate.get_value() / self.length) % 1.0
        self._place()

    def _place(self):
        last = len(self.pts) - 1
        for i, d in enumerate(self.submobjects):
            a = (self.offset + i / self.n + self.jitter[i]) % 1.0
            d.move_to(self.pts[int(a * last)])
            if self.color_fn is not None:
                d.set_fill(self.color_fn(a))
            if self.fade_ends:
                d.set_opacity(float(np.clip(min(a, 1 - a) / 0.06, 0, 1)))
