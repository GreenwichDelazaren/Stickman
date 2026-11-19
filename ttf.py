"""The caption font: what the document layout measures text with and the PDF export embeds.

Stickman Sans (fonts/: Liberation Sans, cut down and renamed as its SIL Open Font License asks) has
the same letter widths as Arial, which Word and
PowerPoint use for the captions, so a caption wraps the same way in the preview, the PDF and Office.
The files are subsets (Latin and Greek) made with fontTools; only the tables needed here are read.

No pygame/OpenGL.
"""

import functools
import os
import struct

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FILES = {False: "StickmanSans-Regular.ttf", True: "StickmanSans-Bold.ttf"}
OFFICE_FONT = "Arial"   # what the Office files name: Liberation Sans's widths
FAMILY = "Stickman Sans"


class Font:
    """A TrueType font's metrics: glyph ids, advance widths and vertical extents."""

    def __init__(self, data, bold=False):
        self.data, self.bold = data, bold
        count = struct.unpack(">H", data[4:6])[0]
        self.tables = {}
        for k in range(count):
            tag, _, offset, length = struct.unpack(">4sIII", data[12 + 16 * k:28 + 16 * k])
            self.tables[tag.decode("latin-1")] = (offset, length)
        head = self._table("head")
        self.units = struct.unpack(">H", head[18:20])[0]
        self.bbox = struct.unpack(">hhhh", head[36:44])
        hhea = self._table("hhea")
        self.ascent, self.descent = struct.unpack(">hh", hhea[4:8])
        metrics = struct.unpack(">H", hhea[34:36])[0]
        hmtx = self._table("hmtx")
        self.advances = [struct.unpack(">H", hmtx[4 * i:4 * i + 2])[0] for i in range(metrics)]
        os2 = self._table("OS/2")
        self.cap_height = struct.unpack(">h", os2[88:90])[0] if len(os2) >= 90 else self.ascent
        self.cmap = self._read_cmap()
        self.name = "StickmanSans-Bold" if bold else "StickmanSans-Regular"

    def _table(self, tag):
        offset, length = self.tables[tag]
        return self.data[offset:offset + length]

    def _read_cmap(self):
        cmap = self._table("cmap")
        count = struct.unpack(">H", cmap[2:4])[0]
        subtables = {}
        for k in range(count):
            platform, encoding, offset = struct.unpack(">HHI", cmap[4 + 8 * k:12 + 8 * k])
            subtables[(platform, encoding)] = offset
        out = {}
        for key in ((3, 10), (0, 4), (3, 1), (0, 3)):
            if key not in subtables:
                continue
            at = subtables[key]
            fmt = struct.unpack(">H", cmap[at:at + 2])[0]
            if fmt == 12:
                groups = struct.unpack(">I", cmap[at + 12:at + 16])[0]
                for g in range(groups):
                    first, last, gid = struct.unpack(">III", cmap[at + 16 + 12 * g:at + 28 + 12 * g])
                    for c in range(first, last + 1):
                        out[c] = gid + c - first
                return out
            if fmt == 4:
                segs = struct.unpack(">H", cmap[at + 6:at + 8])[0] // 2
                ends = struct.unpack(f">{segs}H", cmap[at + 14:at + 14 + 2 * segs])
                base = at + 16 + 2 * segs
                starts = struct.unpack(f">{segs}H", cmap[base:base + 2 * segs])
                deltas = struct.unpack(f">{segs}h", cmap[base + 2 * segs:base + 4 * segs])
                range_at = base + 4 * segs
                offsets = struct.unpack(f">{segs}H", cmap[range_at:range_at + 2 * segs])
                for s in range(segs):
                    for c in range(starts[s], ends[s] + 1):
                        if c == 0xFFFF:
                            continue
                        if offsets[s] == 0:
                            gid = (c + deltas[s]) & 0xFFFF
                        else:
                            p = range_at + 2 * s + offsets[s] + 2 * (c - starts[s])
                            gid = struct.unpack(">H", cmap[p:p + 2])[0]
                            gid = (gid + deltas[s]) & 0xFFFF if gid else 0
                        if gid:
                            out[c] = gid
                return out
        return out

    def glyph(self, char):
        return self.cmap.get(ord(char), self.cmap.get(ord("?"), 0))

    def advance(self, gid):
        return self.advances[min(gid, len(self.advances) - 1)]

    def width(self, text, size):
        """Width of text at size (in the same unit as size, e.g. points)."""
        return sum(self.advance(self.glyph(c)) for c in text) * size / self.units


@functools.lru_cache(maxsize=None)
def font(bold=False):
    with open(os.path.join(FONT_DIR, FILES[bold]), "rb") as f:
        return Font(f.read(), bold)


def wrap(text, width, size, bold=False, max_lines=None):
    """text broken into lines no wider than width at size (same unit), at spaces (or anywhere in a
    word too long for a line), and cut with an ellipsis after max_lines."""
    f, lines = font(bold), []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = word if not line else line + " " + word
            if f.width(trial, size) <= width:
                line = trial
                continue
            if line:
                lines.append(line)
            while f.width(word, size) > width and len(word) > 1:  # a word wider than the line
                cut = len(word) - 1
                while cut > 1 and f.width(word[:cut], size) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and f.width(last + "…", size) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines
