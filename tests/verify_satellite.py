"""Verificación autocontenida de la capa satelital (NASA GIBS / GOES-East).

Arranca una copia del servidor en un puerto propio, comprueba `/api/satellite`,
descarga una tesela real y confirma que la interfaz expone el interruptor y la
atribución. No necesita clave ni detiene la instalación habitual.

Uso: python tests/verify_satellite.py
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("HV_SAT_PORT", "9344"))
BASE = "http://127.0.0.1:%d" % PORT
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

env = dict(os.environ, HV_PORT=str(PORT))
proc = subprocess.Popen([sys.executable, str(ROOT / "src" / "server.py")],
                        cwd=str(ROOT), env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            if requests.get(BASE + "/api/health", timeout=1).ok:
                break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("El servidor de prueba no arrancó")

    response = requests.get(BASE + "/api/satellite", timeout=60)
    data = response.json()
    assert response.status_code == 200, response.status_code
    assert data.get("ok"), data
    assert TIME_RE.match(data.get("time") or ""), data.get("time")
    assert data.get("sample", {}).get("status") == 200, data.get("sample")
    assert "image/" in data.get("sample", {}).get("contentType", ""), data.get("sample")
    assert data.get("attribution") and data.get("attributionUrl"), data
    assert data.get("note") and "predicción" in data["note"], data.get("note")
    tiles = data.get("tiles") or []
    assert tiles and "gibs.earthdata.nasa.gov" in tiles[0], tiles
    assert "{z}/{y}/{x}" in tiles[0], tiles[0]

    tile = tiles[0].replace("{z}", "0").replace("{y}", "0").replace("{x}", "0")
    probe = requests.get(tile, headers={"User-Agent": "HorizonView/4.0 (test)"}, timeout=30)
    assert probe.status_code == 200, probe.status_code
    assert probe.headers.get("Content-Type", "").startswith("image/"), probe.headers
    assert probe.headers.get("Access-Control-Allow-Origin") == "*", probe.headers

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "src" / "app.js").read_text(encoding="utf-8")
    assert 'id="dlSatellite"' in html and 'id="driveAttrSatellite"' in html
    assert '"drive-satellite"' in script and '"/api/satellite"' in script

    print("SAT_OK", {
        "time": data["time"],
        "label": data.get("timeLabel"),
        "sample": data["sample"],
        "tileStatus": probe.status_code,
        "tileType": probe.headers.get("Content-Type"),
        "maxzoom": data.get("maxzoom"),
        "cached": data.get("cached"),
    })
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
