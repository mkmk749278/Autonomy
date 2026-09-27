# Autonomy: a zero-cost animated explainer studio

This repo turns a script into a **narrated, captioned, chaptered animation video** of how a body system works.
It uses only free, open-source software, runs on an ordinary laptop CPU, and needs no paid APIs, no GPU and no
subscriptions.

**First video:** [`output/heart/heart.mp4`](output/heart/heart.mp4). *How the Heart Pumps Blood*
(about 5 min, 1080p, burned-in captions, chapter markers, sidecar [`heart.srt`](output/heart/heart.srt)).

| # | Chapter | What you see |
|---|---------|--------------|
| 0 | Introduction | Beating heart, 5 L/min, roadmap |
| 1 | Two pumps in one | Double circulation loop: blood turns red at the lungs and blue in the body |
| 2 | Inside the heart | 4 chambers, septum, 4 valves opening and closing, LV wall vs RV wall (≈120 vs ≈25 mmHg) |
| 3 | The path of blood | One drop travels SVC/IVC → RA → tricuspid → RV → pulmonary artery → lungs → pulmonary veins → LA → mitral → LV → aorta |
| 4 | One heartbeat | Cardiac cycle with live valve status, synced ECG and synthesised *lub-dub* sounds |
| 5 | The electrical spark | SA node → atria → AV node delay → bundle of His → Purkinje fibres, with the P / QRS / T waves labelled |
| 6 | By the numbers & recap | 70 bpm, 70 mL, 5 L/min, 100,000 beats/day |

---

## The free toolchain

| Job | Tool | Licence | Why |
|-----|------|---------|-----|
| Animation | [Manim Community](https://www.manim.community/) | MIT | Precise, code-driven 2D animation (the engine behind 3Blue1Brown-style videos) |
| Narration | [Piper](https://github.com/rhasspy/piper) neural TTS | MIT (voices vary; `lessac` is free to use) | Natural-sounding voice, offline, fast on CPU. 177 voices in 58 locales, **including Telugu, Hindi, Malayalam, Marathi, Bengali, Nepali and Urdu** |
| Video, captions, audio | [FFmpeg](https://ffmpeg.org/) + libass | LGPL/GPL | Joins chapters, burns captions, normalises loudness to −16 LUFS, writes chapter markers |
| Sound effects | numpy (in `studio/sfx.py`) | — | Heart sounds are synthesised, so there are no samples to license |
| Font | [Inter](https://rsms.me/inter/) | OFL | Clean and very legible on phones |

**Total cost: ₹0 / $0.** The heart video renders in about 5–10 minutes on 4 CPU cores (draft preview: under 2 minutes).

## Quick start

```bash
./setup.sh                                   # installs ffmpeg, Manim, Piper + downloads the voice
.venv/bin/python build.py heart --quality draft   # 480p preview in ~2 min
.venv/bin/python build.py heart                   # final 1080p → output/heart/heart.mp4
.venv/bin/python build.py heart --only Cycle      # re-render one chapter, then re-join
```

To render one chapter interactively: `.venv/bin/manim -pql videos/heart/scenes.py Journey`.

Change the voice with `STUDIO_VOICE=te_IN-venkatesh-medium ./setup.sh`, and set the same variable when you build.
For narration in another language, also translate the script strings and install a font for that script
(for example `fonts-noto-core` for Telugu or Hindi).

## How it works

```
script text ──► Piper TTS (cached per sentence) ──► exact durations
                                                  │
Manim scene ◄─────────────────────────────────────┘  animations timed to the voice
   │  one scene per chapter, rendered in parallel
   ▼
chapter MP4s + per-chapter SRT captions
   │  build.py
   ▼
FFmpeg: concat → burn captions → loudness-normalise → chapter markers → heart.mp4
```

* `studio/narrated.py`: `NarratedScene.voice("...")` speaks a line, adds exactly timed captions, and holds the
  scene until the line finishes. Animations inside the block use `v.left()` to fill the remaining speech time.
* `studio/tts.py`: Piper wrapper with caching and a `PRONOUNCE` map, so the screen shows "bundle of His" or "ECG"
  and the voice says "Hiss" or "E C G".
* `studio/flow.py`: particle streams along any path (blood, air or food), with per-position colour
  (for example blue→red across the lungs).
* `videos/heart/heart_parts.py`: the reusable schematic heart, with working valves, chambers and routes.
* `videos/heart/scenes.py`: the script plus the cardiac-cycle model (chamber volume, valve state and ECG as
  functions of beat phase).

## Adding the next system

The respiratory and digestive videos reuse the same studio. Only the diagram and the script change.

1. `videos/<system>/<system>_parts.py`: draw the organ schematic (as in `heart_parts.py`).
2. `videos/<system>/scenes.py`: one `NarratedScene` per chapter, plus a `CHAPTERS` list.
3. Register it in `PROJECTS` in `build.py`, then run `python build.py <system>`.

Storyboards ready to build:

* **Breathing (respiratory):** air path (nose → trachea → bronchi → alveoli) · diaphragm down = inhale
  (pressure-volume, Boyle's law) · alveolus close-up with O₂/CO₂ diffusion across the capillary wall ·
  haemoglobin loading · brainstem rhythm and the CO₂ trigger · numbers (≈12–20 breaths/min, ≈500 mL tidal volume).
* **Digestion:** mouth (amylase) → oesophagus (peristalsis wave) → stomach (acid + pepsin, churning) →
  small intestine (bile, pancreatic enzymes, villi absorption close-up) → large intestine (water) · a
  timeline of how long each stage takes.

## How far can this go for free?

| Level | What | Free? | Honest limits |
|-------|------|-------|---------------|
| **1. Done here** | 2D schematic explainer with voice, captions and chapters | ✅ fully | Stylised rather than photorealistic. Every video is code, so it can be edited, translated and re-rendered |
| 2 | Interactive web version (SVG/Canvas/Three.js) where learners click a valve or slow the heartbeat | ✅ (GitHub Pages hosting) | More front-end work |
| 3 | 3D anatomical animation: **Blender** (GPL) scripted from Python, with free CC BY-SA anatomy models (BodyParts3D, Z-Anatomy) | ✅ software, ✅ models (keep attribution) | CPU rendering is slow (hours per minute of video). A free Colab/Kaggle GPU session helps but has quotas |
| 4 | Multi-language dubbing: same script, different Piper voice | ✅ | Neural voices can mispronounce medical terms, so check each language with the `PRONOUNCE` map |
| 5 | Background music | ✅ synthesise it, or use CC0 tracks | Check each track's licence yourself |
| 6 | AI text-to-video (open-weight models) | ⚠️ weights free, GPU is not | Needs a 12–24 GB GPU. **Anatomy is not reliable**: models invent structures, which is unacceptable for teaching |
| 7 | Hosted AI video/voice services | ❌ paid beyond small trials | Not used here |

## Accuracy notes (read before classroom use)

This is a teaching schematic, and a qualified educator should review it before formal use. Deliberate simplifications:

* A frontal-section diagram with the heart's right side on the viewer's left (the video says so).
* Oxygen-poor blood is drawn blue by convention (the video says blood is always red).
* Only two of the four pulmonary veins are drawn. Vessel crossings are simplified.
* Cardiac-cycle phase proportions are stretched for readability. The **order** of events, valve states and ECG
  timing relative to contraction are correct.
* Figures are typical resting-adult values (60–100 bpm, ≈70 mL stroke volume, ≈5 L/min cardiac output,
  ≈120/≈25 mmHg LV/RV systolic pressure).

Not medical advice.
