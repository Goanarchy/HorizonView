"""Verifica favoritos persistentes, filtro y boton de reporte (etapa 1)."""
import json
import subprocess
import tempfile
import time

import requests

from verify_mobile import CHROME, BASE, CDP, PORT


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_stage1_")
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

        first_id = c.js("document.querySelector('#list .item').dataset.camId")
        c.js("document.querySelector('#list .fav').click()")
        time.sleep(0.4)
        stored = c.js("localStorage.getItem('horizonViewFavoritos') || ''")
        starred = c.js("document.querySelectorAll('#list .fav.on').length")
        print("FAVORITO:", json.dumps({"id": first_id, "guardado": first_id in stored, "estrellas": starred}))

        c.js("(()=>{const e=document.getElementById('favOnly');e.checked=true;e.dispatchEvent(new Event('change'))})()")
        time.sleep(0.5)
        filtro = c.js("JSON.stringify({contador:document.getElementById('listCount').textContent,filas:document.querySelectorAll('#list .item').length})")
        print("FILTRO:", filtro)

        c.js("(()=>{const e=document.getElementById('favOnly');e.checked=false;e.dispatchEvent(new Event('change'))})()")
        c.js("document.querySelector('#list .item').click()")
        time.sleep(0.5)
        viewer = c.js("JSON.stringify({fav:document.getElementById('btnFav').textContent.trim(),favDesactivado:document.getElementById('btnFav').disabled,reporteActivo:!document.getElementById('btnReport').disabled})")
        print("VISOR:", viewer)

        c.js("document.getElementById('btnReport').click()")
        time.sleep(0.2)
        armado = c.js("document.getElementById('btnReport').textContent.trim()")
        c.js("document.querySelectorAll('#list .item')[1].click()")
        time.sleep(0.3)
        reiniciado = c.js("document.getElementById('btnReport').textContent.trim()")
        print("REPORTE:", json.dumps({"armado": armado, "reiniciado": reiniciado}))

        c.call("Page.reload", {"ignoreCache": True})
        time.sleep(6)
        persist = c.js("JSON.stringify({guardado:(localStorage.getItem('horizonViewFavoritos')||'').includes(" + json.dumps(first_id) + "),estrella:!!document.querySelector('#list .fav.on')})")
        print("PERSISTENCIA:", persist)
        print("HTTP_ERRORES:", json.dumps(c.responses[:8], ensure_ascii=False))
        print("ERRORES:", json.dumps(c.errors, ensure_ascii=False))
    finally:
        p.terminate()
        try:
            p.wait(timeout=6)
        except Exception:
            p.kill()


if __name__ == "__main__":
    main()
