"""Write simple 3D scenes of spheres, tubes and small meshes as binary glTF (.glb).

Parts are plain dicts in world coordinates (metres, y up), matching glTF:
  {"kind": "sphere", "name", "center": (x, y, z), "radius", "color"}
  {"kind": "tube", "name", "a": (x, y, z), "b": (x, y, z), "radius", "color"}
  {"kind": "mesh", "name", "positions", "normals", "triangles", "color"}
A mesh may also have "texcoords" (u, v per vertex, v = 0 at the top of the
image) and "image" (PNG bytes, with alpha): the image, tinted by the colour,
is then its surface, blended over what's behind it.
Colours are RGB tuples in 0..1 as shown on screen (sRGB).  Each part becomes a
named node.
"""

import json
import struct

import numpy as np

from geometry import normalize

SPHERE_SEGMENTS = 32
TUBE_SEGMENTS = 16


def sphere(center, radius, segments=SPHERE_SEGMENTS):
    """(positions, normals, triangle indices) of a UV sphere."""
    rings = segments // 2
    theta = np.linspace(0, np.pi, rings + 1)[:, None]
    phi = np.linspace(0, 2 * np.pi, segments + 1)[None, :]
    normals = np.stack([np.sin(theta) * np.cos(phi),
                        np.cos(theta) * np.ones_like(phi),
                        -np.sin(theta) * np.sin(phi)], axis=-1).reshape(-1, 3)
    tris = []
    for r in range(rings):
        for s in range(segments):
            a, b = r * (segments + 1) + s, (r + 1) * (segments + 1) + s
            if r > 0:
                tris.append((a, b, a + 1))
            if r < rings - 1:
                tris.append((a + 1, b, b + 1))
    return np.asarray(center) + radius * normals, normals, np.array(tris)


def tube(a, b, radius, segments=TUBE_SEGMENTS):
    """(positions, normals, triangle indices) of an open cylinder from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    axis = normalize(b - a)
    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = normalize(np.cross(axis, helper))
    v = np.cross(axis, u)
    angles = np.linspace(0, 2 * np.pi, segments + 1)[:, None]
    ring = np.cos(angles) * u + np.sin(angles) * v
    positions = np.concatenate([a + radius * ring, b + radius * ring])
    n = segments + 1
    tris = [t for s in range(segments) for t in ((s, s + 1, n + s), (s + 1, n + s + 1, n + s))]
    return positions, np.concatenate([ring, ring]), np.array(tris)


def build_glb(parts, rotation=None):
    """The parts as a binary glTF file (bytes), optionally rotated by a 3x3 matrix."""
    blob = bytearray()
    views, accessors, meshes, nodes, materials, images = [], [], [], [], [], []
    material_of, image_of = {}, {}

    def add_view(data, target=None):
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        views.append(view)
        blob.extend(data + b"\0" * (-len(data) % 4))
        return len(views) - 1

    def add(array, target, component, kind, minmax=False):
        acc = {"bufferView": add_view(array.tobytes(), target), "componentType": component,
               "count": len(array), "type": kind}
        if minmax:
            acc["min"], acc["max"] = array.min(axis=0).tolist(), array.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    for part in parts:
        if part["kind"] == "sphere":
            pos, nrm, tris = sphere(part["center"], part["radius"])
        elif part["kind"] == "mesh":
            pos, nrm, tris = (np.asarray(part[k]) for k in ("positions", "normals", "triangles"))
        else:
            if np.linalg.norm(np.subtract(part["b"], part["a"])) < 1e-6:
                continue
            pos, nrm, tris = tube(part["a"], part["b"], part["radius"])
        if rotation is not None:
            pos, nrm = pos @ rotation.T, nrm @ rotation.T
        color = tuple(round(float(c) ** 2.2, 4) for c in part["color"])  # glTF colours are linear
        image = part.get("image")
        if image is not None and image not in image_of:
            image_of[image] = len(images)
            images.append({"bufferView": add_view(image), "mimeType": "image/png"})
        key = (color, image)
        if key not in material_of:
            material_of[key] = len(materials)
            pbr = {"baseColorFactor": [*color, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.5}
            material = {"pbrMetallicRoughness": pbr}
            if image is not None:
                pbr["baseColorTexture"] = {"index": image_of[image]}  # texture i uses image i
                material["alphaMode"] = "BLEND"
            materials.append(material)
        attributes = {"POSITION": add(pos.astype(np.float32), 34962, 5126, "VEC3", True),
                      "NORMAL": add(nrm.astype(np.float32), 34962, 5126, "VEC3")}
        if image is not None:
            attributes["TEXCOORD_0"] = add(np.asarray(part["texcoords"], np.float32), 34962, 5126, "VEC2")
        primitive = {
            "attributes": attributes,
            "indices": add(tris.astype(np.uint16).ravel(), 34963, 5123, "SCALAR"),
            "material": material_of[key],
        }
        meshes.append({"name": part["name"], "primitives": [primitive]})
        nodes.append({"name": part["name"], "mesh": len(meshes) - 1})

    doc = {
        "asset": {"version": "2.0", "generator": "Stickman Poser"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    if images:
        doc["images"] = images
        doc["textures"] = [{"source": i, "sampler": 0} for i in range(len(images))]
        # Linear filtering with mipmaps, clamped at the edges.
        doc["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}]
    text = json.dumps(doc, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    chunks = (struct.pack("<II", len(text), 0x4E4F534A) + text
              + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))
    return struct.pack("<III", 0x46546C67, 2, 12 + len(chunks)) + chunks
