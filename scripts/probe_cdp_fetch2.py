"""Prueba limpia: interceptar después de cargar y parchear cuerpo de petición firmada."""
import asyncio
import base64
import json
import pathlib
import subprocess
import time
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import websockets

PORT = 9359
URL = "https://511nj.org/camera"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")
KEY = b"lIo3M)_83,ALC0Wz"
IV = b".%A}8Qvqm23jYVc9"


def enc(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(raw, 16)).hex()


def body(obj):
    return base64.b64encode(json.dumps(
        {"encryptedData": enc(obj)}, separators=(",", ":")).encode()).decode()


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
            events = []

            async def rpc(method, params=None, timeout=60):
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
                    if msg.get("method"):
                        events.append(msg)
                    if msg.get("id") == mid:
                        return msg
                return None

            async def wait(method, timeout=30, pred=None):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    for e in list(events):
                        if e.get("method") == method and (pred is None or pred(e)):
                            events.remove(e)
                            return e
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.6))
                        if msg.get("method"):
                            events.append(msg)
                    except asyncio.TimeoutError:
                        pass
                return None

            async def ev(expr):
                r = await rpc("Runtime.evaluate", {"expression": expr,
                                                   "returnByValue": True, "awaitPromise": True})
                return (((r or {}).get("result") or {}).get("result") or {}).get("value")

            await rpc("Page.enable")
            await rpc("Runtime.enable")
            await rpc("Network.enable")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(26)
            print("página cargada; activando intercepción")

            # Interceptar getCameraDetail
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*511nj.org/edge/trafficMap/getCameraDetail*",
                "requestStage": "Request",
            }]})
            clicked = await ev("""(()=>{const e=[...document.querySelectorAll('li.camera-item')][0];
              if(!e)return 'no'; e.click(); return (e.textContent||'').trim().slice(0,50);})()""")
            print("clic cámara:", clicked)
            p = await wait("Fetch.requestPaused", timeout=25)
            if not p:
                print("sin pausa")
                return
            pr = p["params"]
            print("body original:", str(pr["request"].get("postData", ""))[:120])
            await rpc("Fetch.continueRequest", {
                "requestId": pr["requestId"], "postData": body({"cameraId": 740}),
            })
            resp = await wait("Network.responseReceived", timeout=25,
                              pred=lambda e: "getCameraDetail" in e["params"].get("response", {}).get("url", ""))
            if resp:
                rid = resp["params"]["requestId"]
                r = await rpc("Network.getResponseBody", {"requestId": rid})
                print("RESPUESTA PARCHADA:", ((r or {}).get("result") or {}).get("body", "")[:400])
            else:
                print("sin respuesta")
            await rpc("Fetch.disable")

            # Ahora getCameraDataByTourId con tour 4
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*511nj.org/client/trafficMap/getCameraDataByTourId*",
                "requestStage": "Request",
            }]})
            clicked = await ev("""(()=>{const e=[...document.querySelectorAll('li.pure-checkbox')]
              .find(x=>x.textContent.includes('I-80 Tour')); if(!e)return 'no'; e.click(); return 'ok';})()""")
            print("clic tour I-80:", clicked)
            p = await wait("Fetch.requestPaused", timeout=25)
            if not p:
                print("sin pausa tour")
                return
            pr = p["params"]
            print("body tour original:", str(pr["request"].get("postData", ""))[:120])
            await rpc("Fetch.continueRequest", {
                "requestId": pr["requestId"], "postData": body({"tourId": 4}),
            })
            resp = await wait("Network.responseReceived", timeout=25,
                              pred=lambda e: "getCameraDataByTourId" in e["params"].get("response", {}).get("url", ""))
            if resp:
                rid = resp["params"]["requestId"]
                r = await rpc("Network.getResponseBody", {"requestId": rid})
                data = json.loads(((r or {}).get("result") or {}).get("body", "{}")).get("data") or []
                print("TOUR 4 CÁMARAS:", len(data))
                print("ejemplo:", json.dumps(data[:3], ensure_ascii=False)[:400])
            else:
                print("sin respuesta tour")
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
