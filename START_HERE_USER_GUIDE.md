# START HERE — HorizonView User Guide (v1.0.0)

This guide is for anyone who wants to **test HorizonView in minutes**. No account, API key, credit card or technical setup is required.

---

## 1. Requirements

- Windows 10/11 with **Python 3** installed (`python --version`).
- Google Chrome (only needed for the verification scripts and 511NJ refresh).
- Internet connection for official data sources and map tiles.
- Optional: **Tailscale** personal account for a stable HTTPS link (`https://tailscale.com/download/windows`).

Everything else is included in the repository, including the local MapLibre, Leaflet and HLS libraries and the Cloudflare/Caddy executables.

## 2. Start on your computer (30 seconds)

1. Download or clone this repository.
2. Double-click **`start.bat`**.
3. Open `http://127.0.0.1:8770` in your browser.

That's it. The app starts with the driving question: *«¿Viajas hacia un lugar o usas los datos?»*

## 3. Open it on your Android or iPhone

1. Double-click **`start-stable.bat`**.
2. If Tailscale is installed and signed in, you get a **fixed** HTTPS URL such as `https://<your-machine>.<your-tailnet>.ts.net`.
3. Otherwise the script automatically falls back to a Cloudflare Quick Tunnel and prints a temporary `https://*.trycloudflare.com` URL.
4. Copy the URL into your phone browser, or scan `assets/qr-movil.png` from the **«Celular»** button on the computer.
5. Allow location when asked. The URL is saved in `URL_Movil.txt`.

The link has a valid public certificate: no security warnings, nothing installed on the phone, no open ports and no IPv6 needed. The computer must stay on. Cloudflare URLs change on every run; Tailscale Funnel URLs do not.

## 4. First drive

1. Choose **«Viajar»**.
2. Type a destination (real suggestions come from Nominatim) or pick one of six quick destinations.
3. Pick a travel profile: Explorador, Directo, Panorama, Tranquilo u Observador.
4. Pick music (five verified public stations or silence) and press **«Iniciar experiencia»**.
5. You will see the MapLibre route, ETA, current road, next official camera, weather and road context. Cameras appear automatically before you reach them.
6. At the end, the log and summary show every camera and event with distance, source and time.

Use **«Datos»** at any time to open the eight-tab administration area: Cámaras, Cerca, Locales, Mapa, IA, Radio, Tours y Guía. The **«Viaje»** tab returns to the drive.

## 5. What you can verify yourself

| Check | Where |
|---|---|
| Official inventory count | `http://127.0.0.1:8770/api/health` → `cameras`, `streams` |
| Source provenance | **«Datos» → Cámaras → Ver procedencia** |
| AI explanations | **«Datos» → IA** → each answer shows source, time and confidence |
| Tours are real | **«Datos» → Tours** → membership comes from 511NJ, not names |
| No invented PTZ | Camera viewer zoom is digital; no remote pan/tilt exists in the feed |
| Rain and road layers | Driving map → layer toggles; RainViewer attribution visible |
| Stable public URL | `start-stable.bat` with Tailscale Funnel |

## 6. Run the automated checks

From a terminal in the repository root:

```bat
python -m py_compile src\server.py src\ai.py src\extras.py
node --check src\app.js
set HV_API=http://127.0.0.1:8770
python -u tests\verify_ai.py
python -u tests\verify_extras.py
```

Browser checks need Chrome and `HV_BASE` pointing to the running app:

```bat
set HV_BASE=http://127.0.0.1:8770
python -u tests\audit_ui.py
python -u tests\verify_mobile.py
python -u tests\verify_drive.py
```

To test a **second copy** without stopping the original one, start it with `set HV_PORT=8771` and set `HV_API` / `HV_BASE` to `http://127.0.0.1:8771`.

## 7. Troubleshooting

- **`python` not found:** install Python 3 from `https://www.python.org/downloads/` and check *Add Python to PATH*.
- **Port 8770 busy:** set `HV_PORT` to another value and open that port in the browser.
- **Tunnel URL never appears:** check the logs in `%TEMP%\horizonview_movil` and make sure the computer has internet access.
- **Map is blank:** the map needs internet for CARTO tiles. The rest of the app keeps working.
- **Camera does not play:** public feeds can expire. The app marks the camera as unavailable and hides it for 6 hours after a real playback failure.
- **Refresh takes minutes:** refreshing 511NJ queries about 680 camera details through the real browser. Use **«Actualizar»** only when needed.

## 8. Legal and privacy notes

- All data comes from free, official or public sources with visible attribution.
- Radio streams are played directly from each station; nothing is recorded or redistributed.
- No accounts, advertising, telemetry or tracking.
- The app is informational: it is not a navigation or road-safety system.
- Favorites and reliability history stay in your browser and on your device.

See [README.md](./README.md) for the full feature list, [PROJECT_CONTEXT.md](./PROJECT_CONTEXT.md) for the architecture and [docs/QA_CHECKLIST.md](./docs/QA_CHECKLIST.md) for the verification record.
