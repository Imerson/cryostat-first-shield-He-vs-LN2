import re, numpy as np
for R in ("domain0","domain1"):
    p=f"constant/{R}/F"; s=open(p).read()
    i=s.index("FoamFile"); j=s.index("}",i)+1; body=s[j:]
    m=re.search(r"\n(\d+)\s*\n\(", body); n=int(m.group(1)); start=m.end()
    rows=re.findall(r"(\d+)\s*(\(|\{)([^)}]*)(\)|\})", body[start:])
    assert len(rows)==n, (len(rows),n)
    outrows=[]; sums=[]
    for cnt,br,vals,_ in rows:
        cnt=int(cnt)
        v=np.full(cnt,float(vals.strip())) if br=="{" else np.array([float(x) for x in vals.split()])
        assert len(v)==cnt
        rs=v.sum(); sums.append(rs)
        if rs>0.2: v=v/rs
        outrows.append("%d(%s)"%(cnt," ".join("%.10g"%x for x in v)))
    sums=np.array(sums)
    print(R,"n=",n,"row-sum mean %.4f min %.4f max %.4f; within 10%%: %.1f%%; untouched(sum<=0.2): %d"%(sums.mean(),sums.min(),sums.max(),100*np.mean(np.abs(sums-1)<0.1),int((sums<=0.2).sum())))
    open(p,"w").write(s[:j]+"\n\n%d\n(\n"%n+"\n".join(outrows)+"\n)\n")
