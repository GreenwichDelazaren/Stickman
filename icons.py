"""Toolbar icons, drawn with pygame.draw on a 20 x 20 grid.

Each icon is drawn at 4x size and smoothed down, which anti-aliases it.  The
figure icons assume the front view, where the figure's left is screen right.
"""

import functools
import math

import pygame

GRID = 20
SUPERSAMPLE = 4
STROKE = 1.6
CLEAR = (0, 0, 0, 0)


class Pen:
    """Draws on a surface in grid units, optionally rotated about the centre."""

    def __init__(self, surf, color, turn=0.0):
        self.surf, self.color = surf, color
        self.unit = surf.get_width() / GRID
        self.cos, self.sin = math.cos(math.radians(turn)), math.sin(math.radians(turn))

    def _p(self, p):
        x, y = p[0] - GRID / 2, p[1] - GRID / 2
        x, y = x * self.cos - y * self.sin, x * self.sin + y * self.cos
        return ((x + GRID / 2) * self.unit, (y + GRID / 2) * self.unit)

    def line(self, *pts, w=STROKE, closed=False, color=None):
        """Polyline with round joins and caps."""
        color = color or self.color
        pts = [self._p(p) for p in pts]
        if closed:
            pts.append(pts[0])
        r = w * self.unit / 2
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            length = math.hypot(bx - ax, by - ay) or 1.0
            nx, ny = -(by - ay) / length * r, (bx - ax) / length * r
            pygame.draw.polygon(self.surf, color, [(ax + nx, ay + ny), (bx + nx, by + ny),
                                                   (bx - nx, by - ny), (ax - nx, ay - ny)])
        for p in pts:
            pygame.draw.circle(self.surf, color, p, r)

    def fill(self, *pts, color=None):
        pygame.draw.polygon(self.surf, color or self.color, [self._p(p) for p in pts])

    def erase(self, *pts, pad=1.2):
        """Clear a polygon and a margin around it, so what follows sits in front."""
        if len(pts) > 2:
            self.fill(*pts, color=CLEAR)
        self.line(*pts, w=2 * pad, closed=len(pts) > 2, color=CLEAR)

    def dot(self, c, r, color=None):
        pygame.draw.circle(self.surf, color or self.color, self._p(c), r * self.unit)

    def ring(self, c, r, w=STROKE):
        self.line(*arc_points(c, r, r, 0, 360), w=w)

    def head(self, tip, toward, length=4.2, width=6.4):
        """Filled arrowhead at tip, pointing away from the point toward."""
        dx, dy = tip[0] - toward[0], tip[1] - toward[1]
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        bx, by = tip[0] - dx * length, tip[1] - dy * length
        self.fill(tip, (bx - dy * width / 2, by + dx * width / 2), (bx + dy * width / 2, by - dx * width / 2))

    def arrow(self, *pts, w=STROKE, both=False, length=4.2, width=6.4):
        """Polyline with an arrowhead at the end (and at the start if both)."""
        pts = list(pts)
        ends = [(pts[-1], pts[-2])] + ([(pts[0], pts[1])] if both else [])
        pts[-1] = _back(pts[-1], pts[-2], length * 0.6)
        if both:
            pts[0] = _back(pts[0], pts[1], length * 0.6)
        self.line(*pts, w=w)
        for tip, toward in ends:
            self.head(tip, toward, length, width)

    def arc_arrow(self, c, rx, ry, a0, a1, **kw):
        pts = arc_points(c, rx, ry, a0, a1)
        cut = kw.get("length", 4.2) * 0.6
        while len(pts) > 2 and math.dist(pts[-2], pts[-1]) < cut:  # keep the head's direction
            pts.pop(-2)
        self.arrow(*pts, **kw)


def _back(tip, toward, d):
    n = math.dist(tip, toward) or 1.0
    return (tip[0] + (toward[0] - tip[0]) * d / n, tip[1] + (toward[1] - tip[1]) * d / n)


def arc_points(c, rx, ry, a0, a1, step=6):
    """Points on an ellipse from angle a0 to a1 (degrees, anticlockwise on screen)."""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(c[0] + rx * math.cos(math.radians(a)), c[1] - ry * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / (n - 1) for i in range(n))]


def cube(pen, c, s):
    """Isometric cube outline seen from above, centred on c, s from centre to corner."""
    x, y = c
    k = s * 0.866
    hexagon = [(x, y - s), (x + k, y - s / 2), (x + k, y + s / 2), (x, y + s), (x - k, y + s / 2), (x - k, y - s / 2)]
    pen.line(*hexagon, closed=True)
    pen.line((x - k, y - s / 2), (x, y), (x + k, y - s / 2))
    pen.line((x, y), (x, y + s))
    return hexagon


def front_figure(pen, x=10.0, y=3.6):
    """Stick figure seen from the front, head centred at (x, y)."""
    pen.ring((x, y), 2.0)
    pen.line((x, y + 2.2), (x, y + 8.4))
    pen.line((x - 3.4, y + 7.0), (x, y + 3.6), (x + 3.4, y + 7.0))
    pen.line((x - 3.0, y + 14.4), (x, y + 8.4), (x + 3.0, y + 14.4))


def side_figure(pen, x=10.0, y=3.6):
    """Stick figure seen from the side, facing right, head centred at (x, y)."""
    pen.ring((x, y), 2.0)
    pen.line((x, y + 2.2), (x, y + 8.4))
    pen.line((x, y + 3.6), (x + 2.6, y + 7.4))
    pen.line((x, y + 8.4), (x, y + 14.4), (x + 2.6, y + 14.4))


# --- icons -------------------------------------------------------------------
# Each takes a Pen and draws one icon.

def _open(p):
    p.line((2, 16), (2, 4), (7.5, 4), (9.5, 6), (15.5, 6), (15.5, 9))
    p.line((2, 16), (5, 9.5), (18.5, 9.5), (15.5, 16), closed=True)


def _floppy(p):
    p.line((3, 3), (14.5, 3), (17, 5.5), (17, 17), (3, 17), closed=True)
    p.line((6.5, 3), (6.5, 7), (12.5, 7), (12.5, 3))
    p.line((6, 17), (6, 11.5), (14, 11.5), (14, 17))


def _image(p):
    p.line((2.5, 4), (17.5, 4), (17.5, 16), (2.5, 16), closed=True)
    p.fill((2.5, 16), (8, 9.5), (11.5, 13), (13.5, 11), (17.5, 15), (17.5, 16))
    p.dot((13.5, 7.5), 1.6)


def _copy(p):
    p.line((7, 2.5), (17.5, 2.5), (17.5, 13), (7, 13), closed=True)
    page = [(2.5, 7), (13, 7), (13, 17.5), (2.5, 17.5)]
    p.erase(*page)
    p.line(*page, closed=True)


def _copy_3d(p):
    p.line((7, 2.5), (17.5, 2.5), (17.5, 13), (7, 13), closed=True)
    p.erase(*cube(p, (7.5, 12.5), 5.5))
    cube(p, (7.5, 12.5), 5.5)


def _save_3d(p):
    cube(p, (10, 7.5), 5.5)
    p.line((3, 12), (3, 17), (17, 17), (17, 12))


def _save_shapes(p):
    """A small figure over a tray: download the figure as shapes (the website's PowerPoint file)."""
    p.ring((10, 3.6), 1.8)
    p.line((10, 5.6), (10, 9.2))
    p.line((7, 7.8), (10, 6.4), (13, 7.8))
    p.line((7.8, 12), (10, 9.2), (12.2, 12))
    p.line((3, 12), (3, 17), (17, 17), (17, 12))


def _undo(p):
    p.arc_arrow((11, 11.5), 6, 6, -50, 175)


def _reset(p):
    p.arc_arrow((10, 10.5), 6.5, 6.5, 65, -195)


def _ground(p):
    p.arrow((10, 2), (10, 14))
    p.line((2.5, 17.5), (17.5, 17.5), w=2.2)


def _limits(p):
    p.line((17.5, 16), (3.5, 16), (10.5, 3.9))
    p.line(*arc_points((3.5, 16), 9, 9, 6, 54), w=1.3)
    p.dot((3.5, 16), 2.0)


def _drag_screen(p):
    for x, y in ((2, 2), (18, 2), (18, 18), (2, 18)):  # corners of the screen
        dx, dy = (10 - x) * 0.45, (10 - y) * 0.45
        p.line((x + dx, y), (x, y), (x, y + dy), w=1.4)
    small = dict(w=1.4, length=3.4, width=5)
    p.arrow((10, 4.5), (10, 15.5), both=True, **small)
    p.arrow((4.5, 10), (15.5, 10), both=True, **small)


def _drag_floor(p):
    p.line((0.5, 17.5), (5.5, 5.5), (19.5, 5.5), (14.5, 17.5), closed=True, w=1.3)
    small = dict(w=1.4, length=3.2, width=4.6)
    p.arrow((4.2, 11.5), (15.8, 11.5), both=True, **small)
    p.arrow((8.3, 15.6), (11.7, 7.4), both=True, **small)


def _drag_vertical(p):
    p.line((1, 18.5), (4, 14.5), (19, 14.5), (16, 18.5), closed=True, w=1.3)
    p.arrow((10, 1.5), (10, 12.5), both=True, length=3.8, width=6)


def _pin(p):
    p.fill((7, 2), (13, 2), (13, 3.6), (12, 3.6), (12, 9), (15, 12.5), (5, 12.5),
           (8, 9), (8, 3.6), (7, 3.6))
    p.line((10, 12.5), (10, 18.5))


def _unpin(p):
    _pin(p)
    p.erase((2.5, 10), (17.5, 10), pad=1.6)
    p.line((2.5, 10), (17.5, 10))


def _mirror(p):
    for y in (1.5, 5.5, 9.5, 13.5):
        p.line((10, y), (10, y + 2.2), w=1.3)
    p.fill((8, 4.5), (8, 16), (1.5, 16))
    p.line((12, 4.5), (12, 16), (18.5, 16), closed=True, w=1.4)


def _twist(p):
    c, rx, ry = (10, 10.5), 7.5, 3.2
    p.line(*arc_points(c, rx, ry, 25, 180))
    p.erase((10, 2), (10, 18.5))
    p.line((10, 2), (10, 18.5))
    p.dot((10, 2.5), 1.8)
    front = arc_points(c, rx, ry, 180, 335)
    p.erase(*front[len(front) // 3: 2 * len(front) // 3 + 1], pad=1.0)
    p.arc_arrow(c, rx, ry, 180, 335, length=3.8, width=6)


def _turn(p):
    c, rx, ry = (10, 13), 8.8, 2.8
    p.line(*arc_points(c, rx, ry, 20, 180))
    front_figure(p, y=3.2)
    front = arc_points(c, rx, ry, 180, 340)
    p.erase(*front[len(front) // 4: 3 * len(front) // 4 + 1], pad=1.0)
    p.arc_arrow(c, rx, ry, 180, 340, length=3.8, width=6)


def _move(sign):
    def draw(p):
        front_figure(p, x=7)
        p.arrow((15.5, 10 + 7.5 * sign), (15.5, 10 - 7.5 * sign), length=3.8, width=6)
    return draw


def _tip(figure, sign):
    def draw(p):
        figure(p, x=10 - 3.6 * sign, y=4.6)
        foot = (10 - 3.6 * sign, 19)
        a0 = 90 - 18 * sign
        p.arc_arrow(foot, 13.5, 13.5, a0, a0 - 52 * sign, length=3.8, width=6)
    return draw


def _view(face):
    def draw(p):
        front = [(2.5, 7.5), (12.5, 7.5), (12.5, 17.5), (2.5, 17.5)]
        top = [(2.5, 7.5), (7.5, 2.5), (17.5, 2.5), (12.5, 7.5)]
        side = [(12.5, 7.5), (17.5, 2.5), (17.5, 12.5), (12.5, 17.5)]
        shade = p.color[:3] + (150,)
        p.fill(*{"front": front, "top": top, "side": side}[face], color=shade)
        for poly in (front, top, side):
            p.line(*poly, closed=True, w=1.4)
    return draw


def _view_angled(p):
    x, y, s = 10, 10, 8
    k = s * 0.866
    top = [(x, y - s), (x + k, y - s / 2), (x, y), (x - k, y - s / 2)]
    left = [(x - k, y - s / 2), (x, y), (x, y + s), (x - k, y + s / 2)]
    p.fill(*top, color=p.color[:3] + (150,))
    p.fill(*left, color=p.color[:3] + (70,))
    cube(p, (x, y), s)


def _centre(p):
    p.ring((10, 10), 5.5)
    for a, b in (((10, 1.5), (10, 5)), ((10, 15), (10, 18.5)), ((1.5, 10), (5, 10)), ((15, 10), (18.5, 10))):
        p.line(a, b)
    p.dot((10, 10), 1.5)


def _zoom(sign):
    def draw(p):
        p.ring((8.5, 8.5), 6)
        p.line((13, 13), (18, 18), w=2.6)
        p.line((5.6, 8.5), (11.4, 8.5))
        if sign > 0:
            p.line((8.5, 5.6), (8.5, 11.4))
    return draw


def _help(p):
    pts = arc_points((10, 7), 4, 4, 165, -55)
    p.line(*pts, (10, 12), (10, 13.2), w=2.2)
    p.dot((10, 17), 1.4)


# The flags are drawn in their own colours, in a 3:2 box.
FLAG = (1.0, 4.0, 19.0, 16.0)  # left, top, right, bottom
FLAG_WHITE = (255, 255, 255, 255)


def _info(p):
    p.ring((10, 10), 8.2)
    p.dot((10, 5.9), 1.3)
    p.line((10, 9), (10, 14.6), w=2.2)


def _rect(p, x0, y0, x1, y1, color):
    p.fill((x0, y0), (x1, y0), (x1, y1), (x0, y1), color=color)


def _flag_greece(p):
    x0, y0, x1, y1 = FLAG
    blue, h = (13, 94, 175, 255), (y1 - y0) / 9  # nine stripes, blue at top and bottom
    _rect(p, *FLAG, FLAG_WHITE)
    for i in range(0, 9, 2):
        _rect(p, x0, y0 + i * h, x1, y0 + (i + 1) * h, blue)
    # Canton five stripes square, with a white cross one stripe wide.
    _rect(p, x0, y0, x0 + 5 * h, y0 + 5 * h, blue)
    _rect(p, x0, y0 + 2 * h, x0 + 5 * h, y0 + 3 * h, FLAG_WHITE)
    _rect(p, x0 + 2 * h, y0, x0 + 3 * h, y0 + 5 * h, FLAG_WHITE)


def _flag_uk(p):
    x0, y0, x1, y1 = FLAG
    blue, red = (1, 33, 105, 255), (200, 16, 46, 255)
    u = (y1 - y0) / 30  # the flag is 30 units high
    c = ((x0 + x1) / 2, (y0 + y1) / 2)

    def band(corner, w0, w1, color):
        """The strip from the centre to a corner between offsets w0 and w1, measured anticlockwise."""
        dx, dy = corner[0] - c[0], corner[1] - c[1]
        n = math.hypot(dx, dy)
        nx, ny = dy / n, -dx / n  # perpendicular, anticlockwise on screen
        p.fill(*[(q[0] + nx * w, q[1] + ny * w) for q, w in ((c, w0), (corner, w0), (corner, w1), (c, w1))],
               color=color)

    _rect(p, *FLAG, blue)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for corner in corners:
        band(corner, -3 * u, 3 * u, FLAG_WHITE)
    for corner in corners:  # the red saltire is offset anticlockwise: broad white uppermost at the hoist
        band(corner, 0, 2 * u, red)
    _rect(p, c[0] - 5 * u, y0, c[0] + 5 * u, y1, FLAG_WHITE)
    _rect(p, x0, c[1] - 5 * u, x1, c[1] + 5 * u, FLAG_WHITE)
    _rect(p, c[0] - 3 * u, y0, c[0] + 3 * u, y1, red)
    _rect(p, x0, c[1] - 3 * u, x1, c[1] + 3 * u, red)
    # The diagonals run past the corners; clear everything outside the flag.
    for box in ((0, 0, GRID, y0), (0, y1, GRID, GRID), (0, 0, x0, GRID), (x1, 0, GRID, GRID)):
        _rect(p, *box, CLEAR)


# name: (draw function, mirror left-right, rotation in degrees)
ICONS = {
    "open": (_open, False, 0),
    "save": (_floppy, False, 0),
    "png": (_image, False, 0),
    "copy": (_copy, False, 0),
    "copy_3d": (_copy_3d, False, 0),
    "save_3d": (_save_3d, False, 0),
    "save_shapes": (_save_shapes, False, 0),
    "undo": (_undo, False, 0),
    "redo": (_undo, True, 0),
    "reset": (_reset, False, 0),
    "ground": (_ground, False, 0),
    "limits": (_limits, False, 0),
    "drag_screen": (_drag_screen, False, 0),
    "drag_floor": (_drag_floor, False, 0),
    "drag_vertical": (_drag_vertical, False, 0),
    "pin": (_pin, False, 40),
    "unpin": (_unpin, False, 40),
    "mirror": (_mirror, False, 0),
    "twist_minus": (_twist, True, 0),
    "twist_plus": (_twist, False, 0),
    "move_up": (_move(1), False, 0),
    "move_down": (_move(-1), False, 0),
    "turn_left": (_turn, False, 0),
    "turn_right": (_turn, True, 0),
    "tip_forward": (_tip(side_figure, 1), False, 0),
    "tip_back": (_tip(side_figure, -1), False, 0),
    "lean_left": (_tip(front_figure, 1), False, 0),
    "lean_right": (_tip(front_figure, 1), True, 0),
    "view_front": (_view("front"), False, 0),
    "view_side": (_view("side"), False, 0),
    "view_top": (_view("top"), False, 0),
    "view_angled": (_view_angled, False, 0),
    "centre": (_centre, False, 0),
    "zoom_in": (_zoom(1), False, 0),
    "zoom_out": (_zoom(-1), False, 0),
    "help": (_help, False, 0),
    "info": (_info, False, 0),
    "flag_el": (_flag_greece, False, 0),
    "flag_en": (_flag_uk, False, 0),
}


@functools.cache
def icon(name, size, color):
    """The icon called name as a size x size SRCALPHA surface."""
    draw, mirror, turn = ICONS[name]
    big = pygame.Surface((size * SUPERSAMPLE,) * 2, pygame.SRCALPHA)
    draw(Pen(big, tuple(color[:3]) + (255,), turn))
    if mirror:
        big = pygame.transform.flip(big, True, False)
    return pygame.transform.smoothscale(big, (size, size))
