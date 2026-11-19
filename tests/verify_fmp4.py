"""Comprueba reproducción real de una cámara fMP4 del nuevo host 511NJ."""
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

PORT = 9340
CAM = "nj-10710"  # NJ-21 @ Hamilton Street · nj-511.wink.co


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_fmp4_")
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
        "--window-size=390,844", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        page = next(p for p in requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json()
                    if p.get("type") == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Runtime.enable")
        c.call("Log.enable")
        c.call("Network.enable")
        c.call("Page.enable")
        url = f"{BASE}/?nowizard=1&theme=dark&cam={CAM}"
        c.call("Page.navigate", {"url": url})
        time.sleep(16)
        print("URL:", url)
        print("VIDEO:", c.js("""JSON.stringify({
          pestana: document.body.dataset.tab,
          camara: document.getElementById('vName').textContent,
          listo: document.getElementById('video').readyState,
          ancho: document.getElementById('video').videoWidth,
          actual: Math.round(document.getElementById('video').currentTime * 10) / 10,
          error: document.getElementById('playerErr').hidden ? '' : document.getElementById('playerErr').textContent,
          badge: document.getElementById('viewBadge').textContent
        })"""))
        shot = c.shot("horizonview-fmp4-nuevo-host.png")
        print("CAPTURA:", shot)
        print("ERRORES:", json.dumps(c.errors, ensure_ascii=False))
        print("HTTP >=400:", json.dumps(c.responses[:12], ensure_ascii=False))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=6)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
