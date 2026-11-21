#!/usr/bin/env python3
"""
Smoke-tests the RUNNING API with real logins and prints a table. Standard library only.
    python check_system.py [--base http://localhost:8000]
Start the API first (start_backend.bat / ./start_backend.sh). Exit code 0 = everything passed.
"""
import argparse, json, sys, urllib.error, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--admin-pw", default="Admin@12345")
ap.add_argument("--user-pw", default="School@12345")
A = ap.parse_args()
rows = []


def call(method, path, token=None, body=None, platform="web"):
    req = urllib.request.Request(A.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Client-Platform", platform)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw or b"null")
            except ValueError:
                return r.status, None
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None


def check(name, ok, detail=""):
    rows.append((name, ok, detail))


def login(user, pw, platform):
    s, d = call("POST", "/api/v1/auth/login", body={"login_id": user, "password": pw}, platform=platform)
    tok = (d or {}).get("access_token") if isinstance(d, dict) else None
    return s, tok


def find(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return d


s, _ = call("GET", "/docs")
check("API reachable", s == 200, f"GET /docs -> {s}")
if s != 200:
    print("API not reachable at", A.base, "- start it first."); sys.exit(2)

plan = [("admin", A.admin_pw, "web"), ("teacher1", A.user_pw, "web"), ("teacher1", A.user_pw, "mobile"),
        ("student1", A.user_pw, "mobile"), ("parent1", A.user_pw, "mobile")]
tokens = {}
for u, pw, plat in plan:
    s, t = login(u, pw, plat)
    check(f"login {u} on {plat}", s == 200 and bool(t), f"-> {s}")
    tokens[(u, plat)] = t
for u, plat in (("student1", "web"), ("parent1", "web"), ("admin", "mobile")):
    s, _ = login(u, A.user_pw if u != "admin" else A.admin_pw, plat)
    check(f"{u} refused on {plat} (by design)", s in (401, 403), f"-> {s}")
s, _ = login("admin", "wrong-password", "web")
check("wrong password rejected", s == 401, f"-> {s}")

def me(tok, label):
    s, d = call("GET", "/api/v1/auth/me", tok)
    check(f"/auth/me {label}", s == 200, f"-> {s}")

adm, tch, stu, par = tokens[("admin", "web")], tokens[("teacher1", "web")], tokens[("student1", "mobile")], tokens[("parent1", "mobile")]
for t, l in ((adm, "admin"), (tch, "teacher1"), (stu, "student1"), (par, "parent1")):
    if t: me(t, l)

def count(d):
    d = find(d, "items", "data", "results")
    return len(d) if isinstance(d, list) else "?"

for who, tok, path in [
    ("admin", adm, "/api/v1/students"), ("admin", adm, "/api/v1/classes"), ("admin", adm, "/api/v1/attendance/overview"), ("admin", adm, "/api/v1/exams"),
    ("admin", adm, "/api/v1/fee-invoices"), ("admin", adm, "/api/v1/announcements"), ("admin", adm, "/api/v1/complaints"),
    ("admin", adm, "/api/v1/events"), ("teacher1", tch, "/api/v1/assignments"), ("student1", stu, "/api/v1/assignments"),
    ("student1", stu, "/api/v1/notifications"), ("parent1", par, "/api/v1/fee-invoices"),
]:
    if not tok: continue
    s, d = call("GET", path, tok)
    check(f"{who}: GET {path}", s == 200, f"-> {s}, {count(d)} rows" if s == 200 else f"-> {s}")
if stu:
    s, _ = call("GET", "/api/v1/fee-invoices", stu)
    check("student1 cannot see fees (by design)", s in (401, 403), f"-> {s}")

w = max(len(r[0]) for r in rows)
print()
for name, ok, det in rows:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(w)}  {det}")
bad = [r for r in rows if not r[1]]
print(f"\n{len(rows) - len(bad)}/{len(rows)} checks passed")
if bad:
    print("Failed paths may just be a different URL than guessed here - compare with http://localhost:8000/docs")
sys.exit(1 if bad else 0)
