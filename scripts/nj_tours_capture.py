"""Captura la pertenencia real de cada cámara 511NJ a los 85 tours oficiales.

La app de 511NJ firma y cifra cada petición; se deja que la propia página
genere la petición y se sustituye el cuerpo cifrado por {"tourId": id}.
Resultado: data/nj_tours.json con IDs por tour y tours por cámara.
"""
import asyncio
import json
import pathlib
import subprocess
import sys
import time

import websockets

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh import DATA, URL, encrypted_body, find_chrome, get_target, log

PORT = 9250


async def run():
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome no encontrado")
    raw_info = json.loads((DATA / "nj_raw_inventory.json").read_text(encoding="utf-8-sig"))
    tours = raw_info.get("tours") or []
    if not tours:
        raise RuntimeError("Falta data/nj_raw_inventory.json con la lista de tours")
    profile = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh")
    proc = subprocess.Popen([
        chrome, "--disable-gpu", "--no-first-run", "--ignore-certificate-errors",
        "--remote-debugging-port=%d" % PORT, "--user-data-dir=" + str(profile),
        "--window-position=-2400,-2400", "--window-size=1200,900", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = get_target(PORT)
        if not target:
            raise RuntimeError("No se pudo iniciar Chrome")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            seq = 0
            events = []

            async def rpc(method, params=None, timeout=60):
                nonlocal seq
                seq += 1
                mid = seq
                await ws.send(json.dumps({"id": mid, "method": method,
                                          "params": params or {}}))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
                    except asyncio.TimeoutError:
                        continue
                    handle(msg)
                    if msg.get("id") == mid:
                        return msg
                return None

            def handle(msg):
                if msg.get("method"):
                    events.append(msg)

            async def wait(method, pred=None, timeout=15):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    for e in list(events):
                        if e.get("method") == method and (pred is None or pred(e)):
                            events.remove(e)
                            return e
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                        handle(msg)
                    except asyncio.TimeoutError:
                        pass
                return None

            def is_tour_request(e):
                return "getCameraDataByTourId" in e.get("params", {}).get(
                    "request", {}).get("url", "")

            def is_tour_response(e):
                return "getCameraDataByTourId" in e.get("params", {}).get(
                    "response", {}).get("url", "")

            async def body_of(rid):
                r = await rpc("Network.getResponseBody", {"requestId": rid})
                return ((r or {}).get("result") or {}).get("body", "")

            await rpc("Network.enable")
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*getCameraDataByTourId*",
                "requestStage": "Request"}]})
            log("Abriendo 511NJ…")
            await rpc("Page.navigate", {"url": URL})
            paused = await wait("Fetch.requestPaused", is_tour_request, timeout=60)
            if not paused:
                raise RuntimeError("511NJ no emitió la petición de tours")

            by_tour = {}
            for i, t in enumerate(tours):
                if i == 0:
                    p = paused
                else:
                    idx = (i + 1) % 3
                    await rpc("Runtime.evaluate", {"expression":
                        "(()=>{const e=document.querySelectorAll('li.pure-checkbox')[%d];"
                        "if(e)e.click();return !!e})()" % idx, "returnByValue": True})
                    p = await wait("Fetch.requestPaused", is_tour_request, timeout=12)
                    if not p:
                        log("Sin petición en tour %s; se omite" % t.get("name"))
                        by_tour[t.get("name")] = []
                        continue
                pr = p["params"]
                await rpc("Fetch.continueRequest", {
                    "requestId": pr["requestId"],
                    "postData": encrypted_body({"tourId": int(t["id"])}),
                })
                resp = await wait("Network.responseReceived", is_tour_response, timeout=12)
                ids = []
                if resp:
                    try:
                        data = json.loads(await body_of(resp["params"]["requestId"])).get("data") or []
                        ids = [int(c["id"]) for c in data if c.get("id")]
                    except Exception:
                        pass
                by_tour[t.get("name")] = ids
                if (i + 1) % 10 == 0 or i + 1 == len(tours):
                    log("Tours %d/%d · %s: %d cámaras" %
                        (i + 1, len(tours), t.get("name"), len(ids)))

            by_camera = {}
            for name, ids in by_tour.items():
                for cid in ids:
                    by_camera.setdefault("nj-%s" % cid, []).append(name)
            out = {
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tours": [{"id": t["id"], "name": t["name"],
                           "cameras": len(by_tour.get(t["name"]) or [])}
                          for t in tours],
                "byCamera": by_camera,
            }
            (DATA / "nj_tours.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            log("OK %d tours · %d cámaras con tour" % (len(tours), len(by_camera)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(run())
