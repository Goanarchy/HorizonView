"""Verificación de extremo a extremo de la etapa 3 (IA explicable y Tours)."""
import json
import os
import sys
import time

import requests

BASE = os.environ.get("HV_API", "http://127.0.0.1:8770")
UA = {"User-Agent": "HorizonView-verify/3.0"}
FAILURES = []
PASSED = []


def check(name, cond, detail=""):
    (PASSED if cond else FAILURES).append(name)
    print(("  OK  " if cond else " FAIL ") + name + ((" · " + str(detail)[:240]) if detail else ""))


def get(path, timeout=90):
    r = requests.get(BASE + path, headers=UA, timeout=timeout)
    return r.status_code, r.json()


def post(path, body, timeout=90):
    r = requests.post(BASE + path, headers={**UA, "Content-Type": "application/json"},
                      json=body, timeout=timeout)
    return r.status_code, r.json()


def traceable(j):
    return bool(j.get("sources") or j.get("source")) and bool(j.get("at") or j.get("source"))


def no_invention(j):
    text = json.dumps(j, ensure_ascii=False).lower()
    return not any(k in text for k in ("ptz", "pan/tilt", "zoom remoto", "control remoto"))


def main():
    print("HorizonView · verificación etapa 3 ·", time.strftime("%Y-%m-%d %H:%M:%S"))
    code, health = get("/api/health", 20)
    check("GET /api/health", code == 200 and health.get("ok"), health.get("cameras"))
    check("inventario completo", health.get("cameras") == 1051, health.get("cameras"))

    code, inv = get("/api/cameras", 30)
    cams = inv.get("cameras") or []
    check("GET /api/cameras", code == 200 and len(cams) >= 1000, len(cams))
    check("radar de confianza en cada cámara",
          all(isinstance(c.get("trust"), int) and c.get("trustLabel") and
              isinstance(c.get("trustReasons"), list) for c in cams))
    check("sin controles PTZ inventados", no_invention(inv))

    code, ev = get("/api/events", 20)
    njde = [e for e in ((ev.get("events") or []) if "events" in ev else [])]
    check("GET /api/events", code == 200 and ev.get("ok") and ev.get("count", 0) >= 100,
          "%s eventos NJ/DE" % ev.get("count"))
    check("eventos con categoría real", bool(ev.get("byCategory")), ev.get("byCategory"))
    check("feed 511NJ trazable", traceable(ev))

    code, st = get("/api/ai/stats", 20)
    check("GET /api/ai/stats", code == 200 and st.get("ok") and "rate" in st,
          "%s OK / %s fallos" % (st.get("successes"), st.get("failures")))

    code, geo = get("/api/geocode?q=Newark%2C%20NJ", 45)
    place = geo.get("place") or {}
    check("GET /api/geocode", code == 200 and geo.get("ok") and abs(place.get("lat", 0) - 40.7) < 1,
          place.get("name", "")[:70])

    code, q = post("/api/ai/query", {"q": "cámaras con video cerca de Newark NJ", "favs": []}, 120)
    check("POST /api/ai/query", code == 200 and q.get("ok") and q.get("count", 0) > 0,
          "%s resultados" % q.get("count"))
    check("asistente explicable", bool(q.get("interpretation")) and traceable(q) and
          all(k in q for k in ("confidence", "note")))
    check("asistente sin invenciones", no_invention(q))

    code, qt = post("/api/ai/query", {"q": "cámaras en el tour NJ Turnpike Tour", "favs": []}, 40)
    check("asistente reconoce tours reales", code == 200 and qt.get("ok") and
          qt.get("count", 0) > 100 and any("tour" in x.lower() for x in qt.get("interpretation") or []),
          "%s resultados" % qt.get("count"))

    code, r = post("/api/ai/route", {"from": "Newark, NJ", "to": "Trenton, NJ",
                                     "bufferKm": 5, "limit": 12}, 120)
    check("POST /api/ai/route", code == 200 and r.get("ok") and r.get("distanceKm", 0) > 20,
          "%s km · %s cámaras" % (r.get("distanceKm"), len(r.get("cameras") or [])))
    check("ruta con geometría real y cámaras", len(r.get("geometry") or []) > 4 and
          all("offRouteKm" in c and "atKm" in c for c in (r.get("cameras") or [])))
    check("ruta trazable", traceable(r) and bool(r.get("explanation")))

    fav_ids = [c["id"] for c in cams[:3]]
    code, b = post("/api/ai/brief", {"favs": fav_ids, "geo": {"lat": 40.74, "lon": -74.17}}, 120)
    check("POST /api/ai/brief", code == 200 and b.get("ok") and b.get("headline") and
          len(b.get("bullets") or []) >= 2, b.get("basis"))
    check("resumen trazable", traceable(b) and all(x.get("confidence") for x in b.get("bullets") or []))

    code, a = post("/api/ai/alerts", {"state": "NJ,DE"}, 120)
    check("POST /api/ai/alerts", code == 200 and a.get("ok") and traceable(a),
          "%s señales" % len(a.get("alerts") or []))
    check("alertas con evidencia", all(x.get("text") and x.get("evidence") and x.get("source")
                                        for x in (a.get("alerts") or [])[:5]))

    code, g = post("/api/ai/groups", {"favs": fav_ids}, 30)
    check("POST /api/ai/groups", code == 200 and g.get("ok") and len(g.get("groups") or []) >= 2,
          [x.get("title") for x in g.get("groups") or []])

    first = cams[0]
    code, cx = post("/api/ai/context", {"id": first["id"], "geo": {"lat": first["lat"],
                                                                     "lon": first["lon"]}}, 120)
    check("POST /api/ai/context", code == 200 and cx.get("ok") and len(cx.get("lines") or []) >= 3,
          len(cx.get("events") or []))
    check("contexto trazable", traceable(cx) and "events" in cx and "neighbors" in cx)

    code, tm = get("/api/tours", 20)
    tours = sorted((tm.get("tours") or []), key=lambda t: t.get("cameras", 0), reverse=True)
    tour = next((t.get("name") for t in tours if t.get("cameras", 0) > 100), None)
    code, tn = post("/api/ai/tour", {"tour": tour}, 30)
    check("POST /api/ai/tour", code == 200 and tn.get("ok") and len(tn.get("steps") or []) >= 5,
          "%s · %s pasos" % (tn.get("tour"), len(tn.get("steps") or [])))
    check("tour narrado sin inventarios falsos", traceable(tn) and
          all(s.get("id") and s.get("lat") is not None for s in tn.get("steps") or []))

    ids = [c["id"] for c in cams[:2] if c.get("stream")]
    ids += [c["id"] for c in cams if c.get("stream") and c["id"] not in ids][:2]
    code, cm = post("/api/ai/compare", {"ids": ids[:4]}, 30)
    check("POST /api/ai/compare", code == 200 and cm.get("ok") and len(cm.get("cameras") or []) >= 2,
          cm.get("recommendation"))
    check("comparador con distancias reales", bool(cm.get("pairs")) and traceable(cm))

    code, lay = get("/api/ai/layers?lat=%.4f&lon=%.4f&infra=0" % (first["lat"], first["lon"]), 120)
    check("GET /api/ai/layers", code == 200 and lay.get("ok") and traceable(lay),
          "%s capas" % len(lay.get("layers") or []))
    check("capas sin invenciones", no_invention(lay))

    print("\nRESULTADO: %s correctas, %s fallidas" % (len(PASSED), len(FAILURES)))
    if FAILURES:
        print("FALLIDAS: " + ", ".join(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
