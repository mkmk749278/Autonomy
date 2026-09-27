"""NarratedScene: keeps animation timing locked to the spoken narration.

Usage inside ``construct``::

    with self.voice("The heart has four chambers.") as v:
        self.play(FadeIn(heart), run_time=v.left() * 0.5)
        self.play(Write(label))
    # leaving the block waits until the sentence has finished playing

Each sentence becomes its own audio clip and subtitle cue, so captions
are timed exactly rather than estimated.
"""
from __future__ import annotations

import math
import re
from contextlib import contextmanager
from dataclasses import dataclass

from manim import Scene

from . import style
from .tts import synthesize

SENTENCE_GAP = 0.18       # breath between sentences, seconds
MAX_CAPTION_CHARS = 84    # longer sentences are split across cues


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _caption_chunks(sentence: str) -> list[str]:
    """Split a long sentence into evenly sized cues (no one-word orphans)."""
    if len(sentence) <= MAX_CAPTION_CHARS:
        return [sentence]
    k = math.ceil(len(sentence) / MAX_CAPTION_CHARS)
    target = len(sentence) / k
    chunks, cur = [], ""
    for w in sentence.split():
        cand = f"{cur} {w}".strip()
        if cur and len(cand) > target and len(chunks) < k - 1:
            if abs(len(cand) - target) <= abs(len(cur) - target):
                chunks.append(cand)
                cur = ""
            else:
                chunks.append(cur)
                cur = w
            continue
        cur = cand
    if cur:
        chunks.append(cur)
    return chunks


@dataclass
class Narration:
    scene: Scene
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration

    def left(self, minimum: float = 0.3) -> float:
        """Seconds of speech remaining (never below ``minimum``)."""
        return max(minimum, self.end - self.scene.renderer.time)


class NarratedScene(Scene):
    def setup(self):
        self.camera.background_color = style.BG

    @contextmanager
    def voice(self, text: str, pad: float = 0.4):
        t0 = self.renderer.time
        offset = 0.0
        for sentence in _sentences(text):
            wav, dur = synthesize(sentence)
            self.add_sound(str(wav), time_offset=offset)
            chunks = _caption_chunks(sentence)
            total_chars = sum(len(c) for c in chunks)
            c_off = offset
            for c in chunks:
                c_dur = dur * len(c) / total_chars
                self.add_subcaption(c, duration=c_dur, offset=c_off)
                c_off += c_dur
            offset += dur + SENTENCE_GAP
        n = Narration(self, t0, offset - SENTENCE_GAP)
        yield n
        remaining = n.end + pad - self.renderer.time
        if remaining > 1 / 60:
            self.wait(remaining)

    def say(self, text: str, pad: float = 0.4):
        """Narrate with no accompanying animation (holds the current frame)."""
        with self.voice(text, pad=pad):
            pass
