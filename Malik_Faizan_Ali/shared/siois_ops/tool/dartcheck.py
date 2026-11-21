import re,sys,os,collections
root=sys.argv[1]
pub=open(os.path.join(root,'pubspec.yaml')).read()
deps=set(re.findall(r'^  ([a-z_0-9]+):',pub,re.M))
def strip(src):
    out=[];i=0;n=len(src)
    while i<n:
        c=src[i]
        if src.startswith('//',i):
            while i<n and src[i]!='\n': i+=1
        elif src.startswith('/*',i):
            j=src.find('*/',i+2); i=n if j<0 else j+2
        elif c in '\'"':
            raw = i>0 and src[i-1]=='r'
            q=src[i:i+3] if src[i:i+3] in ("'''",'"""') else c
            i+=len(q)
            while i<n and not src.startswith(q,i):
                if src[i]=='\\' and not raw: i+=1
                elif src[i]=='$' and not raw and i+1<n and src[i+1]=='{':
                    d=1;i+=2;start=i
                    while i<n and d:
                        if src[i]=='{':d+=1
                        elif src[i]=='}':d-=1
                        i+=1
                    out.append('('+strip(src[start:i-1])+')');continue
                i+=1
            i+=len(q);out.append('""')
        else: out.append(c);i+=1
    return ''.join(out)
problems=[];tops=collections.defaultdict(list);files=[]
for d,_,fs in os.walk(os.path.join(root,'lib')):
    for f in fs:
        if f.endswith('.dart'): files.append(os.path.join(d,f))
for p in sorted(files):
    src=open(p).read();s=strip(src)
    st=[];pairs={')':'(',']':'[','}':'{'}
    for ln,line in enumerate(s.split('\n'),1):
        for ch in line:
            if ch in '([{': st.append((ch,ln))
            elif ch in ')]}':
                if not st or st[-1][0]!=pairs[ch]: problems.append(f'{p}:{ln}: unbalanced {ch}');st=[];break
                st.pop()
    if st: problems.append(f'{p}: unclosed {st[-1]}')
    for m in re.finditer(r"^(?:import|export|part) '([^']+)'",src,re.M):
        t=m.group(1)
        if t.startswith('dart:'): continue
        if t.startswith('package:'):
            pk=t[8:].split('/')[0]
            if pk!='flutter' and pk not in deps and pk!=os.path.basename(root.rstrip('/')): problems.append(f'{p}: package {pk} not in pubspec')
            continue
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p),t))): problems.append(f'{p}: missing import {t}')
    for m in re.finditer(r'^(?:abstract |sealed |final |base )*(?:class|mixin|enum|typedef|extension)\s+([A-Za-z_]\w*)',s,re.M):
        if not m.group(1).startswith('_'): tops[m.group(1)].append(p)
    for m in re.finditer(r'^(?:[A-Za-z<>?,\s]+?)\s+([a-zA-Z]\w*)\s*\([^;{]*\)\s*(?:async\s*)?(?:=>|\{)',s,re.M):
        pass
for k,v in tops.items():
    if len(v)>1: problems.append(f'duplicate top-level {k}: '+', '.join(os.path.relpath(x,root) for x in v))
print(len(files),'files');print('\n'.join(problems) or 'no problems')
