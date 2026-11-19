# HorizonView — Next Version Roadmap (v1.1 & v2.0)

This roadmap summarizes the highest-impact upgrades prioritized after v1.0.0. For the full v1.0 verification record, see [RELEASE_NOTES.md](./RELEASE_NOTES.md) and [docs/AUDITORÍA.md](./docs/AUDITORÍA.md).

---

## v1.1 — Robustez de publicación y cobertura de datos

- **Enlace fijo por defecto:** simplificar `start-stable.bat` para que Tailscale Funnel sea el único mecanismo recomendado y Cloudflare quede como respaldo explícitamente marcado, con comprobación automática de `navigator.geolocation` tras publicar.
- **Refresco 511NJ programable:** permitir `scripts/refresh.py --tours-only` y `--events-only` desde la interfaz administrativa con progreso visible, sin relanzar el navegador para cada cámara.
- **Caducidad de `otp`:** detectar tokens vencidos antes de abrir el comparador y sustituirlos por vecinas verificadas con un avance visible en la bitácora.
- **Caché persistente ligera:** mover las cachés de geocodificación y Overpass de memoria a un archivo local pequeño para sobrevivir reinicios sin bases de datos ni servicios externos.
- **Pruebas de regresión del túnel:** añadir una verificación que compruebe certificado público, GPS y `/api/health` en el enlace publicado, sin credenciales.

## v1.2 — Mejoras de la experiencia de conducción

- **Alertas por corredor con umbrales declarados:** sustituir el medidor genérico por reglas explícitas y auditables por tipo de vía, mostrando siempre la señal original y su hora.
- **Cámaras próximas fuera de ruta:** opción para mostrar cámaras verificadas a 1–2 km del trazado sin interrumpir la navegación, con distancia real al vehículo.
- **Modo offline parcial:** conservar inventario, zonas, favoritos y tours en caché local para que la administración funcione sin red; el mapa y las fuentes en vivo seguirán requiriendo conexión.
- **Accesibilidad:** etiquetas ARIA completas en chips, controles de mapa y reproductor; navegación por teclado en el onboarding y el visor.

## v2.0 — Perfil opcional y herramientas ampliadas

- **Perfil opcional sin costo:** sincronización de favoritos y bitácora mediante exportación/importación cifrada por el usuario, sin cuentas ni servidores propios.
- **Más fuentes oficiales:** incorporar agencias adicionales solo desde catálogos públicos documentados, con el mismo estándar de procedencia y verificación de bytes de video.
- **Narración multilingüe:** motor de voz con selección de idioma por dispositivo y textos EN/ES para toda la interfaz.
- **Panel de procedencia unificado:** una sola vista con todas las fuentes, su hora de consulta, licencia y enlace, exportable como informe.

---

## Principios que no cambian

- Gratis y legal: fuentes oficiales y gratuitas, sin claves de pago ni redistribución de señales.
- Verificable: cada dato muestra fuente, hora y confianza explicable.
- Sin invenciones: no se inventan cámaras, incidentes, sensores, frecuencias ni controles PTZ.
- Separación clara entre **Radio** (emisoras reales) y **Tours** (pertenencia publicada por 511NJ).
- Cualquier actualización grande se propone al usuario antes de ejecutarse y se registra aquí y en `RELEASE_NOTES.md`.
