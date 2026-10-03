#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logparse.py -- pull SIMPLE convergence history from a solver log.

chtMultiRegionSimpleFoam writes, per outer iteration, lines like
    Time = 1
    ...
    DICPCG:  Solving for h, Initial residual = 3.1e-2, Final residual = 8e-9, ...
    GAMG:    Solving for p_rgh, Initial residual = 1.2e-1, Final residual = 9e-7, ...

We record, for every field, the INITIAL residual at each Time (the meaningful
SIMPLE residual). The gate uses the last value and the trend.
"""

import re

_TIME = re.compile(r"^Time\s*=\s*([0-9.eE+-]+)")
_RES = re.compile(r"Solving for (\w+),\s*Initial residual = ([0-9.eE+-]+),"
                  r"\s*Final residual = ([0-9.eE+-]+)")
_BOUND = re.compile(r"(\w+)\s*:.*?min(?:imum)?\s*[:=]?\s*([0-9.eE+-]+)"
                    r".*?max(?:imum)?\s*[:=]?\s*([0-9.eE+-]+)", re.I)


def parse_residuals(log_path):
    """Return dict field -> list of initial residuals (one per Time step seen)."""
    hist = {}
    cur_time = None
    seen_this_time = set()
    try:
        f = open(log_path, "r", errors="replace")
    except OSError:
        return {}
    with f:
        for line in f:
            mt = _TIME.match(line)
            if mt:
                cur_time = mt.group(1)
                seen_this_time = set()
                continue
            mr = _RES.search(line)
            if mr:
                fld = mr.group(1)
                # only the FIRST solve of each field per Time (the outer residual)
                if fld in seen_this_time:
                    continue
                seen_this_time.add(fld)
                try:
                    hist.setdefault(fld, []).append(float(mr.group(2)))
                except ValueError:
                    pass
    return hist


def last_residuals(log_path):
    """field -> last initial residual."""
    hist = parse_residuals(log_path)
    return {k: v[-1] for k, v in hist.items() if v}


def n_time_steps(log_path):
    n = 0
    try:
        for line in open(log_path, "r", errors="replace"):
            if _TIME.match(line):
                n += 1
    except OSError:
        return 0
    return n


def parse_checkmesh(log_path):
    """Return dict with maxNonOrtho, maxSkewness, mesh_ok (bool) if found."""
    out = {}
    try:
        txt = open(log_path, "r", errors="replace").read()
    except OSError:
        return out
    m = re.search(r"Max(?:imum)? non-orthogonality\s*=\s*([0-9.eE+-]+)", txt)
    if m:
        out["maxNonOrtho"] = float(m.group(1))
    m = re.search(r"Max(?:imum)? skewness\s*=\s*([0-9.eE+-]+)", txt)
    if m:
        out["maxSkewness"] = float(m.group(1))
    out["mesh_ok"] = ("Mesh OK" in txt)
    return out
