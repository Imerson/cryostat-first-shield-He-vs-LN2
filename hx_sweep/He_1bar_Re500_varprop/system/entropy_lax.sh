#!/usr/bin/env bash
# Add-on: axial-conduction number (lambda_ax) + EGM entropy generation (Bejan, exergy)
# for the cold-plate cases. Computes entropy by a coded domainIntegrate on converged fields.
set -uo pipefail
CASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$CASE_DIR"
source system/metricConstants
KAP="$k_W_mK"; MU="$mu_Pa_s"; PR="$Pr"; DH="$Dh"; L="$Lflow"; T0=300
Re=$(grep -oE "Re: [0-9.eE+-]+" Nu_f_report.txt | head -1 | awk '{print $2}')

# --- axial conduction number (fluid axial conduction vs advection) ---
Pe=$(awk -v Re="$Re" -v Pr="$PR" 'BEGIN{print Re*Pr}')                 # axial Peclet (Dh)
PeL=$(awk -v Re="$Re" -v Pr="$PR" -v L="$L" -v Dh="$DH" 'BEGIN{print Re*Pr*L/Dh}')  # length-based
lax=$(awk -v Pe="$Pe" 'BEGIN{print 1.0/Pe}')                           # lambda_ax = 1/Pe

# --- EGM: coded domainIntegrate of thermal & viscous entropy generation ---
cat > /tmp/egm_$$.dict << EOF
FoamFile { version 2.0; format ascii; class dictionary; object egm; }
functions
{
  egm
  {
    type coded; libs (utilityFunctionObjects); name egm;
    codeExecute
    #{
        const volScalarField& T = mesh().lookupObject<volScalarField>("T");
        const volVectorField& U = mesh().lookupObject<volVectorField>("U");
        dimensionedScalar kappa("kappa", dimensionSet(1,1,-3,-1,0,0,0), $KAP);
        dimensionedScalar mu("mu", dimensionSet(1,-1,-1,0,0,0,0), $MU);
        volVectorField gradT(fvc::grad(T));
        volTensorField gradU(fvc::grad(U));
        volSymmTensorField S(symm(gradU));
        volScalarField sT(kappa*(gradT & gradT)/(T*T));
        volScalarField sV(2.0*mu*(S && S)/T);
        dimensionedScalar SgenT = fvc::domainIntegrate(sT);
        dimensionedScalar SgenV = fvc::domainIntegrate(sV);
        Info<< "EGM_THERMAL " << SgenT.value() << nl
            << "EGM_VISCOUS " << SgenV.value() << endl;
    #};
  }
}
EOF
postProcess -dict /tmp/egm_$$.dict -latestTime -fields "(T U)" > log.egm 2>&1 || true
rm -f /tmp/egm_$$.dict
ST=$(grep "EGM_THERMAL" log.egm | tail -1 | awk '{print $2}')
SV=$(grep "EGM_VISCOUS" log.egm | tail -1 | awk '{print $2}')
[ -z "$ST" ] && ST=0; [ -z "$SV" ] && SV=0
Stot=$(awk -v a="$ST" -v b="$SV" 'BEGIN{print a+b}')
BeS=$(awk -v a="$ST" -v t="$Stot" 'BEGIN{print (t>0)?a/t:0}')          # Bejan irreversibility (thermal fraction)
Exergy=$(awk -v t="$Stot" -v T0="$T0" 'BEGIN{print T0*t}')             # exergy destruction W (T0=300K)

# --- append to report ---
cat >> Nu_f_report.txt << EOR
--- axial conduction (fluid) ---
axial_Peclet_Dh: $Pe   axial_Peclet_L: $PeL   lambda_ax_1overPe: $lax   (<<1 => axial conduction negligible)
--- EGM / entropy generation (domain integral, converged fields) ---
Sgen_thermal_WperK: $ST   Sgen_viscous_WperK: $SV   Sgen_total_WperK: $Stot
Bejan_irreversibility_thermal_frac: $BeS   exergy_destruction_W(T0=300K): $Exergy
EOR
# --- write a small csv for the comparison ---
cat > egm_lax.csv << EOC
case,fluid,Re,axial_Peclet,lambda_ax,Sgen_thermal_WK,Sgen_viscous_WK,Sgen_total_WK,Bejan_irrev,exergy_W
$CASE_NAME,$FLUID_NAME,$Re,$Pe,$lax,$ST,$SV,$Stot,$BeS,$Exergy
EOC
echo "wrote egm_lax.csv  Sgen_T=$ST Sgen_V=$SV Be=$BeS lambda_ax=$lax"
