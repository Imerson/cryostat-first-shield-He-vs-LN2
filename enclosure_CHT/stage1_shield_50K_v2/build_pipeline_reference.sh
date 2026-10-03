#!/bin/bash
# Coarse re-mesh for viewFactor:
#   - OVC at (0 0) refinement, shield at (1 1) to properly disconnect domain1/domain2
#   - 30x30 base mesh, coax searchableBox refinement for topoSet detection
#   - Creates all per-region constant files (thermophysicalProperties, radiationProperties=viewFactor, etc.)
#   - Runs faceAgglomerate + viewFactorsGen + solver queue

source /usr/lib/openfoam/openfoam2412/etc/bashrc

LOG=/home/ubuntu/remesh_coarse.log
echo "$(date): Starting coarse re-mesh for viewFactor" | tee $LOG

# ─── helper: write snappyHexMeshDict ─────────────────────────────────────────
# Shield uses level (1 1) + faceZone to create proper mesh disconnection
# OVC uses (0 0) — only needs wall patch, not a domain separator
write_snappy() {
    local DIR=$1 REFINE_LVL=$2
    local LOC_X=$3 LOC_Y=$4 LOC_Z=$5
    local MGCELLS=$6
    local CX1=$7  CY1=$8  BSZ1=$9  H1=${10}
    local CX2=${11} CY2=${12} BSZ2=${13} H2=${14}
    local CX3=${15} CY3=${16} BSZ3=${17} H3=${18}
    local CX4=${19} CY4=${20} BSZ4=${21} H4=${22}
    local CHIP_CX=${23:-} CHIP_CY=${24:-} CHIP_BSZ=${25:-} CHIP_H=${26:-} CHIP_REFINE=${27:-2}

    local X1min X1max Y1min Y1max
    X1min=$(python3 -c "print(f'{$CX1-$BSZ1:.5f}')"); X1max=$(python3 -c "print(f'{$CX1+$BSZ1:.5f}')")
    Y1min=$(python3 -c "print(f'{$CY1-$BSZ1:.5f}')"); Y1max=$(python3 -c "print(f'{$CY1+$BSZ1:.5f}')")
    X2min=$(python3 -c "print(f'{$CX2-$BSZ2:.5f}')"); X2max=$(python3 -c "print(f'{$CX2+$BSZ2:.5f}')")
    Y2min=$(python3 -c "print(f'{$CY2-$BSZ2:.5f}')"); Y2max=$(python3 -c "print(f'{$CY2+$BSZ2:.5f}')")
    X3min=$(python3 -c "print(f'{$CX3-$BSZ3:.5f}')"); X3max=$(python3 -c "print(f'{$CX3+$BSZ3:.5f}')")
    Y3min=$(python3 -c "print(f'{$CY3-$BSZ3:.5f}')"); Y3max=$(python3 -c "print(f'{$CY3+$BSZ3:.5f}')")
    X4min=$(python3 -c "print(f'{$CX4-$BSZ4:.5f}')"); X4max=$(python3 -c "print(f'{$CX4+$BSZ4:.5f}')")
    Y4min=$(python3 -c "print(f'{$CY4-$BSZ4:.5f}')"); Y4max=$(python3 -c "print(f'{$CY4+$BSZ4:.5f}')")

    local CHIP_GEOM="" CHIP_REF_REGION=""
    if [ -n "$CHIP_CX" ]; then
        local CXmin CXmax CYmin CYmax
        CXmin=$(python3 -c "print(f'{$CHIP_CX-$CHIP_BSZ:.5f}')"); CXmax=$(python3 -c "print(f'{$CHIP_CX+$CHIP_BSZ:.5f}')")
        CYmin=$(python3 -c "print(f'{$CHIP_CY-$CHIP_BSZ:.5f}')"); CYmax=$(python3 -c "print(f'{$CHIP_CY+$CHIP_BSZ:.5f}')")
        CHIP_GEOM="    chip_box { type searchableBox; min ($CXmin $CYmin 0); max ($CXmax $CYmax $CHIP_H); }"
        CHIP_REF_REGION="        chip_box { mode inside; levels ((1E15 $CHIP_REFINE)); }"
    fi

    cat > $DIR/system/snappyHexMeshDict << EOF
FoamFile { version 2.0; format ascii; class dictionary; object snappyHexMeshDict; }
castellatedMesh true; snap true; addLayers false;
geometry
{
    OVC.stl    { type triSurfaceMesh; name OVC; }
    shield.stl { type triSurfaceMesh; name shield; }
    coax_box_L1 { type searchableBox; min ($X1min $Y1min 0); max ($X1max $Y1max $H1); }
    coax_box_L2 { type searchableBox; min ($X2min $Y2min 0); max ($X2max $Y2max $H2); }
    coax_box_L3 { type searchableBox; min ($X3min $Y3min 0); max ($X3max $Y3max $H3); }
    coax_box_L4 { type searchableBox; min ($X4min $Y4min 0); max ($X4max $Y4max $H4); }
$CHIP_GEOM
}
castellatedMeshControls
{
    maxLocalCells 500000; maxGlobalCells $MGCELLS; minRefinementCells 5;
    nCellsBetweenLevels 3; resolveFeatureAngle 30;
    features ();
    refinementSurfaces
    {
        OVC    { level (0 0); patchInfo { type wall; } }
        shield { level (1 1); faceType boundary; faceZone shield; patchInfo { type wall; } }
    }
    refinementRegions
    {
        coax_box_L1 { mode inside; levels ((1E15 $REFINE_LVL)); }
        coax_box_L2 { mode inside; levels ((1E15 $REFINE_LVL)); }
        coax_box_L3 { mode inside; levels ((1E15 $REFINE_LVL)); }
        coax_box_L4 { mode inside; levels ((1E15 $REFINE_LVL)); }
$CHIP_REF_REGION
    }
    locationInMesh ($LOC_X $LOC_Y $LOC_Z);
    allowFreeStandingZoneFaces true;
}
snapControls
{
    nSmoothPatch 3; tolerance 2.0; nSolveIter 30; nRelaxIter 5;
    nFeatureSnapIter 10; implicitFeatureSnap true; explicitFeatureSnap false;
    multiRegionFeatureSnap false;
}
addLayersControls { relativeSizes true; layers {}; expansionRatio 1.0; finalLayerThickness 0.3; minThickness 0.1; }
meshQualityControls
{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80;
    minFlatness 0.5; minVol 1e-13; minTetQuality -1e30; minArea -1; minTwist 0.02;
    minDeterminant 0.001; minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1;
    nSmoothScale 4; errorReduction 0.75;
}
debug 0; mergeTolerance 1e-6;
EOF
}

# ─── helper: add viewFactorWall inGroups — skip coax_L* patches ──────────────
add_viewfactor_groups() {
    local BFILE=$1
    python3 << PYEOF
import re
def upgrade_ingroups(text):
    lines = text.split('\n')
    result = []
    current_patch_name = ''
    keywords = {'FoamFile','version','format','arch','class','location',
                'object','boundary','nFaces','startFace','type','inGroups',
                'polyBoundaryMesh','physicalType'}
    for line in lines:
        stripped = line.strip()
        if (re.match(r'^\s+\w[\w_]*\s*$', line) and
            stripped not in keywords and
            not stripped.startswith('//') and
            not stripped.startswith('*') and
            not stripped.isdigit()):
            current_patch_name = stripped
        if 'inGroups' in line and '1(wall)' in line:
            if 'coax_L' not in current_patch_name:
                line = line.replace('1(wall)', '2(wall viewFactorWall)')
        result.append(line)
    return '\n'.join(result)

txt = open('$BFILE').read()
new_txt = upgrade_ingroups(txt)
open('$BFILE', 'w').write(new_txt)
print(f"Updated {sum(1 for l in new_txt.split(chr(10)) if 'viewFactorWall' in l)} patches with viewFactorWall")
PYEOF
}

# ─── helper: update domain2/qr — coax_L* interfaces → calculated ─────────────
update_qr_coax() {
    local QR_FILE=$1
    python3 << PYEOF
import re
txt = open('$QR_FILE').read()
def replace_coax_qr(text):
    lines = text.split('\n')
    result = []
    patch_name = ''
    in_coax_block = False
    brace_count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if re.match(r'\s+domain2_to_coax_L\d+\s*$', line):
            patch_name = stripped
            result.append(line)
            i += 1
            continue
        if patch_name and stripped == '{':
            in_coax_block = True
            brace_count = 1
            result.append(line)
            result.append('        type            calculated;')
            result.append('        value           uniform 0;')
            i += 1
            patch_name = ''
            continue
        if in_coax_block:
            if '{' in stripped: brace_count += 1
            if '}' in stripped:
                brace_count -= 1
                if brace_count <= 0:
                    in_coax_block = False
                    result.append(line)
            i += 1
            continue
        result.append(line)
        i += 1
    return '\n'.join(result)
new_txt = replace_coax_qr(txt)
open('$QR_FILE', 'w').write(new_txt)
print("Updated domain2 qr: coax_L interfaces → calculated")
PYEOF
}

# ─── helper: create per-region constant files (thermophysical, radiation) ─────
# viewFactor radiation model — NOT fvDOM
# The top-level constant/radiationProperties has fvDOM but is ignored by
# chtMultiRegionSimpleFoam; each region needs its own radiationProperties.
setup_domain_files() {
    local DIR=$1
    local T_WARM=$2 T_COLD=$3 T_INIT=$4

    for REG in domain1 domain2; do
        [ ! -d $DIR/constant/$REG ] && continue

        # thermophysicalProperties — helium gas (same for both fluid regions)
        cat > $DIR/constant/$REG/thermophysicalProperties << EOF
FoamFile { version 2.0; format ascii; class dictionary; location "constant/$REG"; object thermophysicalProperties; }
thermoType
{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}
mixture
{
    specie      { molWeight 4.003; }
    thermodynamics { Cp 5193; Hf 0; }
    transport   { mu 1.0e-08; Pr 0.67; }
}
EOF

        # turbulenceProperties — laminar (no convection at cryogenic vacuum)
        cat > $DIR/constant/$REG/turbulenceProperties << EOF
FoamFile { version 2.0; format ascii; class dictionary; location "constant/$REG"; object turbulenceProperties; }
simulationType  laminar;
EOF

        # radiationProperties — viewFactor (reads precomputed F matrix from constant/$REG/F)
        cat > $DIR/constant/$REG/radiationProperties << EOF
FoamFile { version 2.0; format ascii; class dictionary; location "constant/$REG"; object radiationProperties; }
radiation       on;
radiationModel  viewFactor;
viewFactorCoeffs
{
    nBands              1;
    smoothing           false;
    constantEmissivity  true;
    nFacesInCoarsestLevel 100;
    featureAngle        10;
}
absorptionEmissionModel constantAbsorptionEmission;
constantAbsorptionEmissionCoeffs
{
    absorptivity    absorptivity    [0 -1 0 0 0 0 0] 0.0;
    emissivity      emissivity      [0 -1 0 0 0 0 0] 0.0;
    E               E               [1 -1 -3 0 0 0 0] 0;
}
scatterModel    none;
sootModel       none;
EOF

        # boundaryRadiationProperties — emissivities read by greyDiffusiveRadiation BC
        # Include all possible patch names; OpenFOAM uses only those present in the boundary
        cat > $DIR/constant/$REG/boundaryRadiationProperties << EOF
FoamFile { version 2.0; format ascii; class dictionary; location "constant/$REG"; object boundaryRadiationProperties; }
// warm surfaces (OVC, warmPlate, farfield if present)
warmPlate   { type lookup; emissivity 0.04; absorptivity 0.04; }
OVC         { type lookup; emissivity 0.04; absorptivity 0.04; }
OVC_slave   { type lookup; emissivity 0.04; absorptivity 0.04; }
farfield    { type lookup; emissivity 0.04; absorptivity 0.04; }
// cold surfaces (coldPlate, shield)
coldPlate   { type lookup; emissivity 0.02; absorptivity 0.02; }
shield      { type lookup; emissivity 0.02; absorptivity 0.02; }
shield_slave { type lookup; emissivity 0.02; absorptivity 0.02; }
// chip (stage4 only)
domain2_to_chip { type lookup; emissivity 0.02; absorptivity 0.02; }
EOF

    done
    echo "  domain1/domain2 constant files written (viewFactor)" | tee -a $LOG

    # 0/domain1/T — create from scratch with correct patches
    # domain1 = outer annular fluid between OVC and shield
    # OVC patch: T_WARM; shield_slave patch: T_COLD; coldPlate/warmPlate: fixed T
    mkdir -p $DIR/0/domain1
    python3 << PYEOF
import re, os

# Read actual domain1 boundary to get patch names
bfile = '$DIR/constant/domain1/polyMesh/boundary'
try:
    txt = open(bfile).read()
    # Extract patch names and types
    patches = re.findall(r'\n    (\w[\w_]*)\s*\n\s*\{[^}]*type\s+(\w+)', txt)
except:
    patches = []

lines = []
lines.append('FoamFile { version 2.0; format ascii; class volScalarField; location "0/domain1"; object T; }')
lines.append('dimensions      [0 0 0 1 0 0 0];')
lines.append(f'internalField   uniform $T_INIT;')
lines.append('boundaryField')
lines.append('{')

for pname, ptype in patches:
    if ptype == 'empty': continue
    # Determine temperature BC based on patch name
    plow = pname.lower()
    if 'warm' in plow:
        bc = f'    {pname} {{ type fixedValue; value uniform $T_WARM; }}'
    elif 'cold' in plow:
        bc = f'    {pname} {{ type fixedValue; value uniform $T_COLD; }}'
    elif 'ovc' in plow and 'slave' not in plow:
        bc = f'    {pname} {{ type fixedValue; value uniform $T_WARM; }}'
    elif 'ovc_slave' in plow:
        bc = f'    {pname} {{ type fixedValue; value uniform $T_WARM; }}'
    elif 'shield' in plow:
        bc = f'    {pname} {{ type fixedValue; value uniform $T_COLD; }}'
    elif 'farfield' in plow:
        bc = f'    {pname} {{ type zeroGradient; }}'
    elif 'coax' in plow or 'chip' in plow:
        bc = f'    {pname} {{ type zeroGradient; }}'
    else:
        bc = f'    {pname} {{ type zeroGradient; }}'
    lines.append(bc)

lines.append('}')
open('$DIR/0/domain1/T', 'w').write('\n'.join(lines) + '\n')
print(f"Written 0/domain1/T with {len(patches)} patches")
PYEOF

    # 0/domain1/qr — rebuild from actual patch list
    python3 << PYEOF
import re

bfile = '$DIR/constant/domain1/polyMesh/boundary'
try:
    txt = open(bfile).read()
    patches = re.findall(r'\n    (\w[\w_]*)\s*\n\s*\{[^}]*type\s+(\w+)', txt)
except:
    patches = []

lines = []
lines.append('FoamFile { version 2.0; format ascii; class volScalarField; location "0/domain1"; object qr; }')
lines.append('dimensions      [1 0 -3 0 0 0 0];')
lines.append('internalField   uniform 0;')
lines.append('boundaryField')
lines.append('{')

for pname, ptype in patches:
    if ptype == 'empty': continue
    plow = pname.lower()
    # Skip coax/chip CHT interfaces (no radiation from domain1)
    if 'coax' in plow or ('chip' in plow and 'domain2' in plow):
        lines.append(f'    {pname} {{ type calculated; value uniform 0; }}')
        continue
    # All other domain1 patches are radiation surfaces
    if 'warm' in plow or 'ovc' in plow or 'farfield' in plow:
        emiss = '0.04'
    else:
        emiss = '0.02'  # coldPlate, shield_slave, etc.
    lines.append(f'    {pname}')
    lines.append('    {')
    lines.append('        type            greyDiffusiveRadiation;')
    lines.append('        emissivityMode  lookup;')
    lines.append(f'        emissivity      uniform {emiss};')
    lines.append('        value           uniform 0;')
    lines.append('    }')

lines.append('}')
open('$DIR/0/domain1/qr', 'w').write('\n'.join(lines) + '\n')
print(f"Written 0/domain1/qr with {len(patches)} patches")
PYEOF
    echo "  0/domain1/T and qr written" | tee -a $LOG
}

# ─── main remesh function ─────────────────────────────────────────────────────
remesh_case() {
    local NAME=$1
    local NX=$2 NY=$3 NZ=$4
    local COAX_REFINE=$5
    local LOC_X=$6 LOC_Y=$7 LOC_Z=$8
    local MAXCELLS=$9
    local C1X=${10} C1Y=${11} C1BSZ=${12} C1H=${13}
    local C2X=${14} C2Y=${15} C2BSZ=${16} C2H=${17}
    local C3X=${18} C3Y=${19} C3BSZ=${20} C3H=${21}
    local C4X=${22} C4Y=${23} C4BSZ=${24} C4H=${25}
    local COAX_R=${26}
    local T_WARM=${27} T_COLD=${28} T_INIT=${29} K_EFF=${30}
    local HAS_CHIP=${31:-}

    local DIR=/home/ubuntu/$NAME
    echo "" | tee -a $LOG
    echo "$(date): === $NAME ===" | tee -a $LOG
    cd $DIR

    # 1. Update blockMeshDict
    sed -i "s/(60 60 28)/($NX $NY $NZ)/;s/(60 60 20)/($NX $NY $NZ)/" system/blockMeshDict
    echo "  blockMeshDict: ($NX $NY $NZ)" | tee -a $LOG

    # 2. Write snappyHexMeshDict with shield (1 1) for proper domain separation
    if [ -n "$HAS_CHIP" ]; then
        write_snappy $DIR $COAX_REFINE $LOC_X $LOC_Y $LOC_Z $MAXCELLS \
            $C1X $C1Y $C1BSZ $C1H  $C2X $C2Y $C2BSZ $C2H \
            $C3X $C3Y $C3BSZ $C3H  $C4X $C4Y $C4BSZ $C4H \
            0.0 0.0 0.005 0.0095 2
    else
        write_snappy $DIR $COAX_REFINE $LOC_X $LOC_Y $LOC_Z $MAXCELLS \
            $C1X $C1Y $C1BSZ $C1H  $C2X $C2Y $C2BSZ $C2H \
            $C3X $C3Y $C3BSZ $C3H  $C4X $C4Y $C4BSZ $C4H
    fi
    echo "  snappyHexMeshDict written (shield level 1 1)" | tee -a $LOG

    # 3. Clean old mesh dirs (keep 0/ — qr and other ICs survive)
    rm -rf constant/polyMesh constant/domain1 constant/domain2
    for L in 1 2 3 4; do rm -rf constant/coax_L${L}; done
    rm -rf constant/coax_lumped
    [ -n "$HAS_CHIP" ] && rm -rf constant/chip
    find . -maxdepth 1 -regex '\./[1-9][0-9]*\(\.[0-9]*\)?' -type d -exec rm -rf {} + 2>/dev/null || true
    echo "  old mesh cleaned" | tee -a $LOG

    # 4. blockMesh
    echo "  blockMesh..." | tee -a $LOG
    blockMesh > log.blockMesh_coarse 2>&1 || { echo "  blockMesh FAILED"; tail -5 log.blockMesh_coarse | tee -a $LOG; return 1; }

    # 5. snappyHexMesh
    echo "  snappyHexMesh..." | tee -a $LOG
    snappyHexMesh -overwrite > log.snappyHexMesh_coarse 2>&1
    SHM_EXIT=$?
    if [ $SHM_EXIT -ne 0 ] && [ $SHM_EXIT -ne 134 ]; then
        echo "  snappyHexMesh FAILED (exit $SHM_EXIT)" | tee -a $LOG
        tail -8 log.snappyHexMesh_coarse | tee -a $LOG
        return 1
    fi
    # Verify shield created proper faceZone (connectivity check)
    NREGIONS=$(grep 'global region' log.snappyHexMesh_coarse | grep -oP '\d+ region' | head -1)
    echo "  snappyHexMesh: $NREGIONS connected" | tee -a $LOG

    # 6. Update base polyMesh boundary: add viewFactorWall to main patches
    add_viewfactor_groups constant/polyMesh/boundary 2>&1 | tee -a $LOG

    # 7. topoSet
    echo "  topoSet..." | tee -a $LOG
    topoSet > log.topoSet_coarse 2>&1
    echo "  topoSet exit $?" | tee -a $LOG

    # 8. regionProperties
    if [ -n "$HAS_CHIP" ]; then
        cat > constant/regionProperties << 'EOF'
FoamFile { version 2.0; format ascii; class dictionary; location "constant"; object regionProperties; }
regions ( fluid ( domain1 domain2 ) solid ( coax_L1 coax_L2 coax_L3 coax_L4 chip ) );
EOF
    else
        cat > constant/regionProperties << 'EOF'
FoamFile { version 2.0; format ascii; class dictionary; location "constant"; object regionProperties; }
regions ( fluid ( domain1 domain2 ) solid ( coax_L1 coax_L2 coax_L3 coax_L4 ) );
EOF
    fi

    echo "  splitMeshRegions..." | tee -a $LOG
    splitMeshRegions -cellZones -overwrite > log.splitMeshRegions_coarse 2>&1
    rm -rf constant/polyMesh
    # Report regions found
    grep -E 'Region.*Cells|Region.*Zone.*Name' log.splitMeshRegions_coarse | head -20 | tee -a $LOG

    # Report domain boundary face counts (key indicator of correct split)
    for REG in domain1 domain2; do
        if [ -d constant/$REG ]; then
            BFACES=$(python3 -c "
import re
try:
    txt = open('constant/$REG/polyMesh/boundary').read()
    faces = sum(int(x) for x in re.findall(r'nFaces\s+(\d+)', txt))
    patches = re.findall(r'\n    (\w[\w_]*)\s*\n\s*\{', txt)
    print(f'$REG: {faces} boundary faces, patches: {\" \".join(patches)}')
except Exception as e: print(f'$REG check failed: {e}')
" 2>/dev/null)
            echo "  $BFACES" | tee -a $LOG
        else
            echo "  $REG: MISSING after split" | tee -a $LOG
        fi
    done

    # 9. Per-region constant files: thermophysicalProperties, radiationProperties (viewFactor), etc.
    setup_domain_files $DIR $T_WARM $T_COLD $T_INIT

    # 10. coax thermophysicalProperties (NbTi with effective kappa)
    for L in 1 2 3 4; do
        [ ! -d constant/coax_L${L} ] && continue
        cat > constant/coax_L${L}/thermophysicalProperties << EOF
FoamFile { version 2.0; format ascii; class dictionary; location "constant/coax_L${L}"; object thermophysicalProperties; }
thermoType { type heSolidThermo; mixture pureMixture; transport constIso; thermo hConst; equationOfState rhoConst; specie specie; energy sensibleEnthalpy; }
mixture { specie { molWeight 92.9; } transport { kappa ${K_EFF}; } thermodynamics { Hf 0; Cp 300; } equationOfState { rho 8600; } }
EOF
    done

    # chip thermophysicalProperties (Si, stage4 only)
    if [ -n "$HAS_CHIP" ] && [ -d constant/chip ]; then
        cat > constant/chip/thermophysicalProperties << 'EOF'
FoamFile { version 2.0; format ascii; class dictionary; location "constant/chip"; object thermophysicalProperties; }
thermoType { type heSolidThermo; mixture pureMixture; transport constIso; thermo hConst; equationOfState rhoConst; specie specie; energy sensibleEnthalpy; }
mixture { specie { molWeight 28.09; } transport { kappa 100; } thermodynamics { Hf 0; Cp 700; } equationOfState { rho 2329; } }
EOF
    fi

    # 11. 0/domain2/T (domain2 = inner fluid, inside shield)
    if [ -n "$HAS_CHIP" ]; then
        CHIP_T_BC="    domain2_to_chip { type calculated; value uniform ${T_INIT}; }"
    else
        CHIP_T_BC=""
    fi
    cat > 0/domain2/T << EOF
FoamFile { version 2.0; format ascii; class volScalarField; location "0/domain2"; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform ${T_INIT};
boundaryField
{
    coldPlate   { type fixedValue; value uniform ${T_COLD}; }
    warmPlate   { type fixedValue; value uniform ${T_WARM}; }
    shield      { type fixedValue; value uniform ${T_COLD}; }
    domain2_to_coax_L1 { type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; kappaMethod fluidThermo; value uniform ${T_INIT}; }
    domain2_to_coax_L2 { type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; kappaMethod fluidThermo; value uniform ${T_INIT}; }
    domain2_to_coax_L3 { type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; kappaMethod fluidThermo; value uniform ${T_INIT}; }
    domain2_to_coax_L4 { type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; kappaMethod fluidThermo; value uniform ${T_INIT}; }
${CHIP_T_BC}
}
EOF

    # 12. 0/coax_L*/T
    for L in 1 2 3 4; do
        mkdir -p 0/coax_L${L}
        cat > 0/coax_L${L}/T << EOF
FoamFile { version 2.0; format ascii; class volScalarField; location "0/coax_L${L}"; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform ${T_INIT};
boundaryField
{
    coax_L${L}_to_domain2 { type compressible::turbulentTemperatureCoupledBaffleMixed; Tnbr T; kappaMethod solidThermo; value uniform ${T_INIT}; }
}
EOF
    done

    # chip/T (stage4)
    if [ -n "$HAS_CHIP" ] && [ -d constant/chip ]; then
        mkdir -p 0/chip
        cat > 0/chip/T << EOF
FoamFile { version 2.0; format ascii; class volScalarField; location "0/chip"; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform ${T_INIT};
boundaryField
{
    coldPlate       { type fixedValue; value uniform ${T_COLD}; }
    chip_to_domain2 { type calculated; value uniform ${T_INIT}; }
}
EOF
    fi

    # 13. Update domain2/qr: coax_L* → calculated (not radiation surfaces)
    if [ -f 0/domain2/qr ]; then
        update_qr_coax 0/domain2/qr 2>&1 | tee -a $LOG
    fi

    # 14. Update per-region boundary inGroups after split
    for REG in domain1 domain2; do
        [ -f constant/$REG/polyMesh/boundary ] && add_viewfactor_groups constant/$REG/polyMesh/boundary 2>&1 | tee -a $LOG
    done

    echo "$(date): $NAME DONE" | tee -a $LOG
}

# ─── Run all 6 cases ──────────────────────────────────────────────────────────
# locationInMesh is inside domain2 (inner fluid, near center)
# domain1 (outer annular) will appear as a disconnected region

# stage1: base 30x30x14, coax_refine 2, coax r=10mm (effective k)
remesh_case stage1_shield_77K_v2 30 30 14 2  0.008 0.003 0.170  500000 \
    0.13936 0.05630 0.030 0.335  -0.05630 0.13936 0.030 0.335  -0.13936 -0.05630 0.030 0.335  0.05630 -0.13936 0.030 0.335 \
    0.01  300 77 188.5  0.006277

remesh_case stage1_shield_50K_v2 30 30 14 2  0.008 0.003 0.170  500000 \
    0.13936 0.05630 0.030 0.335  -0.05630 0.13936 0.030 0.335  -0.13936 -0.05630 0.030 0.335  0.05630 -0.13936 0.030 0.335 \
    0.01  300 50 175  0.005832

# stage2: base 30x30x14, coax_refine 2, coax r=10mm
remesh_case stage2_4K_from77K_v2 30 30 14 2  0.008 0.003 0.123  500000 \
    0.10180 0.04113 0.025 0.2447  -0.04113 0.10180 0.025 0.2447  -0.10180 -0.04113 0.025 0.2447  0.04113 -0.10180 0.025 0.2447 \
    0.01  77 4 40.5  0.001336

remesh_case stage2_4K_from50K_v2 30 30 14 2  0.008 0.003 0.123  500000 \
    0.10180 0.04113 0.025 0.2447  -0.04113 0.10180 0.025 0.2447  -0.10180 -0.04113 0.025 0.2447  0.04113 -0.10180 0.025 0.2447 \
    0.01  50 4 27  0.000890

# stage3: base 30x30x10, coax_refine 3, coax r=2.11mm
remesh_case stage3_100mK_v2 30 30 10 3  0.005 0.003 0.076  200000 \
    0.06240 0.02521 0.015 0.1498  -0.02521 0.06240 0.015 0.1498  -0.06240 -0.02521 0.015 0.1498  0.02521 -0.06240 0.015 0.1498 \
    0.00211  4 0.1 2.05  4.3e-4

# stage4: base 30x30x10, coax_refine 2, coax r=2.11mm, HAS_CHIP=1
remesh_case stage4_10mK_v2 30 30 10 2  0.003 0.003 0.048  200000 \
    0.03941 0.01592 0.012 0.0948  -0.01592 0.03941 0.012 0.0948  -0.03941 -0.01592 0.012 0.0948  0.01592 -0.03941 0.012 0.0948 \
    0.00211  0.1 0.01 0.055  4.3e-4  1

echo "" | tee -a $LOG
echo "$(date): All re-meshes done. Starting viewFactor computation..." | tee -a $LOG

# ─── Phase 2: faceAgglomerate + viewFactorsGen ────────────────────────────────
for CASE in stage1_shield_77K_v2 stage1_shield_50K_v2 stage2_4K_from77K_v2 stage2_4K_from50K_v2 stage3_100mK_v2 stage4_10mK_v2; do
    echo "" | tee -a $LOG
    echo "$(date): === viewFactor: $CASE ===" | tee -a $LOG
    cd /home/ubuntu/$CASE
    for REGION in domain1 domain2; do
        [ ! -d constant/$REGION ] && continue
        cat > constant/$REGION/viewFactorsDict << EOF
FoamFile { version 2.0; format ascii; class dictionary; object viewFactorsDict; }
writeViewFactorMatrix   true;
writeFacesAgglomeration true;
nAgglomeratingIter      6;
EOF
        rm -f constant/$REGION/F constant/$REGION/mapDist constant/$REGION/finalAgglom
        rm -f constant/$REGION/globalFaceFaces constant/$REGION/globalNumbering
        echo "  [$REGION] faceAgglomerate..." | tee -a $LOG
        faceAgglomerate -region $REGION > log.faceAgglom_${REGION} 2>&1
        FA=$?; echo "  [$REGION] faceAgglomerate exit $FA" | tee -a $LOG
        [ $FA -ne 0 ] && [ $FA -ne 134 ] && tail -3 log.faceAgglom_${REGION} | tee -a $LOG

        echo "  [$REGION] viewFactorsGen..." | tee -a $LOG
        viewFactorsGen -region $REGION > log.viewFactorsGen_${REGION} 2>&1
        VFG=$?; echo "  [$REGION] viewFactorsGen exit $VFG" | tee -a $LOG
        grep -i 'coarse' log.viewFactorsGen_${REGION} | tail -1 | tee -a $LOG
        if [ -f constant/$REGION/F ]; then
            F_BYTES=$(wc -c < constant/$REGION/F)
            echo "  [$REGION] F: $F_BYTES bytes" | tee -a $LOG
            [ "$F_BYTES" -lt 500 ] && echo "  [$REGION] WARNING: F appears empty" | tee -a $LOG
        else
            echo "  [$REGION] F: MISSING — viewFactorsGen may have OOM'd" | tee -a $LOG
        fi
    done
done

echo "" | tee -a $LOG
echo "$(date): viewFactor phase done. Launching solver queue..." | tee -a $LOG

# ─── Phase 3: solver queue ────────────────────────────────────────────────────
/home/ubuntu/run_queue_v2_scaled.sh >> /home/ubuntu/run_v2_cases.log 2>&1

echo "$(date): ALL DONE" | tee -a $LOG
