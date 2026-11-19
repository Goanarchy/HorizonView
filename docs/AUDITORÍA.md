# Auditoría de HorizonView

Fecha: 18 de noviembre de 2026. Servidor local `127.0.0.1:8770`, Chrome con CDP.

> **Estado final:** las cifras, el enlace vigente y la última etapa están en «Etapa 6: mapa vectorial MapLibre, radar, hechos viales y contexto costero» al final de este documento. Las secciones anteriores conservan el historial de verificaciones previas.
>
> **Enlaces:** todos los nombres `*.trycloudflare.com` citados en pasadas anteriores eran válidos al cerrar esa pasada, pero **ya caducaron** (Cloudflare Quick Tunnel cambia de hostname al reiniciar). El único vigente es `https://sam-provide-michel-install.trycloudflare.com/`, guardado en `URL_Movil.txt`.

## Verificado

### Inventario

- `GET /api/health` responde `200`: **1051 cámaras** (679 de 511NJ, 372 de DelDOT) y **420 streams** (48 HLS de 511NJ, 372 de DelDOT).
- `GET /api/cameras`, `/api/source`, `/assets/*` y `/` responden `200`.
- 511NJ: `getTourList` devolvió los tours oficiales; `getCameraDataByTourId` con `tourId=3` (NJ Turnpike Tour) devolvió 679 cámaras con coordenadas reales; 48 registros con `iconFile=cctv-red.png` tienen `cameraUseFlag=HLS` y URL de stream verificada en `getCameraDetail`.
- DelDOT: el feed `videocamera.json?id=4yte` devolvió `cameraCount=372`, con `timestamp=2026-11-18T04:30:50Z`, 207 cámaras en New Castle, 94 en Sussex y 71 en Kent.
- Ejemplos comprobados: `nj-55` → `MM 001.2 North of Delaware Memorial Bridge`, 39.680817 / -75.47113; `de-KCAM001` → stream HLS de `video.deldot.gov`.

### Reproducción y proxy

- Proxy NJ: playlist HLS `200`, 738 bytes, con segmentos `.ts` reescritos al proxy local.
- Proxy DelDOT: playlist maestra `200` → sub-playlist `200` → segmento `200` (`video/MP2T`, 346296 bytes).
- Selección real en navegador: cámara DelDOT reproducida con `readyState=4`, `videoWidth=1280`, `videoHeight=720`, `currentTime` avanzando, `paused=false` y sin errores del reproductor.

### GPS

- Con permiso concedido y ubicación simulada en `39.680817, -75.47113`:
  - mensaje: «La cámara más cercana es MM 001.2 North of Delaware Memorial Bridge (0 m)»;
  - orden cambiado a distancia;
  - grupos «Más cercanas · 10» y «Resto del inventario · 1041»;
  - primera fila con distancia `0 m`.

### Actualización

- `POST /api/refresh {"kind":"de"}`: estado `done`, archivo `de_cameras.json` reescrito, 372 cámaras / 372 streams.
- `POST /api/refresh {"kind":"nj"}`: estado `done`, archivo `nj_cameras.json` reescrito, 679 cámaras / 48 streams; registro: «Inventario: 679 cámaras», «Detalles: 48 cámaras de la ruta», «Detalles capturados: 48».
- Durante la auditoría se corrigió un fallo real: el refresco de 511NJ no consumía los eventos del CDP antes de leer las respuestas. Tras añadir el drenaje de eventos, el refresco funciona de extremo a extremo.

### Acceso online (enlace fijo)

- Enlace fijo: `https://horizonviewnjtp.2600-4040-afd7-bb00-b1da-3188-4db-2b19.sslip.io/` (sin cuenta, sin interstitial; DNS gratuito sslip.io + Caddy con CA local en el usuario).
- Procesos activos: servidor local `src/server.py` PID 22540 y proxy `caddy.exe` PID 23308. Los antiguos túneles Cloudflare y Serveo se detuvieron.
- A través de la URL fija: `/api/health` devuelve `200`, `ok=true`, 1051 cámaras y 420 streams; `/api/cameras` devuelve 1051 cámaras.
- El proxy HLS de `nj-55` responde `200` con playlist M3U8 de 738 bytes y segmentos relativos reescritos al propio proxy.
- En Chrome con la URL fija: `window.isSecureContext=true`, API del mismo origen operativa y `navigator.geolocation` devuelve `39.680817,-75.47113` con permiso concedido y coordenada simulada por CDP.
- Reproducción real verificada previamente en el visor (`readyState=4`, 1280×720, video avanzando, sin errores JS); el proxy HTTPS actual sirve la misma playlist y los mismos segmentos.
- El enlace permanece estable mientras la IPv6 pública no cambie y el equipo siga encendido; no regenera una URL nueva en cada ejecución.

### Tema y guía

- Tema inicial: noche.
- Al pulsar el botón de tema: `light`, guardado en `localStorage.horizonViewTema`; tras recargar, sigue `light`.
- `?theme=dark` fuerza el tema noche aunque `localStorage` indique claro.
- Guía: se abre la primera vez, se puede recorrer con «Siguiente» y volver a abrir con «Guía»; los cinco pasos y sus imágenes cargan.

### Geometría, contraste y errores

Seis casos auditados con Chrome CDP:

| Caso | ancho × alto | tema | wizard | oob | clipped | tiny | overlaps | contraste | errores JS |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1360-dark | 1360×900 | noche | cerrado | 0 | 0 | 0 | 0 | 0 | 0 |
| 1024-dark | 1024×820 | noche | cerrado | 0 | 0 | 0 | 0 | 0 | 0 |
| 768-dark | 768×900 | noche | cerrado | 0 | 0 | 0 | 0 | 0 | 0 |
| 545-light | 545×900 | claro | cerrado | 0 | 0 | 0 | 0 | 0 | 0 |
| 1360-light | 1360×900 | claro | cerrado | 0 | 0 | 0 | 0 | 0 | 0 |
| 1360-wizard | 1360×900 | noche | abierto | 0 | 0 | 0 | 0 | 0 | 0 |

- `oob`: elementos fuera del viewport.
- `clipped`: texto recortado por `overflow`.
- `tiny`: texto por debajo de 9 px.
- `overlaps`: controles interactivos superpuestos (con recorte por contenedores con scroll correctamente descartado).
- `contraste`: pares de texto/fondo por debajo del umbral aplicable.
- Se corrigieron tres fallos reales durante la auditoría: uso de `.add()` en contenedores no-select (lista y wizard vacíos), contraste insuficiente en el icono de búsqueda y en la nota del visor, y contraste del pie de página en tema claro.

Capturas y datos crudos: `audit_final.json` en esta carpeta.

## Inferido

- **Zonas de Nueva Jersey**: «NJ · Turnpike», «NJ · I-295 / I-76» y «NJ · Vías adyacentes» se derivan del nombre de la cámara y del icono rojo/verde del feed de 511NJ. No son etiquetas oficiales.
- **«En ruta» en Nueva Jersey**: se considera en ruta si el icono es `cctv-red.png` o si el nombre contiene «Turnpike». Es una clasificación derivada del feed.
- **«En ruta» en Delaware**: se considera en ruta si `county == "New Castle"`. Es una aproximación al corredor, no un campo oficial de pertenencia a ruta.
- **Disponibilidad del stream**: el badge «En vivo» significa que la fuente oficial expone una URL HLS; no garantiza que el video esté emitiendo en ese instante.

## No verificado

- Que todas y cada una de las 420 URLs HLS estén operativas en un momento dado: solo se probaron individualmente `nj-55` y `de-KCAM001`, además de la reproducción real de una cámara DelDOT.
- Que 511NJ mantenga sin cambios su mecanismo de prueba WebCrypto: el refresco depende de la app oficial cargada en un Chrome real y puede requerir ajustes si la agencia modifica ese mecanismo.
- La precisión cartográfica sub-metro de las coordenadas: se conservan tal como las publican 511NJ y DelDOT, sin reprocesamiento geodésico.
- Cualquier recomendación de uso en carretera: la aplicación es un visor informativo, no un sistema de navegación ni de seguridad vial.

---

## Rediseño móvil y acceso desde celular (18 de noviembre de 2026, segunda pasada)

### Acceso público con certificado válido

- Se añadió `start-mobile.ps1` / `.bat`: levanta el servidor local, crea un túnel HTTPS de Cloudflare, espera a que el nombre DNS resuelva (con `ipconfig /flushdns` para evitar cache negativo), comprueba `/api/health` a través del túnel, guarda `URL_Movil.txt` y genera `assets/qr-movil.png` con `qrcode` de Python.
- Enlace generado durante la verificación: `https://sprint-chris-techrepublic-hampton.trycloudflare.com/`.
- A través de ese enlace, Chrome reportó contexto seguro y `navigator.geolocation` funcionó con permiso concedido y coordenada simulada: **no hace falta instalar certificados en el teléfono**.
- El enlace fijo anterior (`sslip.io` + `tls internal`) se conserva como modo legado, pero no es adecuado para celulares ajenos por su certificado de CA local.

### Verificación de extremo a extremo (`tests/verify_mobile.py`)

Ejecutada contra el enlace público, con Chrome CDP, coordenada simulada `39.680817, -75.47113` y permiso de geolocalización concedido:

| Comprobación | Resultado |
|---|---|
| Inventario cargado | 1051 cámaras, contador «1051 / 1051 cámaras» |
| Pestaña «Cerca» + GPS | 10 tarjetas, precisión ±5 m |
| Cámara más cercana | `MM 001.2 North of Delaware Memorial Bridge`, **0 m** |
| Selección desde «Cerca» | visor abierto con esa cámara y badge «En vivo» |
| Reproducción HLS | `readyState=4`, `videoWidth=853`, sin error de reproductor |
| Controles de zoom | barra de zoom visible sobre el escenario |
| Errores JS / consola | 0 |

Capturas: `docs/screenshots/horizonview-movil-dark.png`, `horizonview-movil-light.png` y `horizonview-escritorio-light.png`.

### Auditoría geométrica a 390×844 (`tests/audit_ui.py`)

Cuatro estados revisados (tema noche, tema día, pestaña «Cerca» y guía abierta):

- `scrollWidth = 390` = `innerWidth`: **sin desbordamiento horizontal**.
- Elementos fuera del viewport: **0**; texto recortado por `overflow`: **0**.
- Objetos interactivos por debajo de 40 px: solo los dos botones del conmutador (38 px dentro de un contenedor de 44 px) y las dos casillas nativas (20 px dentro de etiquetas de 42 px). Tamaño táctil efectivo correcto.
- Barra inferior de pestañas visible en móvil (`display:grid`) y oculta en escritorio, donde el inventario y el visor se muestran en dos columnas.
- Errores JS: **0**.

### Controles de cámara

Se revisaron los 1051 registros normalizados y las claves expuestas por las fuentes: no existe ningún campo `ptz`, `pan`, `tilt`, `zoom` ni URL de control (0 coincidencias). Las agencias publican solo streams HLS de observación. En consecuencia:

- No se han inventado controles PTZ remotos.
- Los controles implementados son de reproducción (play, sonido, pantalla completa, captura, compartir) y **zoom/paneo digital** sobre la imagen, marcados explícitamente como digitales en la guía y en el visor.

Otros cambios: interfaz rediseñada mobile-first (Liquid Glass + Bento + pestañas inferiores), filtro «Con video», opción de 50 cámaras cercanas, enlace compartible `?cam=<id>`, endpoint `/api/mobile`, guía ampliada a seis pasos y respaldo de la versión anterior en `_backup_v1/`.

---

## Categoría «Locales en vivo» (18 de noviembre de 2026, tercera pasada)

### Motor de búsqueda y filtro

- Nuevo `POST /api/nearby`: calcula distancias con Haversine, filtra cámaras con `enabled !== false`, `status` no disponible/offline/inactivo y con URL HLS, y comprueba en paralelo (8 hilos) que la playlist responda `#EXTM3U` y que el primer segmento de video devuelva datos.
- Cache de 5 minutos por coordenadas redondeadas, radio y límite; el botón «Verificar de nuevo» envía `force: true`.
- La categoría busca en todo el inventario oficial (511NJ + DelDOT), sin limitar por zona ni por marca «en ruta».

### Verificación contra el enlace público (Chrome CDP, GPS simulado)

| Comprobación | Resultado |
|---|---|
| Ubicación simulada | `39.680817, -75.47113`, precisión ±5 m |
| Candidatas en 25 km | **173** con stream y operativas |
| Candidatas comprobadas | **173** (playlist + segmento) |
| Cámaras mostradas en «Locales» | **173**, todas con hora de verificación |
| Cámaras sin stream en la lista | **0** |
| Cámaras dadas de baja / no disponibles en la lista | **0** |
| Cámaras en «Cerca» | 10 primeras de la lista verificada; la más cercana a 0 m |
| Reproducción desde «Locales» | `readyState=4`, `videoWidth=853`, sin error |
| Errores JS | **0** |

Captura adicional: `docs/screenshots/horizonview-movil-locales.png`.

Prueba directa del endpoint con `radiusKm=25, limit=200, force=true`: 173 candidatas, 173 verificadas en ~9 s.

### Geometría

La auditoría a 390×844 se repitió con la cuarta pestaña («Locales»): sin desbordamiento horizontal (`scrollWidth=390`), 0 elementos fuera del viewport, 0 textos recortados y 0 errores JS. Los únicos objetivos táctiles por debajo de 40 px siguen siendo los botones del conmutador (38 px dentro de un contenedor de 44 px) y las casillas nativas (20 px dentro de etiquetas de 42 px).

### Límite declarado

«Cualquier tipo de cámara pública» se refiere a cualquier cámara pública incluida en los dos inventarios oficiales. No se han añadido fuentes de terceros sin verificar, para cumplir el requisito de que solo se muestren cámaras que funcionan.

---

## Cobertura estatal y filtro de cámaras fallidas (18 de noviembre de 2026, cuarta pasada)

### Diagnóstico de las dos quejas

- El inventario de 511NJ tenía **679 cámaras pero solo 48 con stream**: el refresco anterior leía únicamente las cámaras «rojas» del NJ Turnpike Tour.
- `getCameraDataByTourId` devuelve las **679 cámaras de todo el estado con cualquier `tourId`**; la app oficial ofrece **85 tours** (Garden State Parkway, I‑80, I‑295, NJ‑21, US‑1, etc.).
- `getCameraDetail` devuelve streams para la mayoría de esas cámaras. Muestreo inicial: **10 de 12** tenían HLS real, incluidas cámaras «verdes» que antes se descartaban.
- `de-KCAM001` respondía `404` en su playlist y aparecía en el inventario general: era una de las cámaras «que no funcionan» que se veían en la lista.

### Cómo se obtuvo el inventario completo

511NJ firma cada petición con WebCrypto (`X-Browser-Proof`, de un solo uso) y cifra el cuerpo con AES‑128‑CBC (`X-Browser-Proof` reutilizado desde Python devuelve 403). Se reescribió `refresh.py` para:

1. Cargar `https://511nj.org/camera` en Chrome real con el perfil validado.
2. Capturar el inventario completo de `getCameraDataByTourId` (679 cámaras, 85 tours).
3. Interceptar `getCameraDetail` con CDP `Fetch`, dejar que la página firme la petición y sustituir el `encryptedData` por el `cameraId` deseado.
4. Recargar el navegador cada 150 cámaras y capturar los 679 detalles.

Resultado: **`nj_cameras.json` pasó de 48 a 670 streams**. Junto con DelDOT (372), el total es **1042 streams sobre 1051 cámaras**. Después de excluir bajas y fallos, `GET /api/cameras` devuelve **1029 cámaras visibles y 22 excluidas**.

### Endurecimiento de la verificación

- `probe_stream()` ya no acepta solo HTTP 200: exige `#EXTM3U`, rechaza HTML/Cloudflare, sigue playlists maestras hasta la media playlist y comprueba hasta 3 segmentos.
- Acepta video real MPEG‑TS (sync byte `0x47`) o ISO BMFF (`ftyp`/`moof`/`mdat`/`styp`), no solo `Content-Length != 0`.
- Se añadió `nj-511.wink.co` a los hosts permitidos con `Referer: https://511nj.org/` y conservación del token `otp`.
- El proxy HLS reescribe ahora `EXT-X-KEY`, `EXT-X-MAP` (init fMP4), `EXT-X-PART` y `EXT-X-PRELOAD-HINT`, además de los segmentos normales. Sin esto, HLS.js pedía el `init.mp4` y los partial segments directamente al host remoto y fallaba con HTTP 400.
- `POST /api/stream-report` registra fallos fatales del reproductor; `is_operational()` oculta esas cámaras en `/api/cameras`, `/api/nearby` y la interfaz durante 6 horas. `de-KCAM001` queda excluido permanentemente hasta que cambie su URL.
- Si el GPS no encuentra cámaras a 25 km, la interfaz prueba automáticamente 50 y 100 km y explica que la cobertura oficial es Nueva Jersey y Delaware.

### Pruebas finales

Enlace público regenerado: **`https://compute-proven-undefined-mid.trycloudflare.com/`**, `/api/health` = 200.

| Comprobación | Resultado |
|---|---|
| Inventario por HTTPS | 1029 visibles, 22 excluidas, 1042 streams en el total |
| GPS en Turnpike (`39.680817, -75.47113`) | 170 verificadas en 25 km; la más cercana a **0 m** |
| GPS en **Newark** (`40.7355, -74.1724`), fuera del Turnpike | **134 verificadas**; la más cercana `NJ-21 @ Hamilton Street` a **579 m** |
| Cámara fMP4 del nuevo host (`nj-10710`) | `readyState=4`, `videoWidth=768`, `currentTime=26.2`, sin errores ni HTTP ≥400 |
| Cámara TS del Turnpike (`nj-55`) | `readyState=4`, `videoWidth=853`, sin errores |
| Proxy `nj-511.wink.co` | playlist maestra → media → `init.mp4` (`ftyp`) → segmento (`video/mp4`) |
| Reporte de fallo | `POST /api/stream-report` devuelve `ok=true, hidden=true` y crea el registro persistente |
| Auditoría 390×844 (5 estados) | `scrollWidth=390`, 0 fuera, 0 recortados, 0 errores JS |

Scripts añadidos: `tests/verify_fmp4.py` y `tests/verify_gps_newark.py`. Capturas: `docs/screenshots/horizonview-fmp4-nuevo-host.png` y `docs/screenshots/horizonview-gps-newark.png`.

### Límite actual

La cobertura sigue siendo exclusivamente de los inventarios oficiales de 511NJ y DelDOT. Un GPS fuera de NJ/DE no tendrá cámaras cercanas hasta añadir nuevas fuentes oficiales. Los tokens `otp` de `nj-511.wink.co` los emite la app oficial en cada captura; si expiran, esas cámaras se descartan en la verificación y habría que volver a ejecutar `python refresh.py`.

## Etapa 1: enlace estable, reporte manual y favoritos (18 de noviembre de 2026, quinta pasada)

### Enlace fijo gratuito

- Nuevos lanzadores **`start-stable.bat` / `.ps1`**: detectan `tailscale.exe` en PATH o en `C:\Program Files\Tailscale\tailscale.exe`, comprueban la sesión con `tailscale status --json`, activan `tailscale funnel --bg 8770`, extraen la URL `https://<maquina>.<tailnet>.ts.net`, guardan `URL_Movil.txt`, regeneran el QR y verifican `/api/health`.
- Si Tailscale no está instalado o no hay sesión, el script delega automáticamente en `start-mobile.ps1` (Cloudflare Quick Tunnel). En esta máquina `TAILSCALE=NO`, así que el enlace fijo queda **listo para activarse** sin instalar nada sin confirmación.
- Tailscale Funnel está disponible en todos los planes, incluido el personal gratuito; el hostname no cambia entre reinicios y el certificado es público. Para detenerlo: `tailscale funnel off`.
- Enlace vigente de respaldo tras la pasada: **`https://rob-searched-study-cultures.trycloudflare.com/`**, `/api/health` = 200.

### Favoritos y reporte manual

- `LS.favs = "horizonViewFavoritos"` guarda un arreglo de IDs en `localStorage`; al cargar se reconstruye `state.favs`. La estrella aparece en el inventario, en «Cerca», en «Locales» y en el visor.
- El filtro **«Solo favoritos»** (`#favOnly`) se aplica al inventario; mensaje específico cuando aún no hay favoritos.
- `btnFav` muestra `☆ Favorito` / `★ Guardado` y `syncFavUI()` mantiene sincronizadas todas las estrellas y el visor.
- `btnReport` usa confirmación en dos toques («⚠ Confirmar fallo», expira en 5 s o se reinicia al cambiar de cámara) y llama a `reportBroken(c, "reporte manual")`, el mismo camino del reporte automático por fallo fatal HLS.

### Verificación de la etapa 1

`python tests/verify_stage1.py` contra el enlace HTTPS, Chrome CDP, 390×844:

| Comprobación | Resultado |
|---|---|
| Guardar favorito desde el inventario | `de-KCAM181` quedó en `localStorage`, 1 estrella activa |
| Filtro «Solo favoritos» | `1 / 1025 cámaras`, 1 fila |
| Visor con favorito | `★ Guardado`, botón habilitado, «Reportar fallo» habilitado |
| Confirmación de reporte | Primer toque: `⚠ Confirmar fallo`; al cambiar de cámara vuelve a `⚑ Reportar fallo` |
| Persistencia tras recarga | ID y estrella conservados |
| Errores | 0 errores JS, 0 HTTP ≥400 |

`python tests/audit_ui.py` a 390×844, cinco estados (noche, día, Cerca, Locales, guía): `scrollWidth=390`, 0 fuera del viewport, 0 textos recortados, 0 errores JS. La estrella mide 36×40 px en móvil (objetivo táctil ≥40 px de alto). `python tests/verify_mobile.py` volvió a reproducir `nj-55` con `readyState=4`, `videoWidth=853`, 170–173 cámaras verificadas en 25 km y sin errores. Los registros temporales de fallo generados por las pruebas se limpiaron y el servidor se reinició; `/api/cameras` quedó en **1026 visibles** al cerrar la pasada (el filtro automático puede reducirlo transitoriamente).

> No se pulsó la confirmación final del reporte manual durante la auditoría para no ocultar una cámara funcionante; el camino `POST /api/stream-report` ya había sido verificado en la pasada anterior.

## Etapa 2: mapa interactivo y tours oficiales (18 de noviembre de 2026, sexta pasada)

### Pertenencia real a los tours de 511NJ

- El inventario normalizado no guardaba la pertenencia a tours, así que no se infirió nada a partir de los nombres.
- `refresh.py` ahora conserva la respuesta cruda en `data/nj_raw_inventory.json` (679 cámaras) y la lista completa de tours con sus IDs (85). Con `NJ_TOURS_ONLY=1` solo captura ese material, sin repetir los 679 detalles de stream.
- El código de la app oficial mostró que el cuerpo cifrado de `getCameraDataByTourId` es `{"tourId": <id>}`. `scripts/nj_tours_capture.py` deja que la página firme una petición real, intercepta el cuerpo con CDP `Fetch` y lo sustituye para cada uno de los 85 tours, alternando el `li.pure-checkbox` clicado para forzar una petición nueva.
- Resultado en `data/nj_tours.json`: **85 tours**, 808 IDs de cámaras mencionados (incluye 126 IDs de otros listados no presentes en el inventario unificado; el servidor los ignora) y pertenencia real por cámara. Ejemplo: `nj-51` pertenece a 5 tours. El tour `NJ Turnpike Tour` devuelve las 679 cámaras del inventario, tal como publica la agencia. Cinco tours están vacíos en la fuente actual.
- `GET /api/tours` expone los 85 tours con su número de cámaras; `/api/cameras` añade `tours` a cada cámara 511NJ. En esta máquina `nj-51` llegó con 5 tours y el total visible sigue siendo 1026.

### Mapa

- Nueva pestaña «Mapa» (la navegación inferior pasa a 5 pestañas) con **Leaflet 1.9.4 servido localmente** (`assets/leaflet.js`, `assets/leaflet.css`, licencia BSD-2) y teselas gratuitas CARTO/OSM claro u oscuro según el tema. Atribución visible en la leyenda.
- `L.circleMarker` sobre renderer Canvas para las cámaras filtradas: ámbar para 511NJ, cian para DelDOT, relleno verde para las verificadas en vivo, blanco y mayor radio para la seleccionada. Tooltip con nombre y distancia; al tocar un punto se abre el visor.
- Controles: «Mi ubicación» (pide GPS sin resetear filtros ni cambiar de pestaña), «Ajustar» (`fitBounds` de los resultados), toggle «Solo verificadas en vivo» y círculo de precisión del usuario.
- El filtro de tours del inventario (`#tour`) también afecta al mapa porque ambos usan `filtered()`.

### Pruebas de la etapa 2

| Comprobación | Resultado |
|---|---|
| `GET /api/tours` | 85 tours |
| Selector de tours | 86 opciones (todos + 85); primera `Garden State Parkway Tour · 612` |
| Filtro `NJ Turnpike Tour` | `665 / 1026 cámaras`, 665 filas, sin errores |
| Pestaña Mapa | canvas Leaflet activo, **9 teselas cargadas**, contador `1026 cámaras` |
| Toggle «Solo verificadas» sin GPS | `0 cámaras · 0 con video verificado` (correcto) |
| `tests/audit_ui.py` a 390×844, ahora 6 estados | `scrollWidth=390`, 0 fuera del viewport, 0 recortados, 0 errores JS |
| Zoom de Leaflet | botones ampliados a 40×40 px para objetivo táctil |
| `tests/verify_mobile.py` | GPS 171 verificadas, `nj-55` con `readyState=4`, `videoWidth=853`, sin errores |
| `tests/verify_stage1.py` | favoritos, filtro y reporte manual siguen funcionando |

Enlace público regenerado durante la pasada: **`https://flights-acute-penetration-sail.trycloudflare.com/`**, `/api/health` = 200. No quedó archivo `data/stream_failures.json` al cerrar la auditoría.

> Las teselas se descargan del proveedor en cada sesión; si no hay internet, el mapa queda vacío pero el inventario, el GPS, los tours, los favoritos y los streams siguen funcionando. No se usa ningún servicio de mapas de pago ni clave API.

## Etapa 3: IA explicable, categoría IA y Tours narrados (18 de noviembre de 2026, séptima pasada)

### Fuentes públicas nuevas, verificadas una por una

`python tests/verify_new_sources.py` contra Internet real:

| Fuente | Respuesta | Uso |
|---|---|---|
| Open‑Meteo `forecast?latitude=39.68…` | `200`, 526 bytes | clima actual en la coordenada de la cámara |
| NWS `points/39.68,-75.47` | `200`, 3906 bytes | punto de alertas activas de NOAA |
| Overpass `way[highway=construction]` | `200`, 1248 bytes | obras viales de OpenStreetMap bajo demanda |

También se comprobaron `api.weather.gov/alerts/active?area=NJ,DE`, OSRM y Nominatim dentro de `tests/verify_ai.py`. Ninguna requiere clave; Nominatim se llama con `User-Agent` y caché de 24 h.

### Feed real de eventos 511NJ

- El servicio `highwayEventsService.getEvents()` se define en `https://511nj.org/chunk-AKFIZP2K.js`, línea 2, columna ~26014, y publica `POST https://511nj.org/client/get/event`.
- El cuerpo es `{"isScheduleEvent":false}` cifrado AES‑CBC con la misma clave/IV que el resto de la app (`lIo3M)_83,ALC0Wz` / `.%A}8Qvqm23jYVc9`), más `X-Browser-Proof`, `X-Browser-Public-Key`, `X-XSRF-TOKEN` y `Token`. Una prueba controlada con CDP `Fetch` demostró que el cuerpo plano devuelve HTTP 500: el cifrado y la firma son obligatorios.
- `scripts/nj_events_capture.py` deja que la propia página firme la petición y lee la respuesta real con `Network.getResponseBody`. Resultado: **404 eventos**, **131 de NJ/DE**, guardados en `data/nj_events.json` con hora de captura. Categorías verificadas: 120 `Construction`, 5 `Detour`, 3 `Incident`, 1 `Congestion`, 2 `Special Events`.
- Los eventos se usan como contexto verificable en «IA · Contexto», «Alertas por zona» y «Capas del mapa». No se afirma nada que la agencia no haya publicado, y el feed es una captura puntual, no una suscripción.

### Núcleo IA y reglas de seguridad

- `ai.py` implementa 16 capacidades deterministas: radar de confianza, copiloto de ruta, lenguaje natural, contexto, resumen, grupos, alertas, capas, tours y comparador, entre otras. No hay LLM, llamadas de pago ni análisis de imagen.
- `score_camera()` devuelve `trust`, `trustLabel`, `trustConfidence`, `trustReasons` y `trustNote`. Esos campos se añaden a los 1026 registros de `GET /api/cameras`; el puntaje mide calidad del dato, nunca tráfico ni contenido de video.
- `record_signal()` alimenta `data/ai_signals.json` solo con aciertos/fallos locales de reproducción, sin datos personales. `/api/nearby` y `/api/stream-report` ya registran señales reales.
- Auditoría de seguridad semántica: las respuestas fueron comprobadas contra `ptz`, `pan/tilt`, `zoom remoto` y `control remoto`; **0 coincidencias** en inventario, asistente, ruta y capas. No se reconocen rostros, placas ni vehículos.

### Pruebas de la etapa 3

`python tests/verify_ai.py` contra `127.0.0.1:8770`: **30 correctas, 0 fallidas**.

| Comprobación | Resultado |
|---|---|
| `GET /api/health`, `/api/cameras` | 1051 totales, 1026 visibles, confianza presente en todos |
| `GET /api/events` | 131 eventos NJ/DE, categorías y fuente con hora |
| `GET /api/ai/stats`, `/api/geocode` | historial local operativo; `Newark, Essex County, New Jersey` resuelto por Nominatim |
| `POST /api/ai/query` | 123 cámaras para «con video cerca de Newark NJ»; 679 para «tour NJ Turnpike Tour», con interpretación y fuentes |
| `POST /api/ai/route` | Newark → Trenton: 82,4 km, 12 cámaras a ≤2,5 km, polilínea y 3 fuentes |
| `POST /api/ai/brief` | resumen basado en favoritos, con clima y alertas |
| `POST /api/ai/alerts` | 7 señales, cada una con texto, evidencia y fuente |
| `POST /api/ai/groups`, `/context`, `/compare` | grupos por corredor/tour; 8 eventos cerca de la cámara; recomendación de fuente con distancias reales |
| `POST /api/ai/tour` | `NJ Turnpike Tour`, 10 pasos con coordenadas e IDs reales |
| `GET /api/ai/layers` | 26 capas (NWS + Open‑Meteo + eventos 511NJ), sin controles inventados |

Durante la pasada se detectaron y corrigieron tres fallos reales antes de cerrar: desempaquetado invertido de `nearest()` (devuelve `(distancia, cámara)`), variable `needle` sin asignar en combinación de filtros, y prioridad del tour sobre la zona genérica en lenguaje natural. Tras las correcciones, la suite completa pasó sin errores.

### Interfaz y auditoría visual

- La navegación inferior pasa a **7 pestañas**: Cámaras, Cerca, Mapa, Locales, **IA**, **Tours** y Visor. IA y Tours son categorías aparte; Tours ya no vive dentro del visor.
- La pestaña IA tiene ocho tarjetas desplegables, botones de ejemplo, visualización del razonamiento, enlaces «Ver datos», botón para quitar el filtro IA, ruta dibujable en el mapa y comparador modal con hasta 4 videos HLS simultáneos.
- La pestaña Tours permite elegir cualquiera de los 85 tours oficiales, genera pasos reales y los narra con `speechSynthesis` del dispositivo. El texto incluye coordenadas, distancias al paso anterior y al usuario, y fuente 511NJ.
- El mapa incorpora el toggle «Capas IA: clima / obras»; al activarlo consulta NWS, Open‑Meteo, eventos 511NJ y Overpass, dibuja marcadores por tipo y muestra el recuento. En la prueba: `9 capas: Evento 511NJ 8 · Clima actual 1`.
- `python tests/audit_ui.py` ampliado a **14 estados** a 390×844 (noche, claro, Cerca, Locales, Mapa, IA, Tours, pregunta IA, ruta, alertas, grupos, contexto, comparador, tours narrados, capas y guía): `scrollWidth=390`, **0 fuera del viewport**, **0 recortados**, **0 errores JS**, **0 HTTP ≥400**. Sondas: 30 resultados de IA, 12 cámaras de ruta, 16 bloques de alertas, 3 bloques de contexto, 4 tarjetas de comparador, 10 pasos de tour y 9 capas en el mapa.
- La elipsis intencional de títulos largos y los campos de texto nativos se excluyen del conteo de recortes porque no suponen pérdida visual; el auditor ahora separa correctamente «fuera» de «recortado».

### Regresiones

| Script | Resultado |
|---|---|
| `python tests/verify_map.py` | 86 opciones de tour, filtro `665 / 1026`, 9 teselas, 0 errores |
| `python tests/verify_mobile.py` | GPS 170 verificadas a 25 km, `nj-55` `readyState=4`, `videoWidth=853`, 0 errores |
| `python tests/verify_stage1.py` | favoritos, filtro y reporte manual siguen funcionando |
| `node --check src/app.js`, `python -m py_compile src/ai.py src/server.py` | `JS_OK`, `PY_OK` |

Enlace vigente al cerrar la pasada: **`https://flights-acute-penetration-sail.trycloudflare.com/`**, `/api/health` = 200. Tailscale sigue sin instalarse en esta máquina (`TAILSCALE=NO`), así que el hostname fijo `*.ts.net` continúa pendiente de confirmación del usuario; el túnel Cloudflare puede cambiar de hostname al reiniciar.

> La IA no sustituye a las agencias: no predice tráfico, no interpreta video y no crea incidentes. Su valor está en traducir preguntas a datos verificables, explicar cada paso y dejar siempre un enlace «Ver datos» con fuente y hora.

## Etapa 4: zonas, clima animado, sensores, radio y herramientas combinadas (18 de noviembre de 2026, octava pasada)

### Zonas locales

- `data/local_zones.json`: Somerville (10), Raritan (6), Manville (7) y Bridgewater (5) cámaras, todas `enabled` con stream verificado. Es un overlay propio: `data/nj_cameras.json` no se modificó.
- `POST /api/cameras` devuelve 1023 visibles con el campo `zone` anotado; 11 cámaras caen en zonas. `GET /api/zones` devuelve los cuatro recuentos.
- En la interfaz, los chips filtran la lista (`Somerville · 10` → 10 filas, contador `10 / 1023 cámaras`) y se dibujan como capa en el mapa.

### Clima animado y NWR real

- `GET /api/weather/live?lat=40.6209&lon=-74.6085` → `200`, escena `clear-night`, temperatura 6,5 °C, 0 alertas, confianza 0.97, `ok: true`.
- **Corrección aplicada:** la frecuencia NWR no está en `points/<lat,lon>/radio` (404), sino en `https://api.weather.gov/radio/KWO35/broadcast`. Devuelve `162.55 MHz` y `SAME 034035`. El tile animado usa `data-anim=clear-night`; la tarjeta IA muestra 12 horas de pronóstico y el enlace a la fuente NWS.
- La auditoría excluye `.wscene` del conteo de desbordamiento: las sombras y seudoelementos de la escena climática salen del cajón a propósito.

### Sensores y frecuencias

- `GET /api/sensors` → `200`, 30 sensores USGS + 2 radios NOAA, confianza 0.95, `ok: true`. En la pestaña IA: 30 bloques y el texto «32 lecturas públicas · confianza 0.95». No se asume capacidad de sensor ni frecuencia: todo viene del registro público con hora y enlace.

### Estado del corredor

- `POST /api/ai/corridor` → `200`, nivel `amber`, `75/100 · Atención al corredor`, 1 evento 511NJ, 6 fuentes verificables en la tarjeta. Reglas sobre datos reales, no predicción de tráfico.

### Radio en vivo

- `data/radio_stations.json`: 5 emisoras (WBGO, WQXR Q2, NJ 101.5, 94.3 The Point, WFMU) con categorías `noticias`, `cultura`, `clasica`, `musica`, `comunitaria`, logos HTTPS (todos `200`) y `cityLat`/`cityLon` aproximados de la ciudad (no del transmisor).
- Verificación real: WBGO ICY `audio/mpeg`; WFMU ICY; WQXR Q2 `audio/aacp`; NJ 101.5 y 94.3 The Point HLS con 2 variantes y segmentos `.aac` en `d25j5qm9y8ulag.cloudfront.net`. Ese host de CloudFront se añadió a `RADIO_HOSTS` tras comprobar que es el CDN real de los segmentos (antes devolvía 400 en el proxy).
- `/api/radio/stream/<id>` sirve `audio/mpeg` para WBGO y HLS con 2 referencias reescritas para WJLK; los segmentos proxyficados devuelven `audio/aac` con bytes `ID3…` reales.
- La pestaña «Radio» (8.ª pestaña) muestra `5/5 emisoras verificadas`, 6 opciones de categoría, 5 logos y reproductor con metadata real (`HLS en vivo · 2 variante(s)`). La app no redistribuye ni graba la señal.

### Comparador y streams con token caducado

- 542 cámaras usan `nj-511.wink.co`; el token `otp` caduca por cámara, no globalmente. Muestra: `nj-12600`, `nj-12840` responden `200`; `nj-10000308`, `nj-12780`, `nj-11410`, `nj-10000314`, `nj-51` devuelven `404`.
- Se añadió `POST /api/streams/check` (verificación paralela, `ThreadPoolExecutor(max_workers=8)`) y el comparador sustituye las cámaras sin señal por vecinas verificadas, indicándolo en el encabezado. Con las IDs problemáticas: `working=[nj-10000179, nj-12600, nj-12840, nj-1, nj-69]`, `failed=[nj-11410, nj-10000314, nj-51]`.
- Se endurecieron `gate()` y `do_GET()` para que los `ConnectionAbortedError` (WinError 10053) al cancelar HLS desde el navegador no generen tracebacks.

### Regresiones y auditoría final (octava pasada)

| Script | Resultado |
|---|---|
| `python tests/verify_extras.py` | health 200 / 1051; cámaras 1023 visibles, 11 zonificadas; zonas 10/6/7/5; clima `clear-night` 6.5 °C, NWR `KWO35/162.55`, 0 alertas; sensores 30+2; radio 5/5; WBGO `audio/mpeg`, WJLK HLS 2 refs; corredor `amber 75` |
| `python tests/audit_ui.py` | **0 incidencias**, `scrollWidth=390`, 0 fuera, 0 recortados, 0 errores JS, `HTTP_ERRORES=[]` |
| Sondas de auditoría | comparador 4 tarjetas/4 videos; clima `clear-night` + 12 horas + NWR; corredor `75/100`; sensores 30 bloques; radio 5 emisoras/6 categorías/5 logos y audio HLS; **ICY real en navegador**: WBGO `THIS STATION WILL CONTINUE AFTER THIS BREAK` · `Metadatos reales · HTTP 200`; mapa 9 capas y 43 combinadas; zona `Somerville · 10` → 10 filas |
| `python tests/verify_ai.py` | **30 correctas, 0 fallidas**; `/api/ai/stats` 170 OK / 8 fallos |
| `python tests/verify_map.py` | 86 tours, filtro `662 / 1023`, 9 teselas, 0 errores |
| `python tests/verify_stage1.py` | favoritos, filtro y reporte manual OK |
| `python tests/verify_mobile.py` | GPS 158 verificadas ±5 m, `nj-55` `readyState=4` `videoWidth=853`, 0 errores |
| `node --check src/app.js`, `python -m py_compile …` | `JS_OK`, `PY_OK` |

> Nota sobre `verify_map.py`: el selector `#map .leaflet-container` del diagnóstico está desactualizado (Leaflet aplica la clase al propio `#map`); el canvas y las 9 teselas cargadas confirman que el mapa funciona. No es una regresión.

Enlace vigente al cerrar la pasada: **`https://flights-acute-penetration-sail.trycloudflare.com/`**, `/api/health` = 200. Tailscale sigue sin instalarse (`TAILSCALE=NO`), por lo que el hostname fijo `*.ts.net` queda pendiente de confirmación del usuario; el túnel Cloudflare puede cambiar de hostname al reiniciar.

## Etapa 5: experiencia principal de conducción (19 de noviembre de 2026, novena pasada)

### Cambio de interfaz

- La pantalla de entrada pregunta **«Viajar hacia un lugar» / «Usar los datos»**. «Viajar» abre el asistente de destino, estilo y música; «Usar los datos» abre la administración anterior. El botón **«Datos»** (☰) del HUD permite volver a ella en cualquier momento; la pestaña **«Viaje»** es la décima entrada y devuelve a la experiencia.
- `?nowizard=1` y `?mode=admin` omiten el onboarding para no romper enlaces ni pruebas previas.
- `verify_drive.py` (Chrome CDP, 390×844): modal inicial visible, 9 pestañas visibles en la barra administrativa, 5 perfiles, 6 destinos rápidos, ruta Somerville → Newark de **46,7 km / 43 min / 40 cámaras**, teselas cargadas, HUD con ETA/restante/próxima cámara, cámara emergente real (`I-287 @ Cedarbrook Road`, **406 m antes**, video HLS vía proxy), bitácora con 3 eventos y botón «Datos» funcional. `ERRORES: []`, `HTTP: []`.
- Geometría del HUD a 390 px: `scroll=390`, 0 elementos fuera, 0 recortados, 0 targets táctiles pequeños.

### Correcciones aplicadas durante la pasada

- `tick()` ya no se detiene con `document.hidden`; `dt` se limita a 3 s para evitar saltos al volver a la pestaña. Verificado: progreso `0,64 % → 1,07 %` en diez segundos con la pestaña en segundo plano.
- Las cámaras emergentes ignoran las que están al inicio (`atKm > minAt`, con `minAt = min(0,8, 6 % de la ruta)`) o lejos del trazado (`offRouteKm <= bufferKm` del perfil). Antes se repetían cámaras a 4,7 km de la ruta; ahora la primera es `I-287 @ Cedarbrook Road` a 2,5 km.
- Los chips contextuales se renderizan al llegar cada fuente, no solo al final de `Promise.all`: en la sonda aparecieron «40 servicios en ruta», «131 eventos 511NJ», la emisora y «40 cámaras en la ruta» mientras la ruta avanzaba.
- `applyLayerVisibility()` respeta los interruptores de cámaras, servicios, alertas y sensores del panel del HUD.

### APIs conectadas en esta pasada

- `GET /api/geocode?q=&limit=1..8` → sugerencias reales de Nominatim; `Newark, NJ` resolvió a `Newark, Essex County, New Jersey, United States` (40.7357, -74.1724).
- `GET /api/reverse?lat=&lon=` → vía actual con fuente OSM y hora. Ejemplo: `Carolkim Drive, Bridgewater Township, Nueva Jersey`, `https://www.openstreetmap.org/way/11779853`. En el HUD: «Estás en Carolkim Drive» con el título de procedencia. Caché de 24 h y redondeo a ~100 m para cumplir la política de uso de Nominatim.
- `POST /api/trip/services` → servicios sobre la polilínea real. Tras probar cinco mirrors se eligió `overpass.openstreetmap.fr` como principal (`overpass-api.de` devolvió 502 por saturación y `kumi.systems` agotó el tiempo de espera). La consulta usa hasta seis cajas pequeñas, cabeceras `User-Agent`/`Accept`, deduplicación por `type/id` y el separador final `;)` que exige ese mirror. Resultado: **`count: 40`**, fuente `OpenStreetMap / Overpass`.
- `GET /api/weather/live` → campo `air` de Open-Meteo Air Quality: **`usAqi 36`, `pm2_5 17,8`**, con su propia fuente y hora.
- La ficha «Ver procedencia» incluye ahora Nominatim reverse junto al resto de fuentes.

### Regresiones finales

| Script | Resultado |
|---|---|
| `python -u tests/audit_ui.py` | **0 incidencias**, `scroll=390`, `HTTP_ERRORES=[]`, `ERRORES=[]` |
| `python -u tests/verify_drive.py` | onboarding, setup, ruta, HUD, chips, spotlight, bitácora y «Datos» OK; sin errores JS ni HTTP |
| `python -u tests/verify_extras.py` | health 200 / 1051; 1023 visibles; clima con NWR real; 30+2 sensores; radio 5/5; corredor `amber 75`; streams 4/4 |
| `python -u tests/verify_ai.py` | **30/30** correctas |
| `python -u tests/verify_map.py`, `verify_stage1.py`, `verify_mobile.py` | OK, sin regresiones |
| `python -m py_compile src/server.py src/extras.py src/ai.py`, `node --check src/app.js` | `PY_OK`, `JS_OK` |

Enlace público de testing de la pasada: `https://location-separate-design-lid.trycloudflare.com/` (ya caducado; ver «Etapa 6» para el vigente). Verificado a través del túnel: `/api/health` = 200, 1051 cámaras, 1042 streams, `ok: true`, HTTPS con certificado público válido para Android e iPhone. Tailscale sigue sin instalarse, así que el hostname fijo `*.ts.net` queda pendiente; Cloudflare regenera el enlace al ejecutar `start-mobile.ps1`.

---

## Etapa 6: mapa vectorial MapLibre, radar, hechos viales y contexto costero (19 de noviembre de 2026, décima pasada)

### Migración del mapa de conducción

- El mapa de la experiencia de conducción pasó de Leaflet a **MapLibre GL JS 5.6.0**, con `assets/maplibre-gl.js` y `assets/maplibre-gl.css` servidos localmente (sin CDN ni clave) y teselas vectoriales de CARTO: `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json` y `positron-gl-style/style.json`. Leaflet queda reservado al mapa de la interfaz administrativa (`tests/verify_map.py` sigue verificándolo).
- Renderizado en GPU y `easeTo`: zoom de conducción `DRIVE_ZOOM = 15.6` con seguimiento del vehículo; «Ver ruta completa» (`btnDriveOverview`) es un botón aparte que aleja a zoom 14 y desactiva el seguimiento, y «Recentrar» (`btnDriveRecenter`) vuelve a 15.6 y lo reactiva.
- El cambio de tema usa `map.setStyle`, sin reconstruir la app; las capas GeoJSON propias se reinsertan sobre el nuevo estilo.
- El render vectorial se comprobó visualmente en `docs/screenshots/probe_maplibre.png`. En la auditoría de red `RED_FINAL` no aparecen `.mvt`: MapLibre descarga las teselas vectoriales dentro de un Web Worker, no como peticiones del hilo principal. No es un fallo.

### Capas nuevas y fuentes verificadas

| Capa | Endpoint | Fuente y comprobación |
|---|---|---|
| Lluvia | `GET /api/radar` | RainViewer (`api.rainviewer.com/public/weather-maps.json` → `tilecache.rainviewer.com`). En la prueba: `200`, `frames=8`, `host=https://tilecache.rainviewer.com`, atribución «Weather data by RainViewer» con enlace a `rainviewer.com`, visible en `driveAttrRadar` y ocultable con `dlRadar` |
| Hechos viales | `POST /api/roadfacts` | OpenStreetMap vía Overpass (`maxspeed`, `highway=speed_camera`). `200`, `count=15`, `cameras=0`, `limits=15` (otra corrida: 194 límites en la ruta larga). Cada objeto lleva nombre, valor, distancia al trazado y enlace a OSM |
| Contexto costero | `GET /api/coastal?lat=&lon=` | NOAA CO-OPS vía MDAPI + NHC. `200`, estación `The Battery` a 50,9 km (`near=true` según el criterio del colector), `waterLevel=1.312 m` en la corrida final, `storms=0`, con hora y fuente |

- `route_roadfacts()` pide ahora `out center 300`, calcula `_distance_to_route_km()` con proyección equirectangular local, ordena por distancia real al trazado y descarta lo que queda a más de 2 km. Antes `out center 40` devolvía los primeros 40 objetos por caja y descartaba el límite más cercano: en la ruta corta Somerville el `35 mph` de `Mount Vernon Road` estaba a 2,19 km del inicio y no aparecía; con el cambio quedó a **42–57 m** del trazado.
- Overpass se intenta con `overpass.openstreetmap.fr` y `overpass-api.de`, con `timeout=60` (se midió ~26–41 s en horas punta). Se retiró `overpass.kumi.systems` por timeouts de 45–60 s repetidos. Si fallan los dos espejos, `/api/roadfacts` responde `200` con `ok:false`, `items:[]` y una nota: la ruta sigue funcionando sin badge de límite.
- El badge `driveLimit` se verificó en el navegador: `35|false` (visible) con título `Mount Vernon Road · 35 mph · 651 m · OpenStreetMap`. El límite se presenta como dato cartográfico, nunca como señal oficial; no se inventaron cámaras de velocidad (`cameras=0`).
- Radio: la playlist oficial HLS de NJ 101.5 referencia segmentos publicitarios en `d1n065hnrro57i.cloudfront.net`. Se comprobó que el segmento devuelve `HTTP 200` con bytes `ID3…` y se añadió ese host a `RADIO_HOSTS`, eliminando cuatro errores 400 de la auditoría. No se añadió ningún host que la playlist oficial no referencie.

### Interacciones verificadas en el navegador

Sonda CDP ad-hoc (`verify_drive_interactions.py`, Chrome headless 390×844) sobre la ruta corta `40.6220,-74.6045`:

| Acción | Resultado |
|---|---|
| Estado inicial | `zoom 15.6`, `follow:true`, capas `drive-radar`, `drive-route-line`, `drive-cameras`, `drive-services`, `drive-alerts`, `drive-roadfacts`, `drive-coastal`; visibles radar, ruta, cámaras, viales y costa |
| `dlRadar` off/on | capa `drive-radar` desaparece/aparece y `driveAttrRadar` se oculta/muestra |
| `dlRoad` off/on | capa `drive-roadfacts` desaparece/aparece |
| `dlCoastal` off/on | capa `drive-coastal` desaparece/aparece |
| «Ver ruta completa» | `zoom 14`, `follow:false` |
| «Recentrar» | `zoom 15.6`, `follow:true` |
| Cambio de tema | `data-theme=light` y `setStyle` a `positron`; se restaura `dark-matter` al volver; capas propias presentes en ambos |
| Atribución | «Weather data by RainViewer» visible solo con la capa de radar activa |

### Regresiones finales (URL vigente)

| Script | Resultado |
|---|---|
| `python -u tests/verify_extras.py` | health `200`/1051; cámaras `200` visibles=1031; zonas 10/6/7/5; clima NWR `KWO35/162.55`; sensores 30+2; radio 5/5; corredor `amber 75`; streams 4/4; **radar `200` frames=8**; **roadfacts `200` count=15 cameras=0 limits=15**; **coastal `200` The Battery near=true water=1.312 storms=0** |
| `python -u tests/verify_drive.py` | zoom `15.6`, `loaded:true`, `tilesLoaded:true`, capas MapLibre presentes, `roadCount=194`, `radarCount=8`, `coastalStation="The Battery"`, `SPOTLIGHT_VISTO True`, `DATOS OK`, `GEOMETRIA … recortados:0`, `ERRORES []`, `HTTP []` |
| `python -u tests/audit_ui.py` | **0 incidencias**, `scroll=390`, `recortados=0`, `HTTP_ERRORES=[]`, `ERRORES=[]` |
| `python -u tests/verify_ai.py` | **30 correctas, 0 fallidas** |
| `python -u tests/verify_map.py`, `verify_stage1.py`, `verify_mobile.py` | OK ejecutados secuencialmente, sin regresiones |
| `python -m py_compile src/server.py src/extras.py src/ai.py`, `node --check src/app.js` | `PY_OK`, `JS_OK` |

> Durante la pasada, dos verificaciones CDP (`verify_map.py`, `verify_stage1.py`) fallaron al ejecutarse en paralelo porque comparten el puerto 9333 y porque un túnel caducado devolvía HTTP 530 / Error 1033. Se ejecutaron de nuevo de forma secuencial con el túnel vigente y pasaron. No fue una regresión de la app.

Enlace vigente al cerrar la auditoría: **`https://sam-provide-michel-install.trycloudflare.com/`**. Verificado por HTTPS con certificado público (`/api/health` = 200, 1051 cámaras, 1042 streams; `/src/app.js` y `/styles.css` = 200; título de HorizonView) y guardado en `URL_Movil.txt` junto con `assets/qr-movil.png`. Se generó con `HV_PORT=8771` para publicar la copia de HorizonView sin detener la instalación original en 8770. Tailscale sigue sin instalarse (`TAILSCALE=NO`), así que el hostname fijo `*.ts.net` continúa pendiente de confirmación; el equipo debe permanecer encendido y Cloudflare regenera el enlace al ejecutar `start-mobile.ps1`.
