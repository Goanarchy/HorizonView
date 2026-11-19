"""Verificación móvil de HorizonView mediante Chrome CDP.

Abre el enlace público en un viewport de celular, simula GPS, comprueba la
lista de cámaras cercanas, reproduce una cámara, toma capturas y reporta
errores de consola. Uso: python tests/verify_mobile.py
"""
import base64
import os
import json
import pathlib
import subprocess
import tempfile
import time

import requests
import websocket

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = os.environ.get("HV_BASE") or (ROOT / "URL_Movil.txt").read_text(encoding="utf-8-sig").strip().rstrip("/")
PORT = 9333


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=40)
        self.n = 0
        self.errors = []
        self.responses = []
        self.all_responses = []
        self.all_requests = []

    def call(self, method, params=None, quiet=False):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                self.errors.append("JS: " + json.dumps(msg["params"].get("exceptionDetails", {}))[:300])
            elif msg.get("method") == "Log.entryAdded":
                e = msg["params"].get("entry", {})
                if e.get("level") == "error":
                    self.errors.append("LOG: " + e.get("text", "")[:300])
            elif msg.get("method") == "Network.requestWillBeSent":
                self.all_requests.append(msg["params"].get("request", {}).get("url", ""))
            elif msg.get("method") == "Network.responseReceived":
                resp = msg["params"].get("response", {})
                self.all_responses.append((resp.get("status"), resp.get("url", "")))
                if resp.get("status", 0) >= 400:
                    self.responses.append((resp.get("status"), resp.get("url", "")))
            if msg.get("id") == mid:
                if "error" in msg and not quiet:
                    return {"error": msg["error"]}
                return msg.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "error" in r:
            return {"error": r["error"]}
        return r.get("result", {}).get("value")

    def shot(self, name):
        r = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        data = r.get("data")
        if not data:
            return None
        out = ROOT / "docs" / "screenshots" / name
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(base64.b64decode(data))
        return str(out)


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_cdp_")
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
        "--window-size=390,844", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        for _ in range(40):
            try:
                version = requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=1).json()
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Chrome CDP no respondió")

        pages = requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json()
        page = next(p for p in pages if p.get("type") == "page")
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Runtime.enable")
        cdp.call("Log.enable")
        cdp.call("Page.enable")

        # Permiso de geolocación en el origen público.
        try:
            browser = CDP(version["webSocketDebuggerUrl"])
            browser.call("Browser.grantPermissions", {
                "origin": BASE, "permissions": ["geolocation"],
            }, quiet=True)
        except Exception:
            pass

        url = BASE + "/?nowizard=1&theme=dark"
        cdp.call("Page.navigate", {"url": url})
        time.sleep(6)

        print("URL:", url)
        print("INICIO:", cdp.js("""JSON.stringify({
          ancho: innerWidth, scroll: document.documentElement.scrollWidth,
          tabbar: getComputedStyle(document.querySelector('.tabbar')).display,
          items: document.querySelectorAll('.item').length,
          contador: document.getElementById('listCount').textContent,
          health: document.getElementById('stTotal').textContent,
          titulo: document.title
        })"""))

        cdp.call("Emulation.setGeolocationOverride", {
            "latitude": 39.680817, "longitude": -75.47113, "accuracy": 5,
        })
        cdp.js("document.querySelector('.tabbar .tab[data-tab=cerca]').click()")
        time.sleep(0.8)
        cdp.js("document.getElementById('btnGps').click()")
        for _ in range(45):
            time.sleep(1)
            state = cdp.js("document.getElementById('localStatus').textContent")
            if state and "Comprobando" not in state:
                break

        print("GPS:", cdp.js("""JSON.stringify({
          pestana: document.body.dataset.tab,
          etiqueta: document.getElementById('gpsLabel').textContent,
          meta: document.getElementById('nearMeta').textContent,
          cantidad: document.querySelectorAll('#nearList .ncard').length,
          primera: document.querySelector('#nearList .ncard .nm') && document.querySelector('#nearList .ncard .nm').textContent,
          distancia: document.querySelector('#nearList .ncard .go') && document.querySelector('#nearList .ncard .go').textContent,
          aviso: document.getElementById('gpsInfo').textContent.trim().slice(0,160)
        })"""))

        cdp.js("document.querySelector('.tabbar .tab[data-tab=locales]').click()")
        time.sleep(1.5)
        print("LOCALES:", cdp.js("""JSON.stringify({
          pestana: document.body.dataset.tab,
          estado: document.getElementById('localStatus').textContent,
          radio: document.getElementById('radiusKm').value,
          cantidad: document.querySelectorAll('#localList .ncard').length,
          primera: document.querySelector('#localList .ncard .nm') && document.querySelector('#localList .ncard .nm').textContent,
          distancia: document.querySelector('#localList .ncard .go') && document.querySelector('#localList .ncard .go').textContent,
          sinStream: [...document.querySelectorAll('#localList .ncard')].filter(n=>!n.textContent.includes('verificado')).length,
          fueraDeServicio: [...document.querySelectorAll('#localList .ncard')].filter(n=>/Unavailable|Offline|Inactive/i.test(n.textContent)).length
        })"""))
        print("CAPTURA:", cdp.shot("horizonview-movil-locales.png"))

        cdp.js("document.querySelector('#localList .ncard') && document.querySelector('#localList .ncard').click()")
        time.sleep(8)
        print("VISOR:", cdp.js("""JSON.stringify({
          pestana: document.body.dataset.tab,
          camara: document.getElementById('vName').textContent,
          badge: document.getElementById('viewBadge').textContent,
          listo: document.getElementById('video').readyState,
          anchoVideo: document.getElementById('video').videoWidth,
          error: document.getElementById('playerErr').hidden ? '' : document.getElementById('playerErr').textContent,
          zoomVisible: !document.getElementById('stageTools').hidden
        })"""))

        print("CAPTURA:", cdp.shot("horizonview-movil-dark.png"))
        cdp.js("document.getElementById('btnTheme').click()")
        time.sleep(1)
        print("CAPTURA:", cdp.shot("horizonview-movil-light.png"))

        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1360, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        time.sleep(1.5)
        print("ESCRITORIO:", cdp.js("""JSON.stringify({
          scroll: document.documentElement.scrollWidth,
          tabbar: getComputedStyle(document.querySelector('.tabbar')).display,
          columnas: getComputedStyle(document.querySelector('.main')).gridTemplateColumns
        })"""))
        print("CAPTURA:", cdp.shot("horizonview-escritorio-light.png"))

        print("ERRORES:", json.dumps(cdp.errors, ensure_ascii=False))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
