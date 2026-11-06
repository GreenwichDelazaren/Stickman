"""Realistic range of motion for the stick man's joints.

Each limit constrains the rotation of one bone relative to its parent bone.
Directions are given in the parent bone's frame, which in the rest pose lines
up with the world: +x is the figure's left (outward for left limbs), +y is up
and +z is forward.  Limits are written for the left side; the right side is
mirrored automatically.  Angles are in degrees.
"""

import copy
import math

import numpy as np

from geometry import (MIRROR, angle_about, angle_between, normalize, perpendicular,
                      rotation_between, rotation_matrix, toward)

OUT = np.array([1.0, 0.0, 0.0])
IN = -OUT
UP = np.array([0.0, 1.0, 0.0])
DOWN = -UP
FORWARD = np.array([0.0, 0.0, 1.0])
BACK = -FORWARD


def arm_direction(elevation, azimuth):
    """Limb direction raised `elevation` degrees from hanging straight down, in
    the vertical plane at `azimuth` (0 out to the side, 90 forward, 180 across
    the body, -90 backward)."""
    a = math.radians(azimuth)
    return toward(DOWN, np.array([math.cos(a), 0.0, math.sin(a)]), elevation)


class Cone:
    """Ball joint.  The bone may point anywhere inside a boundary drawn around
    `center` and twist about its own axis within `twist` = (lo, hi).

    The boundary is either `swing`, a list of (direction, degrees) pairs giving
    how far the bone may tilt from the center towards each direction, or
    `boundary`, a list of explicit boundary directions.  Between boundary
    points the limit is interpolated.  Without `center` the bone's rest
    direction is used.  For left limbs positive twist turns inwards.
    """

    # Set by bind().
    rest: np.ndarray     # the bone's rest direction
    c: np.ndarray        # the center of the boundary
    neutral: np.ndarray  # rotation taking rest to c
    u: np.ndarray        # u, v: axes perpendicular to c, for azimuths
    v: np.ndarray
    phis: np.ndarray     # boundary azimuths (wrapped around) ...
    thetas: np.ndarray   # ... and how far the bone may tilt at each
    lo: float            # twist range, radians
    hi: float

    def __init__(self, swing=(), twist=(0, 0), center=None, boundary=()):
        self.swing = [(np.asarray(d, float), deg) for d, deg in swing]
        self.boundary = [np.asarray(b, float) for b in boundary]
        self.center = None if center is None else normalize(np.asarray(center, float))
        self.twist = twist

    def mirrored(self):
        return Cone([(MIRROR @ d, deg) for d, deg in self.swing], (-self.twist[1], -self.twist[0]),
                    None if self.center is None else MIRROR @ self.center,
                    [MIRROR @ b for b in self.boundary])

    def bind(self, rest_dir, parent_dir):
        """Copy of this limit set up for a bone whose rest direction is rest_dir."""
        b = copy.copy(self)
        b.rest = rest_dir
        b.c = rest_dir if self.center is None else self.center
        b.neutral = rotation_between(rest_dir, b.c)
        b.u = perpendicular(b.c)
        b.v = np.cross(b.c, b.u)
        points = self.boundary or [toward(b.c, d, deg) for d, deg in self.swing]
        table = sorted((b._azimuth(p), angle_between(b.c, p)) for p in points)
        phis = [phi for phi, _ in table]
        thetas = [theta for _, theta in table]
        b.phis = np.array([phis[-1] - 2 * math.pi] + phis + [phis[0] + 2 * math.pi])
        b.thetas = np.array([thetas[-1]] + thetas + [thetas[0]])
        b.lo, b.hi = (math.radians(t) for t in self.twist)
        return b

    def _azimuth(self, d):
        return math.atan2(float(d @ self.v), float(d @ self.u))

    def clamp(self, rot):
        d = rot @ self.rest
        swing = rotation_between(self.c, d)
        twist = _twist_angle((swing @ self.neutral).T @ rot, self.rest)
        theta = angle_between(self.c, d)
        if theta > 1e-9:
            m = normalize(d - math.cos(theta) * self.c)
            limit = float(np.interp(self._azimuth(m), self.phis, self.thetas))
            if theta > limit:
                swing = rotation_matrix(np.cross(self.c, m), limit)
        twist = min(max(twist, self.lo), self.hi)
        return swing @ self.neutral @ rotation_matrix(self.rest, twist)


class Hinge:
    """Hinge joint: bends one way only, from lo to hi degrees (0 = straight).
    The bending direction is taken from the slight bend of the rest pose."""

    # Set by bind().
    rest: np.ndarray      # the bone's rest direction
    straight: np.ndarray  # the parent bone's direction (bend 0)
    axis: np.ndarray      # the hinge axis
    rest_bend: float      # bend of the rest pose, radians

    def __init__(self, lo, hi):
        self.lo, self.hi = math.radians(lo), math.radians(hi)

    def mirrored(self):
        return self

    def bind(self, rest_dir, parent_dir):
        b = copy.copy(self)
        b.rest, b.straight = rest_dir, parent_dir
        b.axis = normalize(np.cross(parent_dir, rest_dir))
        b.rest_bend = angle_about(b.axis, parent_dir, rest_dir)
        return b

    def clamp(self, rot):
        d = rot @ self.rest
        flat = d - (d @ self.axis) * self.axis
        bend = angle_about(self.axis, self.straight, flat) if np.linalg.norm(flat) > 1e-9 else self.rest_bend
        if not self.lo <= bend <= self.hi:
            bend = self.lo if _arc(bend, self.lo) < _arc(bend, self.hi) else self.hi
        return rotation_matrix(self.axis, bend - self.rest_bend)


def _twist_angle(twist_rot, axis):
    p = perpendicular(axis)
    return angle_about(axis, p, twist_rot @ p)


def _arc(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


# Where the shoulder's reachable region is centred: out, slightly up, forward.
SHOULDER_CENTER = (0.6, 0.3, 0.75)

RANGE_OF_MOTION = {
    # joint:       (bone it moves, named by the joint at the bone's far end, limit)
    "lower back": ("chest", Cone([(FORWARD, 45), (BACK, 20), (OUT, 20), (IN, 20)],
                                 twist=(-10, 10), center=UP)),
    "upper back": ("neck", Cone([(FORWARD, 35), (BACK, 15), (OUT, 15), (IN, 15)],
                                twist=(-30, 30), center=UP)),
    "neck": ("head", Cone([(FORWARD, 50), (BACK, 60), (OUT, 40), (IN, 40)],
                          twist=(-75, 75), center=UP)),
    # Shoulder girdle: shrug up/down, shoulders forward/back.
    "collarbone": ("shoulder", Cone([(UP, 30), (DOWN, 8), (FORWARD, 25), (BACK, 20)])),
    # The arm can rise overhead to the front or side, cross the chest when
    # raised, but only reach a little across or behind the body when lowered.
    "shoulder": ("elbow", Cone(center=SHOULDER_CENTER, twist=(-100, 70), boundary=[
        arm_direction(20, 180),    # across the front of the hips
        arm_direction(70, 140),    # across the belly
        arm_direction(105, 140),   # across the chest
        arm_direction(150, 180),   # overhead, leaning over the head
        arm_direction(165, -90),   # overhead, slightly behind
        arm_direction(100, -40),   # out to the side and pulled back
        arm_direction(60, -90),    # straight back
        arm_direction(45, -140),   # behind the back
    ])),
    "elbow": ("hand", Hinge(0, 150)),
    "hip": ("knee", Cone([(FORWARD, 125), (BACK, 20), (OUT, 45), (IN, 30)],
                         twist=(-45, 40), center=DOWN)),
    "knee": ("ankle", Hinge(0, 150)),
    "ankle": ("toe", Cone([(UP, 35), (DOWN, 45), (IN, 25), (OUT, 15)])),
}
