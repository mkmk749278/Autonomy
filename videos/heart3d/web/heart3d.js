// Heart in 3D: one scene, two modes.
//   ?mode=render    deterministic frames for the video (window.renderAt(t))
//   (default)       interactive viewer with orbit controls and toggles
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { FXAAShader } from "three/addons/shaders/FXAAShader.js";

const params = new URLSearchParams(location.search);
const RENDER = params.get("mode") === "render";
const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
const ASSETS = params.get("assets") || (LOCAL ? "/assets/heart3d/" : "./");
const TIMELINE = params.get("timeline") || "/build/heart3d/timeline.json";

const C = {
  muscle: 0xb85a52, cap: 0xd98a80, right: 0x3a7bd5, left: 0xe63946, valve: 0xf5e6c8,
  artery: 0xe8474f, vein: 0x6f7fe0, accent: 0xffd166,
};
const CHAMBERS = ["ra", "rv", "la", "lv"];

// ----------------------------------------------------------------- helpers
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const ramp = (t, a, b) => smooth((t - a) / (b - a));
const window01 = (t, a, b, fade = 0.6) => Math.min(ramp(t, a, a + fade), 1 - ramp(t, b - fade, b));
const lerp = (a, b, u) => a + (b - a) * u;
const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);

// Cardiac cycle (same model as the 2D video): phase 0..1 per beat.
const PH = { atrial: 0.40, lub: 0.55, eject: 0.60, dub: 0.90 };
const r01 = (x, a, b) => clamp((x - a) / (b - a));
function ventricleSqueeze(p) {   // 0 = relaxed/full, 1 = fully contracted
  p = ((p % 1) + 1) % 1;
  if (p < PH.eject) return 0.1 * (1 - r01(p, 0, PH.lub)) ;
  if (p < PH.dub) return Math.sin(r01(p, PH.eject, PH.dub) * Math.PI / 2);
  return 1 - 0.9 * r01(p, PH.dub, 1.0);
}
function atriumSqueeze(p) {
  p = ((p % 1) + 1) % 1;
  if (p < PH.atrial) return 0;
  if (p < PH.lub) return Math.sin(r01(p, PH.atrial, PH.lub) * Math.PI);
  return 0;
}

// ----------------------------------------------------------------- shared shader uniforms
const shared = {
  uContract: { value: new THREE.Vector4() },
  uC: { value: [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()] },
};

function patch(mat, { cap = null, xrayMin = 0.06 } = {}) {
  const u = {
    uXray: { value: 0 }, uXrayMin: { value: xrayMin },
    uCap: { value: 0 }, uCapColor: { value: new THREE.Color(cap ?? mat.color) },
  };
  mat.userData.u = u;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, shared, u);
    sh.vertexShader = "attribute vec4 aW;\nuniform vec4 uContract;\nuniform vec3 uC[4];\n" + sh.vertexShader.replace(
      "#include <begin_vertex>",
      `#include <begin_vertex>
       vec3 disp = aW.x * (uC[0] - transformed) * uContract.x + aW.y * (uC[1] - transformed) * uContract.y
                 + aW.z * (uC[2] - transformed) * uContract.z + aW.w * (uC[3] - transformed) * uContract.w;
       transformed += disp;`);
    sh.fragmentShader = "uniform float uXray;\nuniform float uXrayMin;\nuniform float uCap;\nuniform vec3 uCapColor;\n" +
      sh.fragmentShader
        .replace("#include <clipping_planes_fragment>",
          `#include <clipping_planes_fragment>
           if (uCap > 0.5 && !gl_FrontFacing) { gl_FragColor = vec4(uCapColor, 1.0); return; }`)
        .replace("#include <opaque_fragment>",
          `#include <opaque_fragment>
           float fres = pow(1.0 - abs(dot(normalize(vViewPosition), normal)), 2.2);
           gl_FragColor.a = mix(gl_FragColor.a, clamp(uXrayMin + fres * 0.95, 0.0, 1.0) * gl_FragColor.a, uXray);`);
  };
  mat.customProgramCacheKey = () => "heartpatch";
  return mat;
}

// ----------------------------------------------------------------- scene
const stage = document.getElementById("stage");
const W = RENDER ? 1920 : innerWidth, H = RENDER ? 1080 : innerHeight;
const AA = params.get("aa") ? params.get("aa") !== "0" : !RENDER;   // CPU renders use FXAA instead of MSAA
const LITE = params.get("lite") ? params.get("lite") === "1" : RENDER;
const renderer = new THREE.WebGLRenderer({ antialias: AA, alpha: true, preserveDrawingBuffer: RENDER });
renderer.setPixelRatio(RENDER ? 1 : Math.min(devicePixelRatio, 2));
renderer.setSize(W, H);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.localClippingEnabled = true;
renderer.setClearColor(0x000000, 0);
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
if (params.get("env") !== "0") scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;
const camera = new THREE.PerspectiveCamera(30, W / H, 0.05, 50);
const key = new THREE.DirectionalLight(0xfff1e6, 2.4); key.position.set(2.5, 3.5, 4); scene.add(key);
const rim = new THREE.DirectionalLight(0x8fb8ff, 1.6); rim.position.set(-3, 1.5, -4); scene.add(rim);
scene.add(new THREE.HemisphereLight(0xdde6ff, 0x301a1a, 0.5));
camera.add(new THREE.PointLight(0xffffff, 0.8, 0, 0)); scene.add(camera);

const clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 100);

let composer = null;
if (!AA) {
  const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 0 });
  composer = new EffectComposer(renderer, rt);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new OutputPass());
  const fxaa = new ShaderPass(FXAAShader);
  fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
  composer.addPass(fxaa);
}
const draw = () => (composer ? composer.render() : renderer.render(scene, camera));

const M = {
  wall: patch(LITE
    ? new THREE.MeshStandardMaterial({ color: C.muscle, roughness: 0.42, side: THREE.DoubleSide, transparent: true })
    : new THREE.MeshPhysicalMaterial({ color: C.muscle, roughness: 0.52, clearcoat: 0.35, clearcoatRoughness: 0.35,
      sheen: 0.4, sheenColor: new THREE.Color(0xffb0a0), side: THREE.DoubleSide, transparent: true }), { cap: C.cap, xrayMin: 0.03 }),
  right: patch(new THREE.MeshStandardMaterial({ color: C.right, roughness: 0.35, emissive: C.right, emissiveIntensity: 0,
    side: THREE.DoubleSide, transparent: true }), { cap: 0x2d5fa8, xrayMin: 0.18 }),
  left: patch(new THREE.MeshStandardMaterial({ color: C.left, roughness: 0.35, emissive: C.left, emissiveIntensity: 0,
    side: THREE.DoubleSide, transparent: true }), { cap: 0xb82a36, xrayMin: 0.18 }),
  valve: patch(new THREE.MeshStandardMaterial({ color: C.valve, roughness: 0.6, emissive: C.accent, emissiveIntensity: 0,
    side: THREE.DoubleSide })),
  papillary: patch(new THREE.MeshStandardMaterial({ color: C.muscle, roughness: 0.6, side: THREE.DoubleSide })),
  arteryVessel: patch(new THREE.MeshStandardMaterial({ color: 0xc8404a, roughness: 0.45, side: THREE.DoubleSide,
    transparent: true }), { cap: 0xa0303a, xrayMin: 0.12 }),
  veinVessel: patch(new THREE.MeshStandardMaterial({ color: 0x4a74c0, roughness: 0.45, side: THREE.DoubleSide,
    transparent: true }), { cap: 0x335a9a, xrayMin: 0.12 }),
  coronaryArtery: patch(new THREE.MeshStandardMaterial({ color: C.artery, roughness: 0.35, emissive: C.artery,
    emissiveIntensity: 0, transparent: true })),
  coronaryVein: patch(new THREE.MeshStandardMaterial({ color: C.vein, roughness: 0.4, transparent: true })),
};
const clipped = [M.wall, M.right, M.left, M.valve, M.papillary, M.arteryVessel, M.veinVessel, M.coronaryArtery, M.coronaryVein];

const parts = {};        // node name -> mesh
let L = null;            // landmarks
let TL = null;           // timeline
const heart = new THREE.Group();
scene.add(heart);

function materialFor(name) {
  if (name === "wall") return M.wall;
  if (name === "cavity_ra" || name === "cavity_rv") return M.right;
  if (name === "cavity_la" || name === "cavity_lv") return M.left;
  if (name.startsWith("valve_")) return M.valve;
  if (name === "papillary") return M.papillary;
  if (["vessel_aorta", "vessel_pulmonary_veins"].includes(name)) return M.arteryVessel;
  if (name.startsWith("vessel_")) return M.veinVessel;
  if (name === "coronary_arteries") return M.coronaryArtery;
  if (name === "coronary_veins") return M.coronaryVein;
  return M.papillary;
}

// Per-vertex chamber weights (which chamber's contraction moves this vertex).
function assignWeights(mesh, centroidsWorld, cavityPts) {
  const g = mesh.geometry, pos = g.attributes.position, n = pos.count;
  const w = new Float32Array(n * 4);
  const name = mesh.name;
  const own = { cavity_ra: 0, cavity_rv: 1, cavity_la: 2, cavity_lv: 3 }[name];
  const deform = !name.startsWith("vessel_");
  const p = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    if (!deform) continue;
    if (own !== undefined) { w[i * 4 + own] = 1; continue; }
    p.fromBufferAttribute(pos, i);
    let sum = 0; const d = [0, 0, 0, 0];
    for (let c = 0; c < 4; c++) {
      let best = 1e9; const pts = cavityPts[c];
      for (let k = 0; k < pts.length; k += 3) {
        const dx = pts[k] - p.x, dy = pts[k + 1] - p.y, dz = pts[k + 2] - p.z;
        const dd = dx * dx + dy * dy + dz * dz; if (dd < best) best = dd;
      }
      d[c] = Math.exp(-best / (0.06 * 0.06)); sum += d[c];
    }
    for (let c = 0; c < 4; c++) w[i * 4 + c] = sum > 1e-6 ? d[c] / sum : 0;
  }
  g.setAttribute("aW", new THREE.BufferAttribute(w, 4));
}

// ----------------------------------------------------------------- blood particles
const flows = [];
function buildFlows() {
  const sprite = (() => {
    const cv = document.createElement("canvas"); cv.width = cv.height = 64;
    const x = cv.getContext("2d"); const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.35, "rgba(255,255,255,0.55)"); gr.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = gr; x.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(cv);
  })();
  const defs = [
    ["svc_to_pa_right", "right", C.right], ["ivc_to_pa_left", "right", 0x4f8ff0],
    ["pv_right_to_aorta", "left", C.left], ["pv_left_to_aorta", "left", 0xff5a64],
  ];
  for (const [key, side, color] of defs) {
    const pts = L.routes[key].map(V);
    const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
    const length = curve.getLength();
    const N = Math.round(length / 0.04);
    const samples = curve.getSpacedPoints(600);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    const mat = new THREE.PointsMaterial({ size: 0.12, map: sprite, vertexColors: true, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
    const pts3 = new THREE.Points(geo, mat);
    pts3.renderOrder = 5; pts3.frustumCulled = false;
    const core = new THREE.InstancedMesh(new THREE.SphereGeometry(0.021, 12, 8),
      new THREE.MeshBasicMaterial({ color, transparent: true, depthWrite: false }), N);
    core.renderOrder = 6; core.frustumCulled = false;
    heart.add(pts3, core);
    flows.push({ key, side, color: new THREE.Color(color), N, length, samples, pts3, core,
      jitter: Array.from({ length: N }, (_, i) => (Math.sin(i * 12.9898 + key.length) * 43758.5453) % 1 * 0.35 / N) });
  }
}
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3();
function updateFlows(t, vis, pulse) {
  const speed = 0.32, w = 2 * Math.PI / BEAT_T;
  const travel = speed * (t + pulse * Math.sin(w * t - 1.2) / w);
  for (const f of flows) {
    const v = vis[f.side] ?? 0;
    f.pts3.visible = f.core.visible = v > 0.01;
    if (!f.pts3.visible) continue;
    const pos = f.pts3.geometry.attributes.position, col = f.pts3.geometry.attributes.color;
    for (let i = 0; i < f.N; i++) {
      const a = (((travel / f.length + i / f.N + f.jitter[i]) % 1) + 1) % 1;
      const p = f.samples[Math.floor(a * (f.samples.length - 1))];
      const fade = clamp(Math.min(a, 1 - a) / 0.05) * v;
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, f.color.r * fade * 0.9, f.color.g * fade * 0.9, f.color.b * fade * 0.9);
      _s.setScalar(Math.max(fade, 1e-4));
      _m.compose(p, _q, _s); f.core.setMatrixAt(i, _m);
    }
    pos.needsUpdate = col.needsUpdate = true; f.core.instanceMatrix.needsUpdate = true;
    f.core.material.opacity = v;
  }
}

// ----------------------------------------------------------------- labels (HTML overlay)
const labelsEl = document.getElementById("labels"), linesEl = document.getElementById("lines");
const labelDefs = {};
function defineLabel(id, text, anchor, side, dy = 0, sub = "") {
  const el = document.createElement("div"); el.className = "label";
  el.innerHTML = text + (sub ? `<small>${sub}</small>` : "");
  labelsEl.appendChild(el);
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
  line.setAttribute("stroke", "rgba(232,238,244,0.85)"); line.setAttribute("stroke-width", "2.5");
  const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  dot.setAttribute("r", "5"); dot.setAttribute("fill", "#e8eef4");
  linesEl.append(line, dot);
  labelDefs[id] = { el, line, dot, anchor, side, dy };
}
const _p = new THREE.Vector3(), _c = new THREE.Vector3();
function labelBand(h) {
  // Keep labels between the page's info cards and its control bar when those exist.
  const hud = document.querySelector(".hud"), ui = document.getElementById("ui");
  const top = hud ? hud.getBoundingClientRect().bottom + 28 : h * 0.12;
  const bottom = ui && ui.offsetParent !== null && !RENDER ? ui.getBoundingClientRect().top - 28 : h * 0.8;
  return [Math.min(top, h * 0.5), Math.max(bottom, h * 0.55)];
}
function updateLabels(vis) {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  const [bandTop, bandBottom] = labelBand(h);
  for (const [id, d] of Object.entries(labelDefs)) {
    const o = vis[id] ?? 0;
    d.el.style.opacity = d.line.style.opacity = d.dot.style.opacity = o;
    if (o <= 0.001) { d.el.style.display = "none"; continue; }
    d.el.style.display = "";
    const a = typeof d.anchor === "function" ? d.anchor() : d.anchor;
    _p.copy(a).applyMatrix4(heart.matrixWorld).project(camera);
    const ax = (_p.x * 0.5 + 0.5) * w, ay = (-_p.y * 0.5 + 0.5) * h;
    let side = d.side;
    if (side === "A") { _c.set(0, 0, 0).project(camera); side = _p.x < _c.x ? "L" : "R"; }
    const bw = d.el.offsetWidth, colX = side === "L" ? w * 0.2 : w * 0.8;
    const lx = clamp(colX, bw / 2 + 12, w - bw / 2 - 12), ly = clamp(ay + d.dy * h, bandTop, bandBottom);
    d.el.style.left = `${lx}px`; d.el.style.top = `${ly}px`;
    const ex = lx + (side === "L" ? bw / 2 : -bw / 2);
    d.line.setAttribute("x1", ex); d.line.setAttribute("y1", ly);
    d.line.setAttribute("x2", ax); d.line.setAttribute("y2", ay);
    d.dot.setAttribute("cx", ax); d.dot.setAttribute("cy", ay);
  }
}

// ----------------------------------------------------------------- load
const BEAT_T = 1.0;  // seconds per beat (60 bpm)
let base = {};       // derived landmarks
async function load() {
  // Published pages get the model as base64 in JSON (hosts that don't serve .glb); local renders load the .glb.
  let gltf;
  if (LOCAL) {
    gltf = await new GLTFLoader().loadAsync(ASSETS + "heart.glb");
  } else {
    const b64 = (await (await fetch(ASSETS + "heart.glb.json")).json()).glb;
    const bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    gltf = await new GLTFLoader().parseAsync(bytes.buffer, "");
  }
  L = await (await fetch(ASSETS + "landmarks.json")).json();
  if (RENDER) TL = await (await fetch(TIMELINE)).json();
  gltf.scene.traverse((o) => { if (o.isMesh) parts[o.name] = o; });
  const cavityPts = CHAMBERS.map((c) => {
    const pos = parts[`cavity_${c}`].geometry.attributes.position; const out = [];
    for (let i = 0; i < pos.count; i += 6) out.push(pos.getX(i), pos.getY(i), pos.getZ(i));
    return out;
  });
  CHAMBERS.forEach((c, i) => shared.uC.value[i].copy(V(L.anchors[`cavity_${c}`])));
  for (const [name, mesh] of Object.entries(parts)) {
    mesh.geometry.computeVertexNormals();
    mesh.material = materialFor(name);
    assignWeights(mesh, null, cavityPts);
  }
  parts.wall.renderOrder = 10;
  for (const n of ["cavity_ra", "cavity_rv", "cavity_la", "cavity_lv"]) parts[n].renderOrder = 2;
  for (const n of Object.keys(parts)) if (n.startsWith("vessel_")) parts[n].renderOrder = 3;
  heart.add(gltf.scene);
  for (const m of clipped) m.clippingPlanes = [clipPlane];

  // Derived geometry: 4-chamber plane, valve plane, wall-thickness anchors.
  const tri = V(L.anchors.tricuspid), mit = V(L.anchors.mitral), apex = V(L.anchors.lv_apex);
  const valveC = ["tricuspid", "mitral", "pulmonary_valve", "aortic_valve"].map((k) => V(L.anchors[k]))
    .reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(0.25);
  let n4 = new THREE.Vector3().crossVectors(mit.clone().sub(tri), apex.clone().sub(tri)).normalize();
  if (n4.z < 0) n4.negate();
  const baseDir = valveC.clone().sub(apex).normalize();
  base = { tri, mit, apex, valveC, n4, baseDir, center: new THREE.Vector3(0, 0, 0) };
  heart.updateMatrixWorld(true);
  const ray = new THREE.Raycaster();
  const wallHits = (from, dir) => {
    ray.set(from, dir.clone().normalize()); ray.far = 2;
    return ray.intersectObject(parts.wall, false).map((h) => h.point);
  };
  const inPlane = (v) => v.clone().sub(n4.clone().multiplyScalar(v.dot(n4)));
  const lvC = V(L.anchors.cavity_lv), rvC = V(L.anchors.cavity_rv);
  const lateral = inPlane(mit.clone().sub(tri)).normalize();
  const mid = (hs) => (hs.length >= 2 ? hs[0].clone().add(hs[1]).multiplyScalar(0.5) : hs[0] || new THREE.Vector3());
  const planeProj = (v) => v.clone().sub(n4.clone().multiplyScalar(v.clone().sub(tri).dot(n4)));
  base.lvWall = mid(wallHits(planeProj(lvC), lateral));
  base.rvWall = mid(wallHits(planeProj(rvC), lateral.clone().negate()));
  base.septum = mid(wallHits(planeProj(lvC), planeProj(rvC).sub(planeProj(lvC))));

  const A = (k) => V(L.anchors[k]);
  defineLabel("aorta", "Aorta", A("aortic_arch_top"), "R", -0.02);
  defineLabel("pulm_trunk", "Pulmonary trunk", () => A("pulmonary_valve").lerp(A("pa_left_end"), 0.35), "R", 0.10);
  defineLabel("svc", "Superior vena cava", A("svc_top"), "L", 0.0);
  defineLabel("coronary", "Coronary arteries", () => A("cavity_lv").lerp(A("lv_apex"), 0.6).add(new THREE.Vector3(0.05, 0, 0.35)), "R", 0.12, "feed the heart muscle");
  defineLabel("ra", "Right atrium", A("cavity_ra"), "A", -0.06, "oxygen-poor");
  defineLabel("rv", "Right ventricle", A("cavity_rv"), "A", 0.08, "oxygen-poor");
  defineLabel("la", "Left atrium", A("cavity_la"), "A", -0.08, "oxygen-rich");
  defineLabel("lv", "Left ventricle", A("cavity_lv"), "A", 0.08, "oxygen-rich");
  defineLabel("v_tri", "Tricuspid valve", A("tricuspid"), "A", 0.07);
  defineLabel("v_pul", "Pulmonary valve", A("pulmonary_valve"), "A", -0.17);
  defineLabel("v_mit", "Mitral valve", A("mitral"), "A", 0.07);
  defineLabel("v_aor", "Aortic valve", A("aortic_valve"), "A", -0.05);
  defineLabel("from_body", "from the body", A("svc_top"), "L", -0.02);
  defineLabel("to_lungs", "to the lungs", A("pa_right_end"), "L", 0.02);
  defineLabel("from_lungs", "from the lungs", A("pv_left_end"), "R", 0.04);
  defineLabel("to_body", "to the body", A("aortic_arch_top"), "R", -0.06);
  defineLabel("lv_wall", "Left ventricle wall", () => base.lvWall, "R", 0.0, "≈10 mm");
  defineLabel("rv_wall", "Right ventricle wall", () => base.rvWall, "L", 0.0, "≈4 mm");
  defineLabel("septum", "Septum", () => base.septum, "R", 0.2);

  buildFlows();
  document.getElementById("loading")?.remove();
}

// ----------------------------------------------------------------- state -> scene
function applyState(S) {
  // camera
  const cp = S.camPos, ct = S.camTarget;
  camera.position.copy(cp); camera.up.set(0, 1, 0); camera.lookAt(ct); camera.updateMatrixWorld(true);
  // heartbeat
  const p = S.beatPhase, amp = S.beatAmp;
  const v = ventricleSqueeze(p) * 0.13 * amp, a = atriumSqueeze(p) * 0.10 * amp;
  shared.uContract.value.set(a, v, a, v);
  // x-ray / fades
  M.wall.userData.u.uXray.value = S.wallX;
  M.wall.depthWrite = S.wallX < 0.02;
  for (const m of [M.right, M.left]) {
    m.userData.u.uXray.value = S.cavX; m.depthWrite = S.cavX < 0.02; m.emissiveIntensity = 0.55 * S.cavX;
  }
  for (const m of [M.arteryVessel, M.veinVessel]) {
    m.userData.u.uXray.value = S.vesX; m.depthWrite = S.vesX < 0.02 && S.vesFade > 0.99;
    m.opacity = S.vesFade; m.visible = S.vesFade > 0.01;
  }
  M.coronaryArtery.opacity = M.coronaryVein.opacity = 1 - S.wallX;
  M.coronaryArtery.visible = M.coronaryVein.visible = S.wallX < 0.98;
  M.coronaryArtery.emissiveIntensity = 0.7 * S.coronaryGlow;
  M.valve.emissiveIntensity = 0.9 * S.valveGlow;
  // clipping
  clipPlane.normal.copy(S.clipN); clipPlane.constant = S.clipD;
  for (const m of clipped) m.userData.u.uCap.value = S.cap;
  for (const m of [M.right, M.left]) m.userData.u.uCap.value = S.cavX < 0.05 ? S.cap : 0;
  for (const m of [M.arteryVessel, M.veinVessel]) m.userData.u.uCap.value = S.vesX < 0.05 ? S.cap : 0;
  // flow + labels
  updateFlows(S.t, { right: S.flowR, left: S.flowL }, S.pulse);
  heart.updateMatrixWorld(true);
  updateLabels(S.labels);
  // overlays
  setOverlay(S);
}

let lastOverlay = "";
function setOverlay(S) {
  const key = JSON.stringify([S.tag, S.titleO.toFixed(2), S.creditsO.toFixed(2)]);
  if (key === lastOverlay) return; lastOverlay = key;
  if (!document.getElementById("tag")) return;
  document.getElementById("tag").innerHTML = S.tag ? `<b>${S.tag[0]}</b>${S.tag[1].toUpperCase()}` : "";
  const t = document.getElementById("title");
  t.innerHTML = `<h1>The Heart in 3D</h1><p>A real human heart, explored from the outside in</p>`;
  t.style.opacity = S.titleO;
  const c = document.getElementById("credits");
  c.innerHTML = `<div class="big">Made entirely with free, open-source tools</div>
    <div>3D anatomy: BodyParts3D © DBCLS (CC BY-SA 2.1 JP) · three.js · Piper TTS · FFmpeg</div>
    <div class="small">Simplified for learning. Colours follow textbook convention. Not medical advice.</div>`;
  c.style.opacity = S.creditsO;
}

// ----------------------------------------------------------------- choreography (render mode)
function orbit(target, az, el, dist) {
  const a = THREE.MathUtils.degToRad(az), e = THREE.MathUtils.degToRad(el);
  return target.clone().add(new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).multiplyScalar(dist));
}
function dirToAzEl(d) {
  return [THREE.MathUtils.radToDeg(Math.atan2(d.x, d.z)), THREE.MathUtils.radToDeg(Math.asin(clamp(d.y, -1, 1)))];
}

function stateAt(t) {
  const sh = Object.fromEntries(TL.shots.map((s) => [s.id, s]));
  const at = (id, k = 0) => sh[id].sentences[Math.min(k, sh[id].sentences.length - 1)].start;
  const st = (id) => sh[id].start, en = (id) => sh[id].end;
  const tgt = new THREE.Vector3(0, 0.05, 0), low = new THREE.Vector3(0, 0.32, 0);

  // camera keyframes: [time, az, el, dist, target]
  const [vAz, vEl] = dirToAzEl(base.baseDir);
  const [sAz, sEl] = dirToAzEl(base.n4);
  const K = [
    [st("intro"), -35, 8, 5.6, low], [en("intro") - 1, 25, 10, 4.8, low],
    [at("exterior", 1), 10, 14, 4.2, tgt], [at("exterior", 4), -10, 6, 4.0, tgt], [en("exterior"), 0, 4, 4.2, tgt],
    [at("xray", 1), 0, 6, 4.3, tgt], [at("xray", 2) + 0.5, -40, 8, 4.2, tgt], [at("xray", 3) - 0.2, -30, 8, 4.2, tgt],
    [at("xray", 3) + 2.0, 100, 12, 4.2, tgt], [en("xray"), 112, 14, 4.2, tgt],
    [at("valves", 0) + 1.5, vAz, Math.min(vEl, 70), 3.2, base.valveC], [en("valves"), vAz + 12, Math.min(vEl, 70), 3.0, base.valveC],
    [at("flow", 0) + 1.5, -8, 6, 4.4, tgt], [en("flow"), 14, 8, 4.4, tgt],
    [st("beat") + 2, 20, 10, 4.0, tgt], [en("beat"), -15, 6, 4.1, tgt],
    [at("section", 0) + 1.0, sAz, sEl, 4.0, tgt], [en("section"), sAz + 6, sEl + 2, 3.8, tgt],
    [st("outro") + 1.5, -30, 10, 5.2, tgt], [en("outro"), 40, 12, 5.6, tgt],
  ];
  let i = 0; while (i < K.length - 2 && t > K[i + 1][0]) i++;
  const [t0, a0, e0, d0, g0] = K[i], [t1, a1, e1, d1, g1] = K[i + 1];
  const u = smooth((t - t0) / Math.max(1e-3, t1 - t0));
  let da = a1 - a0; while (da > 180) da -= 360; while (da < -180) da += 360;
  const target = g0.clone().lerp(g1, u);
  const camPos = orbit(target, a0 + da * u, lerp(e0, e1, u), lerp(d0, d1, u));

  // x-ray and flow
  const xOn = ramp(t, at("xray", 0) + 0.3, at("xray", 1));
  const xOff = ramp(t, at("section", 0) - 1.5, at("section", 0));
  const valveShot = window01(t, st("valves") + 0.4, en("valves") - 0.3, 1.2);
  const wallX = clamp(xOn * (1 - xOff) * (1 - valveShot));
  const flowOn = ramp(t, at("flow", 1) - 0.5, at("flow", 1) + 0.5) * (1 - ramp(t, en("beat") - 1, en("beat")));
  const flowR = flowOn * (t < at("flow", 2) ? 1 : 1);
  const flowL = ramp(t, at("flow", 2) - 0.5, at("flow", 2) + 0.5) * (1 - ramp(t, en("beat") - 1, en("beat")));
  const cavX = Math.max(clamp(ramp(t, at("flow", 0), at("flow", 1)) * (1 - xOff)), 0.75 * valveShot);
  const vesX = cavX;

  // clipping: valve plane (remove atria from above) then 4-chamber section
  let clipN = new THREE.Vector3(0, 0, -1), clipD = 100, cap = 0;
  if (valveShot > 0) {
    clipN = base.baseDir.clone().negate();
    const d0v = -clipN.dot(base.valveC);           // plane through valve centre
    clipD = lerp(d0v + 1.2, d0v + 0.08, valveShot);
    cap = 1;
  }
  const secU = window01(t, at("section", 0), en("section") + 5, 1.8);
  if (secU > 0) {
    clipN = base.n4.clone().negate();
    const d0s = -clipN.dot(base.tri);
    clipD = lerp(d0s + 1.2, d0s, secU);
    cap = 1;
  }

  const beatAmp = Math.max(0.35 * (1 - valveShot) * (1 - secU),
    window01(t, st("beat"), en("beat"), 1.0));
  const labels = {
    aorta: window01(t, at("exterior", 1), en("exterior")), pulm_trunk: window01(t, at("exterior", 2), en("exterior")),
    svc: window01(t, at("exterior", 3), en("exterior")), coronary: window01(t, at("exterior", 4), en("exterior")),
    ra: window01(t, at("xray", 2) + 0.4, at("xray", 3) + 0.4), rv: window01(t, at("xray", 2) + 0.4, at("xray", 3) + 0.4),
    la: window01(t, at("xray", 3) + 1.8, en("xray")), lv: window01(t, at("xray", 3) + 1.8, en("xray")),
    v_tri: window01(t, at("valves", 1), en("valves")), v_mit: window01(t, at("valves", 1), en("valves")),
    v_pul: window01(t, at("valves", 2), en("valves")), v_aor: window01(t, at("valves", 2), en("valves")),
    from_body: window01(t, at("flow", 1), at("flow", 2) + 1), to_lungs: window01(t, at("flow", 1) + 3, at("flow", 2) + 1),
    from_lungs: window01(t, at("flow", 2), en("flow")), to_body: window01(t, at("flow", 2) + 4, en("flow")),
    lv_wall: window01(t, at("section", 1), en("section")), rv_wall: window01(t, at("section", 1) + 1.5, en("section")),
    septum: window01(t, at("section", 1) + 3, en("section")),
  };
  const tags = [["intro", null], ["exterior", ["01", "The outside"]], ["xray", ["02", "Four chambers"]],
    ["valves", ["03", "Four valves"]], ["flow", ["04", "The path of blood"]], ["beat", ["05", "The heartbeat"]],
    ["section", ["06", "Cross-section"]], ["outro", null]];
  let tag = null; for (const [id, tg] of tags) if (t >= st(id)) tag = tg;
  const beatPhase = t / BEAT_T;
  const bp = ((beatPhase % 1) + 1) % 1;
  const valveGlowBeat = window01(t, st("beat"), en("beat"), 0.5) *
    (Math.exp(-Math.pow((bp - PH.lub) / 0.04, 2)) + Math.exp(-Math.pow((bp - PH.dub) / 0.04, 2)));
  return {
    t, camPos, camTarget: target, beatPhase, beatAmp, pulse: 0.6,
    wallX, cavX, vesX, flowR, flowL, clipN, clipD, cap, vesFade: (1 - valveShot) * (1 - secU),
    coronaryGlow: window01(t, at("exterior", 4), en("exterior")),
    valveGlow: Math.max(valveShot * 0.5, valveGlowBeat),
    labels, tag, titleO: window01(t, 0.3, en("intro") - 0.5, 1.0), creditsO: ramp(t, st("outro") + 0.8, st("outro") + 2),
  };
}

// ----------------------------------------------------------------- interactive mode
function interactive() {
  document.body.classList.add("interactive");
  // Fit the heart's ~1.3-unit width on narrow portrait screens too.
  const view = () => Math.max(4.6, 0.75 / (Math.tan(THREE.MathUtils.degToRad(15)) * (innerWidth / innerHeight)));
  camera.position.copy(orbit(new THREE.Vector3(0, 0.05, 0), -20, 8, view()));
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.05, 0); controls.enableDamping = true; controls.minDistance = 1.5; controls.maxDistance = 14;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const st = { xray: false, flow: false, beat: !reduced, labels: true, cut: 0 };
  const ui = document.getElementById("ui"); ui.style.display = "flex";
  let buttons = [...ui.querySelectorAll("[data-toggle]")];
  if (!buttons.length) {
    for (const [k, label] of [["xray", "X-ray"], ["flow", "Blood flow"], ["beat", "Heartbeat"], ["labels", "Labels"]]) {
      const b = document.createElement("button"); b.dataset.toggle = k; b.textContent = label; ui.appendChild(b); buttons.push(b);
    }
    const lab = document.createElement("label"); lab.textContent = "Slice";
    const r = document.createElement("input"); r.type = "range"; r.id = "slice"; r.min = 0; r.max = 1; r.step = 0.01; r.value = 0;
    lab.appendChild(r); ui.appendChild(lab);
  }
  const slider = ui.querySelector("#slice");
  const noteEl = document.getElementById("note");
  const note = () => {
    if (!noteEl) return;
    noteEl.textContent = st.cut > 0.05
      ? "Sliced through all four chambers. The left ventricle wall (about 10 mm) is much thicker than the right (about 4 mm)."
      : st.flow ? "Blue: body → right atrium → right ventricle → lungs. Red: lungs → left atrium → left ventricle → aorta."
      : st.xray ? "The muscle is see-through. Blue chambers hold oxygen-poor blood, red chambers oxygen-rich blood."
      : "Drag to rotate, pinch or scroll to zoom. Red vessels on the surface are the coronary arteries.";
  };
  const sync = () => { for (const b of buttons) b.setAttribute("aria-pressed", String(st[b.dataset.toggle])); note(); };
  for (const b of buttons) b.addEventListener("click", () => { st[b.dataset.toggle] = !st[b.dataset.toggle]; sync(); });
  slider.addEventListener("input", () => { st.cut = +slider.value; note(); });
  sync();
  const sm = { wallX: 0, cavX: 0, flow: 0, beat: st.beat ? 1 : 0, lab: 1 };
  const clock = new THREE.Clock();
  const resize = () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
  };
  addEventListener("resize", resize); resize();
  renderer.setAnimationLoop(() => {
    const t = clock.getElapsedTime(), k = 0.08, cutting = st.cut > 0.02;
    sm.wallX += ((st.xray || st.flow) && !cutting ? 1 - sm.wallX : -sm.wallX) * k;
    sm.cavX += (st.flow && !cutting ? 1 - sm.cavX : -sm.cavX) * k;
    sm.flow += ((st.flow ? 1 : 0) - sm.flow) * k;
    sm.beat += ((st.beat ? 1 : 0) - sm.beat) * k;
    sm.lab += ((st.labels ? 1 : 0) - sm.lab) * k;
    controls.update();
    const n = base.n4.clone().negate(), d0 = -n.dot(base.tri);
    const inside = sm.wallX > 0.5 || cutting ? 1 : 0;
    const cutLabels = sm.lab * (st.cut > 0.6 ? 1 : 0);
    applyState({
      t, camPos: camera.position.clone(), camTarget: controls.target.clone(), beatPhase: t / BEAT_T,
      beatAmp: 0.8 * sm.beat * (cutting ? 0 : 1), pulse: 0.6, wallX: sm.wallX, cavX: sm.cavX, vesX: sm.cavX,
      flowR: sm.flow, flowL: sm.flow, vesFade: cutting ? 1 - st.cut : 1, clipN: n,
      clipD: cutting ? lerp(d0 + 1.2, d0, st.cut) : 100, cap: cutting ? 1 : 0,
      coronaryGlow: 0, valveGlow: 0, tag: null, titleO: 0, creditsO: 0,
      labels: { ra: sm.lab * inside * (1 - cutLabels), rv: sm.lab * inside * (1 - cutLabels),
        la: sm.lab * inside * (1 - cutLabels), lv: sm.lab * inside * (1 - cutLabels),
        aorta: sm.lab * (1 - inside), svc: sm.lab * (1 - inside), pulm_trunk: sm.lab * (1 - inside),
        lv_wall: cutLabels, rv_wall: cutLabels, septum: cutLabels },
    });
    renderer.render(scene, camera);
  });
}

// ----------------------------------------------------------------- boot
await load();
if (RENDER) {
  window.duration = TL.duration;
  window.renderAt = (t) => { applyState(stateAt(t)); draw(); return true; };
  window.timeFrame = (t) => {   // profiling: CPU state update vs GPU render (forced sync)
    const gl = renderer.getContext(), px = new Uint8Array(4);
    const a = performance.now(); applyState(stateAt(t)); const b = performance.now();
    draw(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); const c = performance.now();
    return [b - a, c - b];
  };
  window.ready = true;
} else {
  interactive();
}
