import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_mobile import CHROME, BASE, CDP, PORT  # noqa: E402
from audit_ui import GEO_JS  # noqa: E402

PORT = 9341
profile = tempfile.mkdtemp(prefix="horizonview_drive_")
proc = subprocess.Popen([
    CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions",
    f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
    "--window-size=390,844", "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

c = None
try:
    for _ in range(40):
        try:
            requests_ok = __import__("requests").get(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
            if requests_ok.ok:
                break
        except Exception:
            time.sleep(0.5)
    page = next(x for x in __import__("requests").get(f"http://127.0.0.1:{PORT}/json", timeout=5).json() if x["type"] == "page")
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
            return {"raw": str(raw)[:300]}

    state0 = probe({
        "inicio": "!document.getElementById('startModal').hidden",
        "conduccion": "!document.getElementById('driveShell').hidden",
        "guia": "!document.getElementById('overlay').hidden",
        "pestanas": "document.querySelectorAll('.tabbar .tab').length",
    })
    print("INICIO", json.dumps(state0, ensure_ascii=False))
    c.shot("drive_01_inicio.png")

    c.js("document.getElementById('btnStartTrip').click()")
    time.sleep(1.0)
    print("SETUP", json.dumps(probe({
        "viaje": "document.body.dataset.tab",
        "shell": "!document.getElementById('driveShell').hidden",
        "modal": "!document.getElementById('tripSetup').hidden",
        "perfiles": "document.querySelectorAll('#tripProfiles .profile-card').length",
        "musica": "document.querySelectorAll('#tripMusicList .music-card').length",
        "destinos": "document.querySelectorAll('#tripQuick .chip').length",
    }), ensure_ascii=False))
    c.shot("drive_02_setup.png")

    c.js("document.querySelectorAll('#tripQuick .chip')[1].click()")
    time.sleep(2.0)
    c.js("document.querySelectorAll('#tripProfiles .profile-card')[2].click()")
    c.js("document.querySelectorAll('#tripMusicList .music-card')[1].click()")
    print("DESTINO", json.dumps(probe({
        "resuelto": "document.getElementById('tripDestResolved').textContent.slice(0,120)",
        "perfil": "document.querySelector('#tripProfiles .profile-card.on b').textContent",
        "musica": "document.querySelector('#tripMusicList .music-card.on b').textContent",
    }), ensure_ascii=False))

    c.js("document.getElementById('btnTripGo').click()")
    time.sleep(14)
    print("RUTA", json.dumps(probe({
        "eta": "document.getElementById('driveEta').textContent",
        "restante": "document.getElementById('driveLeft').textContent",
        "camara": "document.getElementById('driveNext').textContent",
        "progreso": "document.getElementById('driveProgressBar').style.width",
        "chips": "document.querySelectorAll('#driveChips .drive-chip').length",
        "chipTextos": "[...document.querySelectorAll('#driveChips .drive-chip b')].map(x=>x.textContent).slice(0,6)",
        "mapa": "!!document.querySelector('#driveMap canvas.maplibregl-canvas')",
        "debug": "window.__driveMapDebug ? window.__driveMapDebug() : null",
        "limit": "document.getElementById('driveLimitValue').textContent + '|' + document.getElementById('driveLimit').hidden",
        "radarAttr": "!document.getElementById('driveAttrRadar').hidden",
        "recursosMapa": "performance.getEntriesByType('resource').filter(x=>/cartocdn|rainviewer/.test(x.name)).length",
        "hostsMapa": "[...new Set(performance.getEntriesByType('resource').filter(x=>/cartocdn|rainviewer/.test(x.name)).map(x=>new URL(x.name).host))]",
        "destino": "document.getElementById('driveDestName').textContent",
        "aqui": "document.getElementById('driveHere').textContent",
        "aquiFuente": "document.getElementById('driveHere').title",
        "oculto": "document.hidden",
    }), ensure_ascii=False))
    net = c.all_responses
    print("RED", json.dumps({
        "total": len(net),
        "carto": sum(1 for _, u in net if "cartocdn.com" in u),
        "rain": sum(1 for _, u in net if "rainviewer.com" in u),
        "rainStatuses": sorted({s for s, u in net if "rainviewer.com" in u}),
        "overpass": sum(1 for _, u in net if "overpass" in u),
        "cartoUrls": [u.split("?")[0][:120] for _, u in net if "cartocdn.com" in u][:6],
    }, ensure_ascii=False))
    timeline = []
    for _ in range(5):
        time.sleep(2)
        timeline.append(c.js("document.getElementById('driveProgressBar').style.width"))
    print("PROGRESO", json.dumps(timeline, ensure_ascii=False))

    c.js("document.getElementById('btnTripLog').click()")
    time.sleep(0.3)
    print("LOG_INICIAL", json.dumps(c.js(
        "[...document.querySelectorAll('#tripLogBody .log-item')].map(x=>x.innerText.replace(/\\n/g,' | '))"
    ), ensure_ascii=False)[:700])
    c.js("document.getElementById('btnTripLogClose').click()")

    print("GEOMETRIA", json.dumps(c.js(GEO_JS), ensure_ascii=False)[:600])
    c.shot("drive_03_ruta.png")

    c.js("document.getElementById('driveSpeed').value='110';document.getElementById('driveSpeed').dispatchEvent(new Event('change'))")
    spot_seen = False
    for _ in range(70):
        time.sleep(0.5)
        visible = c.js("!document.getElementById('camSpotlight').hidden")
        if visible:
            spot_seen = True
            print("SPOTLIGHT", json.dumps(probe({
                "nombre": "document.getElementById('spotName').textContent",
                "meta": "document.getElementById('spotMeta').textContent",
                "video": "document.getElementById('spotVideo').src.slice(0,90)",
                "conteo": "document.getElementById('spotCount').textContent",
            }), ensure_ascii=False))
            c.shot("drive_04_camara.png")
            c.js("document.getElementById('btnSpotSkip').click()")
            break
    print("SPOTLIGHT_VISTO", spot_seen)

    c.js("document.getElementById('btnTripLog').click()")
    time.sleep(0.5)
    print("BITACORA", json.dumps(probe({
        "items": "document.querySelectorAll('#tripLogBody .log-item').length",
        "primero": "document.querySelector('#tripLogBody .log-item b')?.textContent || ''",
    }), ensure_ascii=False))
    c.js("document.getElementById('btnTripLogClose').click()")

    c.js("document.getElementById('btnDriveData').click()")
    time.sleep(1.0)
    print("DATOS", json.dumps(probe({
        "pestana": "document.body.dataset.tab",
        "shell": "!document.getElementById('driveShell').hidden",
        "admin": "getComputedStyle(document.querySelector('.app')).display !== 'none'",
    }), ensure_ascii=False))
    net2 = c.all_responses
    print("RED_FINAL", json.dumps({
        "total": len(net2),
        "mvt": sum(1 for _, u in net2 if ".mvt" in u),
        "carto": sum(1 for _, u in net2 if "cartocdn.com" in u),
        "rain": sum(1 for _, u in net2 if "rainviewer.com" in u),
        "mvtUrls": [u[:130] for _, u in net2 if ".mvt" in u][:4],
        "mvtReq": sum(1 for u in c.all_requests if ".mvt" in u),
        "mvtReqUrls": [u[:130] for u in c.all_requests if ".mvt" in u][:4],
        "baseSource": "window.__driveMapDebug && window.__driveMapDebug().baseSource",
    }, ensure_ascii=False))
    print("ERRORES", json.dumps(c.errors[:6], ensure_ascii=False))
    print("HTTP", json.dumps(c.responses[:6], ensure_ascii=False))
finally:
    if c:
        try:
            c.ws.close()
        except Exception:
            pass
    proc.terminate()
