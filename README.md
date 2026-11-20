# HorizonView

**Super-app de conducción con interfaz principal tipo Waze**, respaldada por el visor de cámaras públicas reales de **toda Nueva Jersey y Delaware** (no solo del Turnpike), con GPS, distancias y video en vivo. Diseño mobile-first (Liquid Glass + Bento) y enlace HTTPS válido para abrirlo desde cualquier celular. Incluye **zonas locales, clima animado real, sensores y frecuencias públicas, radio en vivo verificada** y herramientas combinadas, todo gratis y trazable. La interfaz administrativa de ocho pestañas sigue disponible en segundo plano mediante el botón discreto **«Datos»**.

## Arrancar y abrirlo en el celular (recomendado)

1. Doble clic en **`start-stable.bat`** (etapa 1).
2. Si Tailscale está instalado y con sesión iniciada, el script activa **Tailscale Funnel** y publica un hostname **fijo**: `https://<tu-maquina>.<tu-tailnet>.ts.net`. Es gratis en el plan personal, trae HTTPS válido y **no cambia entre reinicios**.
3. Si Tailscale no está instalado, el script usa automáticamente el túnel rápido de Cloudflare y te dice cómo instalar Tailscale (gratis) para obtener el enlace fijo.
4. Copia el enlace que aparece en la ventana (también queda en `URL_Movil.txt`) y ábrelo en tu Android o iPhone. En la computadora puedes pulsar **«Celular»** para ver el QR (`assets/qr-movil.png`).
5. En el celular aparece primero la pregunta **«¿Viajar hacia un lugar o usar los datos?»**. Elige **«Viajar»**, escribe o sugiere un destino, selecciona estilo de viaje y música, y pulsa **«Iniciar experiencia»**. Verás el mapa de ruta, ETA, cámara siguiente, música y avisos; las cámaras oficiales aparecen solas unos segundos antes de pasar. Si eliges **«Usar los datos»** entras directo a la administración. En cualquier momento el botón **«Datos»** (☰) te lleva a ella y la pestaña **«Viaje»** te devuelve a la experiencia.

Es HTTPS con certificado público: **no hay avisos de seguridad, no se instala nada en el teléfono y el GPS funciona**. No hace falta abrir puertos ni tener IPv6 público.

- Enlace vigente al cerrar esta documentación (respaldo Cloudflare): **`https://sam-provide-michel-install.trycloudflare.com/`**. Sirve HTTPS válido para Android e iPhone; `/api/health` responde `200` con 1051 cámaras y 1042 streams, y muestra la interfaz de HorizonView (`src/app.js` y `styles.css` responden `200`). Los enlaces `*.trycloudflare.com` citados en secciones históricas de `docs/AUDITORÍA.md` ya caducaron: solo es vigente el de `URL_Movil.txt`. Si necesitas un enlace nuevo, ejecuta `start-mobile.ps1`; con `HV_PORT=8771` publica una copia separada sin detener la instalación original.
- Con Cloudflare el enlace cambia en cada ejecución; con Tailscale Funnel es estable. Ambos son gratuitos.
- Para detener el enlace fijo: `tailscale funnel off`. Para volver a publicarlo: ejecuta de nuevo el `.bat` estable.
- La computadora debe permanecer encendida y conectada; el servicio se publica desde ella.
- Puedes cerrar la ventana: el servidor y el túnel siguen activos.

> Instalación gratuita de Tailscale: `https://tailscale.com/download/windows`, luego `tailscale login` con una cuenta personal. No se requiere tarjeta de crédito.

## Arranque local

Doble clic en **`start.bat`** → `http://127.0.0.1:8770`. Puerto configurable con `HV_PORT`.

## Enlace fijo anterior (solo en esta computadora)

`start-online.bat` sigue generando el enlace fijo con `sslip.io` + Caddy y certificado local (`URL_Online.txt`). Está pensado para el navegador de **esta** máquina: en un celular ajeno aparece una advertencia de certificado y `navigator.geolocation` puede no funcionar. Para celulares usa el modo «Movil» descrito arriba.

## Qué hace la app

- **Inventario:** 1051 cámaras oficiales (679 de 511NJ, 372 de DelDOT) con **1042 streams HLS reales** (670 de 511NJ, 372 de DelDOT). La interfaz muestra unas 1025–1029 cámaras operativas (1026 al cerrar esta pasada); el número baja temporalmente cuando el filtro automático oculta fallos verificados, además de las exclusiones permanentes por baja o no disponibilidad. Búsqueda por nombre/ruta/punto kilométrico, filtros por zona, «Solo ruta» y «Con video», orden por zona, nombre o distancia.
- **GPS:** en la pestaña «Cerca» calcula distancias reales (Haversine) y muestra las 5, 10, 20 o 50 cámaras más cercanas con su distancia. Si no hay resultados a 25 km, amplía automáticamente a 50 y 100 km y lo indica en el mensaje. La ubicación se procesa solo en el dispositivo.
- **Cámaras locales en vivo (categoría «Locales»):** con el GPS busca cámaras públicas de **cualquier fuente del inventario** dentro de un radio de 10, 25, 50 o 100 km. Descarta las cámaras dadas de baja, sin stream o marcadas como no disponibles, y verifica la playlist (incluidas **playlists maestras**, `init.mp4` fMP4 y partial segments LL-HLS) y **bytes reales de video** (MPEG‑TS `0x47` o cajas ISO BMFF `ftyp`/`moof`/`mdat`) antes de mostrarla. Si una cámara falla al reproducirse en el celular, se reporta al servidor y se oculta de todo el inventario durante 6 horas. Solo aparecen cámaras que responden, ordenadas por distancia, con hora de verificación. «Verificar de nuevo» fuerza una nueva comprobación (hay cache de 5 minutos para no saturar a las agencias).
- **Visor:** streams HLS oficiales mediante proxy local. Controles de reproducción, sonido, pantalla completa, captura de fotograma y **zoom/paneo digital** (+/−, arrastrar, «Centrar»).
- **Mapa interactivo de administración (etapa 2):** pestaña «Mapa» con Leaflet local y teselas gratuitas de OpenStreetMap/CARTO (claro/oscuro según el tema). Muestra **todas las cámaras filtradas** en su coordenada real, distingue 511NJ/DelDOT, resalta las verificadas en vivo y tu ubicación con su precisión. Incluye «Mi ubicación», «Ajustar» a los filtros y toggle «Solo verificadas en vivo». Toca un punto para abrir el visor. Es el mapa de la interfaz administrativa; el de la conducción usa MapLibre GL (ver más abajo).
- **Tours oficiales (etapa 2):** filtro con los **85 tours reales de 511NJ**, capturados uno por uno desde la app oficial. El visor indica los tours de cada cámara. No se infieren tours por el nombre: vienen de la pertenencia publicada por la agencia.
- **Favoritos (etapa 1):** estrella ☆/★ en cada tarjeta y en el visor; se guardan en `localStorage` (`horizonViewFavoritos`). El filtro **«Solo favoritos»** reduce el inventario y la selección sobrevive a cambios de enlace, tema o recarga.
- **Reportar fallo (etapa 1):** botón «Reportar fallo» en el visor con confirmación en dos toques; usa el mismo `POST /api/stream-report` y oculta la cámara 6 horas. Los fallos fatales de reproducción siguen reportándose automáticamente.
- **Compartir:** «Compartir» copia un enlace `?cam=nj-55` que abre directamente esa cámara.
- **Actualización:** DelDOT cada 5 minutos mientras la página está abierta; 511NJ bajo demanda desde «Actualizar» (captura los detalles/streams de las 679 cámaras de los 85 tours oficiales mediante el navegador real; tarda varios minutos).
- **Tema:** noche por defecto, se recuerda en `localStorage`; se puede forzar con `?theme=light` o `?theme=dark`. `?nowizard=1` omite la guía (útil para pruebas y enlaces directos).
- **IA explicable (etapa 3, categoría «IA»):** ocho herramientas deterministas con fuente, hora y confianza visibles, más un botón «Ver datos» en cada respuesta. No usa LLM, no interpreta imágenes, no reconoce rostros, placas ni vehículos y no inventa incidentes, cámaras ni controles.
- **Asistente en lenguaje natural:** traduce frases como «cámaras con video cerca de Newark NJ», «cámaras en el tour NJ Turnpike Tour» o «mis favoritos más confiables» a filtros sobre datos reales. Explica cada interpretación y permite quitar el filtro IA.
- **Copiloto de ruta:** calcula un trayecto real con OSRM, dibuja la polilínea en el mapa y lista cámaras oficiales con video a 1, 2, 5 o 10 km de la ruta, con kilómetro aproximado y tiempo estimado **sin tráfico en vivo**.
- **Resumen matutino, alertas y favoritos inteligentes:** unen favoritos locales, clima actual de Open‑Meteo y alertas activas de NWS; agrupan tus cámaras guardadas por corredor, confianza, tour y cercanía sin sincronizarlas a la nube.
- **Triangulación y comparador:** explican una cámara con vecinas reales, eventos oficiales 511NJ y clima en el punto; el comparador abre hasta **4 streams oficiales** en vivo para comparar la calidad de cada fuente.
- **Tours narrados (etapa 3, categoría aparte «Tours»):** convierte los 85 tours oficiales de 511NJ en un recorrido de cámaras reales con distancias sobre coordenadas publicadas, puntos clicables y lectura en voz alta con el motor del dispositivo. La pertenencia al tour viene de 511NJ, nunca del nombre.
- **Capas IA en el mapa:** toggle opcional que superpone alertas NWS, eventos oficiales 511NJ, clima actual y obras viales señalizadas en OpenStreetMap (Overpass), cada una con fuente y hora.
- **Feed de eventos 511NJ:** 404 eventos oficiales capturados de `POST /client/get/event` (131 de NJ/DE), con categorías reales: construcción, desvíos, incidentes, congestión y eventos especiales. Se usa como contexto verificable, nunca como predicción.
- **Zonas locales (etapa 4):** chips de Somerville (10), Raritan (6), Manville (7) y Bridgewater (5) sobre el inventario real. Cada zona es un overlay en `data/local_zones.json` con IDs oficiales verificados y stream activo; no altera `data/nj_cameras.json`. Filtran la lista y se dibujan en el mapa.
- **Clima animado real (etapa 4):** tile del resumen con escena animada según el estado del cielo (despejado/nublado/lluvia/nieve/tormenta, día o noche), datos actuales de Open‑Meteo, pronóstico por horas y alertas NWS activas. Incluye la frecuencia real de radio NOAA (NWR) de la zona —p. ej. KWO35 `162.55 MHz`, `SAME 034035`— leída de `api.weather.gov/radio/<estación>/broadcast`, no supuesta.
- **Sensores y frecuencias públicas (etapa 4):** 32 lecturas verificadas cerca de la zona (30 sensores USGS de caudal/nivel más 2 radios NOAA) con valor, hora y enlace a la fuente. La app no inventa capacidad de sensor ni frecuencias.
- **Estado del corredor (etapa 4):** medidor explicable (p. ej. `75/100 · Atención`) que combina eventos oficiales 511NJ, alertas NWS y clima en la zona, con cada señal, su fuente y su hora. Es contexto verificable, no una predicción de tráfico.
- **Radio en vivo (etapa 4, categoría «Radio»):** 5 emisoras públicas reales (WBGO Jazz, WQXR Q2, NJ 101.5, 94.3 The Point y WFMU) con logo verificado, orden por categoría (noticias, cultura, clásica, música, comunitaria) y botón propio para elegir cada una. Audio directo desde la emisora: ICY (`audio/mpeg`, `audio/aacp`) o HLS con playlists y segmentos reescritos por el proxy. La app **no redistribuye ni graba** la señal; solo verifica el host HTTPS y la metadata real (`nowPlaying`).
- **Guía:** ocho pasos, se puede volver a abrir con «Guía».

### Sobre los controles de las cámaras

Las fuentes públicas de 511NJ y DelDOT **no exponen control PTZ remoto** (ni giro, inclinación ni zoom mecánico): el inventario no contiene ningún campo de control. Por eso el zoom de la app es **digital** (sobre la imagen recibida). No se simulan controles que la agencia no ofrece.

## Experiencia de conducción (interfaz principal)

Al abrir la app se pregunta **«¿Viajas hacia un lugar o usas los datos?»**. La experiencia de viaje es la pantalla principal; la administración queda a un toque en **«Datos»**.

- **Onboarding en tres pasos:** destino (con sugerencias reales de Nominatim y seis destinos rápidos), estilo de viaje (Explorador, Directo, Panorama, Tranquilo u Observador) y música (cinco emisoras verificadas o silencio). Se recuerda la elección; `?nowizard=1` o `?mode=admin` omiten el asistente y abren la administración directamente.
- **Mapa inmersivo (etapa 6):** **MapLibre GL JS 5.6.0 servido localmente** con **teselas vectoriales CARTO** (`dark-matter` / `positron`, sin clave), ruta OSRM con tramo recorrido, marcador de posición, cámaras, servicios, alertas y eventos. Zoom de conducción `15.6` con seguimiento del vehículo; «Ver ruta completa» aleja sin perder la ruta y «Recentrar» vuelve a seguir. Capas conmutables: lluvia en vivo de RainViewer, masa de aire satelital GOES-East/ABI de NASA GIBS, límites y cámaras de velocidad de OpenStreetMap y contexto costero de NOAA. Botones grandes para centrar, capas, voz y música.
- **HUD tipo Waze:** destino, **«Estás en …»** con la vía real (Nominatim reverse, caché de 24 h y enlace a OSM), hora de llegada, distancia restante, próxima cámara y barra de progreso.
- **Cámaras emergentes:** cuando una cámara oficial está en la ruta y a menos del margen del perfil, aparece ~400 m antes con su video HLS real durante 4–12 s y vuelve sola al mapa. Se ignoran cámaras al inicio o demasiado lejos del trazado para evitar repeticiones. Botones «Saltar» y «Ver en grande».
- **Chips contextuales progresivos:** clima y AQI (NWS + Open-Meteo), alertas NWS, corredor explicable, sensores USGS/NOAA, servicios de OpenStreetMap, eventos 511NJ, música y próximos servicios. Aparecen conforme llega cada fuente, sin bloquear la ruta.
- **Simulación y GPS real:** velocidad de 50/90/110 km/h con avance continuo, o `watchPosition` del dispositivo con precisión y aviso si te sales del trazado. La simulación sigue avanzando con la pantalla en segundo plano.
- **Bitácora y resumen:** registro de cada cámara mostrada y evento, con distancia, cámaras, estilo y música al llegar; fuentes y limitaciones indicadas. La narración por voz es opcional y usa el motor del dispositivo.

### Mapa vectorial y contexto en ruta (etapa 6)

El mapa de conducción se migró de Leaflet a **MapLibre GL JS 5.6.0** (JS y CSS locales en `assets/`) con teselas vectoriales de CARTO. El renderizado en GPU permite el zoom alto de conducción sin depender de teselas raster y el cambio día/noche usa `setStyle` sin reconstruir la interfaz. Leaflet sigue sirviendo solo al mapa administrativo.

| Capa | Fuente | Presentación |
|---|---|---|
| Lluvia | RainViewer (`api.rainviewer.com` → `tilecache.rainviewer.com`) | Fotogramas reales recientes sobre el mapa; atribución visible «Weather data by RainViewer» con enlace a `rainviewer.com`; interruptor `dlRadar` |
| Satélite (masa de aire) | NASA GIBS · GOES-East/ABI (`GOES-East_ABI_Air_Mass`) | Escena real con hora exacta leída de GIBS, teselas WMTS sin clave, atribución «NASA GIBS · NOAA GOES-East» en el pie del mapa; interruptor `dlSatellite` |
| Límites y cámaras de velocidad | OpenStreetMap vía Overpass (`maxspeed`, `highway=speed_camera`) | Dato cartográfico con nombre, valor y enlace al objeto OSM; ordenado por distancia real al trazado y descartado si queda a más de 2 km; interruptor `dlRoad` |
| Contexto costero | NOAA CO-OPS (estación más cercana vía MDAPI) y NHC | Nivel de agua observado y tormentas activas con hora y fuente; sin umbrales de riesgo inventados; interruptor `dlCoastal` |

El badge `driveLimit` muestra el límite más cercano al vehículo con su distancia y procedencia (p. ej. «Mount Vernon Road · 35 mph · 651 m · OpenStreetMap»). Un `maxspeed` de OpenStreetMap nunca se presenta como señalización oficial y la app no inventa cámaras de velocidad donde el mapa no las publica.

### Endpoints nuevos de esta etapa

| Endpoint | Uso |
|---|---|
| `GET /api/geocode?q=&limit=1..8` | Geocodificación con varias sugerencias para el destino del viaje |
| `GET /api/reverse?lat=&lon=` | Vía/paraje actual con fuente OSM, hora y caché de 24 h |
| `POST /api/trip/services` | Servicios (repostaje, carga, áreas de servicio, peajes) sobre la geometría de la ruta, vía Overpass |
| `GET /api/weather/live` | Añade `air` con `usAqi` y `pm25` de Open-Meteo Air Quality |
| `GET /api/radar` | Fotogramas de lluvia de RainViewer con plantilla de tesela, atribución y hora |
| `GET /api/satellite` | Escena GOES-East/ABI vía NASA GIBS: hora exacta, plantilla de tesela, `maxzoom`, muestra verificada, fuente y atribución |
| `GET /api/coastal?lat=&lon=` | Estación CO-OPS más cercana, último nivel de agua y tormentas NHC |
| `POST /api/roadfacts` | Límites y cámaras de velocidad de OSM sobre la geometría, ordenados por distancia real al trazado |

Overpass usa `https://overpass.openstreetmap.fr/api/interpreter` como mirror principal, con `overpass-api.de` de respaldo, varias cajas pequeñas a lo largo de la ruta, cabeceras `User-Agent`/`Accept` y 60 s de espera (en horas punta la respuesta tarda ~40 s). `overpass.kumi.systems` se retiró por timeouts repetidos. Los hechos viales piden `out center 300` y se ordenan por distancia real al trazado (máximo 2 km) para que los objetos cercanos no queden fuera por el límite de salida. Todo sigue siendo gratuito, sin clave y verificable.

## Fuentes oficiales

| Fuente | Endpoint | Uso |
|---|---|---|
| 511NJ | `https://511nj.org/camera` (`getTourList`, `getCameraDataByTourId`, `getCameraDetail`) | Inventario completo de Nueva Jersey (85 tours) y sus streams HLS |
| DelDOT | `https://tmc.deldot.gov/json/videocamera.json?id=4yte` | Inventario de Delaware y streams HLS |
| 511NJ · eventos | `POST https://511nj.org/client/get/event` (cuerpo cifrado, capturado con CDP) | 404 eventos oficiales, 131 de NJ/DE: obras, desvíos, incidentes, congestión |
| NWS / NOAA | `https://api.weather.gov/alerts/active?area=NJ,DE` y `?point=lat,lon` | Alertas meteorológicas activas por estado y por coordenada |
| NWS · radio NWR | `https://api.weather.gov/radio/KWO35/broadcast` | Frecuencia y código SAME reales de radio NOAA (no inferidos) |
| USGS | `https://waterservices.usgs.gov/nwis/iv/...` | Lecturas públicas de caudal/nivel de sensores cercanos |
| Open‑Meteo | `https://api.open-meteo.com/v1/forecast?...` | Clima actual (temperatura, precipitación, viento, visibilidad) y pronóstico por horas |
| Emisoras públicas | streams HTTPS verificados (WBGO, WNYC/WQXR, Townsquare, WFMU) | Radio en vivo con metadata ICY; audio directo desde cada emisora |
| OSRM | `https://router.project-osrm.org/route/v1/driving/...` | Rutas por red viaria y polilínea para el copiloto y la experiencia de conducción |
| Nominatim | `https://nominatim.openstreetmap.org/search?...` | Geocodificación de lugares introducidos por el usuario |
| Nominatim reverse | `https://nominatim.openstreetmap.org/reverse?...` | Vía actual mostrada en el HUD del viaje, con enlace al objeto OSM |
| Open-Meteo Air Quality | `https://air-quality-api.open-meteo.com/v1/air-quality?...` | `usAqi` y `pm25` en el clima del viaje |
| Overpass / OSM | `https://overpass.openstreetmap.fr/api/interpreter?...` (respaldo `overpass-api.de`) | Obras, servicios, límites y cámaras de velocidad en ruta, con fuente y hora |
| CARTO / OSM | `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json` y `positron-gl-style/style.json`, vía MapLibre GL local | Mapa vectorial claro/oscuro de la conducción, con atribución visible |
| CARTO / OSM (admin) | teselas `basemaps.cartocdn.com` vía Leaflet local | Mapa administrativo claro/oscuro, con atribución visible |
| RainViewer | `https://api.rainviewer.com/public/weather-maps.json` → `https://tilecache.rainviewer.com/...` | Fotogramas reales de lluvia sobre el mapa de conducción |
| NASA GIBS / NOAA GOES-East | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GOES-East_ABI_Air_Mass/default/...` | Capa opcional de masa de aire observada por ABI; hora exacta y atribución visibles, sin clave |
| NOAA CO-OPS | `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json` y `/api/prod/datagetter` | Estación mareográfica más cercana y último nivel de agua observado |
| NOAA NHC | `https://www.nhc.noaa.gov/CurrentStorms.json` | Tormentas activas como contexto, sin predicción propia |

La ficha **Ver procedencia** muestra los datos de inventario con sus enlaces y timestamps; cada respuesta IA incluye además sus propias fuentes, hora y confianza. Todas las fuentes son gratuitas y no requieren clave API.

## Arquitectura

```
HorizonView/
├─ README.md · PROJECT_CONTEXT.md · RELEASE_NOTES.md
├─ NEXT_VERSION_ROADMAP.md · START_HERE_USER_GUIDE.md
├─ VERSION · LICENSE (MIT) · .gitignore · .gitattributes
├─ index.html                       interfaz mobile-first (viaje + administración)
├─ styles.css                       Liquid Glass + Bento, animación climática
├─ start.bat                        arranque local de un clic
├─ start-stable.bat/.ps1            enlace FIJO gratis + fallback           ★
├─ start-mobile.bat/.ps1            servidor + cloudflared + URL + QR
├─ start-online.bat/.ps1            enlace fijo legado (CA local)
├─ URL_Movil.txt · URL_Online.txt   enlaces publicados (se regeneran)
├─ Caddyfile                        configuración del modo fijo legado
├─ src/
│  ├─ server.py                     servidor, API, proxy HLS/radio y refresco
│  ├─ ai.py                         IA determinista y explicable           ★
│  ├─ extras.py                     zonas, clima, sensores, radio, radar, vial y costa ★
│  └─ app.js                        inventario, GPS, visor, IA, radio, viaje y mapa MapLibre
├─ assets/
│  ├─ maplibre-gl.js / .css          mapa vectorial de conducción (BSD-3)  ★
│  ├─ leaflet.js / leaflet.css       mapa interactivo de administración (BSD-2) ★
│  ├─ hls.min.js                     reproductor HLS local
│  ├─ qr-movil.png                   QR del enlace móvil (se regenera)      ★
│  └─ logo.svg y wizard-*.svg
├─ data/
│  ├─ nj_raw_inventory.json          respuesta cruda 511NJ (procedencia)     ★
│  ├─ nj_tours.json                  85 tours y cámaras por tour             ★
│  ├─ nj_events.json                 404 eventos oficiales 511NJ            ★
│  ├─ local_zones.json               4 zonas locales con IDs oficiales       ★
│  ├─ radio_stations.json            5 emisoras, streams, logos y categorías ★
│  ├─ ai_signals.json                historial local anónimo de verificaciones ★
│  └─ inventarios normalizados y procedencia
├─ scripts/
│  ├─ refresh.py                     refresco de 511NJ mediante Chrome y CDP
│  ├─ nj_tours_capture.py            pertenencia real a los 85 tours 511NJ  ★
│  ├─ nj_events_capture.py           captura CDP del feed de eventos 511NJ   ★
│  └─ analyze/probe/find511endpoints  utilidades de diagnóstico
├─ tools/
│  ├─ cloudflared.exe                túnel HTTPS con certificado público
│  └─ caddy.exe                      proxy del modo fijo legado
├─ tests/
│  ├─ verify_mobile.py · verify_fmp4.py · verify_gps_newark.py
│  ├─ verify_map.py · verify_stage1.py · verify_ai.py · verify_extras.py
│  ├─ verify_new_sources.py          prueba de NWS/Open-Meteo/Overpass
│  └─ audit_ui.py                    auditoría geométrica + estados IA/Radio
├─ docs/
│  ├─ AUDITORÍA.md                   verificación visual y funcional
│  ├─ ARCHITECTURE.md · QA_CHECKLIST.md · DEPLOYMENT.md
│  └─ screenshots/                   capturas de auditoría
└─ .github/workflows/verify.yml      comprobación automática de sintaxis
```

## API local

- `GET /api/health` — resumen y estado del servidor.
- `GET /api/cameras` — cámaras operativas, procedencia y número de excluidas (incluye `zone` anotado).
- `GET /api/source` — metadatos de las fuentes.
- `GET /api/tours` — 85 tours oficiales de 511NJ con número de cámaras.
- `GET /api/events` — resumen de los 131 eventos NJ/DE con categorías y hora de captura.
- `GET /api/zones` — 4 zonas locales con sus cámaras oficiales.
- `GET /api/geocode?q=...` — geocodificación real con Nominatim (caché de 24 h).
- `GET /api/weather/alerts` — alertas activas de NWS para NJ/DE.
- `GET /api/weather/live?lat=&lon=` — clima animado real, pronóstico por horas y radio NWR con frecuencia verificada.
- `GET /api/sensors?lat=&lon=` — sensores USGS y radios NOAA cercanos, con valor, hora y fuente.
- `GET /api/radar` — fotogramas de lluvia de RainViewer con host, plantilla de tesela, atribución y hora.
- `GET /api/satellite` — escena de masa de aire GOES-East/ABI vía NASA GIBS, con hora exacta, plantilla de tesela, muestra verificada, atribución y nota de «observación, no predicción».
- `GET /api/coastal?lat=&lon=` — estación CO-OPS más cercana, nivel de agua observado y tormentas NHC.
- `POST /api/roadfacts` — `{geometry}`: límites y cámaras de velocidad de OSM ordenados por distancia al trazado; responde `200` con `ok:false` si Overpass no está disponible.
- `GET /api/radio/stations[?refresh=1]` — 5 emisoras verificadas, categorías, logos y metadata real.
- `GET /api/radio/metadata?id=<id>` — `nowPlaying`, disponibilidad y hora de comprobación de una emisora.
- `GET /api/radio/stream/<id>[/<url-codificada>]` — proxy de streams ICY y HLS (playlists y segmentos reescritos).
- `GET /api/ai/stats` — historial local anónimo de verificaciones de video.
- `GET /api/ai/layers?lat=&lon=&infra=&radiusKm=` — capas públicas para el mapa.
- `POST /api/ai/query` — `{q, favs, geo?}`: lenguaje natural → filtros reales y explicación.
- `POST /api/ai/route` — `{from, to|useGeo, bufferKm, limit}`: ruta OSRM y cámaras a lo largo del trayecto.
- `POST /api/ai/brief` — `{favs, geo?}`: resumen con clima y alertas.
- `POST /api/ai/alerts` — `{state|geo, radiusKm?}`: señales por zona con evidencia.
- `POST /api/ai/groups` — `{favs, geo?}`: agrupación local de favoritos.
- `POST /api/ai/context` — `{id, geo?}`: triangulación de una cámara con fuentes públicas.
- `POST /api/ai/tour` — `{tour, geo?}`: narración de un tour oficial.
- `POST /api/ai/compare` — `{ids}`: comparación de 2 a 4 cámaras vecinas.
- `POST /api/ai/corridor` — `{zone?, lat?, lon?}`: medidor explicable del corredor con eventos, alertas y clima.
- `POST /api/streams/check` — `{ids}`: verifica en paralelo qué streams responden; el comparador sustituye los que fallan por vecinas verificadas.
- `GET /api/mobile` — enlace público móvil y ruta del QR.
- `POST /api/nearby` — `{lat, lon, radiusKm, limit, force}`: cámaras cercanas operativas con playlist y bytes de video verificados.
- `POST /api/stream-report` — `{id, reason}`: marca una cámara como no funcional tras un fallo real de reproducción (6 h).
- `POST /api/refresh` — `{"kind":"de"|"nj"|"all"}`.
- `GET /api/refresh/status` — progreso de los trabajos.
- `GET /api/hls/<id>/<url-codificada>` — proxy de playlists y segmentos.

El proxy es necesario porque los streams de 511NJ exigen `Referer: https://511nj.org/` y no permiten CORS. Reescribe playlists maestras, segmentos, `EXT-X-KEY`, `EXT-X-MAP` (init fMP4) y partial segments de LL-HLS, conservando el token `otp`. Los streams de DelDOT también se proxyfican de forma uniforme. El proxy de radio reescribe playlists HLS (incluidos los segmentos `.aac` servidos por los CDN verificados de las emisoras, `d25j5qm9y8ulag.cloudfront.net` y `d1n065hnrro57i.cloudfront.net` — este último referenciado por la playlist oficial de NJ 101.5 para sus bloques publicitarios) y pasa los streams ICY sin `Content-Length`; solo acepta hosts HTTPS comprobados de las emisoras (`RADIO_HOSTS`).

## Notas y límites

- No se inventaron cámaras ni coordenadas: todo procede de las fuentes oficiales.
- La marca «en ruta» y las zonas son clasificaciones derivadas del nombre o del condado, no etiquetas oficiales de las agencias; se detallan en `docs/AUDITORÍA.md`.
- La disponibilidad futura de cada stream depende de la agencia. El badge «En vivo» en el inventario general significa que la fuente expone una URL HLS; en «Locales» significa que la playlist **y bytes reales de video** respondieron en el momento de la verificación. Si falla durante la reproducción, el cliente la reporta y desaparece de la app por 6 horas.
- «Cualquier tipo de cámara pública» significa cualquier cámara pública presente en los inventarios oficiales de 511NJ y DelDOT (tráfico, rutas, puntos kilométricos, etc.). Para añadir otras agencias o cámaras municipales harían falta sus fuentes oficiales.
- El enlace móvil depende de que la computadora siga encendida y del servicio gratuito elegido (Tailscale Funnel o Cloudflare); no es un alojamiento 24/7.
- Los favoritos viven en el navegador del dispositivo: se conservan al cambiar de enlace, pero no se sincronizan entre teléfonos. Un futuro perfil opcional podría sincronizarlos sin costo.
- Ambos mapas usan teselas gratuitas con atribución visible (© OpenStreetMap, © CARTO) y necesitan conexión; la app y el proxy siguen funcionando sin mapa. MapLibre GL y Leaflet se sirven localmente, sin CDN. El radar de RainViewer muestra su atribución «Weather data by RainViewer» con enlace a `rainviewer.com`.
- Algunos tours oficiales están vacíos o comparten cámaras con otros tours: eso es lo que publica 511NJ. La pertenencia se capturó con `scripts/nj_tours_capture.py` y se guarda en `data/nj_tours.json`.
- La precisión cartográfica se conserva tal como la publican 511NJ y DelDOT.
- La app es informativa: no es un sistema de navegación ni de seguridad vial.
- La IA es **determinista y explicable**: reglas sobre datos públicos, sin LLM y sin análisis de video. Nunca identifica rostros, placas ni vehículos, y nunca afirma un incidente que no publique una agencia. El puntaje de confianza mide la **calidad del dato** (fuente oficial, stream, historial local, verificación en sesión), no el tráfico ni lo que se ve en la imagen.
- Los eventos de 511NJ son una **captura puntual** con hora guardada en `data/nj_events.json`; no es una suscripción en vivo. Para renovarlos: `python scripts\nj_events_capture.py`. La app firma/cifra esa petición en la página oficial, por eso se captura con el navegador real (CDP), no con `requests`.
- NWS, Open‑Meteo, OSRM, Nominatim, RainViewer, NOAA y Overpass son gratuitos, pero tienen límites de uso: las respuestas se cachean en memoria (10 min para clima/alertas, 24 h para geocodificación, 15 min para Overpass, 5 min para radar, 10 min para la capa satelital GIBS, 24 h para estaciones CO-OPS). Overpass espera hasta 60 s porque en horas punta tarda ~40 s. Nominatim exige `User-Agent`, ya incluido.
- Las rutas de OSRM **no incluyen tráfico en vivo**: el tiempo mostrado es una estimación de la red viaria. Las cámaras se comparan con la polilínea real, con un margen elegido por el usuario.
- Las obras, límites de velocidad y cámaras de velocidad de OpenStreetMap/Overpass son aportaciones cartográficas, no una señal oficial ni un aviso de la agencia; pueden estar desactualizados. El límite mostrado en el HUD es el objeto OSM más cercano a la ruta, con su distancia y enlace; aparece solo si activas la capa vial.
- El radar de RainViewer, la capa satelital GOES-East/ABI de NASA GIBS y los datos costeros de NOAA CO-OPS/NHC son observaciones con hora propia, no una predicción de la app. GOES-East publica escenas nuevas aproximadamente cada 10 minutos y la capa se sobre-amplía en zooms altos; si GIBS no responde, la capa se oculta sin afectar la ruta. En el relevo de escena pueden aparecer `404` aislados en la consola del navegador: son transitorios y se recuperan solos. La cobertura del radar depende del país y el servicio no ofrece SLA; el nivel de agua y las tormentas se muestran con su fuente, sin umbrales de riesgo inventados.
- El comparador abre hasta 4 videos HLS reales a la vez: consume más ancho de banda que el visor individual. La recomendación es sobre la fuente del video, no sobre lo que ocurre en la imagen.
- La narración de tours usa pertenencia real publicada por 511NJ y muestra los primeros 10 pasos para no saturar la pantalla; el total de cámaras del tour se indica aparte. La voz depende de los idiomas instalados en el dispositivo.
- Los favoritos y el historial de confianza viven solo en este dispositivo (`localStorage` y `data/ai_signals.json`): no hay cuentas, publicidad ni seguimiento.
- Las zonas locales son un overlay propio (`data/local_zones.json`) sobre el inventario oficial; son una comodidad de navegación, no una división administrativa de las agencias.
- El clima y el pronóstico son datos de Open‑Meteo y NWS con hora de observación; la animación es una representación del estado del cielo, no una imagen de cámara ni una predicción propia. La frecuencia NWR se lee del registro público de la estación; puede cambiar si NOAA reasigna el transmisor.
- Los sensores USGS y las radios NOAA son fuentes públicas con su propia hora de lectura; la app no deduce capacidad de sensor ni inventa frecuencias. Algunas lecturas pueden estar desactualizadas en origen.
- La radio se reproduce directamente desde cada emisora: no se redistribuye ni se graba. Si una emisora cambia su host o deja de emitir, la tarjeta marca la señal como no disponible y deja de ofrecerla; la app nunca sustituye una emisora por otra inventada. `cityLat`/`cityLon` son coordenadas aproximadas de la ciudad para el mapa, **no** la ubicación del transmisor.
- El comparador verifica los streams antes de abrirlos (`POST /api/streams/check`) y sustituye por vecinas verificadas las cámaras cuyo token `otp` haya caducado; el mensaje del modal indica cuántas se sustituyeron.
