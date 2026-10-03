#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ofparse.py -- dependency-free OpenFOAM reader for the gate-check suite.

Reads ascii + binary OpenFOAM files (no OpenFOAM install needed). The mesh /
field readers are adapted from the project's own extract_heat_loads.py so the
suite parses exactly the same artifacts the heat-load extractor already trusts.

Public helpers
--------------
read_points / read_faces / read_boundary   polyMesh geometry
read_field_boundary                          boundaryField values of a field
read_internal_scalar                         internalField of a volScalarField
face_area / patch_zextent                    geometry helpers
read_dict_scalar                             pull "key  value;" from any dict
patch_area_map                               {patch: area} for a region
"""

import os
import re
import struct
import math


# --------------------------------------------------------------------------- #
# header / cursor
# --------------------------------------------------------------------------- #
def _read_header(raw):
    head = raw[:2000].decode("latin-1", "replace")
    fmt = "ascii"
    m = re.search(r"format\s+(\w+)\s*;", head)
    if m:
        fmt = m.group(1)
    lab, sca = 4, 8
    a = re.search(r'arch\s+"[^"]*label=(\d+)\s*;\s*scalar=(\d+)', head)
    if a:
        lab = int(a.group(1)) // 8
        sca = int(a.group(2)) // 8
    return fmt, lab, sca


class _Cur:
    def __init__(self, buf, pos=0):
        self.b = buf
        self.p = pos

    def skip_ws(self):
        b, n = self.b, len(self.b)
        while self.p < n:
            c = b[self.p]
            if c in (32, 9, 10, 13):
                self.p += 1
            elif c == 0x2F and self.p + 1 < n and b[self.p + 1] == 0x2F:
                while self.p < n and b[self.p] not in (10, 13):
                    self.p += 1
            elif c == 0x2F and self.p + 1 < n and b[self.p + 1] == 0x2A:
                self.p += 2
                while self.p + 1 < n and not (b[self.p] == 0x2A and b[self.p + 1] == 0x2F):
                    self.p += 1
                self.p += 2
            else:
                break

    def peek(self):
        return self.b[self.p] if self.p < len(self.b) else -1

    def token(self):
        self.skip_ws()
        b, n = self.b, len(self.b)
        s = self.p
        while self.p < n:
            c = b[self.p]
            if c in (32, 9, 10, 13, 59, 123, 125, 40, 41):
                break
            self.p += 1
        return b[s:self.p].decode("latin-1")

    def expect(self, ch):
        self.skip_ws()
        if self.p < len(self.b) and self.b[self.p] == ord(ch):
            self.p += 1
            return True
        return False

    def read_int(self):
        self.skip_ws()
        b, n = self.b, len(self.b)
        s = self.p
        if self.p < n and b[self.p] in (43, 45):
            self.p += 1
        while self.p < n and 48 <= b[self.p] <= 57:
            self.p += 1
        return int(b[s:self.p])


def _read_scalar_list(cur, fmt, sbytes):
    n = cur.read_int()
    cur.skip_ws()
    cur.expect("(")
    if fmt == "binary":
        raw = cur.b[cur.p:cur.p + n * sbytes]
        cur.p += n * sbytes
        vals = list(struct.unpack("<%dd" % n, raw)) if sbytes == 8 else \
            list(struct.unpack("<%df" % n, raw))
        cur.expect(")")
        return vals
    vals = []
    for _ in range(n):
        cur.skip_ws()
        s = cur.p
        b = cur.b
        while cur.p < len(b) and b[cur.p] not in (32, 9, 10, 13, 41):
            cur.p += 1
        vals.append(float(b[s:cur.p]))
    cur.expect(")")
    return vals


# --------------------------------------------------------------------------- #
# mesh
# --------------------------------------------------------------------------- #
def read_points(path):
    raw = open(path, "rb").read()
    fmt, lab, sca = _read_header(raw)
    i = raw.find(b"// *")
    i = raw.find(b"\n", i) if i >= 0 else 0
    cur = _Cur(raw, i)
    n = cur.read_int()
    cur.skip_ws(); cur.expect("(")
    if fmt == "binary":
        block = raw[cur.p:cur.p + n * 3 * sca]
        flat = struct.unpack("<%dd" % (n * 3), block)
        return [(flat[k * 3], flat[k * 3 + 1], flat[k * 3 + 2]) for k in range(n)]
    pts = []
    for _ in range(n):
        cur.skip_ws(); cur.expect("(")
        x = float(cur.token()); y = float(cur.token()); z = float(cur.token())
        cur.expect(")")
        pts.append((x, y, z))
    return pts


def read_faces(path):
    raw = open(path, "rb").read()
    fmt, lab, sca = _read_header(raw)
    i = raw.find(b"// *")
    i = raw.find(b"\n", i) if i >= 0 else 0
    cur = _Cur(raw, i)
    if fmt == "binary":
        n1 = cur.read_int(); cur.skip_ws(); cur.expect("(")
        off = list(struct.unpack("<%di" % n1, raw[cur.p:cur.p + n1 * lab])) if lab == 4 \
            else list(struct.unpack("<%dq" % n1, raw[cur.p:cur.p + n1 * lab]))
        cur.p += n1 * lab; cur.expect(")")
        n2 = cur.read_int(); cur.skip_ws(); cur.expect("(")
        dat = list(struct.unpack("<%di" % n2, raw[cur.p:cur.p + n2 * lab])) if lab == 4 \
            else list(struct.unpack("<%dq" % n2, raw[cur.p:cur.p + n2 * lab]))
        cur.p += n2 * lab; cur.expect(")")
        return [dat[off[k]:off[k + 1]] for k in range(len(off) - 1)]
    nf = cur.read_int(); cur.skip_ws(); cur.expect("(")
    faces = []
    for _ in range(nf):
        k = cur.read_int(); cur.skip_ws(); cur.expect("(")
        verts = [cur.read_int() for _ in range(k)]
        cur.expect(")")
        faces.append(verts)
    return faces


def read_boundary(path):
    txt = open(path, "rb").read().decode("latin-1", "replace")
    body = txt[txt.find("// *"):]
    patches = []
    for m in re.finditer(r"(\w+)\s*\{([^}]*?)\}", body, re.DOTALL):
        name, blk = m.group(1), m.group(2)
        nf = re.search(r"nFaces\s+(\d+)\s*;", blk)
        sf = re.search(r"startFace\s+(\d+)\s*;", blk)
        tp = re.search(r"type\s+(\S+)\s*;", blk)
        if nf and sf:
            patches.append(dict(name=name, nFaces=int(nf.group(1)),
                                startFace=int(sf.group(1)),
                                type=tp.group(1) if tp else ""))
    return patches


# --------------------------------------------------------------------------- #
# fields
# --------------------------------------------------------------------------- #
def read_field_boundary(path):
    """Return {patch: value} where value is float (uniform), list (nonuniform)
    or None (vector / unreadable). Mirrors extract_heat_loads.read_field_boundary."""
    raw = open(path, "rb").read()
    fmt, lab, sca = _read_header(raw)
    i = raw.find(b"boundaryField")
    if i < 0:
        return {}
    cur = _Cur(raw, i + len("boundaryField"))
    cur.skip_ws(); cur.expect("{")
    out = {}
    while True:
        cur.skip_ws()
        if cur.peek() == ord("}") or cur.peek() == -1:
            break
        name = cur.token()
        cur.skip_ws(); cur.expect("{")
        value = None
        btype = None
        while True:
            cur.skip_ws()
            if cur.peek() == ord("}"):
                cur.p += 1
                break
            key = cur.token()
            cur.skip_ws()
            nxt = cur.token()
            if key == "type":
                btype = nxt
                cur.skip_ws(); cur.expect(";")
                continue
            if nxt == "uniform":
                cur.skip_ws()
                if cur.peek() == ord("("):
                    cur.expect("(")
                    while cur.peek() not in (ord(")"), -1):
                        cur.p += 1
                    cur.expect(")")
                    val = None
                else:
                    val = float(cur.token())
                cur.skip_ws(); cur.expect(";")
                if key == "value":
                    value = val
            elif nxt == "nonuniform":
                listtok = cur.token()
                if "vector" in listtok:
                    n = cur.read_int(); cur.skip_ws(); cur.expect("(")
                    if fmt == "binary":
                        cur.p += n * 3 * sca
                    else:
                        for _ in range(n * 3):
                            cur.token()
                    cur.expect(")")
                    vals = None
                else:
                    vals = _read_scalar_list(cur, fmt, sca)
                cur.skip_ws(); cur.expect(";")
                if key == "value":
                    value = vals
            else:
                b = cur.b
                while cur.p < len(b) and b[cur.p] != 59:
                    cur.p += 1
                cur.expect(";")
        out[name] = (value if value is not None else btype)
    return out


def read_internal_scalar(path):
    """Return (kind, data) for internalField of a volScalarField.
    kind='uniform' -> data=float ; kind='nonuniform' -> data=list[float]."""
    raw = open(path, "rb").read()
    fmt, lab, sca = _read_header(raw)
    i = raw.find(b"internalField")
    if i < 0:
        return ("none", None)
    cur = _Cur(raw, i + len("internalField"))
    tok = cur.token()
    if tok == "uniform":
        return ("uniform", float(cur.token()))
    # nonuniform List<scalar>
    # advance to the list count
    vals = _read_scalar_list(cur, fmt, sca)
    return ("nonuniform", vals)


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #
def face_area(face_idx, pts):
    p = [pts[k] for k in face_idx]
    if len(p) < 3:
        return 0.0
    sx = sy = sz = 0.0
    p0 = p[0]
    for i in range(1, len(p) - 1):
        ax, ay, az = p[i][0] - p0[0], p[i][1] - p0[1], p[i][2] - p0[2]
        bx, by, bz = p[i + 1][0] - p0[0], p[i + 1][1] - p0[1], p[i + 1][2] - p0[2]
        sx += ay * bz - az * by
        sy += az * bx - ax * bz
        sz += ax * by - ay * bx
    return 0.5 * math.sqrt(sx * sx + sy * sy + sz * sz)


def patch_zextent(face_idxs, pts):
    zs = [pts[k][2] for f in face_idxs for k in f]
    return (max(zs) - min(zs)) if zs else 0.0


def patch_area_map(region_dir, region):
    """Return {patch: (area, nFaces, faceIdxList)} for a region's polyMesh."""
    mesh = os.path.join(region_dir, "constant", region, "polyMesh")
    pts = read_points(os.path.join(mesh, "points"))
    faces = read_faces(os.path.join(mesh, "faces"))
    bnd = read_boundary(os.path.join(mesh, "boundary"))
    out = {}
    for pb in bnd:
        s, e = pb["startFace"], pb["startFace"] + pb["nFaces"]
        fidx = faces[s:e]
        areas = [face_area(f, pts) for f in fidx]
        out[pb["name"]] = dict(area=sum(areas), nFaces=pb["nFaces"],
                               faces=fidx, areas=areas, type=pb["type"])
    return pts, out


# --------------------------------------------------------------------------- #
# dict scalars
# --------------------------------------------------------------------------- #
def read_dict_scalar(path, key):
    """Pull a numeric 'key  value;' from any OpenFOAM dictionary. Returns float
    or None."""
    try:
        txt = open(path, "rb").read().decode("latin-1", "replace")
    except OSError:
        return None
    m = re.search(r"\b" + re.escape(key) + r"\s+([-+0-9.eE]+)\s*;", txt)
    return float(m.group(1)) if m else None


def read_solid_transport(path):
    """Read a solid thermophysicalProperties transport block.
    Returns ('constIso', kappa_float) or ('polynomial', [c0,c1,...]) or
    (transport_type, None) if unreadable."""
    try:
        txt = open(path, "rb").read().decode("latin-1", "replace")
    except OSError:
        return (None, None)
    tm = re.search(r"transport\s+(\w+)", txt)
    ttype = tm.group(1) if tm else None
    pm = re.search(r"kappaCoeffs\s*<\d+>\s*\(([^)]*)\)", txt)
    if pm:
        coeffs = [float(x) for x in re.findall(r"[-+0-9.eE]+", pm.group(1))]
        return ("polynomial", coeffs)
    k = read_dict_scalar(path, "kappa")
    return (ttype or "constIso", k)


def integrate_kappa(transport, Tc, Th):
    """integral_{Tc}^{Th} kappa(T) dT for a parsed solid transport tuple."""
    ttype, data = transport
    if data is None:
        return None
    if ttype == "polynomial":
        s = 0.0
        for i, c in enumerate(data):
            s += c / (i + 1) * (Th ** (i + 1) - Tc ** (i + 1))
        return s
    # constant isotropic kappa
    return data * (Th - Tc)


def list_time_dirs(case):
    times = []
    for d in os.listdir(case):
        if os.path.isdir(os.path.join(case, d)) and re.fullmatch(r"\d+(\.\d+)?", d):
            times.append(d)
    return sorted(times, key=float)
