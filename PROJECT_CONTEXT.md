# Project Technical Context — HorizonView (v1.0.0)

This document is the technical orientation for maintainers. It describes the runtime architecture, API surface, configuration, data sources and the non-obvious constraints of the project.

---

## 1. Runtime & architecture

- **Backend:** Python 3 standard library (`http.server`) plus `requests`. No framework, no database, no build step.
- **Frontend:** vanilla HTML5, CSS3 and ES2020 JavaScript. No bundler, no framework, no package dependencies.
- **Entry point:** `src/server.py`, launched by any `start*.bat` / `start*.ps1` from the repository root.
- **Root resolution:** `src/server.py` uses `ROOT = pathlib.Path(__file__).resolve().parents[1]` so all data, assets and static files are resolved from the repository root regardless of the launcher's working directory.
- **Modules:**
  - `src/server.py` — HTTP server, REST API, HLS/radio proxy and refresh jobs.
  - `src/ai.py` — deterministic, explainable rules over public data. No LLM, no image analysis.
  - `src/extras.py` — zones, weather, sensors, radio, RainViewer radar, OSM road facts and NOAA coastal context.
  - `src/app.js` — driving experience and eight-tab administration UI.
- **Maps:** MapLibre GL JS 5.6.0 (driving) and Leaflet (administration), both served locally from `assets/` with visible attribution. No API key.

## 2. Static routes and load order

`index.html` must keep this load order:

1. `styles.css`
2. `assets/leaflet.css`, `assets/maplibre-gl.css`
3. `assets/hls.min.js`, `assets/leaflet.js`, `assets/maplibre-gl.js`
4. `src/app.js`

The server serves static files with these exact routes:

| Route | File |
|---|---|
| `/`, `/index.html` | `index.html` |
| `/styles.css` | `styles.css` |
| `/src/app.js` | `src/app.js` |
| `/assets/<name>` | `assets/<name>` (single path segment only) |

Do not move `styles.css` or `src/app.js` without updating `src/server.py` and `index.html` together — the original layout served them from `assets/` and produced 404s after the v1.0 restructure until explicit routes were added.

## 3. Configuration

All configuration is environment-based; no `.env` file is required.

| Variable | Purpose | Default |
|---|---|---|
| `HV_PORT` | HTTP listen port | `8770` |
| `HV_API` | Base URL used by HTTP verification scripts | `http://127.0.0.1:8770` |
| `HV_BASE` | Base URL used by CDP/browser verification scripts | `URL_Movil.txt` |
| `HV_QR_URL` / `HV_QR_OUT` | URL and output path for the local QR generator | set by launcher |
| `HV_QR_URL` | Complements the old `CAML_*` names from v1.x | — |

Old `CAML_*` names were fully renamed to `HV_*` in v1.0. The original `CamLocatorNJTP` installation and its live tunnel were left untouched.

## 4. API surface

`/api/*` routes are intentionally stable for backward compatibility with existing verifiers and links. They include health, cameras, source metadata, tours, events, zones, geocoding/reverse, weather live/alerts, sensors, radar, coastal, road facts, radio stations/metadata/stream proxy, the explainable AI endpoints, nearby camera verification, stream reports, refresh jobs and the HLS proxy.

The HLS/radio proxy exists because 511NJ streams require `Referer: https://511nj.org/` and do not send CORS headers. It rewrites master playlists, segments, `EXT-X-KEY`, `EXT-X-MAP` (fMP4 `init.mp4`) and LL-HLS partial segments while preserving the `otp` token. Radio streams are accepted only from verified HTTPS hosts.

## 5. Data model

All inventories live in `data/` as JSON and are loaded into memory with thread-safe caches:

- `nj_cameras.json`, `de_cameras.json` — normalized official inventories.
- `nj_raw_inventory.json` — raw 511NJ response with provenance.
- `nj_tours.json` — 85 official tours and camera membership.
- `nj_events.json` — point-in-time capture of 404 official 511NJ events (131 in NJ/DE).
- `local_zones.json` — local overlay with official camera IDs (does not modify the source inventories).
- `radio_stations.json` — 5 verified stations, streams, logos and categories.
- `ai_signals.json`, `stream_failures.json` — local, anonymous reliability history.

**Non-obvious constraint:** 511NJ signs each request with WebCrypto (`X-Browser-Proof`, single use) and encrypts the body with AES-128-CBC. It cannot be replicated with `requests`; `scripts/nj_tours_capture.py` and `scripts/nj_events_capture.py` let the real page sign the request and read/intercept it through Chrome CDP.

## 6. Sources and limits

Sources are free and require no API key: 511NJ, DelDOT, NWS/NOAA, USGS, Open‑Meteo, public radio stations, OSRM, Nominatim, OpenStreetMap/Overpass, CARTO, RainViewer and NOAA CO-OPS/NHC.

Caches: 10 min weather/alerts, 24 h geocoding, 15 min Overpass, 5 min radar, 24 h CO-OPS stations. Overpass waits up to 60 s because peak responses take ~40 s. `overpass.kumi.systems` was removed after repeated timeouts; `overpass.openstreetmap.fr` is primary and `overpass-api.de` is fallback. Nominatim requires a `User-Agent`, already included.

## 7. Verification model

- `tests/verify_*` scripts are standalone and import `CHROME`, `BASE`, `CDP` and `PORT` from `verify_mobile.py`.
- `verify_ai.py` and `verify_extras.py` use `HV_API`; browser tests use `HV_BASE`.
- Tests can run against a separate copy on port 8771 without stopping the original instance on 8770.
- `tests/verify_drive.py` and `tests/verify_drive_interactions.py` check the Waze-style experience, MapLibre layers and toggles.

## 8. Constraints that must not change

- No cameras, coordinates, incidents, sensors, frequencies or PTZ controls are invented.
- Zoom is digital because the public feeds expose no remote PTZ control.
- `maxspeed` values come from OpenStreetMap and are never presented as official signage.
- Radar and coastal data are observations with their own timestamps, never app predictions.
- Radio is played directly from each station; it is never redistributed or recorded.
- Favorites and reliability history stay on the device: no accounts, ads or tracking.
