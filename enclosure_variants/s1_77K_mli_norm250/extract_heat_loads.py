#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_heat_loads.py  --  stage2 vacuum-radiation CHT heat-load extractor
==========================================================================
Self-contained (pure python). Run from inside a case folder:
    python3 extract_heat_loads.py
It reads the LAST time directory's fields directly (not postProcessing/*.dat):
    <t>/<region>/qr            radiative wall flux  [W/m^2]  (viewFactor)
    <t>/<region>/wallHeatFlux  diffusive wall flux  [W/m^2]
and the polyMesh, computes per-face areas, and integrates per patch.

Model: the inter-stage gap is a radiative vacuum (gas transparent, p=0.001 Pa,
g=0).  So the heat paths are RADIATION (qr, surface-to-surface viewFactor) and
solid CONDUCTION down the coax.  Gas convection/conduction is negligible.

Writes heat_loads_<case>.xlsx (sheets by_patch, summary, NOTES); falls back to
heat_loads_<case>.csv if openpyxl is absent.
"""
import os, re, struct, math

FLUID_REGIONS = ["domain0", "domain1"]
# net radiative flux sign from viewFactor qr: report magnitudes + signed.

# ---------- OpenFOAM readers (ascii + binary) ----------
def _hdr(raw):
    h=raw[:2000].decode('latin-1','replace'); fmt='ascii'
    m=re.search(r'format\s+(\w+)\s*;',h); fmt=m.group(1) if m else 'ascii'
    lab,sca=4,8
    a=re.search(r'arch\s+"[^"]*label=(\d+)\s*;\s*scalar=(\d+)',h)
    if a: lab=int(a.group(1))//8; sca=int(a.group(2))//8
    return fmt,lab,sca
class _Cur:
    def __init__(s,b,p=0): s.b=b; s.p=p
    def ws(s):
        b,n=s.b,len(s.b)
        while s.p<n:
            c=b[s.p]
            if c in (32,9,10,13): s.p+=1
            elif c==0x2F and s.p+1<n and b[s.p+1]==0x2F:
                while s.p<n and b[s.p] not in (10,13): s.p+=1
            elif c==0x2F and s.p+1<n and b[s.p+1]==0x2A:
                s.p+=2
                while s.p+1<n and not(b[s.p]==0x2A and b[s.p+1]==0x2F): s.p+=1
                s.p+=2
            else: break
    def peek(s): return s.b[s.p] if s.p<len(s.b) else -1
    def tok(s):
        s.ws(); b,n=s.b,len(s.b); st=s.p
        while s.p<n and b[s.p] not in (32,9,10,13,59,123,125,40,41): s.p+=1
        return b[st:s.p].decode('latin-1')
    def exp(s,ch):
        s.ws()
        if s.p<len(s.b) and s.b[s.p]==ord(ch): s.p+=1; return True
        return False
    def rint(s):
        s.ws(); b,n=s.b,len(s.b); st=s.p
        if s.p<n and b[s.p] in (43,45): s.p+=1
        while s.p<n and 48<=b[s.p]<=57: s.p+=1
        return int(b[st:s.p])
def _scalist(cur,fmt,sb):
    n=cur.rint(); cur.ws(); cur.exp('(')
    if fmt=='binary':
        raw=cur.b[cur.p:cur.p+n*sb]; cur.p+=n*sb
        v=list(struct.unpack('<%dd'%n,raw)) if sb==8 else list(struct.unpack('<%df'%n,raw))
        cur.exp(')'); return v
    v=[]
    for _ in range(n):
        cur.ws(); st=cur.p; b=cur.b
        while cur.p<len(b) and b[cur.p] not in (32,9,10,13,41): cur.p+=1
        v.append(float(b[st:cur.p]))
    cur.exp(')'); return v
def read_points(path):
    raw=open(path,'rb').read(); fmt,lab,sca=_hdr(raw)
    i=raw.find(b'// *'); i=raw.find(b'\n',i) if i>=0 else 0; cur=_Cur(raw,i)
    n=cur.rint(); cur.ws(); cur.exp('(')
    if fmt=='binary':
        fl=struct.unpack('<%dd'%(n*3),raw[cur.p:cur.p+n*3*sca])
        return [(fl[k*3],fl[k*3+1],fl[k*3+2]) for k in range(n)]
    p=[]
    for _ in range(n):
        cur.ws(); cur.exp('('); x=float(cur.tok());y=float(cur.tok());z=float(cur.tok()); cur.exp(')'); p.append((x,y,z))
    return p
def read_faces(path):
    raw=open(path,'rb').read(); fmt,lab,sca=_hdr(raw)
    i=raw.find(b'// *'); i=raw.find(b'\n',i) if i>=0 else 0; cur=_Cur(raw,i)
    if fmt=='binary':
        n1=cur.rint(); cur.ws(); cur.exp('(')
        off=list(struct.unpack('<%di'%n1,raw[cur.p:cur.p+n1*lab])); cur.p+=n1*lab; cur.exp(')')
        n2=cur.rint(); cur.ws(); cur.exp('(')
        dat=list(struct.unpack('<%di'%n2,raw[cur.p:cur.p+n2*lab])); cur.p+=n2*lab; cur.exp(')')
        return [dat[off[k]:off[k+1]] for k in range(len(off)-1)]
    nf=cur.rint(); cur.ws(); cur.exp('('); f=[]
    for _ in range(nf):
        k=cur.rint(); cur.ws(); cur.exp('('); f.append([cur.rint() for _ in range(k)]); cur.exp(')')
    return f
def read_boundary(path):
    txt=open(path,'rb').read().decode('latin-1','replace'); body=txt[txt.find('// *'):]; out=[]
    for m in re.finditer(r'(\w+)\s*\{([^}]*?)\}',body,re.DOTALL):
        nf=re.search(r'nFaces\s+(\d+)',m.group(2)); sf=re.search(r'startFace\s+(\d+)',m.group(2))
        if nf and sf: out.append(dict(name=m.group(1),nFaces=int(nf.group(1)),startFace=int(sf.group(1))))
    return out
def read_field_boundary(path):
    raw=open(path,'rb').read(); fmt,lab,sca=_hdr(raw)
    i=raw.find(b'boundaryField')
    if i<0: return {}
    cur=_Cur(raw,i+13); cur.ws(); cur.exp('{'); out={}
    while True:
        cur.ws()
        if cur.peek()==ord('}') or cur.peek()==-1: break
        name=cur.tok(); cur.ws(); cur.exp('{'); val=None
        while True:
            cur.ws()
            if cur.peek()==ord('}'): cur.p+=1; break
            key=cur.tok(); cur.ws(); nx=cur.tok()
            if nx=='uniform':
                cur.ws()
                if cur.peek()==ord('('):
                    cur.exp('(')
                    while cur.peek() not in (ord(')'),-1): cur.p+=1
                    cur.exp(')'); v=None
                else: v=float(cur.tok())
                cur.ws(); cur.exp(';')
                if key=='value': val=v
            elif nx=='nonuniform':
                lt=cur.tok()
                if 'vector' in lt:
                    n=cur.rint(); cur.ws(); cur.exp('(')
                    if fmt=='binary': cur.p+=n*3*sca
                    else:
                        for _ in range(n*3): cur.tok()
                    cur.exp(')'); v=None
                else: v=_scalist(cur,fmt,sca)
                cur.ws(); cur.exp(';')
                if key=='value': val=v
            else:
                b=cur.b
                while cur.p<len(b) and b[cur.p]!=59: cur.p+=1
                cur.exp(';')
        out[name]=val
    return out
def face_area(idx,pts):
    p=[pts[k] for k in idx]
    if len(p)<3: return 0.0
    sx=sy=sz=0.0; p0=p[0]
    for i in range(1,len(p)-1):
        ax,ay,az=p[i][0]-p0[0],p[i][1]-p0[1],p[i][2]-p0[2]
        bx,by,bz=p[i+1][0]-p0[0],p[i+1][1]-p0[1],p[i+1][2]-p0[2]
        sx+=ay*bz-az*by; sy+=az*bx-ax*bz; sz+=ax*by-ay*bx
    return 0.5*math.sqrt(sx*sx+sy*sy+sz*sz)

def integ(field,patch,faces,pts):
    s,e=patch['startFace'],patch['startFace']+patch['nFaces']
    ar=[face_area(f,pts) for f in faces[s:e]]; A=sum(ar)
    v=field.get(patch['name'])
    if isinstance(v,list) and len(v)==len(ar): return sum(v[i]*ar[i] for i in range(len(ar))),A
    if isinstance(v,(int,float)): return v*A,A
    return 0.0,A

def latest_time(case):
    ts=[d for d in os.listdir(case) if os.path.isdir(os.path.join(case,d)) and re.fullmatch(r'\d+(\.\d+)?',d) and d!='0']
    return max(ts,key=float) if ts else '0'

def coax_conduction(case,t):
    """Axial solid conduction down each coax cable: Q = kappa*A_cross*dT/L."""
    cdir=os.path.join(case,'constant'); out=[]
    for reg in sorted(d for d in os.listdir(cdir) if re.match(r'coax',d) and os.path.isdir(os.path.join(cdir,d,'polyMesh'))):
        mesh=os.path.join(cdir,reg,'polyMesh')
        pts=read_points(mesh+'/points'); faces=read_faces(mesh+'/faces'); bnd=read_boundary(mesh+'/boundary')
        kt=open(os.path.join(cdir,reg,'thermophysicalProperties')).read()
        km=re.search(r'kappa\s+([0-9.eE+-]+)',kt); kappa=float(km.group(1)) if km else None
        Tbf=read_field_boundary(f'{case}/{t}/{reg}/T')
        L=max(p[2] for p in pts)-min(p[2] for p in pts)
        ends=[]
        for pb in bnd:
            if 'to_domain' in pb['name']: continue
            s,e=pb['startFace'],pb['startFace']+pb['nFaces']
            ar=[face_area(f,pts) for f in faces[s:e]]
            v=Tbf.get(pb['name']); Tm=(sum(v)/len(v)) if isinstance(v,list) else v
            if Tm is not None: ends.append((sum(ar),Tm))
        if len(ends)<2 or not kappa or L<=0: continue
        ends.sort(key=lambda x:x[1]); cold,hot=ends[0],ends[-1]
        Ac=0.5*(cold[0]+hot[0]); dT=hot[1]-cold[1]; Q=kappa*Ac*dT/L
        out.append(dict(region=reg,kappa=kappa,A=Ac,L=L,dT=dT,Q=Q))
    return out

def main():
    case=os.path.dirname(os.path.abspath(__file__)); name=os.path.basename(case); t=latest_time(case)
    rows=[]; reg_bal={}
    # collect all wall fixedValue temps to find the cold (sink) temperature
    walltemps=[]
    for reg in FLUID_REGIONS:
        tf=f'{case}/0/{reg}/T'
        if os.path.exists(tf):
            walltemps+=[float(x) for x in re.findall(r'value\s+uniform\s+([0-9.eE+-]+)',open(tf,errors="replace").read())]
    Tcold=min(walltemps) if walltemps else 0; Twarm=max(walltemps) if walltemps else 0
    Q_rad_cold=0.0; Q_gas_cold=0.0
    for reg in FLUID_REGIONS:
        mesh=os.path.join(case,'constant',reg,'polyMesh')
        if not os.path.isdir(mesh): continue
        pts=read_points(mesh+'/points'); faces=read_faces(mesh+'/faces'); bnd=read_boundary(mesh+'/boundary')
        qr=read_field_boundary(f'{case}/{t}/{reg}/qr') if os.path.exists(f'{case}/{t}/{reg}/qr') else {}
        whf=read_field_boundary(f'{case}/{t}/{reg}/wallHeatFlux') if os.path.exists(f'{case}/{t}/{reg}/wallHeatFlux') else {}
        # which patches are cold (4K) sinks
        Tbc={x.group(1):float(x.group(2)) for x in re.finditer(r'(\w+)\s*\{[^}]*?value\s+uniform\s+([0-9.eE+-]+)',
             open(f'{case}/0/{reg}/T',errors="replace").read(),re.DOTALL)} if os.path.exists(f'{case}/0/{reg}/T') else {}
        sQ=sW=0.0
        for pb in bnd:
            Qr,A=integ(qr,pb,faces,pts); Qw,_=integ(whf,pb,faces,pts)
            sQ+=Qr; sW+=Qw
            is_cold = abs(Tbc.get(pb['name'],1e9)-Tcold)<1e-6
            if is_cold:
                Q_rad_cold+=abs(Qr); Q_gas_cold+=abs(Qw)
            rows.append(dict(region=reg,patch=pb['name'],nFaces=pb['nFaces'],area=A,
                             Q_rad=Qr,Q_wall=Qw,q_rad_avg=(Qr/A if A else 0),cold=is_cold))
        reg_bal[reg]=dict(sumQrad=sQ,sumQwall=sW,net=sQ+sW)
    coax=coax_conduction(case,t)
    Q_cond=sum(c['Q'] for c in coax)
    load=dict(Twarm=Twarm,Tcold=Tcold,
              Q_radiation=Q_rad_cold,            # radiation absorbed by 4K surfaces
              Q_conduction_coax=Q_cond,          # axial solid conduction down coax
              Q_convection=0.0,                  # vacuum, g=0 -> no gas convection
              Q_gas_conduction=Q_gas_cold,       # gas conduction across gap (~0 in vacuum)
              Q_total=Q_rad_cold+Q_cond+Q_gas_cold)
    write(case,name,t,rows,reg_bal,coax,load)

def _write_pp(case,name,t,load,coax):
    """Write a postProcessing summary the same way as the .dat function objects."""
    d=os.path.join(case,'postProcessing','heatLoadSummary'); os.makedirs(d,exist_ok=True)
    with open(os.path.join(d,'heat_load_summary.dat'),'w') as f:
        f.write(f"# stage2 total heat-load summary  case={name}  time={t}\n")
        f.write(f"# warm stage T={load['Twarm']} K   cold (4K) stage T={load['Tcold']} K\n")
        f.write("# component                          Q [W]\n")
        f.write(f"radiation_on_4K_surfaces            {load['Q_radiation']:.6e}\n")
        f.write(f"conduction_coax_axial               {load['Q_conduction_coax']:.6e}\n")
        f.write(f"convection_gas                      {load['Q_convection']:.6e}\n")
        f.write(f"gas_conduction_across_gap           {load['Q_gas_conduction']:.6e}\n")
        f.write(f"TOTAL_heat_load_on_4K_stage         {load['Q_total']:.6e}\n")
        f.write("#\n# coax per-cable axial conduction (kappa*A*dT/L):\n")
        for c in coax:
            f.write(f"#   {c['region']}: kappa={c['kappa']} A={c['A']:.4e} L={c['L']:.4f} dT={c['dT']:.1f}  Q={c['Q']:.4e} W\n")
    print('Wrote',os.path.join(d,'heat_load_summary.dat'))

def write(case,name,t,rows,reg_bal,coax,load):
    _write_pp(case,name,t,load,coax)
    try:
        from openpyxl import Workbook; from openpyxl.styles import Font
        wb=Workbook()
        # --- HEAT LOAD sheet (the comparison numbers) ---
        ws0=wb.active; ws0.title='heat_load'
        ws0.append(['component','Q [W]','note'])
        for c in ws0[1]: c.font=Font(bold=True)
        ws0.append(['warm stage T [K]',load['Twarm'],'']); ws0.append(['cold (4K) stage T [K]',load['Tcold'],''])
        ws0.append(['RADIATION on 4K surfaces',load['Q_radiation'],'integral qr on cold walls (viewFactor)'])
        ws0.append(['CONDUCTION coax (axial)',load['Q_conduction_coax'],'kappa*A*dT/L, 4 cables'])
        ws0.append(['CONVECTION gas',load['Q_convection'],'0 (vacuum, g=0, no flow)'])
        ws0.append(['gas conduction across gap',load['Q_gas_conduction'],'integral wallHeatFlux on cold walls (~0)'])
        ws0.append(['TOTAL heat load on 4K stage',load['Q_total'],'radiation + coax conduction + gas'])
        ws0['A8'].font=Font(bold=True); ws0['B8'].font=Font(bold=True)
        # --- by_patch ---
        ws=wb.create_sheet('by_patch')
        ws.append(['region','patch','cold(4K)?','nFaces','area [m2]','Q_radiation [W]','Q_wall_diffusive [W]','q_rad_avg [W/m2]'])
        for c in ws[1]: c.font=Font(bold=True)
        for r in rows: ws.append([r['region'],r['patch'],'yes' if r['cold'] else 'no',r['nFaces'],r['area'],r['Q_rad'],r['Q_wall'],r['q_rad_avg']])
        # --- coax conduction detail ---
        wsc=wb.create_sheet('coax_conduction')
        wsc.append(['coax','kappa [W/mK]','A_cross [m2]','length [m]','dT [K]','Q_cond [W]'])
        for c in wsc[1]: c.font=Font(bold=True)
        for c in coax: wsc.append([c['region'],c['kappa'],c['A'],c['L'],c['dT'],c['Q']])
        wsc.append(['TOTAL','','','','',sum(c['Q'] for c in coax)])
        # --- region energy balance ---
        ws2=wb.create_sheet('energy_balance'); ws2.append(['region','sum Q_rad [W]','sum Q_wall [W]','net sum(whf+qr) [W]'])
        for c in ws2[1]: c.font=Font(bold=True)
        for reg,b in reg_bal.items(): ws2.append([reg,b['sumQrad'],b['sumQwall'],b['net']])
        # --- NOTES ---
        ws3=wb.create_sheet('NOTES')
        for ln in [
            'Vacuum-radiation CHT (p=0.001 Pa, g=0, transparent gas).',
            'TOTAL heat load on the 4K stage = RADIATION (qr on 4K walls) + CONDUCTION (coax axial) + CONVECTION(=0).',
            'RADIATION: integral(qr) absorbed by the cold (4K) walls (shield, coldPlate, shield_slave).',
            'CONDUCTION: axial solid conduction down the coax, Q=kappa*A_cross*dT/L (Nb kappa=12.2).',
            'CONVECTION: 0 -- vacuum with g=0 has no gas flow.',
            'gas conduction across the gap is the diffusive wallHeatFlux on cold walls (~uW, negligible).',
            'Energy balance net=sum(whf+qr) per region -> 0 confirms conservation.',
            'Extracted directly from the last time dir, not postProcessing/*.dat.']:
            ws3.append([ln])
        out=os.path.join(case,f'heat_loads_{name}.xlsx'); wb.save(out); print('Wrote',out)
    except ImportError:
        import csv
        out=os.path.join(case,f'heat_loads_{name}.csv')
        with open(out,'w',newline='') as f:
            w=csv.writer(f)
            w.writerow(['HEAT LOAD SUMMARY','Q_W','note'])
            w.writerow(['warm_T_K',load['Twarm'],'']); w.writerow(['cold_T_K',load['Tcold'],''])
            w.writerow(['radiation_on_4K',load['Q_radiation'],'integral qr cold walls'])
            w.writerow(['conduction_coax',load['Q_conduction_coax'],'kA dT/L x4'])
            w.writerow(['convection_gas',load['Q_convection'],'0 vacuum'])
            w.writerow(['gas_conduction',load['Q_gas_conduction'],'~0'])
            w.writerow(['TOTAL',load['Q_total'],'rad+cond+gas'])
            w.writerow([]); w.writerow(['region','patch','cold','nFaces','area_m2','Q_rad_W','Q_wall_W','q_rad_avg'])
            for r in rows: w.writerow([r['region'],r['patch'],r['cold'],r['nFaces'],r['area'],r['Q_rad'],r['Q_wall'],r['q_rad_avg']])
            w.writerow([]); w.writerow(['coax','kappa','A_cross','L','dT','Q_cond'])
            for c in coax: w.writerow([c['region'],c['kappa'],c['A'],c['L'],c['dT'],c['Q']])
        print('openpyxl absent -> wrote',out)

if __name__=='__main__': main()
