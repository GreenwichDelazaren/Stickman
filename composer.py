"""The Document Composer: figures put together on A4 pages, for Word, PowerPoint or PDF.

A Document holds its settings (format, orientation, margins, grid, how figures are included,
captions) and its entries in order. An entry is a snapshot of the editor: the figures as a pose file
(scene.pose_file), the camera it was seen from, and its own options and caption text. The order of
the entries fills the grid left to right, top to bottom, page after page.

layout() turns a document into page geometry in millimetres (top-left origin), which the previews
(main.py's composer window, web/app.js) and every export (doc_export.py) use, so they all agree.
The images are rendered by the front ends: render_jobs() says what to draw (camera matrices cropped
to the figure, size, ground, background), and they hand back the pixels.

No pygame/OpenGL.
"""

import copy
import hashlib
import json
import math

import numpy as np

import props
import scene
import skeleton as sk
import ttf
from i18n import tr

KIND = "stickman-document"
VERSION = 1
A4 = (210.0, 297.0)  # millimetres
FORMATS = ("docx", "pptx", "pdf")
FORMAT_NAMES = {"docx": "Word (.docx)", "pptx": "PowerPoint (.pptx)", "pdf": "PDF (.pdf)"}
MODES = ("image", "shapes", "model")
MODE_NAMES = {"image": "Image", "shapes": "Editable 2D shapes", "model": "3D model"}
# Grids as (columns, rows), in the order the composers offer them.
LAYOUTS = [(1, 1), (2, 1), (1, 2), (1, 3), (3, 1), (2, 2), (3, 2), (2, 3), (4, 2), (2, 4), (3, 3),
           (4, 3), (3, 4), (4, 4), (2, 5), (3, 5)]
DEFAULTS = {
    "format": "docx", "orientation": "portrait", "margin": 15.0,  # mm, all round
    "columns": 2, "rows": 2,
    "mode": "image",          # entries without their own mode
    "ground": False,          # images: the floor, its grid and the shadows
    "transparent": True,      # images: no background colour
    "numbers": True, "names": True, "descriptions": True,  # captions
}
MARGINS = (5.0, 40.0)
EXPORT_DPI, EXPORT_MAX = 300, 3000      # image pixels: dots per inch, and the most on a side
PREVIEW_DPI, PREVIEW_MAX = 110, 900
REFERENCE = 1000                         # pixels: the square view entries are framed in
PADDING = 0.04                           # room round a figure, of its larger side
PT = 25.4 / 72                           # millimetres per point
LINE = 1.2                               # caption line height, times the font size
CAPTION_GAP = 1.5                        # mm between a figure and its caption
MAX_DESCRIPTION_LINES = 3
OFFICE_UNIT = 36000000                   # Office's 3D models: the longest side of a model
OFFICE_FOV = 45.0                        # ... and its camera's field of view


def _number(value, lo, hi, default):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else min(hi, max(lo, value))


def clean_settings(settings):
    """The settings with every value present and in range."""
    out = dict(DEFAULTS)
    for key, value in (settings or {}).items():
        if key not in DEFAULTS:
            continue
        if key == "format":
            out[key] = value if value in FORMATS else DEFAULTS[key]
        elif key == "orientation":
            out[key] = "landscape" if value == "landscape" else "portrait"
        elif key == "mode":
            out[key] = value if value in MODES else DEFAULTS[key]
        elif key == "margin":
            out[key] = round(_number(value, *MARGINS, DEFAULTS[key]), 1)
        elif key in ("columns", "rows"):
            out[key] = int(_number(value, 1, 6, DEFAULTS[key]))
        else:
            out[key] = bool(value)
    return out


# --- entries ---------------------------------------------------------------------

def make_entry(figures, exercise, parts, camera):
    """An entry: the editor's figures, equipment and camera as they are now (copies)."""
    return {"pose": copy.deepcopy(scene.pose_file(figures, exercise, parts)),
            "camera": {"yaw": float(camera.yaw), "pitch": float(camera.pitch), "dist": float(camera.dist),
                       "target": [round(float(v), 5) for v in camera.target]},
            "mode": None, "ground": None, "name": None, "description": ""}


def clean_entry(entry):
    """An entry read from a file, with every field present (raises on a broken pose)."""
    scene.read_pose_file(entry["pose"])  # check it
    camera = dict(entry.get("camera") or {})
    out = {"pose": entry["pose"],
           "camera": {"yaw": _number(camera.get("yaw"), -1e6, 1e6, 0.0),
                      "pitch": _number(camera.get("pitch"), -89.0, 89.0, 5.0),
                      "dist": _number(camera.get("dist"), 0.5, 20.0, 3.0),
                      "target": [_number(v, -100, 100, 0.0) for v in (list(camera.get("target") or [0, 0.9, 0]) + [0] * 3)[:3]]},
           "mode": entry.get("mode") if entry.get("mode") in MODES else None,
           "ground": entry.get("ground") if isinstance(entry.get("ground"), bool) else None,
           "name": entry.get("name") if isinstance(entry.get("name"), str) else None,
           "description": entry.get("description") if isinstance(entry.get("description"), str) else ""}
    return out


def entry_camera(entry):
    c, camera = entry["camera"], scene.Camera()
    camera.yaw, camera.pitch, camera.dist = c["yaw"], c["pitch"], c["dist"]
    camera.target = np.array(c["target"], float)
    return camera


_built = {}  # pose JSON text -> (figures, parts): entries are never changed in place, only replaced


def entry_figures(entry):
    """(figures, equipment) of the entry, built from its pose file (cached; don't change them)."""
    key = json.dumps(entry["pose"], sort_keys=True)
    if key not in _built:
        dicts, _, parts = scene.read_pose_file(entry["pose"])
        figures = []
        for data in dicts:
            figure = sk.Skeleton()
            figure.from_dict(data)
            figures.append(figure)
        if len(_built) > 200:
            _built.clear()
        _built[key] = (figures, parts)
    return _built[key]


def exercise_of(entry):
    return entry["pose"].get("exercise")


def entry_name(entry):
    """The name in the caption: the entry's own, or its exercise's (translated), or ""."""
    if entry.get("name") is not None:
        return entry["name"]
    exercise = exercise_of(entry)
    return tr(exercise) if exercise else ""


def entry_label(entry, number):
    """How the composers list an entry: number and name."""
    return f"{number}. {entry_name(entry) or tr('Figure')}"


# --- the document ---------------------------------------------------------------------

class Document:
    """Settings, entries in order, and an undo history of its own."""

    def __init__(self, settings=None, name=""):
        self.settings = clean_settings(settings)
        self.entries = []
        self.name = name or tr("Document")
        self.selected = None     # entry index
        self.modified = False
        self.undo_stack, self.redo_stack = [], []

    # --- files ------------------------------------------------------------------

    def to_dict(self):
        return {"kind": KIND, "version": VERSION, "name": self.name, "settings": dict(self.settings),
                "entries": copy.deepcopy(self.entries)}

    def to_json(self):
        return json.dumps(self.to_dict(), indent=1, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data):
        """A document from to_dict() data; raises ValueError, KeyError or TypeError if it's broken."""
        if data.get("kind") != KIND:
            raise ValueError(tr("not a Stickman document"))
        doc = cls(data.get("settings"), str(data.get("name") or ""))
        doc.entries = [clean_entry(e) for e in data.get("entries", [])]
        return doc

    # --- editing ------------------------------------------------------------------

    def _state(self):
        return copy.deepcopy(self.settings), copy.deepcopy(self.entries), self.selected

    def _push(self):
        self.undo_stack.append(self._state())
        del self.undo_stack[:-100]
        self.redo_stack.clear()
        self.modified = True

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self._state())
            self.settings, self.entries, self.selected = self.undo_stack.pop()
            self.modified = True
            return True
        return False

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self._state())
            self.settings, self.entries, self.selected = self.redo_stack.pop()
            self.modified = True
            return True
        return False

    def _index(self, i):
        if i is None or not 0 <= i < len(self.entries):
            raise IndexError(tr("No figure is selected"))
        return i

    def set(self, key, value):
        """Change a setting; True if it changed."""
        new = clean_settings(dict(self.settings, **{key: value}))
        if new == self.settings:
            return False
        self._push()
        self.settings = new
        return True

    def set_layout(self, columns, rows):
        new = clean_settings(dict(self.settings, columns=columns, rows=rows))
        if new == self.settings:
            return False
        self._push()
        self.settings = new
        return True

    def add(self, entry, at=None):
        """Put entry at index at (the end by default); returns its index."""
        self._push()
        at = len(self.entries) if at is None else max(0, min(at, len(self.entries)))
        self.entries.insert(at, entry)
        self.selected = at
        return at

    def delete(self, i):
        i = self._index(i)
        self._push()
        del self.entries[i]
        self.selected = min(i, len(self.entries) - 1) if self.entries else None

    def duplicate(self, i):
        i = self._index(i)
        self._push()
        self.entries.insert(i + 1, copy.deepcopy(self.entries[i]))
        self.selected = i + 1
        return i + 1

    def move(self, i, to):
        """Move entry i to index to; the others close up. True if it moved."""
        i = self._index(i)
        to = max(0, min(to, len(self.entries) - 1))
        if to == i:
            return False
        self._push()
        self.entries.insert(to, self.entries.pop(i))
        self.selected = to
        return True

    def replace(self, i, entry):
        """Put a new pose and camera into entry i, keeping its options and captions."""
        i = self._index(i)
        self._push()
        old = self.entries[i]
        new = dict(old, pose=entry["pose"], camera=entry["camera"])
        # A caption that was the old exercise's name follows the new one.
        if old.get("name") is not None and old["name"] == tr(exercise_of(old) or ""):
            new["name"] = None
        self.entries[i] = new
        self.selected = i

    def set_entry(self, i, key, value):
        """Change one entry's mode, ground, name or description; True if it changed."""
        i = self._index(i)
        entry = self.entries[i]
        if key == "mode":
            value = value if value in MODES else None
        elif key == "ground":
            value = value if isinstance(value, bool) else None
        elif key == "name":
            value = None if value is None else str(value)
            if value is not None and value == tr(exercise_of(entry) or "") and exercise_of(entry):
                value = None  # the exercise's own name: keep following the language
        elif key == "description":
            value = str(value or "")
        else:
            raise KeyError(key)
        if entry.get(key) == value:
            return False
        self._push()
        self.entries[i] = dict(entry, **{key: value})
        return True

    # --- what the entries look like ---------------------------------------------------

    def mode(self, entry):
        return entry.get("mode") or self.settings["mode"]

    def ground(self, entry):
        g = entry.get("ground")
        return self.settings["ground"] if g is None else g

    @property
    def capacity(self):
        return self.settings["columns"] * self.settings["rows"]

    def page_count(self):
        return max(1, math.ceil(len(self.entries) / self.capacity))


class Composer:
    """The documents open in the app, one of them current: where Add to Document goes."""

    def __init__(self):
        self.docs = []
        self.current = None

    @property
    def doc(self):
        return self.docs[self.current] if self.current is not None else None

    def _unique(self, name):
        names = {d.name for d in self.docs}
        if name not in names:
            return name
        n = 2
        while f"{name} {n}" in names:
            n += 1
        return f"{name} {n}"

    def new(self, settings=None, name=None):
        doc = Document(settings, self._unique(name or tr("Document")))
        self.docs.append(doc)
        self.current = len(self.docs) - 1
        return doc

    def open(self, data, name=None):
        doc = Document.from_dict(data)
        doc.name = self._unique(name or doc.name)
        self.docs.append(doc)
        self.current = len(self.docs) - 1
        return doc

    def close(self, i=None):
        i = self.current if i is None else i
        if i is None:
            return
        del self.docs[i]
        self.current = (min(i, len(self.docs) - 1) if self.docs else None)

    def choose(self, i):
        if 0 <= i < len(self.docs):
            self.current = i


# --- page layout ----------------------------------------------------------------------

def page_size(settings):
    w, h = A4
    return (h, w) if settings["orientation"] == "landscape" else (w, h)


def caption_sizes(cell_w, cell_h):
    """(name, description) font sizes in points for a cell of this size (mm)."""
    name = min(14.0, max(7.5, min(cell_w, cell_h * 1.4) * 0.13))
    return round(name, 1), round(max(7.0, name * 0.85), 1)


def layout(doc):
    """The pages as geometry in mm (top-left origin):
    {"page": (w, h), "content": (x, y, w, h), "pages": [[cell, ...], ...], "sizes": (name pt, description pt)}
    with each cell {"entry", "number", "slot", "cell", "figure": (x, y, w, h), "lines": [line]} and each
    line {"text", "x", "top", "width", "height", "size", "bold"} (centred in its width, one line high)."""
    s = doc.settings
    pw, ph = page_size(s)
    m = s["margin"]
    cw, ch = pw - 2 * m, ph - 2 * m
    cols, rows = s["columns"], s["rows"]
    slot_w, slot_h = cw / cols, ch / rows
    pad = min(4.0, max(1.5, min(slot_w, slot_h) * 0.04))
    cell_w, cell_h = slot_w - 2 * pad, slot_h - 2 * pad
    name_pt, desc_pt = caption_sizes(cell_w, cell_h)
    name_h, desc_h = name_pt * LINE * PT, desc_pt * LINE * PT

    def name_text(n, entry):
        name = entry_name(entry) if s["names"] else ""
        number = f"{n + 1}." if s["numbers"] else ""
        return " ".join(t for t in (number, name) if t)

    descriptions = [ttf.wrap(e["description"], cell_w, desc_pt * PT) if s["descriptions"] and e["description"].strip()
                    else [] for e in doc.entries]
    has_name = any(name_text(n, e) for n, e in enumerate(doc.entries)) if doc.entries else (s["numbers"] or s["names"])
    desc_lines = min(MAX_DESCRIPTION_LINES, max([len(d) for d in descriptions] + [0]))

    def figure_height(lines):
        caption = (name_h if has_name else 0) + lines * desc_h
        return cell_h - caption - (CAPTION_GAP if caption else 0)

    while desc_lines and figure_height(desc_lines) < cell_h * 0.45:
        desc_lines -= 1
    show_name = has_name and figure_height(0) >= cell_h * 0.4
    caption_h = (name_h if show_name else 0) + desc_lines * desc_h
    fig_h = cell_h - caption_h - (CAPTION_GAP if caption_h else 0)

    pages = []
    for page in range(doc.page_count()):
        cells = []
        for k in range(doc.capacity):
            n = page * doc.capacity + k
            if n >= len(doc.entries):
                break
            entry = doc.entries[n]
            row, col = divmod(k, cols)
            sx, sy = m + col * slot_w, m + row * slot_h
            x, y = sx + pad, sy + pad
            lines, top = [], y + fig_h + CAPTION_GAP
            text = name_text(n, entry)
            if show_name:
                if text:
                    line = ttf.wrap(text, cell_w, name_pt * PT, bold=True, max_lines=1)[0]
                    lines.append({"text": line, "x": x, "top": top, "width": cell_w, "height": name_h,
                                  "size": name_pt, "bold": True})
                top += name_h
            if desc_lines and descriptions[n]:
                wrapped = ttf.wrap(entry["description"], cell_w, desc_pt * PT, max_lines=desc_lines)
                for line in wrapped:
                    lines.append({"text": line, "x": x, "top": top, "width": cell_w, "height": desc_h,
                                  "size": desc_pt, "bold": False})
                    top += desc_h
            cells.append({"entry": n, "number": n + 1, "slot": (sx, sy, slot_w, slot_h),
                          "cell": (x, y, cell_w, cell_h), "figure": (x, y, cell_w, fig_h), "lines": lines})
        pages.append(cells)
    return {"page": (pw, ph), "content": (m, m, cw, ch), "pages": pages, "sizes": (name_pt, desc_pt),
            "pad": pad}


# --- framing a figure in its rectangle ----------------------------------------------------

def _points(figures, parts, ground):
    """World points with radii that a figure's picture must show."""
    points = []
    for f in figures:
        points += [(p, r) for p, r in zip(f.pos, f.radii)]
        if ground:  # the shadows
            points += [(p * (1, 0, 1), r) for p, r in zip(f.pos, f.radii)]
    for part in parts:
        lo, hi = (np.asarray(b, float) for b in props.bounds(part))
        for k in range(8):
            corner = np.where([k & 1, k & 2, k & 4], hi, lo)
            points.append((corner, 0.0))
            if ground:
                points.append((corner * (1, 0, 1), 0.0))
    return points


def _ndc(view, points):
    """[(x, y, r)] of the points in normalised device coordinates of a square view."""
    f = 1 / math.tan(math.radians(scene.FOV) / 2)
    out = []
    for p, r in points:
        c = view.pv @ np.append(p, 1.0)
        if c[3] <= 1e-6:
            continue
        out.append((c[0] / c[3], c[1] / c[3], r * f / c[3]))
    return out


def frame(entry, aspect, mode, ground):
    """How the entry's figure fills a rectangle of this width / height:
    {"proj", "view", "eye", "crop"}: the projection (cropped so the rectangle is exactly the view),
    the view matrix, the eye, and the rectangle as (x0, y0, x1, y1) in REFERENCE pixels of the
    uncropped square view (for the 2D shapes). A 3D model is framed as Office frames one (round the
    middle of its box, from a distance that shows its bounding sphere), with "office" for its XML."""
    figures, parts = entry_figures(entry)
    camera = entry_camera(entry)
    if mode == "model":
        return _model_frame(figures, parts, camera, aspect)
    view = scene.View(camera, (REFERENCE, REFERENCE))
    pts = _ndc(view, _points(figures, parts, ground))
    if not pts:
        pts = [(0.0, 0.0, 0.5)]
    x0 = min(x - r for x, _, r in pts)
    x1 = max(x + r for x, _, r in pts)
    y0 = min(y - r for _, y, r in pts)
    y1 = max(y + r for _, y, r in pts)
    w, h = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
    pad = PADDING * max(w, h)
    w, h = w + 2 * pad, h + 2 * pad
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx, sy = 2 / w, 2 / h
    crop = np.array([[sx, 0, 0, -sx * cx], [0, sy, 0, -sy * cy], [0, 0, 1, 0], [0, 0, 0, 1]])
    half = REFERENCE / 2  # NDC -> pixels of the square view (y down)
    rect = (half * (cx - w / 2 + 1), half * (1 - cy - h / 2), half * (cx + w / 2 + 1), half * (1 - cy + h / 2))
    return {"proj": crop @ view.proj, "view": view.view, "eye": view.eye, "crop": rect}


def _model_frame(figures, parts, camera, aspect):
    view = scene.View(camera, (REFERENCE, REFERENCE))
    rotation = view.view[:3, :3]
    pts = _points(figures, parts, False)
    turned = np.array([rotation @ p for p, _ in pts])
    radii = np.array([r for _, r in pts])
    lo, hi = (turned - radii[:, None]).min(axis=0), (turned + radii[:, None]).max(axis=0)
    centre_view = (lo + hi) / 2
    longest = float(max(hi - lo))
    sphere = float(np.linalg.norm(hi - lo)) / 2
    dist = sphere / math.sin(math.radians(OFFICE_FOV) / 2)
    # The camera Office uses: looking at the middle of the box from the same direction.
    centre = rotation.T @ centre_view
    office = scene.Camera()
    office.yaw, office.pitch = camera.yaw, camera.pitch
    office.target, office.dist = centre, dist
    model_view = scene.View(office, (REFERENCE, REFERENCE))
    model_view.proj = scene.perspective(OFFICE_FOV, 1.0, 0.05, 100.0)
    model_view.pv = model_view.proj @ model_view.view
    ndc = _ndc(model_view, pts)
    ex = max(abs(x) + r for x, _, r in ndc) * (1 + PADDING)
    ey = max(abs(y) + r for _, y, r in ndc) * (1 + PADDING)
    # The square viewport (NDC -1..1) is `size` wide, the rectangle aspect x 1; fit the figure in it.
    size = min(aspect / ex, 1 / ey)  # in units of the rectangle's height
    crop = np.diag([size / aspect, size, 1.0, 1.0])
    return {"proj": crop @ model_view.proj, "view": model_view.view, "eye": model_view.eye, "crop": None,
            "office": {"rotation": rotation, "centre": centre_view, "longest": longest,
                       "sphere": sphere / longest * OFFICE_UNIT, "size": size}}


# --- images the front ends render -----------------------------------------------------------

def image_size(rect, dpi, most):
    """Pixels (w, h) of a picture rect (mm) wide and high at dpi, no side over most."""
    w, h = rect[2] / 25.4 * dpi, rect[3] / 25.4 * dpi
    scale = min(1.0, most / max(w, h))
    return max(8, round(w * scale)), max(8, round(h * scale))


def image_key(entry, size, mode, ground, transparent):
    text = json.dumps([entry["pose"], entry["camera"], size, mode == "model", ground, transparent], sort_keys=True)
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def render_jobs(doc, purpose):
    """What the front end must render: [{"key", "entry", "width", "height", "proj", "view", "eye",
    "ground", "transparent", "figures", "parts"}], one per picture, for the "preview" or for an export
    format. A 2D shapes entry needs a picture only in the preview; a 3D model needs one everywhere
    (Office shows it until the model is first drawn, and the PDF has only the picture)."""
    lay = layout(doc)
    dpi, most = (PREVIEW_DPI, PREVIEW_MAX) if purpose == "preview" else (EXPORT_DPI, EXPORT_MAX)
    jobs, seen = [], set()
    for cells in lay["pages"]:
        for cell in cells:
            entry = doc.entries[cell["entry"]]
            mode = doc.mode(entry)
            if mode == "shapes" and purpose != "preview":
                continue
            ground = doc.ground(entry) and mode == "image"  # shapes and models have no floor
            transparent = doc.settings["transparent"] or mode == "model"
            rect = cell["figure"]
            size = image_size(rect, dpi, most)
            key = image_key(entry, size, mode, ground, transparent)
            if key in seen:
                continue
            seen.add(key)
            framing = frame(entry, rect[2] / rect[3], mode, ground)
            figures, parts = entry_figures(entry)
            jobs.append({"key": key, "entry": cell["entry"], "width": size[0], "height": size[1],
                         "proj": framing["proj"], "view": framing["view"], "eye": framing["eye"],
                         "ground": ground, "transparent": transparent, "figures": figures, "parts": parts})
    return jobs


def cell_key(doc, cell, purpose):
    """The render_jobs key of a cell's picture."""
    entry = doc.entries[cell["entry"]]
    mode = doc.mode(entry)
    dpi, most = (PREVIEW_DPI, PREVIEW_MAX) if purpose == "preview" else (EXPORT_DPI, EXPORT_MAX)
    ground = doc.ground(entry) and mode == "image"  # shapes and models have no floor
    transparent = doc.settings["transparent"] or mode == "model"
    return image_key(entry, image_size(cell["figure"], dpi, most), mode, ground, transparent)


def finish_pixels(data, width, height, bottom_up, premultiplied):
    """RGBA bytes read back from a renderer as top-down, straight-alpha RGBA (numpy, uint8)."""
    a = np.frombuffer(bytes(data), np.uint8).reshape(height, width, 4)
    if bottom_up:
        a = a[::-1]
    if premultiplied:
        a = a.astype(np.float32)
        alpha = a[..., 3:4]
        rgb = np.where(alpha > 0, a[..., :3] * 255.0 / np.maximum(alpha, 1.0), 0.0)
        a = np.concatenate([np.clip(rgb, 0, 255), alpha], axis=2).round().astype(np.uint8)
    return np.ascontiguousarray(a)


def downsample(rgba, factor):
    """Average factor x factor blocks of premultiplied-alpha pixels (uint8 RGBA) into straight alpha."""
    if factor == 1:
        return rgba
    h, w = rgba.shape[0] // factor, rgba.shape[1] // factor
    a = rgba[:h * factor, :w * factor].astype(np.float32).reshape(h, factor, w, factor, 4).mean(axis=(1, 3))
    alpha = a[..., 3:4]
    rgb = np.where(alpha > 0, a[..., :3] * 255.0 / np.maximum(alpha, 1e-3), 0.0)
    return np.ascontiguousarray(np.concatenate([np.clip(rgb, 0, 255), alpha], axis=2).round().astype(np.uint8))


# --- what the front ends show ------------------------------------------------------------

def summary(doc):
    """JSON-ready data for the composer panels: settings, entries and the layout."""
    lay = layout(doc)
    entries = []
    for n, e in enumerate(doc.entries):
        entries.append({"label": entry_label(e, n + 1), "name": entry_name(e),
                        "own_name": e.get("name") is not None, "description": e["description"],
                        "mode": e.get("mode"), "ground": e.get("ground"), "effective_mode": doc.mode(e),
                        "exercise": exercise_of(e), "page": n // doc.capacity + 1})
    pages = []
    for cells in lay["pages"]:
        pages.append([{"entry": c["entry"], "number": c["number"], "figure": c["figure"], "cell": c["cell"],
                       "slot": c["slot"], "lines": c["lines"], "key": cell_key(doc, c, "preview"),
                       "mode": doc.mode(doc.entries[c["entry"]])} for c in cells])
    return {"name": doc.name, "settings": doc.settings, "entries": entries, "selected": doc.selected,
            "page": lay["page"], "content": lay["content"], "pages": pages,
            "capacity": doc.capacity, "can_undo": bool(doc.undo_stack), "can_redo": bool(doc.redo_stack)}
