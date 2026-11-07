// The website's page side: draws what bridge.py's frame() returns with Three.js and sends it the
// input. The posing, exercises and exports are the desktop app's own Python modules, run by Pyodide.
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.mjs";

// Toolbar groups as main.TOOLBAR: icon (icons.ICONS name), tooltip (English, translated by i18n), and
// either an action (a key's action, see keyAction) with an optional forced Shift, or a drag mode.
const TOOLBAR = [
  [{ icon: "info", tip: "About Stickman (I)", action: "info" }],
  [{ icon: "open", tip: "Open a pose (Ctrl+O)", action: "open" },
   { icon: "save", tip: "Save the pose (Ctrl+S)", action: "save" },
   { icon: "png", tip: "Export a PNG image (Ctrl+E)", action: "png" },
   { icon: "copy", tip: "Copy as a picture for Word or PowerPoint (Ctrl+C)", action: "copy" },
   { icon: "save_shapes", tip: "Download as editable shapes for PowerPoint or Word, .pptx (Ctrl+Shift+S)", action: "pptx" },
   { icon: "save_3d", tip: "Export a 3D model file, .glb (Ctrl+Shift+E)", action: "glb" }],
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
   { icon: "help", tip: "Show / hide the help (H)", action: "help" }],
  [{ icon: "language", tip: "Language: English. Switch to Greek (T)", action: "language" }],
];

const KEYS = {
  KeyH: "help", KeyI: "info", KeyT: "language", Tab: "menu", Escape: "escape", KeyP: "pin", KeyM: "mirror",
  KeyZ: "twist_minus", KeyX: "twist_plus", KeyL: "limits", KeyG: "ground", KeyR: "reset",
  KeyQ: "turn_left", KeyE: "turn_right", KeyW: "tip_forward", KeyS: "tip_back", KeyA: "lean_left", KeyD: "lean_right",
  ArrowUp: "move_up", ArrowDown: "move_down", KeyF: "centre",
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

const $ = (id) => document.getElementById(id);
// "?v=<build>": web/build.py puts it on app.js in index.html, and app.js puts it on the files it loads, so a
// browser never mixes a cached file of one build with another's.
const V = new URL(import.meta.url).search;
const canvas = $("view");
let py, app, C;            // Pyodide, bridge.app, bridge colours
const tr = (text) => app.tr(text);

// --- start -----------------------------------------------------------------------

async function start() {
  py = await loadPyodide();
  await py.loadPackage("numpy");
  const files = await (await fetch("py/files.json" + V)).json();
  py.FS.mkdirTree("/stickman");
  await Promise.all(files.map(async (name) => {
    const response = await fetch("py/" + name + V);
    if (!response.ok) throw new Error(`py/${name}: ${response.status}`);
    py.FS.writeFile("/stickman/" + name, await response.text());
  }));
  py.runPython("import sys; sys.path.insert(0, '/stickman')");
  app = py.pyimport("bridge").app;
  C = JSON.parse(app.colors());
  await makeTattoo();
  setupScene();
  buildToolbar();
  setupMenu();
  setupInput();
  for (const box of document.querySelectorAll(".panel")) {  // the OK buttons of the help and info boxes
    const ok = box.querySelector(".ok");
    ok.addEventListener("pointerdown", (e) => { if (e.button === 0) { e.preventDefault(); doAction("close_panel"); } });
    ok.addEventListener("click", (e) => { if (e.detail === 0) doAction("close_panel"); });  // keyboard
  }
  resize();
  $("loading").remove();
  window.stickman = { py, app };  // for testing from the browser console
  requestAnimationFrame(tick);
}

start().catch((error) => {
  console.error(error);
  const box = $("loading");
  box.classList.add("error");
  $("loading-text").textContent = "Δεν ήταν δυνατή η εκκίνηση / Could not start:\n" + error;
});

// --- drawing ---------------------------------------------------------------------

let renderer, scene, camera, floor, figureGroup, shadowGroup, propGroup, propShadowGroup, tattooTexture;
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
  const grid = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(lines, 3)),
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
  const above = f.eye[1] > 0;  // the floor and shadows only from above
  floor.visible = shadowGroup.visible = propShadowGroup.visible = above;
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
    default: app.action(action, shift);
  }
  dirty = true;
}

function bytes(proxy) {
  const data = proxy.toJs();
  proxy.destroy();
  return data;
}

// Save with the browser's save dialog where there is one, else as a download.
async function saveFile(name, data, type, extension, description, done) {
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

function openPose(file) {
  file.text().then((text) => {
    app.open_pose(text, file.name);
    dirty = true;
  });
}

// --- toolbar -------------------------------------------------------------------

const toolButtons = [];

function buildToolbar() {
  const bar = $("tools");
  for (const group of TOOLBAR) {
    const box = document.createElement("div");
    box.className = "group";
    for (const item of group) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tool";
      button.item = item;
      const img = document.createElement("img");
      img.alt = "";
      if (item.icon === "language") {
        img.className = "flag";  // its src is the current language's flag, set by setLanguage
      } else {
        img.src = `icons/${item.icon}.png${V}`;
      }
      button.append(img);
      button.addEventListener("pointerdown", (e) => pressTool(e, button));
      button.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse" && !e.buttons) showTip(button); });
      button.addEventListener("pointerleave", () => { hideTip(); releaseTool(button); });
      button.addEventListener("pointerup", () => releaseTool(button));
      button.addEventListener("pointercancel", () => releaseTool(button));
      button.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation(); });
      button.addEventListener("click", (e) => { if (e.detail === 0) runTool(item, false); });  // keyboard activation
      button.addEventListener("contextmenu", (e) => e.preventDefault());
      toolButtons.push(button);
      box.append(button);
    }
    bar.append(box);
  }
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

function showTip(button) {
  const tip = $("tooltip");
  tip.textContent = tr(button.item.tip);
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
    $("menu-box").style.width = `min(${menuWidth}px, calc(100vw - 12px))`;
  }
  const label = $("menu-label");
  label.textContent = f.exercise_label || tr(MENU_PLACEHOLDER);
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
  const list = $("menu-list");
  list.hidden = false;
  // Down to the bottom of the window: the list sits under the toolbar's rows of buttons.
  list.style.maxHeight = `${Math.max(100, Math.min(24 * 25, window.innerHeight - list.getBoundingClientRect().top - 12))}px`;
  search.focus({ preventScroll: true });
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

let pointer = null;  // the pointer pressed on the view: {id, button, x, y}

function setupInput() {
  window.addEventListener("resize", resize);
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener("pointerdown", (e) => {
    if (pointer || e.button > 2) return;
    closeMenu();
    hideTip();
    canvas.setPointerCapture(e.pointerId);
    pointer = { id: e.pointerId, button: e.button, x: e.clientX, y: e.clientY };
    pending = null;
    app.press(e.clientX, e.clientY, e.button, e.ctrlKey || e.metaKey, e.shiftKey);
    dirty = true;
  });
  canvas.addEventListener("pointermove", (e) => {
    if (pointer && e.pointerId !== pointer.id) return;
    const last = pointer || pending || { x: e.clientX, y: e.clientY };
    pending = { x: e.clientX, y: e.clientY, dx: (pending ? pending.dx : 0) + e.clientX - last.x,
                dy: (pending ? pending.dy : 0) + e.clientY - last.y };
    if (pointer) pointer.x = e.clientX, pointer.y = e.clientY;
  });
  const up = (e) => {
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
