"""The website's Python side, run in the browser by Pyodide: the editing of main.App without pygame.

web/app.js handles the page (Three.js drawing, toolbar, menu, files, clipboard). It sends input here
(press/move/release, action names for keys and buttons) and draws what frame() returns. Everything
crossing over is a plain value: numbers, strings, bytes or JSON text. Only `app` is used from JS.
"""

import json
import math
import re

import numpy as np

import gltf
import i18n
import office_clip
import props
import scene
import skeleton as sk
import svg
from i18n import tr

# Turn/tip/lean actions: (Skeleton.turn kind, sign), as main.ROTATE_KEYS.
ROTATE = {"turn_left": ("yaw", 1), "turn_right": ("yaw", -1), "tip_forward": ("pitch", 1),
          "tip_back": ("pitch", -1), "lean_left": ("roll", -1), "lean_right": ("roll", 1)}
LIFT = {"move_up": 1, "move_down": -1}
VIEWS = {"view_front": "front", "view_side": "side", "view_top": "top", "view_angled": "angled"}
ZOOM = {"zoom_in": 1, "zoom_out": -1}

HELP = [
    "Tab or the list on the toolbar: pick an exercise (type to search)",
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
    "Ctrl+C copy as a picture (Office: right-click > Convert to Shape)",
    "Ctrl+Shift+S download editable shapes (.pptx)",
    "Ctrl+Shift+E export 3D model (.glb)",
    "T  language: Greek / English (the flag button)",
    "Hold a key or toolbar button to repeat it",
    "Colours: blue = left, red = right, green = pinned",
    "H  hide help",
]
HELP_GREEK = [
    "Tab ή η λίστα στη γραμμή εργαλείων: επιλογή άσκησης (γράψτε για αναζήτηση)",
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
    "Ctrl+C αντιγραφή ως εικόνα (Office: δεξί κλικ > Μετατροπή σε σχήμα)",
    "Ctrl+Shift+S λήψη ως επεξεργάσιμα σχήματα (.pptx)",
    "Ctrl+Shift+E εξαγωγή τρισδιάστατου μοντέλου (.glb)",
    "T  γλώσσα: Ελληνικά / English (το κουμπί με τη σημαία)",
    "Κρατήστε πατημένο ένα πλήκτρο ή κουμπί για επανάληψη",
    "Χρώματα: μπλε = αριστερά, κόκκινο = δεξιά, πράσινο = καρφιτσωμένο",
    "H  απόκρυψη βοήθειας",
]


def _flat(array):
    return [round(float(x), 6) for x in array.ravel()]


class Editor:
    def __init__(self):
        self.size = (1280, 800)
        self.camera = scene.Camera()
        self.figures = [sk.Skeleton()]  # an exercise can show two positions side by side
        self.skel = self.figures[0]     # the figure being edited
        self.exercise = None            # name of the exercise last chosen
        self.props = []                 # the equipment (props.py parts); never changed in place
        self._props_sent = None         # the props frame() last sent
        self.selected = None            # joint index in self.skel
        self.hovered = None             # (figure, joint index)
        self.drag = None                # active joint drag
        self.camera_drag = None         # "orbit" or "pan"
        self.press_pos = (0, 0)
        self.undo_stack, self.redo_stack = [], []
        self.show_help = False
        self.drag_mode = "screen"       # used when no modifier is held
        self.message = ""               # for app.js to show, taken by frame()
        self.tattoo = scene.Tattoo(1, 1, b"")
        self.update_view()

    # --- view ----------------------------------------------------------------

    def update_view(self):
        self.v = scene.View(self.camera, self.size)

    def resize(self, w, h):
        self.size = (max(1, int(w)), max(1, int(h)))
        self.update_view()

    def set_tattoo(self, width, height, png):
        """The tattoo image app.js drew (white text on transparent, as PNG bytes)."""
        self.tattoo = scene.Tattoo(int(width), int(height), bytes(png.to_py() if hasattr(png, "to_py") else png))

    def say(self, text):
        self.message = text

    # --- editing (as main.App) ---------------------------------------------------

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

    def load_exercise(self, exercise):
        figures, self.props = scene.build_exercise(exercise, self.camera, self.size, self.skel.limits_on)
        self.set_figures(figures)
        self.exercise = exercise.name
        self.update_view()

    def load_figures(self, dicts, exercise=None, parts=()):
        figures = [self.new_figure() for _ in dicts]
        for figure, data in zip(figures, dicts):
            figure.from_dict(data)
        self.set_figures(figures)
        self.exercise = exercise
        self.props = list(parts)

    # --- the exercise list ---------------------------------------------------------

    def exercise_rows(self, query):
        """JSON [{"heading"} or {"name", "label", "two"}] of the exercises matching query."""
        rows = []
        for category, e in scene.search_exercises(query):
            if e is None:
                rows.append({"heading": i18n.upper(tr(category))})
            else:
                rows.append({"name": e.name, "label": tr(e.name), "two": len(e.positions) > 1})
        return json.dumps(rows)

    def choose_exercise(self, name):
        exercise = scene.find_exercise(name)
        if exercise is None:
            return
        self.edit(self.load_exercise, exercise)
        if len(exercise.positions) > 1:
            self.say(tr("{}: start position on the left, end position on the right").format(tr(exercise.name)))
        else:
            self.say(tr(exercise.name))

    # --- mouse ---------------------------------------------------------------------

    def press(self, x, y, button, ctrl, shift):
        """A press on the view (button 0 left, 1 middle, 2 right): "drag", "orbit" or "pan"."""
        self.update_view()
        hit = scene.pick(self.figures, self.v, x, y) if button == 0 else None
        self.press_pos = (x, y)
        if hit is not None:
            self.skel, self.selected = hit
            mode = "floor" if ctrl else "vertical" if shift else self.drag_mode
            self.drag = scene.begin_drag(self.skel, self.selected, self.v, self.camera, mode, x, y)
            self.drag.update(before=self.state(), moved=False)
            return "drag"
        self.camera_drag = "pan" if button == 1 or (button == 2 and shift) else "orbit"
        return self.camera_drag

    def move(self, x, y, dx, dy):
        """Mouse motion to (x, y), by (dx, dy) since the last call; True if anything changed."""
        if self.drag:
            target = scene.drag_target(self.drag, self.v, x, y)
            if target is None:
                return False
            if not self.drag["moved"]:
                self.push_undo(self.drag["before"])
                self.drag["moved"] = True
            self.skel.drag(self.drag["joint"], target)
            return True
        if self.camera_drag == "orbit":
            self.camera.orbit(dx, dy)
        elif self.camera_drag == "pan":
            self.camera.pan(dx, dy, self.size[1])
        else:
            return self.hover(x, y)
        self.update_view()
        return True

    def hover(self, x, y):
        """Hover over (x, y), or nothing for x < 0; True if the hovered joint changed."""
        hovered = scene.pick(self.figures, self.v, x, y) if x >= 0 else None
        changed = hovered != self.hovered
        self.hovered = hovered
        return changed

    def release(self, x, y, button):
        if button == 0 and self.drag is None and self.camera_drag and math.dist((x, y), self.press_pos) < 4:
            self.selected = None  # a click on empty space
        self.drag = self.camera_drag = None

    def zoom(self, steps):
        self.camera.zoom(steps)
        self.update_view()

    def set_drag_mode(self, mode):
        self.drag_mode = mode

    # --- keys and toolbar buttons -------------------------------------------------------

    def action(self, name, shift=False):
        """A key or toolbar button, named as the toolbar icon (main.App.on_key without the files)."""
        sel = self.selected
        if name == "undo":
            self.undo()
        elif name == "redo":
            self.redo()
        elif name == "help":
            self.show_help = not self.show_help
        elif name == "language":
            i18n.language = "en" if i18n.language == "el" else "el"
            self.say(tr("Language: English"))
        elif name == "escape":
            self.selected = None
        elif name == "pin":
            if shift:
                self.edit(self.skel.clear_pins)
                self.say(tr("All pins removed"))
            elif sel is None:
                self.say(tr("Click a joint first, then press P to pin it"))
            else:
                self.edit(self.skel.toggle_pin, sel)
        elif name == "mirror":
            side = None if sel is None else self.skel.side(sel)
            if side is None:
                self.say(tr("Select a left or right joint to mirror its side"))
            else:
                self.edit(self.skel.mirror, side)
                self.say(tr({"l": "Copied left side onto the other side",
                             "r": "Copied right side onto the other side"}[side]))
        elif name in ("twist_minus", "twist_plus"):
            if sel is None:
                self.say(tr("Click a joint first, then press Z/X to twist it"))
            else:
                before = self.state()
                step = (5 if shift else 15) * (1 if name == "twist_plus" else -1)
                if self.skel.twist(sel, step):
                    self.push_undo(before)
                else:
                    self.say(tr("This joint can't twist any further"))
        elif name == "limits":
            self.edit(self.set_limits, not self.skel.limits_on)
            if self.skel.limits_on:
                self.say(tr("Joint limits on"))
        elif name in ROTATE:
            kind, sign = ROTATE[name]
            self.edit(self.skel.turn, kind, sign * (5 if shift else 15))
        elif name in LIFT:
            step = LIFT[name] * (0.01 if shift else 0.05)
            self.edit(self.skel.translate, np.array([0.0, step, 0.0]))
        elif name == "ground":
            self.edit(self.skel.drop_to_ground)
        elif name == "reset":
            self.edit(self.reset)
            self.say(tr("Pose reset (Ctrl+Z to undo)"))
        elif name in VIEWS:
            self.camera.yaw, self.camera.pitch = scene.VIEW_ANGLES[VIEWS[name]]
        elif name == "centre":
            lo, hi = scene.figures_bounds(self.figures, self.props)
            self.camera.target = (lo + hi) / 2
        elif name in ZOOM:
            self.camera.zoom(ZOOM[name])
        self.update_view()

    # --- files and exports ---------------------------------------------------------

    def file_name(self):
        """A file name (without extension) for the exports: the exercise's, or "pose"."""
        name = re.sub(r'[\\/:*?"<>|]+', "", tr(self.exercise)).strip() if self.exercise else ""
        return name or "pose"

    def pose_json(self):
        return json.dumps(scene.pose_file(self.figures, self.exercise, self.props), indent=2)

    def open_pose(self, text, name):
        try:
            dicts, exercise, parts = scene.read_pose_file(json.loads(text))
            before = self.state()
            self.load_figures(dicts, exercise, parts)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            self.say(tr("Could not open pose: {}").format(exc))
            return
        self.push_undo(before)
        self.say(tr("Opened {}").format(name))

    def svg(self):
        return svg.build_svg(scene.figure_shapes(self.figures, self.props, self.v, self.tattoo), "Stickman")

    def pptx(self):
        return office_clip.build_pptx(scene.figure_shapes(self.figures, self.props, self.v, self.tattoo), "Stickman")

    def glb(self):
        return gltf.build_glb(scene.model_parts(self.figures, self.props, self.tattoo))

    # --- drawing -------------------------------------------------------------------

    def tr(self, text):
        return tr(text)

    def help_lines(self):
        return "\n".join(HELP_GREEK if i18n.language == "el" else HELP)

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
        return "  |  ".join(parts)

    def _figure(self, skel, clean):
        """What app.js draws of one figure."""
        selected = None if clean or skel is not self.skel else self.selected
        hovered = None if clean or not self.hovered or self.hovered[0] is not skel else self.hovered[1]
        pos = skel.pos
        joints = []
        for i, p in enumerate(pos):
            color, scale = scene.joint_style(skel, i, selected, hovered, clean)
            joints.append(_flat(p) + [float(skel.radii[i] * scale)] + list(color))
        bones = [_flat(pos[parent]) + _flat(pos[child]) + list(scene.SIDE_COLORS[skel.side(child)][0])
                 for parent, child in skel.bones]
        face = [{"positions": _flat(positions), "normals": _flat(normals), "triangles": tris.ravel().tolist(),
                 "color": scene.face_color(skel, color, selected, hovered)}
                for (_, _, color), (positions, normals, tris) in zip(scene.FACE, scene.face_meshes(skel))]
        positions, normals, texcoords, tris = scene.tattoo_mesh(skel, self.tattoo.aspect)
        tattoo = {"positions": _flat(positions), "normals": _flat(normals), "uvs": _flat(texcoords),
                  "triangles": tris.ravel().tolist()}
        return {"joints": joints, "bones": bones, "face": face, "tattoo": tattoo}

    def frame(self, clean=False):
        """JSON of everything app.js draws: camera matrices (column-major, for Three.js), the figures,
        the equipment (only when it changed), the status line and toolbar states. Clean is the look
        of the exports: no highlights."""
        self.update_view()
        v = self.v
        out = {
            "proj": _flat(v.proj.T), "view": _flat(v.view.T), "eye": _flat(v.eye),
            "figures": [self._figure(skel, clean) for skel in self.figures],
            "status": self.status_text(), "message": self.message,
            "help": self.help_lines() if self.show_help else "",
            "active": {"limits": self.skel.limits_on, "help": self.show_help,
                       "pin": self.selected is not None and self.selected in self.skel.pins,
                       "drag_mode": self.drag_mode},
            "exercise": self.exercise, "exercise_label": tr(self.exercise) if self.exercise else "",
            "language": i18n.language,
        }
        self.message = ""
        if self.props is not self._props_sent:
            self._props_sent = self.props
            out["props"] = []
            for part in self.props:
                positions, normals, tris = props.mesh(part)
                out["props"].append({"positions": _flat(positions), "normals": _flat(normals),
                                     "triangles": tris.ravel().tolist()})
        return json.dumps(out)

    def colors(self):
        """JSON of the scene's fixed colours and sizes, for app.js."""
        return json.dumps({"background": scene.BACKGROUND, "floor": scene.FLOOR_COLOR, "grid": scene.GRID_COLOR,
                           "shadow": scene.SHADOW_COLOR, "props": props.COLOR, "light": scene.LIGHT_DIR,
                           "floor_half": scene.FLOOR_HALF, "grid_step": scene.GRID_STEP,
                           "bone_radius": scene.BONE_RADIUS, "tattoo_text": scene.TATTOO_TEXT,
                           "tattoo_font": scene.TATTOO_FONT, "tattoo_pad": scene.TATTOO_PAD})


app = Editor()
