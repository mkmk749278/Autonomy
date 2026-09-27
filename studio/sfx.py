"""Synthesised sound effects (no samples needed, so no licensing issues)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "build" / "sfx"
RATE = 44100


def _write(name: str, signal: np.ndarray) -> str:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    path = SFX_DIR / f"{name}.wav"
    pcm = np.int16(np.clip(signal, -1, 1) * 32767)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(pcm.tobytes())
    return str(path)


def _thump(freq: float, dur: float, decay: float, level: float) -> np.ndarray:
    t = np.arange(int(RATE * dur)) / RATE
    env = (1 - np.exp(-t * 400)) * np.exp(-t * decay)
    # Fundamental plus harmonics so the thump is audible on small speakers.
    tone = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in [(1, 1.0), (2, 0.55), (3, 0.3), (5, 0.12)])
    rng = np.random.default_rng(int(freq))
    click = rng.normal(0, 1, t.size) * np.exp(-t * 90) * 0.25
    click = np.convolve(click, np.ones(12) / 12, mode="same")
    return level * env * (tone / 2.0 + click)


def lub() -> str:
    """First heart sound (S1): AV valves closing. Longer and lower."""
    return _write("lub", _thump(55, 0.22, 22, 0.9))


def dub() -> str:
    """Second heart sound (S2): semilunar valves closing. Shorter and higher."""
    return _write("dub", _thump(80, 0.16, 32, 0.75))


def pop() -> str:
    """Soft UI blip for labels appearing."""
    t = np.arange(int(RATE * 0.09)) / RATE
    sig = np.sin(2 * np.pi * (660 + 900 * t) * t) * np.exp(-t * 45) * 0.18
    return _write("pop", sig)
