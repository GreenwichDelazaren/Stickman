"""The Document Composer's buttons and fields, shared by the desktop (main.App) and the website
(web/bridge.Editor), so both do exactly the same thing.

`app` is either front end: it has composer (a composer.Composer), the editor's figures, exercise,
props and camera, edit(fn, *args), load_figures(dicts, exercise, parts) and say(text).

No pygame/OpenGL.
"""

import json

import composer
import doc_export
import scene
from i18n import tr


def composer_action(app, name, arg=None):
    """Do the composer action name with its argument; returns a message for the status line ("" for none)."""
    c, doc = app.composer, app.composer.doc
    try:
        if name == "new":
            c.new(arg or None)
        elif name == "choose":
            c.choose(int(arg))
        elif name == "close":
            c.close()
        elif name == "add":
            if doc is None:
                doc = c.new()
            n = doc.add(composer.make_entry(app.figures, app.exercise, app.props, app.camera))
            return tr("Added as figure {} of {}").format(n + 1, doc.name)
        elif doc is None:
            return ""
        elif name == "set":
            doc.set(arg[0], arg[1])
        elif name == "layout":
            doc.set_layout(int(arg[0]), int(arg[1]))
        elif name == "rename":
            doc.name = str(arg).strip() or doc.name
        elif name == "select":
            doc.selected = arg if arg is None or 0 <= int(arg) < len(doc.entries) else doc.selected
        elif name == "entry":
            doc.set_entry(doc.selected, arg[0], arg[1])
        elif name == "move":     # to an index (drag and drop)
            doc.move(doc.selected, int(arg))
        elif name == "step":     # earlier / later by a number of places
            i = doc._index(doc.selected)
            doc.move(i, i + int(arg))
        elif name == "page":     # the same place on the page before / after
            i = doc._index(doc.selected)
            doc.move(i, i + int(arg) * doc.capacity)
        elif name == "duplicate":
            doc.duplicate(doc.selected)
        elif name == "delete":
            doc.delete(doc.selected)
        elif name == "replace":
            doc.replace(doc.selected, composer.make_entry(app.figures, app.exercise, app.props, app.camera))
            return tr("Figure {} now shows the editor's pose").format(doc.selected + 1)
        elif name == "edit":
            entry = doc.entries[doc._index(doc.selected)]
            dicts, exercise, parts = scene.read_pose_file(entry["pose"])
            app.edit(app.load_figures, dicts, exercise, parts)
            cam = composer.entry_camera(entry)
            app.camera.yaw, app.camera.pitch, app.camera.dist = cam.yaw, cam.pitch, cam.dist
            app.camera.target = cam.target
            return tr("Editing figure {}: change the pose, then press Replace with the editor's pose").format(
                doc.selected + 1)
        elif name == "undo":
            doc.undo()
        elif name == "redo":
            doc.redo()
    except IndexError as exc:
        return str(exc)
    return ""


def open_any(app, raw, name):
    """A file chosen with Open: a pose, a document, or a file Stickman exported (which carries its
    document). Loads it and returns "pose" or "doc", or "" with a message if it can't be read."""
    parsed = doc_export.read_exported(raw)
    if parsed is None:
        try:
            parsed = json.loads(bytes(raw).decode("utf-8"))
        except ValueError as exc:
            app.say(tr("Could not open pose: {}").format(exc))
            return ""
    if isinstance(parsed, dict) and parsed.get("kind") == composer.KIND:
        try:
            app.composer.open(parsed)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            app.say(tr("Could not open the document: {}").format(exc))
            return ""
        app.say(tr("Opened {}").format(name))
        return "doc"
    try:
        dicts, exercise, parts = scene.read_pose_file(parsed)
        before = app.state()
        app.load_figures(dicts, exercise, parts)
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        app.say(tr("Could not open pose: {}").format(exc))
        return ""
    app.push_undo(before)
    app.say(tr("Opened {}").format(name))
    return "pose"
