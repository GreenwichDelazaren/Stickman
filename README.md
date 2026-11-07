# Stickman Poser

Pose a 3D stick figure standing on a floor to illustrate exercises
(pull-ups, push-ups, lunges, ...). Drag any joint with the mouse; bone lengths
always stay the same. Or start from one of over 150 ready-made exercises in
the list under the toolbar.

The app starts in Greek. The flag button at the end of the toolbar (or T)
switches between Greek and English; it shows the flag of the current language.
Exercise names without an established Greek term stay in English, and the
exercise search matches both languages, with or without accents.

```
pip install -r requirements.txt
python main.py
```

The same app also runs as a website, with the same exercises, posing and
files: try it at https://greenwichdelazaren.github.io/Stickman/ or see
[Website](#website) below.

## Controls

Every action is on the toolbar at the top of the window (hover over a button
to see what it does and its shortcut), and also has a keyboard shortcut.
Holding down a key or toolbar button for turning, tipping, leaning, raising,
lowering, twisting, zooming, undo or redo repeats it; Shift-click a turn or
twist button for 5° steps, or a raise/lower button for 1 cm steps. The three drag-mode buttons (screen, floor, up/down) choose how a joint
drag moves; holding Ctrl or Shift while dragging overrides that choice.

| Input | Action |
|---|---|
| Tab, or click the list under the toolbar | Choose an exercise: type to search, Up/Down and Enter or click to pick, Esc to close |
| Left-drag a joint | Move it parallel to the screen |
| Ctrl + left-drag | Move it parallel to the floor |
| Shift + left-drag | Move it straight up/down |
| Left-drag empty space / right-drag | Orbit camera |
| Middle-drag / Shift + right-drag | Pan |
| Mouse wheel, + / - | Zoom |
| P / Shift+P | Pin or unpin the selected joint / unpin all |
| M | Mirror the selected joint's side (left or right) onto the other side |
| Z / X | Twist the selected joint: turn the head, twist the torso, rotate the upper arm or thigh; on a hand or ankle, swing the elbow or knee around while the hand or foot stays put |
| L | Realistic joint limits on / off |
| Q/E, W/S, A/D | Turn, tip forward/back, lean the whole figure (Shift: 5° steps) |
| Up / Down arrow | Raise / lower the whole figure by 5 cm (Shift: 1 cm) |
| G | Put the figure on the floor |
| R | Reset to a single figure in the standing pose |
| 1 2 3 4 / F | Front, side, top, angled view / centre on figure |
| Ctrl+Z, Ctrl+Y | Undo, redo |
| Ctrl+S, Ctrl+O | Save / open a pose (JSON, in `poses/` by default) |
| Ctrl+E or F12 | Export a PNG without the help overlay or highlights |
| Ctrl+C | Copy the figure as editable shapes, for pasting into Word or PowerPoint (Windows) |
| Ctrl+Shift+C | Copy the figure as a 3D model, for pasting into Word or PowerPoint (Windows) |
| Ctrl+Shift+E | Export a 3D model file (`.glb`) |
| T | Switch language: Greek / English (the flag button) |
| I | Show / hide what Stickman is and how it came about (the i button, first on the toolbar). The OK button closes this box or the help |

## Exercises

The list under the toolbar holds over 150 exercises in ten groups: basic
positions, legs and glutes, push, pull, arms and shoulders, core, cardio and
plyometrics, running drills, stretching and yoga. Click it (or press Tab),
type part of a name or group ("squat", "core") to narrow it down, then pick
one. The figure takes up that position, and the camera turns to the angle that
shows it best.

Exercises that need a start and an end position ("2 positions" in the list)
show two figures side by side: the start on the left, the end on the right.
Both can be edited. Clicking a joint selects that figure, and the keys (turn,
pin, mirror, ...) act on the selected figure. Save, export and copy include
both figures; R goes back to a single standing figure.

Exercises that use equipment show it as simple gray shapes, fitted to the
pose: a bar on two posts for pull-ups, parallel bars for dips, a barbell or
dumbbells in the hands, a bench, box, chair or wall. The floor itself isn't
drawn as equipment. The equipment stays where it is while you edit the
figure, and it is included when you save, export or copy. The positions are
defined in `exercises.py` as directions of the body parts, so they are easy to
adjust or add to.

## Pasting into Word

Ctrl+C copies the figure as seen from the current camera, as a group of flat
Office shapes: a line for each bone and a circle for each joint, named
"Left upper arm", "Left elbow" and so on (with two figures, "Figure 1: Left
upper arm" and so on). Equipment comes as gray shapes named "Bar", "Bench"
and so on; long bars are cut into short pieces so they pass correctly in
front of or behind the body. In Word or PowerPoint, paste with
Ctrl+V. You can then:

- move or resize the whole figure as one object,
- ungroup it (right-click → Group → Ungroup) to recolour, thicken or move
  single parts,
- use Home → Select → Selection Pane to find a part by name.

Line widths don't change when you resize the group, so set the size first and
adjust line weights afterwards if needed. Other programs (Paint, email) get a
plain picture of the view instead.

### As a 3D model

Ctrl+Shift+C copies the figure as a 3D model instead. Pasted into Word or
PowerPoint (Microsoft 365 or Office 2019 and later), it sits in the text like
a picture and starts out showing the current camera view. Drag the round arrow
in its middle to turn it in 3D, or use the 3D Model tab (Format pane →
3D Model Rotation) for exact angles. The pose itself can't be changed in Word,
and older Word versions show a still picture.

Ctrl+Shift+E saves the same model as a `.glb` file, upright and facing the
front, for Insert → 3D Models → This Device in Office or for other 3D
programs.

## Website

The `web/` folder turns the app into a website that needs no installation:
it runs the same Python code (posing, joint limits, exercises, exports) in the
browser. Build it and try it locally:

```
python web/build.py
python web/serve.py      # then open http://localhost:8000
```

To publish it, upload everything in `web/dist` to any web host that serves
static files (your own server, GitHub Pages, Netlify, ...). Use an `https://`
address, which browsers need for copying to the clipboard. The page loads its
Python runtime (Pyodide) and 3D library (Three.js) from the jsDelivr CDN, so
the first visit downloads roughly 10–15 MB, which the browser then caches.

The website has the same toolbar, keys, help (H), info (I) and languages as the app, and
saves and opens the same pose files. Copying to Office works differently,
because a web page can only put pictures on the clipboard, not Office shapes
or 3D models:

| Input | Action on the website |
|---|---|
| Ctrl+C | Copy the figure as a vector picture (SVG, with a PNG for other programs). In Word or PowerPoint, paste it, then right-click → Convert to Shape to get editable shapes |
| Ctrl+Shift+S | Download the figure as editable shapes in a `.pptx`, exactly as the app's Ctrl+C makes them; open it and copy the group from there |
| Ctrl+Shift+E | Download the 3D model (`.glb`), for Insert → 3D Models → This Device |
| Ctrl+Shift+C | Not available: browsers can't copy 3D models (use Ctrl+Shift+E) |

Ctrl+S, Ctrl+E and Ctrl+Shift+E open the browser's save dialog where it has
one (Chrome, Edge) and download the file otherwise. The SVG copy needs a
recent Chrome or Edge; other browsers copy the PNG only.

## How dragging works

Each joint has an anchor that stays fixed while you drag it (see
`DRAG_ANCHOR` in `skeleton.py`): a hand bends the elbow around a fixed
shoulder, an ankle bends the knee around a fixed hip, the neck bends the spine
over the pelvis, a hip tilts the pelvis, and the pelvis moves the whole figure. Everything below the
dragged joint turns with it.

Dragging or twisting never pushes a joint through the floor: a joint dragged
down slides along the floor, and the drag stops when another joint touches it.
The raise/lower and turn/tip/lean buttons (and their keys) aren't held back,
so they can move the whole figure below the floor; after that, dragging can
still raise a joint that is below the floor but not push it further down.

Each joint stays within a realistic range of motion. Elbows and knees bend one
way only (0-150°). The shoulders can raise the arm overhead or across the
chest, but can reach only a little behind or across the body when the arm is
lowered. The hips, spine, neck, collarbones and ankles each have their own
range and twist limits. If you drag a joint further than it can go, it stops at
the limit. The ranges are listed in degrees in `joint_limits.py` and are easy
to adjust. Press L to switch the limits off for unusual poses; switching them
back on brings the pose back within range.

Pinned joints (green) stay where they are while you move the rest of the body.
For example, pin both hands and both feet, then drag the pelvis to set up a
push-up or plank. If a pinned joint can't be reached, the limb stretches
towards it as far as it can.

Tip: to lay the figure down (push-ups, planks), press W a few times to tip it
over, then G to put it on the floor.
