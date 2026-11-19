"""Prueba de concepto: interceptar petición firmada de 511NJ y cambiar su cuerpo."""
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

PORT = 9357
URL = "https://511nj.org/camera"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")
KEY = b"lIo3M)_83,ALC0Wz"
IV = b".%A}8Qvqm23jYVc9"


def encrypt(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(raw, 16)).hex()


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
            bodies = {}

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

            async def wait_event(method, timeout=40, predicate=None):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    for e in list(events):
                        if e.get("method") == method and (predicate is None or predicate(e)):
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
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*511nj.org/client/trafficMap/getCameraDataByTourId*",
                "requestStage": "Request",
            }]})
            await rpc("Page.navigate", {"url": URL})
            print("cargando…")
            await asyncio.sleep(26)

            # La página ya hizo una petición al cargar; la interceptamos y la dejamos pasar.
            initial_ids = set()
            for _ in range(4):
                e = await wait_event("Fetch.requestPaused", timeout=3)
                if not e:
                    break
                p = e["params"]
                initial_ids.add(p["requestId"])
                print("pausada inicial:", p["request"]["url"][:90])
                await rpc("Fetch.continueRequest", {"requestId": p["requestId"]})

            new_body = base64.b64encode(json.dumps(
                {"encryptedData": encrypt({"tourId": 4})}).encode()).decode()
            print("encryptedData tour 4:", encrypt({"tourId": 4}))

            # Disparar una petición nueva haciendo clic en el tour 3 (seleccionarlo otra vez).
            clicked = await ev("""(()=>{const e=[...document.querySelectorAll('li.pure-checkbox')]
              .find(x=>x.textContent.includes('I-80 Tour')); if(!e)return 'no'; e.click(); return 'ok';})()""")
            print("click:", clicked)

            paused = await wait_event("Fetch.requestPaused", timeout=30)
            if not paused:
                print("NO SE INTERCEPTÓ")
                return
            p = paused["params"]
            print("URL interceptada:", p["request"]["url"][:120])
            print("body original:", str(p["request"].get("postData", ""))[:160])

            await rpc("Fetch.continueRequest", {
                "requestId": p["requestId"], "postData": new_body,
            })
            print("petición continuada con body del tour 4")

            # Capturar respuesta
            resp = await wait_event("Network.responseReceived", timeout=30,
                                    predicate=lambda e: ("getCameraDataByTourId" in e["params"].get("response", {}).get("url", "")
                                                        and e["params"].get("requestId") not in initial_ids))
            if not resp:
                print("sin respuesta")
                return
            rid = resp["params"]["requestId"]
            print("status:", resp["params"]["response"].get("status"))
            r = await rpc("Network.getResponseBody", {"requestId": rid})
            body = ((r or {}).get("result") or {}).get("body", "")
            data = json.loads(body).get("data") or []
            print("CÁMARAS RECIBIDAS:", len(data))
            print("ejemplo:", json.dumps(data[:3], ensure_ascii=False)[:600])
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
