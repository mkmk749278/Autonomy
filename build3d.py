#!/usr/bin/env python3
"""Build the 3D heart video.

    python build3d.py                    # full 1080p30 render (~1 h on 4 CPU cores)
    python build3d.py --preview 20 40    # render only seconds 20-40 to check a shot
    python build3d.py --timeline-only    # just narration + timeline.json (for the web preview)

Steps: narrate each shot (Piper) -> timeline.json with exact sentence
times -> headless-Chromium render of the three.js scene -> mix voice and
synthesised heart sounds -> burn captions, chapter markers, loudness
normalise -> output/heart3d/heart3d.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from datetime import timedelta
from pathlib import Path

import numpy as np
import srt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "videos" / "heart3d"))

from build import CAPTION_STYLE  # noqa: E402
from script import SHOTS, TITLE  # noqa: E402
from studio import sfx  # noqa: E402
from studio.narrated import _caption_chunks  # noqa: E402
from studio.tts import synthesize  # noqa: E402

BUILD = ROOT / "build" / "heart3d"
OUT = ROOT / "output" / "heart3d"
FPS = 30
RATE = 44100
LEAD_IN, GAP = 0.8, 0.3          # seconds before first sentence / between sentences
BEAT_T, PH_LUB, PH_DUB = 1.0, 0.55, 0.90   # must match web/heart3d.js
CHAPTER_TITLES = {"intro": "Introduction", "exterior": "The outside", "xray": "Four chambers",
                  "valves": "Four valves", "flow": "The path of blood", "beat": "The heartbeat",
                  "section": "Cross-section", "outro": "Credits"}


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        rate = wf.getframerate()
    if rate != RATE:
        t = np.arange(int(len(data) * RATE / rate)) / RATE
        data = np.interp(t, np.arange(len(data)) / rate, data)
    return data


def make_timeline() -> dict:
    t, shots = 0.0, []
    for shot_id, hold, sentences in SHOTS:
        start, cur, items = t, t + LEAD_IN, []
        for text in sentences:
            wav, dur = synthesize(text)
            items.append({"text": text, "start": round(cur, 3), "end": round(cur + dur, 3), "wav": str(wav)})
            cur += dur + GAP
        end = cur - GAP + hold
        shots.append({"id": shot_id, "start": round(start, 3), "end": round(end, 3), "sentences": items})
        t = end
    return {"title": TITLE, "fps": FPS, "beat_T": BEAT_T, "duration": round(t, 3), "shots": shots}


def mix_audio(tl: dict, path: Path):
    total = np.zeros(int((tl["duration"] + 1) * RATE), np.float32)

    def place(sig, at, gain=1.0):
        i = int(at * RATE)
        n = min(len(sig), len(total) - i)
        total[i:i + n] += sig[:n] * gain

    speech = []
    for shot in tl["shots"]:
        for s in shot["sentences"]:
            place(read_wav(Path(s["wav"])), s["start"])
            speech.append((s["start"], s["end"]))
    lub, dub = read_wav(Path(sfx.lub())), read_wav(Path(sfx.dub()))
    beat = next(s for s in tl["shots"] if s["id"] == "beat")
    k = int(np.ceil(beat["start"] / BEAT_T))
    while (k + PH_DUB) * BEAT_T < beat["end"] - 0.5:
        for ph, snd in ((PH_LUB, lub), (PH_DUB, dub)):
            at = (k + ph) * BEAT_T
            talking = any(a - 0.2 < at < b + 0.2 for a, b in speech)
            place(snd, at, 0.35 if talking else 0.85)
        k += 1
    pcm = np.int16(np.clip(total, -1, 1) * 32767)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(pcm.tobytes())


def write_captions(tl: dict, path: Path):
    subs = []
    for shot in tl["shots"]:
        for s in shot["sentences"]:
            chunks = _caption_chunks(s["text"])
            total = sum(len(c) for c in chunks)
            t = s["start"]
            for c in chunks:
                d = (s["end"] - s["start"]) * len(c) / total
                subs.append(srt.Subtitle(len(subs) + 1, timedelta(seconds=t), timedelta(seconds=t + d), c))
                t += d
    path.write_text(srt.compose(subs), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", nargs=2, type=float, metavar=("FROM", "TO"))
    ap.add_argument("--timeline-only", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tl = make_timeline()
    (BUILD / "timeline.json").write_text(json.dumps(tl, indent=1))
    print(f"Timeline: {tl['duration']:.1f} s, {len(tl['shots'])} shots")
    if args.timeline_only:
        return

    video = BUILD / ("preview.mp4" if args.preview else "video.mp4")
    cmd = ["node", str(ROOT / "videos/heart3d/render3d.mjs"), "--out", str(video), "--fps", str(FPS),
           "--workers", str(args.workers)]
    if args.preview:
        cmd += ["--from", str(args.preview[0]), "--to", str(args.preview[1])]
    subprocess.run(cmd, check=True, cwd=ROOT)

    audio = BUILD / "audio.wav"
    mix_audio(tl, audio)
    captions = OUT / "heart3d.srt"
    write_captions(tl, captions)
    meta = [";FFMETADATA1", f"title={TITLE}"]
    for s in tl["shots"]:
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(s['start'] * 1000)}", f"END={int(s['end'] * 1000)}",
                 f"title={CHAPTER_TITLES.get(s['id'], s['id'])}"]
    (BUILD / "chapters.txt").write_text("\n".join(meta) + "\n")

    final = OUT / ("heart3d_preview.mp4" if args.preview else "heart3d.mp4")
    offset = ["-ss", str(args.preview[0])] if args.preview else []
    dur = ["-t", str(args.preview[1] - args.preview[0])] if args.preview else []
    sub = f"subtitles={captions}:force_style='{CAPTION_STYLE}'"
    if args.preview:
        sub = f"setpts=PTS+{args.preview[0]}/TB,{sub},setpts=PTS-STARTPTS"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), *offset, *dur, "-i", str(audio),
                    "-i", str(BUILD / "chapters.txt"), "-map", "0:v", "-map", "1:a", "-map_metadata", "2",
                    "-map_chapters", "2", "-vf", sub, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    print(f"Done: {final} ({final.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
