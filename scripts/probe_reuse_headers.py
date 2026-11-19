"""Prueba: reutilizar headers firmados de 511NJ para consultar detalles por Python."""
import asyncio
import json
import pathlib
import subprocess
import time
import urllib.request

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import websockets

PORT = 9358
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
        captured = {}
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            seq = 0

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
                    m = msg.get("method", "")
                    p = msg.get("params", {})
                    if m == "Network.requestWillBeSent":
                        r = p.get("request", {})
                        if "getCameraDetail" in r.get("url", ""):
                            captured["headers"] = dict(r.get("headers") or {})
                            captured["url"] = r.get("url")
                            captured["body"] = r.get("postData")
                    if msg.get("id") == mid:
                        return msg
                return None

            await rpc("Network.enable")
            await rpc("Page.enable")
            await rpc("Runtime.enable")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(26)
            print("cargado")
            for i in range(3):
                r = await rpc("Runtime.evaluate", {"expression": """(()=>{
                  const e=[...document.querySelectorAll('li.camera-item')][%d];
                  if(!e)return 'end'; e.click(); return (e.textContent||'').trim().slice(0,60);})()""" % i,
                    "returnByValue": True})
                print("clic", i, (((r or {}).get("result") or {}).get("result") or {}).get("value"))
                await asyncio.sleep(3)
                if captured.get("headers"):
                    break
        print("header capturado:", json.dumps(captured, ensure_ascii=False)[:900])
        if not captured.get("headers"):
            print("sin headers")
            return
        h = {k: v for k, v in captured["headers"].items()
             if k.lower() in ("x-browser-proof", "x-browser-public-key",
                              "content-type", "referer", "origin", "user-agent", "token")}
        print("headers útiles:", list(h.keys()))
        s = requests.Session()
        for cid in (55, 51, 681, 740):
            body = json.dumps({"encryptedData": encrypt({"cameraId": cid})}, separators=(",", ":"))
            r = s.post(captured["url"], headers=h, data=body, timeout=25)
            print("cameraId", cid, "->", r.status_code, r.text[:260].replace("\n", " "))
            time.sleep(0.4)
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
