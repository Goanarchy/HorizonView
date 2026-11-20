"""HorizonView · servidor local.

Expone el inventario verificado de cámaras públicas entre Delaware y Nueva
Jersey, un proxy HLS para poder ver los streams oficiales desde el navegador y
un endpoint de refresco que vuelve a consultar las fuentes oficiales.

Sin dependencias externas salvo `requests` (ya instalada). Arrancar con
start.bat o: python src/server.py
"""
import http.server
import json
import math
import pathlib
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import ai
import extras

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
PORT = int(__import__("os").environ.get("HV_PORT", "8770"))
ai.configure(DATA)

DE_FEED = "https://tmc.deldot.gov/json/videocamera.json?id=4yte"
NJ_REFERER = "https://511nj.org/"
DE_REFERER = "https://deldot.gov/"
NJ_HOSTS = ("njtpk-wink.xcmdata.org", "nj-511.wink.co")
DE_HOSTS = ("video.deldot.gov", "tmc.deldot.gov")
ALLOWED_HOSTS = NJ_HOSTS + DE_HOSTS
# Emisoras públicas: sufijos verificados por los proveedores de cada stream.
# El host de CloudFront es el CDN real que sirve los segmentos .aac de las
# playlists HLS verificadas de NJ 101.5 y 94.3 The Point (amperwave).
RADIO_HOSTS = ("amperwave.net", "cdnstream1.com", "wqxr.org", "wfmu.org",
               "streamguys1.com", "d25j5qm9y8ulag.cloudfront.net",
               # CDN de los bloques publicitarios que la propia playlist oficial
               # de NJ 101.5 inserta entre segmentos (verificado HTTP 200).
               "d1n065hnrro57i.cloudfront.net")
DEFAULT_LAT, DEFAULT_LON = 40.6209, -74.6085  # Somerville, NJ (centro por defecto)
FAILURES_FILE = DATA / "stream_failures.json"
FAILURE_TTL = 6 * 3600  # un fallo real de reproducción oculta la cámara 6 horas
KNOWN_BAD = {"de-KCAM001": "Playlist HLS devolvió 404 en verificación del 2026-11-18"}

JOBS = {}
JOBS_LOCK = threading.Lock()
CACHE = {"cameras": None, "meta": None}
NEAR_CACHE = {"key": None, "at": 0.0, "data": None}
NEAR_TTL = 300
FAILURES = None
TOURS = None
BAD_STATUS = {"unavailable", "offline", "inactive", "down", "disabled", "not active"}


def host_allowed(host):
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def referer_for(host):
    host = (host or "").lower()
    return NJ_REFERER if any(host == h or host.endswith("." + h) for h in NJ_HOSTS) else DE_REFERER


def radio_host_allowed(host):
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in RADIO_HOSTS)


def hls_join(base, ref):
    """Une una URI HLS conservando el token otp de la URL original."""
    url = urllib.parse.urljoin(base, ref)
    query = urllib.parse.urlparse(base).query
    if query and not urllib.parse.urlparse(url).query:
        url += ("&" if "?" in url else "?") + query
    return url


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def de_zone(county):
    return "DE · " + (county or "Delaware")


def normalize_de(feed):
    out = []
    for c in feed.get("videoCameras") or []:
        try:
            lat, lon = float(c["lat"]), float(c["lon"])
        except Exception:
            continue
        urls = c.get("urls") or {}
        cid = c.get("id")
        if not cid:
            continue
        out.append({
            "id": "de-%s" % cid,
            "source": "DelDOT",
            "name": c.get("title") or cid,
            "zone": de_zone(c.get("county")),
            "lat": round(lat, 6), "lon": round(lon, 6),
            "onRoute": (c.get("county") or "") == "New Castle",
            "enabled": bool(c.get("enabled")) and c.get("status") == "Active",
            "stream": urls.get("m3u8s") or urls.get("m3u8"),
            "kind": "HLS",
            "status": c.get("status"),
            "official": "https://deldot.gov/Traffic/cameras/index.shtml?dc=viewer&cameraID=" + str(cid),
        })
    return out


def load_tours():
    """Pertenencia real de cámaras 511NJ a los tours oficiales (85)."""
    global TOURS
    if TOURS is None:
        TOURS = load_json(DATA / "nj_tours.json", {}) or {}
    return TOURS


def cameras(force=False):
    if force or CACHE["cameras"] is None:
        nj = load_json(DATA / "nj_cameras.json", []) or []
        de = load_json(DATA / "de_cameras.json", []) or []
        CACHE["cameras"] = nj + de
        CACHE["meta"] = load_json(DATA / "source_info.json", {}) or {}
        tours = load_tours()
        by_camera = tours.get("byCamera") or {}
        for c in CACHE["cameras"]:
            c["tours"] = sorted(by_camera.get(c["id"], [])) if c["source"] == "511NJ" else []
        CACHE["meta"]["tours"] = tours.get("tours") or []
        CACHE["meta"]["toursAt"] = tours.get("at")
        CACHE["meta"]["toursByCamera"] = by_camera
    return CACHE["cameras"], CACHE["meta"]


# ---------------------------------------------------------------------------
# Cámaras locales cercanas: solo operativas y con stream verificado
# ---------------------------------------------------------------------------
def load_failures():
    global FAILURES
    if FAILURES is None:
        FAILURES = load_json(FAILURES_FILE, {}) or {}
    return FAILURES


def report_failure(cid, reason):
    """Registra un fallo real de reproducción para ocultar la cámara."""
    global FAILURES
    with JOBS_LOCK:
        f = load_failures()
        key = str(cid)
        entry = dict(f.get(key) or {})
        entry["count"] = int(entry.get("count") or 0) + 1
        entry["last"] = time.time()
        entry["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        entry["reason"] = str(reason or "playback")[:160]
        c = next((x for x in CACHE.get("cameras") or [] if x.get("id") == cid), None)
        if c:
            entry["stream"] = c.get("stream")
            ai.record_signal(c, False, reason or "reporte manual", save=True)
        f[key] = entry
        FAILURES = f
        try:
            FAILURES_FILE.write_text(
                json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
        return entry


def is_reported_bad(c):
    cid = c.get("id")
    if cid in KNOWN_BAD:
        return True
    entry = load_failures().get(str(cid))
    if not entry:
        return False
    try:
        age = time.time() - float(entry.get("last") or 0)
    except Exception:
        return False
    if age >= FAILURE_TTL:
        return False
    # Si la fuente cambió el stream, se da una nueva oportunidad.
    expected = entry.get("stream")
    return not expected or expected == c.get("stream")


def is_operational(c):
    """Descarta cámaras dadas de baja, no disponibles o con fallo real conocido."""
    if c.get("enabled") is False or is_reported_bad(c):
        return False
    status = str(c.get("status") or "").strip().lower()
    return status not in BAD_STATUS


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def looks_like_playlist(text):
    head = (text or "").lstrip()[:2000].lower()
    return ("#extm3u" in head and "<html" not in head
            and "attention required" not in head and "just a moment" not in head)


def valid_video_bytes(body, content_type):
    if not body or len(body) < 512:
        return False
    low = body[:512].lower()
    if b"<html" in low or b"<!doctype" in low or b"attention required" in low:
        return False
    if body[:1] == b"\x47":  # sync byte MPEG-TS
        return True
    if len(body) >= 8:  # cajas ISO BMFF: ftyp, moof, mdat, styp
        size = int.from_bytes(body[:4], "big")
        if body[4:8] in (b"ftyp", b"moof", b"mdat", b"styp") and (size == 0 or size >= 8):
            return True
    ctype = (content_type or "").lower()
    return "video/mp2t" in ctype and len(body) > 1024


def probe_stream(c):
    """Verifica playlist real (incluso master) y bytes de video del segmento."""
    url = c.get("stream")
    if not url:
        return False
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not host_allowed(parts.hostname):
        return False
    headers = {"User-Agent": "Mozilla/5.0", "Referer": referer_for(parts.hostname),
               "Accept": "*/*"}
    try:
        r = requests.get(url, timeout=(5, 12), headers=headers)
        if r.status_code >= 400 or "html" in r.headers.get("Content-Type", "").lower():
            return False
        if not looks_like_playlist(r.text):
            return False

        media = [s.strip() for s in r.text.splitlines()
                 if s.strip() and not s.startswith("#")]
        if not media:
            return False
        base = url
        if "#EXT-X-STREAM-INF" in r.text:
            base = hls_join(url, media[0])
            if not host_allowed(urllib.parse.urlparse(base).hostname):
                return False
            mr = requests.get(base, timeout=(5, 12), headers=headers)
            if mr.status_code >= 400 or "html" in mr.headers.get("Content-Type", "").lower():
                return False
            if not looks_like_playlist(mr.text):
                return False
            media = [s.strip() for s in mr.text.splitlines()
                     if s.strip() and not s.startswith("#")]
            if not media:
                return False

        for ref in media[:3]:
            segment = hls_join(base, ref)
            if not host_allowed(urllib.parse.urlparse(segment).hostname):
                continue
            s = requests.get(segment, timeout=(5, 12),
                             headers={**headers, "Range": "bytes=0-8191"}, stream=True)
            try:
                if s.status_code >= 400 or s.headers.get("Content-Length") == "0":
                    continue
                raw = getattr(s, "raw", None)
                body = raw.read(8192) if raw is not None else s.content[:8192]
                if valid_video_bytes(body, s.headers.get("Content-Type", "")):
                    return True
            finally:
                s.close()
        return False
    except Exception:
        return False


def nearby_cameras(payload):
    """Candidatas cercanas, filtradas y verificadas en paralelo."""
    try:
        lat = float(payload.get("lat"))
        lon = float(payload.get("lon"))
    except Exception:
        return {"ok": False, "error": "Coordenadas inválidas"}
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return {"ok": False, "error": "Coordenadas fuera de rango"}
    try:
        radius = min(200, max(1, float(payload.get("radiusKm", 25))))
    except Exception:
        radius = 25.0
    try:
        limit = min(200, max(1, int(payload.get("limit", 100))))
    except Exception:
        limit = 100
    force = bool(payload.get("force"))

    key = (round(lat, 3), round(lon, 3), radius, limit)
    if (not force and NEAR_CACHE["key"] == key
            and time.time() - NEAR_CACHE["at"] < NEAR_TTL):
        return NEAR_CACHE["data"]

    candidates = []
    for c in cameras()[0]:
        if not is_operational(c) or not c.get("stream"):
            continue
        try:
            clat, clon = float(c["lat"]), float(c["lon"])
        except Exception:
            continue
        d = distance_km(lat, lon, clat, clon)
        if d <= radius:
            candidates.append((d, c))
    candidates.sort(key=lambda x: x[0])
    selected = candidates[:limit]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(probe_stream, c): c for _, c in selected}
        ok_ids = set()
        for future in as_completed(futures):
            c = futures[future]
            ok = future.result()
            if ok:
                ok_ids.add(id(c))
            ai.record_signal(c, ok, "verificación nearby")

    ai.save_signals()

    found = []
    for d, c in selected:
        if id(c) in ok_ids:
            item = dict(c)
            item["distKm"] = round(d, 3)
            item["verifiedAt"] = time.strftime("%H:%M:%S")
            found.append(item)

    data = {
        "ok": True,
        "cameras": found,
        "checked": len(selected),
        "candidates": len(candidates),
        "radiusKm": radius,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Playlist HLS y segmento verificados; se excluyen cámaras dadas de baja.",
    }
    NEAR_CACHE.update(key=key, at=time.time(), data=data)
    return data


# ---------------------------------------------------------------------------
# Refresco en segundo plano
# ---------------------------------------------------------------------------
def job_update(jid, **kw):
    with JOBS_LOCK:
        JOBS.setdefault(jid, {}).update(kw)


def refresh_de(jid):
    try:
        job_update(jid, status="running", log=["Consultando feed de DelDOT…"])
        r = requests.get(DE_FEED, timeout=40, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        feed = r.json()
        items = normalize_de(feed)
        if not items:
            raise RuntimeError("El feed no devolvió cámaras")
        (DATA / "de_cameras.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        info = load_json(DATA / "source_info.json", {}) or {}
        for s in info.get("sources", []):
            if s.get("name", "").startswith("DelDOT"):
                s["cameras"] = len(items)
                s["feedTimestamp"] = feed.get("timestamp")
                s["streams"] = sum(1 for c in items if c.get("stream"))
        info["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        (DATA / "source_info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        cameras(force=True)
        job_update(jid, status="done", log=["DelDOT actualizado: %d cámaras" % len(items)])
    except Exception as e:
        job_update(jid, status="error", log=["DelDOT: " + str(e)[:300]])
    return jid


def refresh_nj(jid):
    try:
        job_update(jid, status="running", log=["Abriendo navegador fuera de pantalla…"])
        py = sys.executable or "python"
        p = subprocess.Popen(
            [py, str(ROOT / "scripts" / "refresh.py")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            cwd=str(ROOT),
        )
        lines = []
        assert p.stdout is not None
        for line in p.stdout:
            line = line.strip()
            if line:
                lines.append(line)
                job_update(jid, log=lines[-25:])
        # El refresco completo consulta los ~680 detalles vía CDP: tarda minutos.
        p.wait(timeout=1800)
        if p.returncode != 0:
            raise RuntimeError(lines[-1] if lines else ("salida " + str(p.returncode)))
        cameras(force=True)
        job_update(jid, status="done", log=lines[-25:])
    except Exception as e:
        job_update(jid, status="error", log=["511NJ: " + str(e)[:300]])
    return jid


def start_refresh(kind):
    jid = "job-%d" % (time.time_ns())
    with JOBS_LOCK:
        JOBS[jid] = {"status": "queued", "kind": kind, "log": [], "at": time.strftime("%H:%M:%S")}

    def runner():
        if kind in ("de", "all"):
            refresh_de(jid)
        if kind in ("nj", "all"):
            refresh_nj(jid)
        with JOBS_LOCK:
            j = JOBS[jid]
            if j.get("status") == "queued":
                j["status"] = "done"
            j["finished"] = time.strftime("%H:%M:%S")

    threading.Thread(target=runner, daemon=True).start()
    return jid


# ---------------------------------------------------------------------------
# Proxy HLS
# ---------------------------------------------------------------------------
def gate(check):
    def deco(fn):
        def wrap(self, *a, **kw):
            try:
                return fn(self, *a, **kw)
            except OSError:
                # El navegador canceló la petición (HLS/radio al cambiar de
                # cámara o al cerrar la pestaña): no hay socket donde responder.
                return
            except Exception as e:
                try:
                    self.send_json(500, {"ok": False, "error": str(e)[:300]})
                except OSError:
                    pass
        return wrap
    return deco


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "HorizonView/1.0"

    def log_message(self, fmt, *args):
        pass

    def send_bytes(self, body, content="application/octet-stream", status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, obj):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", status)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        body = {}
        if p.path.startswith("/api/") and p.path != "/api/hls":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}

        if p.path == "/api/ai/corridor":
            try:
                lat, lon = body.get("lat"), body.get("lon")
                lat = float(lat) if lat is not None else None
                lon = float(lon) if lon is not None else None
                result = extras.corridor_status(zone_id=body.get("zone"),
                                                lat=lat, lon=lon)
                self.send_json(200, {"ok": True, **result})
            except Exception as exc:
                self.send_json(400, {"ok": False, "error": str(exc)[:200]})
            return
        if p.path in ("/api/ai/route", "/api/ai/query", "/api/ai/brief", "/api/ai/context",
                      "/api/ai/alerts", "/api/ai/groups", "/api/ai/tour", "/api/ai/compare",
                      "/api/ai/layers"):
            cams, meta = cameras()
            tours_data = load_tours()
            if p.path == "/api/ai/route":
                result = ai.plan_route(body, cams, meta)
            elif p.path == "/api/ai/query":
                result = ai.parse_query(body, cams, meta)
            elif p.path == "/api/ai/brief":
                result = ai.build_brief(body, cams, meta)
            elif p.path == "/api/ai/context":
                result = ai.context_for_camera(body, cams, meta)
            elif p.path == "/api/ai/alerts":
                result = ai.zone_alerts(body, cams, meta)
            elif p.path == "/api/ai/groups":
                result = ai.smart_groups(body, cams, meta)
            elif p.path == "/api/ai/tour":
                result = ai.tour_narrative(body, cams, meta, tours_data)
            elif p.path == "/api/ai/compare":
                result = ai.compare_cameras(body, cams, meta)
            else:
                result = ai.weather_layers(body, cams, meta)
            self.send_json(200 if result.get("ok") else 400, result)
            return
        if p.path == "/api/refresh":
            kind = body.get("kind", "de")
            if kind not in ("de", "nj", "all"):
                kind = "de"
            self.send_json(200, {"ok": True, "job": start_refresh(kind)})
            return
        if p.path == "/api/trip/services":
            # Servicios públicos en ruta (repostaje, carga, áreas de servicio y
            # peajes) desde OpenStreetMap/Overpass, para la experiencia de viaje.
            try:
                geometry = body.get("geometry")
                if not isinstance(geometry, list):
                    self.send_json(400, {"ok": False, "error": "Se espera una geometría de ruta."})
                    return
                self.send_json(200, extras.route_services(geometry))
            except Exception as exc:
                self.send_json(400, {"ok": False, "error": str(exc)[:200]})
            return
        if p.path == "/api/roadfacts":
            # Cámaras de velocidad y límites de OpenStreetMap cerca de la ruta.
            try:
                geometry = body.get("geometry")
                if not isinstance(geometry, list):
                    self.send_json(400, {"ok": False, "error": "Se espera una geometría de ruta."})
                    return
                self.send_json(200, extras.route_roadfacts(geometry))
            except Exception as exc:
                self.send_json(200, {"ok": False, "error": str(exc)[:200], "items": [],
                                     "note": "Overpass no respondió; la ruta sigue disponible sin límites OSM."})
            return
        if p.path == "/api/streams/check":
            # Verifica en paralelo qué cámaras responden con video real antes de
            # abrirlas (comparador): evita streams con token otp caducado.
            ids = body.get("ids") if isinstance(body.get("ids"), list) else []
            ids = [str(i) for i in ids[:24]]
            cams, _ = cameras()
            by_id = {str(c.get("id")): c for c in cams}
            cand = [by_id[i] for i in ids if i in by_id
                    and is_operational(by_id[i]) and by_id[i].get("stream")]
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda c: (str(c.get("id")), probe_stream(c)), cand))
            self.send_json(200, {
                "ok": True,
                "checked": len(cand),
                "working": [cid for cid, good in results if good],
                "failed": [cid for cid, good in results if not good],
            })
            return
        if p.path == "/api/nearby":
            self.send_json(200, nearby_cameras(body))
            return
        if p.path == "/api/stream-report":
            cid = body.get("id") or body.get("camId")
            if not cid:
                self.send_json(400, {"ok": False, "error": "Falta id de cámara"})
                return
            entry = report_failure(cid, body.get("reason") or "playback")
            NEAR_CACHE["key"] = None  # invalida búsquedas previas
            self.send_json(200, {"ok": True, "hidden": True, "entry": entry})
            return
        self.send_json(404, {"ok": False, "error": "No encontrado"})

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = p.path
        try:
            if path in ("/", "/index.html"):
                self.serve_file(ROOT / "index.html", "text/html; charset=utf-8")
            elif path.startswith("/assets/"):
                name = path[len("/assets/"):]
                if "/" in name or "\\" in name or ".." in name:
                    self.send_json(400, {"ok": False, "error": "Ruta inválida"})
                    return
                f = ASSETS / name
                if not f.exists():
                    self.send_json(404, {"ok": False, "error": "No encontrado"})
                    return
                ct = {"css": "text/css; charset=utf-8", "js": "application/javascript; charset=utf-8",
                      "svg": "image/svg+xml", "png": "image/png", "ico": "image/x-icon"}.get(
                          f.suffix.lstrip(".").lower(), "application/octet-stream")
                self.serve_file(f, ct)
            elif path == "/styles.css":
                self.serve_file(ROOT / "styles.css", "text/css; charset=utf-8")
            elif path == "/src/app.js":
                self.serve_file(ROOT / "src" / "app.js", "application/javascript; charset=utf-8")
            elif path == "/api/health":
                cams, meta = cameras()
                self.send_json(200, {
                    "ok": True, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "cameras": len(cams),
                    "nj": sum(1 for c in cams if c["source"] == "511NJ"),
                    "de": sum(1 for c in cams if c["source"] == "DelDOT"),
                    "streams": sum(1 for c in cams if c.get("stream")),
                    "sources": meta.get("sources", []),
                })
            elif path == "/api/cameras":
                cams, meta = cameras()
                visible = []
                for c in cams:
                    if not is_operational(c):
                        continue
                    item = dict(c)
                    item.update(ai.score_camera(c))
                    visible.append(item)
                visible = extras.annotate_cameras(visible)
                meta_out = dict(meta)
                meta_out["localZones"] = extras.local_zones_data()
                meta_out["zoneSummary"] = extras.zones_summary(visible)
                self.send_json(200, {
                    "ok": True, "cameras": visible,
                    "excluded": len(cams) - len(visible), "meta": meta_out,
                })
            elif path == "/api/source":
                _, meta = cameras()
                self.send_json(200, {"ok": True, **meta})
            elif path == "/api/tours":
                tours = load_tours()
                self.send_json(200, {
                    "ok": True, "at": tours.get("at"),
                    "tours": tours.get("tours") or [],
                })
            elif path == "/api/zones":
                cams, _ = cameras()
                visible = [c for c in cams if is_operational(c)]
                self.send_json(200, {
                    "ok": True, "meta": extras.local_zones_data()["meta"],
                    "zones": extras.zones_summary(extras.annotate_cameras(visible)),
                })
            elif path == "/api/weather/live":
                qs = urllib.parse.parse_qs(p.query)
                try:
                    lat = float(qs.get("lat", [str(DEFAULT_LAT)])[0])
                    lon = float(qs.get("lon", [str(DEFAULT_LON)])[0])
                except ValueError:
                    lat, lon = DEFAULT_LAT, DEFAULT_LON
                self.send_json(200, {"ok": True, **extras.weather_live(lat, lon)})
            elif path == "/api/sensors":
                qs = urllib.parse.parse_qs(p.query)
                try:
                    lat = float(qs.get("lat", [str(DEFAULT_LAT)])[0])
                    lon = float(qs.get("lon", [str(DEFAULT_LON)])[0])
                except ValueError:
                    lat, lon = DEFAULT_LAT, DEFAULT_LON
                self.send_json(200, {"ok": True, **extras.sensors_near(lat, lon)})
            elif path == "/api/radar":
                # Radar meteorológico real (RainViewer), sin clave y con atribución.
                try:
                    self.send_json(200, extras.rain_radar())
                except Exception as exc:
                    self.send_json(200, {"ok": False, "error": str(exc)[:200],
                                         "note": "El radar no está disponible ahora; el mapa sigue funcionando."})
            elif path == "/api/satellite":
                # Observación satelital real (NASA GIBS / GOES-East), sin clave.
                try:
                    self.send_json(200, extras.satellite_goes())
                except Exception as exc:
                    self.send_json(200, {"ok": False, "error": str(exc)[:200],
                                         "note": "El satélite no está disponible ahora; el mapa sigue funcionando."})
            elif path == "/api/coastal":
                # Contexto costero oficial (NOAA CO-OPS + NHC) solo cerca del agua.
                qs = urllib.parse.parse_qs(p.query)
                try:
                    lat = float(qs.get("lat", [str(DEFAULT_LAT)])[0])
                    lon = float(qs.get("lon", [str(DEFAULT_LON)])[0])
                except ValueError:
                    lat, lon = DEFAULT_LAT, DEFAULT_LON
                try:
                    self.send_json(200, extras.coastal_context(lat, lon))
                except Exception as exc:
                    self.send_json(200, {"ok": False, "error": str(exc)[:200],
                                         "note": "El contexto costero no está disponible ahora."})
            elif path == "/api/radio/stations":
                self.send_json(200, {"ok": True, **extras.radio_catalog(
                    refresh=urllib.parse.parse_qs(p.query).get("refresh", ["0"])[0] == "1")})
            elif path == "/api/radio/metadata":
                sid = urllib.parse.parse_qs(p.query).get("id", [""])[0]
                refresh = urllib.parse.parse_qs(p.query).get("refresh", ["0"])[0] == "1"
                station = next((s for s in extras.radio_catalog(refresh=refresh)["stations"]
                                if s["id"] == sid), None)
                if not station:
                    self.send_json(404, {"ok": False, "error": "Emisora no encontrada"})
                    return
                self.send_json(200, {
                    "ok": True, "id": sid, "status": station.get("status"),
                    "available": station.get("available"),
                    "nowPlaying": station.get("nowPlaying"),
                    "checkedAt": station.get("checkedAt"),
                    "source": station.get("source"),
                })
            elif path.startswith("/api/radio/stream/"):
                self.proxy_radio(path[len("/api/radio/stream/"):])
            elif path == "/api/geocode":
                qs = urllib.parse.parse_qs(p.query)
                q = qs.get("q", [""])[0]
                try:
                    limit = max(1, min(8, int(qs.get("limit", ["1"])[0])))
                except Exception:
                    limit = 1
                places = ai.geocode_many(q, limit)
                self.send_json(200, {"ok": bool(places), "place": places[0] if places else None,
                                     "places": places})
            elif path == "/api/reverse":
                qs = urllib.parse.parse_qs(p.query)
                try:
                    lat = float(qs.get("lat", [""])[0])
                    lon = float(qs.get("lon", [""])[0])
                except Exception:
                    lat = lon = 0
                place = ai.reverse_place(lat, lon)
                self.send_json(200, {"ok": bool(place), "place": place})
            elif path == "/api/weather/alerts":
                items = ai.nws_alerts()
                self.send_json(200, {"ok": True, "at": ai.now(), "alerts": items,
                                     "source": ai.source("NWS", ai.NWS_ALERTS)})
            elif path == "/api/events":
                self.send_json(200, ai.events_summary())
            elif path == "/api/ai/stats":
                self.send_json(200, ai.stats())
            elif path == "/api/ai/layers":
                qs = urllib.parse.parse_qs(p.query)
                geo = None
                try:
                    geo = {"lat": float(qs.get("lat", [""])[0]),
                           "lon": float(qs.get("lon", [""])[0])}
                except Exception:
                    pass
                cams, meta = cameras()
                self.send_json(200, ai.weather_layers({"geo": geo,
                                "infra": qs.get("infra", ["0"])[0] == "1",
                                "radiusKm": qs.get("radiusKm", ["8"])[0]}, cams, meta))
            elif path == "/api/refresh/status":
                with JOBS_LOCK:
                    self.send_json(200, {"ok": True, "jobs": dict(JOBS)})
            elif path == "/api/mobile":
                try:
                    url = (ROOT / "URL_Movil.txt").read_text(encoding="utf-8-sig").strip()
                except Exception:
                    url = ""
                self.send_json(200, {
                    "ok": True, "url": url,
                    "qr": "/assets/qr-movil.png" if (ASSETS / "qr-movil.png").exists() else None,
                })
            elif path.startswith("/api/hls/"):
                self.proxy_hls(path[len("/api/hls/"):])
            else:
                self.send_json(404, {"ok": False, "error": "No encontrado"})
        except OSError:
            # El navegador canceló la petición (HLS/radio al cambiar de cámara):
            # no hay socket donde responder; es un cierre normal del cliente.
            return
        except Exception as e:
            try:
                self.send_json(500, {"ok": False, "error": str(e)[:300]})
            except OSError:
                pass

    def serve_file(self, f, content):
        self.send_bytes(f.read_bytes(), content)

    def proxy_hls(self, rest):
        # /api/hls/<cameraId>/<url-codificada>
        parts = rest.split("/", 1)
        if len(parts) != 2:
            self.send_json(400, {"ok": False, "error": "Ruta HLS inválida"})
            return
        cid, encoded = parts
        url = urllib.parse.unquote(encoded)
        host = urllib.parse.urlparse(url).hostname or ""
        if not host_allowed(host):
            self.send_json(400, {"ok": False, "error": "Host no permitido"})
            return
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0", "Referer": referer_for(host), "Accept": "*/*",
        }, stream=False)
        if r.status_code >= 400:
            self.send_bytes(b"", "text/plain", r.status_code)
            return
        ctype = r.headers.get("Content-Type", "application/octet-stream")
        low = r.content[:512].lower()
        if "html" in ctype.lower() or b"<html" in low or b"attention required" in low:
            self.send_bytes(b"", "text/plain", 502)
            return
        is_playlist = looks_like_playlist(r.text) or "mpegurl" in ctype.lower()
        if not is_playlist:
            self.send_bytes(r.content, ctype or "video/mp2t")
            return
        out = []
        for line in r.text.splitlines():
            s = line.strip()
            if not s:
                out.append(line)
                continue
            if s.startswith("#"):
                # Reescribir URI de clave y de segmento de inicialización (fMP4),
                # si no, HLS.js pediría el init.mp4 directamente al host remoto.
                for pattern in (r"(#EXT-X-KEY:.*URI=\")([^\"]+)(\".*)",
                                r"(#EXT-X-MAP:.*URI=\")([^\"]+)(\".*)",
                                r"(#EXT-X-PART:.*URI=\")([^\"]+)(\".*)",
                                r"(#EXT-X-PRELOAD-HINT:.*URI=\")([^\"]+)(\".*)"):
                    m = re.match(pattern, s)
                    if m:
                        u = hls_join(url, m.group(2))
                        s = m.group(1) + "/api/hls/%s/%s" % (
                            cid, urllib.parse.quote(u, safe="")) + m.group(3)
                        break
                out.append(s)
                continue
            u = hls_join(url, s)
            out.append("/api/hls/%s/%s" % (cid, urllib.parse.quote(u, safe="")))
        self.send_bytes(("\n".join(out) + "\n").encode("utf-8"),
                        "application/vnd.apple.mpegurl")

    def proxy_radio(self, rest):
        """Relé del audio en vivo (ICY/HLS) de emisoras verificadas.

        La app no redistribuye la señal: solo la retransmite tal cual del
        servidor oficial de cada emisora, en el mismo origen HTTPS para evitar
        contenido mixto y permitir que hls.js lea las playlists.
        """
        parts = rest.split("/", 1)
        sid = parts[0]
        station = next((s for s in extras.radio_catalog()["stations"]
                        if s["id"] == sid), None)
        if not station:
            self.send_json(404, {"ok": False, "error": "Emisora no encontrada"})
            return
        if len(parts) == 2:
            url = urllib.parse.unquote(parts[1])
            if not radio_host_allowed(urllib.parse.urlparse(url).hostname or ""):
                self.send_json(400, {"ok": False, "error": "Host no permitido"})
                return
        else:
            url = station["streamUrl"]
        try:
            r = requests.get(url, timeout=20, headers={
                "User-Agent": "Mozilla/5.0", "Accept": "*/*",
            }, stream=True, allow_redirects=True)
        except Exception as exc:
            self.send_json(502, {"ok": False, "error": str(exc)[:200]})
            return
        if r.status_code >= 400:
            self.send_bytes(b"", "text/plain", r.status_code)
            return
        ctype = r.headers.get("Content-Type", "application/octet-stream")
        try:
            sample = r.raw.read(2048, decode_content=True)
        except Exception:
            sample = b""
        low = sample[:1024].lower()
        if b"<html" in low or b"<!doctype" in low or b"attention required" in low:
            self.send_bytes(b"", "text/plain", 502)
            return
        is_playlist = looks_like_playlist(sample.decode("utf-8", "replace")) \
            or "mpegurl" in ctype.lower() or url.lower().endswith(".m3u8")
        if is_playlist:
            try:
                tail = r.raw.read(200000, decode_content=True)
                text = (sample + tail).decode("utf-8", "replace")
            except Exception:
                text = sample.decode("utf-8", "replace")
            out = []
            for line in text.splitlines():
                s = line.strip()
                if not s:
                    out.append(line)
                    continue
                if s.startswith("#"):
                    for pattern in (r"(#EXT-X-KEY:.*URI=\")([^\"]+)(\".*)",
                                    r"(#EXT-X-MAP:.*URI=\")([^\"]+)(\".*)",
                                    r"(#EXT-X-PART:.*URI=\")([^\"]+)(\".*)",
                                    r"(#EXT-X-PRELOAD-HINT:.*URI=\")([^\"]+)(\".*)"):
                        m = re.match(pattern, s)
                        if m:
                            u = hls_join(url, m.group(2))
                            s = m.group(1) + "/api/radio/stream/%s/%s" % (
                                sid, urllib.parse.quote(u, safe="")) + m.group(3)
                            break
                    out.append(s)
                    continue
                u = hls_join(url, s)
                out.append("/api/radio/stream/%s/%s" % (
                    sid, urllib.parse.quote(u, safe="")))
            self.send_bytes(("\n".join(out) + "\n").encode("utf-8"),
                            "application/vnd.apple.mpegurl")
            return
        # Audio ICY: flujo continuo sin Content-Length (HTTP/1.0 → fin al cerrar).
        self.send_response(200)
        self.send_header("Content-Type", (ctype.split(";")[0] or "audio/mpeg"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(sample)
            for chunk in r.raw.stream(8192, decode_content=True):
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                r.close()
            except Exception:
                pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    cameras(force=True)
    print("HorizonView en http://127.0.0.1:%d" % PORT, flush=True)
    print("Cámaras cargadas:", len(CACHE["cameras"] or []), flush=True)
    Server(("127.0.0.1", PORT), Handler).serve_forever()
