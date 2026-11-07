"""Build the website into web/dist: the page, the shared Python modules and the toolbar icons.

    python web/build.py

Upload everything in web/dist to any static web host (https, for copying to the clipboard). To try it
locally:  python web/serve.py  and open http://localhost:8000.
Needs pygame, only to draw the toolbar icons (icons.py).
"""

import hashlib
import json
import os
import shutil
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WEB)
DIST = os.path.join(WEB, "dist")

# The modules the website runs, shared with the desktop app (none of them uses pygame or OpenGL).
SHARED = ["geometry.py", "joint_limits.py", "skeleton.py", "exercises.py", "props.py", "gltf.py", "i18n.py",
          "office_clip.py", "svg.py", "scene.py"]
PAGE = ["index.html", "style.css", "app.js"]
ICON_COLOR = (235, 238, 242)  # main.TOOL_COLORS["icon"]
ICON_SIZE, FLAG_SIZE, SCALE = 20, 26, 2  # main.TOOL_ICON, TOOL_SIZE - 4; drawn at 2x for sharp screens


def build():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "py"))
    os.makedirs(os.path.join(DIST, "icons"))
    for name in PAGE:
        shutil.copy2(os.path.join(WEB, name), DIST)
    modules = SHARED + ["bridge.py"]
    for name in modules:
        shutil.copy2(os.path.join(WEB if name == "bridge.py" else ROOT, name), os.path.join(DIST, "py"))
    with open(os.path.join(DIST, "py", "files.json"), "w", encoding="utf-8") as f:
        json.dump(modules, f)

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, ROOT)
    import pygame

    import icons
    for name in icons.ICONS:
        size = FLAG_SIZE if name.startswith("flag_") else ICON_SIZE
        pygame.image.save(icons.icon(name, size * SCALE, ICON_COLOR), os.path.join(DIST, "icons", name + ".png"))
    version = stamp()
    print(f"Built {DIST}: {len(modules)} Python modules, {len(icons.ICONS)} icons, version {version}")


def stamp():
    """Put ?v=<hash of the build> on style.css and app.js in index.html; app.js puts the same on the
    modules and icons it loads (V). Web hosts let browsers keep files for a while (GitHub Pages: 10
    minutes), and without it a browser could run a new app.js with old modules."""
    digest = hashlib.sha256()
    for folder, dirs, names in sorted(os.walk(DIST)):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(folder, name)
            if path != os.path.join(DIST, "index.html"):
                digest.update(os.path.relpath(path, DIST).replace(os.sep, "/").encode() + b"\0")
                with open(path, "rb") as f:
                    digest.update(f.read())
    version = digest.hexdigest()[:10]
    page = os.path.join(DIST, "index.html")
    with open(page, encoding="utf-8") as f:
        html = f.read()
    for ref in ('href="style.css"', 'src="app.js"'):
        assert ref in html, ref
        html = html.replace(ref, ref[:-1] + f'?v={version}"')
    with open(page, "w", encoding="utf-8", newline="") as f:
        f.write(html)
    return version


if __name__ == "__main__":
    build()
