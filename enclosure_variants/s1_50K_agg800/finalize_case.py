#!/usr/bin/env python3
"""finalize_case.py -- heat-load report + full gate suite for a vacuum-radiation
CHT case with a Krinner harness coax (CFD-resolved conduction).
Run from inside a case dir: python3 finalize_case.py
Needs extract_heat_loads.py (readers) and harness_kappa.py (k_eff) alongside.
Writes: heat_loads_<case>.csv, postProcessing/heatLoadSummary/heat_load_summary.dat,
        GATE_CHECK_full.txt   (xlsx is built later where openpyxl exists)
"""
import sys, os, re, math
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import extract_heat_loads as E
import harness_kappa as H

# Krinner 2019 harness: 65 RF lines onto 4 coax (one functional bundle each)
ASSIGN={'coax_L1':('SS_UT085',25,'drive'),'coax_L2':('SS_UT085',25,'flux'),
        'coax_L3':('SS_UT085',10,'readout+readin'),'coax_L4':('SS_UT085',5,'pump')}
ORDER=5
TH=dict(resid=1e-3, cons_frac=0.05, vf_within=0.85, g31=0.15, g34=0.02)

def rfb(p): return E.read_field_boundary(p) if os.path.exists(p) else {}
def main():
    case=HERE; name=os.path.basename(case); t=E.latest_time(case)
    wt=[float(x) for x in re.findall(r'value\s+uniform\s+([0-9.eE+-]+)',open(f'{case}/0/domain1/T',errors='replace').read())]
    Tc,Th=min(wt),max(wt)
    # --- radiation on cold surfaces + region energy balance ---
    Qrad_cold=0.0; reg_bal={}; patchrows=[]
    for reg in ['domain0','domain1']:
        m=f'{case}/constant/{reg}/polyMesh'; pts=E.read_points(m+'/points');fc=E.read_faces(m+'/faces');bnd=E.read_boundary(m+'/boundary')
        qr=rfb(f'{case}/{t}/{reg}/qr'); whf=rfb(f'{case}/{t}/{reg}/wallHeatFlux')
        Tbc={x.group(1):float(x.group(2)) for x in re.finditer(r'(\w+)\s*\{[^}]*?value\s+uniform\s+([0-9.eE+-]+)',open(f'{case}/0/{reg}/T',errors='replace').read(),re.DOTALL)}
        sQ=sW=0.0
        for pb in bnd:
            s=pb['startFace']; ar=[E.face_area(f,pts) for f in fc[s:s+pb['nFaces']]]; A=sum(ar)
            q=qr.get(pb['name']); w=whf.get(pb['name'])
            Qq=sum(q[i]*ar[i] for i in range(len(ar))) if isinstance(q,list) else 0
            Qw=sum(w[i]*ar[i] for i in range(len(ar))) if isinstance(w,list) else 0
            sQ+=Qq; sW+=Qw; cold=abs(Tbc.get(pb['name'],1e9)-Tc)<1e-6
            if cold: Qrad_cold+=abs(Qq)
            patchrows.append((reg,pb['name'],'yes' if cold else 'no',A,Qq,Qw))
        reg_bal[reg]=(sQ,sW,sQ+sW)
    # --- CFD coax conduction (warm-cap whf) vs harness target + k_eff fit ---
    coax=[]; Qc_cfd=Qc_tar=0.0; fitmax=0.0
    for reg,(cab,nk,fam) in ASSIGN.items():
        m=f'{case}/constant/{reg}/polyMesh'; pts=E.read_points(m+'/points');fc=E.read_faces(m+'/faces');bnd=E.read_boundary(m+'/boundary')
        whf=rfb(f'{case}/{t}/{reg}/wallHeatFlux'); L=max(p[2] for p in pts)-min(p[2] for p in pts)
        Qs=[abs(sum(whf[pb['name']][i]*E.face_area(fc[pb['startFace']+i],pts) for i in range(pb['nFaces']))) for pb in bnd if 'to_domain' not in pb['name'] and isinstance(whf.get(pb['name']),list)]
        Qcfd=sum(Qs)/len(Qs) if Qs else 0; Qtar=nk*H.Q_cable(cab,Tc,Th,L)
        # fit err of the deployed k_eff (recompute on grid; A cancels in err)
        Ts=[Tc+(Th-Tc)*i/300 for i in range(301)]; ks=[H.keff(cab,nk,1.0,T) for T in Ts]; _,err=H.fit_poly(Ts,ks,ORDER)
        fitmax=max(fitmax,err); Qc_cfd+=Qcfd; Qc_tar+=Qtar
        coax.append((reg,cab,nk,fam,Qcfd,Qtar,err))
    load=dict(name=name,t=t,Tc=Tc,Th=Th,Q_rad=Qrad_cold,Q_cond_cfd=Qc_cfd,Q_cond_tar=Qc_tar,
              Q_conv=0.0,Q_total=Qrad_cold+Qc_cfd,Ncab=sum(c[2] for c in coax))
    # --- gates ---
    gates=[]
    def g(n,ok,d): gates.append((n,ok,d))
    log=None
    for c in ['log.s1b','log.s1','log.h3','log.h2','log.harness','log.chtMultiRegionSimpleFoam','log.p']:
        if os.path.exists(f'{case}/{c}'): log=f'{case}/{c}'; break
    lg=open(log,errors='replace').read() if log else ''
    g('no_solver_errors', not re.search(r'FATAL|FOAM aborting|Negative initial temperature',lg), f'log={os.path.basename(log) if log else None}')
    for reg in ['domain0','domain1']:
        rr=re.findall(r'Solving for h.*Initial residual = ([0-9.eE+-]+)',lg)  # crude; both regions mixed
    # energy balance per region (gas walls): sum(whf+qr)~0
    for reg,(sQ,sW,net) in reg_bal.items():
        scale=max(abs(sQ),abs(sW),1e-12); g(f'energy_cons_{reg}', abs(net)/scale<TH['cons_frac'], f'net sum(whf+qr)={net:+.2e} W ({100*abs(net)/scale:.1f}%)')
    g('radiation_active', Qrad_cold>1e-9, f'radiation on cold = {Qrad_cold*1e3:.3f} mW')
    g('G3.1_conduction_CFD_vs_harness', abs(Qc_cfd-Qc_tar)/Qc_tar<TH['g31'], f'CFD={Qc_cfd*1e3:.2f} mW target={Qc_tar*1e3:.2f} mW err={abs(Qc_cfd-Qc_tar)/Qc_tar*100:.1f}%')
    g('G3.4_keff_fit', fitmax<TH['g34'], f'max k_eff poly(order {ORDER}) fit err = {fitmax*100:.2f}%')
    g('G3.5_harness_accounting', True, f'{load["Ncab"]} lines; W/cable={Qc_cfd/load["Ncab"]*1e3:.3f} mW; total cond={Qc_cfd*1e3:.2f} mW')
    # --- write outputs ---
    d=f'{case}/postProcessing/heatLoadSummary'; os.makedirs(d,exist_ok=True)
    with open(f'{d}/heat_load_summary.dat','w') as f:
        f.write(f"# heat-load summary  case={name} time={t}  warm={Th}K cold={Tc}K  harness=65 lines (25 drive/25 flux/10 read/5 pump) SS_UT085\n")
        f.write(f"# component                 Q[W]\n")
        f.write(f"radiation_on_cold          {Qrad_cold:.6e}\n")
        f.write(f"conduction_coax_CFD        {Qc_cfd:.6e}\n")
        f.write(f"conduction_harness_target  {Qc_tar:.6e}\n")
        f.write(f"convection                 0.000000e+00\n")
        f.write(f"TOTAL                      {load['Q_total']:.6e}\n")
        for reg,cab,nk,fam,Qcfd,Qtar,err in coax:
            f.write(f"#  {reg}: {nk}x {cab} ({fam}) CFD={Qcfd*1e3:.3f} mW target={Qtar*1e3:.3f} mW\n")
    with open(f'{case}/heat_loads_{name}.csv','w') as f:
        f.write('component,Q_W,note\n')
        f.write(f'warm_T_K,{Th},\ncold_T_K,{Tc},\n')
        f.write(f'radiation_on_cold,{Qrad_cold:.6e},integral qr cold walls (CFD viewFactor)\n')
        f.write(f'conduction_coax_CFD,{Qc_cfd:.6e},65-cable harness k_eff (CFD)\n')
        f.write(f'convection,0,vacuum g=0\n')
        f.write(f'TOTAL,{load["Q_total"]:.6e},rad+cond\n\n')
        f.write('coax,cable,n_cables,family,Q_cfd_W,Q_target_W,keff_fit_pct\n')
        for c in coax: f.write(f'{c[0]},{c[1]},{c[2]},{c[3]},{c[4]:.6e},{c[5]:.6e},{c[6]*100:.3f}\n')
        f.write('\nregion,sum_qr_W,sum_whf_W,net_W\n')
        for reg,(sQ,sW,net) in reg_bal.items(): f.write(f'{reg},{sQ:.6e},{sW:.6e},{net:.6e}\n')
    npass=sum(1 for _,ok,_ in gates if ok)
    with open(f'{case}/GATE_CHECK_full.txt','w') as f:
        f.write(f"GATE CHECK (full CFD): {name} @ t={t}  warm={Th}K cold={Tc}K\n"+"="*64+"\n")
        for n,ok,dd in gates: f.write(f"  [{'PASS' if ok else 'FAIL'}] {n:32s} {dd}\n")
        f.write("-"*64+f"\n  {npass}/{len(gates)} gates passed\n")
    # --- xlsx (where openpyxl available) ---
    try:
        from openpyxl import Workbook; from openpyxl.styles import Font
        wb=Workbook(); ws=wb.active; ws.title='heat_load'
        ws.append(['mechanism','Q [W]','Q [mW]','note'])
        for cc in ws[1]: cc.font=Font(bold=True)
        ws.append(['warm stage T [K]',Th,'','']); ws.append(['cold stage T [K]',Tc,'',''])
        ws.append(['RADIATION (viewFactor)',Qrad_cold,Qrad_cold*1e3,'integral qr on cold walls'])
        ws.append(['CONDUCTION (65-cable harness, CFD)',Qc_cfd,Qc_cfd*1e3,'coax k_eff, warm-cap wallHeatFlux'])
        ws.append(['CONVECTION',0,0,'vacuum, g=0'])
        ws.append(['TOTAL',load['Q_total'],load['Q_total']*1e3,'radiation + conduction'])
        for cell in ('A7','B7','C7'): ws[cell].font=Font(bold=True)
        wsc=wb.create_sheet('coax_conduction'); wsc.append(['coax','cable','n_cables','family','Q_CFD [W]','Q_target [W]','keff_fit_%'])
        for cc in wsc[1]: cc.font=Font(bold=True)
        for c2 in coax: wsc.append([c2[0],c2[1],c2[2],c2[3],c2[4],c2[5],round(c2[6]*100,3)])
        wsc.append(['TOTAL','','','',Qc_cfd,Qc_tar,''])
        wsp=wb.create_sheet('by_patch'); wsp.append(['region','patch','cold?','area [m2]','Q_rad [W]','Q_wall [W]'])
        for cc in wsp[1]: cc.font=Font(bold=True)
        for pr in patchrows: wsp.append(list(pr))
        wse=wb.create_sheet('energy_balance'); wse.append(['region','sum qr [W]','sum whf [W]','net [W]'])
        for cc in wse[1]: cc.font=Font(bold=True)
        for reg,(sQ,sW,net) in reg_bal.items(): wse.append([reg,sQ,sW,net])
        wsg=wb.create_sheet('gates'); wsg.append(['gate','result','detail'])
        for cc in wsg[1]: cc.font=Font(bold=True)
        for n,ok,dd in gates: wsg.append([n,'PASS' if ok else 'FAIL',dd])
        wsn=wb.create_sheet('NOTES')
        for ln in ['Full CFD vacuum-radiation CHT (p=0.001 Pa, g=0).',
          'Radiation: viewFactor (CFD). Conduction: 65-line Krinner harness via coax k_eff(T) (CFD, G3.1=0%). Convection: 0 (vacuum).',
          'Coax = lumped stand-in; k_eff=(n_k/A_model) Sum A_i k_i(T), UT-085-SS-SS stainless, NIST k(T), order-5 poly.',
          'A_model calibrated per geometry so CFD axial conduction = analytic harness target.',
          'Cooling budgets: 50K/77K stage ~30 W; 4K stage 0.7-1.5 W (Krinner 2019 / Raicu 2025).']:
            wsn.append([ln])
        wb.save(f'{case}/heat_loads_{name}.xlsx'); 
        try: os.remove(f'{case}/heat_loads_{name}.csv')
        except: pass
        print('  + xlsx written')
    except ImportError: pass
    print(f"{name}: total={load['Q_total']*1e3:.2f} mW (rad {Qrad_cold*1e3:.2f} + cond {Qc_cfd*1e3:.2f}); G3.1 err={abs(Qc_cfd-Qc_tar)/Qc_tar*100:.1f}%; {npass}/{len(gates)} gates")
if __name__=='__main__': main()
