# HorizonView — Architecture

Companion to [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md). This document focuses on the runtime flow and how the pieces connect.

---

## 1. Process view

```
start*.bat / start*.ps1
        │
        ▼
src/server.py  ──►  data/*.json        (inventories, tours, events, zones, radio)
        │
        ├──► /api/*                    (REST, explainable AI, proxy, refresh jobs)
        ├──► /assets/*                 (MapLibre, Leaflet, HLS.js, logos, QR)
        ├──► /styles.css               (root static route)
        └──► /src/app.js               (root static route)
                    │
                    ▼
            index.html  ──►  Driving UI (MapLibre)
                        └─►  Admin UI   (Leaflet, 8 tabs)
```

## 2. Request flow

1. The browser loads `/index.html`.
2. `styles.css`, local map libraries, HLS.js and `src/app.js` load in that order.
3. `src/app.js` calls `/api/health` and `/api/cameras` to populate the inventory.
4. Driving mode calls `/api/geocode`, `/api/reverse` and OSRM `/route`; road facts, radar and coastal context come from `/api/roadfacts`, `/api/radar` and `/api/coastal`.
5. Camera video is fetched through `/api/hls/<id>/<url>` so the required `Referer` is preserved and CORS is not an issue. Radio uses `/api/radio/stream/<id>/<url>` with an HTTPS host allow-list.
6. `/api/nearby` verifies playlists and real video bytes before showing local cameras; real playback failures are reported to `/api/stream-report` and hidden for 6 hours.

## 3. Module boundaries

| Module | Responsibility | Must not do |
|---|---|---|
| `src/server.py` | HTTP routing, caches, proxy, refresh jobs | Invent data or bypass source provenance |
| `src/ai.py` | Deterministic rules and explanations | Call an LLM, analyze images or invent incidents |
| `src/extras.py` | External public context (weather, sensors, radio, radar, road, coast) | Present observations as predictions |
| `src/app.js` | Rendering, state, GPS, maps, media | Store personal data outside the device |

## 4. Caching and concurrency

Caches are in-memory dictionaries guarded by locks in the server and extras modules. Timeouts:

| Data | TTL |
|---|---|
| Weather / alerts | 10 min |
| Geocoding / reverse | 24 h |
| Overpass road facts and services | 15 min |
| RainViewer radar | 5 min |
| CO-OPS stations | 24 h |

Refresh jobs run in a background thread and expose progress through `/api/refresh/status`.

## 5. External sources

- **Inventories:** 511NJ (`getTourList`, `getCameraDataByTourId`, `getCameraDetail`) and DelDOT.
- **Membership and events:** captured with Chrome CDP because 511NJ signs and encrypts requests in the browser.
- **Weather / alerts / radio frequency:** Open‑Meteo and NWS/NOAA.
- **Sensors:** USGS and NOAA.
- **Routing / places:** OSRM and Nominatim.
- **Maps:** CARTO vector styles through local MapLibre; CARTO raster tiles through local Leaflet.
- **Road facts / services:** OpenStreetMap via Overpass mirrors.
- **Weather radar:** RainViewer.
- **Coastal:** NOAA CO-OPS and NHC.

## 6. Failure modes

- No map tiles: the map is blank but the rest of the app works.
- Expired `otp`: the comparator replaces the camera with a verified neighbor and reports it.
- Overpass timeout: `/api/roadfacts` answers `200` with `ok:false`; the driving map keeps working without that layer.
- Stream failure: camera hidden for 6 hours after a real playback error.
- Tunnel restart: Cloudflare URL changes; Tailscale Funnel URL stays fixed.

## 7. Extension points

- Add a new public source in `src/extras.py` with a cache, a source label and a visible timestamp.
- Add a new explainable rule in `src/ai.py` with `source`, `time` and `confidence` fields.
- Add a new tab in `index.html` plus its renderer in `src/app.js`, keeping the mobile geometry checks green.
- Add a verifier in `tests/` importing `CHROME`, `BASE`, `CDP` from `verify_mobile.py`.
