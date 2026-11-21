"""Heuristic: calls to project helper functions (format*/as*/show*/parse*/download*/is*) must name a function that exists,
and named arguments must exist in its definition. Usage: python3 tool/funccheck.py <package root>"""
import re, os, sys
root = sys.argv[1]
files = []
for d, _, fs in os.walk(os.path.join(root, 'lib')):
    files += [os.path.join(d, f) for f in fs if f.endswith('.dart')]
FLUTTER_OK = {'showDialog', 'showDatePicker', 'showTimePicker', 'showModalBottomSheet', 'showAboutDialog', 'showSnackBar', 'showLicensePage', 'asMap'}

def balanced(s, i):
    depth = 0; q = None; j = i
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

funcs = {}
for p in files:
    s = open(p).read()
    for m in re.finditer(r'^(?:[\w<>?,\[\] ]+?)\s+(\w+)\s*(?:<[^>]*>)?\(', s, re.M):
        name = m.group(1)
        if name[0].isupper() or name in ('main', 'build', 'if', 'for', 'while', 'switch'): continue
        i = m.end() - 1
        j = balanced(s, i)
        sig = s[i+1:j]
        named = set(re.findall(r'(?:this\.)?(\w+)\s*(?:=\s*[^,}]+)?[,}]', sig[sig.index('{'):])) if '{' in sig else set()
        named |= set(re.findall(r'required\s+(?:[\w<>?,]+\s+)?(\w+)', sig))
        funcs[name] = named
problems = []
for p in files:
    s = open(p).read()
    for m in re.finditer(r'(?<![\w.$])((?:format|as|show|parse|download)[A-Z]\w*)\s*\(', s):
        name = m.group(1)
        line = s.count('\n', 0, m.start()) + 1
        if name in FLUTTER_OK: continue
        pre = s[max(0, m.start()-40):m.start()]
        if name not in funcs:
            problems.append(f'{os.path.relpath(p, root)}:{line}: unknown function {name}')
            continue
        j = balanced(s, m.end() - 1)
        args = s[m.end():j]
        depth = 0; q = None; parts = []; start = 0
        for k, c in enumerate(args):
            if q:
                if c == q and args[k-1] != '\\': q = None
                continue
            if c in '\'"': q = c
            elif c in '([{': depth += 1
            elif c in ')]}': depth -= 1
            elif c == ',' and depth == 0: parts.append(args[start:k]); start = k + 1
        parts.append(args[start:])
        for part in parts:
            mm = re.match(r'\s*([a-zA-Z_]\w*)\s*:(?!:)', part)
            if mm and funcs[name] and mm.group(1) not in funcs[name]:
                problems.append(f'{os.path.relpath(p, root)}:{line}: {name} has no named parameter "{mm.group(1)}"')
print(len(funcs), 'functions indexed')
print('\n'.join(sorted(set(problems))) or 'no unknown helper calls')
