"""The scene apart from how it's drawn: the camera and projection, picking and drag planes, loading
exercises and pose files, the face and tattoo meshes, and the exports built from the figures (3D
model parts for gltf.py, flat shapes for office_clip.py and svg.py).

Shared by the desktop app (main.py) and the website (web/bridge.py), so no pygame/OpenGL here.
"""

import math
from typing import NamedTuple

import numpy as np

import exercises as ex
import i18n
import props
import skeleton as sk
from geometry import convex_hull, normalize
from i18n import tr

FOV = 45.0
BONE_RADIUS = 0.016
PICK_PIXELS = 14

SIDE_COLORS = {  # side: (bone colour, joint colour)
    None: ((0.30, 0.32, 0.36), (0.55, 0.58, 0.63)),
    "l": ((0.18, 0.34, 0.66), (0.30, 0.55, 1.00)),
    "r": ((0.66, 0.24, 0.20), (1.00, 0.42, 0.34)),
}
LIGHT_DIR = (0.4, 1.0, 0.6)  # towards the light
SELECTED_COLOR = (1.00, 0.82, 0.10)
PINNED_COLOR = (0.15, 0.72, 0.35)
BACKGROUND = (0.84, 0.88, 0.92)
FLOOR_COLOR = (0.95, 0.95, 0.93)
GRID_COLOR = (0.78, 0.79, 0.78)
SHADOW_COLOR = (0.74, 0.75, 0.74)
FLOOR_HALF = 3.0  # metres from the centre to the floor's edge
GRID_STEP = 0.5
EYE_COLOR = (0.12, 0.36, 0.92)
NOSE_COLOR = (0.38, 0.41, 0.44)

# Camera angles (yaw, pitch) of the view keys 1-4.
VIEW_ANGLES = {"front": (0, 5), "side": (90, 5), "top": (0, 89), "angled": (35, 15)}


def _circle(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _split_edges(points, n=6):
    """The polygon with each edge cut into n pieces, so it can bend round the head."""
    return [tuple(np.add(a, np.subtract(b, a) * k / n)) for a, b in zip(points, points[1:] + points[:1])
            for k in range(n)]


# The face, drawn flat on the head: (name, outline, colour), with the outlines in metres on the plane
# touching the front of the head (x to the figure's left, y up), anticlockwise as seen from the front.
FACE = [("left eye", _circle(0.038, 0.024, 0.016), EYE_COLOR),
        ("right eye", _circle(-0.038, 0.024, 0.016), EYE_COLOR),
        ("Nose", _split_edges([(0.0, 0.008), (-0.017, -0.036), (0.017, -0.036)]), NOSE_COLOR)]
FACE_LIFT = 0.0015  # how far the face sits above the head's surface
FACE_RINGS = 3

# The tattoo: white text on the outside of the left forearm, reading from the wrist towards the
# elbow (so it reads left to right from the figure's left side when the arm is held forward).
TATTOO_TEXT = "Lazaros.Filippidis@Gmail.com"
TATTOO_COLOR = (1.0, 1.0, 1.0)
TATTOO_BONE = "l_hand"         # the forearm: a bone is named by the joint at its far end
TATTOO_SIDE = (1.0, 0.0, 0.6)  # where its middle faces, in the rest pose: outside and a bit forward
TATTOO_HEIGHT = 0.012          # metres round the arm (the text's line height)
TATTOO_MARGIN = 0.01           # least gap to the elbow and wrist
TATTOO_FONT = ("arial", 64)    # font and pixel size of the image
TATTOO_PAD = 4                 # transparent pixels round the text in the image
TATTOO_SEGMENTS = 8


class Tattoo(NamedTuple):
    """The tattoo image, made by whoever can render text (pygame on the desktop, a canvas on the web)."""
    width: int   # pixels
    height: int
    png: bytes   # white text on transparent

    @property
    def aspect(self):
        return self.width / self.height


# Equipment in the Office export: cylinders up to this radius are drawn as lines, cut into pieces
# this long so each piece sorts in front of or behind the figure where it passes.
THIN_PROP, PROP_PIECE = 0.03, 0.2
# Shape names for the Office export; a bone is named by the joint at its far end.
BONE_NAMES = {"chest": "lower spine", "neck": "upper spine", "head": "neck", "shoulder": "collarbone",
              "elbow": "upper arm", "hand": "forearm", "hip": "hip bone", "knee": "thigh",
              "ankle": "shin", "toe": "foot"}


# --- camera and projection ---------------------------------------------------

def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy) / 2)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
        [0, 0, -1, 0],
    ])


def look_at(eye, target, up=(0.0, 1.0, 0.0)):
    f = normalize(target - eye)
    s = normalize(np.cross(f, up))
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class Camera:
    def __init__(self):
        self.yaw, self.pitch = VIEW_ANGLES["angled"]
        self.dist = 3.0
        self.target = np.array([0.0, 0.9, 0.0])

    def eye(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return self.target + self.dist * np.array(
            [math.cos(p) * math.sin(y), math.sin(p), math.cos(p) * math.cos(y)])

    def matrices(self, aspect):
        return perspective(FOV, aspect, 0.05, 100.0), look_at(self.eye(), self.target)

    def orbit(self, dx, dy):
        self.yaw -= dx * 0.4
        self.pitch = min(89.0, max(-45.0, self.pitch + dy * 0.4))

    def pan(self, dx, dy, height):
        _, view = self.matrices(1.0)
        right, up = view[0, :3], view[1, :3]
        scale = 2 * self.dist * math.tan(math.radians(FOV) / 2) / height
        self.target += (-right * dx + up * dy) * scale

    def zoom(self, steps):
        self.dist = min(20.0, max(0.5, self.dist * 0.9 ** steps))

    def frame(self, lo, hi, size):
        """Aim at the box lo..hi and move back until it fits a window of size (w, h)."""
        self.target = (lo + hi) / 2
        radius = float(np.linalg.norm(hi - lo)) / 2 + 0.15
        half = math.radians(FOV) / 2
        half = min(half, math.atan(math.tan(half) * size[0] / size[1]))
        self.dist = min(20.0, max(0.5, radius / math.sin(half)))


class View:
    """The camera as seen in a window of size (w, h) pixels: projection to and from the screen."""

    def __init__(self, camera, size):
        self.size = (max(int(size[0]), 1), max(int(size[1]), 1))
        self.eye = camera.eye()
        self.proj, self.view = camera.matrices(self.size[0] / self.size[1])
        self.pv = self.proj @ self.view
        self.pv_inv = np.linalg.inv(self.pv)
        self.px = self.size[1] / 2 / math.tan(math.radians(FOV) / 2)  # pixels per metre at depth 1

    def project(self, p):
        """World point -> (screen x, screen y, depth), or None if behind the camera."""
        c = self.pv @ np.append(p, 1.0)
        if c[3] <= 1e-6:
            return None
        w, h = self.size
        return (c[0] / c[3] + 1) * 0.5 * w, (1 - c[1] / c[3]) * 0.5 * h, c[3]

    def project_all(self, points):
        """project() of each point, or None if any of them is behind the camera."""
        projected = []
        for p in points:
            s = self.project(p)
            if s is None:
                return None
            projected.append(s)
        return projected

    def mouse_ray(self, mx, my):
        w, h = self.size
        x, y = 2 * mx / w - 1, 1 - 2 * my / h
        near = self.pv_inv @ (x, y, -1.0, 1.0)
        far = self.pv_inv @ (x, y, 1.0, 1.0)
        near, far = near[:3] / near[3], far[:3] / far[3]
        return near, normalize(far - near)


def pick(figures, view, mx, my):
    """(figure, joint index) of the joint under the mouse, or None."""
    f = 1 / math.tan(math.radians(FOV) / 2)
    best, best_score = None, 0.0
    for skel in figures:
        for i, p in enumerate(skel.pos):
            s = view.project(p)
            if s is None:
                continue
            radius_px = max(PICK_PIXELS, skel.radii[i] * f * view.size[1] / 2 / s[2])
            score = math.hypot(s[0] - mx, s[1] - my) - radius_px
            if score < best_score:
                best, best_score = (skel, i), score
    return best


# --- dragging a joint ----------------------------------------------------------

def begin_drag(skel, j, view, camera, mode, mx, my):
    """A joint drag in the plane through the joint: parallel to the screen ("screen"), to the floor
    ("floor") or upright and facing the camera ("vertical")."""
    p = skel.pos[j].copy()
    forward = normalize(camera.target - camera.eye())
    if mode == "floor":
        normal = np.array([0.0, 1.0, 0.0])
    elif mode == "vertical":
        normal = forward * (1.0, 0.0, 1.0)
        normal = normalize(normal) if np.linalg.norm(normal) > 1e-3 else np.array([0.0, 0.0, 1.0])
    else:
        normal = forward
    d = {"joint": j, "mode": mode, "normal": normal, "point": p, "offset": np.zeros(3)}
    hit = drag_plane_hit(d, view, mx, my)
    if hit is not None:
        d["offset"] = p - hit
    return d


def drag_plane_hit(d, view, mx, my):
    origin, direction = view.mouse_ray(mx, my)
    denom = direction @ d["normal"]
    if abs(denom) < 1e-6:
        return None
    t = (d["point"] - origin) @ d["normal"] / denom
    return origin + t * direction if t > 0 else None


def drag_target(d, view, mx, my):
    """Where the dragged joint should go for the mouse at (mx, my), or None."""
    hit = drag_plane_hit(d, view, mx, my)
    if hit is None:
        return None
    target = hit + d["offset"]
    if d["mode"] == "vertical":
        target = np.array([d["point"][0], target[1], d["point"][2]])
    return target


# --- exercises and pose files ------------------------------------------------

def find_exercise(name):
    return next((e for _, items in ex.CATEGORIES for e in items if e.name == name), None)


def search_exercises(query):
    """[(category, exercise)] of the exercises matching query (in English or the other language, accents
    optional), with (category, None) as the heading of each category."""
    words = i18n.fold(query).split()
    rows = []
    for category, items in ex.CATEGORIES:
        found = [e for e in items
                 if all(w in i18n.fold(" ".join(i18n.variants(e.name) | i18n.variants(category))) for w in words)]
        if found:
            rows += [(category, None)] + [(category, e) for e in found]
    return rows


def build_exercise(exercise, camera, size, limits_on=True):
    """(figures, equipment) of the exercise's positions side by side, seen from its best angle;
    turns the camera to that angle and frames them."""
    figures = [ex.build(p) for p in exercise.positions]
    parts = [ex.equipment(p, figure) for p, figure in zip(exercise.positions, figures)]
    camera.yaw, camera.pitch = exercise.view
    view = View(camera, size)
    parts = ex.arrange(figures, view.view[0, :3], parts=parts)  # left to right on screen
    for figure in figures:
        figure.limits_on = limits_on
    parts = [part for group in parts for part in group]
    camera.frame(*figures_bounds(figures, parts), view.size)
    return figures, parts


def figures_bounds(figures, parts):
    """Corners of a box around the figures and the equipment."""
    pos = np.concatenate([f.pos for f in figures] + [np.array(props.bounds(p)) for p in parts])
    return pos.min(axis=0), pos.max(axis=0)


def pose_file(figures, exercise=None, parts=()):
    """The figures as a pose file's JSON data (see the save format in CLAUDE.md)."""
    if len(figures) == 1:
        data = figures[0].to_dict()
    else:
        data = {"version": 2, "figures": [figure.to_dict() for figure in figures]}
    if exercise:
        data["exercise"] = exercise
    if parts:
        data["props"] = [props.to_dict(part) for part in parts]
    return data


def read_pose_file(data):
    """(figure dicts, exercise name, equipment) of a pose file's JSON data; raises ValueError,
    KeyError or TypeError if it's broken."""
    parts = [props.from_dict(part) for part in data.get("props", [])]
    return data.get("figures") or [data], data.get("exercise"), parts


# --- meshes --------------------------------------------------------------------

def face_meshes(skel):
    """[(positions, normals, triangles)] of each FACE shape wrapped onto the head; the last
    len(outline) positions are the outline."""
    head, frame = skel.pos[skel.index["head"]], skel.world[skel.index["head"]]
    meshes = []
    for _, outline, _ in FACE:
        outline = np.array(outline)
        centre, n = outline.mean(axis=0), len(outline)
        flat = np.vstack([centre] + [centre + (outline - centre) * k / FACE_RINGS
                                     for k in range(1, FACE_RINGS + 1)])
        normals = np.column_stack([flat, np.full(len(flat), sk.HEAD_RADIUS)])
        normals = normals / np.linalg.norm(normals, axis=1, keepdims=True) @ frame.T
        tris = [(0, 1 + s, 1 + (s + 1) % n) for s in range(n)]
        for k in range(1, FACE_RINGS):
            a, b = 1 + (k - 1) * n, 1 + k * n
            for s in range(n):
                t = (s + 1) % n
                tris += [(a + s, b + s, b + t), (a + s, b + t, a + t)]
        meshes.append((head + normals * (sk.HEAD_RADIUS + FACE_LIFT), normals, np.array(tris)))
    return meshes


def tattoo_mesh(skel, aspect):
    """(positions, normals, texcoords, triangles) of the tattoo, a strip wrapped round the forearm
    halfway between the elbow and the wrist; aspect is the image's width / height. Texcoords run
    from the top of the image (0) to the bottom (1), as in glTF. Vertex 2k, 2k + 1 are the wrist
    and elbow ends of row k, with row 0 along the bottom of the letters."""
    j = skel.index[TATTOO_BONE]
    elbow, hand = skel.pos[skel.parent[j]], skel.pos[j]
    axis = normalize(elbow - hand)  # the reading direction
    out = skel.world[j] @ np.array(TATTOO_SIDE)
    out = normalize(out - (out @ axis) * axis)
    up = np.cross(out, axis)  # towards the top of the letters
    room = np.linalg.norm(elbow - hand) - skel.radii[skel.parent[j]] - skel.radii[j] - 2 * TATTOO_MARGIN
    height = min(TATTOO_HEIGHT, max(room, 0.001) / aspect)
    radius, n = BONE_RADIUS + FACE_LIFT, TATTOO_SEGMENTS
    angles = (np.arange(n + 1) / n - 0.5) * height / radius
    normals = np.repeat(np.cos(angles)[:, None] * out + np.sin(angles)[:, None] * up, 2, axis=0)
    along = np.tile([-0.5, 0.5], n + 1)[:, None] * (height * aspect) * axis
    positions = (elbow + hand) / 2 + along + normals * radius
    texcoords = np.column_stack([np.tile([0.0, 1.0], n + 1), np.repeat(1 - np.arange(n + 1) / n, 2)])
    tris = np.array([t for k in range(n) for t in ((2 * k, 2 * k + 1, 2 * k + 3), (2 * k, 2 * k + 3, 2 * k + 2))])
    return positions, normals, texcoords, tris


def _lighter(color):
    return tuple(min(1.0, c + 0.25) for c in color)


def joint_style(skel, i, selected=None, hovered=None, clean=False):
    """(colour, size factor) of joint i as drawn; selected and hovered are joint indices in this figure
    (None for neither). Clean is the look of the exports: no highlights."""
    color, scale = SIDE_COLORS[skel.side(i)][1], 1.0
    if clean:
        return color, scale
    if i in skel.pins:
        color, scale = PINNED_COLOR, 1.35
    if i == selected:
        color = SELECTED_COLOR
    elif i == hovered:
        color = _lighter(color)
    if i == skel.index["head"]:
        scale = 1.0
    return color, scale


def face_color(skel, color, selected=None, hovered=None):
    """The colour of a FACE shape: it darkens to gold with the head selected, lightens with it hovered."""
    head = skel.index["head"]
    if selected == head:
        return tuple(c * 0.6 for c in SELECTED_COLOR)
    return _lighter(color) if hovered == head else color


# --- exports -------------------------------------------------------------------

def bone_name(skel, child):
    """A bone is named after the joint at its far end: l_elbow -> Left upper arm."""
    joint = skel.names[child]
    base = joint[2:] if skel.side(child) else joint
    return tr(sk.pretty_name(joint.replace(base, BONE_NAMES[base]))).capitalize()


def figure_label(n, count):
    """Prefix for the part names of figure n of count, when there is more than one."""
    return tr("Figure {}: ").format(n + 1) if count > 1 else ""


def model_parts(figures, parts, tattoo):
    """The figures as spheres, tubes and face meshes for the 3D export (gltf.build_glb), and the equipment."""
    out = [{"kind": "mesh", "name": tr(part["name"]), "positions": positions, "normals": normals,
            "triangles": tris, "color": props.COLOR}
           for part in parts for positions, normals, tris in [props.mesh(part)]]
    for n, skel in enumerate(figures):
        pos, label = skel.pos, figure_label(n, len(figures))
        out += [{"kind": "tube", "name": label + bone_name(skel, child), "a": pos[parent], "b": pos[child],
                 "radius": BONE_RADIUS, "color": SIDE_COLORS[skel.side(child)][0]}
                for parent, child in skel.bones]
        out += [{"kind": "sphere", "name": label + tr(sk.pretty_name(name)).capitalize(), "center": pos[i],
                 "radius": skel.radii[i], "color": SIDE_COLORS[skel.side(i)][1]}
                for i, name in enumerate(skel.names)]
        out += [{"kind": "mesh", "name": label + tr(name).capitalize(), "positions": positions,
                 "normals": normals, "triangles": tris, "color": color}
                for (name, _, color), (positions, normals, tris) in zip(FACE, face_meshes(skel))]
        positions, normals, texcoords, tris = tattoo_mesh(skel, tattoo.aspect)
        out.append({"kind": "mesh", "name": label + tr("Tattoo"), "positions": positions, "normals": normals,
                    "triangles": tris, "texcoords": texcoords, "image": tattoo.png, "color": TATTOO_COLOR})
    return out


def figure_shapes(figures, parts, view, tattoo):
    """The figures as flat 2D shapes (office_clip.py's shape dicts) seen in view, far to near."""
    px, items = view.px, []
    for n, skel in enumerate(figures):
        pos, label = skel.pos, figure_label(n, len(figures))
        nearest_bone = {}  # joint -> depth of the nearest bone ending there
        for parent, child in skel.bones:
            a, b = view.project(pos[parent]), view.project(pos[child])
            if a is None or b is None:
                continue
            depth = (a[2] + b[2]) / 2
            for j in (parent, child):
                nearest_bone[j] = min(depth, nearest_bone.get(j, depth))
            items.append((depth, {"kind": "line", "name": label + bone_name(skel, child), "a": a[:2], "b": b[:2],
                                  "width": 2 * BONE_RADIUS * px / depth,
                                  "color": SIDE_COLORS[skel.side(child)][0]}))

        head_depth = None
        for i, p in enumerate(pos):
            s = view.project(p)
            if s is None:
                continue
            # Joints cover the ends of their own bones, as the spheres do in 3D.
            depth = min(s[2] - skel.radii[i], nearest_bone.get(i, math.inf) - 1e-6)
            if i == skel.index["head"]:
                head_depth = depth
            color = SIDE_COLORS[skel.side(i)][1]
            items.append((depth, {"kind": "circle", "name": label + tr(sk.pretty_name(skel.names[i])).capitalize(),
                                  "center": s[:2], "radius": skel.radii[i] * px / s[2], "color": color,
                                  "outline": tuple(c * 0.6 for c in color)}))

        # The face goes just in front of the head, if it's turned towards the camera.
        for (name, outline, color), (positions, normals, _) in zip(FACE, face_meshes(skel)):
            points = view.project_all(positions[-len(outline):])
            if head_depth is None or points is None or normals[0] @ (view.eye - positions[0]) <= 0:
                continue
            items.append((head_depth - 1e-6, {"kind": "polygon", "name": label + tr(name).capitalize(),
                                              "points": [s[:2] for s in points], "color": color,
                                              "outline": tuple(c * 0.6 for c in color)}))
        shape = tattoo_shape(skel, view, tattoo)
        if shape is not None:
            depth, shape = shape
            items.append((depth, dict(shape, name=label + shape["name"])))
    items += prop_shapes(parts, view)
    items.sort(key=lambda item: -item[0])
    return [shape for _, shape in items]


def tattoo_shape(skel, view, tattoo):
    """(depth, shape) of the tattoo as a text box along the forearm, or None if it's turned away
    or too small. It goes just in front of the forearm, behind the joints."""
    positions, normals, _, _ = tattoo_mesh(skel, tattoo.aspect)
    middle = TATTOO_SEGMENTS  # the middle row's vertices: wrist end, then elbow end
    wrist, elbow = positions[middle], positions[middle + 1]
    centre = (wrist + elbow) / 2
    a, b, c = view.project(wrist), view.project(elbow), view.project(centre)
    if a is None or b is None or c is None or normals[middle] @ (view.eye - centre) <= 0:
        return None
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    # The line height round the arm, but no more than fits the length the forearm shows.
    height = min(np.linalg.norm(positions[0] - positions[-2]) * view.px / c[2], length / tattoo.aspect)
    if height < 1.0:
        return None
    j = skel.index[TATTOO_BONE]
    ends = view.project(skel.pos[skel.parent[j]]), view.project(skel.pos[j])
    depth = (ends[0][2] + ends[1][2]) / 2 - 5e-7 if None not in ends else c[2]
    return depth, {"kind": "text", "name": tr("Tattoo"), "text": TATTOO_TEXT, "center": c[:2],
                   "width": length, "height": height,
                   "angle": math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])),
                   "size": height * TATTOO_FONT[1] / tattoo.height, "font": TATTOO_FONT[0],
                   "bold": True, "color": TATTOO_COLOR}


def prop_shapes(parts, view):
    """[(depth, shape)] of the equipment for figure_shapes: box sides, thin cylinders as
    lines and thick ones (plates, weights) as their outline plus the end facing the camera."""
    eye, px, items = view.eye, view.px, []
    for part in parts:
        name = tr(part["name"])
        if part["kind"] == "box":
            for normal, corners in props.box_faces(part):
                points = view.project_all(corners)
                if points is None or normal @ (eye - corners[0]) <= 0:
                    continue
                # Sorted by its farthest corner, so it goes behind whatever rests on it.
                items.append((max(p[2] for p in points), prop_polygon(name, [p[:2] for p in points], normal)))
            continue
        a, b = part["a"], part["b"]
        if part["radius"] <= THIN_PROP:
            n = max(1, math.ceil(np.linalg.norm(b - a) / PROP_PIECE))
            ends = [view.project(a + (b - a) * k / n) for k in range(n + 1)]
            for p, q in zip(ends, ends[1:]):
                if p is not None and q is not None:
                    depth = (p[2] + q[2]) / 2
                    items.append((depth, {"kind": "line", "name": name, "a": p[:2], "b": q[:2],
                                          "width": 2 * part["radius"] * px / depth, "color": props.COLOR}))
            continue
        ring_a, ring_b = props.rings(part)
        points = view.project_all(np.concatenate([ring_a, ring_b]))
        if points is None:
            continue
        axis = normalize(b - a)
        side = eye - (a + b) / 2
        depth = sum(p[2] for p in points) / len(points)
        items.append((depth, prop_polygon(name, convex_hull([p[:2] for p in points]),
                                          normalize(side - (side @ axis) * axis))))
        end_a, end_b = points[:len(ring_a)], points[len(ring_a):]
        for end, normal, centre in ((end_a, -axis, a), (end_b, axis, b)):
            if normal @ (eye - centre) > 0:
                items.append((depth - 1e-6, prop_polygon(name, [p[:2] for p in end], normal)))
    return items


def prop_polygon(name, points, normal):
    """An equipment polygon, shaded about as the 3D view lights a surface facing normal."""
    light = 0.5 + 0.75 * max(0.0, float(normal @ normalize(np.array(LIGHT_DIR))))
    color = tuple(min(1.0, c * light) for c in props.COLOR)
    return {"kind": "polygon", "name": name, "points": points, "color": color,
            "outline": tuple(c * 0.6 for c in color)}
