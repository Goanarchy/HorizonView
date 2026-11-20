"""Fuentes públicas adicionales y herramientas combinadas.

Este módulo es determinista y explicable:
 - solo consume fuentes públicas verificables (511NJ, NWS, Open-Meteo, USGS, Radio Browser y sitios oficiales de radio);
 - guarda fuente, hora y confianza en cada respuesta;
 - no inventa capacidad de cámara, evento, programa de radio ni umbral hidrológico.

Las respuestas se cachean en memoria para no abusar de las APIs públicas.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

UA = "HorizonView/4.0 (+app publica gratuita; contacto: fuentes verificables)"
NWS_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/geo+json",
}
CACHE: dict[str, tuple[float, object]] = {}
CACHE_LOCK = threading.Lock()
MEMORY_TTL = 300.0

WMO = {
    0: "Despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna",
    55: "Llovizna densa",
    56: "Llovizna congelante ligera",
    57: "Llovizna congelante",
    61: "Lluvia débil",
    63: "Lluvia",
    65: "Lluvia fuerte",
    66: "Lluvia congelante",
    67: "Lluvia congelante fuerte",
    71: "Nieve débil",
    73: "Nieve",
    75: "Nieve fuerte",
    77: "Granos de nieve",
    80: "Chubascos débiles",
    81: "Chubascos",
    82: "Chubascos fuertes",
    85: "Chubascos de nieve",
    86: "Chubascos de nieve fuertes",
    95: "Tormenta eléctrica",
    96: "Tormenta con granizo",
    99: "Tormenta con granizo fuerte",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(name: str):
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def cached(key: str, ttl: float, producer):
    """Devuelve (valor, desdeCache, fetchedAt)."""
    with CACHE_LOCK:
        item = CACHE.get(key)
        if item and time.time() - item[0] < ttl:
            return item[1], True, item[2]
    value = producer()
    fetched = now_iso()
    with CACHE_LOCK:
        CACHE[key] = (time.time(), value, fetched)
    return value, False, fetched


def http_json(url: str, *, ttl: float = MEMORY_TTL, headers: dict | None = None,
              timeout: float = 14):
    def producer():
        response = requests.get(url, headers=headers or NWS_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()

    return cached("http:" + url, ttl, producer)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, a)))


def weather_animation(code: int | None, is_day: bool = True, gust: float = 0.0) -> str:
    if gust and gust >= 45:
        return "wind"
    if code is None:
        return "cloudy"
    if code == 0:
        return "clear-day" if is_day else "clear-night"
    if code in (1, 2):
        return "partly-day" if is_day else "partly-night"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloudy"


def _first_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text or "", re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Zonas locales de cámaras
# ---------------------------------------------------------------------------
def local_zones_data():
    return cached("local-zones", 3600, lambda: load_json("local_zones.json"))[0]


def annotate_cameras(cameras: list[dict]) -> list[dict]:
    zones = local_zones_data()["zones"]
    result = []
    for camera in cameras:
        item = dict(camera)
        matches = []
        for zone in zones:
            if camera.get("id") in zone.get("cameraIds", []):
                matches.append(
                    {
                        "id": zone["id"],
                        "name": zone["name"],
                        "label": zone.get("label", zone["name"]),
                        "distanceKm": zone.get("distanceKm", {}).get(camera.get("id")),
                        "center": zone.get("center"),
                    }
                )
        item["localZones"] = matches
        result.append(item)
    return result


def zone_camera_ids(zone_id: str) -> list[str]:
    for zone in local_zones_data()["zones"]:
        if zone["id"] == zone_id:
            return list(zone.get("cameraIds", []))
    return []


def zone_by_id(zone_id: str) -> dict | None:
    for zone in local_zones_data()["zones"]:
        if zone["id"] == zone_id:
            return zone
    return None


def zones_summary(cameras: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for camera in cameras:
        for zone in camera.get("localZones", []):
            counts[zone["id"]] = counts.get(zone["id"], 0) + 1
    result = []
    for zone in local_zones_data()["zones"]:
        result.append(
            {
                "id": zone["id"],
                "name": zone["name"],
                "label": zone.get("label"),
                "center": zone.get("center"),
                "radiusKm": zone.get("radiusKm"),
                "cameraCount": counts.get(zone["id"], 0),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Clima en tiempo real + frecuencias públicas
# ---------------------------------------------------------------------------
def _nws_point(lat: float, lon: float):
    url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
    data, hit, fetched = http_json(url, ttl=1800)
    return data, hit, fetched, url


def _nws_stations(point: dict):
    url = point.get("properties", {}).get("observationStations")
    if not url:
        return [], False, now_iso()
    data, hit, fetched = http_json(url, ttl=3600)
    return data.get("features", []), hit, fetched


def _nws_observation(point: dict, lat: float, lon: float):
    stations, _, _ = _nws_stations(point)
    if not stations:
        return None, None
    nearest = None
    for feature in stations:
        geom = feature.get("geometry", {}).get("coordinates", [])
        if len(geom) < 2:
            continue
        s_lon, s_lat = geom[0], geom[1]
        distance = haversine(lat, lon, s_lat, s_lon)
        props = feature.get("properties", {})
        candidate = (distance, props.get("stationIdentifier"), props)
        if nearest is None or distance < nearest[0]:
            nearest = candidate
    if not nearest or not nearest[1]:
        return None, None
    distance, station_id, props = nearest
    url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    obs, _, fetched = http_json(url, ttl=300)
    info = obs.get("properties", {}) if isinstance(obs, dict) else {}
    result = {
        "stationId": station_id,
        "stationName": props.get("name"),
        "distanceKm": round(distance, 2),
        "observedAt": info.get("timestamp"),
        "description": info.get("textDescription"),
        "temperatureC": (info.get("temperature") or {}).get("value"),
        "dewpointC": (info.get("dewpoint") or {}).get("value"),
        "humidity": (info.get("relativeHumidity") or {}).get("value"),
        "windKmh": (info.get("windSpeed") or {}).get("value"),
        "windGustKmh": (info.get("windGust") or {}).get("value"),
        "windDirection": (info.get("windDirection") or {}).get("value"),
        "pressurePa": (info.get("barometricPressure") or {}).get("value"),
        "visibilityM": (info.get("visibility") or {}).get("value"),
        "windChillC": (info.get("windChill") or {}).get("value"),
        "icon": info.get("icon"),
        "rawMessage": info.get("rawMessage"),
        "sourceUrl": url,
        "fetchedAt": fetched,
    }
    return result, point


def _open_meteo(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,"
        "wind_speed_10m,wind_gusts_10m,cloud_cover,is_day"
        "&hourly=temperature_2m,precipitation_probability,weather_code"
        "&forecast_days=2&timezone=America%2FNew_York"
    )
    return http_json(url, ttl=600)


def _nws_alerts_point(lat: float, lon: float):
    url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
    data, hit, fetched = http_json(url, ttl=300)
    alerts = []
    for feature in data.get("features", []) if isinstance(data, dict) else []:
        props = feature.get("properties", {})
        alerts.append(
            {
                "id": props.get("id"),
                "event": props.get("event"),
                "severity": props.get("severity"),
                "urgency": props.get("urgency"),
                "headline": props.get("headline"),
                "startsAt": props.get("effective") or props.get("onset"),
                "endsAt": props.get("expires") or props.get("ends"),
                "sourceUrl": props.get("id") or url,
            }
        )
    return alerts, url, fetched


def _nwr_info(point: dict):
    nwr = point.get("properties", {}).get("nwr") or {}
    call_sign = nwr.get("transmitter")
    area_url = nwr.get("areaBroadcast")
    point_url = nwr.get("pointBroadcast")
    frequency = None
    detail_url = point_url or area_url
    # La frecuencia de transmisión aparece en el broadcast de área, no en el
    # de punto (que solo contiene el pronóstico hablado para las coordenadas).
    for url in (area_url, point_url):
        if not url:
            continue
        try:
            response = requests.get(url, headers=NWS_HEADERS, timeout=12)
            response.raise_for_status()
            frequency = _first_number(response.text, r"frequency\s+([0-9.]+)")
            if frequency is not None:
                detail_url = url
                break
        except Exception:
            continue
    return {
        "callSign": call_sign,
        "sameCode": nwr.get("sameCode"),
        "frequencyMhz": frequency,
        "service": "NOAA Weather Radio (transmisión por frecuencia, no stream de internet)",
        "sourceUrl": detail_url,
        "pointUrl": point_url,
        "audioOnInternet": False,
    }


def air_quality(lat: float, lon: float) -> dict:
    """Calidad del aire actual de Open-Meteo (API pública, sin clave)."""
    url = ("https://air-quality-api.open-meteo.com/v1/air-quality"
           "?latitude=%.4f&longitude=%.4f&current=us_aqi,pm2_5&timezone=auto" % (lat, lon))
    data, hit, fetched = http_json(url, ttl=900.0,
                                   headers={"User-Agent": UA, "Accept": "application/json"})
    current = (data or {}).get("current") or {}
    return {
        "usAqi": current.get("us_aqi"),
        "pm25": current.get("pm2_5"),
        "at": current.get("time") or fetched,
        "cached": hit,
        "source": {"name": "Open-Meteo Air Quality", "url": "https://air-quality-api.open-meteo.com/",
                   "fetchedAt": fetched},
    }


def weather_live(lat: float, lon: float) -> dict:
    errors = []
    sources = []
    try:
        point, point_hit, point_fetched, point_url = _nws_point(lat, lon)
        sources.append({"name": "NWS punto", "url": point_url, "fetchedAt": point_fetched, "cached": point_hit})
    except Exception as exc:
        errors.append("NWS punto: " + str(exc)[:120])
        point, point_url = {}, ""

    observation = None
    if point:
        try:
            observation, _ = _nws_observation(point, lat, lon)
            if observation:
                sources.append(
                    {
                        "name": "NWS observación " + str(observation.get("stationId")),
                        "url": observation["sourceUrl"],
                        "fetchedAt": observation["fetchedAt"],
                    }
                )
        except Exception as exc:
            errors.append("NWS observación: " + str(exc)[:120])

    meteo = None
    meteo_url = ""
    meteo_fetched = now_iso()
    meteo_hit = False
    try:
        meteo, meteo_hit, meteo_fetched = _open_meteo(lat, lon)
        meteo_url = "https://api.open-meteo.com/v1/forecast"
        sources.append({"name": "Open-Meteo", "url": meteo_url, "fetchedAt": meteo_fetched, "cached": meteo_hit})
    except Exception as exc:
        errors.append("Open-Meteo: " + str(exc)[:120])

    alerts = []
    alert_url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
    alert_fetched = now_iso()
    try:
        alerts, alert_url, alert_fetched = _nws_alerts_point(lat, lon)
        sources.append({"name": "NWS alertas", "url": alert_url, "fetchedAt": alert_fetched})
    except Exception as exc:
        errors.append("NWS alertas: " + str(exc)[:120])

    current = meteo.get("current", {}) if isinstance(meteo, dict) else {}
    code = current.get("weather_code")
    is_day = bool(current.get("is_day", 1))
    gust = current.get("wind_gusts_10m") or (observation or {}).get("windGustKmh") or 0
    temp = current.get("temperature_2m")
    if temp is None and observation:
        temp = observation.get("temperatureC")
    humidity = current.get("relative_humidity_2m")
    if humidity is None and observation:
        humidity = observation.get("humidity")
    wind = current.get("wind_speed_10m")
    if wind is None and observation:
        wind = observation.get("windKmh")
    precip = current.get("precipitation") or 0.0
    cloud = current.get("cloud_cover")

    hourly = []
    hours = meteo.get("hourly", {}) if isinstance(meteo, dict) else {}
    times = hours.get("time", [])
    for index, stamp in enumerate(times[:18]):
        h_code = hours.get("weather_code", [None] * len(times))[index]
        hour_is_day = 6 <= int(stamp[11:13]) < 19
        hourly.append(
            {
                "time": stamp,
                "tempC": hours.get("temperature_2m", [None] * len(times))[index],
                "code": h_code,
                "condition": WMO.get(h_code, "—"),
                "animation": weather_animation(h_code, hour_is_day),
                "precipitationProbability": hours.get("precipitation_probability", [None] * len(times))[index],
            }
        )

    nwr = _nwr_info(point) if point else {}
    air = None
    try:
        air = air_quality(lat, lon)
        sources.append({"name": air["source"]["name"], "url": air["source"]["url"],
                        "fetchedAt": air["source"]["fetchedAt"], "cached": air["cached"]})
    except Exception as exc:
        errors.append("Calidad del aire: " + str(exc)[:120])
    props = point.get("properties", {}) if isinstance(point, dict) else {}
    astronomical = props.get("astronomicalData") or {}

    confidence = 0.97
    if not point:
        confidence -= 0.2
    if not meteo:
        confidence -= 0.15
    if not observation:
        confidence -= 0.1
    confidence = round(max(0.4, confidence), 2)

    return {
        "at": now_iso(),
        "latitude": lat,
        "longitude": lon,
        "location": (props.get("relativeLocation", {}).get("properties") or {}),
        "forecastOffice": props.get("forecastOffice"),
        "radarStation": props.get("radarStation"),
        "timeZone": props.get("timeZone"),
        "sunrise": astronomical.get("sunrise"),
        "sunset": astronomical.get("sunset"),
        "current": {
            "temperatureC": round(temp, 1) if isinstance(temp, (int, float)) else None,
            "humidity": round(humidity) if isinstance(humidity, (int, float)) else None,
            "windKmh": round(wind, 1) if isinstance(wind, (int, float)) else None,
            "windGustKmh": round(gust, 1) if isinstance(gust, (int, float)) else None,
            "precipitationMm": precip,
            "cloudCover": cloud,
            "isDay": is_day,
            "code": code,
            "description": WMO.get(code, (observation or {}).get("description") or "Sin dato"),
            "animation": weather_animation(code, is_day, gust),
            "icon": (observation or {}).get("icon"),
            "observedAt": (observation or {}).get("observedAt") or current.get("time"),
        },
        "observation": observation,
        "hourly": hourly,
        "alerts": alerts,
        "nwr": nwr,
        "air": air,
        "sources": sources,
        "confidence": confidence,
        "errors": errors,
    }


def sensors_near(lat: float, lon: float) -> dict:
    bbox = f"{lon - 0.13:.4f},{lat - 0.12:.4f},{lon + 0.13:.4f},{lat + 0.12:.4f}"
    url = (
        "https://waterservices.usgs.gov/nwis/iv/?format=json"
        f"&bBox={bbox}&parameterCd=00060,00065&siteStatus=active"
    )
    data, hit, fetched = http_json(url, ttl=900)
    sensors = []
    series = data.get("value", {}).get("timeSeries", []) if isinstance(data, dict) else []
    for item in series:
        source = item.get("sourceInfo", {})
        variable = item.get("variable", {})
        values = item.get("values", [])
        if not values or not values[0].get("value"):
            continue
        reading = values[0]["value"][0]
        observed = reading.get("dateTime", "")
        # Descarta series históricas: el panel muestra sensores activos, no archivo.
        if observed and observed.startswith("20"):
            try:
                stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - stamp).total_seconds() > 86400:
                    continue
            except ValueError:
                continue
        geo = source.get("geoLocation", {}).get("geogLocation", {})
        site_lat, site_lon = geo.get("latitude"), geo.get("longitude")
        unit = (variable.get("unit") or {}).get("unitCode")
        variable_name = (variable.get("variableName") or "").replace("&#179;", "³")
        sensors.append(
            {
                "id": (source.get("siteCode") or [{}])[0].get("value"),
                "name": source.get("siteName"),
                "type": "gage" if "height" in variable_name.lower() else "streamflow",
                "variable": variable_name,
                "value": float(reading["value"]) if reading.get("value") not in (None, "") else None,
                "unit": unit,
                "qualifier": ",".join(reading.get("qualifiers", [])),
                "observedAt": observed,
                "lat": site_lat,
                "lon": site_lon,
                "distanceKm": round(haversine(lat, lon, site_lat, site_lon), 2)
                if isinstance(site_lat, (int, float))
                else None,
                "sourceUrl": "https://waterdata.usgs.gov/nwis/uv?site_no="
                + str((source.get("siteCode") or [{}])[0].get("value") or ""),
                "provisional": "P" in reading.get("qualifiers", []),
            }
        )
    sensors.sort(key=lambda item: (item.get("distanceKm") is None, item.get("distanceKm") or 9999))

    weather = weather_live(lat, lon)
    extra = []
    if weather.get("observation"):
        obs = weather["observation"]
        extra.append(
            {
                "id": obs["stationId"],
                "name": obs["stationName"],
                "type": "weather",
                "variable": "Temperatura / viento / humedad (observación NWS)",
                "value": obs.get("temperatureC"),
                "unit": "°C",
                "qualifier": "official",
                "observedAt": obs.get("observedAt"),
                "lat": None,
                "lon": None,
                "distanceKm": obs.get("distanceKm"),
                "sourceUrl": obs["sourceUrl"],
                "provisional": False,
            }
        )
    nwr = weather.get("nwr") or {}
    if nwr.get("frequencyMhz") or nwr.get("callSign"):
        extra.append(
            {
                "id": nwr.get("callSign") or "NWR",
                "name": "NOAA Weather Radio " + str(nwr.get("callSign") or ""),
                "type": "frequency",
                "variable": "Frecuencia de radio meteorológica",
                "value": nwr.get("frequencyMhz"),
                "unit": "MHz",
                "qualifier": "official",
                "observedAt": weather.get("at"),
                "lat": None,
                "lon": None,
                "distanceKm": None,
                "sourceUrl": nwr.get("sourceUrl"),
                "provisional": False,
            }
        )

    return {
        "at": now_iso(),
        "latitude": lat,
        "longitude": lon,
        "usgs": sensors,
        "additional": extra,
        "sources": [
            {"name": "USGS NWIS", "url": url, "fetchedAt": fetched, "cached": hit},
            {"name": "NWS / NOAA", "url": "https://api.weather.gov/", "fetchedAt": weather.get("at")},
        ],
        "confidence": 0.95 if sensors else 0.75,
        "note": "Los valores USGS son provisionales cuando el calificador es P. No se declara riesgo de inundación sin umbral oficial.",
    }


# ---------------------------------------------------------------------------
# Radio en vivo
# ---------------------------------------------------------------------------
def radio_catalog(refresh: bool = False) -> dict:
    catalog = load_json("radio_stations.json")

    def probe(station: dict):
        url = station["streamUrl"]
        info = {"available": False, "status": None, "nowPlaying": None, "checkedAt": now_iso()}
        try:
            headers = {"User-Agent": UA, "Icy-MetaData": "1"}
            with requests.get(url, headers=headers, stream=True, timeout=9) as response:
                info["status"] = response.status_code
                content_type = response.headers.get("content-type", "")
                if response.status_code == 200 and ("audio" in content_type or "mpegurl" in content_type or "m3u" in content_type):
                    info["available"] = True
                meta_int = response.headers.get("icy-metaint")
                if meta_int and meta_int.isdigit() and info["available"]:
                    step = int(meta_int)
                    raw = response.raw.read(step + 1 + 255, decode_content=True)
                    if len(raw) >= step + 1:
                        length = raw[step] * 16
                        block = raw[step + 1 : step + 1 + length].decode("utf-8", "replace")
                        match = re.search(r"StreamTitle\s*=\s*'([^']*)'", block)
                        if match:
                            title = re.sub(r"\s+", " ", match.group(1)).strip(" -")
                            info["nowPlaying"] = title or None
                elif info["available"] and station.get("streamKind") == "hls":
                    chunk = response.raw.read(1200, decode_content=True).decode("utf-8", "replace")
                    variants = [line for line in chunk.splitlines() if line.startswith("http")]
                    info["nowPlaying"] = "HLS en vivo" + (f" · {len(variants)} variante(s)" if variants else "")
        except Exception as exc:
            info["status"] = type(exc).__name__
        return station["id"], info

    key = "radio-catalog"
    if refresh:
        with CACHE_LOCK:
            CACHE.pop(key, None)

    def probe_all():
        with ThreadPoolExecutor(max_workers=5) as pool:
            return dict(pool.map(probe, catalog["stations"]))

    payload, hit, fetched = cached(key, 60, probe_all)
    stations = []
    for station in catalog["stations"]:
        item = dict(station)
        status = payload.get(station["id"], {})
        item.update(status)
        item["nowPlaying"] = status.get("nowPlaying") or "Señal en vivo · " + station["name"]
        stations.append(item)
    categories = sorted(
        catalog["categories"],
        key=lambda cat: (cat["id"] != "noticias", cat["name"]),
    )
    return {
        "at": fetched,
        "cached": hit,
        "meta": catalog["meta"],
        "categories": categories,
        "stations": stations,
        "verifiedCount": sum(1 for s in stations if s.get("available")),
        "total": len(stations),
    }


def radio_station(station_id: str) -> dict | None:
    for station in radio_catalog()["stations"]:
        if station["id"] == station_id:
            return station
    return None


# ---------------------------------------------------------------------------
# Herramienta combinada: estado del corredor
# ---------------------------------------------------------------------------
def corridor_status(zone_id: str | None = None, lat: float | None = None, lon: float | None = None) -> dict:
    zone = zone_by_id(zone_id) if zone_id else None
    if zone:
        center = zone["center"]
        lat, lon = center["lat"], center["lon"]
    if lat is None or lon is None:
        raise ValueError("Se requiere zone o lat/lon")

    weather = weather_live(lat, lon)
    sensors = sensors_near(lat, lon)
    events_doc = load_json("nj_events.json")
    nearby_events = []
    for event in events_doc.get("events", []):
        e_lat, e_lon = event.get("latitude"), event.get("longitude")
        if not isinstance(e_lat, (int, float)) or not isinstance(e_lon, (int, float)):
            continue
        distance = haversine(lat, lon, e_lat, e_lon)
        radius = zone.get("radiusKm", 12) if zone else 12
        if distance <= radius:
            nearby_events.append(
                {
                    "id": event.get("eventId"),
                    "category": event.get("categoryName"),
                    "facility": event.get("facility"),
                    "distanceKm": round(distance, 1),
                    "description": re.sub(r"<[^>]+>", " ", event.get("playBackHtml") or "")[:220],
                    "lastUpdate": event.get("lastUpdateDate"),
                }
            )
    nearby_events.sort(key=lambda item: item["distanceKm"])

    severity = weather.get("alerts", [])
    severe_alert = any((a.get("severity") or "").lower() in ("extreme", "severe") for a in severity)
    incident = any((e.get("category") or "").lower() in ("incident", "detour") for e in nearby_events)
    construction = sum(1 for e in nearby_events if (e.get("category") or "").lower() == "construction")
    wind = (weather.get("current", {}).get("windGustKmh") or 0)
    precip = weather.get("current", {}).get("precipitationMm") or 0

    score = 100
    reasons = []
    if severe_alert:
        score -= 35
        reasons.append("Alerta meteorológica NWS de severidad alta")
    elif severity:
        score -= 12
        reasons.append("Aviso meteorológico NWS activo")
    if incident:
        score -= 25
        reasons.append("Incidente/desvío 511NJ en la zona")
    if construction >= 3:
        score -= 12
        reasons.append(f"{construction} eventos de construcción 511NJ en la zona")
    elif construction:
        score -= 5
        reasons.append(f"{construction} evento de construcción 511NJ en la zona")
    if wind >= 45:
        score -= 15
        reasons.append(f"Ráfagas de {wind:.0f} km/h (Open-Meteo)")
    if precip >= 2.5:
        score -= 10
        reasons.append(f"Precipitación de {precip:.1f} mm (Open-Meteo)")
    score = max(0, min(100, score))
    if score >= 80:
        level, label = "green", "Corredor estable"
    elif score >= 55:
        level, label = "amber", "Atención al corredor"
    else:
        level, label = "red", "Corredor afectado"
    if not reasons:
        reasons.append("Sin alertas NWS ni eventos 511NJ críticos en la zona; sensores y clima dentro de lo informado")

    return {
        "at": now_iso(),
        "zone": zone and {"id": zone["id"], "name": zone["name"], "label": zone.get("label")},
        "center": {"lat": lat, "lon": lon},
        "score": score,
        "level": level,
        "label": label,
        "reasons": reasons,
        "weather": {
            "animation": weather.get("current", {}).get("animation"),
            "description": weather.get("current", {}).get("description"),
            "temperatureC": weather.get("current", {}).get("temperatureC"),
            "windGustKmh": weather.get("current", {}).get("windGustKmh"),
            "alerts": weather.get("alerts", []),
        },
        "events": nearby_events[:12],
        "eventCount": len(nearby_events),
        "sensors": (sensors.get("usgs", []) + sensors.get("additional", []))[:10],
        "sources": weather.get("sources", []) + sensors.get("sources", []),
        "confidence": min(weather.get("confidence", 0.7), sensors.get("confidence", 0.7)),
        "method": "Reglas deterministas sobre fuentes oficiales; sin análisis de video ni inferencias encubiertas.",
    }


# ---------------------------------------------------------------------------
# Colector adicional para la experiencia de conducción: servicios en ruta
# ---------------------------------------------------------------------------
def route_services(geometry: list) -> dict:
    """Servicios públicos cerca de una ruta, desde OpenStreetMap (Overpass).

    No son datos oficiales de tráfico: son aportaciones cartográficas de OSM y
    se presentan como ayuda al viaje (repostaje, carga eléctrica, áreas de
    servicio y peajes), con enlace a cada objeto y hora de consulta.
    """
    pts = []
    for p in geometry or []:
        try:
            la, lo = float(p[0]), float(p[1])
        except Exception:
            continue
        if -90 <= la <= 90 and -180 <= lo <= 180:
            pts.append((la, lo))
    if len(pts) < 2:
        return {"ok": False, "error": "La ruta necesita al menos dos puntos."}

    # Varias cajas pequeñas a lo largo del trayecto: una sola caja que cubre
    # toda la ruta puede abarcar áreas metropolitanas enteras y agotar Overpass.
    boxes = []
    step = max(1, len(pts) // 5)
    for i in range(0, len(pts), step):
        la, lo = pts[i]
        pad = 0.035
        boxes.append("%.4f,%.4f,%.4f,%.4f" % (la - pad, lo - pad, la + pad, lo + pad))
        if len(boxes) >= 6:
            break
    items = []
    for b in boxes:
        items.extend([
            "nwr[amenity=fuel](%s)" % b,
            "nwr[amenity=charging_station](%s)" % b,
            "nwr[highway=services](%s)" % b,
            "nwr[barrier=toll_booth](%s)" % b,
        ])
    query = "[out:json][timeout:25];(" + ";".join(items) + ";);out center 40;"
    import urllib.parse
    encoded = urllib.parse.quote(query)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    mirrors = [
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    data = hit = fetched = None
    last_error = None
    for mirror in mirrors:
        try:
            data, hit, fetched = http_json(
                mirror + "?data=" + encoded, ttl=900.0, headers=headers, timeout=25,
            )
            break
        except Exception as exc:
            last_error = exc
    if data is None:
        raise last_error or RuntimeError("No hay un servidor Overpass disponible.")
    kinds = {
        "fuel": "Repostaje", "charging_station": "Carga eléctrica",
        "services": "Área de servicio", "toll_booth": "Peaje",
    }
    out = []
    seen = set()
    for e in (data or {}).get("elements") or []:
        tags = e.get("tags") or {}
        center = e.get("center") or {}
        lat = e.get("lat") if e.get("lat") is not None else center.get("lat")
        lon = e.get("lon") if e.get("lon") is not None else center.get("lon")
        kind = tags.get("amenity") or tags.get("highway") or tags.get("barrier")
        identity = "%s/%s" % (e.get("type") or "node", e.get("id"))
        if lat is None or lon is None or kind not in kinds or identity in seen:
            continue
        seen.add(identity)
        out.append({
            "id": identity,
            "lat": float(lat), "lon": float(lon),
            "kind": kind, "label": kinds[kind],
            "name": tags.get("name") or kinds[kind],
            "brand": tags.get("brand") or tags.get("operator") or "",
            "url": "https://www.openstreetmap.org/%s/%s" % (e.get("type") or "node", e.get("id")),
        })
    out.sort(key=lambda x: (x["label"], x["name"]))
    return {
        "ok": True, "at": fetched, "count": len(out), "services": out[:60],
        "cached": hit,
        "source": {"name": "OpenStreetMap / Overpass", "url": "https://overpass-api.de/",
                   "fetchedAt": fetched},
        "note": "Servicios cartográficos de OpenStreetMap, no un aviso oficial de la agencia vial.",
    }


# ---------------------------------------------------------------------------
# Radar meteorológico (RainViewer): capa raster sobre el mapa de conducción
# ---------------------------------------------------------------------------
RAINVIEWER_URL = "https://api.rainviewer.com/public/weather-maps.json"


def rain_radar() -> dict:
    """Últimos fotogramas de radar real, con plantilla de tesela y atribución.

    RainViewer es gratuito sin clave para uso personal/educativo. Exige citar la
    fuente con enlace; por eso la respuesta incluye `attribution`. No se guarda
    nada: solo se cachea en memoria 5 minutos para no abusar del servicio.
    """
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data, hit, fetched = http_json(RAINVIEWER_URL, ttl=300.0, headers=headers, timeout=15)
    radar = data.get("radar") or {}
    host = str(data.get("host") or "").rstrip("/")
    frames = []
    for group in ("past", "nowcast"):
        group_frames = radar.get(group) or []
        for frame in group_frames[-8:]:
            if not isinstance(frame, dict) or not frame.get("path"):
                continue
            stamp = frame.get("time")
            at = None
            if isinstance(stamp, (int, float)):
                try:
                    at = datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds")
                except (ValueError, OSError, OverflowError):
                    at = None
            frames.append({
                "kind": group,
                "time": stamp,
                "path": frame["path"],
                # Esquema 2 (Universal Blue), nieve=1, suavizado=1.
                "url": "%s%s/256/{z}/{x}/{y}/2/1_1.png" % (host, frame["path"]),
                "at": at,
                "label": "Ahora" if group == "nowcast" else (at or "Radar"),
            })
    return {
        "ok": bool(frames), "at": fetched, "cached": hit,
        "generated": data.get("generated"), "host": host,
        "count": len(frames), "frames": frames[-10:],
        "attribution": "Weather data by RainViewer",
        "attributionUrl": "https://www.rainviewer.com/",
        "source": {"name": "RainViewer Weather Maps", "url": "https://www.rainviewer.com/api.html",
                   "fetchedAt": fetched},
        "note": "Radar meteorológico real. Sin SLA: puede faltar cobertura en algunos países.",
    }


# ---------------------------------------------------------------------------
# Satélite (NASA GIBS / NOAA GOES-East): capa raster verificable sin clave
# ---------------------------------------------------------------------------
GIBS_LAYER = "GOES-East_ABI_Air_Mass"
GIBS_TMS = "GoogleMapsCompatible_Level6"
GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/" + GIBS_LAYER + "/default"
# La petición filtrada por capa devuelve ~33 KB en lugar de los ~6 MB del
# capabilities completo. Es la fuente de la hora exacta de la escena.
GIBS_CAPABILITIES = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
    "?SERVICE=WMTS&REQUEST=GetCapabilities&VERSION=1.0.0&LAYER=" + GIBS_LAYER
)


def _mercator_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Fila/columna Web Mercator para una muestra sobre Nueva Jersey."""
    count = 2 ** zoom
    x = (lon + 180.0) / 360.0 * count
    clamped = max(-85.05112878, min(85.05112878, lat))
    y = (1.0 - math.asinh(math.tan(math.radians(clamped))) / math.pi) / 2.0 * count
    return int(max(0, min(count - 1, x))), int(max(0, min(count - 1, y)))


def satellite_goes() -> dict:
    """Masa de aire observada por GOES-East vía NASA GIBS, sin clave API.

    La hora no se calcula: GIBS devuelve la hora exacta de la escena en la
    cabecera `Layer-Time-Actual` de una tesela real sobre Somerville (NJ), con
    el `Default` del capabilities como respaldo. Se usa la plantilla sin hora
    (`/default/{TileMatrixSet}/...`) para que el mapa muestre siempre la última
    escena publicada. Cualquier respuesta incluye fuente, hora de la escena,
    hora de consulta y atribución. Es una observación, nunca una predicción.
    """
    def producer():
        headers = {"User-Agent": UA, "Accept": "text/xml,application/xml;q=0.9"}
        response = requests.get(GIBS_CAPABILITIES, headers=headers, timeout=(5, 15))
        response.raise_for_status()
        xml = response.text
        start = xml.find("<ows:Identifier>" + GIBS_LAYER + "</ows:Identifier>")
        if start < 0:
            raise RuntimeError("GIBS no publica la capa GOES-East solicitada")
        block = xml[start:start + 20000]
        found_time = re.search(r"<Default>([^<]+)</Default>", block)
        found_tms = re.search(r"<TileMatrixSet>([^<]+)</TileMatrixSet>", block)
        found_format = re.search(r"<Format>image/([^<]+)</Format>", block)
        if not found_time:
            raise RuntimeError("GIBS no informó la hora de la observación")
        default_time = found_time.group(1).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", default_time):
            raise RuntimeError("Formato de hora GIBS inesperado")
        tms = found_tms.group(1).strip() if found_tms else GIBS_TMS
        extension = found_format.group(1).strip() if found_format else "png"
        level = re.search(r"GoogleMapsCompatible_Level(\d+)", tms)
        maxzoom = min(8, max(0, int(level.group(1)))) if level else 6
        # GIBS usa {TileMatrix}/{TileRow}/{TileCol}; MapLibre sustituye
        # {z}/{y}/{x}. El orden de fila/columna se conserva. La variante sin
        # hora sirve siempre la última escena y evita caches 404 de GIBS.
        tile = "%s/%s/{z}/{y}/{x}.%s" % (GIBS_BASE, tms, extension)
        sample_zoom = min(5, maxzoom)
        col, row = _mercator_tile(40.6209, -74.6085, sample_zoom)
        sample = "%s/%s/%d/%d/%d.%s" % (
            GIBS_BASE, tms, sample_zoom, row, col, extension)
        checked = {"status": None, "contentType": None, "time": None}
        probe = requests.get(sample, headers={"User-Agent": UA, "Range": "bytes=0-1023"},
                             timeout=(5, 15), stream=True)
        try:
            checked = {"status": probe.status_code,
                       "contentType": probe.headers.get("Content-Type", ""),
                       "time": probe.headers.get("Layer-Time-Actual")}
        finally:
            probe.close()
        if checked["status"] >= 400 or "image/" not in checked["contentType"]:
            raise RuntimeError("La tesela de muestra de GIBS no es una imagen válida")
        observed = checked["time"] or default_time
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", observed):
            observed = default_time
        return {
            "ok": True,
            "layer": GIBS_LAYER,
            "title": "Masa de aire (ABI, GOES-East)",
            "time": observed,
            "timeLabel": observed.replace("T", " ").replace("Z", " UTC"),
            "tileMatrixSet": tms,
            "maxzoom": maxzoom,
            "tileSize": 256,
            "tiles": [tile],
            "attribution": "NASA GIBS · NOAA GOES-East",
            "attributionUrl": "https://gibs.earthdata.nasa.gov/",
            "source": {
                "name": "NASA GIBS (GOES-East / ABI)",
                "url": "https://gibs.earthdata.nasa.gov/",
                "capabilities": GIBS_CAPABILITIES,
                "sampleTile": sample,
            },
            "sample": checked,
            "note": ("Observación satelital real, no una predicción. GOES-East publica "
                     "escenas nuevas aproximadamente cada 10 minutos; se muestra la hora "
                     "exacta y se atribuye a NASA GIBS / NOAA."),
        }

    value, hit, fetched = cached("gibs:goes-air-mass", 600.0, producer)
    result = dict(value)
    result["cached"] = hit
    result["fetchedAt"] = fetched
    result["source"] = dict(result.get("source") or {})
    result["source"]["fetchedAt"] = fetched
    return result


# ---------------------------------------------------------------------------
# Hechos viales de OpenStreetMap: cámaras de velocidad y límites
# ---------------------------------------------------------------------------
def _distance_to_route_km(lat: float, lon: float, pts: list) -> float:
    """Distancia mínima al trazado, con proyección local en metros.

    Las rutas son locales; la aproximación equirectangular es suficiente y
    permite ordenar los objetos por cercanía real en lugar de por el orden
    arbitrario en que Overpass devuelve las cajas.
    """
    k = 111320.0
    cos_lat = math.cos(math.radians(lat))
    x, y = lon * k * cos_lat, lat * k
    best = float("inf")
    for i in range(len(pts) - 1):
        a_lat, a_lon = pts[i]
        b_lat, b_lon = pts[i + 1]
        ax, ay = a_lon * k * cos_lat, a_lat * k
        bx, by = b_lon * k * cos_lat, b_lat * k
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        t = 0.0 if den == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / den))
        best = min(best, math.hypot(x - (ax + t * dx), y - (ay + t * dy)))
    return best / 1000.0


def route_roadfacts(geometry: list) -> dict:
    """Cámaras de velocidad y límites de OSM cerca de la ruta.

    Es cartografía colaborativa, no señalización oficial: se muestra con su
    enlace a OSM y una nota explícita para no presentarla como dato de la agencia
    vial. Reutiliza el patrón de cajas pequeñas de `route_services`, amplía el
    resultado de Overpass y ordena por distancia real al trazado (máximo 2 km)
    para que los objetos cercanos no queden fuera por el límite de salida.
    """
    pts = []
    for p in geometry or []:
        try:
            la, lo = float(p[0]), float(p[1])
        except Exception:
            continue
        if -90 <= la <= 90 and -180 <= lo <= 180:
            pts.append((la, lo))
    if len(pts) < 2:
        return {"ok": False, "error": "La ruta necesita al menos dos puntos."}

    boxes = []
    step = max(1, len(pts) // 5)
    for i in range(0, len(pts), step):
        la, lo = pts[i]
        pad = 0.035
        boxes.append("%.4f,%.4f,%.4f,%.4f" % (la - pad, lo - pad, la + pad, lo + pad))
        if len(boxes) >= 6:
            break
    clauses = []
    for b in boxes:
        clauses.extend(("nwr[highway=speed_camera](%s)" % b, "nwr[maxspeed](%s)" % b))
    query = "[out:json][timeout:25];(" + ";".join(clauses) + ";);out center 300;"
    import urllib.parse
    encoded = urllib.parse.quote(query)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    # Kumi suele agotar el tiempo de espera; se prueban los dos espejos que
    # históricamente responden para no triplicar la espera del contexto vial.
    mirrors = [
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    ]
    data = hit = fetched = None
    last_error = None
    for mirror in mirrors:
        try:
            # Overpass puede tardar ~40 s en horas punta; este contexto es
            # asíncrono y opcional, así que esperamos antes de degradar.
            data, hit, fetched = http_json(
                mirror + "?data=" + encoded, ttl=900.0, headers=headers, timeout=60,
            )
            break
        except Exception as exc:
            last_error = exc
    if data is None:
        raise last_error or RuntimeError("No hay un servidor Overpass disponible.")

    out = []
    seen = set()
    for e in (data or {}).get("elements") or []:
        tags = e.get("tags") or {}
        center = e.get("center") or {}
        lat = e.get("lat") if e.get("lat") is not None else center.get("lat")
        lon = e.get("lon") if e.get("lon") is not None else center.get("lon")
        camera = tags.get("highway") == "speed_camera"
        limit = tags.get("maxspeed")
        if lat is None or lon is None or (not camera and not limit):
            continue
        identity = "%s/%s" % (e.get("type") or "node", e.get("id"))
        if identity in seen:
            continue
        seen.add(identity)
        distance = _distance_to_route_km(float(lat), float(lon), pts)
        if distance > 2.0:
            continue
        out.append({
            "id": identity,
            "lat": float(lat), "lon": float(lon),
            "kind": "speed_camera" if camera else "maxspeed",
            "limit": str(limit) if limit else "",
            "name": tags.get("name") or ("Cámara de velocidad" if camera else "Límite de velocidad"),
            "url": "https://www.openstreetmap.org/%s/%s" % (e.get("type") or "node", e.get("id")),
            "distanceKm": round(distance, 3),
        })
    out.sort(key=lambda x: x["distanceKm"])
    return {
        "ok": True, "at": fetched, "cached": hit, "count": len(out),
        "cameras": sum(1 for x in out if x["kind"] == "speed_camera"),
        "limits": sum(1 for x in out if x["kind"] == "maxspeed"),
        "items": out[:80],
        "source": {"name": "OpenStreetMap / Overpass", "url": "https://overpass-api.de/",
                   "fetchedAt": fetched},
        "note": "Datos cartográficos de OpenStreetMap; no sustituyen la señalización oficial.",
    }


# ---------------------------------------------------------------------------
# Contexto costero: NOAA CO-OPS + NHC, solo cuando aplica
# ---------------------------------------------------------------------------
COOPS_STATIONS = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
COOPS_DATA = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NHC_STORMS = "https://www.nhc.noaa.gov/CurrentStorms.json"


def _coops_latest(station_id: str, product: str) -> dict | None:
    params = urllib.parse.urlencode({
        "date": "latest", "station": station_id, "product": product,
        "datum": "MLLW", "time_zone": "gmt", "units": "metric", "format": "json",
    })
    try:
        data, _, fetched = http_json(COOPS_DATA + "?" + params, ttl=300.0,
                                     headers={"User-Agent": UA, "Accept": "application/json"},
                                     timeout=12)
    except Exception:
        return None
    row = ((data or {}).get("data") or [{}])[0]
    if not row or row.get("v") in (None, ""):
        return None
    try:
        value = float(row["v"])
    except (TypeError, ValueError):
        return None
    return {"valueM": value, "at": row.get("t"), "sigma": row.get("s"),
            "flags": row.get("f", ""), "fetchedAt": fetched}


def coastal_context(lat: float, lon: float) -> dict:
    """Estación CO-OPS más cercana y tormentas oficiales activas del NHC.

    Solo se informa de mediciones reales: si el producto no está disponible en
    la estación, se omite. Nunca se calcula un nivel "de riesgo" inventado.
    """
    headers = {"User-Agent": UA, "Accept": "application/json"}
    stations, hit, fetched = http_json(COOPS_STATIONS, ttl=86400.0,
                                       headers=headers, timeout=25)
    candidates = []
    for s in (stations or {}).get("stations") or []:
        try:
            sla, slo = float(s.get("lat")), float(s.get("lng"))
        except (TypeError, ValueError):
            continue
        candidates.append((haversine(lat, lon, sla, slo), s))
    candidates.sort(key=lambda x: x[0])
    result = {"ok": True, "at": fetched, "cached": hit, "station": None,
              "waterLevel": None, "airGap": None, "storms": [],
              "source": {"name": "NOAA CO-OPS / NHC", "url": "https://tidesandcurrents.noaa.gov/",
                         "fetchedAt": fetched},
              "note": "Mediciones oficiales de estación; sin umbrales de riesgo calculados."}
    if not candidates:
        return result
    distance, station = candidates[0]
    sid = str(station.get("id") or "")
    if not sid:
        return result
    result["station"] = {
        "id": sid, "name": station.get("name") or sid,
        "lat": float(station.get("lat")), "lon": float(station.get("lng")),
        "distanceKm": round(distance, 1),
        "url": "https://tidesandcurrents.noaa.gov/waterlevels.html?id=" + sid,
        "near": distance <= 150,
    }
    if distance <= 150:
        result["waterLevel"] = _coops_latest(sid, "water_level")
        result["airGap"] = _coops_latest(sid, "air_gap")
    try:
        nhc, _, nhc_at = http_json(NHC_STORMS, ttl=600.0, headers=headers, timeout=12)
        for storm in (nhc or {}).get("activeStorms") or []:
            if not isinstance(storm, dict):
                continue
            try:
                sla, slo = float(storm.get("lat")), float(storm.get("lon"))
            except (TypeError, ValueError):
                sla = slo = None
            near = None
            if sla is not None and slo is not None:
                near = round(haversine(lat, lon, sla, slo), 1)
                if near > 500:
                    continue
            result["storms"].append({
                "name": storm.get("name") or "Tormenta activa",
                "classification": storm.get("classification") or "",
                "advisory": storm.get("advisory") or "",
                "url": storm.get("url") or "https://www.nhc.noaa.gov/",
                "distanceKm": near, "lat": sla, "lon": slo, "at": nhc_at,
            })
    except Exception:
        pass
    return result
