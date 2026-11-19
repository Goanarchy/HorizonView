"""Prueba de GPS en Newark (fuera del corredor Turnpike)."""
import json
import pathlib
import subprocess
import sys
import tempfile
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from verify_mobile import BASE, CHROME, CDP  # noqa: E402

PORT = 9341
LAT, LON = 40.7355, -74.1724


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_newark_")
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
        page = next(p for p in requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json()
                    if p.get("type") == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Runtime.enable")
        c.call("Log.enable")
        c.call("Page.enable")
        try:
            browser = CDP(version["webSocketDebuggerUrl"])
            browser.call("Browser.grantPermissions", {
                "origin": BASE, "permissions": ["geolocation"],
            }, quiet=True)
        except Exception:
            pass
        c.call("Page.navigate", {"url": BASE + "/?nowizard=1&theme=dark"})
        time.sleep(6)
        c.call("Emulation.setGeolocationOverride", {
            "latitude": LAT, "longitude": LON, "accuracy": 8,
        })
        c.js("document.querySelector('.tabbar .tab[data-tab=cerca]').click()")
        time.sleep(0.5)
        c.js("document.getElementById('btnGps').click()")
        for _ in range(60):
            time.sleep(1)
            st = c.js("document.getElementById('localStatus').textContent")
            if st and "Comprobando" not in st:
                break
        print("GPS NEWARK:", c.js("""JSON.stringify({
          pestana: document.body.dataset.tab,
          aviso: document.getElementById('gpsInfo').textContent.trim(),
          meta: document.getElementById('nearMeta').textContent,
          radio: document.getElementById('radiusKm').value,
          cantidad: document.querySelectorAll('#nearList .ncard').length,
          primera: document.querySelector('#nearList .ncard .nm') && document.querySelector('#nearList .ncard .nm').textContent,
          distancia: document.querySelector('#nearList .ncard .go') && document.querySelector('#nearList .ncard .go').textContent,
          sinStream: [...document.querySelectorAll('#nearList .ncard')].filter(n=>!n.textContent.includes('verificado')).length
        })"""))
        print("CAPTURA:", c.shot("horizonview-gps-newark.png"))
        print("ERRORES:", json.dumps(c.errors, ensure_ascii=False))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
