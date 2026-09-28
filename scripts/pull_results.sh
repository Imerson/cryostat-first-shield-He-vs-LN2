#!/usr/bin/env bash
# pull_results.sh -- copy finished VM cases into cfd_campaign/ (dictionaries, logs, postProcessing,
# metrics, gate checks; field data of the last time step is included but compressed binary).
# Usage: bash pull_results.sh [hx|enclosure|all]
set -o pipefail
P="/Users/imerson/Library/CloudStorage/OneDrive-Personal/Documents/Education Hub/15-Energy Systems/4-Year 3/4-Dissertation/8-Publlication/3-Pre-cooling paper v2 TSEP/cfd_campaign"
what="${1:-all}"
pull(){ # pull <vm_root> <local_subdir> <marker_file>
  local VMROOT=$1 LOCAL=$2 MARK=$3
  for c in $(multipass exec openfoam-vm -- bash -c "cd $VMROOT && for d in */; do [ -f \$d/$MARK ] && echo \${d%/}; done"); do
    if [ -f "$P/$LOCAL/$c/$MARK" ]; then echo "  $c already pulled"; continue; fi
    echo "  pulling $c"
    multipass exec openfoam-vm -- bash -c "cd $VMROOT && tar czf /tmp/$c.tgz --exclude='$c/constant/*/F' --exclude='$c/constant/*/polyMesh/*' --exclude='$c/constant/polyMesh/*' --exclude='$c/dynamicCode' $c"
    multipass transfer openfoam-vm:/tmp/$c.tgz "/tmp/$c.tgz" && tar xzf "/tmp/$c.tgz" -C "$P/$LOCAL/" && rm -f "/tmp/$c.tgz"
    multipass exec openfoam-vm -- rm -f /tmp/$c.tgz
  done
}
[ "$what" = hx ] || [ "$what" = all ] && { echo "== HX sweep =="; pull /home/ubuntu/hx_sweep hx_sweep metrics.csv; }
[ "$what" = enclosure ] || [ "$what" = all ] && { echo "== enclosure variants =="; pull /home/ubuntu/enclosure_variants enclosure_variants GATE_CHECK_full.txt; }
echo done
