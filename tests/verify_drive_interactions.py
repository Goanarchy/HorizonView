import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_mobile import CHROME, BASE, CDP  # noqa: E402

PORT = 9351
proc = subprocess.Popen([
    CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions",
    f"--remote-debugging-port={PORT}", f"--user-data-dir={tempfile.mkdtemp()}",
    "--window-size=390,844", "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
c = None
try:
    import requests
    for _ in range(40):
        try:
            if requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=1).ok:
                break
        except Exception:
            time.sleep(0.5)
    page = next(x for x in requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json() if x["type"] == "page")
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Runtime.enable"); c.call("Log.enable"); c.call("Network.enable"); c.call("Page.enable")
    c.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True})
    c.call("Page.navigate", {"url": BASE + "/"})
    time.sleep(6)

    def probe(expr):
        if isinstance(expr, dict):
            expr = "{" + ", ".join("%s:(%s)" % (json.dumps(k), v) for k, v in expr.items()) + "}"
        raw = c.js("JSON.stringify(" + expr + ")")
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": str(raw)[:200]}

    c.js("document.getElementById('btnStartTrip').click()")
    time.sleep(1.2)
    # Destino muy cercano a un maxspeed real de OSM verificado en 40.622, -74.604.
    c.js("(()=>{const e=document.getElementById('tripDest');e.value='40.6220,-74.6045';e.dispatchEvent(new Event('input'))})()")
    time.sleep(0.2)
    c.js("document.getElementById('btnTripGo').click()")
    time.sleep(28)
    print("BASE", json.dumps(probe({
        "destino": "document.getElementById('tripDestResolved').textContent.slice(0,90)",
        "debug": "window.__driveMapDebug()",
        "limite": "document.getElementById('driveLimitValue').textContent + '|' + document.getElementById('driveLimit').hidden",
        "tituloLimite": "document.getElementById('driveLimit').title",
        "chips": "[...document.querySelectorAll('#driveChips .drive-chip b')].map(x=>x.textContent)",
    }), ensure_ascii=False))

    def toggle(cid, checked, wait=0.8):
        c.js("(()=>{const e=document.getElementById('%s');e.checked=%s;e.dispatchEvent(new Event('change'))})()" % (cid, "true" if checked else "false"))
        time.sleep(wait)
        return probe({
            "visible": "window.__driveMapDebug().visible",
            "radarAttr": "!document.getElementById('driveAttrRadar').hidden",
            "satAttr": "!document.getElementById('driveAttrSatellite').hidden",
            "satTime": "document.getElementById('driveSatelliteTime').textContent",
            "satSource": "window.__driveMapDebug().satelliteSource",
            "satTimeDebug": "window.__driveMapDebug().satelliteTime",
        })

    print("RADAR_OFF", json.dumps(toggle("dlRadar", False), ensure_ascii=False))
    print("RADAR_ON", json.dumps(toggle("dlRadar", True), ensure_ascii=False))
    print("SAT_ON", json.dumps(toggle("dlSatellite", True, 4.0), ensure_ascii=False))
    print("SAT_OFF", json.dumps(toggle("dlSatellite", False), ensure_ascii=False))
    print("SAT_ON_2", json.dumps(toggle("dlSatellite", True), ensure_ascii=False))
    print("ROAD_OFF", json.dumps(toggle("dlRoad", False), ensure_ascii=False))
    print("ROAD_ON", json.dumps(toggle("dlRoad", True), ensure_ascii=False))
    print("COAST_OFF", json.dumps(toggle("dlCoastal", False), ensure_ascii=False))
    print("COAST_ON", json.dumps(toggle("dlCoastal", True), ensure_ascii=False))

    c.js("document.getElementById('btnDriveOverview').click()")
    time.sleep(1.6)
    print("OVERVIEW", json.dumps(probe({
        "zoom": "window.__driveMapDebug().zoom",
        "follow": "window.__driveMapDebug().follow",
    }), ensure_ascii=False))

    c.js("document.getElementById('btnDriveRecenter').click()")
    time.sleep(1.4)
    print("RECENTER", json.dumps(probe({
        "zoom": "window.__driveMapDebug().zoom",
        "follow": "window.__driveMapDebug().follow",
    }), ensure_ascii=False))

    c.js("document.getElementById('btnTheme').click()")
    time.sleep(8)
    print("TEMA_CLARO", json.dumps(probe({
        "tema": "document.documentElement.getAttribute('data-theme')",
        "style": "window.__driveMapDebug().style",
        "layers": "window.__driveMapDebug().layers.length",
        "visible": "window.__driveMapDebug().visible",
        "satSource": "window.__driveMapDebug().satelliteSource",
        "satAttr": "!document.getElementById('driveAttrSatellite').hidden",
        "canvas": "!!document.querySelector('#driveMap canvas.maplibregl-canvas')",
    }), ensure_ascii=False))
    c.js("document.getElementById('btnTheme').click()")
    time.sleep(8)
    print("TEMA_OSCURO", json.dumps(probe({
        "tema": "document.documentElement.getAttribute('data-theme')",
        "style": "window.__driveMapDebug().style",
        "layers": "window.__driveMapDebug().layers.length",
    }), ensure_ascii=False))
    print("ERRORES", json.dumps(c.errors[:8], ensure_ascii=False))
    print("HTTP", json.dumps(c.responses[:8], ensure_ascii=False))
finally:
    if c:
        try:
            c.ws.close()
        except Exception:
            pass
    proc.terminate()
