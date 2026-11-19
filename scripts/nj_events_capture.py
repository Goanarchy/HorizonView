"""Captura el feed oficial de eventos/incidentes/obras de 511NJ.

La app pública firma cada petición con WebCrypto (X-Browser-Proof) y cifra el
cuerpo AES-CBC, así que no se puede replicar con requests. Se deja que la propia
página realice la petición y se lee la respuesta con CDP.

Salida: data/nj_events.json con los eventos crudos y la hora de captura.
"""
import asyncio
import json
import pathlib
import sys
import time

import websockets

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh import DATA, find_chrome, get_target, log

PORT = 9251
URL = "https://511nj.org/"
PROFILE = pathlib.Path(r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_events")


async def run():
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome no encontrado")
    proc = __import__("subprocess").Popen([
        chrome, "--disable-gpu", "--no-first-run", "--ignore-certificate-errors",
        "--remote-debugging-port=%d" % PORT, "--user-data-dir=" + str(PROFILE),
        "--window-position=-2400,-2400", "--window-size=1200,900", "about:blank",
    ], stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL)
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
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
                    except asyncio.TimeoutError:
                        continue
                    if msg.get("method"):
                        events.append(msg)
                    if msg.get("id") == mid:
                        return msg
                return None

            def is_event_response(msg):
                return ("client/get/event" in msg.get("params", {}).get(
                    "response", {}).get("url", ""))

            await rpc("Network.enable")
            log("Abriendo 511NJ para capturar eventos…")
            await rpc("Page.navigate", {"url": URL})
            request_id = None
            deadline = time.time() + 90
            while time.time() < deadline:
                for e in list(events):
                    if e.get("method") == "Network.responseReceived" and is_event_response(e):
                        request_id = e["params"]["requestId"]
                        break
                if request_id:
                    break
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                except asyncio.TimeoutError:
                    continue
                if msg.get("method"):
                    events.append(msg)
            if not request_id:
                raise RuntimeError("511NJ no emitió /client/get/event")

            r = await rpc("Network.getResponseBody", {"requestId": request_id})
            raw = ((r or {}).get("result") or {}).get("body", "")
            payload = json.loads(raw)
            data = payload.get("data") or []
            out = {
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "511NJ · /client/get/event",
                "count": len(data),
                "events": data,
            }
            (DATA / "nj_events.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            nj = [e for e in data if str(e.get("state") or "").upper() in ("NJ", "DE")]
            log("OK %d eventos (%d de NJ/DE) guardados en data/nj_events.json" % (len(data), len(nj)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(run())
