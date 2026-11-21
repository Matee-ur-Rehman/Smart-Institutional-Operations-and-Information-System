"""Heuristic: named arguments passed to project-defined classes/functions must exist in their definition.
Usage: python3 tool/argcheck.py <package root>. Not a compiler; catches renamed / misspelled parameters."""
import re, os, sys
root = sys.argv[1]
files = []
for d, _, fs in os.walk(os.path.join(root, 'lib')):
    files += [os.path.join(d, f) for f in fs if f.endswith('.dart')]

def balanced(s, i, open_c='(', close_c=')'):
    depth = 0; j = i; q = None
    while j < len(s):
        c = s[j]
        if q:
            if c == '\\': j += 1
            elif c == q: q = None
        elif c in '\'"': q = c
        elif c in '([{': depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0: return j
        j += 1
    return -1

def top_level_named(args):
    names = []; depth = 0; q = None; start = 0; parts = []
    for k, c in enumerate(args):
        if q:
            if c == q and args[k-1] != '\\': q = None
            continue
        if c in '\'"': q = c
        elif c in '([{': depth += 1
        elif c in ')]}': depth -= 1
        elif c == ',' and depth == 0:
            parts.append(args[start:k]); start = k + 1
    parts.append(args[start:])
    for p in parts:
        m = re.match(r'\s*([a-zA-Z_]\w*)\s*:(?!:)', p)
        if m: names.append(m.group(1))
    return names

defs = {}  # name -> set of named params
for p in files:
    s = open(p).read()
    for m in re.finditer(r'^(?:abstract\s+)?class\s+(\w+)', s, re.M):
        cname = m.group(1)
        for cm in re.finditer(r'(?:const\s+)?\b%s\s*\(' % cname, s[m.end():]):
            i = m.end() + cm.end() - 1
            j = balanced(s, i)
            body = s[i+1:j]
            if '{' in body:
                nb = body[body.index('{'):]
                params = set(re.findall(r'(?:this\.|super\.|(?:\w[\w<>?,\s]*\s))(\w+)\s*(?:=|,|\}|$)', nb))
                params |= set(re.findall(r'this\.(\w+)', nb)) | set(re.findall(r'super\.(\w+)', nb))
                defs[cname] = params
            else:
                defs.setdefault(cname, set())
            break
problems = []
for p in files:
    s = open(p).read()
    for cname, params in defs.items():
        for m in re.finditer(r'(?<![\w.])(?:const\s+|new\s+)?%s\s*\(' % cname, s):
            pre = s[max(0, m.start()-12):m.start()]
            if re.search(r'(class|extends|implements|with)\s+$', pre): continue
            i = m.end() - 1
            j = balanced(s, i)
            if j < 0: continue
            for n in top_level_named(s[i+1:j]):
                if params and n not in params and n != 'key':
                    line = s.count('\n', 0, m.start()) + 1
                    problems.append('%s:%d: %s has no parameter "%s"' % (os.path.relpath(p, root), line, cname, n))
print(len(defs), 'classes indexed')
print('\n'.join(sorted(set(problems))) or 'no unknown named arguments')
