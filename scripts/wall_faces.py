"""Extract heated-wall face temperatures from foamToVTK legacy ASCII output: writes per-case
postProcessing/wallFaces/<time>/wall_faces.csv (x,y,T) and wall_centreline.csv (binned by x at the
duct centre y=0.005), and prints max / area-mean / centreline max."""
import re, os, glob, sys, numpy as np, csv
def read_vtk(path):
    s=open(path).read()
    pts=re.search(r"POINTS\s+(\d+)\s+\w+\s*\n(.*?)\n(?=[A-Z])", s, re.S); n=int(pts.group(1)); P=np.array(pts.group(2).split(),float).reshape(n,3)
    poly=re.search(r"POLYGONS\s+(\d+)\s+(\d+)\s*\n(.*?)\n(?=[A-Z]|$)", s, re.S)
    if poly:
        nf=int(poly.group(1)); arr=np.array(poly.group(3).split(),int); faces=[]; i=0
        for _ in range(nf): k=arr[i]; faces.append(arr[i+1:i+1+k]); i+=k+1
    else:
        cells=re.search(r"CELLS\s+(\d+)\s+(\d+)\s*\n(.*?)\nCELL_TYPES", s, re.S); nf=int(cells.group(1)); arr=np.array(cells.group(3).split(),int); faces=[]; i=0
        for _ in range(nf): k=arr[i]; faces.append(arr[i+1:i+1+k]); i+=k+1
    cd=re.search(r"CELL_DATA\s+(\d+).*?\bT\b\s+1\s+(\d+)\s+\w+\s*\n(.*?)(?=\n[A-Z]|\Z)", s, re.S)
    if cd: T=np.array(cd.group(3).split(),float)[:nf]
    else:
        cd=re.search(r"CELL_DATA\s+(\d+)\s*\nSCALARS\s+T\s+\w+.*?\nLOOKUP_TABLE\s+\w+\s*\n(.*?)(?=\n[A-Z]|\Z)", s, re.S); T=np.array(cd.group(2).split(),float)[:nf]
    C=np.array([P[f].mean(axis=0) for f in faces])
    A=np.array([0.5*abs(np.cross(P[f[1]]-P[f[0]],P[f[2]]-P[f[0]]))[2] if len(f)==3 else abs(np.linalg.norm(np.cross(P[f[2]]-P[f[0]],P[f[3]]-P[f[1]])))*0.5 for f in faces])
    return C,A,T
for vtk in sorted(glob.glob(sys.argv[1])):
    case=vtk.split("/")[-4] if "/VTK/" in vtk else vtk
    C,A,T=read_vtk(vtk)
    wmax=T.max(); wmean=(T*A).sum()/A.sum()
    # centre column of channel 1 (y=0.005): faces whose y is within half a face width of 0.005
    ys=np.unique(np.round(C[:,1],6)); yc=ys[np.argmin(np.abs(ys-0.005))]   # face row nearest the duct centre
    sel=np.abs(C[:,1]-yc)<1e-6
    xs=C[sel,0]; Ts=T[sel]; o=np.argsort(xs)
    out=os.path.join(os.path.dirname(vtk),"..","..","postProcessing","wallFaces"); os.makedirs(out,exist_ok=True)
    with open(os.path.join(out,"wall_centreline.csv"),"w",newline="") as f:
        w=csv.writer(f); w.writerow(["x_m","T_wall_K"]); w.writerows(zip(xs[o],Ts[o]))
    with open(os.path.join(out,"wall_stats.csv"),"w",newline="") as f:
        w=csv.writer(f); w.writerow(["wall_max_K","wall_areaMean_K","centreline_max_K","nfaces"]); w.writerow([wmax,wmean,Ts.max(),len(T)])
    print(f"{case:20} faces={len(T):6d} wall_max={wmax:7.2f} area_mean={wmean:7.2f} centreline_max={Ts.max():7.2f} (n={sel.sum()})")
