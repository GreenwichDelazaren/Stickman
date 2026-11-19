// The website's page side: draws what bridge.py's frame() returns with Three.js and sends it the
// input. The posing, exercises and exports are the desktop app's own Python modules, run by Pyodide.
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.mjs";

// Toolbar groups as main.TOOLBAR: icon (icons.ICONS name), tooltip (English, translated by i18n), and
// either an action (a key's action, see keyAction) with an optional forced Shift, or a drag mode.
const TOOLBAR = [  // File, Document, Edit, Drag, Joint, Figure, View, Help (as TABS)
  [{ icon: "open", tip: "Open a pose (Ctrl+O)", action: "open" },
   { icon: "save", tip: "Save the pose (Ctrl+S)", action: "save" },
   { icon: "png", tip: "Export a PNG image (Ctrl+E)", action: "png" },
   { icon: "copy", tip: "Copy as a picture for Word or PowerPoint (Ctrl+C)", action: "copy" },
   { icon: "save_shapes", tip: "Download as editable shapes for PowerPoint or Word, .pptx (Ctrl+Shift+S)", action: "pptx" },
   { icon: "save_3d", tip: "Export a 3D model file, .glb (Ctrl+Shift+E)", action: "glb" }],
  [{ icon: "add_to_document", tip: "Add the figure to the document (N)", action: "add_to_document" },
   { icon: "document", tip: "Document Composer: arrange, preview and export (V)", action: "composer" }],
  [{ icon: "undo", tip: "Undo (Ctrl+Z)", action: "undo" },
   { icon: "redo", tip: "Redo (Ctrl+Y)", action: "redo" },
   { icon: "reset", tip: "Reset the pose (R)", action: "reset" },
   { icon: "ground", tip: "Put the figure on the floor (G)", action: "ground" },
   { icon: "limits", tip: "Realistic joint limits on / off (L)", action: "limits" }],
  [{ icon: "drag_screen", tip: "Drag joints parallel to the screen", mode: "screen" },
   { icon: "drag_floor", tip: "Drag joints parallel to the floor (or hold Ctrl while dragging)", mode: "floor" },
   { icon: "drag_vertical", tip: "Drag joints straight up / down (or hold Shift while dragging)", mode: "vertical" }],
  [{ icon: "pin", tip: "Pin / unpin the selected joint (P)", action: "pin" },
   { icon: "unpin", tip: "Unpin all joints (Shift+P)", action: "pin", shift: true },
   { icon: "mirror", tip: "Copy the selected side onto the other side (M)", action: "mirror" },
   { icon: "twist_minus", tip: "Twist the selected joint one way (Z, Shift-click: 5 deg)", action: "twist_minus" },
   { icon: "twist_plus", tip: "Twist the selected joint the other way (X, Shift-click: 5 deg)", action: "twist_plus" }],
  [{ icon: "move_up", tip: "Raise the figure (Up arrow, Shift-click: 1 cm)", action: "move_up" },
   { icon: "move_down", tip: "Lower the figure (Down arrow, Shift-click: 1 cm)", action: "move_down" },
   { icon: "turn_left", tip: "Turn the figure to its left (Q, Shift-click: 5 deg)", action: "turn_left" },
   { icon: "turn_right", tip: "Turn the figure to its right (E, Shift-click: 5 deg)", action: "turn_right" },
   { icon: "tip_forward", tip: "Tip the figure forward (W, Shift-click: 5 deg)", action: "tip_forward" },
   { icon: "tip_back", tip: "Tip the figure back (S, Shift-click: 5 deg)", action: "tip_back" },
   { icon: "lean_left", tip: "Lean the figure to its left (A, Shift-click: 5 deg)", action: "lean_left" },
   { icon: "lean_right", tip: "Lean the figure to its right (D, Shift-click: 5 deg)", action: "lean_right" }],
  [{ icon: "view_front", tip: "Front view (1)", action: "view_front" },
   { icon: "view_side", tip: "Side view (2)", action: "view_side" },
   { icon: "view_top", tip: "Top view (3)", action: "view_top" },
   { icon: "view_angled", tip: "Angled view (4)", action: "view_angled" },
   { icon: "centre", tip: "Centre the view on the figure (F)", action: "centre" },
   { icon: "zoom_in", tip: "Zoom in (+ or mouse wheel)", action: "zoom_in" },
   { icon: "zoom_out", tip: "Zoom out (- or mouse wheel)", action: "zoom_out" },
   { icon: "floor_grid", tip: "Show / hide the floor and grid (B)", action: "floor_grid" }],
  [{ icon: "help", tip: "Show / hide the help (H)", action: "help" },
   { icon: "info", tip: "About Stickman (I)", action: "info" },
   { icon: "language", tip: "Language: English. Switch to Greek (T)", action: "language" }],

];
// The buttons to the right of the exercise list (main.MENU_STEPS).
const MENU_STEPS = [{ icon: "exercise_previous", tip: "Previous exercise (Page Up)", action: "exercise_previous" },
                    { icon: "exercise_next", tip: "Next exercise (Page Down)", action: "exercise_next" }];

const KEYS = {
  KeyH: "help", KeyI: "info", KeyT: "language", Tab: "menu", Escape: "escape", KeyP: "pin", KeyM: "mirror",
  KeyZ: "twist_minus", KeyX: "twist_plus", KeyL: "limits", KeyG: "ground", KeyR: "reset",
  KeyQ: "turn_left", KeyE: "turn_right", KeyW: "tip_forward", KeyS: "tip_back", KeyA: "lean_left", KeyD: "lean_right",
  ArrowUp: "move_up", ArrowDown: "move_down", KeyF: "centre", KeyB: "floor_grid", KeyN: "add_to_document", KeyV: "composer", PageUp: "exercise_previous", PageDown: "exercise_next",
  Digit1: "view_front", Digit2: "view_side", Digit3: "view_top", Digit4: "view_angled",
  Numpad1: "view_front", Numpad2: "view_side", Numpad3: "view_top", Numpad4: "view_angled",
  Equal: "zoom_in", NumpadAdd: "zoom_in", Minus: "zoom_out", NumpadSubtract: "zoom_out",
};
// Held keys and buttons repeat (main.REPEAT_KEYS / REPEAT_CTRL_KEYS) after REPEAT_DELAY, every REPEAT_INTERVAL ms.
const REPEAT = new Set(["turn_left", "turn_right", "tip_forward", "tip_back", "lean_left", "lean_right",
                        "move_up", "move_down", "zoom_in", "zoom_out", "twist_minus", "twist_plus", "undo", "redo"]);
const SHIFT_STEPS = new Set([...REPEAT].filter((a) => a !== "undo" && a !== "redo"));  // Shift-click: small steps
const REPEAT_DELAY = 400, REPEAT_INTERVAL = 80, MESSAGE_TIME = 4000;
const MENU_PLACEHOLDER = "Choose an exercise (Tab)", MENU_TWO = "2 positions";

// On a touch screen the groups of TOOLBAR (by index) go under tabs, so the buttons can be big enough for
// a finger and still leave room for the figure. Undo and redo stay on the tabs' row.
const TABS = [{ icon: "open", tip: "File", groups: [0, 7] }, { icon: "document", tip: "Document", groups: [1] },
              { icon: "reset", tip: "Edit", groups: [2] }, { icon: "drag_screen", tip: "Drag", groups: [3] },
              { icon: "pin", tip: "Joint", groups: [4] }, { icon: "turn_left", tip: "Figure", groups: [5] },
              { icon: "view_angled", tip: "View", groups: [6] }];
const ALWAYS_SHOWN = new Set(["undo", "redo"]);
const TIP_TIME = 1500;       // how long pressing a button shows its name on a touch screen
const PINCH_HOLD = 200;      // ms: a second finger this soon after the first makes a pinch, even from a joint
const ZOOM_STEP = -Math.log(0.9);  // scene.Camera.zoom multiplies the distance by 0.9 per step
const AUTOSAVE_KEY = "stickman-pose", AUTOSAVE_DOCS_KEY = "stickman-documents";

const $ = (id) => document.getElementById(id);
const coarse = window.matchMedia("(pointer: coarse)").matches;  // a phone or tablet
const host = window.StickmanHost;  // the Android app (android/.../MainActivity.kt), which saves and shares files
// "?v=<build>": web/build.py puts it on app.js in index.html, and app.js puts it on the files it loads, so a
// browser never mixes a cached file of one build with another's.
const V = new URL(import.meta.url).search;
const canvas = $("view");
let py, app, C;            // Pyodide, bridge.app, bridge colours
const tr = (text) => app.tr(text);

// --- start -----------------------------------------------------------------------

async function start() {
  // The marks are for timing a start: performance.getEntriesByType("mark").
  performance.mark("libraries loaded");
  py = await loadPyodide();
  performance.mark("Python started");
  await py.loadPackage("numpy");
  performance.mark("numpy loaded");
  const files = await (await fetch("py/files.json" + V)).json();
  py.FS.mkdirTree("/stickman");
  py.FS.mkdirTree("/stickman/fonts");
  await Promise.all(files.map(async (name) => {
    const response = await fetch("py/" + name + V);
    if (!response.ok) throw new Error(`py/${name}: ${response.status}`);
    const binary = !name.endsWith(".py");  // the fonts (and their licence)
    py.FS.writeFile("/stickman/" + name, binary ? new Uint8Array(await response.arrayBuffer()) : await response.text());
  }));
  py.runPython("import sys; sys.path.insert(0, '/stickman')");
  app = py.pyimport("bridge").app;
  performance.mark("modules imported");
  app.set_touch(coarse);
  C = JSON.parse(app.colors());
  await makeTattoo();
  performance.mark("tattoo drawn");
  setupScene();
  performance.mark("scene set up");
  buildToolbar();
  setupMenu();
  setupInput();
  for (const box of document.querySelectorAll(".panel")) {  // the OK buttons of the help and info boxes
    const ok = box.querySelector(".ok");
    ok.addEventListener("pointerdown", (e) => { if (e.button === 0) { e.preventDefault(); doAction("close_panel"); } });
    ok.addEventListener("click", (e) => { if (e.detail === 0) doAction("close_panel"); });  // keyboard
  }
  setupComposer();
  resize();
  if (host) restorePose();
  if (host) window.stickmanOpened = takeOpened;
  takeOpened();  // a file picked while Android had closed the app behind the file dialog
  $("loading").remove();
  performance.mark("ready");
  window.stickman = { py, app, renderJob, toggleComposer };  // for testing from the browser console or Playwright
  requestAnimationFrame(tick);
}

start().catch((error) => {
  console.error(error);
  const box = $("loading");
  box.classList.add("error");
  $("loading-text").textContent = "Δεν ήταν δυνατή η εκκίνηση / Could not start:\n" + error;
});

// --- drawing ---------------------------------------------------------------------

let renderer, scene, camera, floor, grid, figureGroup, shadowGroup, propGroup, propShadowGroup, tattooTexture;
const materials = new Map();
const geometries = {};
let dirty = true;             // draw a new frame
let lastFrame = null;

function color(rgb) {
  return new THREE.Color(rgb[0], rgb[1], rgb[2]);
}

function lit(rgb) {
  const key = "lit" + rgb.join(",");
  if (!materials.has(key)) {
    // The desktop's fixed-function lighting: specular 0.35 x 0.25, shininess 40 (Three's Blinn-Phong is ~4x stronger).
    materials.set(key, new THREE.MeshPhongMaterial({ color: color(rgb), specular: new THREE.Color(0.022, 0.022, 0.022),
                                                     shininess: 40, side: THREE.DoubleSide }));
  }
  return materials.get(key);
}

function flat(rgb) {
  const key = "flat" + rgb.join(",");
  if (!materials.has(key)) materials.set(key, new THREE.MeshBasicMaterial({ color: color(rgb) }));
  return materials.get(key);
}

function setupScene() {
  // Colours as the desktop's OpenGL: no colour management, lighting on the sRGB values.
  THREE.ColorManagement.enabled = false;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  scene = new THREE.Scene();
  scene.background = color(C.background);
  camera = new THREE.PerspectiveCamera();
  camera.matrixAutoUpdate = false;
  camera.matrixWorldAutoUpdate = false;

  // main._init_gl: ambient 0.35 + 0.15, diffuse 0.75 (Three's lights are divided by pi).
  scene.add(new THREE.AmbientLight(0xffffff, 0.5 * Math.PI));
  const light = new THREE.DirectionalLight(0xffffff, 0.75 * Math.PI);
  light.position.set(...C.light);
  scene.add(light);

  const half = C.floor_half;
  floor = new THREE.Mesh(new THREE.PlaneGeometry(2 * half, 2 * half).rotateX(-Math.PI / 2),
                         new THREE.MeshBasicMaterial({ color: color(C.floor), polygonOffset: true,
                                                       polygonOffsetFactor: 1, polygonOffsetUnits: 1 }));
  floor.renderOrder = 0;
  scene.add(floor);
  const lines = [];
  const n = Math.round(half / C.grid_step);
  for (let i = -n; i <= n; i++) {
    const v = i * C.grid_step;
    lines.push(v, 0, -half, v, 0, half, -half, 0, v, half, 0, v);
  }
  grid = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(lines, 3)),
                                      new THREE.LineBasicMaterial({ color: color(C.grid) }));
  grid.renderOrder = 1;
  scene.add(grid);

  // Shadows: the figures and equipment flattened onto the floor (main.render), drawn over the grid.
  shadowGroup = new THREE.Group();
  propShadowGroup = new THREE.Group();
  for (const g of [shadowGroup, propShadowGroup]) {
    g.scale.set(1, 1e-6, 1);
    scene.add(g);
  }
  figureGroup = new THREE.Group();
  propGroup = new THREE.Group();
  scene.add(figureGroup, propGroup);

  geometries.sphere = new THREE.SphereGeometry(1, 32, 21);
  geometries.smallSphere = new THREE.SphereGeometry(1, 18, 12);
  geometries.tube = new THREE.CylinderGeometry(1, 1, 1, 14, 1, true).translate(0, 0.5, 0);
}

// Meshes are kept between frames and moved, not made anew.
const pools = new Map();
function pooled(group, name, index, make) {
  const key = group.id + name;
  if (!pools.has(key)) pools.set(key, []);
  const pool = pools.get(key);
  while (pool.length <= index) {
    const mesh = make();
    group.add(mesh);
    pool.push(mesh);
  }
  return pool[index];
}
function hideFrom(group, name, count) {
  for (const mesh of pools.get(group.id + name) || []) mesh.visible = false;
  return count;
}

const UP = new THREE.Vector3(0, 1, 0);
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();

function placeSphere(mesh, j) {
  mesh.geometry = j[3] > 0.05 ? geometries.sphere : geometries.smallSphere;
  mesh.position.set(j[0], j[1], j[2]);
  mesh.scale.setScalar(j[3]);
  mesh.visible = true;
}

function placeTube(mesh, b, radius) {
  tmpA.set(b[0], b[1], b[2]);
  tmpB.set(b[3] - b[0], b[4] - b[1], b[5] - b[2]);
  const length = tmpB.length();
  mesh.visible = length > 1e-6;
  if (!mesh.visible) return;
  mesh.position.copy(tmpA);
  mesh.quaternion.setFromUnitVectors(UP, tmpB.divideScalar(length));
  mesh.scale.set(radius, length, radius);
}

function meshGeometry(m, uvs) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(m.positions, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(m.normals, 3));
  if (uvs) g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(m.triangles);
  return g;
}

let perFrame = [];  // geometries made for this frame only (face, tattoo)

function drawFigures(figures) {
  for (const g of perFrame) g.dispose();
  perFrame = [];
  for (const [name, group] of [["joint", figureGroup], ["bone", figureGroup], ["face", figureGroup],
                               ["tattoo", figureGroup], ["joint", shadowGroup], ["bone", shadowGroup]]) {
    hideFrom(group, name);
  }
  const shadowMaterial = flat(C.shadow);
  let joints = 0, bones = 0, faces = 0;
  for (const f of figures) {
    for (const b of f.bones) {
      const mesh = pooled(figureGroup, "bone", bones, () => new THREE.Mesh(geometries.tube));
      mesh.material = lit(b.slice(6, 9));
      placeTube(mesh, b, C.bone_radius);
      const shadow = pooled(shadowGroup, "bone", bones++, () => new THREE.Mesh(geometries.tube, shadowMaterial));
      shadow.renderOrder = 2;
      placeTube(shadow, b, C.bone_radius);
    }
    for (const j of f.joints) {
      const mesh = pooled(figureGroup, "joint", joints, () => new THREE.Mesh(geometries.sphere));
      mesh.material = lit(j.slice(4, 7));
      placeSphere(mesh, j);
      const shadow = pooled(shadowGroup, "joint", joints++, () => new THREE.Mesh(geometries.sphere, shadowMaterial));
      shadow.renderOrder = 2;
      placeSphere(shadow, j);
    }
    for (const part of f.face) {
      const mesh = pooled(figureGroup, "face", faces++, () => new THREE.Mesh());
      mesh.geometry = meshGeometry(part);
      perFrame.push(mesh.geometry);
      mesh.material = lit(part.color);
      mesh.visible = true;
    }
    // The tattoo doesn't write depth, so its transparent parts hide nothing (main.draw_tattoo).
    const tattoo = pooled(figureGroup, "tattoo", figures.indexOf(f), () => new THREE.Mesh(undefined,
      new THREE.MeshPhongMaterial({ color: 0xffffff, map: tattooTexture, transparent: true, depthWrite: false,
                                    specular: new THREE.Color(0.022, 0.022, 0.022), shininess: 40,
                                    side: THREE.DoubleSide })));
    tattoo.geometry = meshGeometry(f.tattoo, f.tattoo.uvs);
    perFrame.push(tattoo.geometry);
    tattoo.visible = true;
  }
}

function drawProps(parts) {
  for (const group of [propGroup, propShadowGroup]) {
    for (const mesh of [...group.children]) {
      mesh.geometry.dispose();
      group.remove(mesh);
    }
  }
  for (const part of parts) {
    const geometry = meshGeometry(part);
    propGroup.add(new THREE.Mesh(geometry, lit(C.props)));
    const shadow = new THREE.Mesh(geometry.clone(), flat(C.shadow));
    shadow.renderOrder = 2;
    propShadowGroup.add(shadow);
  }
}

function applyFrame(f) {
  camera.projectionMatrix.fromArray(f.proj);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.matrixWorldInverse.fromArray(f.view);
  camera.matrixWorld.copy(camera.matrixWorldInverse).invert();
  const above = f.eye[1] > 0 && f.active.floor_grid;  // the floor and shadows only from above, when shown
  floor.visible = shadowGroup.visible = propShadowGroup.visible = above;
  grid.visible = f.active.floor_grid;
  drawFigures(f.figures);
  if (f.props) drawProps(f.props);
}

function render(clean = false) {
  const f = JSON.parse(app.frame(clean));
  applyFrame(f);
  renderer.render(scene, camera);
  return f;
}

// The view without highlights, as a PNG (main._capture_image).
function capturePng() {
  const f = render(true);
  if (f.message) say(f.message);
  const png = new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  dirty = true;
  return png;
}

// --- the tattoo image (main.tattoo_image) ----------------------------------------------

async function makeTattoo() {
  const [family, size] = C.tattoo_font, pad = C.tattoo_pad;
  const image = document.createElement("canvas");
  const ctx = image.getContext("2d");
  const font = `bold ${size}px ${family}, Arial, Helvetica, sans-serif`;
  ctx.font = font;
  const width = Math.ceil(ctx.measureText(C.tattoo_text).width), height = Math.ceil(size * 1.15);
  image.width = width + 2 * pad;
  image.height = height + 2 * pad;
  ctx.font = font;
  ctx.fillStyle = "#fff";
  ctx.textBaseline = "middle";
  ctx.fillText(C.tattoo_text, pad, pad + height / 2);
  tattooTexture = new THREE.CanvasTexture(image);
  tattooTexture.flipY = false;  // texcoords run from the top of the image, as in glTF
  tattooTexture.anisotropy = 4;
  const blob = await new Promise((resolve) => image.toBlob(resolve, "image/png"));
  app.set_tattoo(image.width, image.height, new Uint8Array(await blob.arrayBuffer()));
}

// --- HUD: status line, help, messages -------------------------------------------------

let message = "", messageUntil = 0, language = null;

function updateHud(f) {
  if (f.message) {
    message = f.message;
    messageUntil = performance.now() + MESSAGE_TIME;
  }
  showStatus(f.status);
  const help = $("help"), info = $("info"), top = $("toolbar").offsetHeight + 8 + "px";
  if (coarse) help.style.maxHeight = info.style.maxHeight = `calc(100% - ${top} - 10px)`;  // they scroll here
  help.hidden = !f.help;
  help.querySelector(".title").textContent = f.help_title;
  help.querySelector(".body").textContent = f.help;
  help.style.top = top;
  const paragraphs = JSON.stringify(f.info);
  if (info.dataset.text !== paragraphs) {  // only when it changed: shown, hidden or translated
    info.dataset.text = paragraphs;
    info.hidden = !f.info.length;
    info.querySelector(".title").textContent = f.info_title;
    info.querySelector(".body").replaceChildren(
      ...f.info.map((text) => Object.assign(document.createElement("p"), { textContent: text })));
  }
  info.style.top = top;
  for (const button of toolButtons) {
    const item = button.item;
    const active = item.mode ? f.active.drag_mode === item.mode
      : item.shift ? false : f.active[item.action] === true;
    button.classList.toggle("active", active);
  }
  if (f.language !== language) setLanguage(f.language);
  menuLabel(f);
}

function showStatus(status) {
  const text = [status, performance.now() < messageUntil ? message : ""].filter(Boolean).join("  |  ");
  const box = $("status");
  box.hidden = !text;
  box.textContent = text;
}

function say(text) {
  message = text;
  messageUntil = performance.now() + MESSAGE_TIME;
  showStatus(lastFrame ? lastFrame.status : "");
}

function setLanguage(lang) {
  language = lang;
  document.documentElement.lang = lang;
  for (const button of toolButtons) {
    if (button.item.icon === "language") button.querySelector("img").src = `icons/flag_${lang}.png${V}`;
  }
  $("menu-search").placeholder = tr("Type to search...");
  menuWidth = null;
}

// --- the main loop ----------------------------------------------------------------

let pending = null;      // the latest mouse motion, solved once per frame (main.run)
let held = null;         // key or button held down, for auto-repeat
let messageShown = false;

function tick(now) {
  try {
    if (pending) {
      const { x, y, dx, dy } = pending;
      pending = null;
      if (app.move(x, y, dx, dy)) dirty = true;
    }
    if (pinch && pinch.moved) pinchStep();
    if (held && now >= held.next) {
      held.next = now + REPEAT_INTERVAL;
      doAction(held.action, held.shift);
    }
    if (dirty) {
      dirty = false;
      lastFrame = render();
      updateHud(lastFrame);
      messageShown = true;
    } else if (messageShown && now >= messageUntil) {
      messageShown = false;
      showStatus(lastFrame.status);
    }
  } catch (error) {
    console.error(error);
  }
  requestAnimationFrame(tick);
}

function resize() {
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  app.resize(window.innerWidth, window.innerHeight);
  if (menuOpen) sizeMenuList();  // the on-screen keyboard came or went, or the phone was turned
  dirty = true;
}

// --- actions (main.App.on_key) ---------------------------------------------------------

function doAction(action, shift = false) {
  switch (action) {
    case "open": $("file").click(); break;
    case "save": saveFile(app.file_name() + ".json", app.pose_json(), "application/json", ".json", tr("Pose"), "Saved {}"); break;
    case "png": capturePng().then((png) => saveFile(app.file_name() + ".png", png, "image/png", ".png", tr("PNG image"), "Exported {}")); break;
    case "copy": copyFigure(); break;
    case "copy_3d": say(tr("Browsers can't copy 3D models: export one (Ctrl+Shift+E), then use Insert > 3D Models in Office")); break;
    case "pptx": saveFile(app.file_name() + ".pptx", bytes(app.pptx()),
                          "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx",
                          "PowerPoint", "Exported {}"); break;
    case "glb": saveFile(app.file_name() + ".glb", bytes(app.glb()), "model/gltf-binary", ".glb", tr("3D model (glTF)"), "Exported {}"); break;
    case "menu": openMenu(); break;
    case "composer": toggleComposer(); break;
    case "add_to_document":
      app.action(action, shift);
      refreshComposer();
      break;
    default: app.action(action, shift);
  }
  dirty = true;
}

function bytes(proxy) {
  const data = proxy.toJs();
  proxy.destroy();
  return data;
}

function base64(data) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(data instanceof Blob ? data : new Blob([data]));
  });
}

let savedMessage = "";  // what the Android app's save dialog reports when it's done

window.stickmanSaved = (name, ok) => say(tr(ok ? savedMessage : "Could not save {}").replace("{}", name));

// The Android back button: true if it closed something on the page.
window.stickmanBack = () => {
  if (menuOpen) closeMenu();
  else if (composerOpen) toggleComposer(false);
  else if (lastFrame && (lastFrame.help || lastFrame.info.length)) doAction("close_panel");
  else return false;
  return true;
};

// Save with the browser's save dialog where there is one, else as a download.
async function saveFile(name, data, type, extension, description, done) {
  if (host) {
    savedMessage = done;
    host.save(name, type, await base64(data));
    return;
  }
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({ suggestedName: name, types: [{ description, accept: { [type]: [extension] } }] });
      const writable = await handle.createWritable();
      await writable.write(data);
      await writable.close();
      say(tr(done).replace("{}", handle.name));
      return;
    } catch (error) {
      if (error.name === "AbortError") return;
      console.warn(error);
    }
  }
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  say(tr(done).replace("{}", name));
}

// The figure as SVG (vector, which Office can turn into shapes) and PNG on the clipboard.
function copyFigure() {
  if (host) {  // Android's share sheet instead of the clipboard
    capturePng().then(base64).then((png) => host.share(app.file_name() + ".png", "image/png", png));
    return;
  }
  if (!navigator.clipboard || !window.ClipboardItem) {
    say(tr("Copying needs a secure page (https)"));
    return;
  }
  const items = { "image/png": capturePng() };
  const vector = ClipboardItem.supports ? ClipboardItem.supports("image/svg+xml") : false;
  if (vector) items["image/svg+xml"] = new Blob([app.svg()], { type: "image/svg+xml" });
  navigator.clipboard.write([new ClipboardItem(items)]).then(
    () => say(tr(vector ? "Copied figure: paste into Word or PowerPoint (right-click > Convert to Shape to edit it)"
                        : "Copied figure as an image: paste into Word or PowerPoint")),
    (error) => say(tr("Could not copy: {}").replace("{}", error.message || error)));
}

// A pose, a document, or a Word / PowerPoint / PDF file Stickman exported (it carries its document).
function openPose(file) {
  file.arrayBuffer().then((data) => {
    const kind = app.open_file(new Uint8Array(data), file.name);
    if (kind === "doc") toggleComposer(true);
    refreshComposer();
    dirty = true;
  });
}

// In the app, MainActivity.kt reads a picked file itself (the WebView drops files whose type doesn't
// match the input's accept list) and calls this; it keeps the file until the page has started.
function takeOpened() {
  const opened = host && host.opened ? host.opened() : "";
  if (!opened) return;
  const { name, data } = JSON.parse(opened);
  openPose(new File([Uint8Array.from(atob(data), (c) => c.charCodeAt(0))], name));
}

// Android can close the app while it's in the background (even behind the file or share dialogs).
function autosavePose() {
  try {
    const text = app.autosave();
    if (text) localStorage.setItem(AUTOSAVE_KEY, text);
    const docs = app.docs_autosave();
    if (docs) localStorage.setItem(AUTOSAVE_DOCS_KEY, docs);
    else localStorage.removeItem(AUTOSAVE_DOCS_KEY);
  } catch (error) {
    console.warn(error);
  }
}

function restorePose() {
  try {
    const text = localStorage.getItem(AUTOSAVE_KEY);
    if (text) app.restore(text);
    const docs = localStorage.getItem(AUTOSAVE_DOCS_KEY);
    if (docs) app.docs_restore(docs);
  } catch (error) {
    console.warn(error);
  }
}

// --- toolbar -------------------------------------------------------------------

const toolButtons = [];
let tabs = [];  // on a touch screen: {button, boxes}, one per TABS entry

function makeIcon(icon) {
  const img = document.createElement("img");
  img.alt = "";
  if (icon === "language") {
    img.className = "flag";  // its src is the current language's flag, set by setLanguage
  } else {
    img.src = `icons/${icon}.png${V}`;
  }
  return img;
}

function makeTool(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tool";
  button.item = item;
  button.append(makeIcon(item.icon));
  button.addEventListener("pointerdown", (e) => pressTool(e, button));
  button.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse" && !e.buttons) showTip(button); });
  button.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hideTip(); releaseTool(button); });
  button.addEventListener("pointerup", () => releaseTool(button));
  button.addEventListener("pointercancel", () => releaseTool(button));
  button.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation(); });
  button.addEventListener("click", (e) => { if (e.detail === 0) runTool(item, false); });  // keyboard activation
  button.addEventListener("contextmenu", (e) => e.preventDefault());
  toolButtons.push(button);
  return button;
}

function makeGroup(items) {
  const box = document.createElement("div");
  box.className = "group";
  box.append(...items.map(makeTool));
  return box;
}

function buildToolbar() {
  const bar = $("tools");
  if (coarse) buildTabs(bar);
  else bar.append(...TOOLBAR.map(makeGroup));
  $("menu-row").append(...MENU_STEPS.map(makeTool));
}

function buildTabs(bar) {
  const row = document.createElement("div");
  row.className = "group tabs";
  bar.append(row);
  const pages = document.createElement("div");
  pages.className = "pages";
  bar.append(pages);
  tabs = TABS.map((tab, i) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tool";
    button.append(makeIcon(tab.icon));
    button.item = { tip: tab.tip };
    button.addEventListener("click", () => {
      closeMenu();
      setTab(i);
      flashTip(button);  // after setTab: the name goes under the toolbar's rows
    });
    button.addEventListener("contextmenu", (e) => e.preventDefault());
    row.append(button);
    const items = tab.groups.flatMap((g) => TOOLBAR[g]).filter((item) => !ALWAYS_SHOWN.has(item.action));
    const box = makeGroup(items);
    box.hidden = true;
    pages.append(box);
    return { button, box };
  });
  row.append(...TOOLBAR.flat().filter((item) => ALWAYS_SHOWN.has(item.action)).map(makeTool));
}

// Open tab i, or close it if it's the open one: the view gets the row back.
function setTab(i) {
  const opening = tabs[i].box.hidden;
  tabs.forEach(({ button, box }, k) => {
    box.hidden = !(opening && k === i);
    button.classList.toggle("active", !box.hidden);
  });
  dirty = true;  // the help and info boxes sit under the toolbar
}

function runTool(item, shift) {
  if (item.mode) {
    app.set_drag_mode(item.mode);
    dirty = true;
    return;
  }
  doAction(item.action, item.shift || (shift && SHIFT_STEPS.has(item.action)));
}

function pressTool(e, button) {
  if (e.button !== 0) return;
  e.preventDefault();  // keep the keyboard focus where it was
  hideTip();
  if (e.pointerType !== "mouse") flashTip(button);
  closeMenu();
  button.classList.add("pressed");
  const item = button.item;
  const shift = item.shift || (e.shiftKey && SHIFT_STEPS.has(item.action));
  runTool(item, e.shiftKey);
  if (REPEAT.has(item.action)) held = { button, action: item.action, shift, next: performance.now() + REPEAT_DELAY };
}

function releaseTool(button) {
  button.classList.remove("pressed");
  if (held && held.button === button) held = null;
}

let tipTimer = 0;
const withoutKey = (text) => text.replace(/\s*\([^()]*\)\s*$/, "");  // "Undo (Ctrl+Z)" -> "Undo"

// A touch screen has no hover: pressing a button shows its name for a moment, without its shortcut.
function flashTip(button) {
  showTip(button);
  const tip = $("tooltip");
  tip.textContent = withoutKey(tip.textContent);
  clearTimeout(tipTimer);
  tipTimer = setTimeout(hideTip, TIP_TIME);
}

function showTip(button) {
  const tip = $("tooltip");
  const text = host && button.item.action === "copy" ? "Share as a picture" : button.item.tip;
  tip.textContent = tr(text);
  tip.hidden = false;
  const rect = button.getBoundingClientRect();
  tip.style.top = $("toolbar").offsetHeight + 2 + "px";
  tip.style.left = Math.max(0, Math.min(rect.left, window.innerWidth - tip.offsetWidth)) + "px";
}

function hideTip() {
  $("tooltip").hidden = true;
}

// --- the exercise list (main.ExerciseMenu) --------------------------------------------------

let menuOpen = false, menuRows = [], highlight = -1, menuWidth = null;

function setupMenu() {
  $("menu-box").addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    menuOpen ? closeMenu() : openMenu();
  });
  $("menu-box").addEventListener("click", (e) => { if (e.detail === 0) menuOpen ? closeMenu() : openMenu(); });
  const search = $("menu-search");
  search.addEventListener("input", () => fillMenu(null));
  search.addEventListener("keydown", menuKey);
  search.addEventListener("pointerdown", (e) => e.stopPropagation());
  const list = $("menu-list");
  list.addEventListener("pointermove", (e) => {
    const row = e.target.closest(".row");
    if (row && row.dataset.i && +row.dataset.i !== highlight) setHighlight(+row.dataset.i, false);
  });
  list.addEventListener("pointerdown", (e) => e.preventDefault());
  list.addEventListener("click", (e) => {
    const row = e.target.closest(".row");
    if (row && row.dataset.i) choose(+row.dataset.i);
  });
  document.addEventListener("pointerdown", (e) => { if (menuOpen && !$("menu").contains(e.target)) closeMenu(); }, true);
}

function menuLabel(f) {
  if (menuWidth === null) {
    // As wide as the longest name in this language, as main.ExerciseMenu.width.
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = getComputedStyle(document.body).font;
    const rows = JSON.parse(app.exercise_rows(""));
    const widest = Math.max(ctx.measureText(tr(MENU_PLACEHOLDER)).width,
                            ...rows.map((r) => ctx.measureText(r.label || r.heading).width));
    menuWidth = Math.ceil(widest + ctx.measureText(tr(MENU_TWO)).width + 4 * 8 + 22);
    const steps = MENU_STEPS.length;  // and room for the buttons to its right
    $("menu-box").style.width = `min(${menuWidth}px, calc(100vw - 12px - ${steps} * (var(--tool) + 4px)))`;
  }
  const label = $("menu-label");
  label.textContent = f.exercise_label || (coarse ? withoutKey(tr(MENU_PLACEHOLDER)) : tr(MENU_PLACEHOLDER));
  label.className = f.exercise_label ? "" : "dim";
  label.style.visibility = menuOpen ? "hidden" : "";
}

function openMenu() {
  if (menuOpen) return;
  menuOpen = true;
  held = null;
  $("menu").classList.add("open");
  const search = $("menu-search");
  search.hidden = false;
  search.value = "";
  $("menu-label").style.visibility = "hidden";
  fillMenu(lastFrame && lastFrame.exercise);
  $("menu-list").hidden = false;
  sizeMenuList();
  if (!coarse) search.focus({ preventScroll: true });  // on a touch screen, the keyboard only when asked for
}

// Down to the bottom of the window: the list sits under the toolbar's rows of buttons.
function sizeMenuList() {
  const list = $("menu-list");
  list.style.maxHeight = `${Math.max(100, Math.min(24 * 25, window.innerHeight - list.getBoundingClientRect().top - 12))}px`;
}

function closeMenu() {
  if (!menuOpen) return;
  menuOpen = false;
  $("menu").classList.remove("open");
  $("menu-search").hidden = true;
  $("menu-search").blur();
  $("menu-list").hidden = true;
  $("menu-label").style.visibility = "";
}

function fillMenu(current) {
  menuRows = JSON.parse(app.exercise_rows($("menu-search").value));
  const list = $("menu-list");
  list.replaceChildren();
  if (!menuRows.length) {
    const row = document.createElement("div");
    row.className = "row empty";
    row.textContent = tr("No exercise matches");
    list.append(row);
  }
  menuRows.forEach((r, i) => {
    const row = document.createElement("div");
    if (r.heading) {
      row.className = "row heading";
      row.textContent = r.heading;
    } else {
      row.className = "row";
      row.dataset.i = i;
      const label = document.createElement("span");
      label.className = "label";
      label.textContent = r.label;
      row.append(label);
      if (r.two) {
        const two = document.createElement("span");
        two.className = "two";
        two.textContent = tr(MENU_TWO);
        row.append(two);
      }
    }
    list.append(row);
  });
  const start = current ? menuRows.findIndex((r) => r.name === current) : -1;
  highlight = -1;
  list.scrollTop = 0;
  if (start >= 0) {
    setHighlight(start, false);
    const row = list.children[start];
    list.scrollTop = row.offsetTop - list.clientHeight / 2;
  } else {
    move(1);
  }
}

function setHighlight(i, scroll) {
  const list = $("menu-list");
  if (highlight >= 0 && list.children[highlight]) list.children[highlight].classList.remove("highlight");
  highlight = i;
  if (i < 0) return;
  const row = list.children[i];
  row.classList.add("highlight");
  if (scroll) {
    // Keep it in view, with its heading when it's the first of a category.
    const top = i > 0 && menuRows[i - 1].heading ? list.children[i - 1] : row;
    if (top.offsetTop < list.scrollTop) list.scrollTop = top.offsetTop;
    if (row.offsetTop + row.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = row.offsetTop + row.offsetHeight - list.clientHeight;
    }
  }
}

function move(steps) {
  const items = menuRows.map((r, i) => (r.name ? i : -1)).filter((i) => i >= 0);
  if (!items.length) return setHighlight(-1, false);
  let k = items.indexOf(highlight);
  k = k >= 0 ? Math.min(Math.max(k + steps, 0), items.length - 1) : steps > 0 ? 0 : items.length - 1;
  setHighlight(items[k], true);
}

function menuKey(e) {
  e.stopPropagation();
  const page = Math.max(1, Math.floor($("menu-list").clientHeight / 25) - 1);
  const moves = { ArrowUp: -1, ArrowDown: 1, PageUp: -page, PageDown: page, Home: -menuRows.length, End: menuRows.length };
  if (e.key === "Escape" || e.key === "Tab") {
    e.preventDefault();
    closeMenu();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (highlight >= 0) choose(highlight);
  } else if (e.key in moves && !(e.key === "Home" || e.key === "End") || (e.key in moves && !e.target.value)) {
    e.preventDefault();
    move(moves[e.key]);
  }
}

function choose(i) {
  closeMenu();
  app.choose_exercise(menuRows[i].name);
  dirty = true;
}

// --- mouse, touch and keys --------------------------------------------------------------

let pointer = null;  // the pointer pressed on the view: {id, button, x, y, kind ("drag", "orbit", "pan"), time, start}
const fingers = new Map();  // the fingers on the view, by pointer id: {x, y}
let pinch = null;           // two fingers zooming and panning: {distance, x, y, moved}

function pinchMiddle() {
  const [a, b] = [...fingers.values()];
  return { distance: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y)), x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

// A joint drag stays one when a second finger touches down, unless it has only just begun without
// going anywhere: then the first finger landed on a joint by chance, and this is a pinch.
function canPinch(e) {
  if (!pointer || pointer.kind !== "drag") return true;
  const moved = Math.hypot(pointer.x - pointer.start.x, pointer.y - pointer.start.y);
  return e.timeStamp - pointer.time < PINCH_HOLD && moved < 10;  // timeStamp: when the finger landed, however busy we are
}

function startPinch() {
  if (pointer) {
    if (pointer.kind === "drag") app.cancel_drag();
    else app.release(pointer.x, pointer.y, 1);  // not button 0: that could count as a click on empty space
    pointer = null;
  }
  pending = null;
  pinch = pinchMiddle();
  app.press(pinch.x, pinch.y, 1, false, false);  // the middle button pans
  dirty = true;
}

// Once per frame while the fingers move, as a mouse drag.
function pinchStep() {
  const now = pinchMiddle();
  app.zoom(Math.log(now.distance / pinch.distance) / ZOOM_STEP);
  app.move(now.x, now.y, now.x - pinch.x, now.y - pinch.y);
  pinch = now;
  dirty = true;
}

function setupInput() {
  window.addEventListener("resize", resize);
  canvas.addEventListener("webglcontextrestored", () => { dirty = true; });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) dirty = true;
    else if (host) autosavePose();
  });
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener("pointerdown", (e) => {
    const touch = e.pointerType === "touch";
    if (touch) fingers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (fingers.size === 2 && !pinch && canPinch(e)) {
      canvas.setPointerCapture(e.pointerId);
      startPinch();
      return;
    }
    if (pointer || pinch || e.button > 2) return;
    closeMenu();
    hideTip();
    canvas.setPointerCapture(e.pointerId);
    pointer = { id: e.pointerId, button: e.button, x: e.clientX, y: e.clientY,
                time: e.timeStamp, start: { x: e.clientX, y: e.clientY } };
    pending = null;
    pointer.kind = app.press(e.clientX, e.clientY, e.button, e.ctrlKey || e.metaKey, e.shiftKey, touch);
    dirty = true;
  });
  canvas.addEventListener("pointermove", (e) => {
    if (fingers.has(e.pointerId)) {
      fingers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinch) {
        pinch.moved = true;
        return;
      }
    }
    if (e.pointerType === "touch" && !pointer) return;  // no hover on a touch screen
    if (pointer && e.pointerId !== pointer.id) return;
    const last = pointer || pending || { x: e.clientX, y: e.clientY };
    pending = { x: e.clientX, y: e.clientY, dx: (pending ? pending.dx : 0) + e.clientX - last.x,
                dy: (pending ? pending.dy : 0) + e.clientY - last.y };
    if (pointer) pointer.x = e.clientX, pointer.y = e.clientY;
  });
  const up = (e) => {
    const finger = fingers.delete(e.pointerId);
    if (pinch) {
      if (finger) {
        app.release(e.clientX, e.clientY, 1);
        pinch = null;
        dirty = true;
      }
      return;
    }
    if (!pointer || e.pointerId !== pointer.id) return;
    if (pending) {
      const { x, y, dx, dy } = pending;
      pending = null;
      app.move(x, y, dx, dy);
    }
    app.release(e.clientX, e.clientY, pointer.button);
    pointer = null;
    dirty = true;
  };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("pointerleave", () => {
    if (!pointer && app.hover(-1, -1)) dirty = true;
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const steps = -e.deltaY / (e.deltaMode === 1 ? 3 : e.deltaMode === 2 ? 0.1 : 100);
    app.zoom(Math.max(-3, Math.min(3, steps)));
    dirty = true;
  }, { passive: false });

  window.addEventListener("keydown", (e) => {
    const action = keyAction(e);
    if (!action) return;
    e.preventDefault();
    if (e.repeat) return;  // the app repeats held keys itself
    doAction(action, e.shiftKey);
    const ctrl = e.ctrlKey || e.metaKey;
    if (ctrl ? action === "undo" || action === "redo" : SHIFT_STEPS.has(action)) {
      held = { key: e.code, action, shift: e.shiftKey, next: performance.now() + REPEAT_DELAY };
    }
  });
  window.addEventListener("keyup", (e) => { if (held && held.key === e.code) held = null; });
  window.addEventListener("blur", () => { held = null; });
  $("file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) openPose(file);
  });
}

function keyAction(e) {
  if (e.altKey) return null;
  const c = e.code, shift = e.shiftKey;
  if (e.ctrlKey || e.metaKey) {
    return { KeyZ: shift ? "redo" : "undo", KeyY: "redo", KeyS: shift ? "pptx" : "save", KeyO: "open",
             KeyE: shift ? "glb" : "png", KeyC: shift ? "copy_3d" : "copy" }[c] || null;
  }
  if (c === "Tab" && shift) return null;
  return KEYS[c] || null;
}

// --- the Document Composer (composer.py; the actions are composer_actions.py) ------------------------

let composerOpen = false, composerData = null, previewZoom = 1, pageShown = 0, composerSettingsOpen = false;
const previewUrls = new Map();  // render_jobs key -> object URL of the preview picture
const MM_PER_PT = 25.4 / 72;
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};

function setupComposer() {
  // The captions' font (ttf.py), so the preview wraps and looks as the exports do.
  const font = (weight, file) => new FontFace("Stickman Sans", `url(py/fonts/${file}${V})`, { weight });
  for (const face of [font("normal", "StickmanSans-Regular.ttf"), font("bold", "StickmanSans-Bold.ttf")]) {
    face.load().then((f) => document.fonts.add(f)).catch(console.warn);
  }
  new ResizeObserver(() => { if (composerOpen) drawPages(); }).observe($("composer"));
}

function toggleComposer(open = !composerOpen) {
  composerOpen = open;
  $("composer").hidden = !open;
  document.body.classList.toggle("composing", open);
  for (const b of toolButtons) if (b.item.action === "composer") b.classList.toggle("active", open);
  if (open) refreshComposer();
}

// After any change: read the state, rebuild the panel, then render the preview pictures it lacks.
let refreshing = null;
async function refreshComposer() {
  if (!composerOpen) return;
  composerData = JSON.parse(app.doc_summary());
  buildComposer();
  if (refreshing) return;
  refreshing = (async () => {
    for (;;) {
      const jobs = JSON.parse(app.doc_jobs("preview", JSON.stringify([...previewUrls.keys()])));
      if (!jobs.length) break;
      for (const job of jobs) {
        const image = renderJob(job);
        const picture = el("canvas", { width: job.width, height: job.height });
        picture.getContext("2d").putImageData(image, 0, 0);
        const blob = await new Promise((resolve) => picture.toBlob(resolve, "image/png"));
        previewUrls.set(job.key, URL.createObjectURL(blob));
      }
      drawPages();
    }
  })();
  try { await refreshing; } finally { refreshing = null; }
}

function docAction(name, arg = null) {
  const text = app.doc_action(name, JSON.stringify(arg));
  if (text) say(text);
  refreshComposer();
  dirty = true;
}

// One of composer.render_jobs's pictures, drawn as the view draws (the same meshes and lights) into an
// offscreen target: top-down RGBA with straight alpha.
function renderJob(job) {
  const w = job.width, h = job.height;
  const target = new THREE.WebGLRenderTarget(w, h, { samples: 4 });
  camera.projectionMatrix.fromArray(job.proj);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.matrixWorldInverse.fromArray(job.view);
  camera.matrixWorld.copy(camera.matrixWorldInverse).invert();
  floor.visible = shadowGroup.visible = propShadowGroup.visible = job.ground && job.eye[1] > 0;
  grid.visible = job.ground;
  drawFigures(job.figures);
  drawProps(job.props);
  const background = scene.background;
  scene.background = job.transparent ? null : color(C.background);
  renderer.setClearColor(0x000000, 0);
  renderer.setRenderTarget(target);
  renderer.clear();
  renderer.render(scene, camera);
  const pixels = new Uint8Array(w * h * 4);
  renderer.readRenderTargetPixels(target, 0, 0, w, h, pixels);
  renderer.setRenderTarget(null);
  target.dispose();
  scene.background = background;
  app.resend_props();  // the view's own equipment comes back with the next frame
  dirty = true;
  // Bottom-up rows, and edges averaged with the transparent clear colour: premultiplied alpha.
  const out = new ImageData(w, h), d = out.data, row = w * 4;
  for (let y = 0; y < h; y++) {
    const from = (h - 1 - y) * row, to = y * row;
    for (let x = 0; x < row; x += 4) {
      const a = pixels[from + x + 3];
      const k = a > 0 && a < 255 ? 255 / a : 1;
      d[to + x] = pixels[from + x] * k;
      d[to + x + 1] = pixels[from + x + 1] * k;
      d[to + x + 2] = pixels[from + x + 2] * k;
      d[to + x + 3] = a;
    }
  }
  return out;
}

const DOC_TYPES = { docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    pdf: "application/pdf" };
const DOC_NAMES = { docx: "Word", pptx: "PowerPoint", pdf: "PDF" };

async function exportDocument() {
  const doc = composerData && composerData.doc;
  if (!doc || !doc.entries.length) { say(tr("Add a figure to the document first")); return; }
  const fmt = doc.settings.format;
  say(tr("Exporting..."));
  await new Promise(requestAnimationFrame);
  try {
    for (const job of JSON.parse(app.doc_jobs(fmt))) {
      app.doc_image(job.key, job.width, job.height, renderJob(job).data);
      await new Promise(requestAnimationFrame);  // keep the page alive between pictures
    }
    const data = bytes(app.doc_export(fmt));
    saveFile(app.doc_file_name() + "." + fmt, data, DOC_TYPES[fmt], "." + fmt, DOC_NAMES[fmt], "Exported {}");
  } catch (error) {
    console.error(error);
    say(tr("Could not export: {}").replace("{}", error.message || error));
  }
}

function saveDocument() {
  if (!composerData || !composerData.doc) return;
  saveFile(app.doc_file_name() + ".json", app.doc_json(), "application/json", ".json", tr("Stickman document"), "Saved {}");
}

// --- the panel ----------------------------------------------------------------------------

function button(label, onClick, { title = "", disabled = false, cls = "" } = {}) {
  const b = el("button", { type: "button", textContent: label, title, disabled, className: "cbutton " + cls });
  b.addEventListener("click", onClick);
  return b;
}

function selectBox(options, value, onChange) {
  const s = el("select");
  for (const [v, label] of options) s.append(el("option", { value: v, textContent: label, selected: v === value }));
  s.addEventListener("change", () => onChange(s.value));
  return s;
}

function check(label, value, onChange) {
  const box = el("input", { type: "checkbox", checked: value });
  box.addEventListener("change", () => onChange(box.checked));
  return el("label", { className: "check" }, box, label);
}

function field(label, control) {
  return el("label", { className: "field" }, el("span", { textContent: label }), control);
}

// A small picture of a grid: columns x rows on a page of the current orientation.
function gridIcon(cols, rows, landscape) {
  const icon = el("span", { className: "grid-icon" + (landscape ? " landscape" : "") });
  icon.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  icon.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
  for (let k = 0; k < cols * rows; k++) icon.append(el("span"));
  return icon;
}

function buildComposer() {
  const box = $("composer"), data = composerData, doc = data.doc;
  const old = box.querySelector(".pages"), scroll = old ? old.scrollTop : 0;
  box.replaceChildren();
  const head = el("div", { className: "chead" });
  if (data.docs.length) {
    head.append(selectBox(data.docs.map((name, i) => [String(i), name]), String(data.current),
                          (v) => docAction("choose", +v)));
  }
  head.append(button(tr("New"), () => docAction("new"), { title: tr("New document") }),
              button(tr("Open"), () => $("file").click(), { title: tr("Open a document or a pose") }));
  if (doc) {
    head.append(button(tr("Save"), saveDocument, { title: tr("Save the document to edit it later") }),
                button(tr("Close"), () => docAction("close"), { title: tr("Close this document") }),
                button(tr("Export"), exportDocument, { title: tr("Export the document as the chosen format"), cls: "primary" }));
  }
  head.append(button("×", () => toggleComposer(false), { title: tr("Hide the composer (V)"), cls: "close" }));
  box.append(el("div", { className: "ctitle", textContent: tr("Document Composer") }), head);
  if (!doc) {
    box.append(el("p", { className: "hint",
      textContent: tr("No document yet. Press New, or add a figure with Add to Document (N): a document is made for it.") }));
    return;
  }
  const s = doc.settings;
  const settings = el("details", { className: "csection", open: !doc.entries.length || composerSettingsOpen });
  settings.addEventListener("toggle", () => { composerSettingsOpen = settings.open; });
  settings.append(el("summary", { textContent: tr("Document settings") }));
  const grid = el("div", { className: "cgrid" });
  settings.append(grid);
  const name = el("input", { type: "text", value: doc.name });
  name.addEventListener("change", () => docAction("rename", name.value));
  const margin = el("input", { type: "number", min: 5, max: 40, step: 1, value: s.margin });
  margin.addEventListener("change", () => docAction("set", ["margin", +margin.value]));
  grid.append(
    field(tr("Name"), name),
    field(tr("Format"), selectBox(data.formats, s.format, (v) => docAction("set", ["format", v]))),
    field(tr("Page"), selectBox([["portrait", tr("A4 portrait")], ["landscape", tr("A4 landscape")]], s.orientation,
                                (v) => docAction("set", ["orientation", v]))),
    field(tr("Margins (mm)"), margin),
    field(tr("Figures go in as"), selectBox(data.modes, s.mode, (v) => docAction("set", ["mode", v]))),
    el("div", { className: "checks" },
       check(tr("Floor in images"), s.ground, (v) => docAction("set", ["ground", v])),
       check(tr("Transparent background"), s.transparent, (v) => docAction("set", ["transparent", v]))),
    el("div", { className: "checks" },
       check(tr("Numbers"), s.numbers, (v) => docAction("set", ["numbers", v])),
       check(tr("Names"), s.names, (v) => docAction("set", ["names", v])),
       check(tr("Descriptions"), s.descriptions, (v) => docAction("set", ["descriptions", v]))));
  const layouts = el("div", { className: "layouts" });
  for (const [c, r] of data.layouts) {
    const b = el("button", { type: "button", className: "layout" + (c === s.columns && r === s.rows ? " active" : ""),
                             title: tr("{} figures per page").replace("{}", c * r) },
                 gridIcon(c, r, s.orientation === "landscape"), el("span", { textContent: `${c}×${r}` }));
    b.addEventListener("click", () => docAction("layout", [c, r]));
    layouts.append(b);
  }
  grid.append(el("div", { className: "field wide" }, el("span", { textContent: tr("Grid (columns × rows)") }), layouts));
  box.append(settings);

  if (!doc.entries.length) {
    box.append(el("p", { className: "hint", textContent: tr("Choose an exercise or pose a figure, then press Add to Document (N).") }));
  }

  const bar = el("div", { className: "cbar" },
    button("−", () => { previewZoom = Math.max(0.3, previewZoom / 1.25); drawPages(); }, { title: tr("Zoom out") }),
    el("span", { className: "zoom" }),
    button("+", () => { previewZoom = Math.min(4, previewZoom * 1.25); drawPages(); }, { title: tr("Zoom in") }),
    button("◀", () => showPage(pageShown - 1), { title: tr("Previous page") }),
    el("span", { className: "pageno" }),
    button("▶", () => showPage(pageShown + 1), { title: tr("Next page") }),
    button("↶", () => docAction("undo"), { title: tr("Undo in the document"), disabled: !doc.can_undo }),
    button("↷", () => docAction("redo"), { title: tr("Redo in the document"), disabled: !doc.can_redo }));
  box.append(bar, el("div", { className: "pages" }));
  if (doc.selected !== null && doc.entries[doc.selected]) box.append(entryPanel(doc, data));
  drawPages();
  box.querySelector(".pages").scrollTop = scroll;
}

function entryPanel(doc, data) {
  const i = doc.selected, e = doc.entries[i];
  const panel = el("div", { className: "csection entry" });
  panel.append(el("div", { className: "entry-title",
    textContent: tr("Figure {}").replace("{}", i + 1) + " · " + tr("page {}").replace("{}", e.page) }));
  const name = el("input", { type: "text", value: e.name, placeholder: tr("Caption") });
  name.addEventListener("change", () => docAction("entry", ["name", name.value]));
  const description = el("textarea", { rows: 2, value: e.description, placeholder: tr("Short description or instruction") });
  description.addEventListener("change", () => docAction("entry", ["description", description.value]));
  const modeName = Object.fromEntries(data.modes);
  const modes = [["", tr("Document's choice ({})").replace("{}", modeName[doc.settings.mode])], ...data.modes];
  const grounds = [["", tr("Document's choice ({})").replace("{}", tr(doc.settings.ground ? "on" : "off"))],
                   ["on", tr("on")], ["off", tr("off")]];
  panel.append(
    field(tr("Name"), name), field(tr("Description"), description),
    field(tr("Goes in as"), selectBox(modes, e.mode || "", (v) => docAction("entry", ["mode", v || null]))),
    field(tr("Floor"), selectBox(grounds, e.ground === null ? "" : e.ground ? "on" : "off",
                                 (v) => docAction("entry", ["ground", v === "" ? null : v === "on"]))));
  const last = doc.entries.length - 1, cap = doc.capacity;
  panel.append(el("div", { className: "buttons" },
    button("↑", () => docAction("step", -1), { title: tr("Move earlier"), disabled: i === 0 }),
    button("↓", () => docAction("step", 1), { title: tr("Move later"), disabled: i === last }),
    button("⇞", () => docAction("page", -1), { title: tr("Move to the page before"), disabled: i < cap }),
    button("⇟", () => docAction("page", 1), { title: tr("Move to the page after"),
                                              disabled: Math.floor(i / cap) === Math.floor(last / cap) }),
    button(tr("Duplicate"), () => docAction("duplicate")),
    button(tr("Delete"), () => docAction("delete"), { cls: "danger" })));
  panel.append(el("div", { className: "buttons" },
    button(tr("Edit in Stickman"), () => { docAction("edit"); if (coarse) toggleComposer(false); },
           { title: tr("Load this figure into the editor; then Replace puts the changes back") }),
    button(tr("Replace with the editor's pose"), () => docAction("replace"),
           { title: tr("Put the pose now in the editor into this figure, keeping its caption and settings") })));
  return panel;
}

function showPage(k) {
  const pages = $("composer").querySelectorAll(".page");
  if (!pages.length) return;
  pageShown = Math.max(0, Math.min(pages.length - 1, k));
  pages[pageShown].scrollIntoView({ block: "start", behavior: "smooth" });
  updatePageNo();
}

function updatePageNo() {
  const no = $("composer").querySelector(".pageno");
  if (no && composerData.doc) {
    no.textContent = tr("Page {} of {}").replace("{}", pageShown + 1).replace("{}", composerData.doc.pages.length);
  }
}

// The pages as the exports lay them out: composer.layout geometry in mm, scaled to the panel.
function drawPages() {
  const holder = $("composer").querySelector(".pages");
  if (!holder || !composerData || !composerData.doc) return;
  const doc = composerData.doc, [pw, ph] = doc.page, [mx, my, mw, mh] = doc.content;
  const zoom = $("composer").querySelector(".zoom");
  if (zoom) zoom.textContent = Math.round(previewZoom * 100) + "%";
  const fit = Math.min(holder.clientWidth - 28, (holder.clientHeight - 30) * pw / ph * 1.6);
  const scale = Math.max(100, fit * previewZoom) / pw;
  const mm = (v) => `${(v * scale).toFixed(2)}px`;
  pageShown = Math.min(pageShown, doc.pages.length - 1);
  holder.replaceChildren();
  doc.pages.forEach((cells, p) => {
    const page = el("div", { className: "page" });
    page.dataset.page = p;
    Object.assign(page.style, { width: mm(pw), height: mm(ph) });
    const margin = el("div", { className: "margin" });
    Object.assign(margin.style, { left: mm(mx), top: mm(my), width: mm(mw), height: mm(mh) });
    page.append(margin);
    for (const c of cells) {
      const [cx, cy, cw, ch] = c.cell, [x, y, w, h] = c.figure;
      const figure = el("div", { className: "figure" + (c.entry === doc.selected ? " selected" : "") });
      Object.assign(figure.style, { left: mm(cx), top: mm(cy), width: mm(cw), height: mm(ch) });
      figure.dataset.entry = c.entry;
      const url = previewUrls.get(c.key);
      if (url) {
        const img = el("img", { src: url, alt: "", draggable: false });
        Object.assign(img.style, { left: mm(x - cx), top: mm(y - cy), width: mm(w), height: mm(h) });
        figure.append(img);
      }
      if (c.mode !== "image") figure.append(el("span", { className: "badge", textContent: c.mode === "model" ? "3D" : "2D" }));
      for (const line of c.lines) {
        const div = el("div", { className: "line" + (line.bold ? " bold" : ""), textContent: line.text });
        Object.assign(div.style, { left: mm(line.x - cx), top: mm(line.top - cy), width: mm(line.width),
                                   height: mm(line.height), lineHeight: mm(line.height),
                                   fontSize: mm(line.size * MM_PER_PT) });
        figure.append(div);
      }
      page.append(figure);
    }
    holder.append(el("div", { className: "pagelabel",
      textContent: tr("Page {} of {}").replace("{}", p + 1).replace("{}", doc.pages.length) }), page);
  });
  holder.onscroll = () => {
    const top = holder.getBoundingClientRect().top;
    const k = [...holder.querySelectorAll(".page")].findIndex((pg) => pg.getBoundingClientRect().bottom > top + 40);
    if (k >= 0 && k !== pageShown) { pageShown = k; updatePageNo(); }
  };
  holder.onpointerdown = previewPress;
  updatePageNo();
}

// Click a figure to select it; drag it (mouse or pen) onto another place, on any page, to move it there.
function previewPress(e) {
  const figure = e.target.closest(".figure");
  if (!figure || e.button !== 0) return;
  const from = +figure.dataset.entry;
  if (from !== composerData.doc.selected) docAction("select", from);
  if (e.pointerType === "touch") return;  // touch screens move figures with the buttons
  e.preventDefault();
  const start = { x: e.clientX, y: e.clientY };
  let ghost = null;
  const move = (ev) => {
    if (!ghost && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return;
    if (!ghost) {
      const f = $("composer").querySelector(`.figure[data-entry="${from}"]`);
      ghost = f ? f.cloneNode(true) : el("div");
      ghost.className = "figure ghost";
      document.body.append(ghost);
    }
    ghost.style.left = ev.clientX + 8 + "px";
    ghost.style.top = ev.clientY + 8 + "px";
  };
  const up = (ev) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    if (!ghost) return;
    ghost.remove();
    const to = dropIndex(ev.clientX, ev.clientY);
    if (to !== null && to !== from) docAction("move", to);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

// The place in the order under a point of the preview: the grid slot it falls in, on whichever page.
function dropIndex(x, y) {
  const doc = composerData.doc;
  for (const page of $("composer").querySelectorAll(".page")) {
    const r = page.getBoundingClientRect();
    if (x < r.left || x > r.right || y < r.top || y > r.bottom) continue;
    const [mx, my, mw, mh] = doc.content, scale = r.width / doc.page[0];
    const cols = doc.settings.columns, rows = doc.settings.rows;
    const col = Math.max(0, Math.min(cols - 1, Math.floor(((x - r.left) / scale - mx) / (mw / cols))));
    const row = Math.max(0, Math.min(rows - 1, Math.floor(((y - r.top) / scale - my) / (mh / rows))));
    return Math.min(doc.entries.length - 1, +page.dataset.page * doc.capacity + row * cols + col);
  }
  return null;
}
