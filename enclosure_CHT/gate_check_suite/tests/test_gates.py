#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest entry point.

  pytest -q                      # runs the synthetic self-tests (no OpenFOAM)
  GATE_CONFIG=config/stage1_shield_77K.json pytest -q
                                 # additionally gate a REAL case: fails if any
                                 # gate is FAIL

CI usage: point GATE_CONFIG at each stage config in a matrix; a FAIL fails CI.
"""

import os
import sys
import json
import tempfile
import shutil

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import selftest as st                      # noqa: E402
from gatecheck import runner               # noqa: E402


def _run_synth(**kw):
    d = tempfile.mkdtemp(prefix="gatepy_")
    try:
        st.build_case(d, **kw)
        return runner.run(st.make_cfg(d), quiet=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _status(results, gid):
    return next((r.status for r in results if r.id == gid), None)


def test_healthy_case_no_fail():
    results, counts = _run_synth()
    assert counts["FAIL"] == 0


def test_conservation_gates_pass_when_balanced():
    results, _ = _run_synth()
    assert _status(results, "G1.1") == "PASS"
    assert _status(results, "G1.2") == "PASS"


def test_pressure_bug_detected():
    results, _ = _run_synth(pressure=101325.0)
    assert _status(results, "G4.1") == "FAIL"
    assert _status(results, "G4.2") == "FAIL"
    assert _status(results, "G4.3") == "FAIL"


def test_radiation_sink_detected():
    rad = {"warmPlate": 3.0, "shield": -1.5, "coldPlate": -1.5,
           "shield_bottom": 0.0, "domain1_to_coax_L1": -3.945,
           "domain1_to_coax_L2": 0.0}
    results, _ = _run_synth(rad=rad)
    assert _status(results, "G1.2") == "FAIL"


@pytest.mark.skipif(not os.environ.get("GATE_CONFIG"),
                    reason="set GATE_CONFIG to gate a real case")
def test_real_case_passes():
    cfg = os.environ["GATE_CONFIG"]
    if not os.path.isabs(cfg):
        cfg = os.path.join(ROOT, cfg)
    results, counts = runner.run(cfg, quiet=True)
    fails = [(r.id, r.name, r.detail) for r in results if r.status == "FAIL"]
    assert not fails, "gate FAILs: %s" % fails


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
