"""Small vector and rotation helpers."""

import math

import numpy as np

MIRROR = np.diag([-1.0, 1.0, 1.0])  # reflection swapping the figure's left and right


def normalize(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def rotation_matrix(axis, angle):
    axis = np.asarray(axis, float)
    if np.linalg.norm(axis) < 1e-12:
        return np.identity(3)
    x, y, z = normalize(axis)
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return np.array([
        [c + x * x * t, x * y * t - z * s, x * z * t + y * s],
        [y * x * t + z * s, c + y * y * t, y * z * t - x * s],
        [z * x * t - y * s, z * y * t + x * s, c + z * z * t],
    ])


def perpendicular(v):
    """Some unit vector perpendicular to v."""
    helper = (1.0, 0.0, 0.0) if abs(v[0]) < 0.9 else (0.0, 1.0, 0.0)
    return normalize(np.cross(v, helper))


def rotation_between(u, v):
    """Smallest rotation that turns direction u into direction v."""
    u, v = normalize(u), normalize(v)
    axis = np.cross(u, v)
    sin, cos = np.linalg.norm(axis), float(np.dot(u, v))
    if sin < 1e-9:
        return np.identity(3) if cos > 0 else rotation_matrix(perpendicular(u), math.pi)
    return rotation_matrix(axis, math.atan2(sin, cos))


def angle_between(u, v):
    return math.acos(max(-1.0, min(1.0, float(np.dot(normalize(u), normalize(v))))))


def angle_about(axis, a, b):
    """Signed angle from a to b around axis (a and b perpendicular to axis)."""
    return math.atan2(float(np.dot(np.cross(a, b), axis)), float(np.dot(a, b)))


def toward(a, b, degrees):
    """Direction a tilted towards direction b by the given angle."""
    return rotation_matrix(np.cross(a, b), math.radians(degrees)) @ normalize(np.asarray(a, float))


def orthonormalize(m):
    """Nearest proper rotation matrix to m."""
    u, _, vt = np.linalg.svd(m)
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    return u @ vt


def convex_hull(points):
    """The convex hull of 2D points, in order round the outline."""
    points = sorted(map(tuple, points))
    if len(points) < 3:
        return points

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]

    return half(points) + half(reversed(points))
