"""Flat 2D drawings (office_clip.py's shape dicts, in screen pixels) as an SVG image.

The website puts this on the clipboard: Office pastes it as a picture that "Convert to Shape"
turns into editable shapes.  Shapes are drawn in order, later ones on top.
"""

from xml.sax.saxutils import escape, quoteattr

from office_clip import extent


def _hex(color):
    return "#" + "".join(f"{int(round(max(0.0, min(1.0, c)) * 255)):02x}" for c in color)


def _n(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _points(points, ox, oy):
    return " ".join(f"{_n(x - ox)},{_n(y - oy)}" for x, y in points)


def _shape(shape, ox, oy):
    title = f"<title>{escape(shape['name'])}</title>"
    kind = shape["kind"]
    if kind == "line":
        (ax, ay), (bx, by) = shape["a"], shape["b"]
        return (f'<line x1="{_n(ax - ox)}" y1="{_n(ay - oy)}" x2="{_n(bx - ox)}" y2="{_n(by - oy)}"'
                f' stroke="{_hex(shape["color"])}" stroke-width="{_n(shape["width"])}"'
                f' stroke-linecap="round">{title}</line>')
    if kind == "polygon":
        return (f'<polygon points="{_points(shape["points"], ox, oy)}" fill="{_hex(shape["color"])}"'
                f' stroke="{_hex(shape["outline"])}" stroke-width="1" stroke-linejoin="round">{title}</polygon>')
    if kind == "text":
        cx, cy = shape["center"][0] - ox, shape["center"][1] - oy
        weight = ' font-weight="bold"' if shape.get("bold") else ""
        return (f'<text x="{_n(cx)}" y="{_n(cy)}" transform="rotate({_n(shape["angle"])} {_n(cx)} {_n(cy)})"'
                f' font-family={quoteattr(shape["font"].capitalize())} font-size="{_n(shape["size"])}"{weight}'
                f' fill="{_hex(shape["color"])}" text-anchor="middle" dominant-baseline="central">'
                f'{title}{escape(shape["text"])}</text>')
    (cx, cy), r = shape["center"], shape["radius"]
    return (f'<circle cx="{_n(cx - ox)}" cy="{_n(cy - oy)}" r="{_n(r)}" fill="{_hex(shape["color"])}"'
            f' stroke="{_hex(shape["outline"])}" stroke-width="1">{title}</circle>')


def build_svg(shapes, title="Drawing", margin=2):
    """The shapes as an SVG document (text), just big enough for them plus margin pixels all round."""
    ox, oy, w, h = extent(shapes)
    # Lines stick out of their end points by half their width (round caps).
    pad = margin + max([s["width"] / 2 for s in shapes if s["kind"] == "line"] + [1.0])
    ox, oy, w, h = ox - pad, oy - pad, w + 2 * pad, h + 2 * pad
    body = "".join(_shape(s, ox, oy) for s in shapes)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(w)}" height="{_n(h)}"'
            f' viewBox="0 0 {_n(w)} {_n(h)}"><title>{escape(title)}</title>{body}</svg>')
