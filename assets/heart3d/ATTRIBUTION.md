# 3D heart model: attribution and licence

`heart.glb` and `landmarks.json` are derived from **BodyParts3D**,
© The Database Center for Life Science (DBCLS), licensed under
[Creative Commons Attribution-Share Alike 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en).
Source: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/

Changes made by `videos/heart3d/prepare_model.py`:

* Chamber cavities, valve leaflets/cusps, papillary muscles, great vessels and coronary vessels
  were taken from the atlas, then trimmed and simplified.
* The ventricular muscle wall is **reconstructed**, not original atlas data. The atlas includes only
  wall fragments, so a wall was grown around the real chamber cavities using typical adult
  thicknesses (LV ≈10 mm, RV ≈4 mm, atria ≈2.5–3 mm) and merged with those fragments.
* Blood-flow centrelines were computed through the chamber and vessel volumes.

**Share-alike:** these model files, and videos or images rendered from them (such as
`output/heart3d/heart3d.mp4`), must keep this attribution and be shared under CC BY-SA 2.1 JP
or a compatible licence.
