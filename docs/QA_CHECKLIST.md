# HorizonView — QA Checklist (v1.0.0)

Results below were obtained on 19 November 2026 against a copy of the project served on the alternate port `8771`, with the original installation and its tunnel left untouched.

---

## 1. Static checks

| Check | Command | Result |
|---|---|---|
| Python syntax | `python -m py_compile src/server.py src/ai.py src/extras.py scripts/*.py tests/*.py` | `PY_OK` |
| JavaScript syntax | `node --check src/app.js` | `JS_OK` |
| Health | `GET /api/health` | 1051 cameras, 1042 streams |
| Static routes | `/`, `/styles.css`, `/src/app.js`, `/assets/*` | 200 |

## 2. HTTP verification

| Script | Result |
|---|---|
| `tests/verify_extras.py` | health 200; cameras 1032 visible / 11 zoned; zones 10/6/7/5; weather `clear-day` 14 °C, NWR `KWO35/162.55`; sensors 30+2; radio 5/5; corridor `amber 75`; **radar `frames=8`**; **roadfacts `count=15`**; **coastal The Battery `water=1.296`** |
| `tests/verify_ai.py` | **30 correctas, 0 fallidas**; tours, route, alerts, groups, context, comparison and layers all traceable |

## 3. Browser / CDP verification (390×844)

| Script | Result |
|---|---|
| `tests/audit_ui.py` | **0 incidencias**, `scroll=390`, `fuera=[]`, `recortados=0`, `HTTP_ERRORES=[]`, `ERRORES=[]` |
| `tests/verify_map.py` | 86 tour options, filter `665 / 1032`, 9 tiles, 0 errors |
| `tests/verify_stage1.py` | favorite saved and persistent, filter `1 / 1032`, two-tap report OK |
| `tests/verify_mobile.py` | GPS 164 verified ±5 m, 10 nearest, `readyState=4`, `videoWidth=853`, 0 errors |
| `tests/verify_drive.py` | onboarding, setup, route, HUD, chips, spotlight, log and admin OK; `zoom=15.6`, `roadCount=194`, `radarCount=8`, `SPOTLIGHT_VISTO True`, `ERRORES []`, `HTTP []` |
| `tests/verify_drive_interactions.py` | radar/road/coastal toggles, overview/recenter and day/night style switch OK |

## 4. Manual acceptance criteria

- [x] Public HTTPS link works on Android and iPhone without installing certificates.
- [x] GPS works only on the device and is never uploaded.
- [x] Camera inventory comes from official sources with visible provenance.
- [x] No invented cameras, incidents, sensors, frequencies or PTZ controls.
- [x] Digital zoom is clearly not remote PTZ.
- [x] Radio and Tours are separate categories.
- [x] AI answers show source, time and confidence; no LLM and no image analysis.
- [x] Map attribution is visible for CARTO, OpenStreetMap and RainViewer.
- [x] Favorites survive reloads and link changes but stay on the device.
- [x] Original `CamLocatorNJTP` installation and `_backup_v1/` were not modified.

## 5. How to reproduce

```bat
set HV_PORT=8771
python src\server.py
```

In another terminal:

```bat
set HV_API=http://127.0.0.1:8771
set HV_BASE=http://127.0.0.1:8771
python -u tests\verify_extras.py
python -u tests\verify_ai.py
python -u tests\audit_ui.py
python -u tests\verify_map.py
python -u tests\verify_stage1.py
python -u tests\verify_drive.py
python -u tests\verify_mobile.py
```

Screenshots from the CDP runs are saved in `docs/screenshots/`.
