"""Offline neural text-to-speech with Piper (MIT licensed, runs on CPU).

Every narration line is synthesised once and cached by a hash of
(voice, speed, text), so re-rendering a scene never re-synthesises audio.
"""
from __future__ import annotations

import hashlib
import os
import wave
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = Path(os.environ.get("STUDIO_VOICE_DIR", ROOT / "assets" / "voices"))
VOICE_NAME = os.environ.get("STUDIO_VOICE", "en_US-lessac-medium")
# >1.0 speaks slower. Slightly slow narration is easier to follow for teaching.
LENGTH_SCALE = float(os.environ.get("STUDIO_VOICE_SPEED", "1.08"))
CACHE_DIR = ROOT / "build" / "tts_cache"

# Captions show the left side; the voice is given the right side. Keeps
# abbreviations and eponyms readable on screen but pronounced correctly.
PRONOUNCE = {
    "ECG": "E C G",
    "QRS": "Q R S",
    "bundle of His": "bundle of Hiss",
    "mmHg": "millimetres of mercury",
}


def spoken(text: str) -> str:
    for shown, said in PRONOUNCE.items():
        text = text.replace(shown, said)
    return text


@lru_cache(maxsize=1)
def _voice():
    from piper import PiperVoice

    model = VOICE_DIR / f"{VOICE_NAME}.onnx"
    if not model.exists():
        raise FileNotFoundError(f"Piper voice not found at {model}. Run ./setup.sh first.")
    return PiperVoice.load(str(model))


def synthesize(text: str) -> tuple[Path, float]:
    """Return (wav_path, duration_seconds) for ``text``, synthesising on cache miss."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    text = spoken(text)
    key = hashlib.sha1(f"{VOICE_NAME}|{LENGTH_SCALE}|{text}".encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{key}.wav"
    if not path.exists():
        from piper import SynthesisConfig

        tmp = path.with_suffix(".tmp.wav")
        with wave.open(str(tmp), "wb") as wf:
            _voice().synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=LENGTH_SCALE))
        tmp.rename(path)
    with wave.open(str(path), "rb") as wf:
        return path, wf.getnframes() / wf.getframerate()
