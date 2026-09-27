#!/usr/bin/env python3
"""Render a narrated explainer end to end.

    python build.py heart              # 1080p30 final video
    python build.py heart --quality draft
    python build.py heart --only Cycle # re-render one chapter, reuse the rest

Steps: render every chapter in parallel with Manim -> join them ->
merge per-chapter captions -> burn captions, normalise loudness, add
chapter markers -> output/<project>/<project>.mp4 (+ .srt, thumbnail).
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import srt

ROOT = Path(__file__).resolve().parent
PROJECTS = {
    "heart": ROOT / "videos" / "heart" / "scenes.py",
}
QUALITY = {"draft": ("854,480", 15), "hd": ("1920,1080", 30)}
CAPTION_STYLE = (
    "FontName=Inter,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H50000000,BackColour=&H00000000,"
    "BorderStyle=3,Outline=7,Shadow=0,MarginV=16,MarginL=40,MarginR=40"
)


def load_chapters(scene_file: Path) -> list[tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("project_scenes", scene_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CHAPTERS


def render(scene_file: Path, scene: str, res: str, fps: int, media: Path) -> Path:
    cmd = [sys.executable, "-m", "manim", "render", "-r", res, "--fps", str(fps), "--disable_caching",
           "--progress_bar", "none", "--media_dir", str(media), str(scene_file), scene]
    log = media / f"{scene}.log"
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=ROOT).returncode
    if rc != 0:
        raise RuntimeError(f"{scene} failed, see {log}")
    height = res.split(",")[1]
    return media / "videos" / scene_file.stem / f"{height}p{fps}" / f"{scene}.mp4"


def duration(path: Path) -> float:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", choices=sorted(PROJECTS))
    ap.add_argument("--quality", choices=sorted(QUALITY), default="hd")
    ap.add_argument("--only", nargs="*", help="re-render just these chapters")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()

    scene_file = PROJECTS[args.project]
    chapters = load_chapters(scene_file)
    res, fps = QUALITY[args.quality]
    media = ROOT / "build" / "media" / args.quality
    media.mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "output" / args.project
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [c for c, _ in chapters if not args.only or c in args.only]
    print(f"Rendering {len(todo)} chapter(s) at {res} {fps}fps with {args.jobs} worker(s)...")
    with ThreadPoolExecutor(args.jobs) as pool:
        futures = {c: pool.submit(render, scene_file, c, res, fps, media) for c in todo}
        for c, f in futures.items():
            f.result()
            print(f"  done: {c}")

    height = res.split(",")[1]
    clip_dir = media / "videos" / scene_file.stem / f"{height}p{fps}"
    clips = [clip_dir / f"{c}.mp4" for c, _ in chapters]
    missing = [str(c) for c in clips if not c.exists()]
    if missing:
        sys.exit(f"Missing chapter renders: {missing}")

    # Merge captions and build chapter markers on one shared timeline.
    subs, meta, t = [], [";FFMETADATA1", f"title={args.project}"], 0.0
    for (scene, title), clip in zip(chapters, clips):
        d = duration(clip)
        cap = clip.with_suffix(".srt")
        if cap.exists():
            for s in srt.parse(cap.read_text(encoding="utf-8")):
                s.start += timedelta(seconds=t)
                s.end += timedelta(seconds=t)
                subs.append(s)
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int((t + d) * 1000)}",
                 f"title={title}"]
        t += d
    captions = out_dir / f"{args.project}.srt"
    captions.write_text(srt.compose(subs), encoding="utf-8")
    meta_file = media / "chapters.txt"
    meta_file.write_text("\n".join(meta) + "\n", encoding="utf-8")
    concat = media / "concat.txt"
    concat.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")

    final = out_dir / f"{args.project}.mp4" if args.quality == "hd" else out_dir / f"{args.project}_{args.quality}.mp4"
    sub_filter = f"subtitles={captions}:force_style='{CAPTION_STYLE}'"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(meta_file),
           "-map", "0:v", "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1",
           "-vf", sub_filter, "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(final)]
    print("Joining chapters, burning captions, normalising audio...")
    subprocess.run(cmd, check=True)

    thumb = out_dir / f"{args.project}_thumbnail.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(duration(clips[0]) + duration(clips[1]) + 20),
                    "-i", str(final), "-frames:v", "1", str(thumb)], check=True)
    print(f"\nDone: {final}  ({t / 60:.1f} min, {final.stat().st_size / 1e6:.1f} MB)")
    print(f"Captions: {captions}\nThumbnail: {thumb}")


if __name__ == "__main__":
    main()
