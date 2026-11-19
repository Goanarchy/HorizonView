"""Verifica el mapa Leaflet y el filtro por tours oficiales a 390x844."""
import json
import subprocess
import tempfile
import time

import requests

from verify_mobile import CHROME, BASE, CDP, PORT


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_map_")
    p = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={PORT}",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        page = next(x for x in requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json() if x["type"] == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Runtime.enable")
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
        })
        c.call("Page.navigate", {"url": BASE + "/?nowizard=1&theme=dark"})
        time.sleep(6)

        tour_info = c.js("JSON.stringify({opciones:document.getElementById('tour').options.length,primera:document.getElementById('tour').options[1].textContent})")
        print("TOURS:", tour_info)

        c.js("(()=>{const e=document.getElementById('tour');e.value='NJ Turnpike Tour';e.dispatchEvent(new Event('change'))})()")
        time.sleep(0.5)
        print("FILTRO_TOUR:", c.js("JSON.stringify({valor:document.getElementById('tour').value,contador:document.getElementById('listCount').textContent,filas:document.querySelectorAll('#list .item').length})"))
        c.js("(()=>{const e=document.getElementById('tour');e.value='';e.dispatchEvent(new Event('change'))})()")

        c.js("document.querySelector('.tabbar .tab[data-tab=mapa]').click()")
        time.sleep(5)
        print("MAPA:", c.js("JSON.stringify({contenedor:!!document.querySelector('#map .leaflet-container'),lienzo:!!document.querySelector('#map canvas'),teselas:document.querySelectorAll('#map .leaflet-tile-loaded').length,conteo:document.getElementById('mapCount').textContent,pestana:document.body.dataset.tab})"))

        c.js("(()=>{const e=document.getElementById('mapVerified');e.checked=true;e.dispatchEvent(new Event('change'))})()")
        time.sleep(0.6)
        print("SOLO_VERIFICADAS:", c.js("document.getElementById('mapCount').textContent"))

        c.js("document.getElementById('btnMapFit').click()")
        time.sleep(0.8)
        print("AJUSTAR:", c.js("document.getElementById('mapCount').textContent"))

        print("HTTP_ERRORES:", json.dumps(c.responses[:10], ensure_ascii=False))
        print("ERRORES:", json.dumps(c.errors, ensure_ascii=False))
    finally:
        p.terminate()
        try:
            p.wait(timeout=6)
        except Exception:
            p.kill()


if __name__ == "__main__":
    main()
