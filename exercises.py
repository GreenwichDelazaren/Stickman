"""Library of exercises, each shown by one or two positions of the figure.

A position is a dict of bone directions in world coordinates (y up; a
standing figure faces +z, so its left is +x).  Every key is optional:

  body          direction of the spine from the pelvis (default up)
  front         the way the front of the pelvis faces (default: forward,
                tipped along with body, so body=FWD lies face down and
                body=BACK lies face up)
  chest, neck, head
                directions of the lower spine, upper spine and neck bones
                (each defaults to the one before)
  twist         degrees the shoulders turn to the figure's left
  look          degrees the head turns to the left
  shrug         degrees both shoulders are raised
  arms, legs    (upper bone, lower bone) directions: upper arm and forearm,
                or thigh and shin
  feet          direction from the ankle to the toes
  l_arm, r_arm, l_leg, r_leg, l_foot, r_foot
                the same for one side only
  rotate        [(axis, degrees)] turns of the whole finished figure
  level         (joint, joint) tip the figure so both are at the same height,
                or (joint, joint, metres) so the second is that much higher
  hang          height of the hands above the floor (hanging from a bar);
                otherwise the figure stands on the floor
  lift          extra height above the floor (jumps, steps, boxes)
  props         equipment: functions that take the built figure and return
                gray objects (props.py parts) placed from its joints; they
                aren't mirrored

Sided directions are written for the left side, with +x pointing outwards,
and mirrored for the right.  Arms and legs wrapped in Rel(...) are given in
the body's own frame instead (the upper back for arms, the pelvis for legs),
as if the figure were standing, so they follow the trunk.  Joint limits
apply, so a direction a joint can't reach stops at its limit.

No pygame or OpenGL here.
"""

import math
from typing import NamedTuple

import numpy as np

import props
import skeleton as sk
from geometry import MIRROR, normalize, rotation_between, rotation_matrix, toward
from joint_limits import arm_direction

UP = np.array([0.0, 1.0, 0.0])
DOWN = -UP
FWD = np.array([0.0, 0.0, 1.0])
BACK = -FWD
OUT = np.array([1.0, 0.0, 0.0])  # outwards for the left side
IN = -OUT

# Camera (yaw, pitch) that shows an exercise best.  The side view looks at
# the figure's left side.
SIDE = (70, 10)
FRONT = (25, 8)
ABOVE = (60, 35)


def v(x, y, z):
    return normalize(np.array([x, y, z], float))


def tilt(a, b, degrees):
    """Direction a tilted towards b by degrees."""
    return toward(a, b, degrees)


def limb(elevation, azimuth):
    """Raised elevation degrees from straight down, towards azimuth (0 out to
    the side, 90 forward, 180 across the body, -90 back)."""
    return arm_direction(elevation, azimuth)


def flat(out=0):
    """Foot flat on the floor, heel to toes, pointing forward and turned out by degrees."""
    return rotation_matrix(UP, math.radians(out)) @ FWD


class Rel(tuple):
    """Limb directions in the body's own frame rather than the world's."""

    def __new__(cls, *dirs):
        return super().__new__(cls, dirs)


class Exercise(NamedTuple):
    name: str
    positions: list
    view: tuple = SIDE


def mirrored(p):
    """The same position with left and right swapped."""
    out = {}
    for key, value in p.items():
        if key[:2] in ("l_", "r_"):
            out[("r_" if key[0] == "l" else "l_") + key[2:]] = value
        elif key in ("body", "front", "chest", "neck", "head"):
            out[key] = MIRROR @ value
        elif key in ("twist", "look"):
            out[key] = -value
        elif key == "rotate":
            out[key] = [(MIRROR @ np.asarray(axis, float), -deg) for axis, deg in value]
        elif key == "level":
            out[key] = tuple(("r_" if n[0] == "l" else "l_") + n[2:]
                             if isinstance(n, str) and n[:2] in ("l_", "r_") else n for n in value)
        else:
            out[key] = value
    return out


def _sided(p, part, plural, side):
    value = p.get(f"{side}_{part}", p.get(plural))
    if value is None or side == "l":
        return value
    flipped = [MIRROR @ np.asarray(d, float) for d in (value if part != "foot" else [value])]
    if part == "foot":
        return flipped[0]
    return Rel(*flipped) if isinstance(value, Rel) else tuple(flipped)


def build(p):
    """A Skeleton in position p."""
    s = sk.Skeleton()
    i = s.index
    body = np.asarray(p.get("body", UP), float)
    s.orient(body, p.get("front", rotation_between(UP, body) @ FWD))
    twist = p.get("twist", 0)
    lower_twist = max(-10, min(10, twist / 4))
    chest = p.get("chest", body)
    neck = p.get("neck", chest)
    s.aim(i["chest"], chest, lower_twist)
    s.aim(i["neck"], neck, twist - lower_twist)
    s.aim(i["head"], p.get("head", neck), p.get("look", 0))
    if p.get("shrug"):
        for side in "lr":
            s.shrug(side, p["shrug"])
    for side in "lr":
        for part, plural, end, frame in (("arm", "arms", "_hand", i["neck"]), ("leg", "legs", "_ankle", 0)):
            dirs = _sided(p, part, plural, side)
            if dirs is not None:
                if isinstance(dirs, Rel):
                    dirs = [s.world[frame] @ d for d in dirs]
                s.aim_limb(i[side + end], *dirs)
        foot = _sided(p, "foot", "feet", side)
        if foot is not None:
            s.aim(i[side + "_toe"], foot)
    for axis, degrees in p.get("rotate", ()):
        s.rotate(rotation_matrix(axis, math.radians(degrees)))
    if "level" in p:
        a, b, *rise = p["level"]
        s.level(i[a], i[b], *rise)
    if "hang" in p:
        hands = (s.pos[i["l_hand"], 1] + s.pos[i["r_hand"], 1]) / 2
        s.translate(np.array([0.0, p["hang"] - hands, 0.0]))
    else:
        s.drop_to_ground()
    s.translate(np.array([0.0, p.get("lift", 0.0), 0.0]))
    return s


def equipment(p, s):
    """The gray objects (props.py parts) of position p, placed around its built figure s."""
    return [part for place in p.get("props", ()) for part in place(s)]


def arrange(figures, right, gap=0.45, parts=None):
    """Centre the figures on the origin, side by side along the horizontal
    direction right with gap metres between them.  parts (a list of props.py
    parts for each figure) move with their figures and are returned moved."""
    right = normalize(np.asarray(right, float) * (1.0, 0.0, 1.0))
    parts = [list(p) for p in parts] if parts else [[] for _ in figures]

    def move(k, offset):
        figures[k].translate(offset)
        parts[k] = [props.moved(part, offset) for part in parts[k]]

    spans = []
    for k, s in enumerate(figures):
        move(k, -(s.pos.min(axis=0) + s.pos.max(axis=0)) / 2 * (1.0, 0.0, 1.0))
        along = s.pos @ right
        lo, hi = (along - s.radii).min(), (along + s.radii).max()
        for part in parts[k]:
            low, high = props.bounds(part)
            middle, half = (low + high) / 2 @ right, (high - low) / 2 @ np.abs(right)
            lo, hi = min(lo, middle - half), max(hi, middle + half)
        spans.append((lo, hi))
    x = -(sum(hi - lo for lo, hi in spans) + gap * (len(figures) - 1)) / 2
    for k, (lo, hi) in enumerate(spans):
        move(k, right * (x - lo))
        x += hi - lo + gap
    return parts


# --- equipment ---------------------------------------------------------------
# Functions for a position's "props": each takes the built figure and returns
# props.py parts placed from its joints, so the equipment fits the pose.

HANDS = ("l_hand", "r_hand")
# Direction of a dumbbell's handle in the forearm's own frame: forward with the
# arms hanging (palms in), or from side to side.
GRIPS = {"neutral": (0.0, 0.0, 1.0), "across": (1.0, 0.0, 0.0)}


def _joint(s, name):
    return s.pos[s.index[name]]


def _mean(s, names):
    return np.mean([_joint(s, n) for n in names], axis=0)


def _bottom(s, names):
    """Height of the lowest point of the joints' spheres."""
    return min(_joint(s, n)[1] - s.radii[s.index[n]] for n in names)


def barbell(s, plate_radius=props.PLATE_RADIUS):
    return props.barbell(_mean(s, HANDS), _joint(s, "l_hand") - _joint(s, "r_hand"), plate_radius)


def deadlift_barbell(s):
    """A barbell with plates big enough to rest on the floor at the start of the deadlift."""
    return barbell(s, 0.265)


def dumbbells(grip="neutral", sides="lr"):
    """A dumbbell in each hand (or the hands on sides) with its handle along grip."""
    def place(s):
        parts = []
        for side in sides:
            h = s.index[side + "_hand"]
            forearm = normalize(s.pos[h] - s.pos[s.parent[h]])
            axis = s.world[h] @ GRIPS[grip]
            parts += props.dumbbell(s.pos[h], axis - (axis @ forearm) * forearm)
        return parts
    return place


def goblet(s):
    """One dumbbell held across both hands."""
    return props.dumbbell(_mean(s, HANDS), _joint(s, "l_hand") - _joint(s, "r_hand"))


def kettlebell(s):
    """A kettlebell held in both hands, hanging on from the forearms."""
    forearms = sum(normalize(_joint(s, side + "_hand") - _joint(s, side + "_elbow")) for side in "lr")
    return props.kettlebell(_mean(s, HANDS), forearms)


def bar_overhead(s):
    """A bar on two posts through both hands, from side to side (pull-up bar)."""
    centre, half = _mean(s, HANDS), np.array([0.6, 0.0, 0.0])
    return props.bar_on_posts(centre - half, centre + half)


def dip_bars(s):
    """A bar on posts through each hand, from front to back."""
    half = np.array([0.0, 0.0, 0.35])
    return [part for side in "lr" for part in props.bar_on_posts(_joint(s, side + "_hand") - half,
                                                                 _joint(s, side + "_hand") + half)]


def lat_bar(s):
    """A wide bar through both hands on a cable from above."""
    l, r = _joint(s, "l_hand"), _joint(s, "r_hand")
    centre = (l + r) / 2
    return [props.bar(centre, l - r, 1.2),
            props.cylinder("Cable", centre, (centre[0], 2.2, centre[2]), props.CABLE_RADIUS)]


def row_handle(s):
    """A handle through both hands on a cable from the front."""
    l, r = _joint(s, "l_hand"), _joint(s, "r_hand")
    centre = (l + r) / 2
    return [props.bar(centre, l - r, np.linalg.norm(l - r) + 0.16, name="Handle"),
            props.cylinder("Cable", centre, centre + (0.0, 0.0, 0.7), props.CABLE_RADIUS)]


def block(name, under, width, depth, dz=0.0, top=None, centre="pelvis"):
    """A box on the floor with its top touching the spheres of the joints
    under (or at height top): depth long front to back, centred under them
    and moved dz forward, width wide, centred on joint centre side to side."""
    def place(s):
        x, z = _joint(s, centre)[0], _mean(s, under)[2] + dz
        height = _bottom(s, under) if top is None else top
        return [props.box(name, (x - width / 2, 0.0, z - depth / 2), (x + width / 2, height, z + depth / 2))]
    return place


def lying_bench(s):
    """A flat bench under a figure lying face up with its head towards -z."""
    x, _, z = _joint(s, "pelvis")
    top = _bottom(s, ("pelvis", "l_hip", "r_hip", "chest", "neck", "head"))
    return [props.box("Bench", (x - 0.15, 0.0, _joint(s, "neck")[2] - 0.3), (x + 0.15, top, z + 0.05))]


def shoulder_bench(s, top=0.46, depth=0.4):
    """A bench across behind the figure, its shoulder blades resting on the
    front edge (hip thrust)."""
    spine = [_joint(s, n) for n in ("pelvis", "chest", "neck")]
    points = [a + (b - a) * t for a, b in zip(spine, spine[1:]) for t in np.linspace(0, 1, 21)]
    low = [p[2] for p in points if p[1] < top + sk.JOINT_RADIUS]
    edge = (min(low) if low else spine[1][2]) - sk.JOINT_RADIUS
    x = spine[0][0]
    return [props.box("Bench", (x - 0.75, 0.0, edge - depth), (x + 0.75, top, edge))]


def chair(back=True):
    """A seat under the pelvis, with a backrest unless back is False."""
    def place(s):
        x, _, z = _joint(s, "pelvis")
        top = _bottom(s, ("pelvis", "l_hip", "r_hip"))
        parts = [props.box("Seat", (x - 0.22, 0.0, z - 0.18), (x + 0.22, top, z + 0.25))]
        if back:
            parts.append(props.box("Backrest", (x - 0.22, top, z - 0.18), (x + 0.22, top + 0.45, z - 0.14)))
        return parts
    return place


def wall(touching, side):
    """A wall from side to side that the joints touching rest on, in front of
    them (side 1) or behind them (side -1)."""
    def place(s):
        faces = [_joint(s, n)[2] + side * s.radii[s.index[n]] for n in touching]
        face, x = (max(faces) if side > 0 else min(faces)), _joint(s, "pelvis")[0]
        return [props.box("Wall", (x - 0.5, 0.0, face), (x + 0.5, 1.7, face + side * 0.1))]
    return place


# --- building blocks ---------------------------------------------------------

ARMS_DOWN = (tilt(DOWN, OUT, 6), tilt(DOWN, OUT, 4))
ARMS_FORWARD = (FWD, FWD)
ARMS_OUT = (OUT, OUT)
ARMS_UP = (tilt(UP, OUT, 12), tilt(UP, OUT, 8))
HANDS_BEHIND_HEAD = Rel(v(1, 0.5, -0.3), v(-1, 0.35, 0.05))
HANDS_ON_HIPS = Rel(v(0.75, -0.6, -0.3), v(-0.35, -0.55, 0.6))
HANDS_AT_CHEST = Rel(v(0.25, -1, 0.35), v(-0.45, 0.7, 0.55))
FRONT_RACK = Rel(v(0.25, -0.15, 1), v(-0.2, 0.55, -0.8))
BACK_SQUAT_GRIP = Rel(v(1, -0.55, -0.45), v(0, 1, -0.1))
RUN_ARM_FORWARD = (tilt(DOWN, FWD, 35), tilt(UP, FWD, 55))
RUN_ARM_BACK = (tilt(DOWN, BACK, 40), tilt(DOWN, FWD, 50))
FOOT_POINTED = tilt(DOWN, FWD, 40)

STAND = {}
STAND_ARMS_FORWARD = {"arms": ARMS_FORWARD}
SQUAT = {"body": tilt(UP, FWD, 35), "head": tilt(UP, FWD, 15), "legs": (v(0.3, -0.15, 1), v(0.12, -1, -0.4)),
         "feet": flat(15), "arms": ARMS_FORWARD}
HALF_SQUAT = {"body": tilt(UP, FWD, 25), "head": tilt(UP, FWD, 10),
              "legs": (v(0.2, -0.7, 1), v(0.08, -1, -0.3)), "feet": flat(10)}
SEATED = {"legs": (v(0.1, -0.05, 1), v(0, -1, 0.05)), "feet": flat(5)}
SIT_FLOOR = {"legs": (FWD, FWD)}
PRONE = {"body": FWD}
SUPINE = {"body": BACK, "legs": (tilt(FWD, DOWN, 5), tilt(FWD, DOWN, 5))}  # heels on the floor
ARMS_ALONG_FLOOR = (v(0.15, -0.15, 1), v(0.1, -0.15, 1))  # lying on the back, hands by the hips
KNEES_UP = (v(0, 0.75, 0.65), v(0, -1.2, 0.65))           # lying on the back, feet flat
PLANK = {"body": tilt(FWD, UP, 20), "arms": (v(0.12, -1, 0), DOWN), "level": ("l_hand", "l_toe")}
PUSH_UP_DOWN = {"body": tilt(FWD, UP, 6), "arms": (v(0.45, 0.35, -0.8), v(-0.1, -1, 0.15)),
                "level": ("l_hand", "l_toe")}
QUADRUPED = {"body": tilt(FWD, UP, 10), "arms": (DOWN, DOWN), "legs": (DOWN, tilt(BACK, UP, 22)),
             "head": tilt(FWD, DOWN, 20), "level": ("l_hand", "l_knee")}
HANG = {"arms": (tilt(UP, OUT, 18), tilt(UP, OUT, 14)), "legs": (tilt(DOWN, FWD, 8), tilt(DOWN, FWD, 4)),
        "feet": FOOT_POINTED, "hang": 2.3, "props": [bar_overhead]}
LUNGE = {"l_leg": (v(0, -0.05, 1), tilt(DOWN, BACK, 8)), "r_leg": (tilt(DOWN, BACK, 15), tilt(BACK, UP, 12)),
         "l_foot": flat(), "r_foot": v(0, -1, 0.3)}
HIP_HINGE = {"body": tilt(UP, FWD, 70), "head": tilt(UP, FWD, 45),
             "legs": (tilt(DOWN, FWD, 12), tilt(DOWN, BACK, 8)), "feet": flat(5)}
BENCH = {"body": BACK, "legs": (v(0, -0.25, 1), v(0, -1, -0.1)), "feet": flat(10),  # lying on a bench
         "props": [lying_bench]}
BENCH_BARBELL = [lying_bench, barbell]
RUN = {"body": tilt(UP, FWD, 8), "l_leg": (tilt(DOWN, FWD, 45), tilt(DOWN, FWD, 5)),
       "r_leg": (tilt(DOWN, BACK, 18), tilt(UP, BACK, 60)), "l_foot": flat(),
       "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK}
WALK = {"l_leg": (tilt(DOWN, FWD, 22), tilt(DOWN, FWD, 20)), "r_leg": (tilt(DOWN, BACK, 15), tilt(DOWN, BACK, 49)),
        "l_foot": tilt(FWD, UP, 10), "r_foot": tilt(DOWN, FWD, 45),
        "r_arm": (tilt(DOWN, FWD, 20), tilt(DOWN, FWD, 40)), "l_arm": (tilt(DOWN, BACK, 20), tilt(DOWN, BACK, 5))}
ON_RIGHT_SIDE = [(FWD, 90)]  # lie the standing figure down on its right side
GUARD = (v(0.15, -1, 0.35), v(-0.3, 0.85, 0.45))  # fist by the chin
BOXING = {"l_leg": (tilt(DOWN, FWD, 15), tilt(DOWN, FWD, 10)), "r_leg": (tilt(DOWN, BACK, 13), tilt(DOWN, BACK, 13)),
          "feet": flat(20)}

STEP = block("Box", ("l_toe", "l_ankle"), 0.6, 0.45)
REAR_FOOT_BENCH = block("Bench", ("r_toe", "r_ankle"), 0.4, 0.5, dz=-0.15)
HANDS_BENCH = block("Bench", HANDS, 0.7, 0.35, dz=0.1)
FEET_BOX = block("Box", ("l_toe", "r_toe"), 0.5, 0.4, dz=-0.1)
BEHIND_BENCH = block("Bench", HANDS, 0.9, 0.35, dz=-0.15)
ONE_ARM_ROW = [block("Bench", ("r_hand",), 0.3, 0.5, dz=0.05, centre="r_hand"), dumbbells(sides="l")]

# --- the exercises -----------------------------------------------------------

CATEGORIES = [
    ("Basic positions", [
        Exercise("Standing", [STAND], FRONT),
        Exercise("Standing, arms out (T-pose)", [{"arms": ARMS_OUT}], FRONT),
        Exercise("Walking", [WALK, mirrored(WALK)]),
        Exercise("Running", [RUN, mirrored(RUN)]),
        Exercise("Sitting on a chair", [SEATED | {"arms": (tilt(DOWN, FWD, 20), tilt(FWD, DOWN, 25)),
                                                  "props": [chair()]}]),
        Exercise("Sitting on the floor", [SIT_FLOOR | {"arms": (tilt(DOWN, BACK, 25), tilt(DOWN, BACK, 22))}]),
        Exercise("Kneeling", [{"legs": (DOWN, tilt(BACK, UP, 20))}]),
        Exercise("Half kneeling", [{"l_leg": (FWD, DOWN), "l_foot": flat(),
                                    "r_leg": (tilt(DOWN, BACK, 5), tilt(BACK, UP, 16))}]),
        Exercise("Deep squat (resting)", [{"body": tilt(UP, FWD, 40), "head": tilt(UP, FWD, 10),
                                           "legs": (v(0.35, 0.1, 1), v(0.12, -1, -0.5)), "feet": flat(20),
                                           "arms": (tilt(DOWN, FWD, 50), tilt(FWD, DOWN, 10))}]),
        Exercise("Lying on the back", [SUPINE | {"arms": ARMS_ALONG_FLOOR}]),
        Exercise("Lying face down", [PRONE | {"arms": ARMS_ALONG_FLOOR}]),
        Exercise("Lying on the side", [{"r_arm": (limb(170, 0), limb(150, 0)), "rotate": ON_RIGHT_SIDE,
                                        "legs": (tilt(DOWN, FWD, 15), tilt(DOWN, FWD, 10))}], FRONT),
    ]),
    ("Legs and glutes", [
        Exercise("Squat", [STAND_ARMS_FORWARD, SQUAT]),
        Exercise("Half squat", [STAND_ARMS_FORWARD, HALF_SQUAT | {"arms": ARMS_FORWARD}]),
        Exercise("Sumo squat", [{"legs": (limb(18, 0), limb(18, 0)), "feet": flat(40), "arms": HANDS_AT_CHEST},
                                {"body": tilt(UP, FWD, 12), "legs": (v(0.85, -0.3, 0.5), v(0.15, -1, -0.1)),
                                 "feet": flat(40), "arms": HANDS_AT_CHEST}], FRONT),
        Exercise("Goblet squat", [{"arms": HANDS_AT_CHEST, "props": [goblet]},
                                  SQUAT | {"arms": (v(0.15, -1, 0.3), v(-0.4, 0.75, 0.5)), "props": [goblet]}]),
        Exercise("Back squat", [{"arms": BACK_SQUAT_GRIP, "props": [barbell]},
                                SQUAT | {"arms": BACK_SQUAT_GRIP, "props": [barbell]}]),
        Exercise("Front squat", [{"arms": FRONT_RACK, "props": [barbell]},
                                 SQUAT | {"body": tilt(UP, FWD, 20), "arms": FRONT_RACK, "props": [barbell]}]),
        Exercise("Pistol squat", [{"l_leg": (limb(40, 90), limb(40, 90)), "arms": ARMS_FORWARD},
                                  {"body": tilt(UP, FWD, 40), "arms": ARMS_FORWARD,
                                   "r_leg": (v(0, -0.25, 1), v(0, -1, -0.55)), "r_foot": flat(),
                                   "l_leg": (limb(80, 90), limb(80, 90))}]),
        Exercise("Lunge", [STAND | {"arms": HANDS_ON_HIPS}, LUNGE | {"arms": HANDS_ON_HIPS}]),
        Exercise("Split squat", [{"l_leg": (tilt(DOWN, FWD, 22), tilt(DOWN, FWD, 15)), "l_foot": flat(),
                                  "r_leg": (tilt(DOWN, BACK, 22), tilt(DOWN, BACK, 48)), "r_foot": v(0, -1, 0.6)},
                                 LUNGE]),
        Exercise("Side lunge", [{"legs": (limb(25, 0), limb(25, 0)), "feet": flat(15), "arms": HANDS_AT_CHEST},
                                {"body": tilt(UP, FWD, 30), "arms": HANDS_AT_CHEST,
                                 "l_leg": (v(0.6, -0.15, 0.75), v(0.1, -1, -0.4)), "l_foot": flat(25),
                                 "r_leg": (limb(49.5, 0), limb(49.5, 0)), "r_foot": flat(5)}], FRONT),
        Exercise("Curtsy lunge", [{"arms": HANDS_ON_HIPS},
                                  {"arms": HANDS_ON_HIPS, "l_leg": (v(0.05, -0.15, 1), tilt(DOWN, BACK, 8)),
                                   "l_foot": flat(), "r_leg": (v(1, -1.6, -0.6), v(0.5, -0.05, -1)),
                                   "r_foot": v(0, -1, 0.3)}], FRONT),
        Exercise("Bulgarian split squat", [
            {"l_leg": (tilt(DOWN, FWD, 15), tilt(DOWN, FWD, 6)), "l_foot": flat(),
             "r_leg": (tilt(DOWN, BACK, 30), v(0, 0.1, -1)), "r_foot": v(0, 0.2, -1), "props": [REAR_FOOT_BENCH]},
            {"body": tilt(UP, FWD, 15), "l_leg": (v(0, -0.2, 1), v(0, -1, -0.25)), "l_foot": flat(),
             "r_leg": (tilt(DOWN, BACK, 5), v(0, 0.85, -0.5)), "r_foot": v(0, -0.2, -1), "props": [REAR_FOOT_BENCH]}]),
        Exercise("Step-up", [{"l_leg": (limb(75, 90), v(0, -1, -0.1)), "l_foot": flat(), "arms": HANDS_ON_HIPS,
                              "props": [STEP]},
                             {"r_leg": (limb(95, 90), DOWN), "lift": 0.3, "arms": HANDS_ON_HIPS, "props": [STEP]}]),
        Exercise("Wall sit", [{"legs": (FWD, DOWN), "feet": flat(5), "arms": ARMS_FORWARD,
                               "props": [wall(("pelvis", "chest", "neck", "head"), -1)]}]),
        Exercise("Calf raise", [STAND, {"feet": v(0, -0.9, 0.42)}]),
        Exercise("Glute bridge", [SUPINE | {"legs": KNEES_UP, "feet": flat(), "arms": ARMS_ALONG_FLOOR},
                                  {"body": v(0, -0.45, -1), "neck": v(0, -0.1, -1), "head": BACK,
                                   "legs": (v(0, 0.25, 1), v(0, -1, 0.1)), "feet": flat(), "arms": ARMS_ALONG_FLOOR}]),
        Exercise("Single-leg glute bridge", [{"body": v(0, -0.45, -1), "neck": v(0, -0.1, -1), "head": BACK,
                                              "r_leg": (v(0, 0.25, 1), v(0, -1, 0.1)), "r_foot": flat(),
                                              "l_leg": (v(0, 0.25, 1), v(0, 0.25, 1)), "arms": ARMS_ALONG_FLOOR}]),
        Exercise("Hip thrust", [{"body": v(0, 0.75, -0.65), "head": BACK, "legs": (v(0, 0.8, 0.6), v(0, -1, 0.2)),
                                 "feet": flat(), "arms": (OUT, OUT), "props": [shoulder_bench]},
                                {"body": BACK, "head": tilt(BACK, UP, 30), "legs": (FWD, DOWN), "feet": flat(),
                                 "arms": (OUT, OUT), "props": [shoulder_bench]}]),
        Exercise("Good morning", [{"arms": HANDS_BEHIND_HEAD}, HIP_HINGE | {"arms": HANDS_BEHIND_HEAD}]),
        Exercise("Deadlift", [{"body": tilt(UP, FWD, 65), "head": tilt(UP, FWD, 40), "arms": (DOWN, DOWN), "shrug": -15,
                               "legs": (tilt(DOWN, FWD, 85), tilt(DOWN, BACK, 33)), "feet": flat(5),
                               "props": [deadlift_barbell]},
                              {"arms": (tilt(DOWN, FWD, 3), tilt(DOWN, FWD, 3)), "props": [deadlift_barbell]}]),
        Exercise("Romanian deadlift", [{"arms": (tilt(DOWN, FWD, 3), tilt(DOWN, FWD, 3)), "props": [barbell]},
                                       HIP_HINGE | {"arms": (DOWN, DOWN), "props": [barbell]}]),
        Exercise("Single-leg Romanian deadlift", [
            {"r_leg": (tilt(DOWN, BACK, 15), tilt(DOWN, BACK, 25)), "arms": (DOWN, DOWN)},
            {"body": tilt(UP, FWD, 85), "head": tilt(UP, FWD, 70), "arms": (DOWN, DOWN),
             "l_leg": (tilt(DOWN, FWD, 10), tilt(DOWN, BACK, 5)), "l_foot": flat(),
             "r_leg": (tilt(DOWN, BACK, 85), tilt(DOWN, BACK, 85)), "r_foot": tilt(DOWN, BACK, 10)}]),
        Exercise("Kettlebell swing", [HIP_HINGE | {"body": tilt(UP, FWD, 60), "arms": (v(-0.25, -1, -0.45), v(-0.15, -1, -0.5)),
                                                   "legs": (tilt(DOWN, FWD, 30), tilt(DOWN, BACK, 15)),
                                                   "props": [kettlebell]},
                                      {"arms": (v(-0.3, 0, 1), v(-0.15, 0, 1)), "feet": flat(10), "props": [kettlebell]}]),
        Exercise("Donkey kick", [QUADRUPED, QUADRUPED | {"l_leg": (tilt(BACK, UP, 10), UP), "l_foot": BACK, "level": ("l_hand", "r_knee")}]),
        Exercise("Fire hydrant", [QUADRUPED, QUADRUPED | {"l_leg": (v(1, -0.5, -0.1), v(0, 0.2, -1)), "level": ("l_hand", "r_knee")}], FRONT),
        Exercise("Clamshell", [{"legs": (limb(45, 90), tilt(DOWN, BACK, 40)), "r_arm": (limb(170, 0), limb(150, 0)),
                                "l_arm": HANDS_ON_HIPS, "rotate": ON_RIGHT_SIDE},
                               {"r_leg": (limb(45, 90), tilt(DOWN, BACK, 40)), "r_arm": (limb(170, 0), limb(150, 0)),
                                "l_leg": (v(0.6, -0.55, 0.6), v(-0.35, -0.75, -0.45)),
                                "l_arm": HANDS_ON_HIPS, "rotate": ON_RIGHT_SIDE}], FRONT),
        Exercise("Side-lying leg raise", [{"r_arm": (limb(170, 0), limb(150, 0)), "l_arm": HANDS_ON_HIPS,
                                           "rotate": ON_RIGHT_SIDE},
                                          {"r_arm": (limb(170, 0), limb(150, 0)), "l_arm": HANDS_ON_HIPS,
                                           "l_leg": (limb(40, 0), limb(40, 0)), "rotate": ON_RIGHT_SIDE}], FRONT),
        Exercise("Standing side leg raise", [{"arms": HANDS_ON_HIPS},
                                             {"arms": HANDS_ON_HIPS, "l_leg": (limb(40, 0), limb(40, 0))}], FRONT),
        Exercise("Standing hip extension", [{"arms": HANDS_ON_HIPS},
                                            {"arms": HANDS_ON_HIPS, "body": tilt(UP, FWD, 10),
                                             "l_leg": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 30)),
                                             "r_leg": (DOWN, DOWN), "r_foot": flat()}]),
    ]),
    ("Push", [
        Exercise("Push-up", [PLANK, PUSH_UP_DOWN]),
        Exercise("Knee push-up", [PLANK | {"body": tilt(FWD, UP, 25), "legs": Rel(DOWN, v(0, -0.5, -1)),
                                           "level": ("l_hand", "l_knee")},
                                  PUSH_UP_DOWN | {"body": tilt(FWD, UP, 10), "legs": Rel(DOWN, v(0, -0.5, -1)),
                                                  "level": ("l_hand", "l_knee")}]),
        Exercise("Wide push-up", [PLANK | {"arms": (v(0.6, -1, 0), v(0.25, -1, 0))},
                                  PUSH_UP_DOWN | {"arms": (v(1, 0.25, -0.2), v(0.1, -1, 0))}]),
        Exercise("Diamond push-up", [PLANK | {"arms": (v(-0.35, -1, 0.05), v(-0.15, -1, 0))},
                                     PUSH_UP_DOWN | {"arms": (v(0.15, 0.3, -1), v(-0.3, -1, 0.45))}]),
        Exercise("Incline push-up", [{"body": tilt(FWD, UP, 45), "arms": (v(0.12, -1, 0), DOWN),
                                      "level": ("l_toe", "l_hand", 0.5), "props": [HANDS_BENCH]},
                                     {"body": tilt(FWD, UP, 33), "arms": (v(0.45, 0.35, -0.8), v(-0.1, -1, 0.15)),
                                      "level": ("l_toe", "l_hand", 0.5), "props": [HANDS_BENCH]}]),
        Exercise("Decline push-up", [{"body": tilt(FWD, DOWN, 12), "arms": (v(0.12, -1, 0), DOWN),
                                      "level": ("l_hand", "l_toe", 0.45), "props": [FEET_BOX]},
                                     {"body": tilt(FWD, DOWN, 18), "arms": (v(0.45, 0.35, -0.8), v(-0.1, -1, 0.15)),
                                      "level": ("l_hand", "l_toe", 0.45), "props": [FEET_BOX]}]),
        Exercise("Pike push-up", [{"body": v(0, -0.8, 0.6), "arms": (v(0, -0.8, 0.6), v(0, -0.8, 0.6)),
                                   "legs": (v(0, -0.75, -0.65), v(0, -0.75, -0.65)), "level": ("l_hand", "l_toe")},
                                  {"body": v(0, -0.95, 0.3), "arms": (v(0.45, -0.2, 0.9), v(0, -1, -0.15)),
                                   "legs": (v(0, -0.75, -0.65), v(0, -0.75, -0.65)), "level": ("l_hand", "l_toe")}]),
        Exercise("Handstand", [{"body": DOWN, "front": FWD, "arms": (tilt(DOWN, OUT, 8), DOWN),
                                "legs": (UP, UP), "feet": tilt(UP, FWD, 20)}], FRONT),
        Exercise("Dip", [{"body": tilt(UP, FWD, 8), "arms": (tilt(DOWN, FWD, 5), DOWN),
                          "legs": (tilt(DOWN, FWD, 15), tilt(DOWN, BACK, 60)), "hang": 1.25, "props": [dip_bars]},
                         {"body": tilt(UP, FWD, 25), "arms": (tilt(DOWN, BACK, 55), tilt(DOWN, FWD, 5)),
                          "legs": (tilt(DOWN, FWD, 15), tilt(DOWN, BACK, 60)), "hang": 1.25, "props": [dip_bars]}]),
        Exercise("Bench dip", [{"arms": (tilt(DOWN, BACK, 15), tilt(DOWN, BACK, 10)),
                                "legs": (v(0, -0.1, 1), tilt(DOWN, FWD, 20)), "feet": tilt(FWD, UP, 20),
                                "level": ("l_ankle", "l_hand", 0.43), "props": [BEHIND_BENCH]},
                               {"arms": (tilt(DOWN, BACK, 55), tilt(DOWN, FWD, 10)),
                                "legs": (v(0, 0.3, 1), tilt(DOWN, FWD, 25)), "feet": tilt(FWD, UP, 20),
                                "level": ("l_ankle", "l_hand", 0.43), "props": [BEHIND_BENCH]}]),
        Exercise("Bench press", [BENCH | {"arms": (tilt(UP, OUT, 8), UP), "props": BENCH_BARBELL},
                                 BENCH | {"arms": (v(0.8, -0.5, 0.25), v(-0.05, 1, 0)), "props": BENCH_BARBELL}]),
        Exercise("Floor press", [SUPINE | {"legs": KNEES_UP, "feet": flat(), "arms": (tilt(UP, OUT, 8), UP),
                                           "props": [barbell]},
                                 SUPINE | {"legs": KNEES_UP, "feet": flat(), "arms": (v(0.8, -0.3, 0.25), UP),
                                           "level": ("l_elbow", "l_ankle"), "props": [barbell]}]),
        Exercise("Dumbbell fly", [BENCH | {"arms": (tilt(UP, OUT, 8), tilt(UP, OUT, 4)), "props": [lying_bench, dumbbells()]},
                                  BENCH | {"arms": (v(1, -0.15, 0), v(1, 0.15, 0)), "props": [lying_bench, dumbbells()]}],
                 ABOVE),
        Exercise("Overhead press", [{"arms": (v(0.75, -0.55, 0.35), v(0, 1, 0.05)), "props": [barbell]},
                                    {"arms": (tilt(UP, OUT, 12), tilt(UP, OUT, 4)), "props": [barbell]}], FRONT),
        Exercise("Push press", [HALF_SQUAT | {"body": tilt(UP, FWD, 10), "arms": (v(0.75, -0.55, 0.35), v(0, 1, 0.05)),
                                              "props": [barbell]},
                                {"arms": (tilt(UP, OUT, 12), tilt(UP, OUT, 4)), "feet": flat(10), "props": [barbell]}],
                 FRONT),
        Exercise("Thruster", [SQUAT | {"body": tilt(UP, FWD, 22), "arms": FRONT_RACK, "props": [barbell]},
                              {"arms": (tilt(UP, OUT, 12), tilt(UP, OUT, 4)), "props": [barbell]}]),
        Exercise("Skull crusher", [BENCH | {"arms": (UP, UP), "props": BENCH_BARBELL},
                                   BENCH | {"arms": (tilt(UP, BACK, 15), v(0, -0.4, -1)), "props": BENCH_BARBELL}]),
        Exercise("Overhead triceps extension", [{"arms": (tilt(UP, FWD, 8), tilt(DOWN, BACK, 15)), "props": [dumbbells()]},
                                                {"arms": (tilt(UP, FWD, 8), tilt(UP, FWD, 8)), "props": [dumbbells()]}]),
        Exercise("Triceps kickback", [HIP_HINGE | {"body": tilt(UP, FWD, 65), "arms": (v(0.1, -0.15, -1), DOWN),
                                                   "props": [dumbbells()]},
                                      HIP_HINGE | {"body": tilt(UP, FWD, 65),
                                                   "arms": (v(0.1, -0.15, -1), v(0.05, 0, -1)), "props": [dumbbells()]}]),
    ]),
    ("Pull", [
        Exercise("Pull-up", [HANG, HANG | {"arms": (v(0.8, -0.6, 0), v(-0.2, 1, 0.05))}], FRONT),
        Exercise("Chin-up", [HANG | {"arms": (tilt(UP, FWD, 8), tilt(UP, FWD, 4))},
                             HANG | {"arms": (v(0.2, -0.8, 0.45), v(-0.05, 1, -0.1))}]),
        Exercise("Hanging leg raise", [HANG, HANG | {"legs": (FWD, FWD), "feet": tilt(FWD, UP, 30)}]),
        Exercise("Hanging knee raise", [HANG, HANG | {"legs": (tilt(FWD, UP, 10), DOWN)}]),
        Exercise("Dead hang", [HANG], FRONT),
        Exercise("Inverted row", [{"body": tilt(BACK, UP, 25), "arms": (UP, UP), "level": ("l_ankle", "l_hand", 1.12),
                                   "props": [bar_overhead]},
                                  {"body": tilt(BACK, UP, 25), "arms": (v(0.3, -0.5, 0.75), v(0, 1, 0.1)),
                                   "level": ("l_ankle", "l_hand", 1.12), "props": [bar_overhead]}]),
        Exercise("Bent-over row", [HIP_HINGE | {"body": tilt(UP, FWD, 60), "arms": (DOWN, DOWN), "props": [barbell]},
                                   HIP_HINGE | {"body": tilt(UP, FWD, 60), "arms": (v(0.2, 0.25, -1), DOWN),
                                                "props": [barbell]}]),
        Exercise("One-arm row", [HIP_HINGE | {"body": tilt(UP, FWD, 75), "r_leg": (tilt(DOWN, FWD, 25), tilt(DOWN, BACK, 5)),
                                              "l_leg": (tilt(DOWN, BACK, 18), tilt(DOWN, BACK, 18)),
                                              "r_arm": (tilt(DOWN, FWD, 10), DOWN), "l_arm": (DOWN, DOWN),
                                              "props": ONE_ARM_ROW},
                                 HIP_HINGE | {"body": tilt(UP, FWD, 75), "r_leg": (tilt(DOWN, FWD, 25), tilt(DOWN, BACK, 5)),
                                              "l_leg": (tilt(DOWN, BACK, 18), tilt(DOWN, BACK, 18)),
                                              "r_arm": (tilt(DOWN, FWD, 10), DOWN),
                                              "l_arm": (v(0.15, 0.3, -1), DOWN), "props": ONE_ARM_ROW}]),
        Exercise("Lat pulldown", [SEATED | {"body": tilt(UP, BACK, 10), "arms": (limb(165, 20), limb(170, 10)),
                                            "props": [chair(back=False), lat_bar]},
                                  SEATED | {"body": tilt(UP, BACK, 15), "arms": (v(0.75, -0.6, -0.2), v(-0.1, 1, 0)),
                                            "props": [chair(back=False), lat_bar]}],
                 FRONT),
        Exercise("Seated row", [SIT_FLOOR | {"legs": (tilt(FWD, UP, 8), tilt(FWD, DOWN, 12)), "body": tilt(UP, FWD, 15),
                                             "arms": (tilt(FWD, DOWN, 10), tilt(FWD, DOWN, 10)), "props": [row_handle]},
                                SIT_FLOOR | {"legs": (tilt(FWD, UP, 8), tilt(FWD, DOWN, 12)), "body": tilt(UP, BACK, 5),
                                             "arms": (v(0.15, -0.5, -1), FWD), "props": [row_handle]}]),
        Exercise("Face pull", [{"arms": (tilt(FWD, UP, 15), tilt(FWD, UP, 15))},
                               {"arms": (v(1, 0.2, -0.15), v(-0.1, 1, 0.35))}], FRONT),
        Exercise("Rear delt fly", [HIP_HINGE | {"arms": (DOWN, DOWN), "props": [dumbbells()]},
                                   HIP_HINGE | {"arms": (v(1, -0.1, 0), v(1, -0.25, 0)), "props": [dumbbells()]}], FRONT),
        Exercise("Superman", [PRONE | {"arms": (tilt(FWD, DOWN, 8), FWD)},
                              {"body": FWD, "chest": tilt(FWD, UP, 15), "neck": tilt(FWD, UP, 25),
                               "arms": (tilt(FWD, UP, 25), tilt(FWD, UP, 25)), "legs": (tilt(BACK, UP, 15), tilt(BACK, UP, 15))}]),
        Exercise("Pullover", [BENCH | {"arms": (UP, UP), "props": BENCH_BARBELL},
                              BENCH | {"arms": (tilt(BACK, DOWN, 5), tilt(BACK, DOWN, 15)), "props": BENCH_BARBELL}]),
    ]),
    ("Arms and shoulders", [
        Exercise("Biceps curl", [{"arms": ARMS_DOWN, "props": [dumbbells("across")]},
                                 {"arms": (tilt(DOWN, FWD, 5), tilt(UP, FWD, 20)), "props": [dumbbells("across")]}]),
        Exercise("Lateral raise", [{"arms": ARMS_DOWN, "props": [dumbbells()]},
                                   {"arms": (limb(88, 5), limb(85, 15)), "props": [dumbbells()]}], FRONT),
        Exercise("Front raise", [{"arms": ARMS_DOWN, "props": [dumbbells("across")]},
                                 {"arms": (limb(90, 85), limb(90, 85)), "props": [dumbbells("across")]}]),
        Exercise("Upright row", [{"arms": (tilt(DOWN, FWD, 5), tilt(DOWN, IN, 10)), "props": [barbell]},
                                 {"arms": (v(1, 0.35, 0.15), v(-0.85, -0.35, 0.4)), "props": [barbell]}], FRONT),
        Exercise("Shrug", [{"arms": ARMS_DOWN, "props": [dumbbells()]},
                           {"arms": ARMS_DOWN, "shrug": 25, "props": [dumbbells()]}], FRONT),
        Exercise("Arm circles", [{"arms": ARMS_OUT}, {"arms": (limb(130, 30), limb(130, 30))}], FRONT),
        Exercise("Farmer's carry", [WALK | {"arms": ARMS_DOWN, "l_arm": ARMS_DOWN, "r_arm": ARMS_DOWN,
                                            "props": [dumbbells()]}]),
        Exercise("Overhead carry", [WALK | {"l_arm": ARMS_UP, "r_arm": ARMS_UP, "props": [dumbbells()]}]),
    ]),
    ("Core", [
        Exercise("Plank", [PLANK]),
        Exercise("Forearm plank", [{"body": tilt(FWD, UP, 10), "arms": (DOWN, v(-0.15, 0, 1)),
                                    "level": ("l_hand", "l_toe")}]),
        Exercise("Side plank", [{"r_arm": (OUT, FWD), "l_arm": HANDS_ON_HIPS, "rotate": ON_RIGHT_SIDE,
                                 "level": ("r_elbow", "r_ankle")}], FRONT),
        Exercise("Side plank, arm raised", [{"r_arm": (OUT, OUT), "l_arm": (OUT, OUT), "rotate": ON_RIGHT_SIDE,
                                             "level": ("r_hand", "r_ankle")}], FRONT),
        Exercise("Crunch", [SUPINE | {"legs": KNEES_UP, "feet": flat(), "arms": HANDS_BEHIND_HEAD},
                            {"body": BACK, "chest": tilt(BACK, UP, 20), "neck": tilt(BACK, UP, 45),
                             "head": tilt(BACK, UP, 55), "legs": KNEES_UP, "feet": flat(), "arms": HANDS_BEHIND_HEAD}]),
        Exercise("Sit-up", [SUPINE | {"legs": KNEES_UP, "feet": flat(), "arms": Rel(v(0.2, 0.4, 1), v(-0.5, 0.6, -0.6))},
                            {"body": tilt(BACK, UP, 70), "chest": tilt(BACK, UP, 90), "neck": tilt(UP, FWD, 15),
                             "legs": KNEES_UP, "feet": flat(), "arms": Rel(v(0.2, 0.4, 1), v(-0.5, 0.6, -0.6))}]),
        Exercise("Bicycle crunch", [
            {"body": BACK, "chest": tilt(BACK, UP, 20), "neck": tilt(BACK, UP, 40), "twist": -35,
             "arms": HANDS_BEHIND_HEAD, "r_leg": (tilt(UP, FWD, 35), tilt(FWD, DOWN, 5)),
             "l_leg": (tilt(FWD, UP, 25), tilt(FWD, UP, 25))},
            mirrored({"body": BACK, "chest": tilt(BACK, UP, 20), "neck": tilt(BACK, UP, 40), "twist": -35,
                      "arms": HANDS_BEHIND_HEAD, "r_leg": (tilt(UP, FWD, 35), tilt(FWD, DOWN, 5)),
                      "l_leg": (tilt(FWD, UP, 25), tilt(FWD, UP, 25))})]),
        Exercise("Leg raise", [SUPINE | {"arms": ARMS_ALONG_FLOOR, "legs": (tilt(FWD, UP, 8), tilt(FWD, UP, 8))},
                               SUPINE | {"arms": ARMS_ALONG_FLOOR, "legs": (tilt(UP, FWD, 5), tilt(UP, FWD, 5))}]),
        Exercise("Flutter kicks", [SUPINE | {"arms": ARMS_ALONG_FLOOR, "neck": tilt(BACK, UP, 20),
                                             "l_leg": (tilt(FWD, UP, 30), tilt(FWD, UP, 30)),
                                             "r_leg": (tilt(FWD, UP, 10), tilt(FWD, UP, 10))}]),
        Exercise("Hollow hold", [{"body": BACK, "chest": tilt(BACK, UP, 15), "neck": tilt(BACK, UP, 30),
                                  "arms": (tilt(BACK, UP, 20), tilt(BACK, UP, 20)),
                                  "legs": (tilt(FWD, UP, 20), tilt(FWD, UP, 20))}]),
        Exercise("V-up", [SUPINE | {"arms": (BACK, BACK), "legs": (tilt(FWD, UP, 5), tilt(FWD, UP, 5))},
                          {"body": tilt(BACK, UP, 45), "chest": tilt(BACK, UP, 50), "neck": tilt(BACK, UP, 55),
                           "arms": (tilt(FWD, UP, 50), tilt(FWD, UP, 50)), "legs": (tilt(FWD, UP, 55), tilt(FWD, UP, 55))}]),
        Exercise("Boat pose", [{"body": tilt(BACK, UP, 50), "chest": tilt(BACK, UP, 55), "neck": tilt(BACK, UP, 60),
                                "arms": (FWD, FWD), "legs": (tilt(FWD, UP, 45), tilt(FWD, UP, 45))}]),
        Exercise("Russian twist", [
            {"body": tilt(UP, BACK, 40), "twist": 40, "arms": Rel(limb(50, 80), limb(70, 120)),
             "legs": (tilt(FWD, UP, 35), tilt(FWD, DOWN, 20))},
            {"body": tilt(UP, BACK, 40), "twist": -40, "arms": Rel(limb(50, 80), limb(70, 120)),
             "legs": (tilt(FWD, UP, 35), tilt(FWD, DOWN, 20))}], ABOVE),
        Exercise("Dead bug", [SUPINE | {"arms": (UP, UP), "legs": (UP, FWD)},
                              SUPINE | {"r_arm": (UP, UP), "l_arm": (tilt(BACK, UP, 15), tilt(BACK, UP, 15)),
                                        "l_leg": (UP, FWD), "r_leg": (tilt(FWD, UP, 12), tilt(FWD, UP, 12))}]),
        Exercise("Bird dog", [QUADRUPED, QUADRUPED | {"l_arm": (tilt(FWD, UP, 5), tilt(FWD, UP, 5)),
                                                      "r_leg": (tilt(BACK, UP, 5), tilt(BACK, UP, 5)), "r_foot": BACK,
                                                      "level": ("r_hand", "l_knee")}]),
        Exercise("Mountain climber", [PLANK | {"l_leg": (v(0, -0.75, 0.65), v(0, -0.3, -1)), "level": ("l_hand", "r_toe")},
                                      PLANK | {"r_leg": (v(0, -0.75, 0.65), v(0, -0.3, -1)), "level": ("l_hand", "l_toe")}]),
        Exercise("Bear crawl hold", [QUADRUPED | {"legs": (v(0, -1, 0.15), v(0, -0.2, -1)), "level": ("l_hand", "l_toe")}]),
        Exercise("L-sit", [{"arms": (DOWN, DOWN), "legs": (FWD, FWD)}]),
        Exercise("Woodchop", [{"twist": 40, "look": 20, "l_arm": (v(0.55, 0.8, 0.3), v(0.4, 0.9, 0.2)),
                               "r_arm": (v(-0.75, 0.6, 0.4), v(-0.6, 0.75, 0.3))},
                              HALF_SQUAT | {"twist": -40, "look": -15, "l_arm": (v(-0.7, -0.6, 0.5), v(-0.6, -0.7, 0.3)),
                                            "r_arm": (v(0.4, -0.8, 0.45), v(0.35, -0.85, 0.3))}], FRONT),
        Exercise("Standing torso twist", [{"twist": 40, "arms": ARMS_OUT, "feet": flat(10)},
                                          {"twist": -40, "arms": ARMS_OUT, "feet": flat(10)}], ABOVE),
    ]),
    ("Cardio and plyometrics", [
        Exercise("Jumping jack", [{"arms": ARMS_DOWN}, {"arms": (limb(155, 0), limb(165, 0)),
                                                        "legs": (limb(18, 0), limb(18, 0)), "feet": flat(15)}], FRONT),
        Exercise("Star jump", [HALF_SQUAT | {"arms": (tilt(DOWN, IN, 10), tilt(DOWN, IN, 15))},
                               {"arms": (limb(135, 0), limb(140, 0)), "legs": (limb(30, 0), limb(30, 0)),
                                "feet": tilt(DOWN, OUT, 30), "lift": 0.35}], FRONT),
        Exercise("Squat jump", [SQUAT | {"arms": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 25))},
                                {"arms": ARMS_UP, "feet": FOOT_POINTED, "lift": 0.3}]),
        Exercise("Tuck jump", [HALF_SQUAT | {"arms": (tilt(DOWN, BACK, 25), tilt(DOWN, BACK, 20))},
                               {"legs": (tilt(FWD, UP, 15), DOWN), "arms": (tilt(DOWN, FWD, 50), tilt(FWD, DOWN, 5)),
                                "lift": 0.45}]),
        Exercise("Burpee", [PLANK, {"arms": ARMS_UP, "feet": FOOT_POINTED, "lift": 0.25}]),
        Exercise("Squat thrust", [{"body": tilt(UP, FWD, 60), "head": tilt(UP, FWD, 40),
                                   "legs": (v(0.25, 0.1, 1), v(0.1, -1, -0.5)), "feet": flat(10),
                                   "arms": (tilt(DOWN, FWD, 15), DOWN)}, PLANK]),
        Exercise("High knees", [{"l_leg": (limb(95, 90), DOWN), "l_foot": flat(), "r_foot": FOOT_POINTED,
                                 "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK},
                                mirrored({"l_leg": (limb(95, 90), DOWN), "l_foot": flat(), "r_foot": FOOT_POINTED,
                                          "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK})]),
        Exercise("Butt kicks", [{"l_leg": (tilt(DOWN, BACK, 5), tilt(UP, BACK, 25)), "l_foot": BACK,
                                 "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK},
                                mirrored({"l_leg": (tilt(DOWN, BACK, 5), tilt(UP, BACK, 25)), "l_foot": BACK,
                                          "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK})]),
        Exercise("Skater jump", [{"body": tilt(UP, FWD, 30), "r_leg": (tilt(DOWN, FWD, 45), tilt(DOWN, BACK, 20)),
                                  "r_foot": flat(), "l_leg": (v(-0.45, -1, -0.5), v(-0.3, -0.4, -0.5)),
                                  "l_arm": (v(-0.5, -0.6, 0.6), v(-0.5, -0.4, 0.7)), "r_arm": (tilt(DOWN, BACK, 35), tilt(DOWN, BACK, 30))},
                                 mirrored({"body": tilt(UP, FWD, 30), "r_leg": (tilt(DOWN, FWD, 45), tilt(DOWN, BACK, 20)),
                                           "r_foot": flat(), "l_leg": (v(-0.45, -1, -0.5), v(-0.3, -0.4, -0.5)),
                                           "l_arm": (v(-0.5, -0.6, 0.6), v(-0.5, -0.4, 0.7)),
                                           "r_arm": (tilt(DOWN, BACK, 35), tilt(DOWN, BACK, 30))})], FRONT),
        Exercise("Box jump", [SQUAT | {"arms": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 25)),
                                       "props": [block("Box", ("l_toe", "r_toe"), 0.6, 0.5, dz=0.5, top=0.5)]},
                              HALF_SQUAT | {"arms": ARMS_FORWARD, "lift": 0.5,
                                            "props": [block("Box", ("l_toe", "r_toe", "l_ankle", "r_ankle"), 0.6, 0.5)]}]),
        Exercise("Jump rope", [{"arms": (tilt(DOWN, OUT, 20), v(0.6, -0.5, 0.6)), "feet": FOOT_POINTED, "lift": 0.06}],
                 FRONT),
        Exercise("Shadow boxing (jab, cross)", [BOXING | {"twist": -15, "l_arm": (v(0, 0.05, 1), v(0, 0.05, 1)), "r_arm": GUARD},
                                                BOXING | {"twist": 30, "l_arm": GUARD,
                                                          "r_arm": (v(-0.25, 0.05, 1), v(-0.25, 0.05, 1))}]),
    ]),
    ("Running drills", [
        Exercise("Running stride", [RUN, mirrored(RUN)]),
        Exercise("Sprint start", [
            {"body": tilt(FWD, DOWN, 30), "arms": (DOWN, DOWN), "head": tilt(DOWN, FWD, 30),
             "l_leg": (tilt(DOWN, FWD, 55), tilt(DOWN, BACK, 35)), "r_leg": (tilt(DOWN, FWD, 10), tilt(DOWN, BACK, 20)),
             "level": ("l_hand", "l_toe")},
            {"body": tilt(UP, FWD, 50), "head": tilt(UP, FWD, 35),
             "l_leg": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 35)), "l_foot": tilt(DOWN, BACK, 10),
             "r_leg": (tilt(DOWN, FWD, 70), tilt(DOWN, BACK, 30)), "r_foot": flat(),
             "l_arm": (tilt(DOWN, FWD, 70), tilt(FWD, UP, 50)), "r_arm": (tilt(DOWN, BACK, 50), tilt(DOWN, FWD, 30))}]),
        Exercise("A-skip", [{"l_leg": (limb(92, 90), DOWN), "l_foot": flat(), "r_foot": FOOT_POINTED,
                             "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK}]),
        Exercise("B-skip", [{"l_leg": (limb(80, 90), limb(80, 90)), "l_foot": tilt(FWD, UP, 20), "r_foot": FOOT_POINTED,
                             "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK},
                            {"l_leg": (tilt(DOWN, FWD, 10), tilt(DOWN, FWD, 10)), "l_foot": flat(),
                             "r_leg": (limb(40, 90), tilt(DOWN, BACK, 30)), "r_foot": FOOT_POINTED,
                             "l_arm": RUN_ARM_FORWARD, "r_arm": RUN_ARM_BACK}]),
        Exercise("Bounding", [{"body": tilt(UP, FWD, 10), "l_leg": (limb(75, 90), tilt(DOWN, FWD, 5)), "l_foot": flat(),
                               "r_leg": (tilt(DOWN, BACK, 20), tilt(DOWN, BACK, 50)), "r_foot": FOOT_POINTED,
                               "r_arm": RUN_ARM_FORWARD, "l_arm": RUN_ARM_BACK, "lift": 0.3}]),
        Exercise("Leg swing, front to back", [{"l_leg": (limb(65, 90), limb(65, 90)), "l_arm": (OUT, OUT)},
                                              {"l_leg": (limb(25, -90), limb(25, -90)), "l_arm": (OUT, OUT)}]),
        Exercise("Leg swing, side to side", [{"l_leg": (limb(40, 0), limb(40, 0)), "arms": ARMS_FORWARD},
                                             {"l_leg": (limb(28, 180), limb(28, 180)), "arms": ARMS_FORWARD}], FRONT),
        Exercise("Walking lunge", [LUNGE | {"arms": HANDS_ON_HIPS}, mirrored(LUNGE | {"arms": HANDS_ON_HIPS})]),
    ]),
    ("Stretching", [
        Exercise("Standing quad stretch", [{"l_leg": (tilt(DOWN, BACK, 8), tilt(UP, BACK, 15)), "l_foot": BACK,
                                            "l_arm": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 30)), "r_arm": (OUT, OUT)}]),
        Exercise("Standing hamstring stretch", [{"body": tilt(UP, FWD, 110), "chest": tilt(UP, FWD, 135),
                                                 "neck": tilt(UP, FWD, 155), "arms": (DOWN, tilt(DOWN, BACK, 33)), "legs": (DOWN, DOWN),
                                                 "feet": flat()}]),
        Exercise("Seated forward fold", [SIT_FLOOR | {"body": tilt(UP, FWD, 30), "chest": tilt(UP, FWD, 70),
                                                      "neck": tilt(UP, FWD, 100), "arms": (tilt(FWD, DOWN, 15), FWD)}]),
        Exercise("Butterfly stretch", [{"body": tilt(UP, FWD, 15), "legs": (v(0.8, -0.05, 0.6), v(-0.75, -0.25, 0.3)),
                                        "arms": (tilt(DOWN, FWD, 30), tilt(FWD, DOWN, 30))}], FRONT),
        Exercise("Hip flexor stretch", [{"l_leg": (FWD, tilt(DOWN, BACK, 28)), "l_foot": flat(),
                                         "r_leg": (tilt(DOWN, BACK, 20), tilt(BACK, UP, 20)), "arms": ARMS_UP}]),
        Exercise("Calf stretch", [{"body": tilt(UP, FWD, 25), "arms": (tilt(FWD, UP, 25), tilt(FWD, UP, 25)),
                                   "l_leg": (tilt(DOWN, FWD, 40), tilt(DOWN, BACK, 15)), "l_foot": flat(),
                                   "r_leg": (tilt(DOWN, BACK, 30), tilt(DOWN, BACK, 30)), "r_foot": flat(),
                                   "props": [wall(HANDS, 1)]}]),
        Exercise("Side bend stretch", [{"chest": tilt(UP, IN, 20), "neck": tilt(UP, IN, 35),
                                        "l_arm": (v(-0.3, 1, 0), v(-0.7, 0.7, 0)), "r_arm": HANDS_ON_HIPS}], FRONT),
        Exercise("Overhead triceps stretch", [{"l_arm": (tilt(UP, BACK, 10), tilt(DOWN, BACK, 15)),
                                               "r_arm": (v(0.15, 0.9, 0.3), v(-0.9, 0.4, -0.1))}], FRONT),
        Exercise("Cross-body shoulder stretch", [{"l_arm": (v(-0.85, -0.1, 0.5), v(-0.9, 0, 0.4)),
                                                  "r_arm": (v(0.2, -0.9, 0.4), v(-0.4, 0.6, 0.6))}], FRONT),
        Exercise("Chest stretch", [{"arms": (v(0.3, -0.75, -0.6), v(-0.4, -0.6, -0.5)), "head": tilt(UP, BACK, 10)}]),
        Exercise("Neck stretch", [{"head": tilt(UP, IN, 35), "r_arm": (v(0.3, 0.9, 0.3), v(-1, 0.3, 0)),
                                   "l_arm": ARMS_DOWN}], FRONT),
        Exercise("Knee to chest", [SUPINE | {"l_leg": (tilt(UP, BACK, 30), v(0, 0.3, 1)),
                                             "l_arm": (v(0.2, 0.9, 0.3), v(0, -0.2, 1)), "r_arm": ARMS_ALONG_FLOOR}]),
        Exercise("Lying spinal twist", [{"body": BACK, "front": v(-1, 0.35, 0), "twist": 40, "arms": (OUT, OUT),
                                         "legs": Rel(limb(90, 90), tilt(DOWN, BACK, 10))}], ABOVE),
        Exercise("Child's pose", [{"body": tilt(FWD, UP, 15), "chest": tilt(FWD, DOWN, 25), "neck": tilt(FWD, DOWN, 40),
                                   "head": tilt(DOWN, FWD, 30), "legs": (v(0, -0.55, 0.8), BACK),
                                   "arms": (tilt(FWD, DOWN, 20), FWD), "level": ("l_hand", "l_knee")}]),
        Exercise("Cobra", [{"body": FWD, "chest": tilt(FWD, UP, 25), "neck": tilt(FWD, UP, 40), "head": tilt(UP, FWD, 35),
                            "arms": (tilt(DOWN, BACK, 55), tilt(DOWN, FWD, 30)), "feet": BACK,
                            "level": ("l_hand", "l_toe")}]),
        Exercise("Cat-cow", [QUADRUPED | {"body": tilt(FWD, UP, 25), "chest": tilt(FWD, UP, 15),
                                          "neck": tilt(FWD, DOWN, 20), "head": tilt(DOWN, FWD, 15)},
                             QUADRUPED | {"body": tilt(FWD, DOWN, 5), "chest": tilt(FWD, DOWN, 8),
                                          "neck": tilt(FWD, UP, 15), "head": tilt(FWD, UP, 35)}]),
        Exercise("Arm and shoulder circles", [{"arms": (limb(60, 90), limb(60, 90))}, {"arms": (limb(150, 0), limb(150, 0))}],
                 FRONT),
    ]),
    ("Yoga", [
        Exercise("Mountain pose", [{"arms": (tilt(DOWN, OUT, 3), tilt(DOWN, OUT, 3))}], FRONT),
        Exercise("Upward salute", [{"arms": (tilt(UP, OUT, 10), tilt(UP, OUT, 2)), "head": tilt(UP, BACK, 15)}], FRONT),
        Exercise("Downward dog", [{"body": v(0, -0.75, 0.66), "arms": (v(0, -0.75, 0.66), v(0, -0.75, 0.66)),
                                   "legs": (v(0, -0.72, -0.7), v(0, -0.72, -0.7)), "feet": tilt(FWD, DOWN, 30),
                                   "level": ("l_hand", "l_ankle")}]),
        Exercise("Upward dog", [{"body": tilt(FWD, UP, 20), "chest": tilt(FWD, UP, 40), "neck": tilt(FWD, UP, 55),
                                 "head": tilt(UP, FWD, 30), "arms": (DOWN, DOWN), "feet": BACK,
                                 "level": ("l_hand", "l_ankle")}]),
        Exercise("Plank pose", [PLANK]),
        Exercise("Chair pose", [{"body": tilt(UP, FWD, 30), "legs": (tilt(FWD, DOWN, 40), tilt(DOWN, BACK, 25)),
                                 "feet": flat(), "arms": (tilt(UP, FWD, 30), tilt(UP, FWD, 30))}]),
        # The pelvis opens towards the back leg and the shoulders turn to the front.
        Exercise("Warrior I", [{"front": v(-1, 0, 1), "twist": 40, "body": tilt(UP, FWD, 10), "chest": UP, "neck": UP,
                                "l_leg": (tilt(FWD, DOWN, 10), DOWN), "l_foot": flat(),
                                "r_leg": (tilt(DOWN, BACK, 49.4), tilt(DOWN, BACK, 49.4)), "r_foot": flat(45),
                                "arms": (tilt(UP, OUT, 8), UP)}]),
        Exercise("Warrior II", [{"look": 70,
                                 "l_leg": (v(1, -0.15, 0.3), DOWN), "l_foot": flat(80),
                                 "r_leg": (limb(54, 10), limb(54, 10)), "r_foot": flat(25),
                                 "l_arm": (OUT, OUT), "r_arm": (OUT, OUT)}], FRONT),
        Exercise("Warrior III", [{"body": tilt(UP, FWD, 88), "head": tilt(UP, FWD, 85), "arms": (FWD, FWD),
                                  "l_leg": (BACK, BACK), "r_leg": (DOWN, DOWN), "r_foot": flat()}]),
        Exercise("Tree pose", [{"l_leg": (v(0.75, -0.65, 0.25), v(-1, 0.05, 0)),
                                "arms": (v(0.4, 0.9, 0.1), v(-0.35, 0.95, 0))}], FRONT),
        # The pelvis turns towards the front leg and tips over it; the shoulders turn back.
        Exercise("Triangle pose", [{"body": tilt(UP, OUT, 35), "front": v(1, 0, 1), "twist": -40,
                                    "l_leg": (limb(40, 0), limb(40, 0)), "r_leg": (limb(30, 0), limb(30, 0)),
                                    "l_foot": flat(60), "r_foot": flat(-30), "l_arm": (DOWN, DOWN), "r_arm": (UP, UP)}],
                 FRONT),
        Exercise("Bridge pose", [{"body": v(0, -0.45, -1), "neck": v(0, -0.1, -1), "head": BACK,
                                  "legs": (v(0, 0.25, 1), v(0, -1, 0.1)), "feet": flat(), "arms": ARMS_ALONG_FLOOR}]),
        Exercise("Happy baby", [SUPINE | {"legs": (v(0.5, 0.75, -0.45), v(0.1, 1, 0)),
                                          "arms": (v(0.25, 0.8, 0.45), v(0.1, 1, 0))}]),
        Exercise("Corpse pose", [SUPINE | {"arms": (v(0.5, -0.1, 1), v(0.45, -0.1, 1)),
                                           "legs": (v(0.12, -0.08, 1), v(0.1, -0.08, 1))}], ABOVE),
    ]),
]
