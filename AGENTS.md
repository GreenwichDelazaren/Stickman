# AGENTS.md

This file provides guidance to Codex (claude.ai/code) when working with code in this repository.

## Running

```
pip install -r requirements.txt   # pygame, PyOpenGL, numpy
python main.py
```

There is no test suite, linter config or build step. `skeleton.py`, `joint_limits.py`, `geometry.py` and `exercises.py` don't depend on pygame/OpenGL, so pose logic can be checked headlessly:

```
python -c "import skeleton as sk; s = sk.Skeleton(); j = s.index['l_hand']; s.drag(j, s.pos[j] + [0, 0.5, 0.3]); print(s.pos[j])"
```

## Architecture

A desktop app for posing a 3D stick figure (for illustrating exercises), in Greek (the default) and English. Nine modules:

- `geometry.py`: vector/rotation helpers (`rotation_between`, `angle_about`, `toward`, `MIRROR`, ...).
- `joint_limits.py`: range of motion data (`RANGE_OF_MOTION`) and the two limit types, `Cone` (ball joint with swing boundary + twist range) and `Hinge` (one-way bend).
- `skeleton.py`: `Skeleton`, which holds the pose and does all kinematics and editing.
- `exercises.py`: the exercise library (`CATEGORIES` of `Exercise(name, positions, view)`), `build(position)` -> `Skeleton`, and `arrange()` to put several figures side by side. No pygame/OpenGL.
- `office_clip.py`: builds the "Art::GVML ClipFormat" package (DrawingML shapes in a locked canvas, the format Office uses to copy shapes) and writes the Windows clipboard via ctypes. No pygame/OpenGL.
- `gltf.py`: meshes spheres and tubes (or takes ready-made meshes, optionally textured) and writes binary glTF (`.glb`). No pygame/OpenGL.
- `i18n.py`: the Greek text. `tr(english)` returns the Greek from `GREEK` while `language == "el"` and the English otherwise, so anything without an entry stays English. Templates are translated before formatting (`tr("Saved {}").format(name)`). Joint/bone names are keyed by `pretty_name` output, with the side adjective in the noun's gender. `upper()` drops accents for Greek capitals; `fold()` is for accent-insensitive search. No pygame/OpenGL.
- `icons.py`: the toolbar icons, drawn with `pygame.draw` on a 20 x 20 grid at 4x size and smoothscaled down (that's the anti-aliasing). `ICONS` maps a name to `(draw function, mirrored, rotation)`; `icon()` is cached.
- `main.py`: `App` (pygame window, fixed-function OpenGL rendering, toolbar, input, undo/redo, file dialogs, clipboard copy), `ExerciseMenu` (the drop-down list at the start of the toolbar) and `Camera`.

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
- `view` is the camera (yaw, pitch). `SIDE` looks at the figure's left side, so one-sided moves use the left limbs. Changing exercises was checked by rendering every exercise to contact sheets with `App.load_exercise` + `_capture_image`; do the same after changing poses or limits.

### App (main.py)

- `App.figures` is a list of `Skeleton`s (two when an exercise has start and end positions); `self.skel` is the one being edited, chosen by clicking one of its joints. `self.selected` is a joint index in `self.skel`, `self.hovered` a `(figure, joint)` pair. Keyboard edits act on `self.skel`; L, F and the exports cover all figures; R goes back to one standing figure.
- Undo/redo stores `App.state()` snapshots: (exercise name, active figure index, `Skeleton.state()` of each figure). Discrete edits go through `App.edit(fn, *args)`, which pushes undo before calling. Drags push undo only on the first actual movement, and `twist` only if something moved. New editing operations should follow the same pattern.
- `ExerciseMenu` is drawn with the HUD (cached on its state). `App.toolbar()` lays it out as the first item of the toolbar (its width depends on the language, so the layout is cached per width and language) and sets `menu.rect`. While open it gets mouse presses, wheel, KEYDOWN and TEXTINPUT first (typing filters by name or category); a press outside closes it. Choosing calls `App.choose_exercise`, which builds the positions, sets the camera to the exercise's view, `arrange`s the figures left to right along the screen and `frame_figures`.
- Mouse motion during a joint drag is coalesced: the latest position is stored in `self.drag["mouse"]` and solved once per frame in `run()`.
- The face (`FACE`: two eyes and a triangle nose) is flat shapes wrapped onto the head sphere by `face_meshes()`, lifted `FACE_LIFT` above it. It belongs to the head joint: clicking it picks the head, and it darkens to gold when the head is selected. The 3D export gets it as meshes and the Office copy as freeform polygons, only when it faces the camera.
- The tattoo (`TATTOO_TEXT`, white) is a texture (`tattoo_image()`) on a strip wrapped round the left forearm by `tattoo_mesh()`, halfway between elbow and wrist, reading from the wrist towards the elbow. It's drawn without writing depth, so its transparent parts hide nothing. The 3D export gets it as a textured mesh (`texcoords` + PNG `image`, alpha blended) and the Office copy as a turned text box (the `text` shape, a GVML `txSp`), only when it faces the camera.
- The HUD is rendered to a pygame surface and blitted with `glDrawPixels`. It is cached on `(show_help, status)`. `render(clean=True)` omits the HUD and highlights for PNG export.
- Save/open/export use tkinter dialogs defaulting to `poses/`.
- Ctrl+C (`copy_to_clipboard`) puts GVML shapes plus PNG and CF_DIB fallbacks on the clipboard. `figure_shapes()` projects the figure with `project()` and sorts far to near (painter's order), keeping each joint above the bones that end at it. Word accepts the package as one group of native shapes; it was checked by pasting through Word's COM interface (`Word.Application`, `Selection.Paste()`, `Shapes(1).GroupItems.Count`).
- Ctrl+Shift+C puts a `.glb` on the clipboard as `model/gltf-binary`, which Word and PowerPoint paste as a 3D model (Word: inline shape type 19). Office always shows a pasted model from its front (+z), so the copy rotates the vertices by the view matrix; the `.glb` file export (Ctrl+Shift+E) stays in world coordinates. glTF colours are linear, so `build_glb` converts the sRGB display colours. A GVML package with an `am3d:model3d` frame and its own camera also works, but Word always places it at the page corner, so it isn't used.
- Language: the code and saved files stay English (exercise names in JSON and undo states are the English names); text is translated where it's drawn or `say()`d. `T` / the `language` toolbar button toggles `i18n.language`, and the button shows `flag_el` or `flag_en` (drawn in colour at `TOOL_SIZE - 4`). The HUD, toolbar and menu caches include the language in their keys; the menu's width is computed per language. `HELP_GREEK` is the Greek help overlay.
- The toolbar (`TOOLBAR`) buttons are square icons with the name in the tooltip. Each maps to a `(key, modifiers)` pair and clicking calls `on_key`, so a button always does exactly what its shortcut does. The drag-mode buttons are the exception and set `drag_mode`. The layout wraps whole groups onto new rows and is cached per window width; the image is cached on hover/pressed/active state.
- Auto-repeat is done by the app, not SDL: `self.held` remembers the key or button and `repeat_held()` in `run()` re-sends it. Only keys in `REPEAT_KEYS` (or `REPEAT_CTRL_KEYS` with Ctrl) repeat, so dialogs and toggles never repeat. `_after_dialog` clears the held state, because the dialog swallows the key/mouse release.

### Save format

`Skeleton.to_dict()` writes `version: 2` JSON with `joints` (positions, informational), `pinned`, `root` and `rotations`. `from_dict` loads `rotations` when present (re-orthonormalized and clamped to limits). Otherwise it falls back to `_fit_positions` for older position-only files. Keep that fallback working when changing the format.

A single figure is saved as exactly that dict. Several figures are saved as `{"version": 2, "figures": [dict, ...]}`. Either form may also carry `"exercise"` (the name shown in the list). `App.open_pose` accepts both.

## Keeping docs in sync

The controls are listed in four places: the key handling in `App.on_key`/`App.handle`, the `TOOLBAR` buttons and `HELP` / `HELP_GREEK` overlay lines in `main.py`, and the controls table in `README.md`. Update all of them together. (The exercise list is the one control that isn't a toolbar button.)

New user-visible text goes through `tr()` with a Greek entry in `i18n.GREEK` (new tooltips and messages too). For exercise names, add a Greek name only when there's an established Greek term; otherwise leave it out and it shows in English.
