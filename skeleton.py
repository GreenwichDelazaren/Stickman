"""Stick figure skeleton with fixed bone lengths and realistic joint limits.

The pose is stored as rotations: the pelvis has a world position and
orientation, and every other bone a rotation relative to its parent bone.
Joint positions follow from these (forward kinematics), so bone lengths can
never change, and each rotation is kept within the joint's range of motion
(see joint_limits.py).

World coordinates are metres: y points up and the floor is the plane y = 0.
In the rest pose the figure faces +z, so its left side is +x.
"""

import math

import numpy as np

from geometry import MIRROR, angle_between, normalize, orthonormalize, rotation_between, rotation_matrix
from joint_limits import RANGE_OF_MOTION, Hinge

JOINT_RADIUS = 0.032
HEAD_RADIUS = 0.11
# How far (metres) a drag may leave a joint dipping into the floor; covers
# the inaccuracy of the IK solver.
FLOOR_TOLERANCE = 0.001

_CENTER = [
    ("pelvis", None, (0.00, 0.95, 0.00)),
    ("chest", "pelvis", (0.00, 1.28, 0.00)),
    ("neck", "chest", (0.00, 1.47, 0.00)),
    ("head", "neck", (0.00, 1.62, 0.01)),
]
# Elbows and knees start slightly bent: this sets the direction they bend in.
_LEFT = [
    ("l_shoulder", "neck", (0.19, 1.44, 0.00)),
    ("l_elbow", "l_shoulder", (0.22, 1.16, -0.04)),
    ("l_hand", "l_elbow", (0.24, 0.91, 0.03)),
    ("l_hip", "pelvis", (0.10, 0.92, 0.00)),
    ("l_knee", "l_hip", (0.11, 0.51, 0.04)),
    ("l_ankle", "l_knee", (0.12, 0.09, 0.00)),
    ("l_toe", "l_ankle", (0.12, JOINT_RADIUS, 0.15)),
]
_RIGHT = [
    ("r" + name[1:], parent if parent in ("neck", "pelvis") else "r" + parent[1:], (-x, y, z))
    for name, parent, (x, y, z) in _LEFT
]
JOINTS = _CENTER + _LEFT + _RIGHT  # parents always come before their children

# The pelvis and both hips form one rigid body.
PELVIS_PARTS = ("pelvis", "l_hip", "r_hip")

# The joint that stays fixed while a joint is dragged; the bones between the
# two bend to follow the mouse.  Dragging the pelvis moves the whole figure
# and dragging a hip tilts the pelvis.
DRAG_ANCHOR = {"chest": "pelvis", "neck": "pelvis", "head": "neck"}
for _s in "lr":
    DRAG_ANCHOR.update({
        f"{_s}_shoulder": "neck",
        f"{_s}_elbow": f"{_s}_shoulder",
        f"{_s}_hand": f"{_s}_shoulder",
        f"{_s}_knee": f"{_s}_hip",
        f"{_s}_ankle": f"{_s}_hip",
        f"{_s}_toe": f"{_s}_ankle",
    })


def pretty_name(name):
    return name.replace("l_", "left ").replace("r_", "right ")


def _frame(a, b):
    """Rotation whose columns are a, b made perpendicular to a, and their cross product."""
    a = normalize(a)
    b = normalize(b - (b @ a) * a)
    return np.column_stack([a, b, np.cross(a, b)])


class Skeleton:
    def __init__(self):
        self.names = [name for name, _, _ in JOINTS]
        self.index = {name: i for i, name in enumerate(self.names)}
        self.parent = [self.index[p] if p else -1 for _, p, _ in JOINTS]
        self.rest = np.array([p for _, _, p in JOINTS], float)
        self.offset = np.array([self.rest[i] - self.rest[p] if p >= 0 else np.zeros(3)
                                for i, p in enumerate(self.parent)])
        self.bones = [(p, i) for i, p in enumerate(self.parent) if p >= 0]
        # Body part that carries each joint: the pelvis (index 0) carries the
        # hips; any other joint is carried by the bone that ends at it.
        self.part = [0 if n in PELVIS_PARTS else i for i, n in enumerate(self.names)]
        self.radii = np.full(len(self.names), JOINT_RADIUS)
        self.radii[self.index["head"]] = HEAD_RADIUS
        self.limits = {}
        for bone, spec in RANGE_OF_MOTION.values():
            sided = bone not in self.index
            for name, sp in ([(f"l_{bone}", spec), (f"r_{bone}", spec.mirrored())] if sided
                             else [(bone, spec)]):
                i = self.index[name]
                self.limits[i] = sp.bind(normalize(self.offset[i]), normalize(self.offset[self.parent[i]]))
        self.limits_on = True
        self.world = np.zeros((len(self.names), 3, 3))
        self.reset()

    def side(self, j):
        prefix = self.names[j][:2]
        return prefix[0] if prefix in ("l_", "r_") else None

    # --- kinematics --------------------------------------------------------

    def _fk(self):
        pos = np.empty_like(self.rest)
        self.world[0] = self.rot[0]
        pos[0] = self.root
        for j in range(1, len(self.names)):
            p = self.parent[j]
            if self.part[j] == j:
                self.world[j] = self.world[self.part[p]] @ self.rot[j]
            pos[j] = pos[p] + self.world[self.part[j]] @ self.offset[j]
        self.pos = pos

    def _limit(self, i, rot):
        limit = self.limits.get(i)
        return limit.clamp(rot) if limit and self.limits_on else rot

    def _solve(self, effector, anchor, target, iterations=30):
        """Turn the bones between anchor and effector so the effector gets as
        close to target as the joint limits allow (cyclic coordinate descent)."""
        chain = []
        j = effector
        while j != anchor:
            chain.append(j)
            j = self.parent[j]
        chain.reverse()
        base_world = self.world[self.part[anchor]].copy()
        base = self.pos[anchor].copy()

        def links():
            worlds, points, w = [], [base], base_world
            for s in chain:
                w = w @ self.rot[s]
                worlds.append(w)
                points.append(points[-1] + w @ self.offset[s])
            return worlds, points

        def aim(k):
            worlds, points = links()
            current, wanted = points[-1] - points[k], target - points[k]
            if np.linalg.norm(current) < 1e-9 or np.linalg.norm(wanted) < 1e-9:
                return
            turned = rotation_between(current, wanted) @ worlds[k]
            above = worlds[k - 1] if k else base_world
            self.rot[chain[k]] = self._limit(chain[k], above.T @ turned)

        def error():
            return np.linalg.norm(links()[1][-1] - target)

        if len(chain) == 2 and isinstance(self.limits.get(chain[1]), Hinge):
            # Arm or leg: bend the elbow / knee exactly enough, then aim the limb.
            self._bend_to_reach(chain, np.linalg.norm(target - base))
            aim(0)
        err = error()
        for _ in range(iterations):
            if err < 1e-4:
                break
            for k in reversed(range(len(chain))):
                aim(k)
            new_err = error()
            if err - new_err < 1e-6:
                break
            err = new_err
        self._fk()

    def _bend_to_reach(self, chain, distance):
        """Set the hinge between the two bones of chain so their ends are distance apart."""
        upper, lower = chain
        hinge = self.limits[lower]
        a, b = np.linalg.norm(self.offset[upper]), np.linalg.norm(self.offset[lower])
        bend = math.acos(max(-1.0, min(1.0, (distance ** 2 - a * a - b * b) / (2 * a * b))))
        if self.limits_on:
            bend = min(max(bend, hinge.lo), hinge.hi)
        self.rot[lower] = rotation_matrix(hinge.axis, bend - hinge.rest_bend)

    # --- state -------------------------------------------------------------

    def reset(self):
        self.root = self.rest[0].copy()
        self.rot = np.tile(np.identity(3), (len(self.names), 1, 1))
        self.pins = {}  # joint index -> position it is pinned to
        self._fk()

    def state(self):
        return self.root.copy(), self.rot.copy(), {j: p.copy() for j, p in self.pins.items()}

    def set_state(self, state):
        root, rot, pins = state
        self.root, self.rot = root.copy(), rot.copy()
        self.pins = {j: p.copy() for j, p in pins.items()}
        self._fk()

    def to_dict(self):
        return {
            "version": 2,
            "joints": {n: [round(float(v), 5) for v in self.pos[i]] for i, n in enumerate(self.names)},
            "pinned": [self.names[j] for j in sorted(self.pins)],
            "root": [round(float(v), 5) for v in self.root],
            # Rotation of each bone relative to its parent, named by the joint
            # at the bone's far end ("pelvis" is the pelvis orientation).
            "rotations": {self.names[i]: np.round(self.rot[i], 6).tolist()
                          for i in range(len(self.names)) if self.part[i] == i},
        }

    def from_dict(self, data):
        self.reset()
        joints = {n: np.asarray(p, float) for n, p in data.get("joints", {}).items() if n in self.index}
        if "rotations" in data:
            self.root = np.asarray(data.get("root", self.root), float)
            for name, m in data["rotations"].items():
                if name in self.index:
                    self.rot[self.index[name]] = orthonormalize(np.asarray(m, float))
            for i in self.limits:
                self.rot[i] = self._limit(i, self.rot[i])
            self._fk()
        else:
            self._fit_positions(joints)
        self.pins = {self.index[n]: self.pos[self.index[n]].copy()
                     for n in data.get("pinned", []) if n in self.index}

    def _fit_positions(self, joints):
        """Approximate a pose saved as joint positions only (older files)."""
        if "pelvis" in joints:
            self.root = joints["pelvis"].copy()
        if all(n in joints for n in ("l_hip", "r_hip", "chest")):
            lateral = normalize(joints["l_hip"] - joints["r_hip"])
            up = joints["chest"] - self.root
            up = normalize(up - (up @ lateral) * lateral)
            self.rot[0] = np.column_stack([lateral, up, np.cross(lateral, up)])
        self._fk()
        for i, name in enumerate(self.names):
            if i and self.part[i] == i and name in joints:
                self._solve(i, self.parent[i], joints[name])
        for name in ("l_hand", "r_hand", "l_ankle", "r_ankle"):
            if name in joints:
                self._solve(self.index[name], self.index[DRAG_ANCHOR[name]], joints[name])

    # --- editing -----------------------------------------------------------

    def _floor_limits(self):
        """How low each joint centre may go in a drag or twist: down to the
        floor, or no lower than it already is if the whole figure was lowered
        below the floor."""
        return np.minimum(self.radii - FLOOR_TOLERANCE, self.pos[:, 1])

    def _above(self, limits):
        return bool(np.all(self.pos[:, 1] >= limits - 1e-9))

    def drag(self, j, target):
        """Move joint j as close to target as bone lengths and joint limits
        allow, without pushing any joint into the floor: the dragged joint
        slides along it, and the drag stops where another joint touches it."""
        target = np.asarray(target, float)
        limits, before, start = self._floor_limits(), self.state(), self.pos[j].copy()
        lowest = np.minimum(self.radii, self.pos[:, 1])
        if j == 0:  # the whole figure moves with the pelvis
            target[1] = max(target[1], start[1] + np.max(lowest - self.pos[:, 1]))
        else:
            target[1] = max(target[1], lowest[j])
        self._drag(j, target)
        if self._above(limits):
            return
        # Something else went into the floor: go as far towards target as possible.
        done, over = 0.0, 1.0
        for _ in range(7):
            t = (done + over) / 2
            self.set_state(before)
            self._drag(j, start + t * (target - start))
            if self._above(limits):
                done = t
            else:
                over = t
        self.set_state(before)
        if done > 0:
            self._drag(j, start + done * (target - start))

    def _drag(self, j, target):
        if j == 0:
            self.root = self.root + target - self.pos[0]
            self._fk()
        elif self.part[j] == 0:
            self._tilt_pelvis(j, target)
        else:
            self._solve(j, self.index[DRAG_ANCHOR[self.names[j]]], target)
        if j in self.pins:
            self.pins[j] = self.pos[j].copy()
        self._satisfy_pins(skip=j)

    def _tilt_pelvis(self, hip, target):
        """Turn the pelvis towards target; trunk and thighs keep their direction where they can."""
        center = self.pos[0]
        turn = rotation_between(self.pos[hip] - center, target - center)
        attached = [i for i in range(1, len(self.names))
                    if self.part[i] == i and self.part[self.parent[i]] == 0]
        keep = {i: self.world[i].copy() for i in attached}
        self.rot[0] = turn @ self.rot[0]
        for i, world in keep.items():
            self.rot[i] = self._limit(i, self.rot[0].T @ world)
        self._fk()

    def _satisfy_pins(self, skip=None):
        for _ in range(3):
            moved = False
            for j in sorted(self.pins):
                if j == skip or self.part[j] == 0:
                    continue
                if np.linalg.norm(self.pos[j] - self.pins[j]) > 1e-3:
                    self._solve(j, self.index[DRAG_ANCHOR[self.names[j]]], self.pins[j])
                    moved = True
            if not moved:
                break

    def twist(self, j, degrees):
        """Twist the bone ending at joint j about its own axis.  For a hand or
        ankle, swing the elbow or knee around instead, keeping the hand or foot
        in place.  Returns False if nothing moved or a joint would go into the floor."""
        saved, limits = self.state(), self._floor_limits()
        before, world_before = self.pos.copy(), self.world.copy()
        angle = math.radians(degrees)
        name = self.names[j]
        if name.endswith(("_hand", "_ankle")):
            anchor, upper = self.index[DRAG_ANCHOR[name]], self.parent[j]
            turned = rotation_matrix(self.pos[j] - self.pos[anchor], angle) @ self.world[upper]
            self.rot[upper] = self._limit(upper, self.world[self.part[anchor]].T @ turned)
            self._fk()
            self._solve(j, anchor, before[j])
        elif self.part[j] == j:
            self.rot[j] = self._limit(j, self.rot[j] @ rotation_matrix(self.offset[j], angle))
            self._fk()
        else:
            return False
        self._satisfy_pins()
        if not self._above(limits):
            self.set_state(saved)
            return False
        # Turning the head moves no joint, only its orientation.
        return np.abs(self.pos - before).max() > 1e-6 or np.abs(self.world - world_before).max() > 1e-6

    def set_limits(self, on):
        self.limits_on = on
        if on:
            for i in self.limits:
                self.rot[i] = self._limit(i, self.rot[i])
            self._fk()
            self._satisfy_pins()

    def toggle_pin(self, j):
        if j in self.pins:
            del self.pins[j]
        else:
            self.pins[j] = self.pos[j].copy()

    def clear_pins(self):
        self.pins = {}

    def turn(self, kind, degrees):
        """Rotate the whole figure about the pelvis: kind is yaw, pitch or roll."""
        pelvis = self.world[0]
        axis = {"yaw": (0.0, 1.0, 0.0), "pitch": pelvis[:, 0], "roll": pelvis[:, 2]}[kind]
        self.rotate(rotation_matrix(axis, math.radians(degrees)))

    def rotate(self, rot):
        """Rotate the whole figure about the pelvis by the rotation matrix rot."""
        center = self.pos[0].copy()
        self.rot[0] = rot @ self.rot[0]
        self.pins = {j: center + rot @ (p - center) for j, p in self.pins.items()}
        self._fk()

    def level(self, a, b, rise=0.0):
        """Tip the whole figure so joint b is rise metres above joint a (at
        the same height by default)."""
        d = self.pos[b] - self.pos[a]
        flat = normalize(d * (1.0, 0.0, 1.0))
        length = np.linalg.norm(d)
        if np.linalg.norm(flat) > 1e-6 and abs(rise) < length:
            self.rotate(rotation_between(d, flat * math.sqrt(length ** 2 - rise ** 2) + (0.0, rise, 0.0)))

    # --- posing by directions (used by the exercise library) ----------------

    def orient(self, up, front):
        """Turn the pelvis so the spine starts out along up and the body faces front."""
        up = normalize(np.asarray(up, float))
        front = normalize(front - (front @ up) * up)
        self.rot[0] = np.column_stack([np.cross(up, front), up, front])
        self._fk()

    def aim(self, j, direction, twist=0.0):
        """Point the bone ending at joint j in a world direction, twisted by
        degrees about its own axis, as far as its joint limits allow."""
        base = self.world[self.part[self.parent[j]]]
        rest = normalize(self.offset[j])
        rot = rotation_between(rest, base.T @ direction) @ rotation_matrix(rest, math.radians(twist))
        self.rot[j] = self._limit(j, rot)
        self._fk()

    def aim_limb(self, end, upper_dir, lower_dir):
        """Point the two bones of an arm or leg in world directions: end is the
        hand or ankle, the elbow or knee bends to match."""
        lower, upper = end, self.parent[end]
        anchor = self.parent[upper]
        hinge = self.limits[lower]
        u, l = normalize(np.asarray(upper_dir, float)), normalize(np.asarray(lower_dir, float))
        bend = angle_between(u, l)
        if self.limits_on:
            bend = min(max(bend, hinge.lo), hinge.hi)
        self.rot[lower] = rotation_matrix(hinge.axis, bend - hinge.rest_bend)
        base = self.world[self.part[anchor]]
        rest = normalize(self.offset[upper])
        if bend < math.radians(6):
            # Nearly straight: the bend doesn't fix the twist, so keep the rest twist.
            world = base @ rotation_between(rest, base.T @ u)
        else:
            # Twist the upper bone so the bend points the lower bone the right way.
            world = _frame(u, l) @ _frame(rest, self.rot[lower] @ normalize(self.offset[lower])).T
        self.rot[upper] = self._limit(upper, base.T @ world)
        self._fk()
        lengths = np.linalg.norm(self.offset[[upper, lower]], axis=1)
        target = self.pos[anchor] + lengths[0] * u + lengths[1] * l
        if np.linalg.norm(self.pos[end] - target) > 0.02:  # a limit got in the way
            self._solve(end, anchor, target)

    def shrug(self, side, degrees):
        """Raise (or with negative degrees lower) the shoulder on side 'l' or 'r'."""
        j = self.index[side + "_shoulder"]
        neck = self.world[self.index["neck"]]
        current = neck @ normalize(self.offset[j])
        self.aim(j, rotation_matrix(np.cross(current, neck[:, 1]), math.radians(degrees)) @ current)

    def translate(self, offset):
        self.root = self.root + offset
        self.pins = {j: p + offset for j, p in self.pins.items()}
        self._fk()

    def drop_to_ground(self):
        lift = -np.min(self.pos[:, 1] - self.radii)
        self.translate(np.array([0.0, lift, 0.0]))

    def mirror(self, src):
        """Copy the pose (and pins) of side src ('l' or 'r') onto the other side."""
        dst = "r" if src == "l" else "l"
        for i, name in enumerate(self.names):
            if name.startswith(dst + "_") and self.part[i] == i:
                self.rot[i] = MIRROR @ self.rot[self.index[src + name[1:]]] @ MIRROR
        self._fk()
        for i, name in enumerate(self.names):
            if name.startswith(dst + "_"):
                if self.index[src + name[1:]] in self.pins:
                    self.pins[i] = self.pos[i].copy()
                else:
                    self.pins.pop(i, None)
