# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```
pip install -r requirements.txt   # pygame, PyOpenGL, numpy
python main.py
```

The website (see below) is built and tried with:

```
python web/build.py    # -> web/dist, the folder to upload; needs pygame for the icons
python web/serve.py    # http://localhost:8000 (python -m http.server serves .js as text/plain on Windows)
```

There is no test suite or linter config. Everything except `main.py` and `icons.py` is free of pygame/OpenGL, so pose logic and the exports can be checked headlessly:

```
python -c "import skeleton as sk; s = sk.Skeleton(); j = s.index['l_hand']; s.drag(j, s.pos[j] + [0, 0.5, 0.3]); print(s.pos[j])"
python -c "import scene, svg; c = scene.Camera(); f, p = scene.build_exercise(scene.find_exercise('Back squat'), c, (1280, 800)); print(svg.build_svg(scene.figure_shapes(f, p, scene.View(c, (1280, 800)), scene.Tattoo(900, 80, b'')))[:200])"
```

## Architecture

A desktop app for posing a 3D stick figure (for illustrating exercises), in Greek (the default) and English, and a static website (`web/`) that runs the same Python modules in the browser. Twelve modules:

- `geometry.py`: vector/rotation helpers (`rotation_between`, `angle_about`, `toward`, `MIRROR`, ...).
- `joint_limits.py`: range of motion data (`RANGE_OF_MOTION`) and the two limit types, `Cone` (ball joint with swing boundary + twist range) and `Hinge` (one-way bend).
- `skeleton.py`: `Skeleton`, which holds the pose and does all kinematics and editing.
- `exercises.py`: the exercise library (`CATEGORIES` of `Exercise(name, positions, view)`), `build(position)` -> `Skeleton`, `equipment(position, skeleton)` -> props parts, and `arrange()` to put several figures (and their equipment) side by side. No pygame/OpenGL.
- `props.py`: the gray equipment (bars, plates, dumbbells, benches, boxes, walls) as parts: closed cylinders and axis-aligned boxes in world coordinates, with their meshes, bounds and JSON form. No pygame/OpenGL.
- `scene.py`: everything about the scene that isn't drawing, shared by the desktop app and the website: the display colours and sizes, `Camera`, `View` (projection, `project`, `mouse_ray` for a window size), `pick`, the drag planes (`begin_drag`, `drag_target`), `search_exercises`, `build_exercise` (positions side by side, framed), `pose_file`/`read_pose_file`, `joint_style`/`face_color` (highlights), the face and tattoo meshes, and the exports `model_parts` (for `gltf.py`) and `figure_shapes` (flat shapes for `office_clip.py` and `svg.py`). The tattoo image comes in as a `Tattoo(width, height, png)`, because only the front ends can render text. No pygame/OpenGL.
- `office_clip.py`: builds the "Art::GVML ClipFormat" package (DrawingML shapes in a locked canvas, the format Office uses to copy shapes) and writes the Windows clipboard via ctypes. `build_pptx` puts the same shapes (as PresentationML `p:` shapes) on a one-slide PowerPoint file cropped to them, for the website. No pygame/OpenGL.
- `svg.py`: the same shape dicts as an SVG image (`build_svg`), for the website's clipboard. No pygame/OpenGL.
- `gltf.py`: meshes spheres and tubes (or takes ready-made meshes, optionally textured) and writes binary glTF (`.glb`). No pygame/OpenGL.
- `i18n.py`: the Greek text. `tr(english)` returns the Greek from `GREEK` while `language == "el"` and the English otherwise, so anything without an entry stays English. Templates are translated before formatting (`tr("Saved {}").format(name)`). Joint/bone names are keyed by `pretty_name` output, with the side adjective in the noun's gender. `upper()` drops accents for Greek capitals; `fold()` is for accent-insensitive search. No pygame/OpenGL.
- `icons.py`: the toolbar icons, drawn with `pygame.draw` on a 20 x 20 grid at 4x size and smoothscaled down (that's the anti-aliasing). `ICONS` maps a name to `(draw function, mirrored, rotation)`; `icon()` is cached.
- `main.py`: `App` (pygame window, fixed-function OpenGL rendering, toolbar, input, undo/redo, file dialogs, clipboard copy) and `ExerciseMenu` (the drop-down list on its own row under the toolbar buttons). It keeps only what needs pygame/OpenGL and calls `scene` for the rest.

### Pose representation (skeleton.py)

- The pose is stored as **rotations, not positions**: `root` (pelvis world position), `rot[0]` (pelvis world orientation), and `rot[i]` for each other bone relative to its parent bone. `_fk()` derives `pos` and `world`. So bone lengths can't drift; never write to `pos` directly.
- A bone is named by the joint at its **far end** (`rot[index["l_elbow"]]` is the upper arm). `RANGE_OF_MOTION` and the saved `rotations` dict use the same convention.
- `part[j]` is the body that carries joint `j`. The pelvis and both hips are one rigid body (`PELVIS_PARTS`), so hips have `part == 0` and no rotation of their own. Code iterating over bones checks `part[i] == i`.
- `JOINTS` lists parents before children; the right side is generated from `_LEFT` by negating x.
- World coordinates are metres: y up, floor at y = 0, figure faces +z in the rest pose, so its **left is +x**.
- Elbows/knees start slightly bent in the rest positions. `Hinge.bind` uses that bend to decide which way the joint bends, so changing those rest coordinates can flip a joint.

### Joint limits

- Limits are written for the **left side only**, in the parent bone's frame. `Skeleton.__init__` binds the left limit to `l_<bone>` and `spec.mirrored()` to `r_<bone>`. A `RANGE_OF_MOTION` entry is treated as sided when its bone name isn't itself a joint name.
- Limit objects follow a small protocol: `mirrored()`, `bind(rest_dir, parent_dir)` returns a bound copy, `clamp(rot)` returns the nearest allowed relative rotation. `Skeleton._limit` applies it only while `limits_on`.

### Dragging / IK

- `DRAG_ANCHOR` maps each joint to the joint that stays fixed when it's dragged. `Skeleton.drag` dispatches: pelvis translates the whole figure, a hip tilts the pelvis (`_tilt_pelvis`), and everything else runs `_solve` on the chain from anchor to the dragged joint.
- `_solve` is cyclic coordinate descent with each step clamped by joint limits. For two-bone limbs ending in a hinge it first sets the elbow/knee bend analytically (`_bend_to_reach`).
- The floor: `drag` (the public entry; `_drag` does the work) and `twist` keep every joint centre at or above `radius - FLOOR_TOLERANCE`, or no lower than it already was if it's below that (`_floor_limits`). `drag` raises the target to the floor so the joint slides along it, then bisects towards the target if another joint (or a pin re-solve) would go under. `translate`, `turn`/`rotate` and the exercise posing helpers aren't held back, so the raise/lower and turn buttons can sink the figure.
- After every edit, `_satisfy_pins` re-solves pinned joints (using their own `DRAG_ANCHOR` chains); pins on pelvis parts are skipped.

### Exercise library (exercises.py)

- A position is a dict of **world directions** for the bones (`body`, `chest`, `arms`, `legs`, `feet`, ...; the module docstring lists every key), not rotations. `build` applies them with the posing helpers in `Skeleton`: `orient` (pelvis from spine and front directions), `aim` (one bone), `aim_limb` (upper + lower bone; it twists the upper bone so the hinge bends the right way, then falls back to `_solve` if a limit got in the way), `shrug`, `rotate` and `level`. Joint limits apply, so a direction out of range silently stops at the limit.
- Sided keys are written for the **left side** and mirrored for the right; `mirrored(position)` swaps sides. `Rel(...)` limbs are given in the trunk's frame (pelvis for legs, upper spine for arms) instead of the world's. Legs without a direction keep their rest pose relative to the pelvis, so a tipped pelvis tips the legs too.
- Every position ends on the floor (`drop_to_ground`) unless it has `hang` (hand height) or `lift`.
- Equipment: a position's `props` lists placement functions (`barbell`, `dumbbells(grip)`, `block(...)`, `lying_bench`, `wall(...)`, ...) that take the built `Skeleton` and return `props.py` parts fitted to its joints (a bar through the hands, a box top touching the feet). They aren't mirrored. Start and end positions that share a bench use `level` with a rise (`("l_toe", "l_hand", 0.5)`) so the support stays the same height. Only objects above the floor are drawn, never the floor itself.
- `view` is the camera (yaw, pitch). `SIDE` looks at the figure's left side, so one-sided moves use the left limbs. Changing exercises was checked by rendering every exercise to contact sheets with `App.load_exercise` + `_capture_image`; do the same after changing poses or limits.

### App (main.py)

- `App.figures` is a list of `Skeleton`s (two when an exercise has start and end positions); `self.skel` is the one being edited, chosen by clicking one of its joints. `self.selected` is a joint index in `self.skel`, `self.hovered` a `(figure, joint)` pair. Keyboard edits act on `self.skel`; L, F and the exports cover all figures; R goes back to one standing figure.
- `App.props` is the equipment of the current exercise, one flat list for all figures. It stays put while the figures are edited, and is replaced (never changed in place, so undo states share it) by choosing an exercise, opening a pose or R (which clears it). It is drawn in `props.COLOR` with shadows, framed by `figures_bounds`, exported as meshes to glTF, and to Office by `prop_shapes`: box sides sorted by their farthest corner (so they go behind what rests on them), thin cylinders as line pieces `PROP_PIECE` long (so a bar sorts in front of or behind the body where it passes), thick ones as their outline plus the end facing the camera.
- Undo/redo stores `App.state()` snapshots: (exercise name, active figure index, `Skeleton.state()` of each figure, props). Discrete edits go through `App.edit(fn, *args)`, which pushes undo before calling. Drags push undo only on the first actual movement, and `twist` only if something moved. New editing operations should follow the same pattern.
- `ExerciseMenu` is drawn with the HUD (cached on its state). `App.toolbar()` lays it out on a row of its own under the buttons (its width depends on the language, so the layout is cached per width and language) and sets `menu.rect`. While open it gets mouse presses, wheel, KEYDOWN and TEXTINPUT first (typing filters by name or category, `scene.search_exercises`); a press outside closes it. Choosing calls `App.choose_exercise`, which calls `scene.build_exercise`: it builds the positions, sets the camera to the exercise's view, `arrange`s the figures left to right along the screen and frames them.
- Mouse motion during a joint drag is coalesced: the latest position is stored in `self.drag["mouse"]` and solved once per frame in `run()`.
- The face (`scene.FACE`: two eyes and a triangle nose) is flat shapes wrapped onto the head sphere by `scene.face_meshes()`, lifted `FACE_LIFT` above it. It belongs to the head joint: clicking it picks the head, and it darkens to gold when the head is selected. The 3D export gets it as meshes and the Office copy as freeform polygons, only when it faces the camera.
- The tattoo (`scene.TATTOO_TEXT`, white) is a texture (`main.tattoo_image()`; the website draws it on a canvas) on a strip wrapped round the left forearm by `scene.tattoo_mesh()`, halfway between elbow and wrist, reading from the wrist towards the elbow. It's drawn without writing depth, so its transparent parts hide nothing. The 3D export gets it as a textured mesh (`texcoords` + PNG `image`, alpha blended) and the Office copy as a turned text box (the `text` shape, a GVML `txSp`), only when it faces the camera.
- The info button (I, first on the toolbar) shows `scene.ABOUT`, paragraphs translated with `tr()`; the desktop wraps them to the window (`App.info_lines`), the website gets them in `frame()["info"]`. Help and info replace each other.
- The HUD is rendered to a pygame surface and blitted with `glDrawPixels`. It is cached on `(show_help, show_info, status, language, window width)`. `render(clean=True)` omits the HUD and highlights for PNG export.
- Save/open/export use tkinter dialogs defaulting to `poses/`.
- Ctrl+C (`copy_to_clipboard`) puts GVML shapes plus PNG and CF_DIB fallbacks on the clipboard. `scene.figure_shapes()` projects the figure with `View.project()` and sorts far to near (painter's order), keeping each joint above the bones that end at it. Word accepts the package as one group of native shapes; it was checked by pasting through Word's COM interface (`Word.Application`, `Selection.Paste()`, `Shapes(1).GroupItems.Count`).
- Ctrl+Shift+C puts a `.glb` on the clipboard as `model/gltf-binary`, which Word and PowerPoint paste as a 3D model (Word: inline shape type 19). Office always shows a pasted model from its front (+z), so the copy rotates the vertices by the view matrix; the `.glb` file export (Ctrl+Shift+E) stays in world coordinates. glTF colours are linear, so `build_glb` converts the sRGB display colours. A GVML package with an `am3d:model3d` frame and its own camera also works, but Word always places it at the page corner, so it isn't used.
- Language: the code and saved files stay English (exercise names in JSON and undo states are the English names); text is translated where it's drawn or `say()`d. `T` / the `language` toolbar button toggles `i18n.language`, and the button shows `flag_el` or `flag_en` (drawn in colour at `TOOL_SIZE - 4`). The HUD, toolbar and menu caches include the language in their keys; the menu's width is computed per language. `HELP_GREEK` is the Greek help overlay.
- The toolbar (`TOOLBAR`) buttons are square icons with the name in the tooltip. Each maps to a `(key, modifiers)` pair and clicking calls `on_key`, so a button always does exactly what its shortcut does. The drag-mode buttons are the exception and set `drag_mode`. The layout wraps whole groups onto new rows and is cached per window width; the image is cached on hover/pressed/active state.
- Auto-repeat is done by the app, not SDL: `self.held` remembers the key or button and `repeat_held()` in `run()` re-sends it. Only keys in `REPEAT_KEYS` (or `REPEAT_CTRL_KEYS` with Ctrl) repeat, so dialogs and toggles never repeat. `_after_dialog` clears the held state, because the dialog swallows the key/mouse release.

### Save format

`Skeleton.to_dict()` writes `version: 2` JSON with `joints` (positions, informational), `pinned`, `root` and `rotations`. `from_dict` loads `rotations` when present (re-orthonormalized and clamped to limits). Otherwise it falls back to `_fit_positions` for older position-only files. Keep that fallback working when changing the format.

A single figure is saved as exactly that dict. Several figures are saved as `{"version": 2, "figures": [dict, ...]}`. Either form may also carry `"exercise"` (the name shown in the list) and `"props"` (a list of `props.to_dict` parts). `App.open_pose` accepts both.

### Website (web/)

- A static site: `web/build.py` copies `index.html`, `style.css`, `app.js`, the shared modules (its `SHARED` list) and `bridge.py` into `web/dist` (with `py/files.json` listing the modules) and renders every `icons.ICONS` icon to `icons/<name>.png` at 2x. Pyodide (with numpy) and Three.js are loaded from jsDelivr at pinned versions. Nothing runs on the server.
- `bridge.py` is `main.App` without pygame: the same state, undo/redo, `edit` pattern and key actions, named after the toolbar icons (`app.action("turn_left", shift)`). `app.js` only draws and forwards input; keep the editing logic in Python. Things both front ends need go in `scene.py`, not in a copy.
- `app.js` sends `press`/`move`/`release`/`hover`/`zoom` with CSS pixel coordinates; mouse motion is coalesced to one `move` per animation frame, as in `App.run`. After any change it calls `frame()`, which returns JSON: the camera matrices (column-major, set directly on the Three.js camera so picking and drawing use the same projection), each figure's joints/bones/face/tattoo, the equipment meshes only when `props` is a new list, the status line, toolbar states and a message (shown for 4 s by `app.js`).
- The drawing copies the desktop's OpenGL: colour management off (lighting on the sRGB values), ambient 0.5 and diffuse 0.75 (times pi for Three.js's lights), the floor and flattened shadows only when the camera is above the floor, the tattoo without depth writes.
- Files: save/export use `showSaveFilePicker` where the browser has it, else a download; open uses a file input. Pose files are the same format as the desktop's.
- Clipboard: a browser can only write standard types, not GVML or `model/gltf-binary`. Ctrl+C writes `image/svg+xml` (`svg.build_svg`, where `ClipboardItem.supports` says so) and `image/png`. Word and PowerPoint paste the SVG as a vector graphic (Word inline shape type 17, PowerPoint shape type 28), and Convert to Shape (`CommandBars.ExecuteMso("SVGEdit")`) turns it into editable shapes; this was checked by copying from a visible Edge window (Playwright) and pasting through COM. Ctrl+Shift+S downloads the exact shapes as a `.pptx`; Ctrl+Shift+C only explains that 3D models can't be copied. The clipboard needs https (or localhost).
- `window.stickman = {py, app}` is there for testing from the console or Playwright.

## Keeping docs in sync

The controls are listed in four places for the desktop: the key handling in `App.on_key`/`App.handle`, the `TOOLBAR` buttons and `HELP` / `HELP_GREEK` overlay lines in `main.py`, and the controls table in `README.md`. The website has its own copies: `TOOLBAR` and `KEYS` in `web/app.js`, `Editor.action` and `HELP` / `HELP_GREEK` in `web/bridge.py`, and the Website section of `README.md`. Update all of them together. (The exercise list is the one control that isn't a toolbar button.)

New user-visible text goes through `tr()` with a Greek entry in `i18n.GREEK` (new tooltips and messages too). For exercise names, add a Greek name only when there's an established Greek term; otherwise leave it out and it shows in English.
