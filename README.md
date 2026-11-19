# Stickman Studio

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

To make a stand-alone Windows program that needs no Python on the other
computer (`dist/Stickman Studio.exe`):

```
pip install pyinstaller
python -m PyInstaller --noconfirm stickman.spec
```

The program's file dialogs start in `Documents\Stickman Poses`.

There is also an Android app, made from the website: see [Android](#android).

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
| Page Up / Page Down, or the arrows to the right of the list | Show the previous / next exercise in the list (wrapping round at the ends) |
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
| B | Show / hide the floor, its grid and the shadows (the grid button) |
| Ctrl+Z, Ctrl+Y | Undo, redo |
| Ctrl+S, Ctrl+O | Save / open a pose (JSON, in `poses/` by default) |
| Ctrl+E or F12 | Export a PNG without the help overlay or highlights |
| Ctrl+C | Copy the figure as editable shapes, for pasting into Word or PowerPoint (Windows) |
| Ctrl+Shift+C | Copy the figure as a 3D model, for pasting into Word or PowerPoint (Windows) |
| Ctrl+Shift+E | Export a 3D model file (`.glb`) |
| N | Add the figure(s) to the current document (see Documents below) |
| V | Show / hide the Document Composer |
| T | Switch language: Greek / English (the flag button) |
| I | Show / hide what Stickman is and how it came about (the i button, at the end of the toolbar beside help and the flag). The OK button closes this box or the help |

## Exercises

The list under the toolbar holds over 150 exercises in ten groups: basic
positions, legs and glutes, push, pull, arms and shoulders, core, cardio and
plyometrics, running drills, stretching and yoga. Click it (or press Tab),
type part of a name or group ("squat", "core") to narrow it down, then pick
one. The figure takes up that position, and the camera turns to the angle that
shows it best. The two arrows to the right of the list (or Page Up / Page
Down) step through the exercises one by one, in the order of the list.

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

## Documents

The Document Composer puts figures together on A4 pages and exports them as a
Word (`.docx`), PowerPoint (`.pptx`) or PDF file: exercise sheets, workout
programmes, handouts.

1. Choose an exercise or pose a figure, and press **Add to Document** (N, the
   page-with-a-plus button). The figure goes into the next place of the
   current document, exactly as it is seen: pose, equipment and camera angle.
   It is a copy, so editing the figure afterwards doesn't change the document.
   The first time, a document is made for it.
2. Repeat for every figure. The same figure can go in more than once.
3. Open the **Document Composer** (V, the page-with-a-grid button) to arrange,
   preview and export. It stays open while you go on posing: on the desktop
   it is a window of its own, on the website a panel at the right (the whole
   screen on a phone).

In the composer:

- **Document settings**: the format to export, A4 portrait or landscape, the
  margins, the grid (1×1 to 4×4, and 1×3, 3×1, 2×5, 3×5; each button shows
  its grid), how figures go in by default, the floor and a transparent
  background for images, and which captions to show (number, name,
  description). Change the grid at any time: the figures flow into it in
  order, and pages are added or removed as needed.
- **The pages** show the document as it will export: the margins, the grid,
  every figure and its caption, page by page. Zoom with − / +, step through
  pages with ◀ ▶. Click a figure to select it; drag it onto another place (on
  any page) to move it there. The others close up in order, left to right and
  top to bottom.
- **The selected figure**: its caption name (the exercise's name to start
  with) and a short description, how it goes in and whether images show the
  floor (or follow the document), ↑ ↓ to move it one place, ⇞ ⇟ to move it to
  the page before or after (these buttons are how to move figures on a touch
  screen), Duplicate, Delete, **Edit in Stickman** (loads the figure into the
  editor) and **Replace with the editor's pose** (puts what is in the editor
  into this figure, keeping its caption and settings). Edit, change the pose,
  Replace: the figure is updated in place.
- **New / Open / Save / Close / Export**. Several documents can be open; the
  list at the top chooses the one Add to Document fills. Save keeps the
  document (a `.json` file with every figure's pose, the settings and the
  captions) to go on editing later, on any of the three versions. Export
  writes the Word, PowerPoint or PDF file. Every exported file also carries
  its document, so opening a `.docx`, `.pptx` or `.pdf` that Stickman made
  (Ctrl+O, or Open in the composer) brings the document back for editing.
  Ctrl+Z / Ctrl+Y (↶ ↷) undo and redo changes to the document.

### How a figure goes in

Each figure can go in one of three ways (the document's choice, or its own):

| | Word (.docx) | PowerPoint (.pptx) | PDF |
|---|---|---|---|
| **Image** | Picture | Picture | Picture |
| **Editable 2D shapes** | Drawing group of native shapes | Group of native shapes | Vector drawing |
| **3D model** | 3D model | 3D model | Picture, with the `.glb` attached |

- **Image**: a 300 dpi picture of the 3D view, sharp when printed at its size
  on the page, with or without the floor, its grid and the shadows, and with a
  transparent or a coloured background.
- **Editable 2D shapes**: every bone is a line, every joint a circle, the
  eyes, nose and equipment are shapes, each named ("Left upper arm", "Left
  elbow", "Bar", ...), in one group. In Word and PowerPoint, ungroup it or
  click into it to recolour, move or delete single parts, as with Ctrl+C. In
  a PDF it is vector drawing: sharp at any zoom, and editable in vector
  programs (Illustrator, Inkscape, Acrobat's Edit PDF). The floor isn't
  drawn in this mode.
- **3D model**: Word and PowerPoint (Microsoft 365, Office 2019 and later)
  get a real 3D model. Drag its round arrow to turn it and look at the pose
  from any side; move and resize it like a picture. Turning the model is not
  editing the pose: the joints can't be moved in Office. To change the pose,
  edit the figure in Stickman (Edit in Stickman, then Replace) and export
  again. Older Office versions and other programs show the picture that comes
  with the model. PDF readers can't be relied on to show 3D (only Adobe
  Acrobat ever did, with formats it has since dropped), so a PDF gets the
  picture, and the model is attached to the PDF as a `.glb` file (the
  paper-clip panel of a PDF reader) for Office or a 3D viewer.

In every case the figure's pose stays in the saved document (and in the
exported file's copy of it), so it can be reopened and edited in Stickman.

Captions are set in Arial in Word and PowerPoint, and in Stickman Sans (the
same letter widths) in the PDF and the preview, so they wrap the same
everywhere. In Word the page is a table per page, one cell per figure; in
PowerPoint every page is an A4 slide; the captions are text you can edit.

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
saves and opens the same pose files. It has the Document Composer too (N, V), as a
panel at the right, with the same documents, preview and exports; Export opens the
browser's save dialog or downloads the file. Copying to Office works differently,
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

On a phone or tablet the toolbar becomes a row of tabs (File, Document, Edit, Drag,
Joint, Figure, View; the same groups, in the same order, as the toolbar on a
computer) with bigger buttons under the open one; undo and redo stay
visible. Pressing a button shows its name.

| Touch | Action |
|---|---|
| Drag a joint | Move it |
| Drag empty space | Orbit the camera |
| Two fingers | Pinch to zoom, move to pan |
| The arrows beside the exercise list | Previous / next exercise |
| Hold a button | Repeat it |
| Document tab | Add the figure to the document; open the Document Composer (full screen; × or the back button closes it) |
| Tap a figure in the composer | Select it; ↑ ↓ ⇞ ⇟ move it |

Ctrl and Shift while dragging are the three Drag buttons here. The smaller
Shift-click steps (5°, 1 cm) aren't available by touch.

## Android

The `android/` folder wraps the website in an Android app. It is the same code
as the website, with Pyodide, numpy and Three.js inside the app, so it works
offline. Building needs the Android SDK (`ANDROID_HOME`) and a JDK 17 or newer;
the libraries are downloaded once, into `android/cache`. With Node.js installed
the build also precompiles numpy, which makes the app start faster.

```
python android/build.py      # -> dist/Stickman Studio.apk
adb install -r "dist/Stickman Studio.apk"
```

That is a debug build, for trying on your own phone. For a release build,
create a signing key and describe it in `android/keystore.properties`
(`storeFile`, `storePassword`, `keyAlias`, `keyPassword`), then run
`python android/build.py --release`. Keep the key and its passwords safe: an
installed app can only be updated by a build signed with the same key.

It works like the website on a phone, except:

- Save and the exports open Android's save dialog.
- The copy button shares the figure as a PNG through Android's share sheet.
  For shapes you can edit in Office, export the `.pptx`.
- The pose and the open documents are kept when Android closes the app in
  the background.
- The back button closes an open list, box or the Document Composer, then
  leaves the app.

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
