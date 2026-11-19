"""Verificación de los endpoints de la etapa 4 contra el servidor local.

Comprueba zonas locales, clima animado con radio NWR, sensores, radio en vivo
(y sus streams ICY/HLS), corredor y el filtro de streams del comparador.

Uso: python tests/verify_extras.py
"""
import os
import requests

B = os.environ.get("HV_API", "http://127.0.0.1:8770")


def get(path, timeout=40):
    return requests.get(B + path, timeout=timeout)


def show(name, r, fn=None):
    try:
        data = r.json()
    except Exception:
        data = {"_text": r.text[:160]}
    print(f"{name}: {r.status_code} {fn(data) if fn else ''}")


def cam_fn(d):
    cams = d.get("cameras", [])
    z = [c for c in cams if c.get("localZones")]
    return (f"visible={len(cams)} zoned={len(z)} "
            f"summary={[(s['id'], s['cameraCount']) for s in d.get('meta', {}).get('zoneSummary', [])]}")


show("health", get("/api/health"), lambda d: f"cams={d.get('cameras')}")
show("cameras", get("/api/cameras"), cam_fn)
show("zones", get("/api/zones"),
     lambda d: f"zones={[(z['id'], z['cameraCount']) for z in d.get('zones', [])]}")
show("weather", get("/api/weather/live?lat=40.6209&lon=-74.6085"),
     lambda d: (f"anim={d.get('current', {}).get('animation')} "
                f"temp={d.get('current', {}).get('temperatureC')} "
                f"alerts={len(d.get('alerts', []))} "
                f"nwr={d.get('nwr', {}).get('callSign')}/{d.get('nwr', {}).get('frequencyMhz')} "
                f"conf={d.get('confidence')} err={d.get('errors')}"))
show("sensors", get("/api/sensors?lat=40.6209&lon=-74.6085"),
     lambda d: (f"usgs={len(d.get('usgs', []))} "
                f"extra={len(d.get('additional', []))} conf={d.get('confidence')}"))
show("radio", get("/api/radio/stations"),
     lambda d: f"{d.get('verifiedCount')}/{d.get('total')} cats={[c['id'] for c in d.get('categories', [])]}")
show("radio-meta", get("/api/radio/metadata?id=wbgo"),
     lambda d: f"now={str(d.get('nowPlaying'))[:50]} avail={d.get('available')}")

with requests.get(B + "/api/radio/stream/wbgo", stream=True, timeout=20) as r:
    chunk = next(r.iter_content(4096), b"")
    print("radio-stream-wbgo:", r.status_code, r.headers.get("content-type"),
          "bytes=", len(chunk), "audio=", chunk[:1] != b"<")

r = get("/api/radio/stream/wjlk", timeout=30)
txt = r.text[:600]
print("radio-stream-wjlk:", r.status_code, r.headers.get("content-type"),
      "proxyRefs=", txt.count("/api/radio/stream/wjlk/"), "extm3u=", "#EXTM3U" in txt)

show("corridor", requests.post(B + "/api/ai/corridor", json={"zone": "somerville"}, timeout=60),
     lambda d: (f"level={d.get('level')} score={d.get('score')} "
                f"events={d.get('eventCount')} reasons={len(d.get('reasons', []))}"))

show("streams-check", requests.post(
    B + "/api/streams/check",
    json={"ids": ["nj-11410", "nj-10000314", "nj-12600", "nj-1"]}, timeout=90),
    lambda d: (f"checked={d.get('checked')} working={d.get('working')} failed={d.get('failed')}"))

# Fuentes nuevas de la experiencia de conducción (mapa vectorial y contexto).
show("radar", get("/api/radar", timeout=60),
     lambda d: (f"frames={d.get('count')} host={d.get('host')} "
                f"attr={d.get('attribution')} cached={d.get('cached')} err={d.get('error')}"))
show("roadfacts", requests.post(
    B + "/api/roadfacts",
    json={"geometry": [[40.6209, -74.6085], [40.6259, -74.6035], [40.63, -74.60]]},
    timeout=180),
    lambda d: (f"count={d.get('count')} cameras={d.get('cameras')} "
               f"limits={d.get('limits')} cached={d.get('cached')} err={d.get('error')}"))
show("coastal", get("/api/coastal?lat=40.6209&lon=-74.6085", timeout=60),
     lambda d: (f"station={str((d.get('station') or {}).get('name'))} "
                f"near={str((d.get('station') or {}).get('near'))} "
                f"water={(d.get('waterLevel') or {}).get('valueM')} "
                f"storms={len(d.get('storms', []))} err={d.get('error')}"))
