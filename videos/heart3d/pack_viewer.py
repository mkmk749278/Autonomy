"""Package the interactive viewer for static hosts that don't serve .glb files.

Writes build/heart3d/viewer/: index.html, heart3d.js, landmarks.json and
heart.glb.json (the model as base64 inside JSON).

    python videos/heart3d/pack_viewer.py
"""
import base64
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "heart3d" / "viewer"
OUT.mkdir(parents=True, exist_ok=True)
glb = (ROOT / "assets/heart3d/heart.glb").read_bytes()
(OUT / "heart.glb.json").write_text(json.dumps({"glb": base64.b64encode(glb).decode()}))
shutil.copy(ROOT / "assets/heart3d/landmarks.json", OUT / "landmarks.json")
shutil.copy(ROOT / "videos/heart3d/web/heart3d.js", OUT / "heart3d.js")
shutil.copy(ROOT / "videos/heart3d/web/viewer.html", OUT / "index.html")
print(f"Packed viewer in {OUT}")
