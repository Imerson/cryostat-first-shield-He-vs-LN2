#!/usr/bin/env bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc
for pair in stage1_shield_77K_v2:s1_77K_norm250 stage2_4K_from50K_v2:s2_from50K_norm250 stage2_4K_from77K_v2:s2_from77K_norm250; do
  S=/home/ubuntu/${pair%%:*}; D=/home/ubuntu/enclosure_variants/${pair##*:}
  LT=$(ls -d $S/[0-9]* | xargs -n1 basename | grep -E "^[0-9]+$" | sort -n | tail -1)
  rm -rf $D; mkdir -p $D; cp -r $S/0 $S/$LT $S/constant $S/system $D/; cp $S/extract_heat_loads.py $S/harness_kappa.py $S/finalize_case.py $D/
  cd $D; sed -i "s/^writeFormat .*/writeFormat ascii;/; s/^startFrom.*/startFrom       latestTime;/; s/^endTime.*/endTime         $((LT+600));/" system/controlDict
  for R in domain0 domain1; do rm -f constant/$R/F constant/$R/finalAgglom constant/$R/mapDist constant/$R/globalFaceFaces constant/$R/globalNumbering; nice -n 19 faceAgglomerate -region $R > log.fa_$R 2>&1; nice -n 19 viewFactorsGen -region $R > log.vfg_$R 2>&1; done
  python3 /home/ubuntu/normalise_F.py > log.normalise 2>&1
  nice -n 19 chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1
  python3 finalize_case.py > log.finalize 2>&1
  python3 /home/ubuntu/gate_check.py $D $((LT+600)) domain0,domain1 > GATE_CHECK_vacuum.txt 2>&1
  echo "[$(date +%H:%M:%S)] DONE $(basename $D) :: $(grep -E "radiation_on_cold|conduction_coax_CFD|^TOTAL" postProcessing/heatLoadSummary/heat_load_summary.dat | awk "{printf \"%s=%s \",\$1,\$2}")" >> /home/ubuntu/enclosure_variants/campaign.log
done
echo "[$(date +%H:%M:%S)] NORM_VARIANTS_DONE" >> /home/ubuntu/enclosure_variants/campaign.log
