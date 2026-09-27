"""Build the 3D heart model for the web renderer from the BodyParts3D atlas.

BodyParts3D gives real, CT-derived meshes for the four blood-filled
chamber cavities, all valve leaflets, the great vessels and the coronary
vessels, but only fragments of the ventricular muscle. So we:

1. voxelise each chamber cavity (generalised winding number, robust to
   the openings where cavities meet valves and vessels);
2. grow a muscle wall around the cavities with anatomically typical
   thickness (LV ~10 mm, RV ~4 mm, atria ~2.5 mm) and merge in the
   atlas's own wall fragments;
3. mesh everything with marching cubes, simplify, and export one GLB
   with named nodes, plus landmarks.json holding label anchors and
   blood-flow centrelines traced through the chambers.

Output coordinates are glTF Y-up metres*10 (1 unit = 10 cm), with +X to
the patient's left (viewer's right in a frontal view) and +Z anterior.

Model data: BodyParts3D, (c) The Database Center for Life Science,
licensed under CC BY-SA 2.1 Japan.

    python videos/heart3d/prepare_model.py --bp3d /path/to/partof_BP3D_4.0_obj_99
"""
from __future__ import annotations

import argparse
import functools
import time
import json
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure
from skimage.graph import route_through_array

HERE = Path(__file__).resolve().parent
print = functools.partial(print, flush=True)  # noqa: A001
T0 = time.time()
ROOT = HERE.parents[1]
OUT_DIR = ROOT / "assets" / "heart3d"
VOX = 1.0  # mm

CAVITIES = {"ra": "FJ2424", "rv": "FJ2423", "la": "FJ2425", "lv": "FJ2422"}
WALL_THICKNESS = {"ra": 2.5, "rv": 4.0, "la": 3.0, "lv": 10.0}  # mm, typical adult
ATLAS_WALLS = ["FJ2438", "FJ2439", "FJ2429", "FJ2432", "FJ2430"]
VALVES = {
    "tricuspid": ["FJ2421", "FJ2433", "FJ2436"],
    "mitral": ["FJ2420"],
    "pulmonary": ["FJ2417", "FJ2427", "FJ2434"],
    "aortic": ["FJ2435", "FJ2426", "FJ2431"],
}
PAPILLARY = ["FJ2419", "FJ2437", "FJ2418"]
VESSELS = {
    "svc": ["FJ3645"],
    "ivc": ["FJ3441"],
    "aorta": ["FJ3413", "FJ3411", "FJ1931"],
    "pulmonary_trunk": ["FJ2966"],
    "pulmonary_arteries": ["FJ3019", "FJ2924"],
    "pulmonary_veins": ["FJ3020", "FJ3040", "FJ2925", "FJ2933", "FJ2944", "FJ2950", "FJ2955"],
}


def load(bp3d: Path, fj: str) -> trimesh.Trimesh:
    return trimesh.load(bp3d / f"{fj}.obj", force="mesh", process=True)


def winding_inside(mesh: trimesh.Trimesh, pts: np.ndarray, chunk: int = 2048, thresh: float = 0.5) -> np.ndarray:
    """Generalised winding number test; tolerant of holes in ``mesh``."""
    tri = mesh.triangles.astype(np.float32)
    A, B, C = tri[:, 0], tri[:, 1], tri[:, 2]
    out = np.zeros(len(pts), dtype=np.float32)
    for s in range(0, len(pts), chunk):
        p = pts[s:s + chunk, None, :].astype(np.float32)
        a, b, c = A[None] - p, B[None] - p, C[None] - p
        la, lb, lc = (np.linalg.norm(v, axis=2) for v in (a, b, c))
        det = np.einsum("ijk,ijk->ij", a, np.cross(b, c))
        den = (la * lb * lc + np.einsum("ijk,ijk->ij", a, b) * lc
               + np.einsum("ijk,ijk->ij", b, c) * la + np.einsum("ijk,ijk->ij", c, a) * lb)
        out[s:s + chunk] = np.arctan2(det, den).sum(axis=1) / (2 * np.pi)
    return np.abs(out) > thresh


class Grid:
    def __init__(self, lo, hi, vox):
        self.lo = np.floor(np.asarray(lo) / vox) * vox
        self.shape = tuple(int(n) for n in np.ceil((np.asarray(hi) - self.lo) / vox) + 1)
        self.vox = vox

    def centers(self, sl):
        idx = np.stack(np.meshgrid(*[np.arange(s.start, s.stop) for s in sl], indexing="ij"), -1)
        return self.lo + idx.reshape(-1, 3) * self.vox

    def slices(self, lo, hi, pad=2):
        a = np.clip(np.floor((lo - self.lo) / self.vox).astype(int) - pad, 0, None)
        b = np.minimum(np.ceil((hi - self.lo) / self.vox).astype(int) + pad + 1, self.shape)
        return tuple(slice(i, j) for i, j in zip(a, b))

    def to_world(self, ijk):
        return self.lo + np.asarray(ijk, float) * self.vox

    def to_index(self, p):
        return tuple(np.clip(np.round((np.asarray(p) - self.lo) / self.vox).astype(int), 0, np.array(self.shape) - 1))

    def voxelize(self, mesh, thresh=0.5, max_faces=2500, reach_mm=None):
        """Solid voxel mask of ``mesh``. Winding numbers are only evaluated
        near the surface (within ``reach_mm``) on a simplified copy, which
        keeps big vessels cheap."""
        test = simplify(mesh, max_faces)
        sl = self.slices(mesh.bounds[0], mesh.bounds[1])
        cand = np.ones([s.stop - s.start for s in sl], bool)
        if reach_mm:
            near = self.surface_mask(mesh, dilate=0)[sl]
            cand = ndimage.distance_transform_edt(~near, sampling=self.vox) <= reach_mm
        pts = self.centers(sl).reshape(cand.shape + (3,))[cand]
        m = np.zeros(self.shape, bool)
        sub = np.zeros(cand.shape, bool)
        sub[cand] = winding_inside(test, pts, thresh=thresh)
        m[sl] = sub
        return m

    def surface_mask(self, mesh, dilate=1):
        m = np.zeros(self.shape, bool)
        pts, _ = trimesh.sample.sample_surface_even(mesh, int(mesh.area / (self.vox * 0.5) ** 2) + 100)
        idx = np.clip(np.round((pts - self.lo) / self.vox).astype(int), 0, np.array(self.shape) - 1)
        m[tuple(idx.T)] = True
        return ndimage.binary_dilation(m, iterations=dilate) if dilate else m


def mask_to_mesh(grid, mask, sigma=1.0, level=0.5, target_faces=None):
    f = ndimage.gaussian_filter(mask.astype(np.float32), sigma)
    f = np.pad(f, 1)
    v, fc, _, _ = measure.marching_cubes(f, level)
    v = grid.lo + (v - 1) * grid.vox
    if target_faces and len(fc) > target_faces:
        v, fc = fast_simplification.simplify(v.astype(np.float32), fc.astype(np.int32),
                                             target_reduction=1 - target_faces / len(fc))
    m = trimesh.Trimesh(v, fc, process=True)
    trimesh.repair.fix_normals(m)
    return m


def simplify(mesh, target_faces):
    if len(mesh.faces) <= target_faces:
        return mesh
    v, f = fast_simplification.simplify(mesh.vertices.astype(np.float32), mesh.faces.astype(np.int32),
                                        target_reduction=1 - target_faces / len(mesh.faces))
    return trimesh.Trimesh(v, f, process=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bp3d", type=Path, default=Path("/opt/bp3d/partof_BP3D_4.0_obj_99"))
    args = ap.parse_args()
    names = json.loads((HERE / "parts_index.json").read_text())
    L = lambda fj: load(args.bp3d, fj)  # noqa: E731

    cav = {k: L(fj) for k, fj in CAVITIES.items()}
    walls = [L(fj) for fj in ATLAS_WALLS]
    valves = {k: trimesh.util.concatenate([L(f) for f in v]) for k, v in VALVES.items()}
    vessels = {k: trimesh.util.concatenate([L(f) for f in v]) for k, v in VESSELS.items()}

    # Trim long vessels so the model is the heart plus short vessel stumps.
    heart_bounds = np.vstack([m.bounds for m in list(cav.values()) + walls])
    z_min = heart_bounds[:, 2].min() - 12
    for k in ("aorta", "ivc"):
        vessels[k] = vessels[k].slice_plane([0, 0, z_min], [0, 0, 1], cap=False)

    lo = heart_bounds.min(0) - 16
    hi = heart_bounds.max(0) + 16
    grid = Grid(lo, hi, VOX)
    print("grid", grid.shape)

    masks = {}
    for k, m in cav.items():
        masks[k] = grid.voxelize(m)
        print(f"[{time.time() - T0:5.0f}s] cavity {k}: {masks[k].sum() * VOX ** 3 / 1000:.0f} mL")
    labels = np.zeros(grid.shape, np.int8)
    for i, k in enumerate(CAVITIES, start=1):
        labels[masks[k] & (labels == 0)] = i
    blood = labels > 0

    # Wall = shell around cavities, thickness chosen by nearest chamber.
    dist, (ii, jj, kk) = ndimage.distance_transform_edt(~blood, sampling=VOX, return_indices=True)
    nearest = labels[ii, jj, kk]
    thick = np.zeros(grid.shape, np.float32)
    for i, k in enumerate(CAVITIES, start=1):
        thick[nearest == i] = WALL_THICKNESS[k]
    wall = (~blood) & (dist <= thick)
    for w in walls:
        wall |= grid.surface_mask(w, dilate=1) & ~blood
    wall = ndimage.binary_closing(wall, iterations=1) & ~blood
    wall_mesh = mask_to_mesh(grid, wall, sigma=1.1, target_faces=90000)
    print(f"[{time.time() - T0:5.0f}s] wall faces", len(wall_mesh.faces))

    # Cavity meshes sit a hair inside the wall surface to avoid z-fighting.
    cav_meshes = {k: mask_to_mesh(grid, labels == i, sigma=1.0, level=0.6, target_faces=12000)
                  for i, k in enumerate(CAVITIES, start=1)}

    # ---------------------------------------------------- flow centrelines
    lumen = blood.copy()
    for k in ("svc", "ivc", "aorta", "pulmonary_trunk", "pulmonary_arteries", "pulmonary_veins"):
        lumen |= grid.voxelize(vessels[k], thresh=0.3, max_faces=1500, reach_mm=14)
    for v in valves.values():
        lumen |= ndimage.binary_dilation(grid.surface_mask(v, dilate=0), iterations=3)
    lumen = ndimage.binary_closing(lumen, iterations=2)
    d_in = ndimage.distance_transform_edt(lumen, sampling=VOX)
    cost = np.where(lumen, 1.0 / (0.3 + d_in) ** 2, 1e4)

    def centroid(m):
        return m.center_mass if m.is_watertight else m.vertices.mean(0)

    def deepest(mask_k, frac_low=None):
        """Point deepest inside a chamber (optionally in its lower part, toward the apex)."""
        d = ndimage.distance_transform_edt(mask_k, sampling=VOX)
        if frac_low is not None:
            zs = np.nonzero(mask_k)[2]
            cut = np.percentile(zs, frac_low * 100)
            d[:, :, int(cut):] = 0
        return grid.to_world(np.unravel_index(np.argmax(d), d.shape))

    def vessel_end(mesh, direction):
        v = mesh.vertices
        tip = v[np.argmax(v @ np.asarray(direction, float))]
        near = v[np.linalg.norm(v - tip, axis=1) < 8]
        return near.mean(0)

    pv_ends = []
    for fj in VESSELS["pulmonary_veins"]:
        m = L(fj)
        c = m.vertices.mean(0)
        away = np.sign(c[0] - vessels["pulmonary_veins"].vertices[:, 0].mean()) * np.array([1.0, 0, 0])
        pv_ends.append((fj, vessel_end(m, away)))
    # keep the outermost segment per side
    left = max((p for p in pv_ends if p[1][0] > 20), key=lambda p: p[1][0])[1]
    right = min((p for p in pv_ends if p[1][0] < 20), key=lambda p: p[1][0])[1]

    wp = {
        "svc_top": vessel_end(vessels["svc"], [0, 0, 1]),
        "ivc_bottom": vessel_end(vessels["ivc"], [0, 0, -1]),
        "ra": deepest(masks["ra"]),
        "tricuspid": centroid(valves["tricuspid"]),
        "rv_apex": deepest(masks["rv"], frac_low=0.45),
        "pulmonary_valve": centroid(valves["pulmonary"]),
        "pa_right_end": vessel_end(vessels["pulmonary_arteries"], [-1, 0, 0]),
        "pa_left_end": vessel_end(vessels["pulmonary_arteries"], [1, 0, 0]),
        "pv_right_end": right,
        "pv_left_end": left,
        "la": deepest(masks["la"]),
        "mitral": centroid(valves["mitral"]),
        "lv_apex": deepest(masks["lv"], frac_low=0.45),
        "aortic_valve": centroid(valves["aortic"]),
        "aorta_end": vessel_end(vessels["aorta"], [0, 0, -1]),
    }
    arch = vessels["aorta"].vertices
    wp["aortic_arch_top"] = arch[np.argmax(arch[:, 2])] - np.array([0, 0, 8.0])

    def route(points):
        path = []
        for a, b in zip(points, points[1:]):
            idx, _ = route_through_array(cost, grid.to_index(wp[a]), grid.to_index(wp[b]),
                                         fully_connected=True, geometric=True)
            seg = grid.to_world(np.array(idx))
            path.extend(seg if not path else seg[1:])
        path = np.array(path)
        # light smoothing, then resample to evenly spaced points
        path = ndimage.gaussian_filter1d(path, 3, axis=0, mode="nearest")
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        t = np.linspace(0, s[-1], max(8, int(s[-1] / 4)))
        return np.stack([np.interp(t, s, path[:, k]) for k in range(3)], 1)

    routes = {
        "svc_to_pa_right": ["svc_top", "ra", "tricuspid", "rv_apex", "pulmonary_valve", "pa_right_end"],
        "ivc_to_pa_left": ["ivc_bottom", "ra", "tricuspid", "rv_apex", "pulmonary_valve", "pa_left_end"],
        "pv_right_to_aorta": ["pv_right_end", "la", "mitral", "lv_apex", "aortic_valve", "aortic_arch_top", "aorta_end"],
        "pv_left_to_aorta": ["pv_left_end", "la", "mitral", "lv_apex", "aortic_valve", "aortic_arch_top", "aorta_end"],
    }
    print(f"[{time.time() - T0:5.0f}s] lumen ready")
    route_pts = {k: route(v) for k, v in routes.items()}
    print(f"[{time.time() - T0:5.0f}s] routes traced")
    # Where along each route the blood passes each landmark (for valve timing / colouring).
    route_marks = {}
    for k, pts in route_pts.items():
        route_marks[k] = {w: float(np.argmin(np.linalg.norm(pts - wp[w], axis=1)) / (len(pts) - 1)) for w in routes[k]}

    # ---------------------------------------------------- coronaries
    cor_art, cor_vein = [], []
    skip = set(sum(VESSELS.values(), []))
    for fj, n in names.items():
        if fj in skip:
            continue
        if any(k in n for k in ("cardiac vein", "venous tree", "coronary sinus", "vein of left ventricle")):
            cor_vein.append(L(fj))
        elif "coronary artery" in n or n.startswith("right conus artery"):
            cor_art.append(L(fj))

    # ---------------------------------------------------- export
    center = np.array([m.bounds.mean(0) for m in cav.values()]).mean(0)

    def to_gl(p):
        p = (np.asarray(p, float) - center) / 100.0
        return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)

    def gl_mesh(m):
        m = m.copy()
        m.vertices = to_gl(m.vertices)
        m.fix_normals()
        return m

    scene = trimesh.Scene()
    scene.add_geometry(gl_mesh(wall_mesh), node_name="wall", geom_name="wall")
    for k, m in cav_meshes.items():
        scene.add_geometry(gl_mesh(m), node_name=f"cavity_{k}", geom_name=f"cavity_{k}")
    for k, m in valves.items():
        scene.add_geometry(gl_mesh(simplify(m, 5000)), node_name=f"valve_{k}", geom_name=f"valve_{k}")
    scene.add_geometry(gl_mesh(simplify(trimesh.util.concatenate([L(f) for f in PAPILLARY]), 3000)),
                       node_name="papillary", geom_name="papillary")
    for k, m in vessels.items():
        scene.add_geometry(gl_mesh(simplify(m, 8000)), node_name=f"vessel_{k}", geom_name=f"vessel_{k}")
    scene.add_geometry(gl_mesh(simplify(trimesh.util.concatenate(cor_art), 20000)), node_name="coronary_arteries",
                       geom_name="coronary_arteries")
    scene.add_geometry(gl_mesh(simplify(trimesh.util.concatenate(cor_vein), 8000)), node_name="coronary_veins",
                       geom_name="coronary_veins")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    glb = OUT_DIR / "heart.glb"
    glb.write_bytes(scene.export(file_type="glb"))

    anchors = {k: to_gl(v).round(4).tolist() for k, v in wp.items()}
    for k, m in cav_meshes.items():
        anchors[f"cavity_{k}"] = to_gl(deepest(labels == list(CAVITIES).index(k) + 1)).round(4).tolist()
    # Outer-surface anchors for exterior labels: nearest wall vertex to each chamber, from the front.
    landmarks = {
        "anchors": anchors,
        "routes": {k: to_gl(v).round(4).tolist() for k, v in route_pts.items()},
        "route_marks": route_marks,
        "wall_thickness_mm": WALL_THICKNESS,
        "source": "BodyParts3D, (c) The Database Center for Life Science, CC BY-SA 2.1 Japan",
    }
    (OUT_DIR / "landmarks.json").write_text(json.dumps(landmarks, indent=1))
    print(f"wrote {glb} ({glb.stat().st_size / 1e6:.1f} MB) and landmarks.json")


if __name__ == "__main__":
    main()
