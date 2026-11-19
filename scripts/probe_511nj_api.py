"""Captura el payload exacto de getCameraDetail y prueba fetch interno (diagnóstico)."""
import asyncio
import json
import pathlib
import subprocess
import time
import urllib.request

import websockets

PORT = 9356
URL = "https://511nj.org/camera"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")


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
    proc = subprocess.Popen([
        CHROME, "--disable-gpu", "--no-first-run", "--disable-dev-shm-usage",
        "--ignore-certificate-errors", "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=" + str(PROFILE),
        "--window-position=-2400,-2400", "--window-size=1200,900", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = get_target(PORT)
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            seq = 0
            reqs = {}

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
                if m == "Network.requestWillBeSent":
                    r = p.get("request", {})
                    u = r.get("url", "")
                    if "getCamera" in u or "getTourList" in u:
                        reqs[p.get("requestId")] = {
                            "url": u, "method": r.get("method"),
                            "post": (r.get("postData") or "")[:500],
                            "headers": {k: v for k, v in (r.get("headers") or {}).items()
                                        if k.lower() in ("content-type", "referer", "x-requested-with")},
                        }
                elif m == "Network.responseReceived":
                    rid = p.get("requestId")
                    if rid in reqs:
                        reqs[rid]["status"] = p.get("response", {}).get("status")

            async def drain(seconds):
                deadline = time.time() + seconds
                while time.time() < deadline:
                    try:
                        handle(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5)))
                    except asyncio.TimeoutError:
                        continue

            async def ev(expr):
                r = await rpc("Runtime.evaluate", {"expression": expr,
                                                   "returnByValue": True, "awaitPromise": True})
                return (((r or {}).get("result") or {}).get("result") or {}).get("value")

            await rpc("Network.enable")
            await rpc("Page.enable")
            await rpc("Runtime.enable")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(26)
            await drain(4)

            print("=== TOURS ===")
            tours_raw = await ev("""(async()=>{
              const r=await fetch('/client/trafficMap/getTourList',{method:'GET',headers:{'Accept':'application/json'}});
              return JSON.stringify({status:r.status, body:(await r.text()).slice(0,300)});
            })()""")
            print(tours_raw)

            print("\n=== CÁMARA ROJA / DETALLE ===")
            clicked = await ev("""(()=>{const e=document.querySelector('li.camera-item');
              if(!e) return 'sin-items'; e.click(); return (e.textContent||'').trim().slice(0,90);})()""")
            print("click:", clicked)
            await asyncio.sleep(4)
            await drain(3)
            for rid, d in reqs.items():
                print(json.dumps(d, ensure_ascii=False)[:800])
                if "getCameraDetail" in d["url"]:
                    r = await rpc("Network.getResponseBody", {"requestId": rid}, timeout=20)
                    print("BODY:", (((r or {}).get("result") or {}).get("body", ""))[:800])

            print("\n=== FETCH DIRECTO getCameraDataByTourId ===")
            print(await ev("""(async()=>{try{
              const r=await fetch('/client/trafficMap/getCameraDataByTourId',{method:'POST',
                headers:{'Content-Type':'application/json','Accept':'application/json'},
                body:JSON.stringify({tourId:4})});
              const t=await r.text(); return JSON.stringify({status:r.status,len:t.length,head:t.slice(0,200)});
            }catch(e){return 'ERR '+e.message}})()"""))

            print("\n=== FETCH DIRECTO getCameraDetail ===")
            print(await ev("""(async()=>{try{
              const r=await fetch('/client/trafficMap/getCameraDetail',{method:'POST',
                headers:{'Content-Type':'application/json','Accept':'application/json'},
                body:JSON.stringify({cameraId:55})});
              const t=await r.text(); return JSON.stringify({status:r.status,len:t.length,head:t.slice(0,500)});
            }catch(e){return 'ERR '+e.message}})()"""))
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
