"""Muestrea getCameraDetail para cámaras verdes y rojas mediante interceptación CDP."""
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

PORT = 9360
URL = "https://511nj.org/camera"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")
KEY = b"lIo3M)_83,ALC0Wz"
IV = b".%A}8Qvqm23jYVc9"
IDS = [51, 52, 55, 56, 269, 681, 740, 742, 745, 100, 200, 300]


def enc(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(json.dumps({"encryptedData": AES.new(
        KEY, AES.MODE_CBC, IV).encrypt(pad(raw, 16)).hex()},
        separators=(",", ":")).encode()).decode()


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

            async def wait(method, timeout=15, pred=None):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    for e in list(events):
                        if e.get("method") == method and (pred is None or pred(e)):
                            events.remove(e)
                            return e
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                        if msg.get("method"):
                            events.append(msg)
                    except asyncio.TimeoutError:
                        pass
                return None

            async def ev(expr):
                r = await rpc("Runtime.evaluate", {"expression": expr, "returnByValue": True})
                return (((r or {}).get("result") or {}).get("result") or {}).get("value")

            await rpc("Page.enable")
            await rpc("Runtime.enable")
            await rpc("Network.enable")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(26)
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*511nj.org/edge/trafficMap/getCameraDetail*",
                "requestStage": "Request"}]})
            print("MUESTREO")
            for n, cid in enumerate(IDS):
                idx = n % 2
                await ev("""(()=>{const e=[...document.querySelectorAll('li.camera-item')][%d];
                  if(e)e.click(); return !!e;})()""" % idx)
                p = await wait("Fetch.requestPaused", timeout=10)
                if not p:
                    print(cid, "SIN PAUSA")
                    continue
                pr = p["params"]
                await rpc("Fetch.continueRequest", {
                    "requestId": pr["requestId"], "postData": enc({"cameraId": cid})})
                resp = await wait("Network.responseReceived", timeout=10,
                                  pred=lambda e: "getCameraDetail" in e["params"].get("response", {}).get("url", ""))
                if not resp:
                    print(cid, "SIN RESPUESTA")
                    continue
                r = await rpc("Network.getResponseBody", {"requestId": resp["params"]["requestId"]})
                try:
                    d = json.loads(((r or {}).get("result") or {}).get("body", "{}")).get("data") or {}
                    print(cid, "->", d.get("cameraId"), "|", d.get("cameraUseFlag"), "|",
                          str(d.get("url"))[:110])
                except Exception as e:
                    print(cid, "ERROR", str(e)[:80])
                await asyncio.sleep(0.3)
            await rpc("Fetch.disable")
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
