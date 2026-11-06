"""Plain gray equipment shown with the figures (bars, plates, dumbbells,
benches, boxes, walls), made of cylinders and boxes.

A part is a dict in world coordinates (metres, y up):
  {"kind": "cylinder", "name", "a": (x, y, z), "b": (x, y, z), "radius"}  closed at both ends
  {"kind": "box", "name", "lo": (x, y, z), "hi": (x, y, z)}              sides along the axes
Parts are never changed in place (moved() makes a new one), so undo states can
share them.  Names are English and translated where they're shown.

No pygame or OpenGL here.
"""

import numpy as np

from geometry import normalize, perpendicular

COLOR = (0.62, 0.63, 0.65)
SEGMENTS = 24

BAR_RADIUS = 0.016
POST_RADIUS = 0.024
CABLE_RADIUS = 0.006
BARBELL_LENGTH = 1.5
PLATE_RADIUS, PLATE_WIDTH = 0.2, 0.05
PLATE_INSET = 0.15  # from the end of the bar to the middle of a plate


def cylinder(name, a, b, radius):
    return {"kind": "cylinder", "name": name, "a": np.asarray(a, float), "b": np.asarray(b, float),
            "radius": float(radius)}


def box(name, lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return {"kind": "box", "name": name, "lo": np.minimum(lo, hi), "hi": np.maximum(lo, hi)}


def moved(part, offset):
    keys = ("a", "b") if part["kind"] == "cylinder" else ("lo", "hi")
    return part | {k: part[k] + offset for k in keys}


def bounds(part):
    """(lowest corner, highest corner) of a box around the part."""
    if part["kind"] == "box":
        return part["lo"], part["hi"]
    a, b, r = part["a"], part["b"], part["radius"]
    return np.minimum(a, b) - r, np.maximum(a, b) + r


def to_dict(part):
    return {k: np.round(v, 5).tolist() if isinstance(v, np.ndarray) else v for k, v in part.items()}


def from_dict(data):
    if data.get("kind") == "box":
        return box(data.get("name", "Box"), data["lo"], data["hi"])
    return cylinder(data.get("name", "Bar"), data["a"], data["b"], data["radius"])


# --- surfaces ----------------------------------------------------------------

def rings(part, segments=SEGMENTS):
    """The circles at the a and b ends of a cylinder, anticlockwise about a -> b."""
    a, b = part["a"], part["b"]
    axis = normalize(b - a)
    u = perpendicular(axis)
    v = np.cross(axis, u)
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)[:, None]
    ring = part["radius"] * (np.cos(angles) * u + np.sin(angles) * v)
    return a + ring, b + ring


def box_faces(part):
    """[(outward normal, 4 corners anticlockwise seen from outside)] of a box."""
    lo, hi = part["lo"], part["hi"]
    faces = []
    for k in range(3):
        u, v = (k + 1) % 3, (k + 2) % 3
        for sign in (-1, 1):
            square = [(0, 0), (1, 0), (1, 1), (0, 1)]
            if sign < 0:
                square.reverse()
            corners = []
            for i, j in square:
                p = np.empty(3)
                p[k] = hi[k] if sign > 0 else lo[k]
                p[u], p[v] = (lo[u], hi[u])[i], (lo[v], hi[v])[j]
                corners.append(p)
            faces.append((np.eye(3)[k] * sign, corners))
    return faces


def mesh(part):
    """(positions, normals, triangle indices) of the part's closed surface,
    triangles anticlockwise seen from outside."""
    if part["kind"] == "box":
        faces = box_faces(part)
        positions = np.array([c for _, corners in faces for c in corners])
        normals = np.repeat([n for n, _ in faces], 4, axis=0)
        tris = [t for f in range(6) for t in ((4 * f, 4 * f + 1, 4 * f + 2), (4 * f, 4 * f + 2, 4 * f + 3))]
        return positions, normals, np.array(tris)
    ring_a, ring_b = rings(part)
    n = len(ring_a)
    axis = normalize(part["b"] - part["a"])
    radial = (ring_a - part["a"]) / part["radius"]
    # The side, then a fan for each end (centre first).
    positions = np.concatenate([ring_a, ring_b, [part["a"]], ring_a, [part["b"]], ring_b])
    normals = np.concatenate([radial, radial, np.tile(-axis, (n + 1, 1)), np.tile(axis, (n + 1, 1))])
    tris = []
    for s in range(n):
        t = (s + 1) % n
        tris += [(s, t, n + s), (t, n + t, n + s)]
        tris.append((2 * n, 2 * n + 1 + t, 2 * n + 1 + s))
        tris.append((3 * n + 1, 3 * n + 2 + s, 3 * n + 2 + t))
    return positions, normals, np.array(tris)


# --- equipment ---------------------------------------------------------------

def bar(centre, axis, length, radius=BAR_RADIUS, name="Bar"):
    """A cylinder of the given length centred on centre along axis."""
    half = normalize(np.asarray(axis, float)) * length / 2
    return cylinder(name, centre - half, centre + half, radius)


def barbell(centre, axis, plate_radius=PLATE_RADIUS):
    axis = normalize(np.asarray(axis, float))
    parts = [bar(centre, axis, BARBELL_LENGTH)]
    for sign in (-1, 1):
        middle = centre + sign * axis * (BARBELL_LENGTH / 2 - PLATE_INSET)
        parts.append(bar(middle, axis, PLATE_WIDTH, plate_radius, "Plate"))
    return parts


def dumbbell(centre, axis):
    axis = normalize(np.asarray(axis, float))
    return [bar(centre, axis, 0.3, BAR_RADIUS, "Dumbbell")] + \
           [bar(centre + sign * axis * 0.11, axis, 0.08, 0.045, "Dumbbell") for sign in (-1, 1)]


def kettlebell(top, down):
    """A kettlebell hanging from top (the handle) in direction down."""
    down = normalize(np.asarray(down, float))
    return [bar(top + down * 0.03, down, 0.06, 0.03, "Kettlebell"),
            bar(top + down * 0.13, down, 0.14, 0.085, "Kettlebell")]


def bar_on_posts(a, b):
    """A horizontal bar from a to b held up by a post from the floor at each end."""
    parts = [cylinder("Bar", a, b, BAR_RADIUS)]
    for end in (a, b):
        parts.append(cylinder("Post", (end[0], 0.0, end[2]), end + (0.0, POST_RADIUS, 0.0), POST_RADIUS))
    return parts
