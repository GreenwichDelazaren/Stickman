"""Copy flat 2D drawings to the Windows clipboard as Office shapes.

Office apps exchange shapes through the "Art::GVML ClipFormat" clipboard
format: a small zip package holding a DrawingML locked canvas.  Pasting it
into Word or PowerPoint gives native, editable shapes.  (A 3D model needs no
package: Office pastes a .glb put on the clipboard as "model/gltf-binary".)

Shapes are plain dicts in screen pixels (y down):
  {"kind": "line", "name", "a": (x, y), "b": (x, y), "width", "color"}
  {"kind": "circle", "name", "center": (x, y), "radius", "color", "outline"}
  {"kind": "polygon", "name", "points": [(x, y), ...], "color", "outline"}
  {"kind": "text", "name", "text", "center": (x, y), "width", "height", "angle",
   "size", "font", "bold", "color"}
A text shape is one line centred in a width x height box turned by angle
(degrees, clockwise), with the font size in pixels.  Colours are RGB tuples in
0..1.  Later shapes are drawn on top.
"""

import io
import math
import struct
import sys
import time
import zipfile
from xml.sax.saxutils import escape, quoteattr

GVML_FORMAT = "Art::GVML ClipFormat"
MODEL_FORMAT = "model/gltf-binary"
CF_DIB = 8
EMU_PER_PIXEL = 9525  # at 96 dpi

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/clipboard/drawings/drawing1.xml"'
    ' ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
    '</Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"'
    ' Target="clipboard/drawings/drawing1.xml"/>'
    '</Relationships>'
)


def _emu(px):
    return int(round(px * EMU_PER_PIXEL))


def _hex(color):
    return "".join(f"{int(round(max(0.0, min(1.0, c)) * 255)):02X}" for c in color)


def _fill(color):
    return f'<a:solidFill><a:srgbClr val="{_hex(color)}"/></a:solidFill>'


def _xfrm(x, y, w, h, flip_v=False, angle=0.0):
    flip = ' flipV="1"' if flip_v else ""
    rot = round(angle % 360 * 60000) % 21600000
    if rot:
        flip += f' rot="{rot}"'
    return (f'<a:xfrm{flip}><a:off x="{_emu(x)}" y="{_emu(y)}"/>'
            f'<a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>')


def _bounds(shape):
    if shape["kind"] == "line":
        (ax, ay), (bx, by) = shape["a"], shape["b"]
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    if shape["kind"] == "polygon":
        xs, ys = zip(*shape["points"])
        return min(xs), min(ys), max(xs), max(ys)
    if shape["kind"] == "text":  # the turned box
        (cx, cy), c, s = shape["center"], math.cos(math.radians(shape["angle"])), math.sin(math.radians(shape["angle"]))
        dx = (abs(c) * shape["width"] + abs(s) * shape["height"]) / 2
        dy = (abs(s) * shape["width"] + abs(c) * shape["height"]) / 2
        return cx - dx, cy - dy, cx + dx, cy + dy
    (cx, cy), r = shape["center"], shape["radius"]
    return cx - r, cy - r, cx + r, cy + r


def _shape_xml(shape, shape_id, ox, oy):
    name = quoteattr(shape["name"])
    if shape["kind"] == "line":
        (ax, ay), (bx, by) = shape["a"], shape["b"]
        # A preset line runs from the top-left to the bottom-right corner of
        # its box; flip it for lines that rise to the right.
        flip_v = (bx < ax) != (by < ay)
        x0, y0 = min(ax, bx) - ox, min(ay, by) - oy
        return (f'<a:cxnSp><a:nvCxnSpPr><a:cNvPr id="{shape_id}" name={name}/><a:cNvCxnSpPr/></a:nvCxnSpPr>'
                f'<a:spPr>{_xfrm(x0, y0, abs(bx - ax), abs(by - ay), flip_v)}'
                f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
                f'<a:ln w="{_emu(shape["width"])}" cap="rnd">{_fill(shape["color"])}<a:round/></a:ln>'
                f'</a:spPr></a:cxnSp>')
    if shape["kind"] == "polygon":
        x0, y0, x1, y1 = _bounds(shape)
        w, h = max(1, _emu(x1 - x0)), max(1, _emu(y1 - y0))
        pts = [f'<a:pt x="{_emu(x - x0)}" y="{_emu(y - y0)}"/>' for x, y in shape["points"]]
        path = (f'<a:moveTo>{pts[0]}</a:moveTo>' + "".join(f'<a:lnTo>{p}</a:lnTo>' for p in pts[1:])
                + '<a:close/>')
        return (f'<a:sp><a:nvSpPr><a:cNvPr id="{shape_id}" name={name}/><a:cNvSpPr/></a:nvSpPr>'
                f'<a:spPr>{_xfrm(x0 - ox, y0 - oy, x1 - x0, y1 - y0)}'
                f'<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/>'
                f'<a:pathLst><a:path w="{w}" h="{h}">{path}</a:path></a:pathLst></a:custGeom>'
                f'{_fill(shape["color"])}<a:ln w="{EMU_PER_PIXEL}">{_fill(shape["outline"])}</a:ln>'
                f'</a:spPr></a:sp>')
    if shape["kind"] == "text":
        # The GVML shape keeps its text in txSp, laid out in the shape's own (turned) box.
        (cx, cy), w, h = shape["center"], shape["width"], shape["height"]
        size = max(100, round(shape["size"] * 0.75 * 100))  # hundredths of a point, at 96 dpi
        bold = ' b="1"' if shape.get("bold") else ""
        return (f'<a:sp><a:nvSpPr><a:cNvPr id="{shape_id}" name={name}/><a:cNvSpPr txBox="1"/></a:nvSpPr>'
                f'<a:spPr>{_xfrm(cx - w / 2 - ox, cy - h / 2 - oy, w, h, angle=shape["angle"])}'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></a:spPr>'
                f'<a:txSp><a:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"'
                f' anchorCtr="1"><a:noAutofit/></a:bodyPr><a:lstStyle/>'
                f'<a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="{size}"{bold}>{_fill(shape["color"])}'
                f'<a:latin typeface={quoteattr(shape["font"].capitalize())}/></a:rPr>'
                f'<a:t>{escape(shape["text"])}</a:t></a:r></a:p></a:txBody><a:useSpRect/></a:txSp></a:sp>')
    (cx, cy), r = shape["center"], shape["radius"]
    return (f'<a:sp><a:nvSpPr><a:cNvPr id="{shape_id}" name={name}/><a:cNvSpPr/></a:nvSpPr>'
            f'<a:spPr>{_xfrm(cx - r - ox, cy - r - oy, 2 * r, 2 * r)}'
            f'<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>{_fill(shape["color"])}'
            f'<a:ln w="{EMU_PER_PIXEL}">{_fill(shape["outline"])}</a:ln>'
            f'</a:spPr></a:sp>')


def build_gvml(shapes, group_name="Group"):
    """The shapes as one named group, packaged for the GVML clipboard format."""
    boxes = [_bounds(s) for s in shapes]
    ox, oy = min(b[0] for b in boxes), min(b[1] for b in boxes)
    w = max(b[2] for b in boxes) - ox
    h = max(b[3] for b in boxes) - oy
    box = (f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/>'
           f'<a:chOff x="0" y="0"/><a:chExt cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>')
    body = "".join(_shape_xml(s, i + 2, ox, oy) for i, s in enumerate(shapes))
    drawing = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/lockedCanvas">'
        '<lc:lockedCanvas xmlns:lc="http://schemas.openxmlformats.org/drawingml/2006/lockedCanvas">'
        f'<a:nvGrpSpPr><a:cNvPr id="0" name=""/><a:cNvGrpSpPr/></a:nvGrpSpPr><a:grpSpPr>{box}</a:grpSpPr>'
        f'<a:grpSp><a:nvGrpSpPr><a:cNvPr id="1" name={quoteattr(group_name)}/><a:cNvGrpSpPr/></a:nvGrpSpPr>'
        f'<a:grpSpPr>{box}</a:grpSpPr>{body}</a:grpSp>'
        '</lc:lockedCanvas></a:graphicData></a:graphic>'
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("clipboard/drawings/drawing1.xml", drawing)
    return out.getvalue()


def dib(width, height, rgb):
    """A CF_DIB bitmap from top-down RGB bytes."""
    stride = (width * 3 + 3) & ~3
    rows = [rgb[y * width * 3:(y + 1) * width * 3] for y in range(height)]
    pad = b"\0" * (stride - width * 3)
    pixels = b"".join(bytes(_bgr(row)) + pad for row in reversed(rows))
    header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    return header + pixels


def _bgr(row):
    out = bytearray(row)
    out[0::3], out[2::3] = row[2::3], row[0::3]
    return out


def set_clipboard(formats, hwnd=None):
    """Replace the clipboard contents with {format name or id: bytes}."""
    if sys.platform != "win32":
        raise OSError("copying shapes to the clipboard needs Windows")
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32")
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    gmem_moveable = 0x0002

    for _ in range(10):  # another program may have the clipboard open briefly
        if user32.OpenClipboard(hwnd):
            break
        time.sleep(0.05)
    else:
        raise OSError("the clipboard is in use by another program")
    try:
        user32.EmptyClipboard()
        for fmt, data in formats.items():
            if isinstance(fmt, str):
                fmt = user32.RegisterClipboardFormatW(fmt)
            handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
            ctypes.memmove(kernel32.GlobalLock(handle), data, len(data))
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(fmt, handle):
                kernel32.GlobalFree(handle)
                raise ctypes.WinError(ctypes.get_last_error())
    finally:
        user32.CloseClipboard()
