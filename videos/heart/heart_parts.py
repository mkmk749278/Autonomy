"""Schematic four-chamber heart used by every heart scene.

Frontal-section view, drawn the way textbooks do: the heart's RIGHT side
appears on the viewer's LEFT. Coordinates are Manim scene units
(frame is 14.2 x 8, origin at centre) before the group is positioned.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    Circle,
    Dot,
    Line,
    Rectangle,
    RoundedRectangle,
    Text,
    ValueTracker,
    VGroup,
    VMobject,
    interpolate_color,
)

from studio import style


def P(x, y):
    return np.array([x, y, 0.0])


def smooth_closed(pts):
    pts = [P(*p) for p in pts]
    m = VMobject()
    m.set_points_smoothly(pts + [pts[0]])
    return m


def smooth_open(pts):
    m = VMobject()
    m.set_points_smoothly([P(*p) for p in pts])
    return m


def tube(pts, width, color, outline=style.MUSCLE_DARK):
    """A blood vessel: a thick stroked centre-line with a darker rim."""
    path = smooth_open(pts)
    rim = path.copy().set_stroke(outline, width=width * 100 + 10).set_fill(opacity=0)
    core = path.copy().set_stroke(color, width=width * 100).set_fill(opacity=0)
    g = VGroup(rim, core)
    g.path = path
    return g


def chamber_fill(color):
    return interpolate_color(color, style.BG, 0.45)


# ---------------------------------------------------------------- geometry
SILHOUETTE = [
    (-3.0, 1.3), (-2.6, 2.1), (-1.5, 2.25), (-0.6, 2.05), (0.5, 2.15), (1.7, 2.3),
    (2.75, 1.95), (3.1, 1.0), (2.95, -0.5), (2.35, -1.8), (1.35, -2.8), (0.55, -3.3),
    (-0.4, -2.95), (-1.6, -2.55), (-2.6, -1.55), (-2.95, -0.3),
]
RA = [(-2.75, 0.35), (-2.75, 1.3), (-2.3, 1.9), (-1.5, 2.0), (-0.95, 1.65), (-0.8, 0.9), (-0.95, 0.25), (-1.85, 0.1)]
RV = [(-2.5, -0.45), (-1.6, -0.35), (-0.5, -0.4), (-0.28, -0.95), (-0.35, -1.8), (-0.85, -2.4), (-1.65, -2.2), (-2.35, -1.4)]
LA = [(0.75, 0.4), (0.7, 1.25), (1.1, 1.85), (1.8, 2.0), (2.55, 1.65), (2.75, 0.95), (2.35, 0.35), (1.5, 0.22)]
LV = [(0.3, -0.45), (1.25, -0.3), (1.95, -0.45), (2.1, -1.2), (1.75, -2.0), (1.0, -2.6), (0.45, -2.5), (0.2, -1.6)]

CENTERS = {"ra": P(-1.8, 1.05), "rv": P(-1.3, -1.25), "la": P(1.75, 1.1), "lv": P(1.15, -1.35)}

VESSEL_W = 0.55
SVC_PTS = [(-2.15, 3.7), (-2.15, 2.6), (-2.1, 1.7)]
IVC_PTS = [(-3.35, -3.7), (-3.35, -1.0), (-3.1, 0.1), (-2.55, 0.6)]
PA_TRUNK = [(-0.5, -0.3), (-0.5, 0.8), (-0.45, 2.35)]
PA_LEFT = [(-0.45, 2.35), (-1.5, 2.6), (-3.8, 2.65)]   # to the right lung (viewer's left)
PA_RIGHT = [(-0.45, 2.35), (1.0, 2.55), (3.9, 2.55)]   # to the left lung (viewer's right)
AORTA = [(0.3, -0.3), (0.3, 1.2), (0.35, 2.9), (1.0, 3.5), (1.9, 3.45), (2.45, 2.9), (2.55, 2.2)]
AORTA_DESC = [(2.5, 2.6), (2.6, 1.0), (2.65, -1.0), (2.7, -3.9)]   # runs behind the heart
AORTA_BRANCHES = [
    [(0.75, 3.35), (0.65, 3.95)],
    [(1.35, 3.5), (1.35, 4.1)],
    [(1.9, 3.45), (2.05, 4.0)],
]
PV_UPPER = [(3.95, 1.45), (3.2, 1.4), (2.55, 1.3)]
PV_LOWER = [(3.95, 0.7), (3.2, 0.72), (2.55, 0.8)]


class Valve(VGroup):
    """Two leaflets hinged on either side of an opening.

    ``openness`` (0 = shut, 1 = wide open) drives the leaflet angle, so
    valves can be animated directly or from an updater. Hinges are tracked
    with invisible dots, so the valve keeps working after the heart is
    moved or scaled.
    """

    def __init__(self, left_hinge, right_hinge, flow_dir, name, **kw):
        super().__init__(**kw)
        self.flow = np.array([*flow_dir, 0.0]) / np.linalg.norm(flow_dir)
        self.name = name
        self.openness = ValueTracker(0.0)
        self.lh = Dot(P(*left_hinge), radius=0.01).set_opacity(0)
        self.rh = Dot(P(*right_hinge), radius=0.01).set_opacity(0)
        self.left_leaf = Line(ORIGIN, RIGHT, stroke_width=7, color=style.VALVE)
        self.right_leaf = Line(ORIGIN, RIGHT, stroke_width=7, color=style.VALVE)
        self.add(self.lh, self.rh, self.left_leaf, self.right_leaf)
        self.left_leaf.add_updater(lambda m: self._pose(m, self.lh, self.rh))
        self.right_leaf.add_updater(lambda m: self._pose(m, self.rh, self.lh))
        self._pose(self.left_leaf, self.lh, self.rh)
        self._pose(self.right_leaf, self.rh, self.lh)

    def _pose(self, leaf, hinge_dot, other_dot):
        hinge, other = hinge_dot.get_center(), other_dot.get_center()
        span = np.linalg.norm(other - hinge)
        o = float(np.clip(self.openness.get_value(), 0, 1))
        closed = (other - hinge) / span
        d = (1 - o) * closed + o * (self.flow * 0.95 + closed * 0.08)
        d /= np.linalg.norm(d)
        leaf.put_start_and_end_on(hinge, hinge + d * span * 0.51)

    @property
    def center_point(self):
        return (self.lh.get_center() + self.rh.get_center()) / 2


def _channel(lh, rh, depth_up, depth_down, color):
    """Blood-coloured gap through the wall where a valve sits."""
    lh, rh = P(*lh), P(*rh)
    w = np.linalg.norm(rh - lh)
    r = RoundedRectangle(corner_radius=0.12, width=w, height=depth_up + depth_down, stroke_width=0)
    r.set_fill(chamber_fill(color), 1)
    r.move_to((lh + rh) / 2 + UP * (depth_up - depth_down) / 2)
    return r


class HeartDiagram(VGroup):
    def __init__(self, **kw):
        super().__init__(**kw)
        blue, red = style.O2_POOR, style.O2_RICH

        # Vessels behind the muscle (IVC disappears into the heart).
        self.ivc = tube(IVC_PTS, VESSEL_W, chamber_fill(blue))
        self.aorta_desc = tube(AORTA_DESC, VESSEL_W * 0.9, chamber_fill(red))
        self.silhouette = smooth_closed(SILHOUETTE).set_fill(style.MUSCLE, 1).set_stroke(style.MUSCLE_DARK, 4)

        self.ra = smooth_closed(RA).set_fill(chamber_fill(blue), 1).set_stroke(width=0)
        self.rv = smooth_closed(RV).set_fill(chamber_fill(blue), 1).set_stroke(width=0)
        self.la = smooth_closed(LA).set_fill(chamber_fill(red), 1).set_stroke(width=0)
        self.lv = smooth_closed(LV).set_fill(chamber_fill(red), 1).set_stroke(width=0)
        self.chambers = VGroup(self.ra, self.rv, self.la, self.lv)

        self.tri_channel = _channel((-2.1, -0.15), (-1.2, -0.15), 0.35, 0.3, blue)
        self.mit_channel = _channel((0.85, -0.1), (1.75, -0.1), 0.35, 0.3, red)

        self.aorta = tube(AORTA, VESSEL_W, chamber_fill(red))
        self.aorta_branches = VGroup(*[tube(b, 0.22, chamber_fill(red)) for b in AORTA_BRANCHES])
        self.pa = VGroup(
            tube(PA_LEFT, 0.42, chamber_fill(blue)),
            tube(PA_RIGHT, 0.42, chamber_fill(blue)),
            tube(PA_TRUNK, VESSEL_W, chamber_fill(blue)),
        )
        self.pv = VGroup(tube(PV_UPPER, 0.32, chamber_fill(red)), tube(PV_LOWER, 0.32, chamber_fill(red)))
        self.svc = tube(SVC_PTS, VESSEL_W, chamber_fill(blue))

        self.tricuspid = Valve((-2.1, -0.15), (-1.2, -0.15), (0, -1), "Tricuspid valve")
        self.mitral = Valve((0.85, -0.1), (1.75, -0.1), (0, -1), "Mitral valve")
        self.pulmonary = Valve((-0.77, 0.05), (-0.23, 0.05), (0, 1), "Pulmonary valve")
        self.aortic = Valve((0.03, 0.05), (0.57, 0.05), (0, 1), "Aortic valve")
        self.valves = VGroup(self.tricuspid, self.mitral, self.pulmonary, self.aortic)

        self.add(
            self.ivc, self.aorta_desc, self.silhouette, self.chambers, self.tri_channel, self.mit_channel,
            self.pv, self.aorta_branches, self.aorta, self.pa, self.svc, self.valves,
        )

    # ------------------------------------------------------------ helpers
    def to_scene(self, p):
        """Map a design-space point (x, y) into the current scene position."""
        return self._origin() + P(*p) * self._scale()

    def _scale(self):
        return self.silhouette.width / self._design_w

    def _origin(self):
        return self.silhouette.get_center() - self._design_c * self._scale()

    def finalize(self):
        """Call once after construction, before moving/scaling the group."""
        self._design_w = self.silhouette.width
        self._design_c = self.silhouette.get_center().copy()
        return self

    def route(self, pts):
        m = smooth_open([tuple(self.to_scene(p)[:2]) for p in pts])
        return m


def build_heart():
    return HeartDiagram().finalize()


# Paths blood follows, in design space (see ``HeartDiagram.route``).
ROUTE_SVC_TO_RA = [(-2.15, 3.9), (-2.15, 2.6), (-2.0, 1.6), (-1.75, 1.05)]
ROUTE_IVC_TO_RA = [(-3.35, -3.9), (-3.35, -1.0), (-3.0, 0.2), (-2.3, 0.75), (-1.75, 1.05)]
ROUTE_RA_TO_RV = [(-1.75, 1.05), (-1.65, 0.3), (-1.65, -0.35), (-1.4, -1.2), (-1.1, -1.8)]
ROUTE_RV_TO_PA = [(-1.1, -1.8), (-0.65, -1.35), (-0.5, -0.5), (-0.5, 0.8), (-0.45, 2.3)]
ROUTE_PA_TO_LUNGS = [(-0.45, 2.3), (1.0, 2.55), (4.2, 2.55)]
ROUTE_PA_TO_LUNGS_L = [(-0.45, 2.3), (-1.5, 2.6), (-4.1, 2.65)]
ROUTE_PV_TO_LA = [(4.2, 1.45), (3.2, 1.4), (2.4, 1.3), (1.75, 1.1)]
ROUTE_LA_TO_LV = [(1.75, 1.1), (1.35, 0.4), (1.3, -0.3), (1.25, -1.2), (0.9, -1.9)]
ROUTE_LV_TO_AORTA = [(0.9, -1.9), (0.4, -1.3), (0.3, -0.3), (0.3, 1.2), (0.35, 2.9), (1.0, 3.5),
                     (1.9, 3.45), (2.45, 2.9), (2.55, 2.2)]
ROUTE_AORTA_UP = [(1.35, 3.5), (1.35, 4.3)]
