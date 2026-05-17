#!/usr/bin/env python3
"""Update VITE_API_URL on Vercel and trigger production redeploy."""
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAILWAY_URL = "https://git-gud-disaster-call-management-system-production.up.railway.app"
TEAM = "team_R5SG30RRl43PolxzZSbcKqWC"
PROJ = "prj_ni923MBrbI3GImANE17P5x6cL6eB"
LAST_DEPLOY = "dpl_9varqFECDx82L7Hp1fQ73iWqojwt"


def main() -> int:
    ctx = ssl.create_default_context()
    auth_path = Path.home() / "Library/Application Support/com.vercel.cli/auth.json"
    token = json.loads(auth_path.read_text())["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        with urllib.request.urlopen(f"{RAILWAY_URL}/health", timeout=15, context=ctx) as r:
            health = json.loads(r.read().decode())
        print("health", r.status, health.get("status"), health.get("tables_ready"))
    except urllib.error.URLError as e:
        print("health_skip", e)

    list_url = f"https://api.vercel.com/v9/projects/{PROJ}/env?teamId={TEAM}"
    with urllib.request.urlopen(urllib.request.Request(list_url, headers=headers), context=ctx) as r:
        envs = json.load(r).get("envs", [])

    vite = next((e for e in envs if e.get("key") == "VITE_API_URL"), None)
    targets = ["production", "preview", "development"]
    if not vite:
        print("VITE_API_URL not found")
        return 1

    patch_url = f"https://api.vercel.com/v9/projects/{PROJ}/env/{vite['id']}?teamId={TEAM}"
    body = json.dumps(
        {"value": RAILWAY_URL, "target": targets, "type": vite.get("type", "encrypted")}
    ).encode()
    req = urllib.request.Request(patch_url, data=body, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        print("env_patch", r.status)

    dep_url = f"https://api.vercel.com/v13/deployments?teamId={TEAM}"
    body = json.dumps(
        {"deploymentId": LAST_DEPLOY, "name": "resqnet_frontend", "target": "production"}
    ).encode()
    req = urllib.request.Request(dep_url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        dep = json.load(r)
    print("redeploy", dep.get("id"), dep.get("readyState"), dep.get("url"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print("http_error", e.code, e.read().decode()[:200])
        raise SystemExit(1)
