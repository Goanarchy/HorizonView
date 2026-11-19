"""Exploración de la API de 511NJ mediante Chrome CDP (diagnóstico)."""
import asyncio
import json
import pathlib
import subprocess
import time
import urllib.request

import websockets

PORT = 9355
URL = "https://511nj.org/camera"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def get_target(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            pages = json.load(urllib.request.urlopen(
                "http://127.0.0.1:%d/json" % port, timeout=3))
            pages = [p for p in pages if p.get("type") == "page"]
            if pages:
                return pages[0]
        except Exception:
            pass
        time.sleep(0.4)
    return None


async def main():
    profile = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")
    proc = subprocess.Popen([
        CHROME, "--disable-gpu", "--no-first-run", "--disable-dev-shm-usage",
        "--ignore-certificate-errors", "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=" + str(profile),
        "--window-position=-2400,-2400", "--window-size=1200,900",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = get_target(PORT)
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            seq = 0
            reqs = {}
            bodies = {}

            async def rpc(method, params=None, timeout=90):
                nonlocal seq
                seq += 1
                mid = seq
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                    except asyncio.TimeoutError:
                        continue
                    handle(msg)
                    if msg.get("id") == mid:
                        return msg
                return None

            def handle(msg):
                m = msg.get("method", "")
                p = msg.get("params", {})
                if m == "Network.responseReceived":
                    r = p.get("response", {})
                    u = r.get("url", "")
                    low = u.lower()
                    if any(k in low for k in ("get", "camera", "tour", "json", "api", "511")):
                        reqs[p.get("requestId")] = (u, r.get("status"))

            async def drain(seconds):
                deadline = time.time() + seconds
                while time.time() < deadline:
                    try:
                        handle(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5)))
                    except asyncio.TimeoutError:
                        continue

            await rpc("Network.enable")
            await rpc("Page.enable")
            await rpc("Runtime.enable")
            print("NAVEGANDO...")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(28)
            await drain(6)

            print("\n=== PETICIONES ===")
            for rid, (u, st) in reqs.items():
                print(st, u[:220])

            print("\n=== BODIES DE INTERÉS ===")
            for rid, (u, st) in reqs.items():
                if any(k in u.lower() for k in ("gettourlist", "getcamera", "tour")):
                    r = await rpc("Network.getResponseBody", {"requestId": rid}, timeout=20)
                    body = ((r or {}).get("result") or {}).get("body", "")
                    print("---", u[:180], "status", st, "len", len(body))
                    print(body[:1400])

            print("\n=== GLOBALES ===")
            r = await rpc("Runtime.evaluate", {"expression":
                "Object.keys(window).filter(k=>/tour|camera|api|map|511|web/i.test(k)).slice(0,100).join(', ')",
                "returnByValue": True})
            print(((r or {}).get("result") or {}).get("result", {}).get("value"))

            print("\n=== UI TOURS ===")
            r = await rpc("Runtime.evaluate", {"expression": """
              JSON.stringify([...document.querySelectorAll('select,button,a,li,option')]
                .filter(e=>/tour|route|camera|region/i.test((e.textContent||'')+' '+(e.value||'')))
                .slice(0,50).map(e=>({tag:e.tagName,id:e.id,cls:String(e.className||'').slice(0,60),
                  txt:(e.textContent||'').trim().slice(0,90),val:e.value||''})))
            """, "returnByValue": True})
            print(((r or {}).get("result") or {}).get("result", {}).get("value"))

            print("\n=== SCRIPTS ===")
            r = await rpc("Runtime.evaluate", {"expression":
                "JSON.stringify([...document.scripts].map(s=>s.src).filter(Boolean).slice(0,40))",
                "returnByValue": True})
            print(((r or {}).get("result") or {}).get("result", {}).get("value"))
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
