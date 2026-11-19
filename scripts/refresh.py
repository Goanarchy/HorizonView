"""Refresco COMPLETO del inventario de 511NJ usando el navegador real.

La app oficial de 511NJ firma cada petición con WebCrypto (X-Browser-Proof, de un
solo uso) y cifra el cuerpo con AES-128-CBC. No se puede replicar con requests:
hay que dejar que la propia página firme una petición real e interceptarla con
CDP para sustituir el cuerpo cifrado por el de la cámara que queremos consultar.

Esto permite obtener el stream HLS de TODAS las cámaras del inventario, no solo
de las 48 del "NJ Turnpike Tour" que aparecían en la lista lateral.

Uso: python refresh.py
"""
import asyncio
import base64
import json
import os
import pathlib
import subprocess
import time
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
PORT = 9241
URL = "https://511nj.org/camera"
KEY = b"lIo3M)_83,ALC0Wz"
IV = b".%A}8Qvqm23jYVc9"
BATCH = 150  # recargar la página cada N cámaras para limpiar el estado de Angular


def log(msg):
    print(msg, flush=True)


def find_chrome():
    for p in CHROME_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    return None


def encrypted_body(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    data = AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(raw, 16)).hex()
    return base64.b64encode(json.dumps(
        {"encryptedData": data}, separators=(",", ":")).encode()).decode()


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


def zone_of(name):
    n = (name or "").lower()
    for key, zone in (
        ("garden state", "NJ · Garden State Pkwy"),
        ("turnpike", "NJ · Turnpike"),
        ("i-295", "NJ · I-295 / I-76"),
        ("i-76", "NJ · I-295 / I-76"),
        ("i-278", "NJ · I-278 / I-280"),
        ("i-280", "NJ · I-278 / I-280"),
        ("i-287", "NJ · I-287"),
        ("i-80", "NJ · I-80"),
        ("i-78", "NJ · I-78"),
    ):
        if key in n:
            return zone
    if n.startswith("nj-"):
        return "NJ · Rutas estatales"
    if n.startswith("us-"):
        return "NJ · US Routes"
    return "NJ · Otras vías"


async def run():
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome no encontrado; no se puede refrescar 511NJ")
    profile = pathlib.Path(
        r"C:\Users\Andrés Montoya\AppData\Local\Temp\opencode\ch_horizonview_refresh"
    )
    proc = subprocess.Popen([
        chrome, "--disable-gpu", "--no-first-run", "--disable-dev-shm-usage",
        "--ignore-certificate-errors", "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=" + str(profile),
        "--window-position=-2400,-2400", "--window-size=1200,900",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = get_target(PORT)
        if not target:
            raise RuntimeError("No se pudo iniciar el navegador de captura")
        async with websockets.connect(target["webSocketDebuggerUrl"],
                                      max_size=80_000_000) as ws:
            seq = 0
            events = []
            inventory = {}
            tours = []
            details = {}

            async def rpc(method, params=None, timeout=90):
                nonlocal seq
                seq += 1
                mid = seq
                await ws.send(json.dumps({"id": mid, "method": method,
                                          "params": params or {}}))
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
                if msg.get("method"):
                    events.append(msg)
                m = msg.get("method", "")
                p = msg.get("params", {})
                if m == "Network.responseReceived":
                    resp = p.get("response", {})
                    u = resp.get("url", "")
                    if "getCameraDataByTourId" in u:
                        inventory[p.get("requestId")] = resp.get("status")
                    elif "getTourList" in u:
                        tours.append(p.get("requestId"))

            async def wait(method, timeout=15, pred=None):
                deadline = time.time() + timeout
                while time.time() < deadline:
                    for e in list(events):
                        if e.get("method") == method and (pred is None or pred(e)):
                            events.remove(e)
                            return e
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.6))
                        handle(msg)
                    except asyncio.TimeoutError:
                        pass
                return None

            async def drain(seconds):
                deadline = time.time() + seconds
                while time.time() < deadline:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                        handle(msg)
                    except asyncio.TimeoutError:
                        pass

            async def body_of(rid):
                r = await rpc("Network.getResponseBody", {"requestId": rid})
                return ((r or {}).get("result") or {}).get("body", "")

            async def ev(expr):
                r = await rpc("Runtime.evaluate", {"expression": expr,
                                                   "returnByValue": True})
                return (((r or {}).get("result") or {}).get("result") or {}).get("value")

            await rpc("Network.enable")
            await rpc("Page.enable")
            await rpc("Runtime.enable")
            log("Abriendo 511NJ…")
            await rpc("Page.navigate", {"url": URL})
            await asyncio.sleep(26)
            await drain(6)

            raw = []
            for rid in list(inventory.keys()):
                try:
                    raw = json.loads(await body_of(rid)).get("data") or []
                except Exception:
                    pass
                if raw:
                    break
            log("Inventario completo: %d cámaras" % len(raw))
            if not raw:
                raise RuntimeError("511NJ no devolvió inventario")

            tour_raw = []
            for rid in tours[-1:]:
                try:
                    tour_raw = json.loads(await body_of(rid)).get("data") or []
                except Exception:
                    pass
            tour_names = [t.get("name") for t in tour_raw]
            log("Tours disponibles: %d" % len(tour_names))

            # Conservar la respuesta cruda del inventario: incluye la
            # pertenencia a tours oficiales, que el archivo normalizado no guarda.
            (DATA / "nj_raw_inventory.json").write_text(
                json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "tours": tour_raw, "cameras": raw},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            if os.environ.get("NJ_TOURS_ONLY") == "1":
                log("Solo tours: inventario crudo guardado.")
                return len(raw)

            # Obtener el detalle (stream) de cada cámara. La UI solo permite hacer
            # clic en las cámaras "rojas", pero interceptamos la petición firmada
            # y sustituimos el cameraId por el que necesitamos.
            log("Capturando streams de todas las cámaras…")
            await rpc("Fetch.enable", {"patterns": [{
                "urlPattern": "*511nj.org/edge/trafficMap/getCameraDetail*",
                "requestStage": "Request"}]})

            total = len(raw)
            done = 0
            for i, c in enumerate(raw):
                cid = c.get("id")
                if not cid:
                    continue
                try:
                    int(cid)
                except Exception:
                    continue
                if i and i % BATCH == 0:
                    # Recargar para evitar que Angular acumule suscripciones.
                    await rpc("Fetch.disable")
                    await rpc("Page.navigate", {"url": URL})
                    await asyncio.sleep(20)
                    await rpc("Fetch.enable", {"patterns": [{
                        "urlPattern": "*511nj.org/edge/trafficMap/getCameraDetail*",
                        "requestStage": "Request"}]})
                    events.clear()
                    log("Recargado en cámara %d/%d" % (i, total))

                idx = i % 2
                await ev("""(()=>{const e=[...document.querySelectorAll('li.camera-item')][%d];
                  if(e)e.click(); return !!e;})()""" % idx)
                paused = await wait("Fetch.requestPaused", timeout=10)
                if not paused:
                    log("Sin petición en cámara %s; se omite" % cid)
                    continue
                pr = paused["params"]
                await rpc("Fetch.continueRequest", {
                    "requestId": pr["requestId"],
                    "postData": encrypted_body({"cameraId": int(cid)}),
                })
                resp = await wait("Network.responseReceived", timeout=10,
                                  pred=lambda e: "getCameraDetail" in e["params"].get(
                                      "response", {}).get("url", ""))
                if resp:
                    try:
                        d = json.loads(await body_of(resp["params"]["requestId"]))
                        data = d.get("data") or {}
                        if data.get("url"):
                            details[int(cid)] = data
                    except Exception:
                        pass
                done += 1
                if done % 25 == 0:
                    log("Detalles: %d/%d (con stream: %d)" % (done, total, len(details)))
            await rpc("Fetch.disable")

            out = []
            for c in raw:
                try:
                    lat, lon = float(c["latitude"]), float(c["longitude"])
                except Exception:
                    continue
                cid = int(c["id"])
                d = details.get(cid) or {}
                name = c.get("name") or ("Cámara %s" % cid)
                out.append({
                    "id": "nj-%s" % cid,
                    "source": "511NJ",
                    "name": name,
                    "zone": zone_of(name),
                    "lat": round(lat, 6), "lon": round(lon, 6),
                    "onRoute": "turnpike" in name.lower() or "garden state" in name.lower(),
                    "enabled": not bool(c.get("stopCameraFlag")),
                    "stream": d.get("url"),
                    "kind": d.get("cameraUseFlag") or ("HLS" if d.get("url") else ""),
                    "priority": d.get("priority"),
                    "streamFetchedAt": time.strftime("%Y-%m-%d %H:%M:%S") if d.get("url") else None,
                    "official": "https://511nj.org/camera",
                })
            (DATA / "nj_cameras.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

            info = load_info = None
            try:
                info = json.loads((DATA / "source_info.json").read_text(encoding="utf-8"))
            except Exception:
                info = {}
            for s in info.get("sources", []):
                if "511NJ" in s.get("name", ""):
                    s["name"] = "511NJ · Camera List / getCameraDetail"
                    s["tour"] = "Todas las rutas (%d tours)" % len(tour_names)
                    s["tours"] = tour_names
                    s["cameras"] = len(out)
                    s["streams"] = sum(1 for c in out if c.get("stream"))
                    s["method"] = ("Inventario completo y streams de todas las cámaras "
                                   "capturados de la app oficial 511NJ en navegador real.")
            info["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            (DATA / "source_info.json").write_text(
                json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            log("OK %d cámaras, %d con stream" %
                (len(out), sum(1 for c in out if c.get("stream"))))
            return len(out)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        log("ERROR " + str(e)[:300])
        raise
