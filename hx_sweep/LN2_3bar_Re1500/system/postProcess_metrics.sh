#!/usr/bin/env bash
# =============================================================================
# postProcess_metrics.sh  -- consolidated, corrected post-processing.
# Handles BOTH the Boussinesq (incompressible, kinematic p_rgh) and the
# variable-density compressible (static p in Pa, phi = mass flux) cases via the
# COMPRESSIBLE flag in metricConstants. Emits TRUE SI units for both, plus a
# one-row metrics.csv with a shared schema for cross-case comparison.
# Groups: Re, Nu, f(Darcy), Nu/Nu_inf, fRe/56.9, Nu/f, PF, Colburn-j, j/f, St,
#         Mouromtseff, eps-NTU, Graetz L_t/L, convective Bejan, pumping power,
#         energy-balance closure, density ratio / Boussinesq diagnostic, provenance.
# EGM entropy Bejan reported NA (out of scope, guideline 2.4).
# =============================================================================
set -uo pipefail
CASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$CASE_DIR"
source system/metricConstants
: "${COMPRESSIBLE:=0}"; : "${MOLWT_kg_mol:=0}"; : "${Rgas_J_molK:=8.314}"

get_last_val(){ printf "%s\n" "$@"|awk -F/ "{n=split(\$0,a,\"/\");print a[n-1]+0\"/\"\$0}"|sort -t/ -k1 -n|cut -d/ -f2-|xargs awk "NF && \$1 !~ /^#/ {v=\$NF} END{print v}"; }
get_last_col(){ local c="$1"; shift; printf "%s\n" "$@"|awk -F/ "{n=split(\$0,a,\"/\");print a[n-1]+0\"/\"\$0}"|sort -t/ -k1 -n|cut -d/ -f2-|xargs awk -v c="$c" "NF && \$1 !~ /^#/ {v=\$c} END{print v}"; }
fw_T(){ command -v postProcess >/dev/null 2>&1||return 0; local t; t="$(mktemp)"
  cat>"$t"<<EOD
FoamFile { version 2.0; format ascii; class dictionary; object fwT; }
functions{ outletFluxWeightedT{ type surfaceFieldValue; libs (fieldFunctionObjects);
  writeControl writeTime; log true; writeFields false; regionType patch;
  name outlet; operation weightedAverage; weightField phi; fields (T); } }
EOD
  postProcess -case "$CASE_DIR" -dict "$t" -latestTime -fields "(T phi)" >log.post_fwT 2>&1||true; rm -f "$t"; }

phiIn=$(get_last_val postProcessing/inletMassFlow/*/surfaceFieldValue.dat)
pin=$(get_last_val postProcessing/pInlet/*/surfaceFieldValue.dat)
pout=$(get_last_val postProcessing/pOutlet/*/surfaceFieldValue.dat)
Tin=$(get_last_val postProcessing/TInlet/*/surfaceFieldValue.dat)
ToutArea=$(get_last_val postProcessing/TOutlet/*/surfaceFieldValue.dat)
Tw=$(get_last_val postProcessing/TWall/*/surfaceFieldValue.dat)
fw_T; ToutBulk="$(get_last_col 2 postProcessing/outletFluxWeightedT/*/surfaceFieldValue*.dat 2>/dev/null||true)"; [ -z "$ToutBulk" ]&&ToutBulk="$ToutArea"

Q="$Qwall_W"; k="$k_W_mK"; rho="$rho_kg_m3"; cp="$cp_J_kgK"; mu="$mu_Pa_s"; Prv="$Pr"; beta="$beta_1_K"
Tb=$(awk -v a="$Tin" -v b="$ToutBulk" "BEGIN{print 0.5*(a+b)}")
dTcool=$(awk -v a="$Tin" -v b="$ToutBulk" "BEGIN{print b-a}")
dpRaw=$(awk -v p1="$pin" -v p2="$pout" "BEGIN{d=p1-p2;print (d<0?-d:d)}")

if [ "$COMPRESSIBLE" = "1" ]; then
  mdot=$(awk -v q="$phiIn" "BEGIN{print (q<0?-q:q)}")               # phi = mass flux
  rin=$(awk  -v p="$pin"  -v M="$MOLWT_kg_mol" -v R="$Rgas_J_molK" -v T="$Tin"      "BEGIN{print p*M/(R*T)}")
  rout=$(awk -v p="$pout" -v M="$MOLWT_kg_mol" -v R="$Rgas_J_molK" -v T="$ToutBulk" "BEGIN{print p*M/(R*T)}")
  rmean=$(awk -v a="$rin" -v b="$rout" "BEGIN{print 0.5*(a+b)}")
  rho_f="$rmean"; Qvol=$(awk -v m="$mdot" -v r="$rmean" "BEGIN{print m/r}")
  dP="$dpRaw"; rho_ratio=$(awk -v a="$rin" -v b="$rout" "BEGIN{print a/b}"); model="compressible variable-density (ideal-gas He; Boussinesq NOT assumed)"
else
  Qvol=$(awk -v q="$phiIn" "BEGIN{print (q<0?-q:q)}"); mdot=$(awk -v r="$rho" -v q="$Qvol" "BEGIN{print r*q}")
  rho_f="$rho"; dP=$(awk -v r="$rho" -v d="$dpRaw" "BEGIN{print r*d}"); rin="$rho"; rout="$rho"; rho_ratio=1
  model="incompressible Boussinesq (beta*dT<<1 valid)"
fi
Umean=$(awk -v q="$Qvol" -v A="$Acs" "BEGIN{print q/A}")

Re=$(awk -v m="$mdot" -v Dh="$Dh" -v A="$Acs" -v mu="$mu" "BEGIN{print m*Dh/(A*mu)}")
h=$(awk -v Q="$Q" -v A="$Aheated" -v Tw="$Tw" -v Tb="$Tb" "BEGIN{print Q/(A*(Tw-Tb))}")
Nu=$(awk -v h="$h" -v Dh="$Dh" -v k="$k" "BEGIN{print h*Dh/k}")
f=$(awk -v dp="$dP" -v Dh="$Dh" -v r="$rho_f" -v U="$Umean" -v L="$Lflow" "BEGIN{print 2*dp*Dh/(r*U*U*L)}")
St=$(awk -v Nu="$Nu" -v Re="$Re" -v Pr="$Prv" "BEGIN{print Nu/(Re*Pr)}")
j=$(awk -v St="$St" -v Pr="$Prv" "BEGIN{print St*(Pr^(2.0/3.0))}")
NuOverF=$(awk -v Nu="$Nu" -v f="$f" "BEGIN{print Nu/f}")
jOverF=$(awk -v j="$j" -v f="$f" "BEGIN{print j/f}")
PF=$(awk -v Nu="$Nu" -v f="$f" "BEGIN{print Nu/(f^(1.0/3.0))}")
Mo=$(awk -v k="$k" -v r="$rho" -v cp="$cp" -v mu="$mu" "BEGIN{print (k^0.6)*(r^0.8)*(cp^0.4)*(mu^(-0.4))}")
NTU=$(awk -v h="$h" -v A="$Aheated" -v m="$mdot" -v cp="$cp" "BEGIN{print h*A/(m*cp)}")
eps=$(awk -v n="$NTU" "BEGIN{print 1-exp(-n)}")
NuRatio=$(awk -v Nu="$Nu" "BEGIN{print Nu/3.61}")
fRe=$(awk -v f="$f" -v Re="$Re" "BEGIN{print f*Re}")
fReRatio=$(awk -v x="$fRe" "BEGIN{print x/56.9}")
Lt=$(awk -v Re="$Re" -v Pr="$Prv" -v Dh="$Dh" "BEGIN{print 0.05*Re*Pr*Dh}")
LtOverL=$(awk -v lt="$Lt" -v L="$Lflow" "BEGIN{print lt/L}")
alpha=$(awk -v k="$k" -v r="$rho_f" -v cp="$cp" "BEGIN{print k/(r*cp)}")
Be=$(awk -v dp="$dP" -v L="$Lflow" -v mu="$mu" -v al="$alpha" "BEGIN{print dp*L*L/(mu*al)}")
Wp=$(awk -v dp="$dP" -v q="$Qvol" "BEGIN{print dp*q}")
Qrem=$(awk -v m="$mdot" -v cp="$cp" -v dT="$dTcool" "BEGIN{print m*cp*dT}")
ebErr=$(awk -v qr="$Qrem" -v q="$Q" "BEGIN{print 100*(qr-q)/q}")
bdtWall=$(awk -v b="$beta" -v Tw="$Tw" -v Tb="$Tb" "BEGIN{print b*(Tw-Tb)}")
bdtCool=$(awk -v b="$beta" -v dT="$dTcool" "BEGIN{print b*dT}")
LT=$(ls -d [0-9]* 2>/dev/null|grep -E "^[0-9]+$"|sort -n|tail -1)
nCells=$(awk -F"nCells:" "/nCells:/{split(\$2,a,\" \");print a[1];exit}" constant/polyMesh/owner 2>/dev/null)
resU=$(grep -E "Solving for Ux" log.rerun_9p4 2>/dev/null|tail -1|sed -E "s/.*Initial residual = ([0-9.eE+-]+).*/\1/")
resT=$(grep -E "Solving for (T|h)" log.rerun_9p4 2>/dev/null|tail -1|sed -E "s/.*Initial residual = ([0-9.eE+-]+).*/\1/")
resP=$(grep -E "Solving for p_rgh" log.rerun_9p4 2>/dev/null|tail -1|sed -E "s/.*Initial residual = ([0-9.eE+-]+).*/\1/")

cat > Nu_f_report.txt << EOR
=====================================================================
 Consolidated metrics report  (true SI units, no manual corrections)
 Case:  $CASE_NAME      Fluid: $FLUID_NAME
 Geometry: mini-channel (Dh=${Dh} m = 10 mm; Kandlikar mini, NOT micro)
 Heat duty Q_wall: $Q W (matched-duty He-vs-N2 basis; Stage-1 load ~9.4 W)
 Flow model: $model
=====================================================================
--- raw CFD ---
Tin_K: $Tin  Tout_bulk_K: $ToutBulk  Tout_area_K: $ToutArea  Tw_K: $Tw  Tb_K: $Tb
dP_Pa(true): $dP  Umean_m_s: $Umean  mdot_kg_s: $mdot  Qvol_m3_s: $Qvol
rho_in: $rin  rho_out: $rout  rho_ratio_in_out: $rho_ratio
--- dimensional ---
h_W_m2K: $h  Wpump_W(true): $Wp  wall_superheat_Tw_minus_Tb_K: $(awk -v a="$Tw" -v b="$Tb" "BEGIN{print a-b}")
--- core dimensionless ---
Re: $Re  Nu: $Nu  f_Darcy: $f  Nu_over_f: $NuOverF  PF_Nu_f13: $PF
St: $St  Colburn_j: $j  j_over_f: $jOverF  Mouromtseff_Mo: $Mo
--- HX effectiveness (single-stream isothermal-wall limit) ---
NTU: $NTU  effectiveness_eps: $eps
--- validation (Shah & London, square duct, const-q: Nu_inf=3.61, fRe=56.9) ---
Nu_over_Nuinf: $NuRatio  fRe_Darcy: $fRe  fRe_over_56p9: $fReRatio
--- thermal entry length (Graetz) ---
Lt_m: $Lt  Lt_over_L: $LtOverL
--- convective Bejan ---
Convec_Bejan: $Be
--- entropy generation (EGM) ---
Irrev_Bejan: NA (out of scope, guideline 2.4)   W_exergy_loss_W: NA
--- density / Boussinesq diagnostic ---
rho_ratio_in_out: $rho_ratio  beta_dT_wall_to_bulk: $bdtWall  beta_dT_coolant: $bdtCool
--- energy balance ---
Q_removed_W: $Qrem  energy_balance_error_pct: $ebErr
--- provenance ---
solver: $( [ "$COMPRESSIBLE" = "1" ] && echo buoyantSimpleFoam || echo buoyantBoussinesqSimpleFoam ) (laminar)  OF: openfoam2412
nCells: $nCells  last_time: $LT  final_resid_Ux: $resU  T_or_h: $resT  p_rgh: $resP
Carnot_COP: $CarnotCOP
=====================================================================
EOR
cat > metrics.csv << EOC
case,fluid,model,Q_W,Re,Nu,f_Darcy,Nu_over_Nuinf,fRe,fRe_over_56p9,Nu_over_f,PF,St,j,j_over_f,Mo,NTU,eps,Lt_over_L,Be,Wpump_W,dP_Pa,h_W_m2K,mdot_kg_s,Tw_K,Tb_K,dTcool_K,rho_ratio,beta_dT_wall,Qrem_W,ebal_pct,nCells
$CASE_NAME,$FLUID_NAME,$( [ "$COMPRESSIBLE" = "1" ] && echo compressible || echo boussinesq ),$Q,$Re,$Nu,$f,$NuRatio,$fRe,$fReRatio,$NuOverF,$PF,$St,$j,$jOverF,$Mo,$NTU,$eps,$LtOverL,$Be,$Wp,$dP,$h,$mdot,$Tw,$Tb,$dTcool,$rho_ratio,$bdtWall,$Qrem,$ebErr,$nCells
EOC
echo "wrote $CASE_DIR/Nu_f_report.txt and metrics.csv"
