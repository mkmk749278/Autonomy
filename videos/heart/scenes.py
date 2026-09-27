"""How the Heart Pumps Blood - a narrated animated explainer.

Render one chapter:   manim -ql videos/heart/scenes.py Anatomy
Render everything:    python build.py heart
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import *

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from heart_parts import (  # noqa: E402
    ROUTE_AORTA_UP, ROUTE_IVC_TO_RA, ROUTE_LA_TO_LV, ROUTE_LV_TO_AORTA, ROUTE_PA_TO_LUNGS,
    ROUTE_PA_TO_LUNGS_L, ROUTE_PV_TO_LA, ROUTE_RA_TO_RV, ROUTE_RV_TO_PA, ROUTE_SVC_TO_RA,
    build_heart, smooth_closed, tube,
)
from studio import sfx, style  # noqa: E402
from studio.flow import Flow  # noqa: E402
from studio.narrated import NarratedScene  # noqa: E402
from studio.ui import T, bullet_list, callout, chapter_tag, heart_icon, panel, pill, rounded_path  # noqa: E402

BLUE, RED = style.O2_POOR, style.O2_RICH


def placed_heart(scale=0.8, shift=UP * 0.35):
    h = build_heart()
    h.scale(scale, scale_stroke=True).shift(shift)
    return h


def lerp_color(a):
    return interpolate_color(BLUE, RED, a)


# --------------------------------------------------------------- cardiac cycle model
# One beat is phase 0..1. Proportions are stretched for teaching; order is exact.
#   0.00-0.40 diastole, passive filling (AV valves open)
#   0.40-0.55 atrial systole ("atrial kick")
#   0.55      AV valves shut  -> S1 "lub"
#   0.60-0.90 ventricular ejection (semilunar valves open)
#   0.90      semilunar valves shut -> S2 "dub"
PH_ATRIAL, PH_LUB, PH_EJECT, PH_DUB = 0.40, 0.55, 0.60, 0.90


def _ramp(x, a, b):
    return float(np.clip((x - a) / (b - a), 0, 1))


def ventricle_scale(p):
    p %= 1
    if p < PH_ATRIAL:
        return 0.86 + 0.10 * _ramp(p, 0.0, PH_ATRIAL) ** 0.6
    if p < PH_LUB:
        return 0.96 + 0.04 * _ramp(p, PH_ATRIAL, PH_LUB)
    if p < PH_EJECT:
        return 1.0
    if p < PH_DUB:
        return 1.0 - 0.14 * np.sin(_ramp(p, PH_EJECT, PH_DUB) * np.pi / 2)
    return 0.86


def atrium_scale(p):
    p %= 1
    if p < PH_ATRIAL:
        return 1.0 - 0.02 * _ramp(p, 0, PH_ATRIAL)
    if p < PH_LUB:
        return 0.98 - 0.12 * np.sin(_ramp(p, PH_ATRIAL, PH_LUB) * np.pi / 2)
    return 0.86 + 0.14 * _ramp(p, PH_LUB, 1.0)


def av_open(p):
    p %= 1
    return min(_ramp(p, 0.0, 0.04), 1 - _ramp(p, PH_LUB - 0.01, PH_LUB + 0.01))


def sl_open(p):
    p %= 1
    return min(_ramp(p, PH_EJECT - 0.01, PH_EJECT + 0.03), 1 - _ramp(p, PH_DUB - 0.015, PH_DUB + 0.005))


def ecg(p):
    p %= 1
    g = lambda c, w, a: a * np.exp(-((p - c) / w) ** 2)
    return (g(0.37, 0.022, 0.16) + g(0.505, 0.006, -0.10) + g(0.52, 0.008, 1.0)
            + g(0.535, 0.007, -0.24) + g(0.78, 0.035, 0.30))


def phase_name(p):
    p %= 1
    if p < PH_ATRIAL:
        return "Diastole: ventricles fill"
    if p < PH_LUB:
        return "Atrial systole: atria squeeze"
    if p < PH_EJECT:
        return "Ventricular systole begins"
    if p < PH_DUB:
        return "Ventricular systole: ejection"
    return "Relaxation"


def attach_cycle(scene, heart, beat):
    """Drive chamber size and valves from the ``beat`` ValueTracker."""
    for name, fn in [("ra", atrium_scale), ("la", atrium_scale), ("rv", ventricle_scale), ("lv", ventricle_scale)]:
        ch = getattr(heart, name)
        ref = ch.copy()
        c = ref.get_center()
        ch.add_updater(lambda m, ref=ref, c=c, fn=fn: m.become(ref.copy().scale(fn(beat.get_value()), about_point=c)))
    for v in (heart.tricuspid, heart.mitral):
        v.openness.add_updater(lambda m: m.set_value(av_open(beat.get_value())))
    for v in (heart.pulmonary, heart.aortic):
        v.openness.add_updater(lambda m: m.set_value(sl_open(beat.get_value())))
    scene.add(heart.tricuspid.openness, heart.mitral.openness, heart.pulmonary.openness, heart.aortic.openness)


def detach_cycle(heart):
    for m in [heart.ra, heart.la, heart.rv, heart.lv]:
        m.clear_updaters()
    for v in heart.valves:
        v.openness.clear_updaters()


# ======================================================================= scenes
class Intro(NarratedScene):
    def construct(self):
        icon = heart_icon(2.2).shift(UP * 1.3)
        t0 = self.renderer.time
        icon.add_updater(lambda m: m.set_height(
            2.2 * (1 + 0.08 * max(0, np.sin((self.renderer.time - t0) * 2 * np.pi * 1.1)) ** 6)))
        title = T("How the Heart Pumps Blood", size=60, bold=True).next_to(icon, DOWN, buff=0.55)
        sub = T("An animated guide to the circulatory system", size=30, color=style.MUTED).next_to(title, DOWN, buff=0.3)
        with self.voice("Every minute, your heart pumps about five litres of blood: "
                        "roughly all the blood in your body.") as v:
            self.play(GrowFromCenter(icon), run_time=1.2)
            self.play(Write(title), FadeIn(sub, shift=UP * 0.2), run_time=2)
            stat = pill("≈ 5 litres every minute", RED, size=26, text_color=style.INK).next_to(sub, DOWN, buff=0.5)
            self.play(FadeIn(stat, scale=0.8))
        with self.voice("Let's see how this fist-sized muscle does it, one step at a time."):
            pass
        icon.clear_updaters()
        self.play(FadeOut(VGroup(title, sub, stat)), icon.animate.set_height(1.3).move_to(UP * 2.75), run_time=0.8)
        chapters = ["Two pumps in one", "Inside the heart", "The path of blood", "One heartbeat",
                    "The electrical spark"]
        rows = VGroup(*[VGroup(T(f"{i + 1:02d}", size=28, bold=True, color=style.ACCENT), T(c, size=30))
                        .arrange(RIGHT, buff=0.35) for i, c in enumerate(chapters)])
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.26).move_to(UP * 0.1)
        with self.voice("We'll look at the heart's two pumps, its chambers and valves, the path that blood takes, "
                        "what happens in a single beat, and the electrical spark that starts it all."):
            self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.3) for r in rows], lag_ratio=0.5), run_time=4)
        self.play(FadeOut(VGroup(icon, rows)), run_time=0.8)


class TwoPumps(NarratedScene):
    """The double circulation: lungs loop on top, body loop below."""

    def construct(self):
        self.add(chapter_tag(1, "Two pumps in one"))
        # Heart in the middle, split into its two sides.
        left_half = RoundedRectangle(corner_radius=0.3, width=1.5, height=1.9).set_fill(interpolate_color(BLUE, style.BG, 0.3), 1).set_stroke(BLUE, 3)
        right_half = RoundedRectangle(corner_radius=0.3, width=1.5, height=1.9).set_fill(interpolate_color(RED, style.BG, 0.3), 1).set_stroke(RED, 3)
        halves = VGroup(left_half, right_half).arrange(RIGHT, buff=0.12).move_to(UP * 0.1)
        lt = T("Right\nside", size=24, bold=True).move_to(left_half)
        rt = T("Left\nside", size=24, bold=True).move_to(right_half)
        heart = VGroup(halves, lt, rt)

        # Loops (clockwise): pulmonary above the heart, systemic below.
        y_top, y_bot, y_hi, y_lo = 2.75, -2.45, 0.65, -0.45
        pul = rounded_path([(-0.8, y_hi), (-2.7, y_hi), (-2.7, y_top), (2.7, y_top), (2.7, y_hi), (0.8, y_hi)])
        sysm = rounded_path([(0.8, y_lo), (3.9, y_lo), (3.9, y_bot), (-3.9, y_bot), (-3.9, y_lo), (-0.8, y_lo)])
        pul_tube = pul.copy().set_stroke(style.PANEL, 22)
        sys_tube = sysm.copy().set_stroke(style.PANEL, 22)

        lungs = VGroup(
            smooth_closed([(-1.9, 2.3), (-1.7, 3.35), (-0.95, 3.6), (-0.35, 3.2), (-0.3, 2.3), (-1.0, 2.05)]),
            smooth_closed([(1.9, 2.3), (1.7, 3.35), (0.95, 3.6), (0.35, 3.2), (0.3, 2.3), (1.0, 2.05)]),
        ).set_fill(style.LUNG, 0.85).set_stroke(interpolate_color(style.LUNG, WHITE, 0.3), 2)
        lung_lbl = T("Lungs", size=26, bold=True, color=style.BG).move_to(lungs[1]).shift(UP * 0.3 + RIGHT * 0.05)
        body = RoundedRectangle(corner_radius=0.35, width=5.2, height=0.9).set_fill(style.PANEL, 1).set_stroke(style.MUTED, 2)
        body.move_to([0, y_bot, 0])
        body_lbl = T("Body: brain, muscles, organs", size=24).move_to(body)

        # Blue until the lungs (half-way round), then red. Opposite for the body loop.
        for m, z in [(pul_tube, 0), (sys_tube, 0), (lungs, 2), (lung_lbl, 3), (body, 2), (body_lbl, 3), (heart, 4)]:
            m.set_z_index(z)
        pul_flow = Flow(pul, n=26, speed=1.4, radius=0.07,
                        color_fn=lambda a: lerp_color(np.clip((a - 0.44) / 0.12, 0, 1)))
        sys_flow = Flow(sysm, n=34, speed=1.4, radius=0.07,
                        color_fn=lambda a: lerp_color(1 - np.clip((a - 0.44) / 0.12, 0, 1)))
        pul_flow.set_z_index(1)
        sys_flow.set_z_index(1)

        with self.voice("The heart is really two pumps, side by side.") as v:
            self.play(FadeIn(heart, scale=0.9), run_time=1)
            self.play(Indicate(left_half, color=BLUE), Indicate(right_half, color=RED), run_time=1.2)

        with self.voice("The right side receives oxygen-poor blood returning from the body, "
                        "and pumps it to the lungs.") as v:
            self.add(pul_tube, heart)
            self.play(Create(pul_tube), FadeIn(lungs), FadeIn(lung_lbl), run_time=2)
            self.add(pul_flow)
            self.play(FadeIn(pul_flow), run_time=0.6)

        co2 = T("CO₂ out", size=24, color=style.MUTED).next_to(lungs, LEFT, buff=0.35).shift(UP * 0.2)
        o2 = T("O₂ in", size=24, color=style.AIR).next_to(lungs, RIGHT, buff=0.35).shift(UP * 0.2)
        with self.voice("In the lungs, blood drops off carbon dioxide and picks up fresh oxygen."):
            self.play(FadeIn(co2, shift=LEFT * 0.3), FadeIn(o2, shift=LEFT * 0.3), run_time=1)
            self.play(Indicate(lungs, scale_factor=1.06, color=style.LUNG), run_time=1.2)

        with self.voice("The left side receives this oxygen-rich blood, and pumps it out "
                        "to every organ and muscle in the body."):
            self.add(sys_tube, pul_tube, heart, pul_flow)
            self.play(Create(sys_tube), FadeIn(body), FadeIn(body_lbl), run_time=2)
            self.add(sys_flow)
            self.play(FadeIn(sys_flow), run_time=0.6)

        used = T("cells use O₂", size=22, color=style.MUTED).move_to([5.25, -2.45, 0])
        with self.voice("There, cells use up the oxygen, and the blood returns to the right side, "
                        "to start the loop again."):
            self.play(FadeIn(used), Indicate(body, color=style.MUTED), run_time=1.2)

        pul_name = T("Pulmonary circulation", size=24, color=style.LUNG).move_to([0, 1.45, 0])
        sys_name = T("Systemic circulation", size=24, color=style.ACCENT).move_to([0, -1.4, 0])
        with self.voice("This is called the double circulation: a short loop through the lungs, "
                        "and a long loop through the whole body."):
            self.play(Write(pul_name), run_time=1.2)
            self.play(Write(sys_name), run_time=1.2)

        legend = VGroup(
            VGroup(Dot(color=RED, radius=0.09), T("oxygen-rich", size=22)).arrange(RIGHT, buff=0.15),
            VGroup(Dot(color=BLUE, radius=0.09), T("oxygen-poor", size=22)).arrange(RIGHT, buff=0.15),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        legend_box = panel(legend.width + 0.5, legend.height + 0.4).move_to(legend)
        legend = VGroup(legend_box, legend).to_corner(UR, buff=0.35)
        with self.voice("By the way, blood is always red. Diagrams colour oxygen-poor blood blue, "
                        "simply to tell the two apart."):
            self.play(FadeIn(legend, shift=LEFT * 0.3))
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)


class Anatomy(NarratedScene):
    def construct(self):
        self.add(chapter_tag(2, "Inside the heart"))
        h = placed_heart()
        S = h.to_scene
        with self.voice("Inside, the heart has four chambers."):
            self.play(FadeIn(VGroup(h.ivc, h.aorta_desc)), DrawBorderThenFill(h.silhouette), run_time=1.4)
            self.play(LaggedStart(*[FadeIn(c, scale=0.9) for c in h.chambers], lag_ratio=0.25), run_time=1.2)
        self.play(FadeIn(VGroup(h.tri_channel, h.mit_channel, h.pv, h.aorta_branches, h.aorta, h.pa, h.svc, h.valves)),
                  run_time=0.8)
        self.add(h)

        ra = callout("Right atrium", S((-1.9, 1.2)), [-5.3, 1.6, 0])
        la = callout("Left atrium", S((1.9, 1.3)), [5.4, 1.1, 0])
        rv = callout("Right ventricle", S((-1.4, -1.4)), [-5.3, -1.2, 0])
        lv = callout("Left ventricle", S((1.3, -1.5)), [5.4, -1.3, 0])
        with self.voice("The two upper chambers, the atria, are receiving rooms, where blood arrives."):
            self.play(Indicate(h.ra, color=BLUE), Indicate(h.la, color=RED), FadeIn(ra), FadeIn(la), run_time=1.5)
        with self.voice("The two lower chambers, the ventricles, are the pumps that push blood out."):
            self.play(Indicate(h.rv, color=BLUE), Indicate(h.lv, color=RED), FadeIn(rv), FadeIn(lv), run_time=1.5)

        septum_line = Line(S((-0.03, -0.45)), S((0.2, -2.55)), stroke_width=10, color=style.ACCENT)
        sep = callout("Septum", S((0.1, -2.0)), [1.6, -2.75, 0])
        with self.voice("A muscular wall called the septum divides the two sides, "
                        "so oxygen-rich and oxygen-poor blood never mix."):
            self.play(Create(septum_line), FadeIn(sep), run_time=1.2)
            self.play(septum_line.animate.set_opacity(0), run_time=1)

        r_tag = pill("heart's RIGHT side", BLUE, size=20, text_color=style.INK).move_to([-5.0, 2.75, 0])
        l_tag = pill("heart's LEFT side", RED, size=20, text_color=style.INK).move_to([5.0, 2.75, 0])
        with self.voice("Notice that in diagrams like this, the heart's right side appears on your left, "
                        "as if you were facing the person."):
            self.play(FadeIn(r_tag, shift=DOWN * 0.2), FadeIn(l_tag, shift=DOWN * 0.2))

        # Swap long chamber names for compact abbreviations inside the chambers.
        abbrs = VGroup(*[T(s, size=26, bold=True).move_to(S(p)) for s, p in
                         [("RA", (-1.85, 1.15)), ("LA", (1.85, 1.15)), ("RV", (-1.35, -1.35)), ("LV", (1.2, -1.5))]])
        self.play(FadeOut(VGroup(ra, la, rv, lv, sep)), FadeIn(abbrs), run_time=0.8)

        tri = callout("Tricuspid valve", h.tricuspid.center_point, [-5.3, -0.1, 0])
        pul = callout("Pulmonary valve", h.pulmonary.center_point, [-5.3, 0.75, 0])
        mit = callout("Mitral valve", h.mitral.center_point, [5.4, -0.2, 0])
        aor = callout("Aortic valve", h.aortic.center_point, [5.4, 0.6, 0])
        self.add(*[v.openness for v in h.valves])
        with self.voice("Four one-way valves keep blood moving forward. "
                        "The tricuspid and mitral valves sit between the atria and the ventricles."):
            self.play(FadeIn(tri), FadeIn(mit), run_time=1)
            for _ in range(2):
                self.play(h.tricuspid.openness.animate.set_value(1), h.mitral.openness.animate.set_value(1), run_time=0.5)
                self.play(h.tricuspid.openness.animate.set_value(0), h.mitral.openness.animate.set_value(0), run_time=0.4)
        with self.voice("The pulmonary and aortic valves guard the exits."):
            self.play(FadeIn(pul), FadeIn(aor), run_time=1)
            self.play(h.pulmonary.openness.animate.set_value(1), h.aortic.openness.animate.set_value(1), run_time=0.5)
            self.play(h.pulmonary.openness.animate.set_value(0), h.aortic.openness.animate.set_value(0), run_time=0.4)

        self.play(FadeOut(VGroup(tri, pul, mit, aor)), run_time=0.6)
        lv_wall = VGroup(
            Line(S((2.1, -1.2)), S((2.98, -1.2)), stroke_width=6, color=style.ACCENT),
            Line(S((-2.5, -1.2)), S((-2.83, -1.2)), stroke_width=6, color=style.ACCENT),
        )
        hi = callout("≈120 mmHg", S((1.3, -1.9)), [5.4, -2.3, 0], color=style.ACCENT)
        lo = callout("≈25 mmHg", S((-1.2, -1.9)), [-5.3, -2.3, 0], color=style.ACCENT)
        with self.voice("And the left ventricle has the thickest wall of all, because it pushes blood "
                        "around the entire body, at about five times the pressure of the right side."):
            self.play(Create(lv_wall), run_time=1)
            self.play(FadeIn(hi), FadeIn(lo), run_time=1)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)


class Journey(NarratedScene):
    """Follow one drop of blood all the way round."""

    def construct(self):
        self.add(chapter_tag(3, "The path of blood"))
        h = placed_heart()
        S = h.to_scene
        abbrs = VGroup(*[T(s, size=24, bold=True).set_opacity(0.8).move_to(S(p)) for s, p in
                         [("RA", (-1.85, 1.2)), ("LA", (1.95, 1.3)), ("RV", (-1.6, -1.1)), ("LV", (1.45, -1.25))]])
        self.add(h, abbrs, *[v.openness for v in h.valves])

        lung = smooth_closed([(0, -1.2), (-0.6, -0.6), (-0.7, 0.6), (-0.2, 1.4), (0.5, 1.5), (1.2, 0.8), (1.2, -1.0)])
        lung.set_fill(style.LUNG, 0.9).set_stroke(width=0).move_to([6.9, 1.75, 0])
        lung_lbl = T("Lungs", size=24, bold=True, color=style.LUNG).move_to([6.45, 0.05, 0])

        def scene_tube(pts, w, color):
            return tube([tuple(S(p)[:2]) for p in pts], w * 0.8, interpolate_color(color, style.BG, 0.45))

        ext = VGroup(scene_tube([(3.7, 2.55), (7.8, 2.5)], 0.42, BLUE),
                     scene_tube([(7.8, 1.4), (3.7, 1.45)], 0.32, RED))
        self.add(ext)
        self.bring_to_back(ext)
        pa_to_lung = ROUTE_PA_TO_LUNGS[:-1] + [(7.8, 2.5)]
        pv_from_lung = [(7.8, 1.4)] + ROUTE_PV_TO_LA[1:]
        drop = Dot(radius=0.13, color=BLUE).set_z_index(10)
        glow = Dot(radius=0.26, color=BLUE).set_opacity(0.3).set_z_index(9)
        glow.add_updater(lambda m: m.move_to(drop).set_color(drop.get_color()))
        ghost = Dot(radius=0.11, color=BLUE).set_opacity(0.8).set_z_index(10)

        def go(route, t, **kw):
            return MoveAlongPath(drop, h.route(route), run_time=t, rate_func=kw.get("rate_func", smooth))

        with self.voice("Let's follow a single drop of blood."):
            drop.move_to(S(ROUTE_SVC_TO_RA[0]))
            ghost.move_to(S(ROUTE_IVC_TO_RA[0]))
            self.add(glow, drop, ghost)
            self.play(FadeIn(drop, scale=2), FadeIn(ghost, scale=2), FadeIn(lung), FadeIn(lung_lbl))

        svc = callout("Superior vena cava", S((-2.15, 3.0)), [-5.2, 3.1, 0])
        ivc = callout("Inferior vena cava", S((-3.35, -2.3)), [-5.6, -1.8, 0])
        with self.voice("Oxygen-poor blood returns from the body through two large veins, "
                        "the superior and inferior vena cava, and enters the right atrium.") as v:
            self.play(FadeIn(svc), FadeIn(ivc), run_time=1)
            self.play(go(ROUTE_SVC_TO_RA, v.left() * 0.8),
                      MoveAlongPath(ghost, h.route(ROUTE_IVC_TO_RA), run_time=v.left() * 0.8), run_time=v.left() * 0.8)
            self.play(Indicate(h.ra, color=BLUE), FadeOut(ghost))

        with self.voice("It passes through the tricuspid valve into the right ventricle.") as v:
            self.play(FadeOut(VGroup(svc, ivc)), h.tricuspid.openness.animate.set_value(1), run_time=0.5)
            self.play(go(ROUTE_RA_TO_RV, v.left() - 0.6))
            self.play(h.tricuspid.openness.animate.set_value(0), run_time=0.4)

        pa = callout("Pulmonary artery", S((-0.5, 1.2)), [-5.3, 1.8, 0])
        with self.voice("The right ventricle contracts, pushing it through the pulmonary valve, "
                        "into the pulmonary artery, and on to the lungs.") as v:
            self.play(h.rv.animate.scale(0.9), h.pulmonary.openness.animate.set_value(1), FadeIn(pa), run_time=0.6)
            self.play(go(ROUTE_RV_TO_PA, v.left() * 0.45),
                      h.rv.animate.scale(1 / 0.9), run_time=v.left() * 0.45)
            self.play(h.pulmonary.openness.animate.set_value(0), go(pa_to_lung, v.left(), rate_func=rush_into))

        o2 = VGroup(*[T("O₂", size=22, color=style.AIR).move_to(lung.get_center() + np.array([np.cos(a), np.sin(a), 0]) * 1.4 + LEFT * 0.4)
                      for a in np.linspace(2.2, 4.1, 4)])
        with self.voice("In the lungs, it drops off carbon dioxide and picks up oxygen, "
                        "turning oxygen-rich."):
            self.play(FadeOut(pa), LaggedStart(*[FadeIn(o, shift=RIGHT * 0.4) for o in o2], lag_ratio=0.2), run_time=1.2)
            drop.move_to(S(pv_from_lung[0])).set_color(RED)
            self.play(Indicate(lung, color=style.LUNG, scale_factor=1.05), FadeOut(o2), run_time=1)

        pv = callout("Pulmonary veins", S((3.3, 0.72)), [4.3, -0.55, 0])
        with self.voice("It returns through the pulmonary veins into the left atrium.") as v:
            self.play(FadeIn(pv), run_time=0.6)
            self.play(go(pv_from_lung, v.left(), rate_func=smooth))

        with self.voice("Then through the mitral valve, into the left ventricle.") as v:
            self.play(FadeOut(pv), h.mitral.openness.animate.set_value(1), run_time=0.5)
            self.play(go(ROUTE_LA_TO_LV, v.left() - 0.5))
            self.play(h.mitral.openness.animate.set_value(0), run_time=0.4)

        aorta = callout("Aorta", S((1.2, 3.5)), [4.3, 3.45, 0])
        with self.voice("Finally, the powerful left ventricle squeezes it through the aortic valve "
                        "into the aorta, the body's largest artery, which carries it to the whole body.") as v:
            self.play(h.lv.animate.scale(0.9), h.aortic.openness.animate.set_value(1), FadeIn(aorta), run_time=0.7)
            self.play(go(ROUTE_LV_TO_AORTA, v.left() * 0.6), h.lv.animate.scale(1 / 0.9), run_time=v.left() * 0.6)
            self.play(h.aortic.openness.animate.set_value(0), FadeOut(drop), FadeOut(glow), run_time=0.5)

        # Now everything at once.
        routes = [
            (ROUTE_SVC_TO_RA, BLUE, 6), (ROUTE_IVC_TO_RA, BLUE, 8), (ROUTE_RA_TO_RV, BLUE, 5),
            (ROUTE_RV_TO_PA, BLUE, 6), (pa_to_lung, BLUE, 9), (ROUTE_PA_TO_LUNGS_L, BLUE, 5),
            (pv_from_lung, RED, 8), (ROUTE_LA_TO_LV, RED, 5), (ROUTE_LV_TO_AORTA, RED, 12), (ROUTE_AORTA_UP, RED, 2),
        ]
        flows = VGroup(*[Flow(h.route(r), n=n, speed=1.6, radius=0.055, color=c, start=0.13 * i)
                         for i, (r, c, n) in enumerate(routes)])
        for f in flows:
            f.set_z_index(5)
        for v in h.valves:
            v.openness.set_value(1)
        with self.voice("Both sides do this at the same time, with every single beat."):
            self.play(FadeOut(aorta), FadeIn(flows), run_time=1)
        self.wait(1.5)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)


class Cycle(NarratedScene):
    """The cardiac cycle: timing of contraction and valves, with lub-dub."""

    def construct(self):
        self.add(chapter_tag(4, "One heartbeat"))
        h = placed_heart(scale=0.68, shift=LEFT * 3.1 + UP * 0.2)
        self.add(h)
        beat = ValueTracker(0.0)
        attach_cycle(self, h, beat)

        box = panel(6.2, 5.6).move_to([3.55, 0.15, 0])
        head = T("Cardiac cycle", size=30, bold=True).move_to(box.get_top() + DOWN * 0.45)
        phase_txt = always_redraw(lambda: T(phase_name(beat.get_value()), size=26, color=style.ACCENT)
                                  .move_to(box.get_top() + DOWN * 1.05))

        def status_row(label, fn, y):
            name = T(label, size=22, color=style.INK).move_to([1.2, y, 0], aligned_edge=LEFT)
            state = always_redraw(lambda: pill("OPEN" if fn(beat.get_value()) > 0.5 else "SHUT",
                                               "#2a9d8f" if fn(beat.get_value()) > 0.5 else "#6c757d",
                                               size=18, text_color=style.INK).move_to([5.8, y, 0]))
            return VGroup(name, state)

        av_row = status_row("Tricuspid + mitral", av_open, 0.95)
        sl_row = status_row("Pulmonary + aortic", sl_open, 0.35)

        # ECG strip: one beat drawn left to right as the phase advances.
        x0, x1, y_base, amp = 1.0, 6.1, -1.55, 0.95
        axis = Line([x0, y_base, 0], [x1, y_base, 0], stroke_width=1.5, color=style.MUTED).set_opacity(0.4)

        def trace():
            p = beat.get_value()
            frac = p % 1 if p < 50 else 1
            xs = np.linspace(0, max(frac, 1e-3), max(2, int(400 * frac)))
            pts = [[x0 + (x1 - x0) * s, y_base + amp * ecg(s), 0] for s in xs]
            m = VMobject(stroke_color="#7CFC9A", stroke_width=3.5).set_points_as_corners(pts)
            return m

        ecg_trace = always_redraw(trace)
        ecg_lbl = T("ECG", size=20, color="#7CFC9A").move_to([x0 + 0.25, y_base + 1.05, 0])

        with self.voice("Each heartbeat is a precisely timed sequence, called the cardiac cycle."):
            self.play(FadeIn(box), Write(head), run_time=1)
            self.add(phase_txt)
            self.play(FadeIn(av_row), FadeIn(sl_row), FadeIn(axis), FadeIn(ecg_lbl), run_time=1)
            self.add(ecg_trace)

        arrows_fill = VGroup(
            Arrow(h.to_scene((-1.7, 0.7)), h.to_scene((-1.55, -0.9)), color=BLUE, buff=0, stroke_width=6),
            Arrow(h.to_scene((1.4, 0.7)), h.to_scene((1.3, -0.9)), color=RED, buff=0, stroke_width=6),
        )
        with self.voice("First, while the heart relaxes, a phase called diastole, blood flows into the atria, "
                        "and straight on through the open valves into the ventricles.") as v:
            self.play(FadeIn(arrows_fill), run_time=0.5)
            self.play(beat.animate.set_value(PH_ATRIAL), run_time=v.left(), rate_func=linear)

        with self.voice("Next, the atria contract, topping up the ventricles with a final push.") as v:
            self.play(beat.animate.set_value(PH_LUB - 0.012), run_time=v.left(), rate_func=linear)

        lub_txt = T("LUB", size=64, bold=True, color=style.ACCENT).move_to(h.get_center() + DOWN * 0.3)
        dub_txt = T("DUB", size=64, bold=True, color=style.ACCENT).move_to(h.get_center() + DOWN * 0.3)
        with self.voice("Then the ventricles contract. This is systole. The rising pressure snaps the "
                        "tricuspid and mitral valves shut, making the first heart sound.") as v:
            self.play(FadeOut(arrows_fill), run_time=0.5)
            self.wait(max(0.1, v.left() - 1.0))
        self.add_sound(sfx.lub())
        self.play(beat.animate.set_value(PH_EJECT - 0.005), FadeIn(lub_txt, scale=1.4), run_time=0.7, rate_func=linear)
        self.play(FadeOut(lub_txt), run_time=0.4)

        arrows_out = VGroup(
            Arrow(h.to_scene((-0.5, -0.6)), h.to_scene((-0.45, 2.1)), color=BLUE, buff=0, stroke_width=6),
            Arrow(h.to_scene((0.3, -0.6)), h.to_scene((0.33, 2.6)), color=RED, buff=0, stroke_width=6),
        ).set_z_index(8)
        with self.voice("The pulmonary and aortic valves are forced open, and blood rushes out, "
                        "to the lungs and to the body.") as v:
            self.play(beat.animate.set_value(PH_EJECT + 0.04), FadeIn(arrows_out), run_time=0.6, rate_func=linear)
            self.play(beat.animate.set_value(PH_DUB - 0.02), run_time=v.left(), rate_func=linear)

        with self.voice("As the ventricles relax, the pressure drops, and the pulmonary and aortic valves "
                        "snap shut, making the second sound.") as v:
            self.play(FadeOut(arrows_out), run_time=0.5)
            self.wait(max(0.1, v.left() - 1.0))
        self.add_sound(sfx.dub())
        self.play(beat.animate.set_value(0.97), FadeIn(dub_txt, scale=1.4), run_time=0.7, rate_func=linear)
        self.play(FadeOut(dub_txt), beat.animate.set_value(1.0), run_time=0.4)

        # A few real-time-ish beats with sound: 1.2 s per beat (50 bpm, slowed a touch for clarity).
        period = 1.2
        beat.set_value(0)
        for k in range(3):
            self.add_sound(sfx.lub(), time_offset=PH_LUB * period)
            self.add_sound(sfx.dub(), time_offset=PH_DUB * period)
            self.play(beat.animate.set_value(k + 1), run_time=period, rate_func=linear)
        with self.voice("At rest, this happens around sixty to one hundred times every minute.") as v:
            n = 0
            while v.left(0) > period * 0.9:
                self.add_sound(sfx.lub(), time_offset=PH_LUB * period, gain=-9)
                self.add_sound(sfx.dub(), time_offset=PH_DUB * period, gain=-9)
                self.play(beat.animate.set_value(beat.get_value() + 1), run_time=period, rate_func=linear)
                n += 1
        detach_cycle(h)
        self.remove(phase_txt, ecg_trace, av_row, sl_row)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)


class Electrical(NarratedScene):
    """Conduction system: SA node -> atria -> AV node -> His -> Purkinje."""

    def construct(self):
        self.add(chapter_tag(5, "The electrical spark"))
        h = placed_heart(scale=0.68, shift=LEFT * 3.2 + UP * 0.25)
        self.add(h)
        S = h.to_scene
        Y = style.ACCENT
        blue_fill, red_fill = interpolate_color(BLUE, style.BG, 0.45), interpolate_color(RED, style.BG, 0.45)
        lit = interpolate_color(Y, style.BG, 0.3)

        def wire(pts, w=6):
            m = VMobject().set_points_smoothly([S(p) for p in pts])
            return m.set_stroke(Y, w).set_opacity(0.3)

        sa = Dot(S((-2.0, 1.75)), radius=0.13, color=Y).set_z_index(9)
        av = Dot(S((-0.95, 0.15)), radius=0.11, color=Y).set_z_index(9)
        internodal = wire([(-2.0, 1.75), (-1.2, 1.2), (-0.95, 0.15)])
        bachmann = wire([(-2.0, 1.75), (-0.6, 1.95), (1.0, 1.75), (1.8, 1.5)])
        his = wire([(-0.95, 0.15), (-0.3, -0.25), (-0.05, -0.5)], 7)
        right_branch = wire([(-0.05, -0.5), (-0.2, -1.4), (-0.35, -2.2), (-0.6, -2.55)])
        left_branch = wire([(-0.05, -0.5), (0.12, -1.4), (0.25, -2.3), (0.55, -2.85)])
        purk_r = wire([(-0.6, -2.55), (-1.6, -2.35), (-2.45, -1.5), (-2.6, -0.6)], 4)
        purk_l = wire([(0.55, -2.85), (1.5, -2.35), (2.3, -1.3), (2.55, -0.5)], 4)
        system = VGroup(internodal, bachmann, his, right_branch, left_branch, purk_r, purk_l)

        def fire(*wires, t=1.0):
            return AnimationGroup(*[ShowPassingFlash(w.copy().set_stroke(Y, 12).set_opacity(1), time_width=0.6)
                                    for w in wires], run_time=t)

        def badge(n, where):
            c = Circle(radius=0.2, stroke_width=0).set_fill(Y, 1)
            return VGroup(c, T(str(n), size=20, bold=True, color=style.BG).move_to(c)).move_to(where).set_z_index(12)

        badges = [badge(1, S((-2.55, 2.35))), badge(2, S((2.05, 1.0))), badge(3, S((-1.35, -0.05))),
                  badge(4, S((0.45, -0.95))), badge(5, S((2.45, -1.9)))]

        steps_box = panel(6.4, 2.95).move_to([3.7, 2.05, 0])
        step_txt = ["SA node fires: the pacemaker", "Signal spreads: atria contract", "AV node holds it ≈ 0.1 s",
                    "Bundle of His, down the septum", "Purkinje fibres: ventricles contract"]
        rows = VGroup(*[VGroup(badge(i + 1, ORIGIN), T(t, size=21)).arrange(RIGHT, buff=0.22)
                        for i, t in enumerate(step_txt)]).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        rows.move_to(steps_box).align_to(steps_box, LEFT).shift(RIGHT * 0.3)
        for r in rows:
            r.set_opacity(0.3)

        def activate(i):
            return AnimationGroup(rows[i].animate.set_opacity(1), FadeIn(badges[i], scale=1.5))

        # ECG panel under the steps, drawn in sync with the signal.
        box = panel(6.4, 3.05).move_to([3.7, -1.35, 0])
        x0, x1, y_base, amp = 0.9, 6.5, -2.2, 1.25
        prog = ValueTracker(0.30)

        def ecg_x(s):
            return x0 + (x1 - x0) * (s - 0.3) / 0.6

        def trace():
            s1 = prog.get_value()
            xs = np.linspace(0.30, max(s1, 0.301), max(2, int(500 * (s1 - 0.3))))
            return VMobject(stroke_color="#7CFC9A", stroke_width=4).set_points_as_corners(
                [[ecg_x(s), y_base + amp * ecg(s), 0] for s in xs])

        ecg_title = T("ECG", size=20, color="#7CFC9A").move_to(box.get_corner(UL) + np.array([0.45, -0.3, 0]))

        with self.voice("What keeps this rhythm so steady? The heart has its own built-in electrical system."):
            self.play(Create(system), FadeIn(sa), FadeIn(av), run_time=2)
            self.play(FadeIn(steps_box), FadeIn(rows), FadeIn(box), FadeIn(ecg_title), run_time=0.8)
            self.add(always_redraw(trace))

        with self.voice("Each beat starts in the sinoatrial node, the heart's natural pacemaker, "
                        "in the wall of the right atrium."):
            self.play(activate(0), Flash(sa, color=Y, line_length=0.3, num_lines=12, flash_radius=0.3), run_time=1.2)
            self.play(Flash(sa, color=Y, line_length=0.3, num_lines=12, flash_radius=0.3), run_time=1)

        with self.voice("Its signal spreads across both atria, making them contract."):
            self.play(activate(1), fire(internodal, bachmann, t=1.2), prog.animate.set_value(0.42),
                      h.ra.animate.set_fill(lit), h.la.animate.set_fill(lit), run_time=1.2)
            self.play(h.ra.animate.scale(0.88).set_fill(blue_fill), h.la.animate.scale(0.88).set_fill(red_fill),
                      run_time=0.6)
            self.play(h.ra.animate.scale(1 / 0.88), h.la.animate.scale(1 / 0.88), run_time=0.5)

        with self.voice("The signal then reaches the atrioventricular node, which holds it back for about "
                        "a tenth of a second, giving the ventricles time to fill.") as v:
            self.play(activate(2), fire(internodal, t=0.8), run_time=0.8)
            self.play(Flash(av, color=Y, flash_radius=0.25), prog.animate.set_value(0.495),
                      run_time=v.left(), rate_func=linear)

        vents = VGroup(h.rv, h.lv)
        with self.voice("Next, it races down the bundle of His through the septum, and spreads out along "
                        "the Purkinje fibres, so the ventricles squeeze from the bottom up, "
                        "like squeezing toothpaste from a tube.") as v:
            self.play(activate(3), fire(his, t=0.6), run_time=0.6)
            self.play(fire(right_branch, left_branch, t=0.8), prog.animate.set_value(0.54), run_time=0.8)
            self.play(activate(4), fire(purk_r, purk_l, t=0.9), h.rv.animate.set_fill(lit), h.lv.animate.set_fill(lit),
                      run_time=0.9)
            self.play(h.rv.animate.scale(0.86, about_edge=UP).set_fill(blue_fill),
                      h.lv.animate.scale(0.86, about_edge=UP).set_fill(red_fill), run_time=0.8)
            self.play(h.rv.animate.scale(1 / 0.86, about_edge=UP), h.lv.animate.scale(1 / 0.86, about_edge=UP),
                      prog.animate.set_value(0.9), run_time=max(0.8, v.left()), rate_func=linear)

        def mark(s0, s1, text):
            rect = Rectangle(width=ecg_x(s1) - ecg_x(s0), height=1.95).move_to(
                [(ecg_x(s0) + ecg_x(s1)) / 2, y_base + 0.45, 0])
            rect.set_fill(Y, 0.12).set_stroke(Y, 1.5, opacity=0.6)
            lbl = T(text, size=22, bold=True, color=Y).next_to(rect, UP, buff=0.06)
            return VGroup(rect, lbl)

        p_m, qrs_m, t_m = mark(0.33, 0.41, "P"), mark(0.49, 0.555, "QRS"), mark(0.72, 0.84, "T")
        with self.voice("An ECG records this electrical activity through the skin."):
            self.play(Indicate(ecg_title, color="#7CFC9A"), run_time=0.8)
        with self.voice("The P wave is the atria firing."):
            self.play(FadeIn(p_m), Indicate(VGroup(h.ra, h.la), color=Y), run_time=1.2)
        with self.voice("The QRS complex is the ventricles firing."):
            self.play(FadeIn(qrs_m), Indicate(vents, color=Y), run_time=1.2)
        with self.voice("And the T wave is the ventricles recharging, ready for the next beat."):
            self.play(FadeIn(t_m), run_time=1.2)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)


class Outro(NarratedScene):
    def construct(self):
        self.add(chapter_tag(6, "By the numbers"))

        specs = [
            (70, "beats / minute", "resting adult"),
            (70, "mL per beat", "from each ventricle"),
            (5, "litres / minute", "70 × 70 mL ≈ 4.9 L"),
            (100000, "beats / day", "≈ 7,000 litres pumped"),
        ]
        cards, anchors = [], []
        for val, unit, note in specs:
            anchor = T(f"{val:,}", size=52, bold=True, color=style.ACCENT)
            u, n = T(unit, size=24), T(note, size=18, color=style.MUTED)
            box = panel(3.6, 2.2)
            VGroup(anchor, u, n).arrange(DOWN, buff=0.18).move_to(box)
            cards.append(VGroup(box, u, n))
            anchors.append(anchor)
        VGroup(*[VGroup(c, a) for c, a in zip(cards, anchors)]).arrange_in_grid(2, 2, buff=(0.4, 0.35)).move_to(UP * 0.15)

        lines = [
            "Let's put some numbers on it. A resting heart beats about seventy times a minute.",
            "Each beat pumps about seventy millilitres from each ventricle.",
            "That adds up to about five litres every minute.",
            "And around one hundred thousand beats, moving some seven thousand litres of blood, every single day.",
        ]
        live = []
        for i, text in enumerate(lines):
            with self.voice(text) as v:
                vt, where = ValueTracker(0), anchors[i].get_center()
                num = always_redraw(lambda vt=vt, where=where: T(f"{int(round(vt.get_value())):,}", size=52,
                                                               bold=True, color=style.ACCENT).move_to(where))
                self.play(FadeIn(cards[i], shift=UP * 0.2), run_time=0.6)
                self.add(num)
                live.append(num)
                self.play(vt.animate.set_value(specs[i][0]), run_time=min(1.6, v.left()), rate_func=smooth)
        for n in live:
            n.clear_updaters()
        self.play(FadeOut(VGroup(*cards, *live)), run_time=0.7)

        self.remove(*[m for m in self.mobjects])
        self.add(chapter_tag(7, "Recap"))
        items = [
            "Right side pumps blood to the lungs",
            "Left side pumps blood to the body",
            "Four valves keep blood moving one way",
            "An electrical signal times every beat",
        ]
        bl = bullet_list(items, size=32).move_to(UP * 0.3)
        with self.voice("To recap.") as v:
            pass
        say = [
            "The right side pumps blood to the lungs.",
            "The left side pumps it to the body.",
            "Four valves keep it flowing one way.",
            "And an electrical signal times every beat.",
        ]
        for row, s in zip(bl, say):
            with self.voice(s, pad=0.2):
                self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=0.6)
        self.wait(0.5)
        self.play(FadeOut(bl), run_time=0.6)

        icon = heart_icon(1.2).shift(UP * 1.9)
        made = T("Made entirely with free, open-source tools", size=34, bold=True).next_to(icon, DOWN, buff=0.4)
        tools = T("Manim  ·  Piper neural TTS  ·  FFmpeg  ·  Python", size=26, color=style.ACCENT).next_to(made, DOWN, buff=0.3)
        note = T("Simplified for learning. Not medical advice.", size=20, color=style.MUTED).next_to(tools, DOWN, buff=0.5)
        with self.voice("This video was made entirely with free and open-source software. Thanks for watching."):
            self.play(GrowFromCenter(icon), Write(made), run_time=1.5)
            self.play(FadeIn(tools, shift=UP * 0.2), FadeIn(note), run_time=1)
        self.wait(1.5)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1)


# (scene class, chapter title shown in video players)
CHAPTERS = [
    ("Intro", "Introduction"),
    ("TwoPumps", "Two pumps in one"),
    ("Anatomy", "Inside the heart"),
    ("Journey", "The path of blood"),
    ("Cycle", "One heartbeat"),
    ("Electrical", "The electrical spark"),
    ("Outro", "By the numbers & recap"),
]
