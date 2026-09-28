#!/usr/bin/env bash
# gen_enclosure_variants.sh -- build + run the Stage-1 enclosure sensitivity/verification variants.
#   mli   : MLI-equivalent emissivity (0.003) on all first-stage (cold) surfaces, 50 K and 77 K routes
#   epsLo : emissivities -50%  (warm 0.02 / cold 0.01)
#   epsHi : emissivities +50%  (warm 0.06 / cold 0.03)
#   agg400, agg800 : view-factor agglomeration refinement (nFacesInCoarsestLevel), 50 K route
# Each case runs from 0 to 2900 iterations (~2-3 min) then finalize_case.py + gate_check.py.
set -o pipefail
source /usr/lib/openfoam/openfoam2412/etc/bashrc
ROOT=/home/ubuntu/enclosure_variants; mkdir -p $ROOT
LOG=$ROOT/campaign.log; : > $LOG
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }

set_eps(){ # set_eps <case> <eps_warm> <eps_cold> <eps_coax>
  local D=$1 EW=$2 EC=$3 EX=$4
  for R in domain0 domain1; do
    F=$D/constant/$R/boundaryRadiationProperties
    python3 - "$F" "$EW" "$EC" "$EX" <<'PY'
import re,sys
f,ew,ec,ex=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
s=open(f).read()
def rep(m):
    name=m.group(1)
    if name in ('warmPlate','OVC'): e=ew
    elif 'coax' in name: e=ex
    else: e=ec           # shield, shield_slave, shield_bottom, coldPlate
    return f"{name} {{ type lookup; emissivity {e}; absorptivity {e}; }}"
s=re.sub(r"(\w+)\s*\{\s*type\s+lookup;\s*emissivity\s+[0-9.eE+-]+;\s*absorptivity\s+[0-9.eE+-]+;\s*\}",rep,s)
open(f,'w').write(s)
PY
  done
}

clone(){ # clone <src> <dst>
  local S=$1 D=$2; rm -rf $D; mkdir -p $D
  cp -r $S/0 $S/constant $S/system $D/
  cp $S/extract_heat_loads.py $S/harness_kappa.py $S/finalize_case.py $D/
  sed -i "s/^startFrom.*/startFrom       startTime;/; s/^endTime.*/endTime         2900;/" $D/system/controlDict
}

solve(){ # solve <case>
  local D=$1; cd $D
  chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1; rc=$?
  LT=$(ls -d [0-9]* | grep -E '^[0-9]+$' | sort -n | tail -1)
  python3 finalize_case.py > log.finalize 2>&1
  python3 /home/ubuntu/gate_check.py $D $LT domain0,domain1 > GATE_CHECK_vacuum.txt 2>&1 || true
  for t in $(ls -d [0-9]* | grep -E '^[0-9]+$' | sort -n | head -n -1); do [ "$t" != "0" ] && rm -rf "$t"; done
  gzip -f log.chtMultiRegionSimpleFoam
  log "DONE $(basename $D) rc=$rc t=$LT :: $(grep -E 'radiation_on_cold|conduction_coax_CFD|^TOTAL' postProcessing/heatLoadSummary/heat_load_summary.dat | awk '{printf "%s=%s ",$1,$2}')"
}

regen_vf(){ # regen_vf <case> <nFaces>
  local D=$1 N=$2; cd $D
  for R in domain0 domain1; do
    sed -i "s/nFacesInCoarsestLevel [0-9]*/nFacesInCoarsestLevel $N/" constant/$R/viewFactorsDict
    rm -f constant/$R/F constant/$R/finalAgglom constant/$R/mapDist constant/$R/globalFaceFaces constant/$R/globalNumbering
    faceAgglomerate -region $R > log.fa_$R 2>&1
    viewFactorsGen   -region $R > log.vfg_$R 2>&1
    log "  $(basename $D) $R: $(grep -ai 'coarse' log.vfg_$R | tail -1)"
  done
}

for T in 50 77; do
  S=/home/ubuntu/stage1_shield_${T}K_v2
  D=$ROOT/s1_${T}K_mli;   clone $S $D; set_eps $D 0.04 0.003 0.02; log "built $D"; solve $D
  D=$ROOT/s1_${T}K_epsLo; clone $S $D; set_eps $D 0.02 0.01 0.02;  log "built $D"; solve $D
  D=$ROOT/s1_${T}K_epsHi; clone $S $D; set_eps $D 0.06 0.03 0.02;  log "built $D"; solve $D
done
for N in 400 800; do
  S=/home/ubuntu/stage1_shield_50K_v2
  D=$ROOT/s1_50K_agg$N; clone $S $D; regen_vf $D $N; log "built $D"; solve $D
done
log "ENCLOSURE_CAMPAIGN_DONE"
