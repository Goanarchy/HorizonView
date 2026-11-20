# Release Notes — HorizonView (v1.0.0)

**Release Date:** 19 de noviembre de 2026  
**Developer:** [Goanarchy (@goanarchy1)](https://x.com/goanarchy1)  
**Repository:** [Goanarchy/HorizonView](https://github.com/Goanarchy/HorizonView)  
**License:** MIT

---

## Highlights in v1.0.0

### 1. Super-app de conducción como pantalla principal

La experiencia de viaje tipo Waze es ahora la interfaz de entrada. Al abrir la app se pregunta *«¿Viajas hacia un lugar o usas los datos?»*. El flujo de conducción incluye onboarding en tres pasos (destino, estilo de viaje y música), mapa inmersivo con ruta OSRM, HUD con ETA y vía real, cámaras emergentes antes de pasar, chips contextuales progresivos, bitácora y resumen al llegar. La administración de ocho pestañas queda accesible en un toque mediante **«Datos»**.

### 2. Mapa vectorial de conducción con MapLibre GL 5.6.0

El mapa de conducción se migró de Leaflet a **MapLibre GL JS 5.6.0**, servido localmente sin CDN ni clave, con teselas vectoriales de CARTO (`dark-matter` / `positron`). Leaflet continúa reservado al mapa de la interfaz administrativa. Capas conmutables: lluvia de RainViewer, límites y cámaras de velocidad de OpenStreetMap vía Overpass, y contexto costero de NOAA CO-OPS/NHC.

### 3. Fuentes públicas verificables, sin invenciones

- **1051 cámaras oficiales** (679 de 511NJ, 372 de DelDOT) con **1042 streams HLS reales**; unas 1032 operativas visibles al cierre de esta versión.
- **85 tours reales** de 511NJ capturados con el navegador real (CDP), nunca inferidos del nombre.
- **404 eventos oficiales** de 511NJ (131 de NJ/DE) con categorías publicadas por la agencia.
- Clima de Open‑Meteo, alertas NWS, frecuencia NWR real, sensores USGS, radio pública verificada, OSRM, Nominatim, RainViewer y NOAA.
- La IA es **determinista y explicable**: reglas sobre datos públicos, sin LLM, sin análisis de imagen, sin rostros, placas, incidentes ni controles PTZ inventados.

### 4. Renombrado total a HorizonView

Se renombraron títulos, documentación, módulos Python, scripts de arranque, claves de configuración y verificadores. Las rutas HTTP `/api/*` se conservan estables para no romper verificadores ni enlaces existentes.

| Antes | Ahora |
|---|---|
| `cam_locator.py` | `src/server.py` |
| `ai_core.py` | `src/ai.py` |
| `extras_core.py` | `src/extras.py` |
| `assets/app.js` | `src/app.js` |
| `assets/app.css` | `styles.css` |
| `nj_refresh.py` | `scripts/refresh.py` |
| `Iniciar_CamLocator_*` | `start*.bat` / `start*.ps1` |
| `CAML_*` | `HV_*` |

### 5. Estructura estándar del proyecto

Se adopta la convención de los repositorios publicados por Goanarchy: `README.md`, `PROJECT_CONTEXT.md`, `RELEASE_NOTES.md`, `NEXT_VERSION_ROADMAP.md`, `START_HERE_USER_GUIDE.md`, `LICENSE` MIT, `VERSION`, `.gitignore`, `.gitattributes`, `src/`, `assets/`, `data/`, `scripts/`, `tools/`, `tests/`, `docs/` y `.github/workflows/`.

### 6. Verificación reproducible

Se añadieron variables de entorno para probar una copia sin detener la instalación original: `HV_PORT`, `HV_API` y `HV_BASE`.

| Comprobación | Resultado |
|---|---|
| `python -m py_compile` (servidor, IA, extras, scripts y tests) | `PY_OK` |
| `node --check src/app.js` | `JS_OK` |
| `tests/verify_extras.py` | radar `frames=8`, roadfacts `count=15`, coastal `water=1.296`, radio `5/5`, sensores `30+2` |
| `tests/verify_ai.py` | **30 correctas, 0 fallidas** |
| `tests/audit_ui.py` | **0 incidencias**, `scroll=390`, `HTTP_ERRORES=[]`, `ERRORES=[]` |
| `tests/verify_drive.py` | zoom `15.6`, `roadCount=194`, `radarCount=8`, `SPOTLIGHT_VISTO True`, `ERRORES []`, `HTTP []` |
| `tests/verify_map.py` | 86 opciones de tour, filtro `665 / 1032`, 9 teselas, 0 errores |
| `tests/verify_stage1.py` | favoritos, filtro y reporte manual OK |
| `tests/verify_mobile.py` | GPS 164 verificadas ±5 m, `videoWidth=853`, 0 errores |

---

## Actualización posterior a v1.0.0 — capa satelital (v1.1 en curso)

Se añadió una **capa opcional de satélite** en el mapa de conducción, sin clave ni certificados:

- **Fuente:** NASA GIBS, producto `GOES-East_ABI_Air_Mass` (masa de aire observada por el instrumento ABI del satélite GOES-East). La Capabilities filtrada por capa (`~33 KB`) y una tesela real sobre Somerville (NJ) se consultan en cada actualización; la hora exacta se lee de la cabecera `Layer-Time-Actual` de GIBS.
- **Interfaz:** interruptor «Satélite GOES-East (NASA GIBS)» en «Capas del viaje» (`dlSatellite`). La atribución «NASA GIBS · NOAA GOES-East» y la hora de la escena aparecen en el pie del mapa solo cuando la capa está activa.
- **API:** nuevo `GET /api/satellite`, aditivo. Devuelve plantilla de tesela, `maxzoom`, hora de la escena, hora de consulta, muestra verificada, fuente y atribución. Las rutas `/api/*` existentes no cambiaron.
- **Límites declarados:** GOES-East publica escenas nuevas aproximadamente cada 10 minutos; es una observación con hora propia, **no una predicción**. La capa usa teselas `GoogleMapsCompatible_Level6` (0–6) y se sobre-amplía en zooms altos; si GIBS no responde, la capa se desactiva sin afectar ruta, cámaras ni radar. Durante el relevo de escena GIBS puede devolver un `404` aislado en alguna tesela; se recupera automáticamente en la siguiente petición y no altera la hora ni la atribución mostradas.
- **Prueba reproducible:** `python tests/verify_satellite.py` y la comprobación `satellite` dentro de `tests/verify_extras.py`.

---

## Notas

- El proyecto original `CamLocatorNJTP` y su túnel público quedan intactos; HorizonView se construyó como copia separada y se verificó en el puerto alterno `8771`.
- El túnel Cloudflare Quick Tunnel caduca y cambia de hostname al reiniciar. Para un enlace estable, `start-stable.bat` usa Tailscale Funnel cuando está disponible.
- Esta versión no incluye cuentas, publicidad, telemetría ni seguimiento. Los favoritos y el historial de confianza viven en el dispositivo.

Consulta [START_HERE_USER_GUIDE.md](./START_HERE_USER_GUIDE.md) para empezar y [NEXT_VERSION_ROADMAP.md](./NEXT_VERSION_ROADMAP.md) para los próximos pasos.
