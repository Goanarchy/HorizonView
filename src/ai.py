"""Núcleo de IA explicable de HorizonView.

Regla de oro: nada de reconocimiento de rostros, placas ni vehículos; ningún
incidente, cámara o control inventado. Toda sugerencia indica fuente pública,
hora y confianza, y puede verificarse con un botón «ver datos».

Las funciones son deterministas: la misma entrada y los mismos datos públicos
producen siempre la misma explicación. No se usa ningún servicio de pago ni
clave API. Fuentes: inventarios oficiales 511NJ/DelDOT, NWS, Open-Meteo,
OSRM, Nominatim y OpenStreetMap (Overpass).
"""
import math
import re
import threading
import time
import unicodedata
import urllib.parse

import requests

UA = "HorizonView/3.0 (app publica de camaras; datos abiertos)"
ROOT_DATA = None  # lo fija src/server.py al importar
SIGNALS_FILE = None
SIGNALS = {}
SIGNALS_LOCK = threading.Lock()
SIGNALS_DIRTY = False
EVENTS = None
EVENTS_FILE = None

NET = {}
NET_LOCK = threading.Lock()
NET_TTL = {
    "nws_alerts": 600,
    "nws_point": 600,
    "meteo": 600,
    "nominatim": 86400,
    "nominatim_reverse": 86400,
    "osrm": 3600,
    "overpass": 900,
}
DEFAULT_TTL = 300

NWS_ALERTS = "https://api.weather.gov/alerts/active?area=NJ,DE"
NWS_POINT = "https://api.weather.gov/alerts/active?point={lat},{lon}"
METEO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
         "&current=temperature_2m,precipitation,rain,snowfall,wind_speed_10m,visibility"
         "&timezone=America/New_York")
OSRM = "https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson&steps=false"
NOMINATIM = "https://nominatim.openstreetmap.org/search?q={q}&format=json&limit={limit}&addressdetails=0"
NOMINATIM_REVERSE = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
                     "&lat={lat}&lon={lon}&zoom=16&addressdetails=1&accept-language=es")
OVERPASS = "https://overpass-api.de/api/interpreter?data={q}"

WEATHER_WORDS = {
    "lluvia": ["rain", "flood", "thunderstorm"], "rain": ["rain", "flood", "thunderstorm"],
    "nieve": ["snow", "winter"], "snow": ["snow", "winter"],
    "tormenta": ["thunderstorm", "storm", "tornado"],
    "niebla": ["fog", "dense fog"], "viento": ["wind", "high wind"],
    "inundacion": ["flood"], "inundación": ["flood"], "calor": ["heat"],
    "frio": ["cold", "winter"], "frío": ["cold", "winter"],
}


# ---------------------------------------------------------------------------
# Utilidades y fuentes
# ---------------------------------------------------------------------------
def norm(s):
    return unicodedata.normalize("NFD", str(s or "")).replace(
        "\u0301", "").replace("\u0308", "").replace("\u0303", "").replace(
        "\u0304", "").replace("\u0302", "").replace("\u0300", "").lower().strip()


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or ""))
                   if not unicodedata.combining(c)).lower()


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def source(label, url, at=None):
    return {"label": label, "url": url, "at": at or now()}


def fetch(key, url, ttl=None, headers=None):
    """GET con caché en memoria; devuelve None si la fuente falla o no responde."""
    ttl = NET_TTL.get(key, DEFAULT_TTL) if ttl is None else ttl
    with NET_LOCK:
        hit = NET.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    try:
        r = requests.get(url, timeout=(5, 18),
                         headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    with NET_LOCK:
        NET[key] = (time.time(), data)
    return data


def configure(data_path):
    global ROOT_DATA, SIGNALS_FILE, EVENTS_FILE, EVENTS
    ROOT_DATA = data_path
    SIGNALS_FILE = data_path / "ai_signals.json"
    EVENTS_FILE = data_path / "nj_events.json"
    try:
        loaded = __import__("json").loads(SIGNALS_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            SIGNALS.update(loaded)
    except Exception:
        pass
    try:
        EVENTS = __import__("json").loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        EVENTS = None


def official_events(state=None, limit=None):
    """Eventos reales publicados por 511NJ (/client/get/event), capturados con CDP."""
    items = (((EVENTS or {}).get("events")) or [])
    if state:
        wanted = set(str(x).upper() for x in str(state).split(","))
        items = [e for e in items if str(e.get("state") or "").upper() in wanted]
    items = [e for e in items if str(e.get("state") or "").upper() in ("NJ", "DE")]
    if limit:
        items = items[:limit]
    return items


def events_summary():
    items = official_events()
    cats = {}
    for e in items:
        cats[e.get("categoryName") or e.get("eventType") or "Otro"] = \
            cats.get(e.get("categoryName") or e.get("eventType") or "Otro", 0) + 1
    return {
        "ok": True, "at": (EVENTS or {}).get("at"), "count": len(items),
        "byCategory": cats,
        "note": "Feed oficial capturado de la app pública de 511NJ. Incluye obras, eventos y avisos; no es una predicción.",
        "source": source("511NJ · /client/get/event", "https://511nj.org/"),
    }


def event_level(e):
    text = plain("%s %s %s" % (e.get("eventType"), e.get("categoryName"), e.get("facility")))
    if any(w in text for w in ("closure", "cerrado", "crash", "accident", "incident")):
        return "alto"
    if any(w in text for w in ("construction", "roadwork", "obra", "maintenance")):
        return "medio"
    return "bajo"


def events_near(lat, lon, radius_km=15, cameras=None, limit=8):
    """Eventos con coordenada real; si no tienen, se remplaza por zona textual."""
    found = []
    for e in official_events():
        try:
            d = haversine(lat, lon, float(e["latitude"]), float(e["longitude"]))
        except Exception:
            d = None
        if d is not None and d <= radius_km:
            found.append((d, e))
    found.sort(key=lambda x: x[0])
    out = []
    for d, e in found[:limit]:
        out.append({
            "id": e.get("eventId"), "type": e.get("eventType"),
            "category": e.get("categoryName"), "facility": e.get("facility"),
            "county": e.get("county"), "state": e.get("state"),
            "distKm": round(d, 1), "lat": e.get("latitude"), "lon": e.get("longitude"),
            "start": e.get("startDateTime"), "end": e.get("endDateTime"),
            "updated": e.get("lastUpdateDate"), "level": event_level(e),
        })
    return out


def save_signals(force=False):
    global SIGNALS_DIRTY
    if not SIGNALS_FILE or not (SIGNALS_DIRTY or force):
        return
    with SIGNALS_LOCK:
        try:
            import json
            SIGNALS_FILE.write_text(json.dumps(SIGNALS, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
            SIGNALS_DIRTY = False
        except Exception:
            pass


def record_signal(cam, ok, reason, save=False):
    """Historial anónimo de aciertos/fallos de reproducción por cámara."""
    cid = str((cam or {}).get("id") or "")
    if not cid:
        return
    with SIGNALS_LOCK:
        global SIGNALS_DIRTY
        e = dict(SIGNALS.get(cid) or {})
        e["ok" if ok else "fail"] = int(e.get("ok" if ok else "fail") or 0) + 1
        e["lastOk" if ok else "lastFail"] = now()
        e["reason"] = str(reason or "")[:90]
        SIGNALS[cid] = e
        SIGNALS_DIRTY = True
    if save:
        save_signals()


def signals_for(cid):
    with SIGNALS_LOCK:
        return dict(SIGNALS.get(str(cid)) or {})


def stats():
    with SIGNALS_LOCK:
        items = list(SIGNALS.values())
    ok = sum(int(x.get("ok") or 0) for x in items)
    fail = sum(int(x.get("fail") or 0) for x in items)
    return {
        "ok": True, "at": now(), "camerasWithHistory": len(items),
        "successes": ok, "failures": fail,
        "rate": round(100.0 * ok / (ok + fail), 1) if ok + fail else None,
        "note": "Historial local anónimo de verificaciones reales; sin datos personales.",
    }


# ---------------------------------------------------------------------------
# Idea 2 · radar de confianza
# ---------------------------------------------------------------------------
def score_camera(c, verified_ids=None):
    """Puntaje 0-100 explicable. Nunca afirma tráfico, solo calidad del dato."""
    reasons = []
    score = 0
    stream = bool(c.get("stream"))

    def add(points, text, src):
        nonlocal score
        score += points
        reasons.append({"points": points, "text": text, "source": src})

    if c.get("source") in ("511NJ", "DelDOT"):
        add(26, "Fuente oficial: " + c["source"], "inventario oficial")
    if c.get("enabled") is not False:
        add(14, "Cámara activa en el inventario", "inventario oficial")
    else:
        add(-40, "Marcada como no operativa", "inventario oficial")
    if stream:
        add(18, "Expone stream HLS público", "inventario oficial")
    else:
        add(-22, "No publica stream HLS", "inventario oficial")

    sig = signals_for(c.get("id"))
    ok_n, fail_n = int(sig.get("ok") or 0), int(sig.get("fail") or 0)
    if ok_n:
        add(min(16, 4 + 3 * ok_n), "%d verificación(es) de video correctas en este dispositivo" % ok_n,
            "historial local")
    if fail_n:
        add(-min(30, 6 * fail_n), "%d fallo(s) de reproducción registrados" % fail_n,
            "historial local")
    if verified_ids is not None and c.get("id") in verified_ids:
        add(12, "Video y segmento verificados en esta sesión", "GET /api/nearby")
    if c.get("verifiedAt"):
        add(6, "Verificada a las " + str(c["verifiedAt"]), "GET /api/nearby")
    fetched_at = str(c.get("streamFetchedAt") or "")
    if fetched_at:
        add(4, "Stream obtenido de la fuente: " + fetched_at, "inventario oficial")
    if (c.get("tours") or []) and c.get("source") == "511NJ":
        add(4, "Aparece en %d tour(es) oficiales" % len(c["tours"]), "511NJ tours")
    if any(x in plain(c.get("name") or "") for x in ("unavailable", "offline", "not available")):
        add(-20, "El propio nombre advierte que no está disponible", "inventario oficial")

    trust = max(0, min(100, score))
    if trust >= 85:
        label = "Muy alta"
    elif trust >= 70:
        label = "Alta"
    elif trust >= 50:
        label = "Media"
    elif trust >= 30:
        label = "Baja"
    else:
        label = "Sin verificar"
    confidence = "alta" if (ok_n + fail_n) >= 3 or stream else ("media" if stream else "baja")
    return {
        "trust": trust, "trustLabel": label, "trustConfidence": confidence,
        "trustReasons": reasons,
        "trustNote": "Mide la calidad del dato, no el tráfico ni la imagen.",
    }


# ---------------------------------------------------------------------------
# Geocodificación / clima / eventos
# ---------------------------------------------------------------------------
def geocode(text, limit=1):
    q = str(text or "").strip()
    if not q:
        return None
    if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*", q):
        a, b = [float(x) for x in q.split(",")]
        if -90 <= a <= 90 and -180 <= b <= 180:
            return {"name": q, "lat": a, "lon": b, "source": source("Coordenadas introducidas", "")}
    data = fetch("geo:" + plain(q)[:60],
                 NOMINATIM.format(q=urllib.parse.quote(q), limit=max(1, min(5, int(limit)))))
    try:
        item = (data or [])[0]
        return {
            "name": item.get("display_name", q),
            "lat": float(item["lat"]), "lon": float(item["lon"]),
            "source": source("Nominatim / OpenStreetMap", item.get("osm_type") and
                             "https://www.openstreetmap.org/%s/%s" % (item["osm_type"], item.get("osm_id")) or
                             "https://nominatim.openstreetmap.org/"),
        }
    except Exception:
        return None


def geocode_many(text, limit=5):
    """Varias sugerencias de lugar para el selector de destino del viaje."""
    q = str(text or "").strip()
    if not q:
        return []
    if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*", q):
        one = geocode(q)
        return [one] if one else []
    data = fetch("geo:" + plain(q)[:60],
                 NOMINATIM.format(q=urllib.parse.quote(q), limit=max(1, min(8, int(limit)))))
    out = []
    try:
        for item in (data or [])[:max(1, min(8, int(limit)))]:
            out.append({
                "name": item.get("display_name", q),
                "lat": float(item["lat"]), "lon": float(item["lon"]),
                "source": source("Nominatim / OpenStreetMap", item.get("osm_type") and
                                 "https://www.openstreetmap.org/%s/%s" % (item["osm_type"], item.get("osm_id")) or
                                 "https://nominatim.openstreetmap.org/"),
            })
    except Exception:
        pass
    return out


def reverse_place(lat, lon):
    """Vía/paraje real del punto actual (Nominatim reverse), con fuente y caché.

    Se redondea a ~100 m para no saturar Nominatim con posiciones casi
    idénticas del mismo viaje y se guarda 24 h: mismo punto, misma respuesta.
    """
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    key = "rev:%.3f,%.3f" % (la, lo)
    data = fetch(key, NOMINATIM_REVERSE.format(lat=la, lon=lo), ttl=86400)
    if not data or not isinstance(data, dict):
        return None
    addr = data.get("address") or {}
    road = (addr.get("road") or addr.get("pedestrian") or addr.get("footway")
            or data.get("name") or "")
    city = (addr.get("city") or addr.get("town") or addr.get("village")
            or addr.get("county") or "")
    state = addr.get("state") or ""
    label = ", ".join(str(x) for x in (road, city, state) if x) or data.get("display_name", "")
    osm_type = data.get("osm_type")
    url = ("https://www.openstreetmap.org/%s/%s" % (osm_type, data.get("osm_id"))
           if osm_type else "https://www.openstreetmap.org/")
    return {
        "label": label, "road": road, "city": city, "state": state,
        "at": now(), "source": source("Nominatim / OpenStreetMap (reverse)", url),
    }


def alert_summary(feature):
    p = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    lat = lon = None
    try:
        coords = geom.get("coordinates") or []
        pts = coords[0] if geom.get("type") == "Polygon" and coords and isinstance(coords[0][0], list) else coords
        if pts and isinstance(pts[0], list):
            lat = sum(float(x[1]) for x in pts) / len(pts)
            lon = sum(float(x[0]) for x in pts) / len(pts)
    except Exception:
        pass
    return {
        "id": p.get("id"), "event": p.get("event"), "severity": p.get("severity"),
        "urgency": p.get("urgency"), "headline": p.get("headline"),
        "area": p.get("areaDesc"), "onset": p.get("onset"), "expires": p.get("expires"),
        "description": str(p.get("description") or "")[:300],
        "instruction": str(p.get("instruction") or "")[:200],
        "lat": lat, "lon": lon,
        "url": p.get("@id") or p.get("web") or "https://api.weather.gov/alerts/active",
    }


def nws_alerts():
    data = fetch("nws_alerts", NWS_ALERTS)
    feats = (data or {}).get("features") or []
    return [alert_summary(f) for f in feats]


def nws_point_alerts(lat, lon):
    key = "nws_pt:%.2f,%.2f" % (lat, lon)
    data = fetch(key, NWS_POINT.format(lat=round(lat, 3), lon=round(lon, 3)))
    feats = (data or {}).get("features") or []
    return [alert_summary(f) for f in feats]


def weather_at(lat, lon):
    key = "meteo:%.2f,%.2f" % (lat, lon)
    data = fetch(key, METEO.format(lat=round(lat, 3), lon=round(lon, 3)))
    try:
        c = data["current"]
        return {
            "time": c.get("time"),
            "temperatureC": c.get("temperature_2m"),
            "precipitationMm": c.get("precipitation"),
            "rainMm": c.get("rain"), "snowCm": c.get("snowfall"),
            "windKmh": c.get("wind_speed_10m"), "visibilityM": c.get("visibility"),
            "source": source("Open-Meteo / NOAA", "https://open-meteo.com/", c.get("time")),
        }
    except Exception:
        return None


def osm_infrastructure(lat, lon, radius_km=8):
    """Obras viales publicadas en OpenStreetMap (solo si el usuario pide capas)."""
    d = max(1, min(25, float(radius_km)))
    lat_delta = d / 111.0
    lon_delta = d / (111.0 * max(0.2, math.cos(math.radians(lat))))
    bbox = "%.4f,%.4f,%.4f,%.4f" % (lat - lat_delta, lon - lon_delta,
                                     lat + lat_delta, lon + lon_delta)
    query = "[out:json][timeout:12];(way[highway=construction](%s);way[highway][construction](%s););out center 12;" % (bbox, bbox)
    key = "overpass:%.2f,%.2f,%.0f" % (lat, lon, d)
    data = fetch(key, OVERPASS.format(q=urllib.parse.quote(query)))
    out = []
    for e in (data or {}).get("elements") or []:
        tags = e.get("tags") or {}
        c = e.get("center") or {}
        lat_e, lon_e = c.get("lat"), c.get("lon")
        if lat_e is None or lon_e is None:
            continue
        out.append({
            "lat": lat_e, "lon": lon_e,
            "label": tags.get("name") or tags.get("ref") or "Obra vial señalizada en OSM",
            "detail": tags.get("construction") or tags.get("highway") or "",
            "url": "https://www.openstreetmap.org/way/%s" % e.get("id"),
        })
    return out[:20]


def operations(cameras):
    """Acepta lista de cámaras o contribuciones {"ok":..,"fail":..} para pruebas."""
    return cameras


def camera_subset(cameras, ids):
    wanted = set(str(x) for x in (ids or []))
    return [c for c in cameras if str(c.get("id")) in wanted]


def nearest(cameras, lat, lon, limit=6, max_km=None, only_stream=False):
    arr = []
    for c in cameras:
        if only_stream and not c.get("stream"):
            continue
        if not all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon")):
            continue
        d = haversine(lat, lon, c["lat"], c["lon"])
        if max_km is not None and d > max_km:
            continue
        arr.append((d, c))
    arr.sort(key=lambda x: x[0])
    return arr[:limit]


def route_progress(points, lat, lon):
    """Distancia al polilínea y posición aproximada en km; devuelve (offKm, atKm)."""
    best = (float("inf"), 0.0)
    acc = 0.0
    for i in range(len(points) - 1):
        la1, lo1 = points[i][1], points[i][0]
        la2, lo2 = points[i + 1][1], points[i + 1][0]
        seg = haversine(la1, lo1, la2, lo2)
        dlat, dlon = la2 - la1, lo2 - lo1
        denom = dlat * dlat + dlon * dlon
        t = 0.0 if denom == 0 else max(0.0, min(1.0, ((lat - la1) * dlat + (lon - lo1) * dlon) / denom))
        d = haversine(la1, lo1, lat, lon)
        if d < best[0]:
            # La distancia perpendicular real se aproxima con la distancia al punto
            # más cercano del segmento (los segmentos de OSRM son cortos).
            pla, plo = la1 + t * dlat, lo1 + t * dlon
            best = (haversine(lat, lon, pla, plo), acc + seg * t)
        acc += seg
    return best


# ---------------------------------------------------------------------------
# Idea 1 · copiloto de ruta
# ---------------------------------------------------------------------------
def plan_route(payload, cameras, meta=None):
    geo = payload.get("from") or payload.get("origin")
    dest = payload.get("to") or payload.get("destination")
    if payload.get("useGeo") and isinstance(payload.get("geo"), dict):
        g = payload["geo"]
        geo = "%.6f,%.6f" % (g.get("lat", 0), g.get("lon", 0))
    start = geocode(geo) if geo else None
    end = geocode(dest) if dest else None
    if not start or not end:
        return {"ok": False, "error": "No se pudieron resolver el origen y el destino. Prueba «Newark, NJ» o «39.68,-75.47»."}
    coords = "%.6f,%.6f;%.6f,%.6f" % (start["lon"], start["lat"], end["lon"], end["lat"])
    data = fetch("osrm:" + coords, OSRM.format(coords=coords))
    try:
        route = data["routes"][0]
        points = route["geometry"]["coordinates"]
    except Exception:
        return {"ok": False, "error": "El servicio de rutas (OSRM) no devolvió un trayecto para esos puntos."}
    # Reducir la polilínea para no cuadrar el coste con cientos de cámaras.
    step = max(1, len(points) // 350)
    pts = points[::step] + ([points[-1]] if points[-1] != points[::step][-1] else [])
    buffer_km = max(0.2, min(25.0, float(payload.get("bufferKm", 2.5))))
    found = []
    for c in cameras:
        if not c.get("stream") or not all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon")):
            continue
        off, at = route_progress(pts, c["lat"], c["lon"])
        if off <= buffer_km:
            item = dict(c)
            item["offRouteKm"] = round(off, 2)
            item["atKm"] = round(at, 1)
            item["atMin"] = round(route["duration"] * (at / max(1.0, route["distance"])) / 60.0, 1)
            item.update(score_camera(c))
            found.append(item)
    found.sort(key=lambda x: (x["atKm"], x["offRouteKm"]))
    limit = max(1, min(40, int(payload.get("limit", 12))))
    found = found[:limit]
    dist_km = route["distance"] / 1000.0
    dur_min = route["duration"] / 60.0
    return {
        "ok": True, "at": now(),
        "start": {"name": start["name"], "lat": start["lat"], "lon": start["lon"]},
        "end": {"name": end["name"], "lat": end["lat"], "lon": end["lon"]},
        "distanceKm": round(dist_km, 1), "durationMin": round(dur_min),
        "geometry": [[p[1], p[0]] for p in pts],
        "cameras": found, "bufferKm": buffer_km,
        "summary": "%d cámaras públicas con video a menos de %.1f km de la ruta (%.0f km, ~%d min)."
                   % (len(found), buffer_km, dist_km, round(dur_min)),
        "explanation": [
            "Ruta calculada por OSRM sobre la red viaria pública; el tiempo es una estimación sin tráfico en vivo.",
            "Se comparó la coordenada real de cada cámara oficial con la polilínea de la ruta.",
            "La confianza mide la calidad del dato, no lo que se ve en la imagen.",
        ],
        "confidence": "alta" if found else "media",
        "sources": [
            source("OSRM / OpenStreetMap", "https://router.project-osrm.org/"),
            start["source"], end["source"],
            source("Inventario oficial 511NJ + DelDOT", "https://511nj.org/camera"),
        ],
    }


# ---------------------------------------------------------------------------
# Idea 5 · búsqueda en lenguaje natural
# ---------------------------------------------------------------------------
def parse_query(payload, cameras, meta=None):
    text = str(payload.get("q") or payload.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "Escribe una pregunta o una descripción."}
    p, n = plain(text), norm(text)
    explanation = []
    sources = []
    ids = None
    favs = set(str(x) for x in (payload.get("favs") or []))
    stream_only = False
    sort = None

    if any(w in p for w in ("favorito", "favoritos", "mis camaras", "guardadas")):
        ids = set(favs)
        explanation.append("Interpretado «favoritos» como tus cámaras guardadas en este dispositivo.")

    if any(w in p for w in ("con video", "en vivo", "funcionan", "funcionando", "stream")):
        stream_only = True
        explanation.append("Solo cámaras que publican un stream HLS en la fuente oficial.")
    if any(w in p for w in ("sin video", "sin stream")):
        explanation.append("Se excluyeron cámaras con stream; no se inventaron fuentes alternativas.")
        ids = set() if ids is None else ids & set()

    tours = ((meta or {}).get("tours") or [])
    tour_detected = False
    for t in tours:
        if len(t.get("name") or "") > 6 and plain(t["name"]) in p:
            tour_detected = True
            matched = set(c["id"] for c in cameras if t["name"] in (c.get("tours") or []))
            ids = matched if ids is None else ids & matched
            explanation.append("Tour oficial 511NJ detectado: " + t["name"])
            sources.append(source("511NJ tours", "https://511nj.org/camera", (meta or {}).get("toursAt")))
            break

    # Zona / ruta: se contrasta contra las zonas reales del inventario.
    zones = sorted(set(c.get("zone") or "" for c in cameras), key=len, reverse=True)
    if not tour_detected:
        for z in zones:
            key = plain(z.replace("NJ · ", "").replace("DE · ", "").strip())
            if len(key) > 4 and key in p:
                matched = set(c["id"] for c in cameras if c.get("zone") == z)
                ids = matched if ids is None else ids & matched
                explanation.append("Zona detectada: " + z)
                break

    # «cerca de X» / «en X»: geocodificación real, nunca inventada.
    m = re.search(r"(?:cerca de|cerca del|cerca de la|en las cercanias de|near)\s+([a-zA-Z0-9 .,\-]{3,60})", p)
    center = None
    radius = 10.0
    mr = re.search(r"(?:a|en)\s+(\d{1,3})\s*(?:km|kilometros)", p)
    if mr:
        radius = max(1, min(200, float(mr.group(1))))
    if m:
        place = m.group(1).strip(" .,de la|del")
        center = geocode(place)
        if center:
            near_ids = set(c["id"] for d, c in nearest(cameras, center["lat"], center["lon"],
                                                        limit=len(cameras), max_km=radius))
            ids = near_ids if ids is None else ids & near_ids
            explanation.append("«Cerca de %s» = %d km alrededor de %s (geocodificado con OSM)."
                               % (place, radius, center["name"][:60]))
            sources.append(center["source"])

    if any(w in p for w in ("lluvia", "rain", "nieve", "snow", "tormenta", "niebla",
                            "viento", "inundacion", "inundación", "calor", "frio", "frío")):
        alerts = nws_alerts()
        keys = [k for k, v in WEATHER_WORDS.items() if k in p]
        wanted = set(x for k in keys for x in WEATHER_WORDS[k])
        hits = [a for a in alerts if any(w in plain(str(a.get("event") or "")) for w in wanted)]
        if hits:
            explanation.append("%d alerta(s) meteorológicas activas de NWS coinciden con el término."
                               % len(hits))
            sources.append(source("NWS alertas activas", NWS_ALERTS))
            if any(w in p for w in ("donde", "zona", "area", "área", "afectad")):
                weather_ids = set()
                for a in hits:
                    for c in cameras:
                        if a.get("lat") is None:
                            if plain(a.get("area") or "").find(plain(c.get("zone") or "").replace("nj · ", "")) >= 0:
                                weather_ids.add(c["id"])
                        elif haversine(a["lat"], a["lon"], c["lat"], c["lon"]) <= 60:
                            weather_ids.add(c["id"])
                ids = weather_ids if ids is None else ids & weather_ids
        else:
            explanation.append("No hay alertas NWS activas que coincidan con ese término ahora mismo.")
            sources.append(source("NWS alertas activas", NWS_ALERTS))

    if any(w in p for w in ("confiable", "confiable", "mejores", "mejor", "fiable")):
        sort = "trust"
        explanation.append("Ordenado por puntaje de confianza del dato (explicable).")

    # Texto libre residual: se usa como filtro literal sobre nombre/zona.
    literal = re.sub(r"(cerca de|cerca del|cerca de la|en las cercanias de|near)\s+[a-zA-Z0-9 .,\-]{3,60}",
                     " ", p)
    literal = re.sub(r"\b(con video|en vivo|funcionan|funcionando|stream|sin video|sin stream|favoritos?|mis camaras|guardadas|confiable|confiable|mejores?|fiable|camaras|camaras|del|near)\b",
                     " ", literal)
    literal = re.sub(r"\b(a|en)\s+\d{1,3}\s*(km|kilometros)\b", " ", literal)
    literal = re.sub(r"[^a-z0-9 ]+", " ", literal).strip()
    stop = {"de", "la", "el", "los", "las", "y", "o", "por", "con", "mas", "cerca", "hay", "que", "una", "un", "al", "del", "nj", "de"}
    tokens = [w for w in literal.split() if len(w) > 2 and w not in stop]
    needle = " ".join(tokens)
    if tokens and not tour_detected:
        needle_ids = set(c["id"] for c in cameras if all(
            t in plain("%s %s %s" % (c.get("name"), c.get("zone"), c.get("id"))) for t in tokens))
        if ids is None:
            ids = needle_ids
            explanation.append("Buscado «%s» en nombres y zonas del inventario oficial." % needle)
        else:
            ids = ids & needle_ids
            explanation.append("Combinado con «%s» sobre nombres y zonas." % needle)

    result = [c for c in cameras if ids is None or c["id"] in ids]
    if stream_only:
        result = [c for c in result if c.get("stream")]
    if sort == "trust":
        result.sort(key=lambda c: score_camera(c)["trust"], reverse=True)
    subset = result[:30]
    cards = []
    for c in subset:
        t = score_camera(c)
        cards.append({
            "id": c["id"], "name": c["name"], "zone": c.get("zone"),
            "source": c.get("source"), "lat": c.get("lat"), "lon": c.get("lon"),
            "trust": t["trust"], "trustLabel": t["trustLabel"],
            "stream": bool(c.get("stream")),
        })
    if not explanation:
        explanation.append("No encontré un filtro explícito; muestro el inventario completo.")
    return {
        "ok": True, "at": now(), "question": text,
        "interpretation": explanation, "ids": [c["id"] for c in result],
        "count": len(result), "cameras": cards,
        "confidence": "alta" if (center or any(t for t in tours if len(t.get("name") or "") > 6 and plain(t["name"]) in p)) else "media",
        "sources": sources or [source("Inventario oficial 511NJ + DelDOT", "https://511nj.org/camera")],
        "note": "Traducción determinista a datos reales; no se generan datos nuevos.",
    }


# ---------------------------------------------------------------------------
# Idea 4 · contexto / triangulación
# ---------------------------------------------------------------------------
def context_for_camera(payload, cameras, meta=None):
    cid = payload.get("id") or payload.get("camId")
    c = next((x for x in cameras if str(x.get("id")) == str(cid)), None)
    if not c or not all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon")):
        return {"ok": False, "error": "Cámara no encontrada o sin coordenadas."}
    near = nearest(cameras, c["lat"], c["lon"], limit=7, max_km=12)
    others = [{"id": x["id"], "name": x["name"], "source": x.get("source"),
               "distKm": round(d, 1), "stream": bool(x.get("stream")),
               "trust": score_camera(x)["trust"]} for d, x in near if x["id"] != c["id"]][:6]
    alerts = nws_point_alerts(c["lat"], c["lon"])
    wx = weather_at(c["lat"], c["lon"])
    evs = events_near(c["lat"], c["lon"], 15)
    t = score_camera(c)
    lines = []
    lines.append("%s pertenece al inventario oficial de %s; %s."
                 % (c["name"], c.get("source", "fuente pública"),
                    "publica video HLS" if c.get("stream") else "no publica video HLS en la fuente"))
    if others:
        lines.append("Hay %d cámaras oficiales a menos de 12 km; la más cercana está a %.1f km."
                     % (len(others), others[0]["distKm"]))
    else:
        lines.append("No hay otras cámaras del inventario en un radio de 12 km.")
    if alerts:
        lines.append("NWS tiene %d alerta(s) activa(s) en este punto: %s."
                     % (len(alerts), ", ".join(str(a.get("event")) for a in alerts[:3])))
    else:
        lines.append("NWS no muestra alertas meteorológicas activas en este punto ahora mismo.")
    if wx:
        bits = ["%.0f °C" % wx["temperatureC"] if wx.get("temperatureC") is not None else None,
                "precipitación %s mm" % wx["precipitationMm"] if wx.get("precipitationMm") is not None else None,
                "viento %s km/h" % wx["windKmh"] if wx.get("windKmh") is not None else None]
        lines.append("Clima actual en la coordenada: " + ", ".join(x for x in bits if x) + ".")
    if evs:
        kinds = {}
        for e in evs:
            kinds[e["category"] or e["type"] or "Evento"] = kinds.get(
                e["category"] or e["type"] or "Evento", 0) + 1
        desc = ", ".join("%d %s" % (v, k) for k, v in list(kinds.items())[:3])
        lines.append("El feed oficial de 511NJ publica %d evento(s) a 15 km (%s); el más cercano está a %.1f km."
                     % (len(evs), desc, evs[0]["distKm"]))
    else:
        lines.append("El feed oficial de 511NJ no publica eventos con coordenada a 15 km.")
    tours = c.get("tours") or []
    if tours:
        lines.append("La agencia la incluye en %d tour(es) oficiales." % len(tours))
    lines.append("Confianza del dato: %s (%d/100). No se identifica tráfico, personas ni placas."
                 % (t["trustLabel"], t["trust"]))
    srcs = [source("Inventario oficial", c.get("official") or "https://511nj.org/camera"),
            source("NWS punto", NWS_POINT.format(lat=round(c["lat"], 3), lon=round(c["lon"], 3))),
            source("511NJ eventos", "https://511nj.org/", (EVENTS or {}).get("at"))]
    if wx:
        srcs.append(wx["source"])
    return {
        "ok": True, "at": now(), "id": c["id"], "name": c["name"],
        "summary": " ".join(lines), "lines": lines,
        "trust": t["trust"], "trustLabel": t["trustLabel"], "trustReasons": t["trustReasons"],
        "neighbors": others, "alerts": alerts[:5], "weather": wx, "tours": tours,
        "events": evs,
        "confidence": "alta" if (wx and alerts is not None) else "media",
        "sources": srcs,
        "note": "Correlación de fuentes públicas; ninguna afirmación sobre incidentes no publicados.",
    }


# ---------------------------------------------------------------------------
# Idea 12 · alertas por zona
# ---------------------------------------------------------------------------
def zone_alerts(payload, cameras, meta=None):
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
    radius = max(1, min(150, float(payload.get("radiusKm", 40))))
    state = str(payload.get("state") or "NJ,DE")
    if state not in ("NJ", "DE", "NJ,DE"):
        state = "NJ,DE"
    alerts = nws_alerts()
    if geo:
        alerts = [a for a in alerts if a.get("lat") is None
                  or haversine(geo["lat"], geo["lon"], a["lat"], a["lon"]) <= max(radius, 80)]
        cams = [c for c in cameras if all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon"))
                and haversine(geo["lat"], geo["lon"], c["lat"], c["lon"]) <= radius]
        label = "%.0f km alrededor de tu ubicación" % radius
        wx = weather_at(geo["lat"], geo["lon"])
    else:
        cams = [c for c in cameras if (("NJ" in state and c.get("source") == "511NJ")
                                       or ("DE" in state and c.get("source") == "DelDOT"))]
        label = state.replace(",", " y ")
        wx = weather_at(40.15, -74.65)
    low = [c for c in cams if score_camera(c)["trust"] < 60]
    no_video = [c for c in cams if not c.get("stream")]
    zones = {}
    for c in low + no_video:
        zones[c.get("zone") or "Sin zona"] = zones.get(c.get("zone") or "Sin zona", 0) + 1
    top = sorted(zones.items(), key=lambda x: x[1], reverse=True)[:4]
    if geo:
        evs = events_near(geo["lat"], geo["lon"], radius, limit=10)
    else:
        evs = [{
            "id": e.get("eventId"), "type": e.get("eventType"),
            "category": e.get("categoryName"), "facility": e.get("facility"),
            "county": e.get("county"), "state": e.get("state"),
            "distKm": None, "start": e.get("startDateTime"), "end": e.get("endDateTime"),
            "updated": e.get("lastUpdateDate"), "level": event_level(e),
        } for e in official_events(state, limit=10)]
    out = []
    for a in alerts[:8]:
        sev = str(a.get("severity") or "").lower()
        level = "alto" if sev in ("extreme", "severe") else ("medio" if sev == "moderate" else "bajo")
        out.append({
            "type": "Alerta meteorológica oficial", "zone": a.get("area") or label,
            "level": level, "confidence": "alta",
            "text": "%s · %s" % (a.get("event"), str(a.get("headline") or "")[:160]),
            "evidence": ["NWS publicó esta alerta activa", "vigencia: %s → %s" % (a.get("onset"), a.get("expires"))],
            "source": source("NWS", a.get("url") or NWS_ALERTS, a.get("onset")),
        })
    for e in evs[:6]:
        out.append({
            "type": "Evento oficial 511NJ",
            "zone": e.get("county") or e.get("state") or label,
            "level": e.get("level") or "bajo", "confidence": "alta",
            "text": "%s en %s%s" % (e.get("category") or e.get("type") or "Evento",
                                    e.get("facility") or e.get("county") or "zona sin nombre",
                                    (" · a %.1f km" % e["distKm"]) if e.get("distKm") else ""),
            "evidence": ["ID oficial: %s" % e.get("id"),
                         "actualizado: %s" % e.get("updated"),
                         "inicio: %s" % e.get("start")],
            "source": source("511NJ eventos", "https://511nj.org/", e.get("updated")),
        })
    if top:
        out.append({
            "type": "Zonas con dato débil", "zone": top[0][0], "level": "medio",
            "confidence": "media",
            "text": "%d cámaras de esa zona tienen baja confianza o sin video en el inventario."
                    % top[0][1],
            "evidence": ["Puntaje calculado con fuente oficial, stream e historial local",
                         "No implica que haya un incidente"],
            "source": source("Inventario oficial + historial local", "https://511nj.org/camera"),
        })
    if wx and (wx.get("precipitationMm") or 0) > 0:
        out.append({
            "type": "Condición meteorológica actual", "zone": label, "level": "bajo",
            "confidence": "alta",
            "text": "Precipitación de %s mm registrada en la coordenada a las %s."
                    % (wx["precipitationMm"], wx.get("time")),
            "evidence": ["Open-Meteo/NOAA, dato observado, no pronóstico"],
            "source": wx["source"],
        })
    return {
        "ok": True, "at": now(), "area": label, "alerts": out,
        "camerasChecked": len(cams), "lowTrust": len(low), "noVideo": len(no_video),
        "confidence": "alta para alertas NWS; media para estimaciones de zona",
        "sources": [source("NWS", NWS_ALERTS),
                    source("Open-Meteo", "https://open-meteo.com/"),
                    source("511NJ eventos", "https://511nj.org/", (EVENTS or {}).get("at")),
                    source("Inventario oficial", "https://511nj.org/camera")],
        "note": "Esto no predice congestionamiento: solo reúne señales verificables y su confianza.",
    }


# ---------------------------------------------------------------------------
# Idea 6 · resumen matutino
# ---------------------------------------------------------------------------
def build_brief(payload, cameras, meta=None):
    fav_ids = set(str(x) for x in (payload.get("favs") or []))
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
    favs = [c for c in cameras if c["id"] in fav_ids]
    basis = favs or cameras
    center_lat = (geo or {}).get("lat")
    center_lon = (geo or {}).get("lon")
    if center_lat is None and favs:
        withcoord = [c for c in favs if isinstance(c.get("lat"), (int, float))]
        if withcoord:
            center_lat = sum(c["lat"] for c in withcoord) / len(withcoord)
            center_lon = sum(c["lon"] for c in withcoord) / len(withcoord)
    if center_lat is None:
        center_lat, center_lon = 40.15, -74.65
    alerts = nws_alerts()
    wx = weather_at(center_lat, center_lon)
    trust = [score_camera(c)["trust"] for c in basis]
    avg = round(sum(trust) / len(trust)) if trust else 0
    low = [c for c in basis if score_camera(c)["trust"] < 60]
    best = sorted(basis, key=lambda c: score_camera(c)["trust"], reverse=True)[:3]
    headline = ("Buenos días. %s cámaras oficiales en tu selección, confianza media %d/100"
                % (len(basis), avg))
    if alerts:
        headline += ", %d alertas meteorológicas activas en NJ/DE." % len(alerts)
    else:
        headline += ", sin alertas meteorológicas activas en NJ/DE."
    bullets = []
    if wx:
        bullets.append({
            "text": "Clima ahora en tu zona: %.0f °C, precipitación %s mm, viento %s km/h (%s)."
                    % (wx.get("temperatureC") or 0, wx.get("precipitationMm"),
                       wx.get("windKmh"), wx.get("time")),
            "confidence": "alta", "source": wx["source"],
        })
    if alerts:
        a = alerts[0]
        bullets.append({
            "text": "Alerta NWS: %s en %s (severidad %s)."
                    % (a.get("event"), a.get("area"), a.get("severity")),
            "confidence": "alta", "source": source("NWS", a.get("url") or NWS_ALERTS, a.get("onset")),
        })
    if low:
        bullets.append({
            "text": "%d cámaras de tu selección tienen baja confianza de dato; conviene elegir alternativa."
                    % len(low), "confidence": "media",
            "source": source("Historial local e inventario oficial", "https://511nj.org/camera"),
        })
    if best:
        bullets.append({
            "text": "Mejor punto de partida: %s (%d/100)."
                    % (best[0]["name"], score_camera(best[0])["trust"]),
            "confidence": "media", "source": source("Radar de confianza", "https://511nj.org/camera"),
        })
    bullets.append({
        "text": "Este resumen no revisa imágenes ni reporta incidentes: solo une datos públicos verificables.",
        "confidence": "alta", "source": source("HorizonView", ""),
    })
    return {
        "ok": True, "at": now(), "headline": headline, "bullets": bullets,
        "basis": "favoritos" if favs else "inventario completo",
        "confidence": "media-alta", "sources": [source("NWS", NWS_ALERTS),
                                               source("Open-Meteo", "https://open-meteo.com/"),
                                               source("Inventario oficial", "https://511nj.org/camera")],
    }


# ---------------------------------------------------------------------------
# Idea 13 · favoritos inteligentes
# ---------------------------------------------------------------------------
def smart_groups(payload, cameras, meta=None):
    fav_ids = set(str(x) for x in (payload.get("favs") or []))
    favs = [c for c in cameras if c["id"] in fav_ids]
    if not favs:
        return {"ok": True, "at": now(), "groups": [], "note": "Aún no hay favoritos guardados."}
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
    groups = []

    def group(title, desc, items, icon):
        if items:
            groups.append({"title": title, "description": desc, "icon": icon,
                           "count": len(items),
                           "cameras": [{"id": c["id"], "name": c["name"],
                                        "zone": c.get("zone"),
                                        "trust": score_camera(c)["trust"]} for c in items[:12]]})

    group("Por corredor", "Agrupados por la zona real publicada por la agencia.", favs, "◇")
    high = [c for c in favs if score_camera(c)["trust"] >= 75]
    group("Dato confiable", "Stream oficial y sin fallos registrados en este dispositivo.", high, "✓")
    revision = [c for c in favs if not c.get("stream") or score_camera(c)["trust"] < 60]
    group("Revisar", "Sin video o con historial de fallos: conviene buscar alternativa.", revision, "!")
    by_tour = {}
    for c in favs:
        for name in (c.get("tours") or []):
            by_tour.setdefault(name, []).append(c)
    for name, items in sorted(by_tour.items(), key=lambda x: len(x[1]), reverse=True)[:4]:
        if len(items) > 1:
            group("Tour: " + name, "Pertenencia real publicada por 511NJ.", items, "↗")
    if geo:
        near = [c for d, c in nearest(favs, geo["lat"], geo["lon"], limit=len(favs), max_km=25)]
        group("Cerca de ti (25 km)", "Distancia calculada desde tu GPS.", near, "◎")
    return {"ok": True, "at": now(), "groups": groups,
            "note": "Agrupación local y privada: no se sincroniza ni se guarda en la nube."}


# ---------------------------------------------------------------------------
# Idea 15 · capas de mapa
# ---------------------------------------------------------------------------
def weather_layers(payload, cameras, meta=None):
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
    lat = float((geo or {}).get("lat", 40.15))
    lon = float((geo or {}).get("lon", -74.65))
    items = []
    for a in nws_alerts():
        if a.get("lat") is not None and haversine(lat, lon, a["lat"], a["lon"]) > 300:
            continue
        n = nearest(cameras, a["lat"], a["lon"], limit=1) if a.get("lat") is not None else []
        items.append({
            "type": "Alerta NWS", "label": a.get("event") or "Alerta", "detail": a.get("area"),
            "severity": a.get("severity"), "lat": a.get("lat"), "lon": a.get("lon"),
            "camera": ({"id": n[0][1]["id"], "name": n[0][1]["name"], "distKm": round(n[0][0], 1)}
                       if n else None), "source": a.get("url") or NWS_ALERTS, "at": a.get("onset"),
        })
    for e in events_near(lat, lon, max(15.0, float(payload.get("radiusKm", 25))), limit=25):
        if e.get("lat") is None:
            continue
        n = nearest(cameras, e["lat"], e["lon"], limit=1)
        items.append({
            "type": "Evento 511NJ", "label": e.get("category") or e.get("type") or "Evento",
            "detail": "%s · %s · id %s" % (e.get("facility"), e.get("county"), e.get("id")),
            "severity": e.get("level"), "lat": e["lat"], "lon": e["lon"],
            "camera": ({"id": n[0][1]["id"], "name": n[0][1]["name"], "distKm": round(n[0][0], 1)}
                       if n else None), "source": "https://511nj.org/", "at": e.get("updated"),
        })
    wx = weather_at(lat, lon)
    if wx:
        items.append({
            "type": "Clima actual", "label": "Temperatura %s °C · precipitación %s mm"
                                      % (wx.get("temperatureC"), wx.get("precipitationMm")),
            "detail": "Viento %s km/h · visibilidad %s m" % (wx.get("windKmh"), wx.get("visibilityM")),
            "severity": "info", "lat": lat, "lon": lon, "camera": None,
            "source": wx["source"]["url"], "at": wx.get("time"),
        })
    if payload.get("infra"):
        for e in osm_infrastructure(lat, lon, float(payload.get("radiusKm", 8))):
            n = nearest(cameras, e["lat"], e["lon"], limit=1)
            items.append({
                "type": "Obra vial OSM", "label": e["label"], "detail": e.get("detail"),
                "severity": "obras", "lat": e["lat"], "lon": e["lon"],
                "camera": ({"id": n[0][1]["id"], "name": n[0][1]["name"], "distKm": round(n[0][0], 1)}
                           if n else None), "source": e["url"], "at": now(),
            })
    return {
        "ok": True, "at": now(), "layers": items,
        "sources": [source("NWS", NWS_ALERTS), source("Open-Meteo", "https://open-meteo.com/"),
                    source("511NJ eventos", "https://511nj.org/", (EVENTS or {}).get("at")),
                    source("OpenStreetMap / Overpass", "https://overpass-api.de/")],
        "note": "Las capas son datos públicos, no detectión automática de incidentes.",
    }


# ---------------------------------------------------------------------------
# Idea 9 · tours narrados (categoría aparte; la narrativa se construye en el cliente)
# ---------------------------------------------------------------------------
def tour_narrative(payload, cameras, meta=None, tours_data=None):
    name = str(payload.get("tour") or "")
    by = ((tours_data or {}).get("byCamera") or {})
    list_info = ((tours_data or {}).get("tours") or [])
    known = set(str(t.get("name")) for t in list_info)
    for c in cameras:
        known.update(str(x) for x in (c.get("tours") or []))
    if name and name not in known:
        names = [n for n in sorted(known) if name.lower() in n.lower()]
        if len(names) == 1:
            name = names[0]
    if not name or name not in known:
        return {"ok": False, "error": "Selecciona un tour oficial de la lista."}
    geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
    chosen = [c for c in cameras if name in (c.get("tours") or [])]
    if not chosen:
        # La pertenencia real también puede venir como cámara → tours (formato del archivo).
        ids = set(cid for cid, names in by.items() if name in (names or []))
        chosen = [c for c in cameras if c.get("id") in ids]
    if not chosen:
        return {"ok": False, "error": "Ese tour no tiene cámaras visibles en el inventario actual."}
    chosen.sort(key=lambda c: (c.get("zone") or "", c.get("name") or ""))
    zones = {}
    for c in chosen:
        zones.setdefault(c.get("zone") or "Sin zona", []).append(c)
    steps = []
    prev = None
    for c in chosen[:10]:
        dprev = (round(haversine(prev["lat"], prev["lon"], c["lat"], c["lon"]), 1)
                 if prev and all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon")) else None)
        duser = (round(haversine(geo["lat"], geo["lon"], c["lat"], c["lon"]), 1)
                 if geo and all(isinstance(c.get(k), (int, float)) for k in ("lat", "lon")) else None)
        line = "%s.%s Coordenada real %s. %s" % (
            c["name"],
            (" A %.1f km de la cámara anterior." % dprev) if dprev is not None else "",
            ("%.5f, %.5f" % (c["lat"], c["lon"])),
            ("A %.1f km de ti." % duser) if duser is not None else "")
        steps.append({
            "id": c["id"], "name": c["name"], "zone": c.get("zone"),
            "lat": c.get("lat"), "lon": c.get("lon"), "text": line,
            "stream": bool(c.get("stream")), "trust": score_camera(c)["trust"],
            "official": c.get("official"),
        })
        prev = c
    intro = ("Tour oficial «%s» de 511NJ: %d cámaras públicas en el inventario vigente, "
             "repartidas en %d zonas. Recorrido ordenado por zona y nombre; los tramos y "
             "distancias son estimaciones sobre coordenadas reales, no itinerarios oficiales."
             % (name, len(chosen), len(zones)))
    outro = ("Fuente: pertenencia publicada por 511NJ y coordenadas del inventario. "
             "No se añaden curiosidades ni hechos históricos no verificados.")
    return {
        "ok": True, "at": now(), "tour": name, "intro": intro, "outro": outro, "steps": steps,
        "total": len(chosen), "zones": [{"name": z, "count": len(v)} for z, v in zones.items()],
        "confidence": "alta (pertenencia y coordenadas oficiales)",
        "sources": [source("511NJ tours", "https://511nj.org/camera",
                           (tours_data or {}).get("at")),
                    source("Inventario oficial", "https://511nj.org/camera")],
    }


# ---------------------------------------------------------------------------
# Idea 16 · comparador
# ---------------------------------------------------------------------------
def compare_cameras(payload, cameras, meta=None):
    ids = [str(x) for x in (payload.get("ids") or [])][:4]
    if len(ids) < 2:
        return {"ok": False, "error": "Selecciona al menos 2 cámaras (máximo 4)."}
    by = {str(c["id"]): c for c in cameras}
    selected = [by[i] for i in ids if i in by]
    if len(selected) < 2:
        return {"ok": False, "error": "Algunas cámaras ya no están disponibles."}
    items = []
    for c in selected:
        t = score_camera(c)
        items.append({
            "id": c["id"], "name": c["name"], "zone": c.get("zone"),
            "stream": c.get("stream"), "official": c.get("official"),
            "trust": t["trust"], "trustLabel": t["trustLabel"],
            "trustReasons": t["trustReasons"][:4], "tours": c.get("tours") or [],
        })
    best = max(items, key=lambda x: x["trust"])
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            ca, cb = by[a["id"]], by[b["id"]]
            if all(isinstance(c.get(k), (int, float)) for c in (ca, cb) for k in ("lat", "lon")):
                pairs.append({"a": a["id"], "b": b["id"],
                              "distKm": round(haversine(ca["lat"], ca["lon"], cb["lat"], cb["lon"]), 1)})
    return {
        "ok": True, "at": now(), "cameras": items, "pairs": pairs,
        "recommendation": "Según la calidad del dato, empieza por %s (%d/100)."
                          % (best["name"], best["trust"]),
        "confidence": "media",
        "note": "La recomendación es sobre la fuente del video, no sobre lo que ocurre en la imagen.",
        "sources": [source("Inventario oficial", "https://511nj.org/camera")],
    }
