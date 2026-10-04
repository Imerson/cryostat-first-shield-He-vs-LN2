#!/usr/bin/env python3
"""Reciprocity and closure audit of an OpenFOAM viewFactor matrix.
usage: reciprocity.py <case> <region>
Reads constant/<region>/{polyMesh,finalAgglom,globalFaceFaces,F} (ASCII), rebuilds the coarse-face areas by
summing the fine-face areas of each agglomeration, and reports
  closure  : row sums  sum_j F_ij
  reciprocity: sum_ij |A_i F_ij - A_j F_ji| / sum_ij A_i F_ij  over all stored pairs
  conservation: sum_i A_i (1 - sum_j F_ij) / sum_i A_i   (area-weighted closure defect)"""
import sys, re, numpy as np
def strip_header(s):
    i = s.index('}', s.index('FoamFile')) + 1
    s = s[i:]
    s = re.sub(r'//.*', '', s)
    return s
def tokens(s):
    return re.findall(r'[()]|[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?', s)
def parse_list_of_lists(path, numeric=float):
    """OpenFOAM ascii List<List<T>>: N ( n(a b ..) n(c ..) ... )  (inner count may be absent)"""
    s = strip_header(open(path, encoding='latin-1').read()); t = tokens(s)
    out = []; i = 0
    # outer count
    while t[i] != '(': i += 1
    i += 1
    cur = None
    while i < len(t):
        tk = t[i]
        if tk == '(':
            cur = []
        elif tk == ')':
            if cur is None: break          # closing outer
            out.append(cur); cur = None
        else:
            if cur is not None: cur.append(numeric(tk))
            # else: an inner count before '(' -> ignore
        i += 1
    return out
def read_points(path):
    pts = parse_list_of_lists(path, float); return np.array(pts)
def read_faces(path):
    return parse_list_of_lists(path, int)
def read_boundary(path):
    s = strip_header(open(path, encoding='latin-1').read())
    pats = []
    for m in re.finditer(r'(\w+)\s*\{([^}]*)\}', s):
        body = m.group(2)
        nf = re.search(r'nFaces\s+(\d+)', body); sf = re.search(r'startFace\s+(\d+)', body)
        if nf and sf: pats.append((m.group(1), int(nf.group(1)), int(sf.group(1))))
    return pats
def face_area(f, P):
    p = P[f]; c = p.mean(axis=0); a = np.zeros(3)
    for k in range(len(f)):
        a += np.cross(p[k] - c, p[(k + 1) % len(f)] - c)
    return 0.5 * np.linalg.norm(a)
case, reg = sys.argv[1], sys.argv[2]
d = f'{case}/constant/{reg}'
P = read_points(f'{d}/polyMesh/points'); Fc = read_faces(f'{d}/polyMesh/faces'); pats = read_boundary(f'{d}/polyMesh/boundary')
agg = parse_list_of_lists(f'{d}/finalAgglom', int)
assert len(agg) == len(pats), (len(agg), len(pats))
A = []; 
for (name, nf, sf), ag in zip(pats, agg):
    if len(ag) == 0: continue
    nc = max(ag) + 1; a = np.zeros(nc)
    for k, c in enumerate(ag): a[c] += face_area(Fc[sf + k], P)
    A.extend(a.tolist())
A = np.array(A)
gff = parse_list_of_lists(f'{d}/globalFaceFaces', int); F = parse_list_of_lists(f'{d}/F', float)
assert len(F) == len(A) == len(gff), (len(F), len(A), len(gff))
rows = np.array([sum(r) for r in F])
# reciprocity over stored pairs
num = den = 0.0; nmiss = 0; nb = {i: {j: F[i][k] for k, j in enumerate(gff[i])} for i in range(len(F))}
for i in range(len(F)):
    for k, j in enumerate(gff[i]):
        fij = F[i][k]; fji = nb[j].get(i)
        if fji is None: nmiss += 1; fji = 0.0
        num += abs(A[i] * fij - A[j] * fji); den += A[i] * fij
print(f"{case.split('/')[-1]:22s} {reg}: ncoarse={len(A)} area={A.sum():.4f} m2 | row sums mean {rows.mean():.4f} min {rows.min():.3f} max {rows.max():.3f} | "
      f"area-weighted closure defect {np.sum(A*(1-rows))/A.sum()*100:+.2f} % | reciprocity error sum|AiFij-AjFji|/sum AiFij = {num/den*100:.2f} % (pairs missing partner: {nmiss})")
