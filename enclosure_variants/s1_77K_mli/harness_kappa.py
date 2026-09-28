#!/usr/bin/env python3
"""harness_kappa.py -- effective T-dependent conductivity for lumped coax.
Each modeled coax represents n_k real cables. k_eff(T)=(n_k/A_model) Sum A_i k_i(T).
Materials k(T) from NIST cryogenics (log10 polynomial form). VERIFY flags where noted.
"""
import math, os, sys
# ---- material k(T) = 10^(sum a_n (log10 T)^n) [W/mK] ----
MAT = {
 # NIST 304 stainless steel (cryo), valid ~1-300 K  -- VERIFY:False (NIST)
 'SS304':[-1.4087,1.3982,0.2543,-0.6260,0.2334,0.4256,-0.4658,0.1650,-0.0199],
 # PTFE / Teflon (NIST), valid 4-300 K  -- VERIFY:False (NIST)
 'PTFE' :[2.7380,-30.677,89.430,-136.99,124.69,-69.556,23.320,-4.3135,0.33829],
 # cupronickel C7150 outer (Raicu 2025 measured) -- VERIFY:False
 'CuNi_out':[-3.198399,20.49947,-66.11415,117.6898,-121.4773,76.21467,-28.74949,5.984756,-0.5266892],
 # Ag-plated cupronickel center (Raicu 2025 measured) -- VERIFY:False
 'CuNi_in' :[-2.750003,25.84512,-74.18405,113.5856,-96.84387,46.38328,-11.82451,1.321682,-0.02456645],
}
def kmat(m,T): x=math.log10(T); c=MAT[m]; return 10**sum(c[n]*x**n for n in range(9))
def intk(m,Tc,Th,n=4000):
    h=(Th-Tc)/n; s=0.5*(kmat(m,Tc)+kmat(m,Th))
    for i in range(1,n): s+=kmat(m,Tc+i*h)
    return s*h
# ---- cable types: component (material, cross-section area m^2) ----
CABLES = {
 'SS_UT085':[('SS304',1.585e-6,'outer'),('PTFE',2.001e-6,'dielectric'),('SS304',0.205e-6,'center')],
 'CuNi_SC086':[('CuNi_out',0.2389e-6,'outer'),('PTFE',0.3098e-6,'dielectric'),('CuNi_in',0.0324e-6,'center')],
}
def Q_cable(cab,Tc,Th,L): return sum(A*intk(mat,Tc,Th) for mat,A,_ in CABLES[cab])/L
def keff(cab,nk,Amodel,T): return (nk/Amodel)*sum(A*kmat(mat,T) for mat,A,_ in CABLES[cab])
def fit_poly(xs,ys,order=3):
    # least squares normal equations, pure python
    m=order+1; X=[[x**j for j in range(m)] for x in xs]
    XtX=[[sum(X[r][i]*X[r][j] for r in range(len(xs))) for j in range(m)] for i in range(m)]
    Xty=[sum(X[r][i]*ys[r] for r in range(len(xs))) for i in range(m)]
    # gaussian elimination
    A=[row[:]+[Xty[i]] for i,row in enumerate(XtX)]
    for c in range(m):
        p=max(range(c,m),key=lambda r:abs(A[r][c])); A[c],A[p]=A[p],A[c]
        for r in range(m):
            if r!=c:
                f=A[r][c]/A[c][c]
                for k in range(c,m+1): A[r][k]-=f*A[c][k]
    coef=[A[i][m]/A[i][i] for i in range(m)]
    err=max(abs((sum(coef[j]*x**j for j in range(m))-y)/y) for x,y in zip(xs,ys) if y)
    return coef,err

if __name__=='__main__':
    # hand-check for stage2 coax: Tc=4, Th=50, L from mesh, A_model from mesh
    sys.path.insert(0,'/home/ubuntu/stage2_4K_from50K_v2'); import extract_heat_loads as E
    case='/home/ubuntu/stage2_4K_from50K_v2'
    pts=E.read_points(case+'/constant/coax_L1/polyMesh/points')
    faces=E.read_faces(case+'/constant/coax_L1/polyMesh/faces'); bnd=E.read_boundary(case+'/constant/coax_L1/polyMesh/boundary')
    L=max(p[2] for p in pts)-min(p[2] for p in pts)
    caps=[sum(E.face_area(f,pts) for f in faces[pb['startFace']:pb['startFace']+pb['nFaces']]) for pb in bnd if 'to_domain' not in pb['name']]
    Amodel=sum(caps)/len(caps)
    Tc,Th=4.0,50.0; nk=6; cab='SS_UT085'
    print(f"A_model (mesh coax cross-section) = {Amodel:.4e} m^2,  L = {L:.4f} m,  n_k={nk}, {cab}")
    # analytic target
    Qtarget=nk*Q_cable(cab,Tc,Th,L)
    # via k_eff integrated (what the solver does: Q=(A_model/L) int keff dT)
    Ts=[Tc+(Th-Tc)*i/200 for i in range(201)]; ks=[keff(cab,nk,Amodel,T) for T in Ts]
    # integrate keff
    h=(Th-Tc)/2000; Ikeff=0.5*(keff(cab,nk,Amodel,Tc)+keff(cab,nk,Amodel,Th))
    for i in range(1,2000): Ikeff+=keff(cab,nk,Amodel,Tc+i*h)
    Ikeff*=h; Qmodel=Amodel/L*Ikeff
    print(f"  Q_target = n_k * (1/L) Sum A_i int k_i dT = {Qtarget*1e3:.4f} mW")
    print(f"  Q_model  = (A_model/L) int k_eff dT       = {Qmodel*1e3:.4f} mW")
    print(f"  cancellation error = {abs(Qmodel-Qtarget)/Qtarget*100:.3e} %  (must be <1%)")
    coef,err=fit_poly(Ts,ks,3)
    print(f"  k_eff(T) cubic fit: coeffs={[f'{c:.4e}' for c in coef]}")
    print(f"  max rel fit error = {err*100:.3f} %  (gate G3.4 needs <2%)")
    print(f"  k_eff range: {ks[0]:.4g} (at {Tc}K) .. {ks[-1]:.4g} (at {Th}K) W/mK")

def write_solid_thermo(coeffs, out_path, rho=8000.0, cp=200.0, molWeight=60.0, header=""):
    pad=list(coeffs)+[0.0]*(8-len(coeffs))   # kappaCoeffs<8>, zero-padded
    kc=' '.join(f'{c:.8e}' for c in pad)
    txt=f"""/*--- effective T-dependent coax conductivity (harness k_eff) ---*\\
{header}
\\*-------------------------------------------------------------------*/
FoamFile {{ version 2.0; format ascii; class dictionary; object thermophysicalProperties; }}

thermoType
{{
    type            heSolidThermo;
    mixture         pureMixture;
    transport       polynomial;
    thermo          hPolynomial;
    equationOfState rhoConst;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie          {{ molWeight {molWeight}; }}
    equationOfState {{ rho {rho}; }}
    thermodynamics
    {{
        Hf 0;
        Sf 0;
        CpCoeffs<8> ( {cp} 0 0 0 0 0 0 0 );
    }}
    transport
    {{
        kappaCoeffs<8> ( {kc} );
    }}
}}
"""
    open(out_path,'w').write(txt)
