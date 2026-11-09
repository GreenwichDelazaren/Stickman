"""Build the Android app: the website (web/build.py) with its libraries, in a WebView.

    python android/build.py             # -> dist/Stickman Poser.apk, a debug build to try on a phone
    python android/build.py --release   # the same, signed with android/keystore.properties

Needs the Android SDK (ANDROID_HOME) and a JDK (17 or newer). The app works offline, so the libraries
the website loads from a CDN go inside it; they are downloaded once, into android/cache.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

ANDROID = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ANDROID)
CACHE = os.path.join(ANDROID, "cache")
GENERATED = os.path.join(ANDROID, "generated")
SITE = os.path.join(GENERATED, "assets", "site")
RES = os.path.join(GENERATED, "res")
OUTPUT = os.path.join(ROOT, "dist", "Stickman Poser.apk")

sys.path.insert(0, ROOT)

THREE_URL = re.compile(r'https://cdn\.jsdelivr\.net/npm/three@[\d.]+/build/three\.module\.js')
PYODIDE_URL = re.compile(r'(https://cdn\.jsdelivr\.net/pyodide/v[\d.]+/full/)pyodide\.mjs')
PYODIDE_FILES = ["pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
ICON_SIZES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}  # an adaptive icon is 108 dp
ICON_FILL = 20 / 27     # of the square, so that the figure is inside the part every phone shows
ICON_FLOOR = 16.2 / 20  # where the floor starts in icons.app_icon


def download(url, sha256=None):
    """The path of url's file in the cache, downloading it the first time."""
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    path = os.path.join(CACHE, digest, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("Downloading", url)
        with urllib.request.urlopen(url) as response, open(path + ".part", "wb") as out:
            shutil.copyfileobj(response, out)
        os.replace(path + ".part", path)
    if sha256:
        with open(path, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        if actual != sha256:
            os.remove(path)
            raise SystemExit(f"{url}: sha256 is {actual}, expected {sha256}")
    return path


def bundle_libraries():
    """Put the CDN's files in the site and point the copied app.js at them."""
    page = os.path.join(SITE, "app.js")
    with open(page, encoding="utf-8") as f:
        code = f.read()
    three = THREE_URL.search(code)
    pyodide = PYODIDE_URL.search(code)
    assert three and pyodide, "the library imports in web/app.js have changed"

    vendor = os.path.join(SITE, "vendor")
    os.makedirs(vendor)
    shutil.copy2(download(three.group(0)), vendor)
    base = pyodide.group(1)
    for name in PYODIDE_FILES:
        shutil.copy2(download(base + name), vendor)
    lock_path = os.path.join(vendor, "pyodide-lock.json")
    with open(lock_path, encoding="utf-8") as f:
        lock = json.load(f)
    numpy = lock["packages"]["numpy"]
    assert not numpy["depends"], "numpy now needs other packages too"
    shutil.copy2(download(base + numpy["file_name"], numpy["sha256"]), vendor)
    if precompile(vendor, numpy["file_name"]):
        with open(os.path.join(vendor, numpy["file_name"]), "rb") as f:
            numpy["sha256"] = hashlib.sha256(f.read()).hexdigest()
        with open(lock_path, "w", encoding="utf-8", newline="") as f:
            json.dump(lock, f)

    code = code.replace(three.group(0), "./vendor/three.module.js").replace(pyodide.group(0), "./vendor/pyodide.mjs")
    with open(page, "w", encoding="utf-8", newline="") as f:
        f.write(code)


def precompile(vendor, wheel):
    """Compile the wheel in the vendor folder, which makes the app start faster. Needs Node; the app
    works without it. True if the wheel changed."""
    if not shutil.which("node"):
        print("Node.js not found: numpy stays uncompiled, and the app takes a few seconds longer to start")
        return False
    subprocess.run(["node", os.path.join(ANDROID, "precompile.mjs"), vendor, wheel], check=True)
    return True


def launcher_icons():
    """The application icon on a full square of its own sky and floor. Android crops a launcher icon to
    a shape that differs by phone, so the picture runs to the edges with the figure well inside."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    import icons
    for density, size in ICON_SIZES.items():
        art = icons.app_icon(round(size * ICON_FILL))
        margin = (size - art.get_width()) // 2
        square = pygame.Surface((size, size), pygame.SRCALPHA)
        square.fill(icons.APP_SKY)
        floor = margin + round(art.get_height() * ICON_FLOOR)
        square.fill(icons.APP_FLOOR, (0, floor, size, size - floor))
        square.blit(art, (margin, margin))
        folder = os.path.join(RES, "mipmap-" + density)
        os.makedirs(folder)
        pygame.image.save(square, os.path.join(folder, "ic_launcher_art.png"))


def gradle(release):
    import scene
    wrapper = os.path.join(ANDROID, "gradlew.bat" if os.name == "nt" else "gradlew")
    task = "assembleRelease" if release else "assembleDebug"
    subprocess.run([wrapper, task, f"-PstickmanVersion={scene.VERSION}"], cwd=ANDROID, check=True)
    kind = "release" if release else "debug"
    return os.path.join(ANDROID, "app", "build", "outputs", "apk", kind, f"app-{kind}.apk")


def build(release):
    if release and not os.path.exists(os.path.join(ANDROID, "keystore.properties")):
        raise SystemExit("A release build needs android/keystore.properties")
    from web import build as website
    website.build()
    if os.path.isdir(GENERATED):
        shutil.rmtree(GENERATED)
    shutil.copytree(website.DIST, SITE)
    bundle_libraries()
    launcher_icons()
    apk = gradle(release)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    shutil.copy2(apk, OUTPUT)
    print(f"Built {OUTPUT}: {os.path.getsize(OUTPUT) / 1e6:.1f} MB")


if __name__ == "__main__":
    build("--release" in sys.argv[1:])
