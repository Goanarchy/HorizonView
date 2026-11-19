# HorizonView — Deployment

HorizonView is a local-first application. It runs from the machine that holds the repository and can be published to a phone through a free HTTPS tunnel. There is no server to rent and no build step.

---

## 1. Local deployment

```bat
start.bat
```

Open `http://127.0.0.1:8770`. To use another port:

```bat
set HV_PORT=8771
python src\server.py
```

## 2. Phone deployment (recommended)

```bat
start-stable.bat
```

- With **Tailscale** installed and signed in, the script publishes a fixed `https://<machine>.<tailnet>.ts.net` URL with a valid public certificate.
- Without Tailscale, it falls back to a Cloudflare Quick Tunnel and writes a temporary URL to `URL_Movil.txt`.
- The local QR at `assets/qr-movil.png` is regenerated from the active URL.
- `HV_QR_URL` and `HV_QR_OUT` are set by the launcher; they do not need to be set manually.

Stop the fixed link with `tailscale funnel off`. Re-run the script to publish again.

## 3. Legacy fixed link (local machine only)

```bat
start-online.bat
```

This uses Caddy and `sslip.io` with a local CA (`URL_Online.txt`). It is intended for the same computer: other devices will see a certificate warning and geolocation may not work. Use `start-stable.bat` for phones.

## 4. Source refresh

```bat
python scripts\refresh.py
```

This opens Chrome through CDP because 511NJ signs and encrypts requests in the browser. A full refresh queries about 680 camera details and takes several minutes. Two helper scripts capture tour membership and events:

```bat
python scripts\nj_tours_capture.py
python scripts\nj_events_capture.py
```

## 5. Verification deployment

Start a second copy on port 8771 while the original keeps running on 8770:

```bat
set HV_PORT=8771
python src\server.py
```

Then point the verifiers at it:

```bat
set HV_API=http://127.0.0.1:8771
set HV_BASE=http://127.0.0.1:8771
python -u tests\verify_ai.py
python -u tests\verify_extras.py
python -u tests\audit_ui.py
python -u tests\verify_drive.py
```

## 6. Files never to publish

- `URL_Movil.txt` / `URL_Online.txt` — regenerated on every run.
- `%TEMP%\horizonview_*` logs and Chrome profiles.
- `data/stream_failures.json` — local reliability cache.
- `__pycache__/` and any `.pyc`.

The executables in `tools/` are included so another person can publish the app without downloading anything else.

## 7. GitHub CI

`.github/workflows/verify.yml` checks Python and JavaScript syntax on every push and pull request. Browser and network verification is intentionally local because it needs Chrome, live public sources and a running server.
