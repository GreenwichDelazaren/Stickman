"""Stickman Poser: pose a 3D stick figure to illustrate exercises.

Run with:  python main.py
"""

import io
import json
import math
import os
import sys
import time
from typing import Any, cast

import numpy as np
import pygame
from OpenGL.GL import (
    GL_AMBIENT, GL_AMBIENT_AND_DIFFUSE, GL_BACK, GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_BUFFER_BIT,
    GL_COLOR_MATERIAL, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_DIFFUSE, GL_FALSE, GL_FLOAT, GL_FRONT_AND_BACK,
    GL_LEQUAL, GL_LIGHT0, GL_LIGHT_MODEL_AMBIENT, GL_LIGHTING, GL_LINEAR, GL_LINEAR_MIPMAP_LINEAR, GL_LINES,
    GL_MODELVIEW, GL_NORMAL_ARRAY, GL_NORMALIZE, GL_ONE_MINUS_SRC_ALPHA, GL_PACK_ALIGNMENT,
    GL_POLYGON_OFFSET_FILL, GL_POSITION, GL_PROJECTION, GL_QUADS, GL_RGB, GL_RGBA, GL_SHININESS, GL_SPECULAR,
    GL_SRC_ALPHA, GL_TEXTURE_2D, GL_TEXTURE_COORD_ARRAY, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TRIANGLES, GL_TRUE, GL_UNPACK_ALIGNMENT, GL_UNSIGNED_BYTE,
    GL_UNSIGNED_INT, GL_VERTEX_ARRAY, glBegin, glBindTexture, glBlendFunc, glClear, glClearColor, glColor3f,
    glColorMaterial, glDepthFunc, glDepthMask, glDisable, glDisableClientState, glDrawElements, glDrawPixels,
    glEnable, glEnableClientState, glEnd, glFinish, glGenTextures, glLightfv, glLightModelfv, glLoadMatrixf,
    glMaterialf, glMaterialfv, glMatrixMode, glNormalPointer, glPixelStorei, glPolygonOffset, glPopMatrix,
    glPushMatrix, glReadBuffer, glReadPixels, glRotatef, glScalef, glTexCoordPointer, glTexParameteri,
    glTranslatef, glVertex3f, glVertexPointer, glViewport, glWindowPos2i,
)
from OpenGL.GLU import GLU_SMOOTH, gluBuild2DMipmaps, gluCylinder, gluNewQuadric, gluQuadricNormals, gluSphere

import exercises as ex
import gltf
import i18n
import icons
import office_clip
import props
import scene
import skeleton as sk
from i18n import tr
from scene import (BACKGROUND, BONE_RADIUS, FACE, FLOOR_COLOR, FLOOR_HALF, GRID_COLOR, GRID_STEP, LIGHT_DIR,
                   SHADOW_COLOR, SIDE_COLORS, TATTOO_COLOR, TATTOO_FONT, TATTOO_PAD, TATTOO_TEXT, VIEW_ANGLES,
                   Camera, Tattoo, face_meshes, tattoo_mesh)


def default_poses_dir():
    """Where the file dialogs start: poses/ beside the code or, in the packaged .exe (whose
    code is unpacked to a temporary folder), a folder in the user's Documents."""
    if not getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "poses")
    import ctypes
    documents = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, documents)  # 5 = CSIDL_PERSONAL
    return os.path.join(documents.value or os.path.expanduser("~"), "Stickman Poses")


POSES_DIR = default_poses_dir()


def tattoo_image():
    """The tattoo text as a white pygame surface with alpha (needs pygame.font)."""
    font = pygame.font.SysFont(TATTOO_FONT[0], TATTOO_FONT[1], bold=True)
    text = font.render(TATTOO_TEXT, True, (255, 255, 255))
    image = pygame.Surface((text.get_width() + 2 * TATTOO_PAD, text.get_height() + 2 * TATTOO_PAD),
                           pygame.SRCALPHA)
    image.fill((255, 255, 255, 0))
    image.blit(text, (TATTOO_PAD, TATTOO_PAD))
    return image


HELP = [
    "Tab or the list under the toolbar: pick an exercise (type to search)",
    "Left-drag a joint ............ move it (bone lengths stay fixed)",
    "   + Ctrl .................... move parallel to the floor",
    "   + Shift ................... move straight up / down",
    "Drag empty space / right-drag  orbit camera",
    "Middle-drag / Shift+right-drag pan       Wheel  zoom",
    "P  pin / unpin joint           Shift+P  unpin all",
    "M  mirror selected side onto the other side",
    "Z/X twist selected joint (turn head, swing elbow/knee)",
    "L  realistic joint limits on / off",
    "Q/E turn  W/S tip fwd/back  A/D lean  (Shift: 5 deg steps)",
    "Up/Down arrow  raise / lower the figure (Shift: 1 cm steps)",
    "G  put figure on the floor     R  reset to one standing figure",
    "1 front  2 side  3 top  4 angled  F centre view  +/- zoom",
    "Ctrl+Z/Y undo/redo  Ctrl+S save  Ctrl+O open  Ctrl+E export PNG",
    "Ctrl+C copy as editable shapes  Ctrl+Shift+C copy as 3D model",
    "Ctrl+Shift+E export 3D model (.glb)",
    "T  language: Greek / English (the flag button)",
    "I  about Stickman (the i button)",
    "Hold a key or toolbar button to repeat it",
    "Colours: blue = left, red = right, green = pinned",
    "H  hide help",
]
HELP_GREEK = [
    "Tab ή η λίστα κάτω από τη γραμμή εργαλείων: επιλογή άσκησης (γράψτε για αναζήτηση)",
    "Σύρσιμο άρθρωσης ............. μετακίνηση (τα μήκη των οστών μένουν ίδια)",
    "   + Ctrl .................... παράλληλα με το δάπεδο",
    "   + Shift ................... κατακόρυφα πάνω / κάτω",
    "Σύρσιμο σε κενό/δεξί σύρσιμο   περιστροφή κάμερας",
    "Μεσαίο σύρσιμο / Shift+δεξί    μετατόπιση     Ροδέλα  ζουμ",
    "P  καρφίτσωμα / ξεκαρφίτσωμα   Shift+P  ξεκαρφίτσωμα όλων",
    "M  αντιγραφή της επιλεγμένης πλευράς στην άλλη πλευρά",
    "Z/X περιστροφή επιλεγμένης άρθρωσης (κεφάλι, αγκώνας/γόνατο)",
    "L  ρεαλιστικά όρια αρθρώσεων ενεργά / ανενεργά",
    "Q/E στροφή  W/S κλίση εμπρός/πίσω  A/D πλάγια κλίση  (Shift: ανά 5°)",
    "Πάνω/Κάτω βέλος  ανύψωση / χαμήλωμα της φιγούρας (Shift: ανά 1 cm)",
    "G  φιγούρα στο δάπεδο          R  επαναφορά σε μία όρθια φιγούρα",
    "1 πρόσοψη  2 πλάγια  3 κάτοψη  4 υπό γωνία  F κεντράρισμα  +/- ζουμ",
    "Ctrl+Z/Y αναίρεση/επανάληψη  Ctrl+S αποθήκευση  Ctrl+O άνοιγμα  Ctrl+E εξαγωγή PNG",
    "Ctrl+C αντιγραφή ως επεξεργάσιμα σχήματα  Ctrl+Shift+C ως τρισδιάστατο μοντέλο",
    "Ctrl+Shift+E εξαγωγή τρισδιάστατου μοντέλου (.glb)",
    "T  γλώσσα: Ελληνικά / English (το κουμπί με τη σημαία)",
    "I  σχετικά με το Stickman (το κουμπί i)",
    "Κρατήστε πατημένο ένα πλήκτρο ή κουμπί για επανάληψη",
    "Χρώματα: μπλε = αριστερά, κόκκινο = δεξιά, πράσινο = καρφιτσωμένο",
    "H  απόκρυψη βοήθειας",
]

ROTATE_KEYS = {
    pygame.K_q: ("yaw", 1), pygame.K_e: ("yaw", -1),
    pygame.K_w: ("pitch", 1), pygame.K_s: ("pitch", -1),
    pygame.K_a: ("roll", -1), pygame.K_d: ("roll", 1),
}
LIFT_KEYS = {pygame.K_UP: 1, pygame.K_DOWN: -1}
VIEWS = {pygame.K_1: VIEW_ANGLES["front"], pygame.K_2: VIEW_ANGLES["side"],
         pygame.K_3: VIEW_ANGLES["top"], pygame.K_4: VIEW_ANGLES["angled"]}
ZOOM_KEYS = {pygame.K_EQUALS: 1, pygame.K_PLUS: 1, pygame.K_KP_PLUS: 1,
             pygame.K_MINUS: -1, pygame.K_KP_MINUS: -1}
# Held keys repeat after REPEAT_DELAY seconds, every REPEAT_INTERVAL seconds.
REPEAT_KEYS = set(ROTATE_KEYS) | set(LIFT_KEYS) | set(ZOOM_KEYS) | {pygame.K_z, pygame.K_x}
REPEAT_CTRL_KEYS = {pygame.K_z, pygame.K_y}  # undo / redo
REPEAT_DELAY, REPEAT_INTERVAL = 0.4, 0.08

CTRL, SHIFT = pygame.KMOD_CTRL, pygame.KMOD_SHIFT
# Toolbar groups of (icon, tooltip, action), icons named as in icons.ICONS ("language" shows the flag of the
# current language).  An action is a (key, modifiers) pair, so a click does exactly what the key does, or a
# drag mode name.  Tooltips are translated with tr() when shown.
TOOLBAR = [
    [("info", "About Stickman (I)", (pygame.K_i, 0))],
    [("open", "Open a pose (Ctrl+O)", (pygame.K_o, CTRL)),
     ("save", "Save the pose (Ctrl+S)", (pygame.K_s, CTRL)),
     ("png", "Export a PNG image (Ctrl+E)", (pygame.K_e, CTRL)),
     ("copy", "Copy as editable shapes for Word or PowerPoint (Ctrl+C)", (pygame.K_c, CTRL)),
     ("copy_3d", "Copy as a 3D model for Word or PowerPoint (Ctrl+Shift+C)", (pygame.K_c, CTRL | SHIFT)),
     ("save_3d", "Export a 3D model file, .glb (Ctrl+Shift+E)", (pygame.K_e, CTRL | SHIFT))],
    [("undo", "Undo (Ctrl+Z)", (pygame.K_z, CTRL)),
     ("redo", "Redo (Ctrl+Y)", (pygame.K_y, CTRL)),
     ("reset", "Reset the pose (R)", (pygame.K_r, 0)),
     ("ground", "Put the figure on the floor (G)", (pygame.K_g, 0)),
     ("limits", "Realistic joint limits on / off (L)", (pygame.K_l, 0))],
    [("drag_screen", "Drag joints parallel to the screen", "screen"),
     ("drag_floor", "Drag joints parallel to the floor (or hold Ctrl while dragging)", "floor"),
     ("drag_vertical", "Drag joints straight up / down (or hold Shift while dragging)", "vertical")],
    [("pin", "Pin / unpin the selected joint (P)", (pygame.K_p, 0)),
     ("unpin", "Unpin all joints (Shift+P)", (pygame.K_p, SHIFT)),
     ("mirror", "Copy the selected side onto the other side (M)", (pygame.K_m, 0)),
     ("twist_minus", "Twist the selected joint one way (Z, Shift-click: 5 deg)", (pygame.K_z, 0)),
     ("twist_plus", "Twist the selected joint the other way (X, Shift-click: 5 deg)", (pygame.K_x, 0))],
    [("move_up", "Raise the figure (Up arrow, Shift-click: 1 cm)", (pygame.K_UP, 0)),
     ("move_down", "Lower the figure (Down arrow, Shift-click: 1 cm)", (pygame.K_DOWN, 0)),
     ("turn_left", "Turn the figure to its left (Q, Shift-click: 5 deg)", (pygame.K_q, 0)),
     ("turn_right", "Turn the figure to its right (E, Shift-click: 5 deg)", (pygame.K_e, 0)),
     ("tip_forward", "Tip the figure forward (W, Shift-click: 5 deg)", (pygame.K_w, 0)),
     ("tip_back", "Tip the figure back (S, Shift-click: 5 deg)", (pygame.K_s, 0)),
     ("lean_left", "Lean the figure to its left (A, Shift-click: 5 deg)", (pygame.K_a, 0)),
     ("lean_right", "Lean the figure to its right (D, Shift-click: 5 deg)", (pygame.K_d, 0))],
    [("view_front", "Front view (1)", (pygame.K_1, 0)),
     ("view_side", "Side view (2)", (pygame.K_2, 0)),
     ("view_top", "Top view (3)", (pygame.K_3, 0)),
     ("view_angled", "Angled view (4)", (pygame.K_4, 0)),
     ("centre", "Centre the view on the figure (F)", (pygame.K_f, 0)),
     ("zoom_in", "Zoom in (+ or mouse wheel)", (pygame.K_EQUALS, 0)),
     ("zoom_out", "Zoom out (- or mouse wheel)", (pygame.K_MINUS, 0)),
     ("help", "Show / hide the help (H)", (pygame.K_h, 0))],
    [("language", "Language: English. Switch to Greek (T)", (pygame.K_t, 0))],
]
TOOL_COLORS = {"bar": (25, 30, 38, 175), "button": (62, 70, 84, 255), "hover": (88, 99, 116, 255),
               "active": (46, 104, 196, 255), "icon": (235, 238, 242)}
TOOL_SIZE, TOOL_ICON, TOOL_GAP, TOOL_GROUP_GAP, TOOL_MARGIN = 30, 20, 4, 14, 6

INFO_WIDTH = 640  # widest line of the info text, in pixels
PANEL_OK = "OK"   # the button that closes the help or info box

MENU_COLORS = {"box": (25, 30, 38, 215), "list": (25, 30, 38, 240), "hover": (88, 99, 116, 255),
               "text": (235, 238, 242), "dim": (150, 160, 175)}
MENU_PAD, MENU_MAX_ROWS = 8, 24
MENU_PLACEHOLDER = "Choose an exercise (Tab)"
MENU_TWO = "2 positions"


def gl_matrix(m):
    return np.ascontiguousarray(m.T, dtype=np.float32)


def ask_file(save, title, extension, kind):
    import tkinter as tk
    from tkinter import filedialog

    os.makedirs(POSES_DIR, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    window_icon = tk.PhotoImage(master=root, data=icons.app_icon_png(48))
    root.iconphoto(True, window_icon)
    root.attributes("-topmost", True)
    try:
        filetypes = [(tr(kind), "*" + extension), (tr("All files"), "*.*")]
        if save:
            path = filedialog.asksaveasfilename(parent=root, title=tr(title), initialdir=POSES_DIR,
                                                filetypes=filetypes, defaultextension=extension)
        else:
            path = filedialog.askopenfilename(parent=root, title=tr(title), initialdir=POSES_DIR,
                                              filetypes=filetypes)
    finally:
        root.destroy()
    return path or None


class ExerciseMenu:
    """The drop-down list of exercises (exercises.CATEGORIES) on its own row
    under the toolbar buttons.  Open, it lists them by category and typing filters the list
    (matching the English or the Greek, accents optional); choosing one calls
    on_choose(exercise)."""

    def __init__(self, font, on_choose):
        self.font, self.on_choose = font, on_choose
        self.is_open = False
        self.query = ""
        self.scroll = 0          # first row shown
        self.highlight = None    # row index
        self.hover_box = False
        self.mouse = (-1, -1)              # last mouse position seen
        self.current = None                # name of the exercise shown, set by the app
        self.rect, self.window = pygame.Rect(0, 0, 1, 1), (1, 1)  # set by the app every frame
        self.row_h = font.get_linesize() + 6
        self._widths = {}  # language: width
        self._rows = (None, [])
        self._image = (None, (0, 0, b""))  # (cache key, (w, h, data))

    @property
    def width(self):
        if i18n.language not in self._widths:
            texts = [tr(e.name) for _, items in ex.CATEGORIES for e in items] + [tr(MENU_PLACEHOLDER)]
            texts += [i18n.upper(tr(category)) for category, _ in ex.CATEGORIES]
            self._widths[i18n.language] = (max(self.font.size(t)[0] for t in texts)
                                           + self.font.size(tr(MENU_TWO))[0] + 4 * MENU_PAD)
        return self._widths[i18n.language]

    def rows(self):
        """[(category, exercise)] matching the query, with (category, None) as the heading of each category."""
        if self._rows[0] != (self.query, i18n.language):
            self._rows = ((self.query, i18n.language), scene.search_exercises(self.query))
        return self._rows[1]

    # --- layout ------------------------------------------------------------

    def box(self):
        return self.rect

    def visible_rows(self):
        space = (self.window[1] - self.box().bottom - 12) // self.row_h
        return max(1, min(len(self.rows()), MENU_MAX_ROWS, space))

    def list_rect(self):
        box = self.box()
        return pygame.Rect(box.left, box.bottom + 2, box.width, self.visible_rows() * self.row_h)

    def contains(self, pos):
        return self.box().collidepoint(pos) or (self.is_open and self.list_rect().collidepoint(pos))

    def row_at(self, pos):
        rect = self.list_rect()
        if not rect.collidepoint(pos):
            return None
        i = self.scroll + (pos[1] - rect.top) // self.row_h
        return i if i < len(self.rows()) else None

    # --- state -------------------------------------------------------------

    def open(self, current=None):
        self.is_open = True
        self.set_query("")
        names = [e.name if e else None for _, e in self.rows()]
        if current in names:
            self.highlight = names.index(current)
            self.scroll = self.highlight - self.visible_rows() // 2
            self._clamp_scroll()

    def close(self):
        self.is_open = False

    def set_query(self, query):
        self.query, self.scroll, self.highlight = query, 0, None
        self.move(1)

    def move(self, steps):
        """Move the highlight by steps exercises (headings are skipped)."""
        items = [i for i, (_, e) in enumerate(self.rows()) if e]
        if not items:
            self.highlight = None
            return
        if self.highlight in items:
            k = min(max(items.index(self.highlight) + steps, 0), len(items) - 1)
        else:
            k = 0 if steps > 0 else len(items) - 1
        self.highlight = items[k]
        # Keep it in view, with its heading when it's the first of a category.
        first = self.highlight - (self.rows()[self.highlight - 1][1] is None)
        self.scroll = min(self.scroll, first)
        self.scroll = max(self.scroll, self.highlight - self.visible_rows() + 1)
        self._clamp_scroll()

    def _clamp_scroll(self):
        self.scroll = max(0, min(self.scroll, len(self.rows()) - self.visible_rows()))

    def choose(self, i):
        self.close()
        self.on_choose(self.rows()[i][1])

    # --- input -------------------------------------------------------------

    def mouse_down(self, pos, button):
        """Handle a mouse press; returns True if the menu used it.  While the
        list is open, a press anywhere else closes it."""
        if self.box().collidepoint(pos):
            if button == 1:
                self.close() if self.is_open else self.open(self.current)
            return True
        if not self.is_open:
            return False
        if self.list_rect().collidepoint(pos):
            i = self.row_at(pos)
            if button == 1 and i is not None and self.rows()[i][1]:
                self.choose(i)
        else:
            self.close()
        return True

    def motion(self, pos):
        self.mouse = pos
        self.hover_box = self.box().collidepoint(pos)
        if self.is_open:
            i = self.row_at(pos)
            if i is not None and self.rows()[i][1]:
                self.highlight = i

    def wheel(self, steps):
        """Scroll the open list if the mouse is over it; returns True if it did."""
        if not (self.is_open and self.list_rect().collidepoint(self.mouse)):
            return False
        self.scroll -= 3 * steps
        self._clamp_scroll()
        return True

    def key(self, key):
        """Keys while the list is open; typed text arrives through text()."""
        page = self.visible_rows() - 1
        moves = {pygame.K_UP: -1, pygame.K_DOWN: 1, pygame.K_PAGEUP: -page, pygame.K_PAGEDOWN: page,
                 pygame.K_HOME: -len(self.rows()), pygame.K_END: len(self.rows())}
        if key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.close()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.highlight is not None:
                self.choose(self.highlight)
        elif key in moves:
            self.move(moves[key])
        elif key == pygame.K_BACKSPACE:
            self.set_query(self.query[:-1])

    def text(self, text):
        text = "".join(c for c in text if c.isprintable())
        if text:
            self.set_query(self.query + text)

    # --- drawing -----------------------------------------------------------

    def draw(self):
        """The menu as [(x, y, w, h, RGBA data)] blocks for the HUD."""
        box = self.box()
        rows, shown = self.rows(), self.visible_rows()
        key = (self.is_open, self.query, self.scroll, self.highlight, self.hover_box, self.current, shown, self.window,
               i18n.language)
        if self._image[0] != key:
            height = box.height + (2 + shown * self.row_h if self.is_open else 0)
            surf = pygame.Surface((box.width, height), pygame.SRCALPHA)
            color = MENU_COLORS["hover"] if self.hover_box and not self.is_open else MENU_COLORS["box"]
            pygame.draw.rect(surf, color, (0, 0, box.width, box.height), border_radius=4)
            if self.is_open:
                label, dim = (self.query + "_", False) if self.query else (tr("Type to search..."), True)
            else:
                label, dim = (tr(self.current), False) if self.current else (tr(MENU_PLACEHOLDER), True)
            self._text(surf, label, MENU_PAD, box.height // 2, "dim" if dim else "text")
            # A small triangle: pointing down when closed, up when open.
            cx, cy, s = box.width - MENU_PAD - 6, box.height // 2, 5
            points = [(cx - s, cy + 3), (cx + s, cy + 3), (cx, cy - 3)] if self.is_open else \
                     [(cx - s, cy - 3), (cx + s, cy - 3), (cx, cy + 3)]
            pygame.draw.polygon(surf, MENU_COLORS["text"], points)
            if self.is_open:
                self._draw_list(surf, box.height + 2, rows, shown)
            self._image = (key, (box.width, height, pygame.image.tobytes(surf, "RGBA", True)))
        return [(box.x, box.y) + self._image[1]]

    def _draw_list(self, surf, top, rows, shown):
        w = surf.get_width()
        pygame.draw.rect(surf, MENU_COLORS["list"], (0, top, w, shown * self.row_h), border_radius=4)
        if not rows:
            self._text(surf, tr("No exercise matches"), MENU_PAD, top + self.row_h // 2, "dim")
        for n, i in enumerate(range(self.scroll, min(len(rows), self.scroll + shown))):
            category, exercise = rows[i]
            y = top + n * self.row_h
            if exercise is None:
                self._text(surf, i18n.upper(tr(category)), MENU_PAD, y + self.row_h // 2, "dim")
                continue
            if i == self.highlight:
                pygame.draw.rect(surf, MENU_COLORS["hover"], (2, y + 1, w - 4, self.row_h - 2), border_radius=3)
            self._text(surf, tr(exercise.name), 2 * MENU_PAD, y + self.row_h // 2, "text")
            if len(exercise.positions) > 1:
                tw = self.font.size(tr(MENU_TWO))[0]
                self._text(surf, tr(MENU_TWO), w - 2 * MENU_PAD - tw, y + self.row_h // 2, "dim")
        if len(rows) > shown:  # scroll bar
            bar_h = max(20, shown * self.row_h * shown // len(rows))
            bar_y = top + (shown * self.row_h - bar_h) * self.scroll // (len(rows) - shown)
            pygame.draw.rect(surf, MENU_COLORS["dim"], (w - 5, bar_y, 3, bar_h), border_radius=2)

    def _text(self, surf, text, x, center_y, color):
        image = self.font.render(text, True, MENU_COLORS[color])
        surf.blit(image, (x, center_y - image.get_height() // 2))


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Stickman Poser")
        pygame.display.set_icon(icons.app_icon(64))
        self._open_window((1280, 800))
        self.font = pygame.font.SysFont("consolas", 15)
        self.title_font = pygame.font.SysFont("consolas", 17, bold=True)
        self.tattoo_surface = tattoo_image()
        png = io.BytesIO()
        pygame.image.save(self.tattoo_surface, png, "png")
        self.tattoo = Tattoo(*self.tattoo_surface.get_size(), png.getvalue())
        self._tattoo_texture = None       # made on first draw
        self.quadric = gluNewQuadric()
        gluQuadricNormals(self.quadric, GLU_SMOOTH)
        self._init_gl()

        self.figures = [sk.Skeleton()]  # an exercise can show two positions side by side
        self.skel = self.figures[0]     # the figure being edited
        self.exercise = None            # name of the exercise last chosen
        self.props = []                 # the equipment (props.py parts); never changed in place
        self._prop_meshes = (None, [])  # (props, meshes for drawing)
        self.menu = ExerciseMenu(self.font, self.choose_exercise)
        self.camera = Camera()
        self.selected = None            # joint index in self.skel
        self.hovered = None             # (figure, joint index)
        self.drag: dict[str, Any] | None = None  # active joint drag
        self.camera_drag = None   # "orbit" or "pan"
        self.press_pos = (0, 0)
        self.undo_stack, self.redo_stack = [], []
        self.show_help = False
        self.show_info = False         # the info text (scene.ABOUT)
        self.panel_ok = self._panel_ok = None  # the help or info box's OK button: in the window, in the box
        self.ok_hover = False
        self.message, self.message_until = "", 0.0
        self._hud_key, self._hud = None, []
        self.drag_mode = "screen"  # used when no modifier is held
        self.held = None           # key or toolbar button held down, for auto-repeat
        self.tool_hover = self.tool_pressed = None
        self._tools = (None, [], pygame.Rect(0, 0, 1, 1), 0)  # (key, [(rect, item)], menu rect, height)
        self._tool_image = (None, (0, 0, b""))               # (cache key, (w, h, data))
        self.running = True
        self._update_matrices()

    def _open_window(self, size):
        for samples in (4, 0):
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1 if samples else 0)
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, samples)
            try:
                pygame.display.set_mode(size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
                return
            except pygame.error:
                if not samples:
                    raise

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_LIGHT0)
        glEnable(GL_NORMALIZE)
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.35, 0.35, 0.35, 1.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.75, 0.75, 0.75, 1.0))
        glLightfv(GL_LIGHT0, GL_SPECULAR, (0.35, 0.35, 0.35, 1.0))
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (0.15, 0.15, 0.15, 1.0))
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.25, 0.25, 0.25, 1.0))
        glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 40.0)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPixelStorei(GL_PACK_ALIGNMENT, 1)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

    # --- main loop ---------------------------------------------------------

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            self._update_matrices()
            for event in pygame.event.get():
                self.handle(event)
            if self.drag and "mouse" in self.drag:
                self.update_drag(*self.drag.pop("mouse"))
            self.repeat_held()
            self.render()
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

    def say(self, text):
        self.message, self.message_until = text, time.time() + 4.0

    # --- projection helpers ------------------------------------------------

    def _update_matrices(self):
        self.v = scene.View(self.camera, pygame.display.get_window_size())
        self.size, self.proj, self.view = self.v.size, self.v.proj, self.v.view
        self.menu.rect, self.menu.window = self.toolbar()[1], self.size

    def pick(self, mx, my):
        """(figure, joint index) of the joint under the mouse, or None."""
        return scene.pick(self.figures, self.v, mx, my)

    # --- editing -----------------------------------------------------------

    def state(self):
        return self.exercise, self.figures.index(self.skel), [f.state() for f in self.figures], self.props

    def set_state(self, state):
        self.exercise, active, states, self.props = state
        figures = self.figures[:len(states)]
        while len(figures) < len(states):
            figures.append(self.new_figure())
        for figure, s in zip(figures, states):
            figure.set_state(s)
        self.set_figures(figures, active, keep_selection=True)

    def new_figure(self):
        figure = sk.Skeleton()
        figure.limits_on = self.skel.limits_on
        return figure

    def set_figures(self, figures, active=0, keep_selection=False):
        self.figures, self.skel = figures, figures[active]
        self.hovered = None
        if not keep_selection:
            self.selected = None

    def push_undo(self, state):
        self.undo_stack.append(state)
        del self.undo_stack[:-200]
        self.redo_stack.clear()

    def edit(self, fn, *args):
        self.push_undo(self.state())
        fn(*args)

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.state())
            self.set_state(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.state())
            self.set_state(self.redo_stack.pop())

    def reset(self):
        self.set_figures([self.new_figure()])
        self.exercise = None
        self.props = []

    def set_limits(self, on):
        for figure in self.figures:
            figure.set_limits(on)

    def choose_exercise(self, exercise):
        self.edit(self.load_exercise, exercise)
        if len(exercise.positions) > 1:
            self.say(tr("{}: start position on the left, end position on the right").format(tr(exercise.name)))
        else:
            self.say(tr(exercise.name))

    def load_exercise(self, exercise):
        """Show the exercise's positions side by side, seen from its best angle."""
        figures, self.props = scene.build_exercise(exercise, self.camera, self.size, self.skel.limits_on)
        self.set_figures(figures)
        self.exercise = exercise.name

    def figures_bounds(self):
        """Corners of a box around the figures and the equipment."""
        return scene.figures_bounds(self.figures, self.props)

    def begin_drag(self, j, mx, my, mods):
        mode = "floor" if mods & CTRL else "vertical" if mods & SHIFT else self.drag_mode
        self.drag = scene.begin_drag(self.skel, j, self.v, self.camera, mode, mx, my)
        self.drag.update(before=self.state(), moved=False)

    def update_drag(self, mx, my):
        d = self.drag
        if d is None:
            return
        target = scene.drag_target(d, self.v, mx, my)
        if target is None:
            return
        if not d["moved"]:
            self.push_undo(d["before"])
            d["moved"] = True
        self.skel.drag(d["joint"], target)

    # --- input -------------------------------------------------------------

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3) and self.menu.mouse_down(e.pos, e.button):
            self.held = None
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3) and (tool := self.tool_at(e.pos)) is not None:
            if e.button == 1 and tool >= 0:
                self.press_tool(tool)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3) and self.over_ok(e.pos):
            if e.button == 1:
                self.close_panel()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3):
            mods = pygame.key.get_mods()
            hit = self.pick(*e.pos) if e.button == 1 else None
            if hit is not None:
                self.skel, self.selected = hit
                self.begin_drag(self.selected, *e.pos, mods=mods)
            elif e.button == 2 or (e.button == 3 and mods & pygame.KMOD_SHIFT):
                self.camera_drag = "pan"
            else:
                self.camera_drag = "orbit"
            self.press_pos = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.tool_pressed is not None:
            self.tool_pressed = None
            if self.held and self.held["button"]:
                self.held = None
        elif e.type == pygame.MOUSEBUTTONUP and e.button in (1, 2, 3):
            clicked = math.dist(e.pos, self.press_pos) < 4
            if e.button == 1 and self.drag is None and self.camera_drag and clicked:
                self.selected = None
            if self.drag and "mouse" in self.drag:
                self.update_drag(*self.drag.pop("mouse"))
            self.drag = self.camera_drag = None
        elif e.type == pygame.MOUSEMOTION:
            if self.drag:
                self.drag["mouse"] = e.pos  # solved once per frame in run()
            elif self.camera_drag == "orbit":
                self.camera.orbit(*e.rel)
            elif self.camera_drag == "pan":
                self.camera.pan(*e.rel, height=self.size[1])
            else:
                self.menu.motion(e.pos)
                tool = None if self.menu.is_open or self.menu.contains(e.pos) else self.tool_at(e.pos)
                self.tool_hover = tool if tool is not None and tool >= 0 else None
                self.ok_hover = tool is None and not self.menu.is_open and self.over_ok(e.pos)
                self.hovered = self.pick(*e.pos) if tool is None and not self.ok_hover and not self.menu.is_open \
                    and not self.menu.contains(e.pos) else None
        elif e.type == pygame.MOUSEWHEEL:
            if not self.menu.wheel(e.y):
                self.camera.zoom(e.y)
        elif e.type == pygame.KEYDOWN and self.menu.is_open:
            self.menu.key(e.key)
        elif e.type == pygame.TEXTINPUT and self.menu.is_open:
            self.menu.text(e.text)
        elif e.type == pygame.KEYDOWN:
            self.on_key(e.key, e.mod)
            if self.repeats(e.key, e.mod):
                self.hold(e.key, e.mod, button=False)
        elif e.type == pygame.KEYUP:
            if self.held and not self.held["button"] and self.held["key"] == e.key:
                self.held = None
        elif e.type == pygame.WINDOWFOCUSLOST:
            self.held = self.tool_pressed = None

    @staticmethod
    def repeats(key, mod):
        return key in (REPEAT_CTRL_KEYS if mod & CTRL else REPEAT_KEYS)

    def over_ok(self, pos):
        """Whether pos is on the OK button of the help or info box."""
        return bool(self.panel_ok and (self.show_help or self.show_info) and self.panel_ok.collidepoint(pos))

    def hold(self, key, mod, button):
        self.held = {"key": key, "mod": mod, "button": button, "next": time.time() + REPEAT_DELAY}

    def repeat_held(self):
        now = time.time()
        if self.held and now >= self.held["next"] and not self.menu.is_open:
            self.held["next"] = now + REPEAT_INTERVAL
            self.on_key(self.held["key"], self.held["mod"])

    def on_key(self, key, mod):
        shift = mod & pygame.KMOD_SHIFT
        sel = self.selected
        if mod & pygame.KMOD_CTRL:
            if key == pygame.K_z:
                self.redo() if shift else self.undo()
            elif key == pygame.K_y:
                self.redo()
            elif key == pygame.K_s:
                self.save_pose()
            elif key == pygame.K_o:
                self.open_pose()
            elif key == pygame.K_e:
                self.export_model() if shift else self.export_image()
            elif key == pygame.K_c:
                self.copy_to_clipboard(three_d=bool(shift))
            return
        if key == pygame.K_h:
            self.show_help, self.show_info = not self.show_help, False
        elif key == pygame.K_i:
            self.show_info, self.show_help = not self.show_info, False
        elif key == pygame.K_t:
            i18n.language = "en" if i18n.language == "el" else "el"
            self.say(tr("Language: English"))
        elif key == pygame.K_TAB:
            self.held = None
            self.menu.open(self.exercise)
        elif key == pygame.K_ESCAPE:
            self.selected = None
        elif key == pygame.K_p:
            if shift:
                self.edit(self.skel.clear_pins)
                self.say(tr("All pins removed"))
            elif sel is None:
                self.say(tr("Click a joint first, then press P to pin it"))
            else:
                self.edit(self.skel.toggle_pin, sel)
        elif key == pygame.K_m:
            side = None if sel is None else self.skel.side(sel)
            if side is None:
                self.say(tr("Select a left or right joint to mirror its side"))
            else:
                self.edit(self.skel.mirror, side)
                self.say(tr({"l": "Copied left side onto the other side",
                             "r": "Copied right side onto the other side"}[side]))
        elif key in (pygame.K_z, pygame.K_x):
            if sel is None:
                self.say(tr("Click a joint first, then press Z/X to twist it"))
            else:
                before = self.state()
                step = (5 if shift else 15) * (1 if key == pygame.K_x else -1)
                if self.skel.twist(sel, step):
                    self.push_undo(before)
                else:
                    self.say(tr("This joint can't twist any further"))
        elif key == pygame.K_l:
            self.edit(self.set_limits, not self.skel.limits_on)
            if self.skel.limits_on:
                self.say(tr("Joint limits on"))
        elif key in ROTATE_KEYS:
            kind, sign = ROTATE_KEYS[key]
            self.edit(self.skel.turn, kind, sign * (5 if shift else 15))
        elif key in LIFT_KEYS:
            step = LIFT_KEYS[key] * (0.01 if shift else 0.05)
            self.edit(self.skel.translate, np.array([0.0, step, 0.0]))
        elif key == pygame.K_g:
            self.edit(self.skel.drop_to_ground)
        elif key == pygame.K_r:
            self.edit(self.reset)
            self.say(tr("Pose reset (Ctrl+Z to undo)"))
        elif key in VIEWS:
            self.camera.yaw, self.camera.pitch = VIEWS[key]
        elif key == pygame.K_f:
            lo, hi = self.figures_bounds()
            self.camera.target = (lo + hi) / 2
        elif key in ZOOM_KEYS:
            self.camera.zoom(ZOOM_KEYS[key])
        elif key == pygame.K_F12:
            self.export_image()

    # --- toolbar -----------------------------------------------------------

    def toolbar(self):
        """[(rect, (icon, tooltip, action))] for the current window width, the
        exercise list's rect and the toolbar height.  Groups wrap onto a new row
        when they don't fit; the list has a row of its own under the buttons."""
        width = self.size[0]
        if self._tools[0] != (width, i18n.language):  # the list's width depends on the language
            items, x, y = [], TOOL_MARGIN, TOOL_MARGIN
            for group in TOOLBAR:
                if x > TOOL_MARGIN and x + len(group) * (TOOL_SIZE + TOOL_GAP) - TOOL_GAP > width - TOOL_MARGIN:
                    x, y = TOOL_MARGIN, y + TOOL_SIZE + TOOL_GAP
                for item in group:
                    items.append((pygame.Rect(x, y, TOOL_SIZE, TOOL_SIZE), item))
                    x += TOOL_SIZE + TOOL_GAP
                x += TOOL_GROUP_GAP - TOOL_GAP
            y += TOOL_SIZE + TOOL_GAP
            menu = pygame.Rect(TOOL_MARGIN, y, max(1, min(self.menu.width, width - 2 * TOOL_MARGIN)), TOOL_SIZE)
            self._tools = ((width, i18n.language), items, menu, menu.bottom + TOOL_MARGIN)
        return self._tools[1:]

    def tool_at(self, pos):
        """Index of the toolbar button at pos, -1 elsewhere on the toolbar, or None."""
        items, _, height = self.toolbar()
        if pos[1] >= height:
            return None
        return next((i for i, (rect, _) in enumerate(items) if rect.collidepoint(pos)), -1)

    def press_tool(self, i):
        action = self.toolbar()[0][i][1][2]
        self.tool_pressed = i
        if isinstance(action, str):
            self.drag_mode = action
            return
        key, mod = action
        if self.repeats(key, mod) and not mod & CTRL:
            mod |= pygame.key.get_mods() & SHIFT  # Shift-click: small steps
        self.on_key(key, mod)
        if self.repeats(key, mod) and self.tool_pressed == i:
            self.hold(key, mod, button=True)

    def tool_active(self, action):
        if isinstance(action, str):
            return self.drag_mode == action
        return {(pygame.K_l, 0): self.skel.limits_on, (pygame.K_h, 0): self.show_help, (pygame.K_i, 0): self.show_info,
                (pygame.K_p, 0): self.selected in self.skel.pins}.get(action, False)

    def draw_toolbar(self):
        """The toolbar and the tooltip, if any, as two lists of HUD blocks."""
        items, _, height = self.toolbar()
        w = self.size[0]
        states = tuple(self.tool_active(action) for _, (_, _, action) in items)
        key = (w, self.tool_hover, self.tool_pressed, states, i18n.language)
        if self._tool_image[0] != key:
            surf = pygame.Surface((w, height), pygame.SRCALPHA)
            surf.fill(TOOL_COLORS["bar"])
            for i, ((rect, (name, _, _)), active) in enumerate(zip(items, states)):
                color = TOOL_COLORS["active" if active else "button"]
                if i in (self.tool_hover, self.tool_pressed):
                    color = tuple(min(255, c + 26) for c in color[:3]) + (255,)
                pygame.draw.rect(surf, color, rect, border_radius=4)
                if name == "language":  # the flag fills most of the button
                    image = icons.icon("flag_" + i18n.language, TOOL_SIZE - 4, TOOL_COLORS["icon"])
                else:
                    image = icons.icon(name, TOOL_ICON, TOOL_COLORS["icon"])
                surf.blit(image, image.get_rect(center=rect.center))
            self._tool_image = (key, (w, height, pygame.image.tobytes(surf, "RGBA", True)))
        tips = []
        if self.tool_hover is not None and self.tool_pressed is None:
            rect, (_, tip, _) = items[self.tool_hover]
            tw, th, data = self._text_block([tr(tip)], alpha=245)
            tips.append((max(0, min(rect.left, w - tw)), height + 2, tw, th, data))
        return [(0, 0) + self._tool_image[1]], tips

    # --- files -------------------------------------------------------------

    def _after_dialog(self):
        self.drag = self.camera_drag = self.held = self.tool_pressed = None

    def save_pose(self):
        path = ask_file(True, "Save pose", ".json", "Pose")
        self._after_dialog()
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(scene.pose_file(self.figures, self.exercise, self.props), f, indent=2)
            self.say(tr("Saved {}").format(os.path.basename(path)))

    def open_pose(self):
        path = ask_file(False, "Open pose", ".json", "Pose")
        self._after_dialog()
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    dicts, exercise, parts = scene.read_pose_file(json.load(f))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.say(tr("Could not open pose: {}").format(exc))
                return
            self.edit(self.load_figures, dicts, exercise, parts)
            self.say(tr("Opened {}").format(os.path.basename(path)))

    def load_figures(self, dicts, exercise=None, parts=()):
        """Replace the figures with poses saved by Skeleton.to_dict, and the equipment with parts."""
        figures = [self.new_figure() for _ in dicts]
        for figure, data in zip(figures, dicts):
            figure.from_dict(data)
        self.set_figures(figures)
        self.exercise = exercise
        self.props = list(parts)

    def export_image(self):
        path = ask_file(True, "Export image", ".png", "PNG image")
        self._after_dialog()
        if not path:
            return
        pygame.image.save(self._capture_image(), path)
        self.say(tr("Exported {}").format(os.path.basename(path)))

    def _capture_image(self):
        self.render(clean=True)
        glFinish()
        w, h = self.size
        glReadBuffer(GL_BACK)
        data = cast(bytes, glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE))
        return pygame.transform.flip(pygame.image.frombuffer(data, (w, h), "RGB"), False, True)

    def export_model(self):
        path = ask_file(True, "Export 3D model", ".glb", "3D model (glTF)")
        self._after_dialog()
        if path:
            with open(path, "wb") as f:
                f.write(gltf.build_glb(self.model_parts()))
            self.say(tr("Exported {}").format(os.path.basename(path)))

    def copy_to_clipboard(self, three_d=False):
        """Copy the figure as Office shapes, or as a 3D model seen from the
        current view, with a bitmap for other programs."""
        image = self._capture_image()
        png = io.BytesIO()
        pygame.image.save(image, png, "png")
        formats: dict[str | int, bytes] = {}  # clipboard format name or id: data
        if three_d:
            # Office shows a pasted model from its front (+z), so turn the
            # model to put the current view there.
            formats[office_clip.MODEL_FORMAT] = gltf.build_glb(self.model_parts(), rotation=self.view[:3, :3])
        else:
            formats[office_clip.GVML_FORMAT] = office_clip.build_gvml(self.figure_shapes(), "Stickman")
        formats["PNG"] = png.getvalue()
        formats[office_clip.CF_DIB] = office_clip.dib(*image.get_size(), pygame.image.tobytes(image, "RGB"))
        try:
            office_clip.set_clipboard(formats, pygame.display.get_wm_info().get("window"))
        except OSError as exc:
            self.say(tr("Could not copy: {}").format(exc))
            return
        self.say(tr("Copied figure as a 3D model: paste into Word or PowerPoint" if three_d
                    else "Copied figure: paste into Word or PowerPoint"))

    def model_parts(self):
        """The figures and the equipment as parts for the 3D export."""
        return scene.model_parts(self.figures, self.props, self.tattoo)

    def figure_shapes(self):
        """The figures as flat 2D shapes from the current view, far to near."""
        return scene.figure_shapes(self.figures, self.props, self.v, self.tattoo)

    # --- drawing -----------------------------------------------------------

    def render(self, clean=False):
        self._update_matrices()
        w, h = self.size
        glViewport(0, 0, w, h)
        glClearColor(*BACKGROUND, 1.0)
        glClear(int(GL_COLOR_BUFFER_BIT) | int(GL_DEPTH_BUFFER_BIT))
        glMatrixMode(GL_PROJECTION)
        glLoadMatrixf(gl_matrix(self.proj))
        glMatrixMode(GL_MODELVIEW)
        glLoadMatrixf(gl_matrix(self.view))
        glLightfv(GL_LIGHT0, GL_POSITION, (*LIGHT_DIR, 0.0))

        above = self.camera.eye()[1] > 0
        self.draw_floor(solid=above)
        if above:
            glPushMatrix()
            glScalef(1.0, 0.0, 1.0)  # flatten onto the floor
            glColor3f(*SHADOW_COLOR)
            for skel in self.figures:
                self.draw_figure(skel, shadow=True)
            self.draw_props(shadow=True)
            glPopMatrix()
        self.draw_props()
        for skel in self.figures:
            self.draw_figure(skel, clean=clean)
        if not clean:
            self.draw_hud()

    def draw_floor(self, solid):
        glDisable(GL_LIGHTING)
        if solid:
            glEnable(GL_POLYGON_OFFSET_FILL)
            glPolygonOffset(1.0, 1.0)  # keep grid lines and shadow on top
            glColor3f(*FLOOR_COLOR)
            glBegin(GL_QUADS)
            for x, z in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
                glVertex3f(x * FLOOR_HALF, 0.0, z * FLOOR_HALF)
            glEnd()
            glDisable(GL_POLYGON_OFFSET_FILL)
        glColor3f(*GRID_COLOR)
        glBegin(GL_LINES)
        n = int(FLOOR_HALF / GRID_STEP)
        for i in range(-n, n + 1):
            v = i * GRID_STEP
            glVertex3f(v, 0.0, -FLOOR_HALF)
            glVertex3f(v, 0.0, FLOOR_HALF)
            glVertex3f(-FLOOR_HALF, 0.0, v)
            glVertex3f(FLOOR_HALF, 0.0, v)
        glEnd()

    def highlights(self, skel, clean):
        """(selected, hovered) joint indices in skel, None for neither."""
        if clean:
            return None, None
        return (self.selected if skel is self.skel else None,
                self.hovered[1] if self.hovered and self.hovered[0] is skel else None)

    def draw_figure(self, skel, shadow=False, clean=False):
        pos = skel.pos
        if not shadow:
            glEnable(GL_LIGHTING)
        for parent, child in skel.bones:
            if not shadow:
                glColor3f(*SIDE_COLORS[skel.side(child)][0])
            self.cylinder(pos[parent], pos[child], BONE_RADIUS)
        selected, hovered = self.highlights(skel, clean)
        for i, p in enumerate(pos):
            radius = skel.radii[i]
            if not shadow:
                color, scale = scene.joint_style(skel, i, selected, hovered, clean)
                glColor3f(*color)
                radius *= scale
            self.sphere(p, radius)
        if not shadow:
            self.draw_face(skel, clean)
            self.draw_tattoo(skel)
        glDisable(GL_LIGHTING)

    def draw_face(self, skel, clean):
        """The eyes and nose, which show which way the head faces. They turn with the head when it's
        hovered or selected (darker than the head, so they stay visible)."""
        selected, hovered = self.highlights(skel, clean)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        for (_, _, color), (positions, normals, tris) in zip(FACE, face_meshes(skel)):
            glColor3f(*scene.face_color(skel, color, selected, hovered))
            positions, normals = positions.astype(np.float32), normals.astype(np.float32)  # alive until drawn
            glVertexPointer(3, GL_FLOAT, 0, positions)
            glNormalPointer(GL_FLOAT, 0, normals)
            glDrawElements(GL_TRIANGLES, tris.size, GL_UNSIGNED_INT, tris.astype(np.uint32))
        glDisableClientState(GL_NORMAL_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

    def draw_tattoo(self, skel):
        """The tattoo, a textured strip on the forearm, lit like the arm. It doesn't write depth, so
        its transparent parts don't hide what's drawn after it."""
        if self._tattoo_texture is None:
            self._tattoo_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._tattoo_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            w, h = self.tattoo_surface.get_size()
            gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                              pygame.image.tobytes(self.tattoo_surface, "RGBA"))  # row 0 at texcoord 0
        positions, normals, texcoords, tris = tattoo_mesh(skel, self.tattoo.aspect)
        positions, normals = positions.astype(np.float32), normals.astype(np.float32)  # alive until drawn
        texcoords = texcoords.astype(np.float32)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self._tattoo_texture)
        glEnable(GL_BLEND)
        glDepthMask(GL_FALSE)
        glColor3f(*TATTOO_COLOR)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, positions)
        glNormalPointer(GL_FLOAT, 0, normals)
        glTexCoordPointer(2, GL_FLOAT, 0, texcoords)
        glDrawElements(GL_TRIANGLES, tris.size, GL_UNSIGNED_INT, tris.astype(np.uint32))
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

    def draw_props(self, shadow=False):
        if self._prop_meshes[0] is not self.props:
            self._prop_meshes = (self.props, [(positions.astype(np.float32), normals.astype(np.float32),
                                               tris.astype(np.uint32))
                                              for positions, normals, tris in map(props.mesh, self.props)])
        if not shadow:
            glEnable(GL_LIGHTING)
            glColor3f(*props.COLOR)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)
        for positions, normals, tris in self._prop_meshes[1]:
            glVertexPointer(3, GL_FLOAT, 0, positions)
            glNormalPointer(GL_FLOAT, 0, normals)
            glDrawElements(GL_TRIANGLES, tris.size, GL_UNSIGNED_INT, tris)
        glDisableClientState(GL_NORMAL_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisable(GL_LIGHTING)

    def sphere(self, p, radius):
        glPushMatrix()
        glTranslatef(*p.tolist())
        detail = 32 if radius > 0.05 else 18
        gluSphere(self.quadric, radius, detail, detail * 2 // 3)
        glPopMatrix()

    def cylinder(self, a, b, radius):
        d = b - a
        length = np.linalg.norm(d)
        if length < 1e-6:
            return
        d = d / length
        angle = math.degrees(math.acos(max(-1.0, min(1.0, d[2]))))
        axis = (-d[1], d[0], 0.0)  # z axis x d
        if math.hypot(axis[0], axis[1]) < 1e-9:
            axis = (1.0, 0.0, 0.0)
        glPushMatrix()
        glTranslatef(*a.tolist())
        glRotatef(angle, *(float(v) for v in axis))
        gluCylinder(self.quadric, radius, radius, length, 14, 1)
        glPopMatrix()

    def status_text(self):
        parts = []
        def which(skel):
            return tr(" of figure {}").format(self.figures.index(skel) + 1) if len(self.figures) > 1 else ""
        if self.selected is not None:
            name = tr(sk.pretty_name(self.skel.names[self.selected])) + which(self.skel)
            parts.append(tr("Selected: {}").format(name) + (tr(" (pinned)") if self.selected in self.skel.pins else ""))
        elif self.hovered is not None:
            skel, j = self.hovered
            parts.append(tr(sk.pretty_name(skel.names[j])) + which(skel))
        if self.skel.pins:
            parts.append(tr("Pins: {}").format(len(self.skel.pins)))
        if not self.skel.limits_on:
            parts.append(tr("Joint limits OFF"))
        if time.time() < self.message_until:
            parts.append(self.message)
        return "  |  ".join(parts)

    def _wrap(self, text, width):
        """Text broken into lines no wider than width pixels (at spaces)."""
        lines = []
        for word in text.split():
            if lines and self.font.size(lines[-1] + " " + word)[0] <= width:
                lines[-1] += " " + word
            else:
                lines.append(word)
        return lines

    def info_lines(self):
        """scene.ABOUT in the current language, wrapped to the window, with a blank line between paragraphs."""
        width = min(INFO_WIDTH, self.size[0] - 36)
        lines = []
        for paragraph in scene.ABOUT:
            lines += ([""] if lines else []) + self._wrap(tr(paragraph), width)
        return lines

    def _text_block(self, lines, alpha=175):
        pad, line_h = 8, self.font.get_linesize()
        rendered = [self.font.render(line, True, (235, 238, 242)) for line in lines]
        w = max(r.get_width() for r in rendered) + 2 * pad
        h = line_h * len(lines) + 2 * pad
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((25, 30, 38, alpha))
        for i, r in enumerate(rendered):
            surf.blit(r, (pad, pad + i * line_h))
        return w, h, pygame.image.tobytes(surf, "RGBA", True)

    def _panel(self, title, lines, alpha=200):
        """A text block with a title and an OK button at the bottom right: ((w, h, data), OK button rect in it)."""
        pad, line_h, gap = 8, self.font.get_linesize(), 8
        heading = self.title_font.render(title, True, TOOL_COLORS["icon"])
        rendered = [self.font.render(line, True, TOOL_COLORS["icon"]) for line in lines]
        label = self.font.render(PANEL_OK, True, TOOL_COLORS["icon"])
        ok = pygame.Rect(0, 0, max(64, label.get_width() + 24), TOOL_SIZE - 4)
        w = max([heading.get_width(), ok.width] + [r.get_width() for r in rendered]) + 2 * pad
        body = pad + heading.get_height() + gap
        h = body + line_h * len(lines) + 2 * gap + ok.height + pad
        ok.bottomright = (w - pad, h - pad)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((25, 30, 38, alpha))
        surf.blit(heading, (pad, pad))
        pygame.draw.line(surf, MENU_COLORS["hover"], (pad, body - gap // 2), (w - pad, body - gap // 2))
        for i, r in enumerate(rendered):
            surf.blit(r, (pad, body + i * line_h))
        pygame.draw.rect(surf, TOOL_COLORS["hover" if self.ok_hover else "button"], ok, border_radius=4)
        surf.blit(label, label.get_rect(center=ok.center))
        return (w, h, pygame.image.tobytes(surf, "RGBA", True)), ok

    def close_panel(self):
        self.show_help = self.show_info = self.ok_hover = False

    def draw_hud(self):
        status = self.status_text()
        key = (self.show_help, self.show_info, self.ok_hover, status, i18n.language, self.size[0])
        if key != self._hud_key:
            self._hud_key = key
            self._hud = []  # (block, at the top)
            self._panel_ok = None
            if self.show_help:
                block, self._panel_ok = self._panel(tr(scene.HELP_TITLE),
                                                    HELP_GREEK if i18n.language == "el" else HELP)
                self._hud.append((block, True))
            elif self.show_info:
                block, self._panel_ok = self._panel(tr(scene.ABOUT_TITLE), self.info_lines(), alpha=225)
                self._hud.append((block, True))
            if status:
                self._hud.append((self._text_block([status]), False))
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        h = self.size[1]
        top = self.toolbar()[2] + 8
        bar, tips = self.draw_toolbar()
        self.menu.current = self.exercise
        menu = self.menu.draw()
        blocks = [(10, top if at_top else h - 10 - bh, bw, bh, data) for (bw, bh, data), at_top in self._hud]
        self.panel_ok = self._panel_ok.move(10, top) if self._panel_ok else None  # for clicks, in window pixels
        for x, y, bw, bh, data in bar + blocks + menu + tips:  # (x, y) is the top-left corner
            glWindowPos2i(x, h - y - bh)
            glDrawPixels(bw, bh, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)


if __name__ == "__main__":
    App().run()
