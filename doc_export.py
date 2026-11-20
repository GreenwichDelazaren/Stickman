"""The Document Composer's exports: a composer.Document as Word (.docx), PowerPoint (.pptx) or PDF.

Every format places the same composer.layout() geometry. A figure goes in as
  "image":  a PNG the front end rendered (render_jobs);
  "shapes": native shapes, one named shape per bone, joint, face part and piece of equipment, in a
            group: a Word drawing group (wpg), a PowerPoint group, or PDF vector paths;
  "model":  an Office 3D model (am3d:model3d, the .glb inside the file) with the rendered picture as
            its fallback. PDF has no 3D model viewers can be relied on to show, so it gets the
            picture, and the .glb is attached to the PDF as a file.
Each exported file also carries the composition itself (stickman/document.json in the Office
files, an attachment in the PDF), so Stickman can open an exported file and go on editing it.

No pygame/OpenGL.
"""

import io
import json
import math
import re
import struct
import zipfile
import zlib

import numpy as np

import composer
import gltf
import office_clip
import scene
import ttf
from i18n import tr
from office_clip import EMU_PER_PIXEL, _bounds, _emu, _fill, _xfrm, escape, quoteattr

EMU_PER_MM = 36000
PX_PER_MM = 96 / 25.4  # the shapes' pixels (office_clip: 96 dpi)
TWIPS_PER_MM = 1440 / 25.4
PT_PER_MM = 72 / 25.4
DOCUMENT_PART = "stickman/document.json"
DOCUMENT_REL = "urn:stickman:document"
TEXT_COLOR = (0.1, 0.1, 0.1)
CREATOR = f"{scene.APP_NAME} v{scene.VERSION}"  # the files' metadata


def _core_props():
    """docProps/core.xml and app.xml: the author and the program that made the file."""
    core = (f'{office_clip._XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:creator>{escape(scene.CONTACT)}</dc:creator>'
            f'<dc:description>{escape(scene.ATTRIBUTION)}</dc:description></cp:coreProperties>')
    app = (f'{office_clip._XML}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
           f'extended-properties"><Application>{escape(CREATOR)}</Application></Properties>')
    return core, app


_PROPS_TYPES = [("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
                ("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml")]


def _write_props(z):
    core, app = _core_props()
    z.writestr("docProps/core.xml", core)
    z.writestr("docProps/app.xml", app)
SLACK = 3.0  # mm: the Word page is this much longer than the layout, for the paragraphs between tables
MIME = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pdf": "application/pdf"}


# --- pictures --------------------------------------------------------------------------

def _filtered(rows, bpp):
    """PNG filter type 1 (Sub) of each row, with its filter byte: what PNG and PDF's predictor 15 read."""
    rows = rows.astype(np.int16)
    sub = rows.copy()
    sub[:, bpp:] = rows[:, bpp:] - rows[:, :-bpp]
    sub = (sub & 255).astype(np.uint8)
    return np.hstack([np.ones((len(rows), 1), np.uint8), sub]).tobytes()


def png(rgba):
    """A PNG file of top-down RGBA pixels (numpy uint8, h x w x 4); RGB if it's all opaque."""
    h, w, _ = rgba.shape
    opaque = bool((rgba[..., 3] == 255).all())
    pixels = rgba[..., :3] if opaque else rgba
    bpp = 3 if opaque else 4
    data = zlib.compress(_filtered(pixels.reshape(h, w * bpp), bpp), 6)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2 if opaque else 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", data) + chunk(b"IEND", b"")


# --- what goes in a cell -----------------------------------------------------------------

def placed_shapes(entry, rect, tattoo):
    """The entry's figure as office_clip shape dicts in page pixels (96 dpi), fitted to rect (mm) as
    its picture is."""
    figures, parts = composer.entry_figures(entry)
    framing = composer.frame(entry, rect[2] / rect[3], "shapes", False)
    view = scene.View(composer.entry_camera(entry), (composer.REFERENCE, composer.REFERENCE))
    shapes = scene.figure_shapes(figures, parts, view, tattoo)
    x0, y0, x1, _ = framing["crop"]
    k = rect[2] / (x1 - x0) * PX_PER_MM  # page pixels per reference pixel
    ox, oy = rect[0] * PX_PER_MM, rect[1] * PX_PER_MM

    def p(point):
        return ox + (point[0] - x0) * k, oy + (point[1] - y0) * k
    out = []
    for s in shapes:
        s = dict(s)
        if s["kind"] == "line":
            s.update(a=p(s["a"]), b=p(s["b"]), width=s["width"] * k)
        elif s["kind"] == "circle":
            s.update(center=p(s["center"]), radius=s["radius"] * k)
        elif s["kind"] == "polygon":
            s.update(points=[p(q) for q in s["points"]])
        elif s["kind"] == "text":
            s.update(center=p(s["center"]), width=s["width"] * k, height=s["height"] * k, size=s["size"] * k)
        out.append(s)
    return out


def entry_glb(entry, tattoo):
    """The entry as a .glb turned to its view and centred, as composer.frame's "office" describes it."""
    figures, parts = composer.entry_figures(entry)
    office = composer.frame(entry, 1.0, "model", False)["office"]
    return gltf.build_glb(scene.model_parts(figures, parts, tattoo), rotation=office["rotation"],
                          offset=-office["centre"])


def _office_frame(entry, rect):
    return composer.frame(entry, rect[2] / rect[3], "model", False)["office"]


_LIGHTS = (  # Office's own lights for a model it inserts
    '<am3d:ambientLight><am3d:clr><a:scrgbClr r="50000" g="50000" b="50000"/></am3d:clr>'
    '<am3d:illuminance n="500000" d="1000000"/></am3d:ambientLight>'
    '<am3d:ptLight rad="0"><am3d:clr><a:scrgbClr r="100000" g="75000" b="50000"/></am3d:clr>'
    '<am3d:intensity n="9765625" d="1000000"/><am3d:pos x="21959998" y="70920001" z="16344003"/></am3d:ptLight>'
    '<am3d:ptLight rad="0"><am3d:clr><a:scrgbClr r="40000" g="60000" b="95000"/></am3d:clr>'
    '<am3d:intensity n="12250000" d="1000000"/><am3d:pos x="-37964106" y="51130435" z="57631972"/></am3d:ptLight>'
    '<am3d:ptLight rad="0"><am3d:clr><a:scrgbClr r="86837" g="72700" b="100000"/></am3d:clr>'
    '<am3d:intensity n="3125000" d="1000000"/><am3d:pos x="-37739122" y="58056624" z="-34769649"/></am3d:ptLight>')


def _model3d(model_rid, picture_rid, cx, cy, office):
    """The am3d:model3d element: the .glb is centred and turned to the view, so no turn or shift here."""
    z = round(office["sphere"] / math.sin(math.radians(composer.OFFICE_FOV) / 2))
    viewport = round(office["size"] * cy)
    per_unit = round(1e6 / max(office["longest"], 1e-6))
    one = 'n="1000000" d="1000000"'
    return (f'<am3d:model3d r:embed="{model_rid}"><am3d:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></am3d:spPr>'
            f'<am3d:camera><am3d:pos x="0" y="0" z="{z}"/><am3d:up dx="0" dy="{composer.OFFICE_UNIT}" dz="0"/>'
            f'<am3d:lookAt x="0" y="0" z="0"/><am3d:perspective fov="{round(composer.OFFICE_FOV * 60000)}"/>'
            f'</am3d:camera><am3d:trans><am3d:meterPerModelUnit n="{per_unit}" d="1000000"/>'
            f'<am3d:preTrans dx="0" dy="0" dz="0"/><am3d:scale><am3d:sx {one}/><am3d:sy {one}/><am3d:sz {one}/>'
            f'</am3d:scale><am3d:rot ax="0" ay="0" az="0"/><am3d:postTrans dx="0" dy="0" dz="0"/></am3d:trans>'
            f'<am3d:raster rName="Office3DRenderer" rVer="16.0.8326"><am3d:blip r:embed="{picture_rid}"/></am3d:raster>'
            f'<am3d:objViewport viewportSz="{viewport}"/>{_LIGHTS}</am3d:model3d>')


def _picture_name(number):
    return tr("Figure {}").format(number)


class _Parts:
    """Media parts of an Office package and the relationships to them from one part."""

    def __init__(self, folder, media):
        self.folder, self.media, self.rels = folder, media, []  # media: shared {name: bytes}

    def add(self, kind, data, extension):
        name = f"{kind}{len(self.media) + 1}.{extension}"
        self.media[name] = data
        rel_type = ("http://schemas.microsoft.com/office/2017/06/relationships/model3d" if extension == "glb"
                    else f"{office_clip._REL}/image")
        self.rels.append((rel_type, f"../media/{name}"))
        return f"rId{len(self.rels) + 100}"

    def xml(self, *base):
        """The relationships part: base (type, target) pairs as rId1.., then the media as rId101.."""
        items = [f'<Relationship Id="rId{i}" Type="{office_clip._REL}/{kind}" Target="{target}"/>'
                 for i, (kind, target) in enumerate(base, 1)]
        items += [f'<Relationship Id="rId{i + 101}" Type="{kind}" Target="{target}"/>'
                  for i, (kind, target) in enumerate(self.rels)]
        return (f'{office_clip._XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                f'relationships">{"".join(items)}</Relationships>')


def _types(overrides, media):
    defaults = {"rels": "application/vnd.openxmlformats-package.relationships+xml", "xml": "application/xml",
                "json": "application/json"}
    if any(n.endswith(".png") for n in media):
        defaults["png"] = "image/png"
    if any(n.endswith(".glb") for n in media):
        defaults["glb"] = "model/gltf.binary"
    return (f'{office_clip._XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            + "".join(f'<Default Extension="{e}" ContentType="{t}"/>' for e, t in defaults.items())
            + "".join(f'<Override PartName="{p}" ContentType="{t}"/>' for p, t in overrides)
            + '</Types>')


def _package_rels(main):
    return (f'{office_clip._XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{office_clip._REL}/officeDocument" Target="{main}"/>'
            f'<Relationship Id="rId2" Type="{DOCUMENT_REL}" Target="{DOCUMENT_PART}"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/'
            'core-properties" Target="docProps/core.xml"/>'
            f'<Relationship Id="rId4" Type="{office_clip._REL}/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>')


def _cells(doc, lay):
    for page, cells in enumerate(lay["pages"]):
        for cell in cells:
            yield page, cell, doc.entries[cell["entry"]]


def _pixels(images, doc, cell):
    key = composer.cell_key(doc, cell, "export")
    if key not in images:
        raise KeyError(tr("A figure's picture is missing"))
    return images[key]


# --- Word ----------------------------------------------------------------------------------

_W_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
         f'xmlns:r="{office_clip._REL}" '
         'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
         f'xmlns:a="{office_clip._DML}" '
         'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
         'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
         'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
         'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
         'xmlns:am3d="http://schemas.microsoft.com/office/drawing/2017/model3d" '
         'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
         'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
         'mc:Ignorable="w14 wp14"')

_W_STYLES = (
    f'{office_clip._XML}<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="el-GR" w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr>'
    '</w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    '</w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/>'
    '<w:qFormat/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:color w:val="1A1A1A"/></w:rPr></w:style>'
    '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
    '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
    '<w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/>'
    '</w:tblCellMar></w:tblPr></w:style></w:styles>')

_W_SETTINGS = (
    f'{office_clip._XML}<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:defaultTabStop w:val="720"/><w:compat><w:compatSetting w:name="compatibilityMode" '
    'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')


def _tw(mm):
    return round(mm * TWIPS_PER_MM)


def _mm_emu(mm):
    return round(mm * EMU_PER_MM)


def _inline(content, cx, cy, pid, name, uri):
    return (f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{pid}" name={quoteattr(name)}/>'
            f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="{uri}">{content}</a:graphicData></a:graphic></wp:inline>')


def _w_picture(rid, cx, cy, pid, name):
    pic = (f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{pid}" name={quoteattr(name)}/><pic:cNvPicPr>'
           f'<a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/>'
           f'<a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
           f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>')
    return _inline(pic, cx, cy, pid, name, "http://schemas.openxmlformats.org/drawingml/2006/picture")


def _wps_shape(shape, sid):
    """A shape of a Word drawing group (wps:wsp), in pixels relative to the group."""
    name = quoteattr(shape["name"])
    kind = shape["kind"]
    if kind == "line":
        (ax, ay), (bx, by) = shape["a"], shape["b"]
        flip_v = (bx < ax) != (by < ay)
        return (f'<wps:wsp><wps:cNvPr id="{sid}" name={name}/><wps:cNvCnPr/><wps:spPr>'
                f'{_xfrm(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), flip_v)}'
                f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
                f'<a:ln w="{max(1, _emu(shape["width"]))}" cap="rnd">{_fill(shape["color"])}<a:round/></a:ln>'
                f'</wps:spPr><wps:bodyPr/></wps:wsp>')
    outline = f'<a:ln w="{round(EMU_PER_PIXEL * 0.75)}">{_fill(shape.get("outline", shape["color"]))}</a:ln>'
    if kind == "polygon":
        x0, y0, x1, y1 = _bounds(shape)
        w, h = max(1, _emu(x1 - x0)), max(1, _emu(y1 - y0))
        pts = [f'<a:pt x="{_emu(x - x0)}" y="{_emu(y - y0)}"/>' for x, y in shape["points"]]
        path = f'<a:moveTo>{pts[0]}</a:moveTo>' + "".join(f'<a:lnTo>{p}</a:lnTo>' for p in pts[1:]) + '<a:close/>'
        geometry = (f'<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/>'
                    f'<a:pathLst><a:path w="{w}" h="{h}">{path}</a:path></a:pathLst></a:custGeom>')
        return (f'<wps:wsp><wps:cNvPr id="{sid}" name={name}/><wps:cNvSpPr/><wps:spPr>'
                f'{_xfrm(x0, y0, x1 - x0, y1 - y0)}{geometry}{_fill(shape["color"])}{outline}</wps:spPr>'
                f'<wps:bodyPr/></wps:wsp>')
    if kind == "text":
        (cx, cy), w, h = shape["center"], shape["width"], shape["height"]
        size = max(2, round(shape["size"] * 0.75 * 2))  # half points
        bold = "<w:b/>" if shape.get("bold") else ""
        font = escape(shape["font"].capitalize())
        para = (f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0" w:line="240" '
                f'w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
                f'{bold}<w:color w:val="{office_clip._hex(shape["color"])}"/><w:sz w:val="{size}"/>'
                f'<w:szCs w:val="{size}"/></w:rPr><w:t xml:space="preserve">{escape(shape["text"])}</w:t></w:r></w:p>')
        return (f'<wps:wsp><wps:cNvPr id="{sid}" name={name}/><wps:cNvSpPr txBox="1"/><wps:spPr>'
                f'{_xfrm(cx - w / 2, cy - h / 2, w, h, angle=shape["angle"])}<a:prstGeom prst="rect"><a:avLst/>'
                f'</a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr><wps:txbx><w:txbxContent>{para}'
                f'</w:txbxContent></wps:txbx><wps:bodyPr rot="0" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" '
                f'anchor="ctr" anchorCtr="1"><a:noAutofit/></wps:bodyPr></wps:wsp>')
    (cx, cy), r = shape["center"], shape["radius"]
    return (f'<wps:wsp><wps:cNvPr id="{sid}" name={name}/><wps:cNvSpPr/><wps:spPr>{_xfrm(cx - r, cy - r, 2 * r, 2 * r)}'
            f'<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>{_fill(shape["color"])}{outline}</wps:spPr>'
            f'<wps:bodyPr/></wps:wsp>')


def _w_group(shapes, rect, pid, name):
    ox, oy = rect[0] * PX_PER_MM, rect[1] * PX_PER_MM
    w, h = rect[2] * PX_PER_MM, rect[3] * PX_PER_MM
    moved = []
    for s in shapes:
        s = dict(s)
        if s["kind"] == "line":
            s.update(a=(s["a"][0] - ox, s["a"][1] - oy), b=(s["b"][0] - ox, s["b"][1] - oy))
        elif s["kind"] == "polygon":
            s.update(points=[(x - ox, y - oy) for x, y in s["points"]])
        else:
            s.update(center=(s["center"][0] - ox, s["center"][1] - oy))
        moved.append(s)
    box = (f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/><a:chOff x="0" y="0"/>'
           f'<a:chExt cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>')
    # Word shrinks a group to its shapes; an invisible rectangle keeps it the size of its cell.
    frame = (f'<wps:wsp><wps:cNvPr id="{pid + 1}" name={quoteattr(tr("Frame"))}/><wps:cNvSpPr/><wps:spPr>'
             f'{_xfrm(0, 0, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln>'
             f'</wps:spPr><wps:bodyPr/></wps:wsp>')
    body = frame + "".join(_wps_shape(s, pid + 2 + i) for i, s in enumerate(moved))
    group = f'<wpg:wgp><wpg:cNvGrpSpPr/><wpg:grpSpPr>{box}</wpg:grpSpPr>{body}</wpg:wgp>'
    return _inline(group, _emu(w), _emu(h), pid, name, "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup")


def _w_footer(line):
    """The footer part: the attribution in a content control that can be neither deleted nor edited
    (w:lock sdtContentLocked), centred and grey. No document protection, so all else stays editable."""
    size = round(line["size"] * 2)
    color = office_clip._hex(composer.ATTRIBUTION_COLOR)
    para = (f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0" '
            f'w:line="{_tw(line["height"])}" w:lineRule="exact"/></w:pPr><w:r><w:rPr><w:color w:val="{color}"/>'
            f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(line["text"])}</w:t></w:r></w:p>')
    sdt = (f'<w:sdt><w:sdtPr><w:alias w:val="{escape(scene.APP_NAME)}"/><w:tag w:val="stickman-attribution"/>'
           f'<w:id w:val="1"/><w:lock w:val="sdtContentLocked"/></w:sdtPr><w:sdtContent>{para}</w:sdtContent></w:sdt>')
    return f'{office_clip._XML}<w:ftr {_W_NS}>{sdt}</w:ftr>'


def _w_run(drawing):
    return f'<w:r><w:rPr><w:noProof/></w:rPr>{drawing}</w:r>'


def _w_tiny(extra=""):
    """An all but invisible paragraph (a table cell needs one; a page break goes in one)."""
    return (f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>'
            f'<w:rPr><w:sz w:val="2"/></w:rPr></w:pPr>{extra}</w:p>')


def _w_caption(lines):
    out = []
    for k, line in enumerate(lines):
        size = round(line["size"] * 2)
        bold = "<w:b/><w:bCs/>" if line["bold"] else ""
        before = f' w:before="{_tw(composer.CAPTION_GAP - 0.4)}"' if k == 0 else ' w:before="0"'
        out.append(f'<w:p><w:pPr><w:pStyle w:val="Caption"/><w:spacing{before} w:after="0" '
                   f'w:line="{_tw(line["height"])}" w:lineRule="exact"/></w:pPr><w:r><w:rPr>{bold}'
                   f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
                   f'<w:t xml:space="preserve">{escape(line["text"])}</w:t></w:r></w:p>')
    return "".join(out)


def build_docx(doc, images, tattoo):
    lay = composer.layout(doc)
    s = doc.settings
    pw, ph = lay["page"]
    m = s["margin"]
    cols, rows = s["columns"], s["rows"]
    slot_w, slot_h = lay["content"][2] / cols, lay["content"][3] / rows
    pad = lay["pad"]
    media, parts = {}, _Parts("word", {})
    parts.media = media
    pid = 1
    tables = []
    by_page = {}
    for page, cell, entry in _cells(doc, lay):
        by_page.setdefault(page, {})[cell["entry"] - page * doc.capacity] = (cell, entry)
    for page in range(len(lay["pages"])):
        cells = by_page.get(page, {})
        trs = []
        for r in range(rows):
            tcs = []
            for c in range(cols):
                content = ""
                if r * cols + c in cells:
                    cell, entry = cells[r * cols + c]
                    rect, number = cell["figure"], cell["number"]
                    cx, cy = _mm_emu(rect[2]), _mm_emu(rect[3])
                    mode, name = doc.mode(entry), _picture_name(number)
                    if mode == "shapes":
                        drawing = _w_group(placed_shapes(entry, rect, tattoo), rect, pid, name)
                        pid += 1000
                        drawing = f'<w:drawing>{drawing}</w:drawing>'
                    else:
                        picture = parts.add("image", png(_pixels(images, doc, cell)), "png")
                        drawing = f'<w:drawing>{_w_picture(picture, cx, cy, pid, name)}</w:drawing>'
                        if mode == "model":
                            model = parts.add("model3d", entry_glb(entry, tattoo), "glb")
                            office = _office_frame(entry, rect)
                            graphic = _inline(_model3d(model, picture, cx, cy, office), cx, cy, pid,
                                              tr("3D model {}").format(number),
                                              "http://schemas.microsoft.com/office/drawing/2017/model3d")
                            drawing = (f'<mc:AlternateContent><mc:Choice Requires="am3d"><w:drawing>{graphic}'
                                       f'</w:drawing></mc:Choice><mc:Fallback>{drawing}</mc:Fallback>'
                                       f'</mc:AlternateContent>')
                        pid += 1
                    content = (f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0"/>'
                               f'<w:rPr><w:sz w:val="2"/></w:rPr></w:pPr>{_w_run(drawing)}</w:p>'
                               + _w_caption(cell["lines"]))
                tcs.append(f'<w:tc><w:tcPr><w:tcW w:w="{_tw(slot_w)}" w:type="dxa"/><w:tcMar>'
                           f'<w:top w:w="{_tw(pad)}" w:type="dxa"/><w:left w:w="{_tw(pad)}" w:type="dxa"/>'
                           f'<w:bottom w:w="0" w:type="dxa"/><w:right w:w="{_tw(pad)}" w:type="dxa"/></w:tcMar>'
                           f'<w:vAlign w:val="top"/></w:tcPr>{content or _w_tiny()}</w:tc>')
            trs.append(f'<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="{_tw(slot_h)}" w:hRule="exact"/></w:trPr>'
                       + "".join(tcs) + '</w:tr>')
        grid = "".join(f'<w:gridCol w:w="{_tw(slot_w)}"/>' for _ in range(cols))
        tables.append(f'<w:tbl><w:tblPr><w:tblW w:w="{_tw(slot_w) * cols}" w:type="dxa"/>'
                      f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
                      f'<w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/>'
                      f'</w:tblCellMar><w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" '
                      f'w:lastColumn="0" w:noHBand="1" w:noVBand="1"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
                      + "".join(trs) + '</w:tbl>')
        pid += 1
    page_break = _w_tiny('<w:r><w:rPr><w:sz w:val="2"/></w:rPr><w:br w:type="page"/></w:r>')
    orient = ' w:orient="landscape"' if s["orientation"] == "landscape" else ""
    line = lay["attribution"]
    # The grid ends composer.FOOTER above the margin and the body may run SLACK further; the footer's
    # line (ending its distance above the page's bottom) starts where the body stops.
    footer = max(0.0, ph - line["top"] - line["height"])
    section = (f'<w:sectPr><w:footerReference w:type="default" r:id="rId3"/>'
               f'<w:pgSz w:w="{_tw(pw)}" w:h="{_tw(ph)}"{orient}/>'
               f'<w:pgMar w:top="{_tw(m)}" w:right="{_tw(m)}" w:bottom="{_tw(m + composer.FOOTER - SLACK)}" '
               f'w:left="{_tw(m)}" w:header="0" w:footer="{_tw(footer)}" w:gutter="0"/></w:sectPr>')
    body = page_break.join(tables) + _w_tiny() + section
    document = f'{office_clip._XML}<w:document {_W_NS}><w:body>{body}</w:body></w:document>'
    rels = parts.xml(("styles", "styles.xml"), ("settings", "settings.xml"), ("footer", "footer1.xml")).replace('"../media/', '"media/')
    wml = "application/vnd.openxmlformats-officedocument.wordprocessingml"
    types = _types([("/word/document.xml", f"{wml}.document.main+xml"), ("/word/styles.xml", f"{wml}.styles+xml"),
                    ("/word/settings.xml", f"{wml}.settings+xml"), ("/word/footer1.xml", f"{wml}.footer+xml")]
                   + _PROPS_TYPES, media)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", _package_rels("word/document.xml"))
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", rels)
        z.writestr("word/styles.xml", _W_STYLES)
        z.writestr("word/settings.xml", _W_SETTINGS)
        z.writestr("word/footer1.xml", _w_footer(line))
        _write_props(z)
        for name, data in media.items():
            z.writestr("word/media/" + name, data, zipfile.ZIP_STORED if name.endswith(".png") else zipfile.ZIP_DEFLATED)
        z.writestr(DOCUMENT_PART, doc.to_json())
    return out.getvalue()


# --- PowerPoint ----------------------------------------------------------------------------

def _p_box(rect):
    return (f'<a:off x="{_mm_emu(rect[0])}" y="{_mm_emu(rect[1])}"/>'
            f'<a:ext cx="{_mm_emu(rect[2])}" cy="{_mm_emu(rect[3])}"/>')


def _p_picture(rid, rect, sid, name):
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name={quoteattr(name)}/><p:cNvPicPr><a:picLocks noChangeAspect="1"/>'
            f'</p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/>'
            f'</a:stretch></p:blipFill><p:spPr><a:xfrm>{_p_box(rect)}</a:xfrm><a:prstGeom prst="rect"><a:avLst/>'
            f'</a:prstGeom></p:spPr></p:pic>')


def _p_caption(lines, cell, sid, number):
    if not lines:
        return ""
    top = lines[0]["top"]
    box = (cell[0], top, cell[2], sum(line["height"] for line in lines))
    paras = []
    for line in lines:
        bold = ' b="1"' if line["bold"] else ""
        paras.append(f'<a:p><a:pPr algn="ctr"><a:lnSpc><a:spcPts val="{round(line["height"] * PT_PER_MM * 100)}"/>'
                     f'</a:lnSpc><a:spcBef><a:spcPts val="0"/></a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft>'
                     f'</a:pPr><a:r><a:rPr lang="el-GR" sz="{round(line["size"] * 100)}"{bold} dirty="0">'
                     f'{_fill(TEXT_COLOR)}<a:latin typeface="{ttf.OFFICE_FONT}"/><a:cs typeface="{ttf.OFFICE_FONT}"/>'
                     f'</a:rPr><a:t>{escape(line["text"])}</a:t></a:r></a:p>')
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name={quoteattr(tr("Caption {}").format(number))}/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>{_p_box(box)}</a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody>'
            f'<a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:noAutofit/></a:bodyPr>'
            f'<a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>')


def _p_attribution(line):
    """The attribution as a locked shape of the slide master: every slide shows and prints it, but it
    can't be selected or deleted on a slide (only in View > Slide Master)."""
    para = (f'<a:p><a:pPr algn="ctr"><a:lnSpc><a:spcPts val="{round(line["height"] * PT_PER_MM * 100)}"/></a:lnSpc>'
            f'<a:spcBef><a:spcPts val="0"/></a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft></a:pPr>'
            f'<a:r><a:rPr lang="en-GB" sz="{round(line["size"] * 100)}" dirty="0">{_fill(composer.ATTRIBUTION_COLOR)}'
            f'<a:latin typeface="{ttf.OFFICE_FONT}"/><a:cs typeface="{ttf.OFFICE_FONT}"/></a:rPr>'
            f'<a:t>{escape(line["text"])}</a:t></a:r></a:p>')
    box = (line["x"], line["top"], line["width"], line["height"])
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="2" name={quoteattr(scene.APP_NAME)}/><p:cNvSpPr txBox="1"><a:spLocks '
            f'noGrp="1" noSelect="1" noRot="1" noMove="1" noResize="1" noTextEdit="1"/></p:cNvSpPr>'
            f'<p:nvPr userDrawn="1"/></p:nvSpPr><p:spPr><a:xfrm>{_p_box(box)}</a:xfrm><a:prstGeom prst="rect">'
            f'<a:avLst/></a:prstGeom><a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" '
            f'rIns="0" bIns="0" anchor="ctr"><a:noAutofit/></a:bodyPr><a:lstStyle/>{para}</p:txBody></p:sp>')


def build_pptx(doc, images, tattoo):
    lay = composer.layout(doc)
    pw, ph = lay["page"]
    media, slides = {}, []
    for page, cells in enumerate(lay["pages"]):
        parts = _Parts("ppt", media)
        sid, items = 2, []
        for cell in cells:
            entry, rect, number = doc.entries[cell["entry"]], cell["figure"], cell["number"]
            mode, name = doc.mode(entry), _picture_name(number)
            if mode == "shapes":
                shapes = placed_shapes(entry, rect, tattoo)
                body = "".join(office_clip._shape_xml(sh, sid + 1 + i, 0, 0, slide=True) for i, sh in enumerate(shapes))
                box = _p_box(rect)
                ch = box.replace("a:off", "a:chOff").replace("a:ext", "a:chExt")
                items.append(f'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{sid}" name={quoteattr(name)}/><p:cNvGrpSpPr/>'
                             f'<p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>{box}{ch}</a:xfrm></p:grpSpPr>{body}</p:grpSp>')
                sid += len(shapes) + 1
            else:
                picture = parts.add("image", png(_pixels(images, doc, cell)), "png")
                pic = _p_picture(picture, rect, sid, name)
                if mode == "model":
                    model = parts.add("model3d", entry_glb(entry, tattoo), "glb")
                    cx, cy = _mm_emu(rect[2]), _mm_emu(rect[3])
                    frame_xml = (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" '
                                 f'name={quoteattr(tr("3D model {}").format(number))}/><p:cNvGraphicFramePr>'
                                 f'<a:graphicFrameLocks noChangeAspect="1"/></p:cNvGraphicFramePr><p:nvPr/>'
                                 f'</p:nvGraphicFramePr><p:xfrm>{_p_box(rect)}</p:xfrm><a:graphic><a:graphicData '
                                 f'uri="http://schemas.microsoft.com/office/drawing/2017/model3d">'
                                 f'{_model3d(model, picture, cx, cy, _office_frame(entry, rect))}'
                                 f'</a:graphicData></a:graphic></p:graphicFrame>')
                    pic = (f'<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
                           f'<mc:Choice xmlns:am3d="http://schemas.microsoft.com/office/drawing/2017/model3d" '
                           f'Requires="am3d">{frame_xml}</mc:Choice><mc:Fallback>{pic}</mc:Fallback></mc:AlternateContent>')
                items.append(pic)
                sid += 1
            items.append(_p_caption(cell["lines"], cell["cell"], sid, number))
            sid += 1
        tree = office_clip._EMPTY_TREE.replace('</p:spTree>', "".join(items) + '</p:spTree>')
        slides.append((f'{office_clip._XML}<p:sld {office_clip._NS}>{tree}{office_clip._NO_COLOR_MAP}</p:sld>',
                       parts.xml(("slideLayout", "../slideLayouts/slideLayout1.xml"))))
    n = len(slides)
    layout_xml = (f'{office_clip._XML}<p:sldLayout {office_clip._NS} type="blank" preserve="1">'
                  f'{office_clip._EMPTY_TREE}{office_clip._NO_COLOR_MAP}</p:sldLayout>')
    master_tree = office_clip._EMPTY_TREE.replace('</p:spTree>', _p_attribution(lay["attribution"]) + '</p:spTree>')
    master = (f'{office_clip._XML}<p:sldMaster {office_clip._NS}>{master_tree}{office_clip._COLOR_MAP}'
              '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>')
    ids = "".join(f'<p:sldId id="{256 + k}" r:id="rId{k + 2}"/>' for k in range(n))
    presentation = (f'{office_clip._XML}<p:presentation {office_clip._NS}>'
                    '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
                    f'<p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{_mm_emu(pw)}" cy="{_mm_emu(ph)}"/>'
                    '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    pml = "application/vnd.openxmlformats-officedocument.presentationml"
    overrides = [("/ppt/presentation.xml", f"{pml}.presentation.main+xml"),
                 ("/ppt/slideMasters/slideMaster1.xml", f"{pml}.slideMaster+xml"),
                 ("/ppt/slideLayouts/slideLayout1.xml", f"{pml}.slideLayout+xml"),
                 ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml")]
    overrides += [(f"/ppt/slides/slide{k + 1}.xml", f"{pml}.slide+xml") for k in range(n)]
    rel = office_clip._rels
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _types(overrides + _PROPS_TYPES, media))
        z.writestr("_rels/.rels", _package_rels("ppt/presentation.xml"))
        z.writestr("ppt/presentation.xml", presentation)
        z.writestr("ppt/_rels/presentation.xml.rels",
                   rel(("slideMaster", "slideMasters/slideMaster1.xml"),
                       *[("slide", f"slides/slide{k + 1}.xml") for k in range(n)],
                       ("theme", "theme/theme1.xml")))
        for k, (slide, slide_rels) in enumerate(slides):
            z.writestr(f"ppt/slides/slide{k + 1}.xml", slide)
            z.writestr(f"ppt/slides/_rels/slide{k + 1}.xml.rels", slide_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout_xml)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rel(("slideMaster", "../slideMasters/slideMaster1.xml")))
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",
                   rel(("slideLayout", "../slideLayouts/slideLayout1.xml"), ("theme", "../theme/theme1.xml")))
        z.writestr("ppt/theme/theme1.xml", office_clip._THEME)
        _write_props(z)
        for name, data in media.items():
            z.writestr("ppt/media/" + name, data, zipfile.ZIP_STORED if name.endswith(".png") else zipfile.ZIP_DEFLATED)
        z.writestr(DOCUMENT_PART, doc.to_json())
    return out.getvalue()


# --- PDF -----------------------------------------------------------------------------------

def _n(x):
    return f"{x:.3f}".rstrip("0").rstrip(".") if abs(x) >= 1e-4 else "0"


def _rgb(color):
    return " ".join(_n(max(0.0, min(1.0, c))) for c in color)


class _Pdf:
    def __init__(self):
        self.objects = []

    def reserve(self):
        self.objects.append(None)
        return len(self.objects)

    def put(self, n, body):
        self.objects[n - 1] = body if isinstance(body, bytes) else body.encode("latin-1")

    def add(self, body):
        n = self.reserve()
        self.put(n, body)
        return n

    def stream(self, data, extra="", compress=True):
        if compress:
            data = zlib.compress(data, 6)
            extra += " /Filter /FlateDecode"
        return self.add(f"<< /Length {len(data)}{extra} >>\nstream\n".encode("latin-1") + data + b"\nendstream")

    def output(self, root, info=None):
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for k, body in enumerate(self.objects, 1):
            offsets.append(len(out))
            out += f"{k} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objects) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<< /Size {len(self.objects) + 1} /Root {root} 0 R{f" /Info {info} 0 R" if info else ""} >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


class _PdfFont:
    """The embedded caption font (ttf.py) as a CID font (Identity-H): text is written as glyph ids."""

    def __init__(self, bold):
        self.font, self.used = ttf.font(bold), {}

    def encode(self, text):
        out = []
        for ch in text:
            gid = self.font.glyph(ch)
            self.used[gid] = ch
            out.append(f"{gid:04X}")
        return "<" + "".join(out) + ">"

    def write(self, pdf, number):
        f = self.font
        scale = 1000 / f.units
        file_obj = pdf.stream(f.data, f" /Length1 {len(f.data)}")
        bbox = " ".join(str(round(v * scale)) for v in f.bbox)
        descriptor = pdf.add(f"<< /Type /FontDescriptor /FontName /{f.name} /Flags 32 /FontBBox [{bbox}] "
                             f"/ItalicAngle 0 /Ascent {round(f.ascent * scale)} /Descent {round(f.descent * scale)} "
                             f"/CapHeight {round(f.cap_height * scale)} /StemV {120 if f.bold else 80} "
                             f"/FontFile2 {file_obj} 0 R >>")
        widths = " ".join(f"{gid} [{round(f.advance(gid) * scale)}]" for gid in sorted(self.used))
        cid = pdf.add(f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{f.name} /CIDSystemInfo << /Registry (Adobe) "
                      f"/Ordering (Identity) /Supplement 0 >> /FontDescriptor {descriptor} 0 R /W [{widths}] "
                      f"/CIDToGIDMap /Identity >>")
        pairs = "".join(f"<{gid:04X}> <{''.join(f'{u:04X}' for u in _utf16(ch))}>\n" for gid, ch in sorted(self.used.items()))
        cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) "
                "/Ordering (UCS) /Supplement 0 >> def /CMapName /Adobe-Identity-UCS def /CMapType 2 def "
                "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
                f"{len(self.used)} beginbfchar\n{pairs}endbfchar endcmap CMapName currentdict /CMap defineresource pop end end")
        unicode_obj = pdf.stream(cmap.encode("latin-1"))
        pdf.put(number, f"<< /Type /Font /Subtype /Type0 /BaseFont /{f.name} /Encoding /Identity-H "
                       f"/DescendantFonts [{cid} 0 R] /ToUnicode {unicode_obj} 0 R >>")


def _utf16(ch):
    data = ch.encode("utf-16-be")
    return [int.from_bytes(data[k:k + 2], "big") for k in range(0, len(data), 2)]


def _pdf_string(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def _pdf_shapes(shapes, page_h, fonts):
    """PDF drawing operators for office_clip shapes in page pixels."""
    k = 1 / PX_PER_MM * PT_PER_MM  # points per page pixel

    def p(point):
        return f"{_n(point[0] * k)} {_n(page_h - point[1] * k)}"
    ops = ["q 1 J 1 j"]
    for s in shapes:
        kind = s["kind"]
        if kind == "line":
            ops.append(f"{_rgb(s['color'])} RG {_n(s['width'] * k)} w {p(s['a'])} m {p(s['b'])} l S")
        elif kind == "polygon":
            path = f"{p(s['points'][0])} m " + " ".join(f"{p(q)} l" for q in s["points"][1:])
            ops.append(f"{_rgb(s['color'])} rg {_rgb(s['outline'])} RG 0.4 w {path} h B")
        elif kind == "circle":
            (cx, cy), r = s["center"], s["radius"]
            c = 0.5523 * r
            pts = [(cx + r, cy), (cx + r, cy + c), (cx + c, cy + r), (cx, cy + r), (cx - c, cy + r), (cx - r, cy + c),
                   (cx - r, cy), (cx - r, cy - c), (cx - c, cy - r), (cx, cy - r), (cx + c, cy - r), (cx + r, cy - c)]
            path = f"{p(pts[0])} m " + " ".join(f"{p(pts[i])} {p(pts[i + 1])} {p(pts[(i + 2) % 12])} c"
                                                 for i in range(1, 12, 3))
            ops.append(f"{_rgb(s['color'])} rg {_rgb(s['outline'])} RG 0.4 w {path} h B")
        elif kind == "text":
            font = fonts[True]
            size = s["size"] * k
            width = font.font.width(s["text"], size)
            a = math.radians(-s["angle"])  # clockwise on the page is clockwise in PDF's y-up too, mirrored
            cos, sin = math.cos(a), math.sin(a)
            cx, cy = s["center"][0] * k, page_h - s["center"][1] * k
            # From the centre to the start of the baseline: half the width back, a third of the size down.
            x = cx - cos * width / 2 + sin * size * 0.35
            y = cy - sin * width / 2 - cos * size * 0.35
            ops.append(f"BT {_rgb(s['color'])} rg /F2 {_n(size)} Tf {_n(cos)} {_n(sin)} {_n(-sin)} {_n(cos)} "
                       f"{_n(x)} {_n(y)} Tm {font.encode(s['text'])} Tj ET")
    ops.append("Q")
    return "\n".join(ops)


def _pdf_image(pdf, rgba):
    h, w, _ = rgba.shape
    parms = f" /DecodeParms << /Predictor 15 /Colors {{}} /BitsPerComponent 8 /Columns {w} >>"
    common = f" /Type /XObject /Subtype /Image /Width {w} /Height {h} /BitsPerComponent 8"
    smask = ""
    if not (rgba[..., 3] == 255).all():
        alpha = pdf.stream(_filtered(rgba[..., 3].reshape(h, w), 1), common + " /ColorSpace /DeviceGray"
                           + parms.format(1))
        smask = f" /SMask {alpha} 0 R"
    return pdf.stream(_filtered(rgba[..., :3].reshape(h, w * 3), 3),
                      common + " /ColorSpace /DeviceRGB" + parms.format(3) + smask)


def _baseline(line, font):
    """The baseline (mm from the top) of a caption line centred in its height, as a browser places it."""
    f = font.font
    asc, desc = f.ascent / f.units, -f.descent / f.units
    size = line["size"] * composer.PT
    return line["top"] + (line["height"] - (asc + desc) * size) / 2 + asc * size


def build_pdf(doc, images, tattoo):
    lay = composer.layout(doc)
    pw, ph = lay["page"]
    page_w, page_h = pw * PT_PER_MM, ph * PT_PER_MM
    pdf = _Pdf()
    catalog, pages_obj = pdf.reserve(), pdf.reserve()
    fonts = {False: _PdfFont(False), True: _PdfFont(True)}
    font_objs = {False: pdf.reserve(), True: pdf.reserve()}
    page_objs, attachments = [], []
    for page, cells in enumerate(lay["pages"]):
        ops, xobjects = [], {}
        for cell in cells:
            entry, rect, number = doc.entries[cell["entry"]], cell["figure"], cell["number"]
            mode = doc.mode(entry)
            if mode == "shapes":
                ops.append(_pdf_shapes(placed_shapes(entry, rect, tattoo), page_h, fonts))
            else:
                name = f"Im{len(xobjects) + 1}"
                xobjects[name] = _pdf_image(pdf, _pixels(images, doc, cell))
                x, y, w, h = (v * PT_PER_MM for v in rect)
                ops.append(f"q {_n(w)} 0 0 {_n(h)} {_n(x)} {_n(page_h - y - h)} cm /{name} Do Q")
                if mode == "model":
                    attachments.append((f"figure-{number}.glb", "model/gltf-binary", entry_glb(entry, tattoo),
                                        tr("3D model {}").format(number)))
            for line in cell["lines"]:
                font = fonts[line["bold"]]
                size_pt = line["size"]
                width = font.font.width(line["text"], size_pt * composer.PT)
                x = (line["x"] + (line["width"] - width) / 2) * PT_PER_MM
                y = page_h - _baseline(line, font) * PT_PER_MM
                ops.append(f"BT {_rgb(TEXT_COLOR)} rg /F{2 if line['bold'] else 1} {_n(size_pt)} Tf {_n(x)} {_n(y)} Td "
                           f"{font.encode(line['text'])} Tj ET")
        line, font = lay["attribution"], fonts[False]
        width = font.font.width(line["text"], line["size"] * composer.PT)
        x = (line["x"] + (line["width"] - width) / 2) * PT_PER_MM
        y = page_h - _baseline(line, font) * PT_PER_MM
        ops.append(f"BT {_rgb(composer.ATTRIBUTION_COLOR)} rg /F1 {_n(line['size'])} Tf {_n(x)} {_n(y)} Td "
                   f"{font.encode(line['text'])} Tj ET")
        content = pdf.stream("\n".join(ops).encode("latin-1"))
        xo = " ".join(f"/{k} {v} 0 R" for k, v in xobjects.items())
        page_objs.append(pdf.add(f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {_n(page_w)} {_n(page_h)}] "
                                 f"/Resources << /Font << /F1 {font_objs[False]} 0 R /F2 {font_objs[True]} 0 R >> "
                                 f"/XObject << {xo} >> >> /Contents {content} 0 R >>"))
    for bold in (False, True):
        fonts[bold].write(pdf, font_objs[bold])
    pdf.put(pages_obj, f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_objs)}] /Count {len(page_objs)} >>")
    # The composition (uncompressed, so read_exported can find it) and the 3D models, as attachments.
    names = []
    data = doc.to_json().encode("utf-8")
    files = [("stickman-document.json", "application/json", data, tr("Stickman document"))] + attachments
    for name, mime, body, description in files:
        stream = pdf.stream(body, f" /Type /EmbeddedFile /Subtype /{mime.replace('/', '#2F')}",
                            compress=not mime.endswith("json"))
        spec = pdf.add(f"<< /Type /Filespec /F {_pdf_string(name)} /UF {_pdf_string(name)} "
                       f"/Desc {_pdf_string(_ascii(description))} /EF << /F {stream} 0 R >> >>")
        names.append(f"{_pdf_string(name)} {spec} 0 R")
    info = f" /Names << /EmbeddedFiles << /Names [{' '.join(sorted(names))}] >> >>"
    pdf.put(catalog, f"<< /Type /Catalog /Pages {pages_obj} 0 R{info} >>")
    meta = pdf.add(f"<< /Creator {_pdf_string(CREATOR)} /Producer {_pdf_string(scene.APP_NAME)} "
                   f"/Author {_pdf_string(scene.CONTACT)} /Subject {_pdf_string(scene.ATTRIBUTION)} >>")
    return pdf.output(catalog, meta)


def _ascii(text):
    return text.encode("ascii", "replace").decode()


# --- the way in and out --------------------------------------------------------------------

BUILDERS = {"docx": build_docx, "pptx": build_pptx, "pdf": build_pdf}


def export(doc, fmt, images, tattoo):
    """The document as a file of the format (bytes). images: {render_jobs key: RGBA pixels}."""
    return BUILDERS[fmt](doc, images, tattoo)


def read_exported(data):
    """The composition inside a file Stickman exported (docx, pptx or pdf), or None."""
    data = bytes(data)
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return json.loads(z.read(DOCUMENT_PART).decode("utf-8"))
        except (KeyError, zipfile.BadZipFile, ValueError):
            return None
    if data[:5] == b"%PDF-":
        match = re.search(rb"/Subtype /application#2Fjson >>\nstream\n", data)
        length = re.search(rb"<< /Length (\d+) /Type /EmbeddedFile /Subtype /application#2Fjson >>\nstream\n", data)
        if length:
            start = length.end()
            try:
                return json.loads(data[start:start + int(length.group(1))].decode("utf-8"))
            except ValueError:
                return None
    return None
