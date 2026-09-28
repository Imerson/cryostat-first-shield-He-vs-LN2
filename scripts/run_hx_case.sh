#!/usr/bin/env bash
# run_hx_case.sh <case_dir>  -- solve one HX sweep case, then post-process (metrics, y+, wall profiles).
set -o pipefail
source /usr/lib/openfoam/openfoam2412/etc/bashrc
D="$1"; cd "$D" || exit 1
NAME=$(basename "$D")
APP=$(grep -E "^application" system/controlDict | awk '{print $2}' | tr -d ';')
echo "[$(date +%H:%M:%S)] START $NAME ($APP)"
if [ ! -f constant/polyMesh/owner ]; then blockMesh > log.blockMesh 2>&1; fi
checkMesh > log.checkMesh 2>&1 || true
$APP > log.rerun_9p4 2>&1
rc=$?
echo "[$(date +%H:%M:%S)] SOLVED $NAME rc=$rc  $(grep ExecutionTime log.rerun_9p4 | tail -1)"
# post: metrics (mixing-cup outlet T), y+ (turbulent), wall-T profile along heated-wall centreline
bash system/postProcess_metrics.sh > log.metrics 2>&1
if grep -q "TURBULENT=1" system/metricConstants; then
  $APP -postProcess -func yPlus -latestTime > log.yPlus 2>&1 || true
  grep -A3 "yPlus" log.yPlus | grep -E "min|max|average" | tail -3 > yplus_summary.txt || true
fi
LT=$(ls -d [0-9]* | grep -E '^[0-9]+$' | sort -n | tail -1)
cat > system/sampleWall <<EOF
FoamFile { version 2.0; format ascii; class dictionary; object sampleWall; }
type sets; libs (sampling); interpolationScheme cellPoint; setFormat raw; writeControl writeTime;
fields (T);
sets
(
    wallCentre  { type uniform; axis x; start (0.0005 0.005 0.0004);  end (0.2995 0.005 0.0004);  nPoints 300; }
    wallCentre2 { type uniform; axis x; start (0.0005 0.023 0.0004);  end (0.2995 0.023 0.0004);  nPoints 300; }
    midChan     { type uniform; axis x; start (0.0005 0.005 0.005);   end (0.2995 0.005 0.005);   nPoints 300; }
    profileZ    { type uniform; axis z; start (0.15 0.005 0.0);       end (0.15 0.005 0.01);      nPoints 200; }
);
EOF
postProcess -func sampleWall -latestTime > log.sample 2>&1 || true
# thin the case: keep only 0 and last time
for t in $(ls -d [0-9]* | grep -E '^[0-9]+$' | sort -n | head -n -1); do [ "$t" != "0" ] && rm -rf "$t"; done
gzip -f log.rerun_9p4
echo "[$(date +%H:%M:%S)] DONE  $NAME  $(head -2 metrics.csv | tail -1 | cut -d, -f1-8)"
