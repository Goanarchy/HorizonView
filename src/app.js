/* HorizonView · interfaz móvil, GPS, reproductor HLS, zoom digital y fuentes. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const LS = {
    theme: "horizonViewTema", wizard: "horizonViewWizard", favs: "horizonViewFavoritos",
    start: "horizonViewInicio", tripPrefs: "horizonViewPreferenciasViaje",
  };

  const state = {
    cameras: [], meta: null, selected: null, hls: null,
    geo: null, nearCount: 10, q: "", zone: "", sort: "zone",
    routeOnly: false, streamOnly: false, poll: null, fallbackDone: false,
    wiz: 0, tab: "camaras", listView: "list",
    zoom: 1, panX: 0, panY: 0, mobileUrl: null,
    locales: null, localLoading: false, radius: 25, reported: new Set(),
    favs: new Set(), favOnly: false, reportArmed: null,
    tour: "", map: null, tiles: null, renderer: null, markers: [], geoLayers: [], mapReady: false,
    aiIds: null, routeData: null, layerItems: [], layerLayers: [], tourData: null,
    compareHls: [], compareCards: [], speaking: false,
    localZone: "", wx: null, wxLoading: false, wxTick: 0,
    radio: null, radioCategory: "", radioLoading: false, radioNow: null, radioHls: null,
    corridorData: null, sensorsData: null, mapExtraLayers: [],
    adminTab: "camaras", drive: null, trip: null,
  };
  try {
    const raw = JSON.parse(getLS(LS.favs) || "[]");
    if (Array.isArray(raw)) state.favs = new Set(raw.filter((x) => typeof x === "string"));
  } catch (_) { /* favoritos vacíos */ }

  const WIZARD = [
    {
      title: "Cámaras públicas reales",
      img: "assets/wizard-inventory.svg",
      text: "HorizonView reúne cámaras oficiales de Nueva Jersey (511NJ) y Delaware (DelDOT) a lo largo del corredor del Turnpike. Ninguna cámara ni coordenada fue inventada.",
      items: [
        "Las cámaras en ruta aparecen marcadas en ámbar.",
        "Cada fila indica su fuente y si expone video en vivo.",
        "La procedencia completa está al pie de la página.",
      ],
    },
    {
      title: "Encuentra la que necesitas",
      img: "assets/wizard-order.svg",
      text: "Busca por nombre, ruta o punto kilométrico. Abre «Buscar y filtrar» para elegir zona, tour oficial de 511NJ, ordenar por nombre o quedarte solo con cámaras que tienen video.",
      items: [
        "«Solo ruta» reduce la lista al corredor principal.",
        "El filtro de tours usa la pertenencia real de los 85 tours oficiales.",
        "Toca una fila para abrirla en el visor o en el mapa.",
      ],
    },
    {
      title: "Tu GPS, tus cámaras cercanas",
      img: "assets/wizard-gps.svg",
      text: "Pulsa «Usar mi GPS». La app busca cámaras públicas cercanas de cualquier fuente y muestra «Cerca» con las más próximas y «Locales» con el radio que elijas.",
      items: [
        "En «Locales» solo aparecen cámaras operativas y con video verificado.",
        "Puedes elegir entre 5, 10, 20 o 50 cámaras cercanas.",
        "La ubicación se procesa solo en tu dispositivo.",
      ],
    },
    {
      title: "Video y controles",
      img: "assets/wizard-viewer.svg",
      text: "El visor reproduce el stream oficial. Puedes reproducir, silenciar, poner pantalla completa, capturar un fotograma y compartir el enlace de la cámara.",
      items: [
        "Los botones + / − hacen zoom digital sobre la imagen.",
        "Arrastra la imagen para moverla cuando esté ampliada.",
        "Las agencias públicas no ofrecen control PTZ remoto.",
      ],
    },
    {
      title: "IA que explica, no vigila",
      img: "assets/wizard-order.svg",
      text: "La pestaña «IA» traduce preguntas en filtros reales, arma rutas con cámaras a lo largo del camino, resume tu corredor y compara ángulos vecinos. Cada respuesta muestra fuente, hora y confianza.",
      items: [
        "El radar de confianza mide la calidad del dato, nunca el tráfico.",
        "NWS, Open-Meteo, OSRM y OSM son públicos y gratuitos.",
        "No se reconocen rostros, placas ni vehículos.",
      ],
    },
    {
      title: "Tours narrados aparte",
      img: "assets/wizard-viewer.svg",
      text: "La categoría «Tours» convierte los 85 recorridos oficiales de 511NJ en una secuencia de cámaras reales que puedes escuchar con la voz del teléfono.",
      items: [
        "La pertenencia al tour viene de 511NJ, no del nombre de la cámara.",
        "Las distancias se calculan con coordenadas reales.",
        "Toca cualquier paso para abrir su video oficial.",
      ],
    },
    {
      title: "Siempre al día",
      img: "assets/wizard-update.svg",
      text: "DelDOT se actualiza automáticamente mientras la página está abierta. Puedes forzar la consulta a cualquiera de las dos fuentes con «Actualizar».",
      items: [
        "El progreso aparece en pantalla al actualizar.",
        "El tema noche/día se recuerda entre visitas.",
        "Esta guía puede volver a abrirse con «Guía».",
      ],
    },
    {
      title: "Llévatelo al celular",
      img: "assets/wizard-viewer.svg",
      text: "Pulsa «Celular» para ver el enlace HTTPS y su código QR. Ábrelo en tu Android o iPhone: funciona sin instalar certificados y el GPS del teléfono funciona correctamente.",
      items: [
        "Usa «start-stable.bat» para un enlace HTTPS fijo y gratis.",
        "Escannea el QR o copia el enlace y envíatelo.",
        "La pestaña «Mapa» muestra todo el inventario en su ubicación real.",
      ],
    },
  ];

  /* ------------------------------------------------------------------ */
  /* Utilidades                                                          */
  /* ------------------------------------------------------------------ */
  function norm(s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function haversine(a, b, c, d) {
    const R = 6371, rad = Math.PI / 180;
    const dLat = (c - a) * rad, dLon = (d - b) * rad;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(a * rad) * Math.cos(c * rad) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function distTo(c) {
    if (!state.geo || !Number.isFinite(c.lat) || !Number.isFinite(c.lon)) return null;
    return haversine(state.geo.lat, state.geo.lon, c.lat, c.lon);
  }
  function fmtDist(km) {
    if (km === null || km === undefined) return "";
    return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
  }
  function coords(c) { return `${c.lat.toFixed(5)}, ${c.lon.toFixed(5)}`; }

  let toastTimer = null, reportTimer = null;
  function toast(msg, ms = 3400) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, ms);
  }
  function getLS(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
  function setLS(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

  async function apiJson(path, payload) {
    const opts = payload === undefined ? { cache: "no-store" } : {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    };
    let j;
    try { j = await (await fetch(path, opts)).json(); }
    catch (_) { throw new Error("No se pudo contactar con el servidor local."); }
    if (!j || !j.ok) throw new Error((j && j.error) || "La fuente no devolvió datos.");
    return j;
  }
  function aiPayload(extra = {}) {
    const p = { favs: [...state.favs], ...extra };
    if (state.geo) p.geo = { lat: state.geo.lat, lon: state.geo.lon };
    return p;
  }
  function trustClass(t) { return t >= 75 ? "hi" : (t < 60 ? "low" : ""); }
  function sourceLinks(sources) {
    const box = el("div", "ai-block");
    box.appendChild(el("h4", null, "Ver datos"));
    (sources || []).forEach((s) => {
      if (!s || !s.url) return;
      const a = el("a", null, (s.label || "Fuente") + " · " + (s.at || "") + " ↗");
      a.href = s.url; a.target = "_blank"; a.rel = "noopener";
      box.appendChild(a);
    });
    return box;
  }

  /* ------------------------------------------------------------------ */
  /* Favoritos persistentes (sobreviven al cambio de enlace/tunel)        */
  /* ------------------------------------------------------------------ */
  function saveFavs() { setLS(LS.favs, JSON.stringify([...state.favs])); }
  function isFav(c) { return !!c && state.favs.has(c.id); }
  function favGlyph(c) { return isFav(c) ? "★" : "☆"; }
  function syncFavUI(c) {
    document.querySelectorAll(".fav").forEach((b) => {
      const on = state.favs.has(b.dataset.camId);
      b.classList.toggle("on", on);
      b.textContent = on ? "★" : "☆";
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.title = on ? "Quitar de favoritos" : "Guardar en favoritos";
    });
    if (c && $("btnFav")) {
      const on = isFav(c);
      $("btnFav").classList.toggle("accent", on);
      $("btnFav").innerHTML = favGlyph(c) + " <span>" + (on ? "Guardado" : "Favorito") + "</span>";
      $("btnFav").title = on ? "Quitar de favoritos" : "Guardar en favoritos";
    }
  }
  function toggleFav(c) {
    if (!c) return;
    if (state.favs.has(c.id)) { state.favs.delete(c.id); toast("Quitado de favoritos."); }
    else { state.favs.add(c.id); toast("Guardado en favoritos. Estará aquí aunque cambie el enlace."); }
    saveFavs();
    syncFavUI(c);
    if (state.favOnly) { render(); renderNear(); renderLocal(); }
  }
  function favButton(c) {
    const b = el("button", "fav" + (isFav(c) ? " on" : ""), isFav(c) ? "★" : "☆");
    b.type = "button";
    b.dataset.camId = c.id;
    b.setAttribute("aria-label", (isFav(c) ? "Quitar de favoritos: " : "Guardar en favoritos: ") + c.name);
    b.setAttribute("aria-pressed", isFav(c) ? "true" : "false");
    b.title = isFav(c) ? "Quitar de favoritos" : "Guardar en favoritos";
    b.addEventListener("click", (e) => { e.stopPropagation(); toggleFav(c); });
    return b;
  }

  /* ------------------------------------------------------------------ */
  /* Tema y pestañas                                                     */
  /* ------------------------------------------------------------------ */
  function applyTheme(theme) {
    const t = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    document.querySelector('meta[name="theme-color"]').content = t === "dark" ? "#0b1020" : "#eef3fb";
    const btn = $("btnTheme");
    btn.innerHTML = t === "dark" ? "☾ <span>Noche</span>" : "☀ <span>Día</span>";
    btn.title = t === "dark" ? "Cambiar a tema día" : "Cambiar a tema noche";
    if (state.map) refreshMapTheme();
    refreshDriveTheme();
  }
  function initTheme() {
    const q = new URLSearchParams(location.search).get("theme");
    let t;
    if (q === "light" || q === "dark") { t = q; setLS(LS.theme, t); }
    else t = getLS(LS.theme) === "light" ? "light" : "dark";
    applyTheme(t);
    $("btnTheme").addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next); setLS(LS.theme, next);
      const u = new URL(location.href); u.searchParams.set("theme", next); history.replaceState(null, "", u);
    });
  }

  function setTab(tab) {
    if (state.tab === "viaje" && tab !== "viaje") pauseTrip();
    if (tab === "viaje") {
      state.tab = tab;
      document.body.dataset.tab = tab;
      $("driveShell").hidden = false;
      document.querySelectorAll(".tabbar .tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
      initDriveMap();
      refreshDriveHud();
      setTimeout(() => { if (state.drive && state.drive.map) state.drive.map.resize(); }, 60);
      return;
    }
    state.adminTab = tab;
    $("driveShell").hidden = true;
    $("driveLayersPanel").hidden = true;
    if (state.tab === "viaje") closeSpotlight(true);
    if (tab === "camaras") state.listView = "list";
    else if (tab === "cerca") state.listView = "near";
    else if (tab === "locales") state.listView = "local";
    else if (tab === "mapa") state.listView = "map";
    else if (tab === "ia") state.listView = "ia";
    else if (tab === "radio") state.listView = "radio";
    else if (tab === "tours") state.listView = "tours";
    state.tab = tab;
    document.body.dataset.tab = tab;
    $("viewList").hidden = state.listView !== "list";
    $("viewNear").hidden = state.listView !== "near";
    $("viewLocal").hidden = state.listView !== "local";
    $("viewMap").hidden = state.listView !== "map";
    $("viewAi").hidden = state.listView !== "ia";
    $("viewRadio").hidden = state.listView !== "radio";
    $("viewTours").hidden = state.listView !== "tours";
    [["segCamaras", "list"], ["segCerca", "near"], ["segLocales", "local"]].forEach(([id, view]) => {
      const on = state.listView === view;
      $(id).classList.toggle("on", on);
      $(id).setAttribute("aria-selected", on);
    });
    document.querySelectorAll(".tabbar .tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    if (tab === "locales" && state.geo && !state.locales && !state.localLoading) loadNearby();
    if (tab === "ia") {
      if ($("aiStats").textContent.indexOf("Consultando") === 0) loadAiStats();
      if (!state.wx) loadWeather(true).catch(() => {});
    }
    if (tab === "radio" && !state.radio) loadRadio().catch(() => {});
    if (tab === "mapa") {
      initMap();
      setTimeout(() => { if (state.map) { state.map.invalidateSize(); renderMap(); } }, 60);
    }
    if (tab === "visor") {
      const stage = $("stage");
      if (stage.scrollIntoView) setTimeout(() => stage.scrollIntoView({ behavior: "smooth", block: "center" }), 40);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Datos                                                               */
  /* ------------------------------------------------------------------ */
  async function loadCameras(keepSelection = true) {
    const r = await fetch("/api/cameras", { cache: "no-store" });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "No se pudo cargar el inventario");
    const previous = keepSelection && state.selected ? state.selected.id : null;
    state.cameras = (j.cameras || []).filter((c) => !state.reported.has(c.id));
    state.meta = j.meta || null;
    populateZones(); populateTours(); renderZoneChips(); populateCorridorZones();
    render();
    if (previous) {
      const again = state.cameras.find((c) => c.id === previous);
      if (again) selectCamera(again, false);
    } else {
      const deep = new URLSearchParams(location.search).get("cam");
      if (deep) {
        const c = state.cameras.find((x) => x.id === deep);
        if (c) { selectCamera(c, true); setTab("visor"); }
        else toast("No se encontró la cámara del enlace.", 4500);
      }
    }
    await ping();
  }

  function populateZones() {
    const sel = $("zone"), current = sel.value;
    const zones = [...new Set(state.cameras.map((c) => c.zone))].sort((a, b) => zoneRank(a) - zoneRank(b) || a.localeCompare(b, "es"));
    sel.replaceChildren(new Option("Todas las zonas", ""));
    zones.forEach((z) => sel.add(new Option(z, z)));
    if (zones.includes(current)) sel.value = current;
  }
  function populateTours() {
    const sel = $("tour"), current = state.tour;
    const tours = (state.meta?.tours || []).slice().sort((a, b) => a.name.localeCompare(b.name, "es"));
    sel.replaceChildren(new Option(`Todos los tours oficiales (${tours.length})`, ""));
    tours.forEach((t) => sel.add(new Option(`${t.name} · ${t.cameras}`, t.name)));
    if (tours.some((t) => t.name === current)) sel.value = current;
    else { state.tour = ""; sel.value = ""; }
    const narr = $("tourNarr");
    if (narr) {
      const prev = narr.value;
      narr.replaceChildren(new Option("Elige un tour oficial…", ""));
      tours.forEach((t) => narr.add(new Option(`${t.name} · ${t.cameras} cámaras`, t.name)));
      if (tours.some((t) => t.name === prev)) narr.value = prev;
    }
  }
  function zoneRank(z) {
    const n = norm(z);
    if (n.startsWith("de ")) return 0;
    if (n.includes("turnpike")) return 1;
    if (n.includes("i-295") || n.includes("i-76")) return 2;
    return 3;
  }

  /* ------------------------------------------------------------------ */
  /* Zonas locales, clima animado, sensores, radio y capas combinadas     */
  /* ------------------------------------------------------------------ */
  function zonesMeta() {
    return (state.meta && state.meta.localZones && state.meta.localZones.zones) || [];
  }
  function zoneSummary() {
    return (state.meta && state.meta.zoneSummary) || [];
  }
  function zonePoint(id) {
    const z = zonesMeta().find((x) => x.id === id);
    return z ? z.center : null;
  }
  function renderZoneChips() {
    const bar = $("localZoneBar"), host = $("localZoneChips");
    const zones = zoneSummary();
    if (!bar || !host || !zones.length) { if (bar) bar.hidden = true; return; }
    bar.hidden = false;
    host.replaceChildren();
    const all = el("button", "zchip" + (!state.localZone ? " on" : ""),
      `Todas · ${state.cameras.length}`);
    all.type = "button";
    all.addEventListener("click", () => { state.localZone = ""; renderZoneChips(); render(); });
    host.appendChild(all);
    zones.forEach((z) => {
      const chip = el("button", "zchip" + (state.localZone === z.id ? " on" : ""),
        `${z.name} · ${z.cameraCount}`);
      chip.type = "button";
      chip.title = `${z.label || z.name} · radio ${z.radiusKm} km`;
      chip.addEventListener("click", () => {
        state.localZone = state.localZone === z.id ? "" : z.id;
        renderZoneChips(); render();
      });
      host.appendChild(chip);
    });
    const active = zones.find((z) => z.id === state.localZone);
    $("localZoneInfo").textContent = active
      ? `${active.name}: ${active.cameraCount} cámaras oficiales · radio ${active.radiusKm} km`
      : `${zones.length} zonas · ${state.cameras.length} cámaras en el inventario`;
  }
  function populateCorridorZones() {
    const sel = $("corridorZone");
    if (!sel) return;
    const zones = zoneSummary();
    if (!zones.length) return;
    const prev = sel.value || "somerville";
    sel.replaceChildren();
    zones.forEach((z) => sel.add(new Option(z.label || z.name, z.id)));
    if (zones.some((z) => z.id === prev)) sel.value = prev;
  }
  function itemDistance(c) {
    const gps = distTo(c);
    if (gps !== null) return gps;
    if (!state.localZone) return null;
    const z = zonesMeta().find((x) => x.id === state.localZone);
    return z && z.distanceKm && z.distanceKm[c.id] !== undefined ? z.distanceKm[c.id] : null;
  }

  const WX_SCENE = '<div class="wscene" aria-hidden="true">' +
    '<i class="w-body"></i><i class="w-cloud a"></i><i class="w-cloud b"></i>' +
    '<i class="w-drop d1"></i><i class="w-drop d2"></i><i class="w-drop d3"></i>' +
    '<i class="w-flake f1"></i><i class="w-flake f2"></i><i class="w-bolt"></i>' +
    '<i class="w-fog l1"></i><i class="w-fog l2"></i>' +
    '<i class="w-streak s1"></i><i class="w-streak s2"></i></div>';
  function extraSources(list) {
    return (list || []).map((s) => ({ label: s.name, url: s.url, at: s.fetchedAt }));
  }
  function wxPoint() {
    const place = ($("wxPlace") && $("wxPlace").value) || "geo";
    if (place === "geo" && state.geo) {
      return { lat: state.geo.lat, lon: state.geo.lon, label: "Tu ubicación" };
    }
    const z = zonePoint(place === "geo" ? "somerville" : place);
    if (z) return { lat: z.lat, lon: z.lon, label: place === "geo" ? "Somerville (sin GPS)" : place };
    return { lat: 40.6209, lon: -74.6085, label: "Somerville" };
  }
  function loadWeather(silent = false) {
    if (state.wxLoading) return Promise.resolve();
    const pt = wxPoint();
    state.wxLoading = true;
    return apiJson(`/api/weather/live?lat=${pt.lat}&lon=${pt.lon}`).then((j) => {
      state.wx = j;
      renderWeatherTile(j);
      renderWeatherCard(j, pt);
      return j;
    }).catch((e) => {
      $("wxDesc").textContent = "Sin clima";
      if (!silent) $("wxOut").replaceChildren(el("div", "empty", e.message));
      throw e;
    }).finally(() => { state.wxLoading = false; });
  }
  function renderWeatherTile(j) {
    const c = j.current || {}, tile = $("weatherTile");
    if (!tile) return;
    tile.dataset.anim = c.animation || "cloudy";
    tile.title = `Clima en vivo · ${c.description || "—"} · NWS + Open-Meteo`;
    $("wxTemp").textContent = (c.temperatureC === null || c.temperatureC === undefined)
      ? "—" : `${Math.round(c.temperatureC)}°`;
    $("wxDesc").textContent = c.description || "Sin dato";
  }
  function renderWeatherCard(j, pt) {
    const box = $("wxOut");
    if (!box) return;
    box.replaceChildren();
    const c = j.current || {};
    const hero = el("div", "wx-now");
    hero.innerHTML = WX_SCENE;
    hero.querySelector(".wscene").dataset.anim = c.animation || "cloudy";
    const copy = el("div", "wx-now-copy");
    copy.appendChild(el("b", "wx-big-temp",
      (c.temperatureC === null || c.temperatureC === undefined) ? "—" : `${Math.round(c.temperatureC)}°C`));
    copy.appendChild(el("span", "wx-cond", c.description || "Sin dato"));
    copy.appendChild(el("span", "wx-where",
      `${pt.label} · ${pt.lat.toFixed(4)}, ${pt.lon.toFixed(4)} · ${c.observedAt || j.at}`));
    hero.appendChild(copy);
    box.appendChild(hero);
    const stats = el("div", "wx-stats");
    [["Humedad", c.humidity !== undefined && c.humidity !== null ? c.humidity + "%" : "—"],
     ["Viento", c.windKmh !== undefined && c.windKmh !== null ? c.windKmh + " km/h" : "—"],
     ["Ráfagas", c.windGustKmh !== undefined && c.windGustKmh !== null ? c.windGustKmh + " km/h" : "—"],
     ["Lluvia", c.precipitationMm !== undefined ? c.precipitationMm + " mm" : "—"],
     ["Nubosidad", c.cloudCover !== undefined && c.cloudCover !== null ? c.cloudCover + "%" : "—"]]
      .forEach(([k, v]) => {
        const s = el("div", "wx-stat");
        s.appendChild(el("small", null, k)); s.appendChild(el("b", null, v));
        stats.appendChild(s);
      });
    box.appendChild(stats);
    if ((j.hourly || []).length) {
      const hours = el("div", "wx-hourly");
      j.hourly.slice(0, 12).forEach((h) => {
        const hb = el("div", "wx-hour");
        hb.innerHTML = WX_SCENE;
        hb.querySelector(".wscene").dataset.anim = h.animation || "cloudy";
        hb.appendChild(el("span", null, h.time ? h.time.slice(11, 16) : "—"));
        hb.appendChild(el("b", null,
          (h.tempC === null || h.tempC === undefined) ? "—" : Math.round(h.tempC) + "°"));
        if (h.precipitationProbability) hb.appendChild(el("small", null, h.precipitationProbability + "%"));
        hours.appendChild(hb);
      });
      box.appendChild(hours);
    }
    const obs = j.observation || {}, nwr = j.nwr || {};
    box.appendChild(aiBlock("Observación y fuentes", [
      `Estación ${obs.stationId || "—"} · ${obs.stationName || "—"} · ${obs.distanceKm !== undefined ? fmtDist(obs.distanceKm) : ""} · ${obs.description || ""}.`,
      `NOAA Weather Radio: ${nwr.callSign || "—"} · ${nwr.frequencyMhz ? nwr.frequencyMhz + " MHz (frecuencia, no stream de internet)" : "frecuencia no publicada"}.`,
      (j.alerts || []).length
        ? `${j.alerts.length} alerta(s) NWS activas: ${j.alerts.map((a) => a.event).join(", ")}.`
        : "Sin alertas NWS activas en el punto.",
      `Confianza ${j.confidence}. ${(j.errors || []).length ? "Avisos: " + j.errors.join(" · ") : "Todas las fuentes respondieron."}`,
    ], extraSources(j.sources)));
  }
  async function ensureSensors() {
    if (state.sensorsData) return state.sensorsData;
    const pt = wxPoint();
    state.sensorsData = await apiJson(`/api/sensors?lat=${pt.lat}&lon=${pt.lon}`);
    return state.sensorsData;
  }
  async function loadSensors() {
    const box = $("combinedOut");
    box.replaceChildren(el("div", "loading", "Consultando USGS, NWS y radio meteorológica…"));
    try {
      const pt = wxPoint(), j = await ensureSensors();
      const rows = [...(j.usgs || []), ...(j.additional || [])];
      box.replaceChildren();
      box.appendChild(aiBlock("Sensores y frecuencias cerca de " + pt.label, [
        `${rows.length} lecturas públicas · confianza ${j.confidence}. ${j.note}`,
      ], extraSources(j.sources)));
      if (!rows.length) box.appendChild(el("div", "empty", "No hay lecturas activas en el área."));
      rows.slice(0, 14).forEach((s) => {
        const b = el("div", "ai-block");
        b.appendChild(el("h4", null, `${s.name} · ${s.id}`));
        b.appendChild(el("p", null,
          `${s.variable}: ${s.value === null || s.value === undefined ? "—" : s.value} ${s.unit || ""} · ` +
          `observado ${s.observedAt || "—"} · ${s.distanceKm !== undefined ? fmtDist(s.distanceKm) : "en el punto"}` +
          `${s.provisional ? " · dato provisional USGS" : ""}`));
        if (s.sourceUrl) b.appendChild(sourceLinks([{ label: "Ver dato", url: s.sourceUrl, at: s.observedAt }]));
        box.appendChild(b);
      });
      toast(`${rows.length} sensores y frecuencias consultados.`);
    } catch (e) { box.replaceChildren(el("div", "empty", e.message)); }
  }
  async function loadCorridor() {
    const box = $("combinedOut");
    box.replaceChildren(el("div", "loading", "Cruzando clima, eventos 511NJ y sensores…"));
    try {
      const zone = $("corridorZone").value;
      const payload = zone ? { zone } : { lat: state.geo && state.geo.lat, lon: state.geo && state.geo.lon };
      const j = await apiJson("/api/ai/corridor", payload);
      state.corridorData = j;
      box.replaceChildren();
      const gauge = el("div", "corridor-gauge " + j.level);
      gauge.appendChild(el("b", null, j.score + "/100"));
      gauge.appendChild(el("span", null, j.label));
      box.appendChild(gauge);
      box.appendChild(aiBlock("Por qué", [
        ...(j.reasons || []),
        `${j.eventCount} evento(s) 511NJ en la zona · ${(j.sensors || []).length} lecturas de sensores.`,
        `Clima: ${j.weather.description || "—"} · ${j.weather.temperatureC}°C · ráfagas ${j.weather.windGustKmh || 0} km/h.`,
        j.method,
      ], extraSources(j.sources)));
      if ((j.events || []).length) {
        const ul = el("ul", "evidence");
        j.events.forEach((e) => ul.appendChild(el("li", null,
          `${e.category} · ${e.facility} · ${fmtDist(e.distanceKm)} · ${e.description}`)));
        box.appendChild(ul);
      }
      toast(`${j.label} (${j.score}/100) · ${j.eventCount} eventos 511NJ.`, 4400);
    } catch (e) { box.replaceChildren(el("div", "empty", e.message)); }
  }
  function loadRadio(refresh = false) {
    if (state.radioLoading) return Promise.resolve();
    state.radioLoading = true;
    $("radioStatus").textContent = "Verificando streams HTTPS de las emisoras…";
    return apiJson("/api/radio/stations" + (refresh ? "?refresh=1" : "")).then((j) => {
      state.radio = j;
      populateRadioCategories();
      renderRadioList();
      $("radioStatus").textContent = `${j.verifiedCount}/${j.total} emisoras verificadas · comprobadas ${j.at}`;
      return j;
    }).catch((e) => {
      $("radioStatus").textContent = "No se pudo verificar: " + e.message;
      $("radioList").replaceChildren(el("div", "empty", e.message));
      throw e;
    }).finally(() => { state.radioLoading = false; });
  }
  function populateRadioCategories() {
    const sel = $("radioCategory"), prev = sel.value;
    sel.replaceChildren(new Option("Todas las categorías", ""));
    (state.radio && state.radio.categories || []).forEach((c) => sel.add(new Option(`${c.icon} ${c.name}`, c.id)));
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
    else state.radioCategory = "";
  }
  function renderRadioList() {
    const host = $("radioList");
    if (!host) return;
    host.replaceChildren();
    const stations = ((state.radio && state.radio.stations) || [])
      .filter((s) => !state.radioCategory || s.category === state.radioCategory);
    if (!stations.length) { host.appendChild(el("div", "empty", "No hay emisoras en esta categoría.")); return; }
    stations.forEach((s) => {
      const card = el("div", "station" + (state.radioNow === s.id ? " on" : ""));
      const img = el("img", "station-logo");
      img.src = s.logo; img.alt = s.name; img.loading = "lazy";
      img.onerror = () => { img.style.visibility = "hidden"; };
      card.appendChild(img);
      const mid = el("div", "station-copy");
      mid.appendChild(el("b", null, s.name));
      mid.appendChild(el("span", "station-sub", `${s.frequency} · ${s.city}`));
      mid.appendChild(el("span", "station-now", s.nowPlaying || ""));
      const tags = el("span", "station-tags");
      [s.category, s.codec, s.available ? "en vivo" : "sin señal"].filter(Boolean)
        .forEach((t) => tags.appendChild(el("i", null, t)));
      mid.appendChild(tags);
      card.appendChild(mid);
      const actions = el("div", "station-actions");
      const play = el("button", "chip accent");
      play.type = "button"; play.innerHTML = "▶ <span>Escuchar</span>";
      play.disabled = !s.available;
      play.addEventListener("click", () => playRadio(s));
      const link = el("a", "chip ghost", "↗");
      link.href = s.homepage; link.target = "_blank"; link.rel = "noopener";
      link.title = "Sitio oficial de " + s.name;
      actions.appendChild(play); actions.appendChild(link);
      card.appendChild(actions);
      host.appendChild(card);
    });
  }
  function playRadio(s) {
    const audio = $("radioAudio");
    if (state.radioNow === s.id && !audio.paused) {
      audio.pause(); $("radioEq").classList.remove("on"); return;
    }
    stopRadio(false);
    state.radioNow = s.id;
    $("radioPlayer").hidden = false;
    const logo = $("radioLogo");
    logo.src = s.logo; logo.style.visibility = "visible";
    $("radioPlayerName").textContent = `${s.name} · ${s.frequency}`;
    $("radioNow").textContent = s.nowPlaying || "Conectando…";
    $("radioMetaAt").textContent = `Verificado ${s.checkedAt || s.verifiedAt} · ${s.codec}`;
    $("radioOfficial").href = s.homepage;
    const url = "/api/radio/stream/" + encodeURIComponent(s.id);
    if (s.streamKind === "hls" && window.Hls && Hls.isSupported()) {
      if (state.radioHls) { try { state.radioHls.destroy(); } catch (_) {} }
      state.radioHls = new Hls({ lowLatencyMode: true, enableWorker: true });
      state.radioHls.loadSource(url);
      state.radioHls.attachMedia(audio);
      state.radioHls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          $("radioNow").textContent = "No se pudo reproducir esta emisora.";
          $("radioEq").classList.remove("on");
        }
      });
    } else {
      audio.src = url;
    }
    audio.play().then(() => { $("radioEq").classList.add("on"); }).catch(() => {
      $("radioNow").textContent = "Pulsa el botón ▶ del reproductor para escuchar.";
    });
    renderRadioList();
    refreshRadioMeta(s.id);
  }
  function stopRadio(clear = true) {
    const audio = $("radioAudio");
    try { audio.pause(); audio.removeAttribute("src"); audio.load(); } catch (_) {}
    if (state.radioHls) { try { state.radioHls.destroy(); } catch (_) {} state.radioHls = null; }
    $("radioEq").classList.remove("on");
    if (clear) { state.radioNow = null; $("radioPlayer").hidden = true; renderRadioList(); toast("Radio detenida."); }
  }
  async function refreshRadioMeta(id) {
    try {
      const j = await apiJson("/api/radio/metadata?id=" + encodeURIComponent(id) + "&refresh=1");
      if (state.radioNow === id) {
        $("radioNow").textContent = j.nowPlaying || "Señal en vivo";
        $("radioMetaAt").textContent = `Metadatos reales · ${j.checkedAt} · HTTP ${j.status}`;
      }
    } catch (_) { /* se conserva el último texto verificado */ }
  }
  function renderMapExtras() {
    if (!state.map) return;
    const push = (layer) => { layer.addTo(state.map); state.mapExtraLayers.push(layer); };
    if ($("mapZones") && $("mapZones").checked) {
      zonesMeta().forEach((z) => {
        const circle = L.circle([z.center.lat, z.center.lon], {
          renderer: state.renderer, radius: (z.radiusKm || 8) * 1000,
          color: "#ffb347", weight: 1.5, fillColor: "#ffb347", fillOpacity: 0.05,
        }).bindTooltip(`${z.name} · radio ${z.radiusKm} km`);
        push(circle);
        const m = L.circleMarker([z.center.lat, z.center.lon], {
          renderer: state.renderer, radius: 10, color: "#ffffff", weight: 2,
          fillColor: "#ffb347", fillOpacity: 1,
        }).bindTooltip(`${z.label || z.name} · ${z.radiusKm} km`);
        m.on("click", () => {
          state.localZone = state.localZone === z.id ? "" : z.id;
          renderZoneChips(); render(); setTab("camaras");
        });
        push(m);
      });
    }
    if ($("mapSensors") && $("mapSensors").checked && state.sensorsData) {
      const rows = [...(state.sensorsData.usgs || []), ...(state.sensorsData.additional || [])];
      rows.forEach((s) => {
        if (!Number.isFinite(s.lat) || !Number.isFinite(s.lon)) return;
        const color = s.type === "frequency" ? "#c792ea" : (s.type === "weather" ? "#8fd4ff" : "#4ade9b");
        push(L.circleMarker([s.lat, s.lon], {
          renderer: state.renderer, radius: 6, color: "#ffffff", weight: 1.5,
          fillColor: color, fillOpacity: 0.9,
        }).bindTooltip(`${s.name} · ${s.variable}: ${s.value} ${s.unit || ""}`, { sticky: true }));
      });
    }
    if ($("mapRadio") && $("mapRadio").checked && state.radio) {
      (state.radio.stations || []).forEach((s) => {
        if (!Number.isFinite(s.cityLat) || !Number.isFinite(s.cityLon)) return;
        const m = L.circleMarker([s.cityLat, s.cityLon], {
          renderer: state.renderer, radius: 8, color: "#ffffff", weight: 2,
          fillColor: s.available ? "#c792ea" : "#ff8080", fillOpacity: 1,
        }).bindTooltip(`${s.name} · ${s.frequency} · ${s.city} (ciudad aproximada)`, { sticky: true });
        m.on("click", () => { setTab("radio"); playRadio(s); });
        push(m);
      });
    }
  }
  async function ping() {
    try {
      const r = await fetch("/api/health", { cache: "no-store" });
      const j = await r.json();
      if (!j.ok) return;
      $("stTotal").textContent = j.cameras;
      $("stNj").textContent = j.nj;
      $("stDe").textContent = j.de;
      $("stStream").textContent = j.streams;
      $("stTime").textContent = "En vivo · " + new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      state.wxTick = (state.wxTick || 0) + 1;
      if (state.wxTick % 15 === 0) loadWeather(true).catch(() => {});
    } catch (_) {
      $("stTime").textContent = "Sin conexión con el servidor";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Listas                                                              */
  /* ------------------------------------------------------------------ */
  function filtered() {
    let arr = state.cameras.slice();
    if (state.q) {
      const needle = norm(state.q);
      arr = arr.filter((c) => norm(`${c.name} ${c.zone} ${c.id} ${c.source}`).includes(needle));
    }
    if (state.zone) arr = arr.filter((c) => c.zone === state.zone);
    if (state.localZone) arr = arr.filter((c) => (c.localZones || []).some((z) => z.id === state.localZone));
    if (state.tour) arr = arr.filter((c) => (c.tours || []).includes(state.tour));
    if (state.aiIds) arr = arr.filter((c) => state.aiIds.has(c.id));
    if (state.routeOnly) arr = arr.filter((c) => c.onRoute);
    if (state.streamOnly) arr = arr.filter((c) => !!c.stream);
    if (state.favOnly) arr = arr.filter((c) => state.favs.has(c.id));
    if (state.sort === "dist" && state.geo) arr.sort((a, b) => (distTo(a) ?? 1e9) - (distTo(b) ?? 1e9));
    else arr.sort((a, b) => a.name.localeCompare(b.name, "es", { numeric: true, sensitivity: "base" }) || a.id.localeCompare(b.id));
    return arr;
  }
  function groupsOf(arr) {
    if (state.sort === "dist" && state.geo) {
      const near = arr.slice(0, state.nearCount), rest = arr.slice(state.nearCount);
      return [
        { title: `Más cercanas · ${near.length}`, items: near },
        { title: `Resto del inventario · ${rest.length}`, items: rest },
      ].filter((g) => g.items.length);
    }
    if (state.sort === "name") return [{ title: `Todas las cámaras · ${arr.length}`, items: arr }];
    const map = new Map();
    arr.forEach((c) => { if (!map.has(c.zone)) map.set(c.zone, []); map.get(c.zone).push(c); });
    return [...map.entries()]
      .sort((a, b) => zoneRank(a[0]) - zoneRank(b[0]) || a[0].localeCompare(b[0], "es"))
      .map(([title, items]) => ({ title: `${title} · ${items.length}`, items }));
  }
  function render() {
    const arr = filtered();
    $("listCount").textContent = `${arr.length} / ${state.cameras.length} cámaras`;
    const list = $("list");
    list.replaceChildren();
    if (!arr.length) {
      list.appendChild(el("div", "empty", state.favOnly && !state.favs.size
        ? "Aún no guardaste favoritos. Toca la estrella ☆ junto a cualquier cámara."
        : state.cameras.length
          ? "No hay cámaras que coincidan con los filtros actuales."
          : "Todavía no hay cámaras cargadas."));
    } else {
      groupsOf(arr).forEach((g) => {
        const box = el("section", "group");
        box.appendChild(el("h4", null, g.title));
        g.items.forEach((c) => box.appendChild(makeItem(c)));
        list.appendChild(box);
      });
    }
    renderNear();
    if (state.selected) {
      document.querySelectorAll(".item,.ncard").forEach((n) => n.classList.toggle("sel", n.dataset.camId === state.selected.id));
    }
    if (state.map && state.tab === "mapa") renderMap();
  }
  function makeItem(c) {
    const d = itemDistance(c);
    const row = el("div", "row");
    const b = el("button", "item" + (c.onRoute ? " on" : "") + (state.selected?.id === c.id ? " sel" : ""));
    b.type = "button"; b.dataset.camId = c.id; b.title = `${c.name} · ${c.zone}`;
    b.appendChild(el("i", "mark"));
    const mid = el("span");
    mid.appendChild(el("span", "nm", c.name));
    mid.appendChild(el("span", "sub", `${c.zone} · ${c.source}${c.stream ? " · HLS" : " · sin stream público"}`));
    if ((c.localZones || []).length) {
      const badges = el("span", "zbadges");
      c.localZones.slice(0, 4).forEach((z) => {
        const badge = el("i", "zbadge" + (state.localZone === z.id ? " on" : ""), z.name);
        badge.title = `Zona local: ${z.label || z.name} · ${fmtDist(z.distanceKm)} del centro`;
        badges.appendChild(badge);
      });
      mid.appendChild(badges);
    }
    b.appendChild(mid);
    const right = el("span", "right");
    if (d !== null) {
      const dist = el("span", "dist", fmtDist(d));
      if (distTo(c) === null) dist.title = "Distancia al centro de la zona local";
      right.appendChild(dist);
    }
    right.appendChild(el("span", "src", c.source.toUpperCase()));
    if (c.trust !== undefined) {
      const tp = el("span", "trust-pill " + trustClass(c.trust), "C " + c.trust);
      tp.title = `Confianza del dato: ${c.trustLabel || "—"} (${c.trust}/100)`;
      right.appendChild(tp);
    }
    b.appendChild(right);
    b.addEventListener("click", () => { selectCamera(c); if (matchMedia("(max-width:900px)").matches) setTab("visor"); });
    row.appendChild(b);
    row.appendChild(favButton(c));
    return row;
  }
  function makeNearCard(c, i) {
    const row = el("div", "nrow");
    const b = el("button", "ncard" + (i === 0 ? " first" : "") + (state.selected?.id === c.id ? " sel" : ""));
    b.type = "button"; b.dataset.camId = c.id;
    b.appendChild(el("span", "rank", String(i + 1).padStart(2, "0")));
    const mid = el("span");
    mid.appendChild(el("span", "nm", c.name));
    mid.appendChild(el("span", "sub", `${c.zone} · ${c.source} · verificado ${c.verifiedAt || "ahora"}`));
    b.appendChild(mid);
    b.appendChild(el("span", "go", fmtDist(c.distKm ?? distTo(c)) + "  ▶"));
    b.addEventListener("click", () => { selectCamera(c); setTab("visor"); });
    row.appendChild(b);
    row.appendChild(favButton(c));
    return row;
  }
  function renderNear() {
    const box = $("nearList");
    box.replaceChildren();
    if (!state.geo) {
      box.appendChild(el("div", "empty", "Todavía no hay una ubicación. Pulsa «Usar mi GPS» para empezar."));
      $("nearMeta").textContent = "—";
      return;
    }
    if (state.localLoading && !state.locales) {
      box.appendChild(el("div", "empty", "Buscando y verificando cámaras cercanas…"));
      $("nearMeta").textContent = "Verificando…";
      return;
    }
    const arr = (state.locales || []).slice(0, state.nearCount);
    $("nearMeta").textContent = state.locales
      ? `${state.locales.length} verificadas · ±${Math.round(state.geo.accuracy || 0)} m`
      : "—";
    if (!arr.length) {
      box.appendChild(el("div", "empty", "No hay cámaras en vivo verificadas cerca de esta ubicación."));
      return;
    }
    arr.forEach((c, i) => box.appendChild(makeNearCard(c, i)));
  }
  function renderLocal() {
    const box = $("localList"), st = $("localStatus");
    box.replaceChildren();
    if (!state.geo) {
      st.textContent = "Pulsa «Usar mi GPS» para buscar cámaras locales en vivo.";
      st.className = "local-status";
      box.appendChild(el("div", "empty", "Sin ubicación: no se puede buscar en un radio."));
      return;
    }
    if (state.localLoading) {
      st.textContent = "Comprobando playlists y segmentos de video…";
      st.className = "local-status warn";
      box.appendChild(el("div", "empty", "Verificando cámaras en vivo…"));
      return;
    }
    const arr = state.locales || [];
    if (!arr.length) {
      st.textContent = "No hay cámaras en vivo verificadas en este radio. Prueba con 50 o 100 km.";
      st.className = "local-status warn";
      box.appendChild(el("div", "empty", "Sin resultados verificados."));
      return;
    }
    st.textContent = `${arr.length} cámaras en vivo verificadas · ${state.checked || arr.length} candidatas comprobadas · ±${Math.round(state.geo.accuracy || 0)} m · ${state.localAt || ""}`;
    st.className = "local-status ok";
    arr.forEach((c, i) => box.appendChild(makeNearCard(c, i)));
  }
  async function loadNearby(force = false, quiet = false) {
    if (!state.geo) { if (!quiet) toast("Primero usa tu GPS."); return; }
    state.localLoading = true;
    state.radius = parseInt($("radiusKm").value, 10) || 25;
    $("btnVerifyLocal").disabled = true;
    renderNear(); renderLocal();
    try {
      const r = await fetch("/api/nearby", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: state.geo.lat, lon: state.geo.lon, radiusKm: state.radius, limit: 200, force }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "fallo en la consulta");
      state.locales = (j.cameras || []).filter((c) => !state.reported.has(c.id));
      state.checked = j.checked || 0;
      state.localAt = j.at || "";
      if (!quiet) toast(`${state.locales.length} cámaras en vivo verificadas cerca de ti.`, 4200);
    } catch (e) {
      state.locales = [];
      if (!quiet) toast("No se pudo verificar el video cercano: " + e.message, 5200);
    } finally {
      state.localLoading = false;
      $("btnVerifyLocal").disabled = false;
      renderNear(); renderLocal();
    }
  }

  /* ------------------------------------------------------------------ */
  /* Mapa interactivo (Leaflet + teselas OpenStreetMap/CARTO)            */
  /* ------------------------------------------------------------------ */
  function mapTileUrl() {
    const dark = document.documentElement.getAttribute("data-theme") !== "light";
    return dark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
  }
  function initMap() {
    if (state.map || !window.L) return;
    state.map = L.map("map", {
      preferCanvas: true, zoomControl: true, attributionControl: false,
      minZoom: 5, maxZoom: 18, worldCopyJump: false,
    }).setView([40.15, -74.65], 7);
    state.renderer = L.canvas({ padding: 0.6 });
    state.tiles = L.tileLayer(mapTileUrl(), {
      subdomains: "abcd", maxZoom: 19, crossOrigin: true,
    }).addTo(state.map);
  }
  function refreshMapTheme() {
    if (!state.map || !state.tiles) return;
    state.map.removeLayer(state.tiles);
    state.tiles = L.tileLayer(mapTileUrl(), {
      subdomains: "abcd", maxZoom: 19, crossOrigin: true,
    }).addTo(state.map);
  }
  function mapRows() {
    let arr = filtered();
    if ($("mapVerified") && $("mapVerified").checked) {
      const ids = new Set((state.locales || []).map((c) => c.id));
      arr = arr.filter((c) => ids.has(c.id));
    }
    return arr;
  }
  function renderMap() {
    if (!state.map) return;
    state.markers.forEach((m) => m.remove());
    state.markers = [];
    state.geoLayers.forEach((l) => l.remove());
    state.geoLayers = [];
    state.layerLayers.forEach((l) => l.remove());
    state.layerLayers = [];
    state.mapExtraLayers.forEach((l) => l.remove());
    state.mapExtraLayers = [];
    if (state.routeData && (state.routeData.geometry || []).length > 1) {
      state.layerLayers.push(L.polyline(state.routeData.geometry, {
        color: "#ffb347", weight: 5, opacity: 0.9,
      }).addTo(state.map));
      [state.routeData.start, state.routeData.end].forEach((p, i) => {
        if (!p) return;
        state.layerLayers.push(L.circleMarker([p.lat, p.lon], {
          renderer: state.renderer, radius: 8, color: "#ffffff", weight: 3,
          fillColor: i ? "#ff8080" : "#4ade9b", fillOpacity: 1,
        }).addTo(state.map).bindTooltip((i ? "Destino: " : "Origen: ") + p.name));
      });
      state.routeData.cameras.forEach((c) => {
        if (!Number.isFinite(c.lat)) return;
        state.layerLayers.push(L.circleMarker([c.lat, c.lon], {
          renderer: state.renderer, radius: 9, color: "#ffffff", weight: 2,
          fillColor: "#ffb347", fillOpacity: 0.95,
        }).addTo(state.map).bindTooltip(
          `${c.name} · km ${c.atKm} · a ${c.offRouteKm} km de la ruta`, { sticky: true }));
      });
    }
    const layerColors = { "Alerta NWS": "#ff8080", "Evento 511NJ": "#ff9f43", "Obra vial OSM": "#c792ea", "Clima actual": "#8fd4ff" };
    state.layerItems.forEach((it) => {
      if (!Number.isFinite(it.lat) || !Number.isFinite(it.lon)) return;
      const m = L.circleMarker([it.lat, it.lon], {
        renderer: state.renderer, radius: 7, color: "#ffffff", weight: 1.5,
        fillColor: layerColors[it.type] || "#8fd4ff", fillOpacity: 0.85,
      });
      m.bindTooltip(`${it.type}: ${it.label}${it.detail ? " · " + it.detail : ""}`
        + (it.camera ? ` · cámara: ${it.camera.name} (${it.camera.distKm} km)` : ""), { sticky: true });
      m.on("click", () => {
        if (it.camera) {
          const c = state.cameras.find((x) => x.id === it.camera.id);
          if (c) { selectCamera(c, false); setTab("visor"); }
        }
      });
      m.addTo(state.map);
      state.layerLayers.push(m);
    });
    const arr = mapRows();
    const verified = new Set((state.locales || []).map((c) => c.id));
    arr.forEach((c) => {
      if (!Number.isFinite(c.lat) || !Number.isFinite(c.lon)) return;
      const isNj = c.source === "511NJ";
      const live = verified.has(c.id);
      const color = isNj ? "#ffb347" : "#5ad1e6";
      const selected = state.selected && state.selected.id === c.id;
      const m = L.circleMarker([c.lat, c.lon], {
        renderer: state.renderer,
        radius: selected ? 8 : (live ? 6 : 4.5),
        color: selected ? "#ffffff" : color,
        weight: selected ? 3 : 1.5,
        fillColor: live ? "#4ade9b" : color,
        fillOpacity: live || selected ? 0.95 : 0.72,
      });
      const d = distTo(c);
      m.bindTooltip(c.name + (d !== null ? " · " + fmtDist(d) : ""), {
        direction: "top", opacity: 1, sticky: true,
      });
      m.on("click", () => { selectCamera(c, false); setTab("visor"); });
      m.addTo(state.map);
      state.markers.push(m);
    });
    if (state.geo) {
      const lat = state.geo.lat, lon = state.geo.lon;
      const radius = Math.min(5000, Math.max(20, state.geo.accuracy || 50));
      const acc = L.circle([lat, lon], {
        renderer: state.renderer, radius, color: "#5ad1e6",
        weight: 1, fillColor: "#5ad1e6", fillOpacity: 0.08,
      }).addTo(state.map);
      const me = L.circleMarker([lat, lon], {
        renderer: state.renderer, radius: 6, color: "#ffffff",
        weight: 2, fillColor: "#5ad1e6", fillOpacity: 1,
      }).addTo(state.map).bindTooltip("Tú estás aquí", { direction: "top" });
      state.geoLayers = [acc, me];
    }
    renderMapExtras();
    $("mapCount").textContent = `${arr.length} cámaras · ${verified.size} con video verificado ahora`
      + (state.geo ? ` · distancia desde tu ubicación` : "")
      + (state.routeData ? ` · ruta ${state.routeData.distanceKm} km` : "")
      + (state.layerItems.length ? ` · ${state.layerItems.length} capas` : "")
      + (state.mapExtraLayers.length ? ` · ${state.mapExtraLayers.length} capas combinadas` : "");
  }
  function fitMap() {
    if (!state.map) return;
    const arr = mapRows().filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon));
    if (!arr.length) { toast("No hay cámaras con estos filtros para ajustar el mapa."); return; }
    state.map.fitBounds(L.latLngBounds(arr.map((c) => [c.lat, c.lon])).pad(0.12), { maxZoom: 12 });
  }
  function locateMap() {
    if (!state.map) initMap();
    if (!navigator.geolocation) { toast("Este navegador no dispone de geolocalización."); return; }
    navigator.geolocation.getCurrentPosition(async (pos) => {
      state.geo = {
        lat: pos.coords.latitude, lon: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
      };
      state.map.setView([state.geo.lat, state.geo.lon], 11);
      render(); renderMap();
      await loadNearby(true, true);
      renderMap();
    }, (e) => toast("No se pudo obtener la ubicación: " + (e.message || "permiso denegado"), 4800),
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  }

  /* ------------------------------------------------------------------ */
  /* IA explicable: asistente, ruta, resumen, alertas, contexto, grupos   */
  /* ------------------------------------------------------------------ */
  function aiBlock(title, lines, sources) {
    const b = el("div", "ai-block");
    b.appendChild(el("h4", null, title));
    (Array.isArray(lines) ? lines : [lines]).forEach((t) => b.appendChild(el("p", null, t)));
    if (sources && sources.length) b.appendChild(sourceLinks(sources));
    return b;
  }
  function cameraCards(list) {
    const box = el("div", "ai-results");
    (list || []).forEach((c) => {
      const card = el("div", "ai-result"), left = el("div"), right = el("div");
      left.appendChild(el("b", null, c.name));
      left.appendChild(el("small", null, [c.zone, c.source,
        c.distKm !== undefined ? fmtDist(c.distKm) : null,
        c.atKm !== undefined ? `km ${c.atKm} de la ruta` : null].filter(Boolean).join(" · ")));
      const pill = el("span", "trust-pill " + trustClass(c.trust || 0),
        `${c.trustLabel || "Confianza"} ${c.trust !== undefined ? c.trust : ""}`.trim());
      right.appendChild(pill);
      const go = el("button", "chip", "Ver ▶");
      go.type = "button";
      go.addEventListener("click", () => {
        const full = state.cameras.find((x) => x.id === c.id);
        if (full) { selectCamera(full, false); setTab("visor"); }
      });
      right.appendChild(go);
      card.appendChild(left); card.appendChild(right);
      box.appendChild(card);
    });
    return box;
  }
  async function loadAiStats() {
    try {
      const j = await apiJson("/api/ai/stats");
      $("aiStats").textContent = `Historial local: ${j.successes} verificaciones correctas · ${j.failures} fallos · ${j.camerasWithHistory} cámaras con datos`;
    } catch (_) { $("aiStats").textContent = "Historial local no disponible."; }
  }
  function renderAnswer(j) {
    const ex = $("aiExplain"), res = $("aiResults");
    ex.replaceChildren(); res.replaceChildren();
    ex.hidden = false;
    ex.appendChild(aiBlock("Cómo lo interpreté", j.interpretation, j.sources));
    const note = el("p", "ai-hint", `Confianza: ${j.confidence}. ${j.note}`);
    ex.appendChild(note);
    const clear = el("button", "chip ghost", "Quitar filtro IA");
    clear.type = "button";
    clear.addEventListener("click", () => {
      state.aiIds = null; res.replaceChildren(); ex.hidden = true; render();
      toast("Filtro de IA retirado.");
    });
    ex.appendChild(clear);
    if (!j.count) res.appendChild(el("div", "empty", "No hay cámaras oficiales que coincidan con esa descripción."));
    else {
      const head = el("p", "ai-hint", `${j.count} cámaras encontradas. Se muestran hasta 30.`);
      res.appendChild(head);
      res.appendChild(cameraCards(j.cameras));
    }
  }
  async function askAi() {
    const q = $("aiQuery").value.trim();
    if (!q) { toast("Escribe una pregunta o una descripción."); return; }
    $("aiResults").replaceChildren(el("div", "loading", "Traduciendo a datos reales…"));
    try {
      const j = await apiJson("/api/ai/query", aiPayload({ q }));
      state.aiIds = new Set(j.ids);
      renderAnswer(j);
      render();
      toast(`${j.count} cámaras para «${q}».`, 4200);
    } catch (e) {
      $("aiResults").replaceChildren(el("div", "empty", e.message));
    }
  }
  function renderRoute(j) {
    const box = $("routeOut"); box.replaceChildren();
    box.appendChild(aiBlock("Ruta calculada", [
      j.summary,
      `Origen: ${j.start.name}. Destino: ${j.end.name}.`,
      "El tiempo es una estimación de OSRM sin tráfico en vivo; las cámaras son las publicadas por las agencias.",
    ], j.sources));
    if (j.cameras.length) box.appendChild(cameraCards(j.cameras));
    else box.appendChild(el("div", "empty", "No hay cámaras con video dentro del margen elegido. Prueba 5 o 10 km."));
    $("btnRouteMap").hidden = false;
    if (state.map) renderMap();
  }
  async function calcRoute() {
    const from = $("routeFrom").value.trim(), to = $("routeTo").value.trim();
    if (!to) { toast("Escribe un destino."); return; }
    if (!from && !state.geo) { toast("Escribe un origen o usa tu GPS."); return; }
    $("routeOut").replaceChildren(el("div", "loading", "Calculando ruta y cámaras cercanas al trayecto…"));
    try {
      const j = await apiJson("/api/ai/route", aiPayload({
        from: from || null, to,
        bufferKm: parseFloat($("routeBuffer").value) || 2.5,
        useGeo: !from && !!state.geo,
      }));
      state.routeData = j;
      renderRoute(j);
      toast(j.summary, 5000);
    } catch (e) {
      state.routeData = null;
      $("routeOut").replaceChildren(el("div", "empty", e.message));
    }
  }
  async function loadMapLayers() {
    if (!state.map) initMap();
    const info = $("mapLayerInfo");
    info.hidden = false;
    info.textContent = "Consultando capas públicas (NWS · Open-Meteo · 511NJ · OpenStreetMap)…";
    try {
      const q = state.geo ? `?lat=${state.geo.lat}&lon=${state.geo.lon}&infra=1&radiusKm=25` : "?infra=1&radiusKm=25";
      const j = await apiJson("/api/ai/layers" + q);
      state.layerItems = j.layers || [];
      const counts = {};
      state.layerItems.forEach((it) => { counts[it.type] = (counts[it.type] || 0) + 1; });
      info.textContent = `${state.layerItems.length} capas: ` +
        Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(" · ") +
        ". Fuente: NWS, Open-Meteo, 511NJ y OSM. Toca un punto con cámara para abrirla.";
      renderMap();
    } catch (e) {
      state.layerItems = [];
      info.textContent = "No se pudieron cargar las capas: " + e.message;
      renderMap();
    }
  }
  async function makeBrief() {
    $("briefOut").replaceChildren(el("div", "loading", "Reuniendo favoritos, clima y alertas…"));
    try {
      const j = await apiJson("/api/ai/brief", aiPayload());
      const box = $("briefOut"); box.replaceChildren();
      box.appendChild(aiBlock(j.headline, j.bullets.map((b) =>
        `${b.text} [confianza: ${b.confidence}]`), j.sources));
      box.appendChild(el("p", "ai-hint", `Basado en ${j.basis} · generado ${j.at}.`));
    } catch (e) { $("briefOut").replaceChildren(el("div", "empty", e.message)); }
  }
  async function loadAlerts() {
    $("alertsOut").replaceChildren(el("div", "loading", "Consultando alertas oficiales…"));
    try {
      const j = await apiJson("/api/ai/alerts", aiPayload({ state: $("alertState").value }));
      const box = $("alertsOut"); box.replaceChildren();
      box.appendChild(aiBlock("Zona: " + j.area, [
        `${j.alerts.length} señales · ${j.camerasChecked} cámaras revisadas · ${j.lowTrust} con baja confianza.`,
        j.note,
      ], j.sources));
      j.alerts.forEach((a) => {
        const b = el("div", "ai-block");
        const h = el("h4", null, `${a.type} · ${a.zone}`);
        b.appendChild(h);
        b.appendChild(el("p", "level-" + a.level, `${a.text} · nivel ${a.level} · confianza ${a.confidence}`));
        const ul = el("ul");
        (a.evidence || []).forEach((e) => ul.appendChild(el("li", null, e)));
        b.appendChild(ul);
        if (a.source) b.appendChild(sourceLinks([a.source]));
        box.appendChild(b);
      });
    } catch (e) { $("alertsOut").replaceChildren(el("div", "empty", e.message)); }
  }
  async function makeGroups() {
    $("groupsOut").replaceChildren(el("div", "loading", "Agrupando tus favoritos…"));
    try {
      const j = await apiJson("/api/ai/groups", aiPayload());
      const box = $("groupsOut"); box.replaceChildren();
      if (!j.groups.length) { box.appendChild(el("div", "empty", j.note)); return; }
      j.groups.forEach((g) => {
        const b = el("div", "ai-block");
        b.appendChild(el("h4", null, `${g.icon} ${g.title} · ${g.count}`));
        b.appendChild(el("p", null, g.description));
        g.cameras.forEach((c) => {
          const btn = el("button", "chip ghost", `${c.name} · C ${c.trust}`);
          btn.type = "button";
          btn.addEventListener("click", () => {
            const full = state.cameras.find((x) => x.id === c.id);
            if (full) { selectCamera(full, false); setTab("visor"); }
          });
          b.appendChild(btn);
        });
        box.appendChild(b);
      });
      box.appendChild(el("p", "ai-hint", j.note));
    } catch (e) { $("groupsOut").replaceChildren(el("div", "empty", e.message)); }
  }
  async function explainContext(c, switchTab = false) {
    if (!c) { toast("Selecciona primero una cámara."); return; }
    if (switchTab) setTab("ia");
    const card = $("btnContextAi").closest("details");
    if (card) card.open = true;
    $("contextOut").replaceChildren(el("div", "loading", "Correlacionando fuentes públicas…"));
    try {
      const j = await apiJson("/api/ai/context", aiPayload({ id: c.id }));
      const box = $("contextOut"); box.replaceChildren();
      box.appendChild(aiBlock(j.name, j.lines, j.sources));
      if (j.events.length) {
        box.appendChild(aiBlock("Eventos oficiales 511NJ cerca", j.events.slice(0, 5).map((e) =>
          `${e.category || e.type} · ${e.facility || e.county} · ${e.distKm} km · id ${e.id}`)));
      }
      if (j.neighbors.length) box.appendChild(cameraCards(j.neighbors));
      box.appendChild(el("p", "ai-hint", `Confianza ${j.confidence}. ${j.note}`));
    } catch (e) { $("contextOut").replaceChildren(el("div", "empty", e.message)); }
  }

  /* ------------------------------------------------------------------ */
  /* Comparador de cámaras vecinas (HLS independiente por ranura)         */
  /* ------------------------------------------------------------------ */
  function comparePool(primary) {
    const pool = new Map();
    const add = (c) => { if (c && c.stream && !pool.has(c.id)) pool.set(c.id, c); };
    if (primary) add(primary);
    state.favs.forEach((id) => add(state.cameras.find((c) => c.id === id)));
    const anchor = primary && Number.isFinite(primary.lat)
      ? primary : (state.geo || { lat: 40.15, lon: -74.65 });
    state.cameras.filter((c) => c.stream).map((c) => ({
      c, d: haversine(anchor.lat, anchor.lon, c.lat || 0, c.lon || 0),
    })).sort((a, b) => a.d - b.d).slice(0, 16).forEach((x) => add(x.c));
    return [...pool.values()].slice(0, 20);
  }
  function destroyCompare() {
    state.compareHls.forEach((h) => { try { h.destroy(); } catch (_) {} });
    state.compareHls = [];
    document.querySelectorAll("#compareGrid video").forEach((v) => {
      try { v.pause(); v.removeAttribute("src"); v.load(); } catch (_) {}
    });
    state.compareCards = [];
  }
  function closeCompare() {
    destroyCompare();
    $("compareModal").hidden = true;
  }
  async function compareOpen(ids) {
    if (!ids || ids.length < 2) { toast("Selecciona al menos 2 cámaras."); return; }
    const primary = state.cameras.find((c) => c.id === ids[0]);
    try {
      const j = await apiJson("/api/ai/compare", aiPayload({ ids }));
      const pool = comparePool(primary);
      // Solo se abren streams que responden con video real: las cámaras con
      // token otp caducado o sin señal se sustituyen por vecinas verificadas.
      const candidates = [...new Set([...j.cameras.map((x) => x.id), ...pool.map((c) => c.id)])].slice(0, 24);
      let working = new Set(candidates);
      try {
        const chk = await apiJson("/api/streams/check", { ids: candidates });
        working = new Set(chk.working);
      } catch (_) { /* sin verificación se conserva el comportamiento anterior */ }
      const goodPool = pool.filter((c) => working.has(c.id));
      const visiblePool = goodPool.length >= 2 ? goodPool : pool;
      const used = new Set();
      const chosen = j.cameras.map((item) => {
        let cid = item.id;
        if (!working.has(cid)) {
          const alt = goodPool.find((c) => !used.has(c.id));
          if (alt) cid = alt.id;
        }
        used.add(cid);
        return cid;
      });
      $("compareModal").hidden = false;
      const replaced = chosen.filter((cid, i) => cid !== j.cameras[i].id).length;
      $("compareHead").textContent = `${j.recommendation} ${j.note}`
        + (replaced ? ` ${replaced} cámara(s) sin señal se sustituyeron por vecinas verificadas.` : "");
      const grid = $("compareGrid"); grid.replaceChildren();
      destroyCompare();
      j.cameras.forEach((item, idx) => {
        const card = el("div", "compare-card");
        const sel = el("select");
        sel.setAttribute("aria-label", "Cambiar cámara en esta ranura");
        visiblePool.forEach((c) => sel.add(new Option(c.name + " · " + c.source, c.id)));
        const cid = chosen[idx];
        sel.value = cid;
        const video = el("video"); video.playsInline = true; video.muted = true;
        video.controls = true;
        const body = el("div", "compare-card-body");
        const name = el("b", null, (state.cameras.find((c) => c.id === cid) || {}).name || item.name);
        const note = el("p", null, `Confianza ${item.trustLabel} (${item.trust}/100)`);
        body.appendChild(name); body.appendChild(note);
        card.appendChild(sel); card.appendChild(video); card.appendChild(body);
        grid.appendChild(card);
        const slot = { sel, video, name, note, hls: null, id: cid };
        state.compareCards.push(slot);
        const load = (cid) => {
          slot.id = cid;
          const c = state.cameras.find((x) => x.id === cid);
          name.textContent = c ? c.name : cid;
          note.textContent = `Confianza ${c && c.trustLabel ? c.trustLabel : "—"} (${c ? c.trust : "—"}/100)`;
          if (slot.hls) { try { slot.hls.destroy(); } catch (_) {} slot.hls = null; }
          state.compareHls = state.compareHls.filter((h) => h !== slot.hls);
          try { video.pause(); video.removeAttribute("src"); video.load(); } catch (_) {}
          if (!c || !c.stream) { note.textContent += " · sin stream público"; return; }
          const url = proxyUrl(c);
          if (window.Hls && Hls.isSupported()) {
            const hls = new Hls({ lowLatencyMode: true, enableWorker: true,
              backBufferLength: 20, maxBufferLength: 10 });
            slot.hls = hls; state.compareHls.push(hls);
            hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
            hls.on(Hls.Events.ERROR, (_e, data) => {
              if (data && data.fatal) note.textContent += " · video no disponible";
            });
            hls.loadSource(url); hls.attachMedia(video);
          } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
            video.src = url; video.play().catch(() => {});
          } else note.textContent += " · navegador sin HLS";
        };
        sel.addEventListener("change", () => load(sel.value));
        load(cid);
      });
      if (j.pairs.length) {
        const p = j.pairs[0];
        $("compareHead").textContent += ` Separación real entre las dos primeras: ${p.distKm} km.`;
      }
      sourceLinks(j.sources).querySelectorAll("a").forEach((a) => {
        const wrap = el("div", "compare-note"); wrap.appendChild(a);
        grid.parentElement.insertBefore(wrap, grid.nextSibling);
      });
    } catch (e) { toast("No se pudo abrir el comparador: " + e.message, 5000); }
  }
  function nearbyForCompare(c) {
    const arr = state.cameras.filter((x) => x.id !== c.id && x.stream && Number.isFinite(x.lat))
      .map((x) => ({ x, d: haversine(c.lat || 40.15, c.lon || -74.65, x.lat, x.lon) }))
      .sort((a, b) => a.d - b.d).slice(0, 3).map((o) => o.x.id);
    return [c.id, ...arr];
  }

  /* ------------------------------------------------------------------ */
  /* Tours narrados (categoría aparte)                                   */
  /* ------------------------------------------------------------------ */
  function renderTour(j) {
    state.tourData = j;
    const box = $("tourOut"); box.replaceChildren();
    box.appendChild(aiBlock(j.tour, [j.intro], j.sources));
    j.steps.forEach((s, i) => {
      const step = el("div", "tour-step");
      step.appendChild(el("i", null, String(i + 1).padStart(2, "0")));
      const mid = el("div");
      mid.appendChild(el("b", null, s.name));
      mid.appendChild(el("p", null, s.text));
      step.appendChild(mid);
      const go = el("button", "chip", "Ver ▶");
      go.type = "button";
      go.addEventListener("click", () => {
        const c = state.cameras.find((x) => x.id === s.id);
        if (c) { selectCamera(c, false); setTab("visor"); }
      });
      step.appendChild(go);
      box.appendChild(step);
    });
    box.appendChild(el("div", "tour-outro", `${j.outro} ${j.total} cámaras en el tour · ${j.zones.length} zonas.`));
    $("btnSpeak").disabled = false;
    $("btnStopSpeak").hidden = true;
  }
  async function narrate() {
    const tour = $("tourNarr").value;
    if (!tour) { toast("Elige un tour oficial."); return; }
    $("tourOut").replaceChildren(el("div", "loading", "Armando el recorrido con cámaras reales…"));
    try {
      const j = await apiJson("/api/ai/tour", aiPayload({ tour }));
      renderTour(j);
      toast(`${j.total} cámaras del tour «${tour}».`, 4200);
    } catch (e) { $("tourOut").replaceChildren(el("div", "empty", e.message)); }
  }
  function speakTour() {
    if (!state.tourData || !("speechSynthesis" in window)) {
      toast("Este navegador no ofrece lectura en voz alta."); return;
    }
    stopSpeak(true);
    const j = state.tourData;
    const text = [j.intro, ...j.steps.map((s) => `${s.name}. ${s.text}`), j.outro].join(" ");
    const u = new SpeechSynthesisUtterance(text.slice(0, 9000));
    u.lang = "es-US"; u.rate = 0.98;
    const voices = (speechSynthesis.getVoices() || []);
    const es = voices.find((v) => /^es/i.test(v.lang));
    if (es) u.voice = es;
    u.onend = () => { state.speaking = false; $("btnSpeak").disabled = false; $("btnStopSpeak").hidden = true; };
    u.onerror = () => { state.speaking = false; $("btnSpeak").disabled = false; $("btnStopSpeak").hidden = true; };
    state.speaking = true;
    $("btnSpeak").disabled = true; $("btnStopSpeak").hidden = false;
    speechSynthesis.speak(u);
  }
  function stopSpeak(silent = false) {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    state.speaking = false;
    if ($("btnSpeak")) $("btnSpeak").disabled = !state.tourData;
    if ($("btnStopSpeak")) $("btnStopSpeak").hidden = true;
    if (!silent) toast("Narración detenida.");
  }

  /* ------------------------------------------------------------------ */
  /* GPS                                                                 */
  /* ------------------------------------------------------------------ */
  function useGps() {
    if (!navigator.geolocation) { toast("Este navegador no dispone de geolocalización."); return; }
    const btn = $("btnGps"), original = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<span class="gps-ring">◌</span><span>Ubicando…</span>';
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        btn.disabled = false; btn.innerHTML = original;
        $("gpsLabel").textContent = "Actualizar ubicación";
        state.geo = { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy };
        state.locales = null;
        state.sensorsData = null;
        loadWeather(true).catch(() => {});
        state.nearCount = parseInt($("nearCount").value, 10) || 10;
        state.sort = "dist"; $("sort").value = "dist";
        state.q = ""; state.zone = ""; state.routeOnly = false; state.streamOnly = false;
        $("q").value = ""; $("zone").value = "";
        $("routeOnly").checked = false; $("streamOnly").checked = false;
        setTab("cerca");
        render();
        await loadNearby(true);
        if (!(state.locales || []).length) {
          for (const r of [50, 100]) {
            if (state.radius >= r) continue;
            $("radiusKm").value = String(r);
            await loadNearby(true, true);
            if ((state.locales || []).length) break;
          }
        }
        const best = (state.locales || [])[0];
        const info = $("gpsInfo");
        info.hidden = false;
        info.replaceChildren(document.createTextNode(
          `Ubicación: ${coords({ lat: state.geo.lat, lon: state.geo.lon })} (precisión ±${Math.round(state.geo.accuracy || 0)} m). ` +
          (best
            ? `La cámara en vivo más cercana es ${best.name} (${fmtDist(best.distKm)}), a ${state.radius} km de búsqueda.`
            : "No hay cámaras en vivo verificadas hasta 100 km. La cobertura oficial es Nueva Jersey y Delaware; abre «Locales en vivo» para probar otro radio."
          )
        ));
        toast(best ? `${state.locales.length} cámaras en vivo verificadas a ${state.radius} km a la redonda.` : "Ubicación obtenida, sin cámaras en vivo en 100 km.", 4600);
        if (state.selected) selectCamera(state.selected, false);
      },
      (err) => {
        btn.disabled = false; btn.innerHTML = original;
        const msg = err.code === 1
          ? "Permiso de ubicación denegado. Revisa los permisos del sitio en tu navegador."
          : err.code === 2 ? "No se pudo determinar tu ubicación." : "La geolocalización tardó demasiado. Inténtalo de nuevo.";
        toast(msg, 5200);
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
    );
  }

  /* ------------------------------------------------------------------ */
  /* Visor HLS + zoom digital                                            */
  /* ------------------------------------------------------------------ */
  function stopPlayer() {
    state.fallbackDone = false;
    resetZoom();
    if (state.hls) { try { state.hls.destroy(); } catch (_) {} state.hls = null; }
    const v = $("video");
    try { v.pause(); v.removeAttribute("src"); v.load(); } catch (_) {}
    $("playerErr").hidden = true;
    $("stageTools").hidden = true;
    $("btnShot").disabled = true; $("btnMute").disabled = true; $("btnFull").disabled = true;
  }
  function proxyUrl(c) { return "/api/hls/" + encodeURIComponent(c.id) + "/" + encodeURIComponent(c.stream); }
  function playerError(msg) { const e = $("playerErr"); e.textContent = msg; e.hidden = false; }
  async function reportBroken(c, reason) {
    if (!c || !c.stream || state.reported.has(c.id)) return;
    state.reported.add(c.id);
    try {
      await fetch("/api/stream-report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: c.id, reason: String(reason || "playback").slice(0, 160) }),
      });
    } catch (_) { /* el filtro local sigue aplicando aunque falle el aviso */ }
    state.cameras = state.cameras.filter((x) => x.id !== c.id);
    if (state.locales) state.locales = state.locales.filter((x) => x.id !== c.id);
    render(); renderLocal();
    if (state.selected && state.selected.id === c.id) {
      $("viewBadge").textContent = "No disponible";
      $("viewBadge").className = "badge off";
    }
    resetReportButton();
    toast("Cámara retirada: el video no respondió. Se ocultará durante unas horas.", 4800);
  }
  function resetReportButton() {
    clearTimeout(reportTimer);
    state.reportArmed = null;
    const btn = $("btnReport");
    if (btn) {
      btn.classList.remove("armed");
      btn.innerHTML = '⚑ <span>Reportar fallo</span>';
    }
  }
  function reportButton(c) {
    const btn = $("btnReport");
    if (!c || !c.stream) { toast("Esta cámara no tiene video que reportar."); return; }
    if (state.reported.has(c.id)) { toast("Esta cámara ya fue reportada en esta sesión."); return; }
    if (state.reportArmed === c.id) {
      reportBroken(c, "reporte manual");
      return;
    }
    state.reportArmed = c.id;
    btn.classList.add("armed");
    btn.innerHTML = '⚠ <span>Confirmar fallo</span>';
    toast("Pulsa otra vez para confirmar que esta cámara no funciona.", 4500);
    reportTimer = setTimeout(() => {
      if (state.reportArmed === c.id) resetReportButton();
    }, 5000);
  }
  function nativeFallback(url, c) {
    if (state.fallbackDone) return;
    state.fallbackDone = true;
    try {
      if (state.hls) { state.hls.destroy(); state.hls = null; }
      const v = $("video");
      v.src = url;
      v.play().catch(() => {
        playerError("El navegador no pudo reproducir este stream. La cámara se ha retirado de la lista.");
        reportBroken(c, "native playback");
      });
    } catch (_) {
      playerError("No se pudo reproducir este stream.");
      reportBroken(c, "native exception");
    }
  }
  function playCamera(c) {
    if (!c.stream) { playerError("Esta cámara no tiene un stream público verificado en la fuente oficial."); return; }
    stopPlayer();
    const url = proxyUrl(c), v = $("video");
    $("placeholder").hidden = true; v.hidden = false; $("stageTools").hidden = false;
    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: true, enableWorker: true, backBufferLength: 30, maxBufferLength: 12 });
      state.hls = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        v.play().catch(() => playerError("Pulsa reproducir para iniciar el video."));
      });
      function onHlsError(_e, data) {
        if (!data || !data.fatal) return;
        const reason = (data.type || "error") + "/" + (data.details || "fatal");
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR && !state.fallbackDone) {
          nativeFallback(url, c);
          return;
        }
        playerError("No se pudo cargar el video. La cámara se ha retirado de la lista.");
        reportBroken(c, reason);
      }
      hls.on(Hls.Events.ERROR, onHlsError);
      hls.loadSource(url); hls.attachMedia(v);
    } else if (v.canPlayType("application/vnd.apple.mpegurl")) {
      v.src = url;
      v.play().catch(() => {
        playerError("Pulsa reproducir para iniciar el video. Si no arranca, prueba otra cámara.");
        reportBroken(c, "native HLS");
      });
    } else {
      playerError("Este navegador no admite HLS. Usa una versión reciente de Chrome, Edge o Safari.");
    }
  }
  function selectCamera(c, autoplay = true) {
    state.selected = c;
    resetReportButton();
    document.querySelectorAll(".item,.ncard").forEach((n) => n.classList.toggle("sel", n.dataset.camId === c.id));
    stopPlayer();
    $("vName").textContent = c.name;
    $("vZone").textContent = c.zone + " · " + c.source;
    $("vCoords").textContent = coords(c);
    const tv = $("vTours");
    if (tv) {
      const names = c.tours || [];
      tv.textContent = names.length ? `Tours: ${names.slice(0, 2).join(", ")}${names.length > 2 ? ` +${names.length - 2}` : ""}` : "";
      tv.hidden = !names.length;
    }
    const dv = $("vDist"), d = distTo(c);
    if (d !== null) { dv.textContent = fmtDist(d) + " desde ti"; dv.hidden = false; } else dv.hidden = true;
    const badge = $("viewBadge");
    badge.textContent = c.enabled === false ? "Fuera de servicio" : c.stream ? "En vivo" : "Sin stream";
    badge.className = "badge " + (c.enabled === false ? "off" : c.stream ? "live" : "muted");
    $("btnPlay").disabled = !c.stream;
    $("btnShare").disabled = false;
    $("btnFav").disabled = false; syncFavUI(c);
    $("btnReport").disabled = !c.stream || state.reported.has(c.id);
    $("btnOfficial").hidden = !c.official; $("btnOfficial").href = c.official || "#";
    $("vNote").textContent = c.stream
      ? "Stream oficial servido mediante proxy local. Zoom digital disponible; las fuentes públicas no permiten control PTZ remoto."
      : "Esta entrada del inventario oficial no expone un stream HLS público.";
    if (autoplay && c.stream) playCamera(c);
  }
  function applyZoom() {
    const v = $("video");
    v.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
    $("zoomLabel").textContent = "×" + state.zoom.toFixed(1);
  }
  function setZoom(z) {
    state.zoom = Math.min(3, Math.max(1, Math.round(z * 10) / 10));
    if (state.zoom === 1) { state.panX = 0; state.panY = 0; }
    applyZoom();
  }
  function resetZoom() { state.zoom = 1; state.panX = 0; state.panY = 0; applyZoom(); }
  function shot() {
    const v = $("video"), c = state.selected;
    if (!c || !v.videoWidth || !v.videoHeight) { toast("Espera a que el video cargue antes de capturar."); return; }
    try {
      const cv = document.createElement("canvas");
      cv.width = v.videoWidth; cv.height = v.videoHeight;
      cv.getContext("2d").drawImage(v, 0, 0);
      const a = document.createElement("a");
      a.download = `cam-${String(c.id).replace(/[^a-z0-9_-]/gi, "_")}-${Date.now()}.png`;
      a.href = cv.toDataURL("image/png"); a.click();
      toast("Fotograma guardado.");
    } catch (_) { toast("No se pudo capturar el fotograma."); }
  }
  async function shareCamera() {
    if (!state.selected) return;
    const url = location.origin + location.pathname + "?cam=" + encodeURIComponent(state.selected.id);
    try { await navigator.clipboard.writeText(url); toast("Enlace a la cámara copiado."); }
    catch (_) { toast("Enlace: " + url, 7000); }
  }

  /* ------------------------------------------------------------------ */
  /* Enlace móvil                                                        */
  /* ------------------------------------------------------------------ */
  async function openMobile() {
    $("mobileModal").hidden = false;
    try {
      const r = await fetch("/api/mobile", { cache: "no-store" });
      const j = await r.json();
      if (!j.ok || !j.url) throw new Error("sin enlace");
      state.mobileUrl = j.url;
      $("mobileUrl").textContent = j.url;
      $("mobileQr").hidden = false;
      $("mobileQr").src = "/assets/qr-movil.png?v=" + Date.now();
      $("mobileNote").textContent = "Escanea el código QR desde tu celular o copia el enlace. Funciona en Android y iPhone con certificado público.";
      $("btnCopyMobile").disabled = false;
    } catch (_) {
      $("mobileUrl").textContent = "Aún no hay enlace móvil.";
      $("mobileQr").hidden = true;
      $("mobileNote").textContent = 'Ejecuta «start-mobile.bat» en la computadora para generar el enlace HTTPS y el código QR.';
      $("btnCopyMobile").disabled = true;
    }
  }
  async function copyMobile() {
    if (!state.mobileUrl) return;
    try { await navigator.clipboard.writeText(state.mobileUrl); toast("Enlace móvil copiado."); }
    catch (_) { toast(state.mobileUrl, 7000); }
  }

  /* ------------------------------------------------------------------ */
  /* Actualización y procedencia                                         */
  /* ------------------------------------------------------------------ */
  async function postRefresh(kind, showUi = true) {
    const r = await fetch("/api/refresh", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "No se pudo iniciar la actualización");
    if (showUi) pollJob(j.job);
    return j.job;
  }
  function pollJob(jid) {
    if (state.poll) clearInterval(state.poll);
    const log = $("refreshlog");
    log.hidden = false;
    $("rlState").textContent = "en cola…";
    $("rlBody").textContent = "Consultando fuentes oficiales…";
    let ticks = 0;
    state.poll = setInterval(async () => {
      ticks++;
      try {
        const r = await fetch("/api/refresh/status", { cache: "no-store" });
        const j = await r.json();
        const job = (j.jobs || {})[jid];
        if (!job) { if (ticks > 10) finish(); return; }
        $("rlState").textContent = job.status === "running" ? "consultando…" : job.status === "queued" ? "en cola…" : job.status;
        $("rlBody").textContent = (job.log || []).join("\n");
        if (job.status === "done" || job.status === "error") {
          toast(job.status === "done" ? "Fuentes oficiales actualizadas." : "La actualización terminó con un error; revisa el registro.");
          await loadCameras(true);
          setTimeout(() => { log.hidden = true; }, 7000);
          finish();
        }
      } catch (_) { if (ticks > 30) finish(); }
    }, 1500);
    function finish() { if (state.poll) clearInterval(state.poll); state.poll = null; }
  }
  function renderSources(meta) {
    const body = $("sourcesBody");
    body.replaceChildren();
    const sources = (meta && meta.sources) || [];
    if (!sources.length) { body.appendChild(el("p", "srcnote", "No hay metadatos de procedencia disponibles.")); return; }
    sources.forEach((s) => {
      const box = el("div", "srcitem");
      box.appendChild(el("b", null, s.name));
      if (s.url) { const a = el("a", null, s.url); a.href = s.url; a.target = "_blank"; a.rel = "noopener"; box.appendChild(a); }
      const bits = [];
      if (s.tour) bits.push("Ruta: " + s.tour);
      if (s.feedTimestamp) bits.push("Timestamp del feed: " + s.feedTimestamp);
      if (s.cameras !== undefined) bits.push("Cámaras: " + s.cameras);
      if (s.streams !== undefined) bits.push("Streams: " + s.streams);
      if (s.method) bits.push(s.method);
      box.appendChild(el("p", null, bits.join(" · ")));
      body.appendChild(box);
    });
    if (meta && meta.generated) body.appendChild(el("p", "srcnote", "Generado: " + meta.generated));
    if (meta && meta.notes) body.appendChild(el("p", "srcnote", meta.notes));
    const more = el("div", "srcitem");
    more.appendChild(el("b", null, "Fuentes públicas adicionales"));
    [["NWS · clima, alertas y radio meteorológica", "https://api.weather.gov/"],
     ["Open-Meteo · clima actual y pronóstico", "https://open-meteo.com/"],
     ["USGS NWIS · sensores de agua", "https://waterservices.usgs.gov/"],
     ["Nominatim · geocodificación y vía actual", "https://nominatim.openstreetmap.org/"],
     ["Radio Browser · directorio de emisoras", "https://www.radio-browser.info/"]]
      .forEach(([name, url]) => {
        const a = el("a", null, name + " ↗");
        a.href = url; a.target = "_blank"; a.rel = "noopener"; more.appendChild(a);
      });
    more.appendChild(el("p", null,
      "Zonas locales: agrupación informativa de cámaras 511NJ reales por distancia al centro municipal. " +
      "Radio: streams HTTPS verificados en el sitio oficial de cada emisora; esta app no redistribuye ni graba la señal."));
    body.appendChild(more);
  }

  /* ------------------------------------------------------------------ */
  /* Guía                                                                */
  /* ------------------------------------------------------------------ */
  function renderWizard() {
    const s = WIZARD[state.wiz];
    $("wTitle").textContent = s.title;
    $("wImg").src = s.img; $("wImg").alt = s.title;
    $("wText").textContent = s.text;
    const ul = $("wList"); ul.replaceChildren();
    s.items.forEach((it) => ul.appendChild(el("li", null, it)));
    const dots = $("wDots"); dots.replaceChildren();
    WIZARD.forEach((_, i) => {
      const d = el("i", i === state.wiz ? "on" : "");
      d.title = `Paso ${i + 1}`;
      d.addEventListener("click", () => { state.wiz = i; renderWizard(); });
      dots.appendChild(d);
    });
    $("wPrev").disabled = state.wiz === 0;
    $("wNext").textContent = state.wiz === WIZARD.length - 1 ? "Empezar" : "Siguiente";
  }
  function openWizard(force = false) {
    if (!force && getLS(LS.wizard) === "1") return;
    state.wiz = 0; renderWizard(); $("overlay").hidden = false; $("wNext").focus();
  }
  function closeWizard(seen = true) { $("overlay").hidden = true; if (seen) setLS(LS.wizard, "1"); }

  /* ================================================================== */
  /* INTERFAZ PRINCIPAL · EXPERIENCIA DE CONDUCCIÓN                      */
  /* La administración sigue disponible en el botón discreto «Datos».   */
  /* ================================================================== */
  const TRIP_PROFILES = [
    { id: "explorador", icon: "✦", name: "Explorador", desc: "Equilibrio entre ruta, cámaras, clima y servicios.", bufferKm: 3, camera: true, alerts: true, sensors: true, spotSec: 8 },
    { id: "directo", icon: "➜", name: "Directo", desc: "Solo lo esencial: ruta, cámaras y avisos críticos.", bufferKm: 1.5, camera: true, alerts: true, sensors: false, spotSec: 5 },
    { id: "panorama", icon: "◎", name: "Panorama", desc: "Máximo contexto: zonas, sensores y servicios.", bufferKm: 5, camera: true, alerts: true, sensors: true, spotSec: 10 },
    { id: "tranquilo", icon: "☾", name: "Tranquilo", desc: "Sin interrupciones salvo alertas graves.", bufferKm: 2, camera: false, alerts: true, sensors: false, spotSec: 4 },
    { id: "observador", icon: "▣", name: "Observador", desc: "Más cámaras y más segundos en cada una.", bufferKm: 6, camera: true, alerts: false, sensors: true, spotSec: 12 },
  ];
  const QUICK_DESTS = [
    "Somerville, NJ", "Newark, NJ", "Trenton, NJ",
    "Atlantic City, NJ", "Wilmington, DE", "Philadelphia, PA",
  ];

  function freshTrip() {
    return {
      active: false, running: false, mode: "sim", follow: true,
      profile: "explorador", musicId: "", music: null,
      prefs: { cameras: true, alerts: true, sensors: true, voice: false },
      from: null, to: null, route: null, cum: null, services: null,
      weather: null, corridor: null, sensors: null, layers: [], events: null,
      progressKm: 0, totalKm: 0, durationMin: 0, pos: null, speed: 90,
      startedAt: 0, lastTick: 0, log: [], chipKeys: new Set(), seenCams: new Set(),
      spotlight: null, spotTimer: null, spotCount: 0, spotHls: null,
      geoWatch: null, geoAtKm: null, finished: false,
      here: "", hereAt: null, hereAtTime: 0, hereBusy: false,
      radar: null, radarLoading: false, roadfacts: null, roadLoading: false,
      satellite: null, satelliteLoading: false,
      coastal: null, coastLoading: false, accuracyM: 60, contextLoading: false,
    };
  }
  function trip() { if (!state.trip) state.trip = freshTrip(); return state.trip; }
  function profileNow() { return TRIP_PROFILES.find((p) => p.id === trip().profile) || TRIP_PROFILES[0]; }
  function shortName(s, n = 26) {
    const v = String(s || "");
    return v.length <= n ? v : v.slice(0, n - 1) + "…";
  }
  function saveTripPrefs() {
    const t0 = trip();
    setLS(LS.tripPrefs, JSON.stringify({ profile: t0.profile, musicId: t0.musicId, prefs: t0.prefs }));
  }
  function loadTripPrefs() {
    const t0 = trip();
    try {
      const p = JSON.parse(getLS(LS.tripPrefs) || "{}");
      if (TRIP_PROFILES.some((x) => x.id === p.profile)) t0.profile = p.profile;
      if (typeof p.musicId === "string") t0.musicId = p.musicId;
      if (p.prefs && typeof p.prefs === "object") Object.assign(t0.prefs, p.prefs);
    } catch (_) { /* ajustes por defecto */ }
  }

  /* ---- geocodificación y geometría de ruta ---- */
  async function geocodePlace(text) {
    const q = String(text || "").trim();
    if (!q) return null;
    const m = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (m) {
      const lat = parseFloat(m[1]), lon = parseFloat(m[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) return { name: q, lat, lon };
    }
    try {
      const j = await fetch("/api/geocode?q=" + encodeURIComponent(q) + "&limit=1")
        .then((r) => r.json());
      return j && j.place ? j.place : null;
    } catch (_) { return null; }
  }
  async function fetchDestSuggest(q) {
    const host = $("tripSuggest");
    if (!host) return;
    if (q.length < 3) { host.replaceChildren(); return; }
    host.replaceChildren(el("div", "trip-hint", "Buscando lugares…"));
    try {
      const j = await fetch("/api/geocode?q=" + encodeURIComponent(q) + "&limit=5").then((r) => r.json());
      host.replaceChildren();
      (j.places || []).forEach((p) => {
        const b = el("button", null, shortName(p.name, 64));
        b.type = "button";
        b.title = p.name;
        b.addEventListener("click", () => setDestination(p));
        host.appendChild(b);
      });
      if (!host.children.length) host.appendChild(el("div", "trip-hint", "Sin resultados. Prueba otro nombre o unas coordenadas."));
    } catch (_) { host.replaceChildren(); }
  }
  function setDestination(p) {
    if (!p) return;
    const t0 = trip();
    t0.to = p;
    $("tripDest").value = shortName(p.name, 64);
    $("tripSuggest").replaceChildren();
    const r = $("tripDestResolved");
    r.hidden = false;
    r.textContent = `Destino: ${p.name} · ${p.lat.toFixed(4)}, ${p.lon.toFixed(4)} · Nominatim / OpenStreetMap`;
  }
  async function confirmDest() {
    const q = $("tripDest").value.trim();
    if (!q) { toast("Escribe un destino o elige una sugerencia."); return; }
    const p = await geocodePlace(q);
    if (!p) { toast("No se pudo resolver ese destino. Prueba «Newark, NJ» o 40.62,-74.60."); return; }
    setDestination(p);
  }
  function routeCumulative(geometry) {
    const cum = [0];
    for (let i = 1; i < geometry.length; i++) {
      cum.push(cum[i - 1] + haversine(geometry[i - 1][0], geometry[i - 1][1], geometry[i][0], geometry[i][1]));
    }
    return cum;
  }
  function pointAtKm(geometry, cum, km) {
    if (!geometry || !geometry.length) return { lat: 40.6209, lon: -74.6085 };
    if (km <= 0) return { lat: geometry[0][0], lon: geometry[0][1] };
    const total = cum[cum.length - 1];
    if (km >= total) return { lat: geometry[geometry.length - 1][0], lon: geometry[geometry.length - 1][1] };
    let lo = 0, hi = cum.length - 1;
    while (lo < hi - 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= km) lo = mid; else hi = mid; }
    const span = Math.max(1e-9, cum[hi] - cum[lo]);
    const f = (km - cum[lo]) / span;
    return {
      lat: geometry[lo][0] + (geometry[hi][0] - geometry[lo][0]) * f,
      lon: geometry[lo][1] + (geometry[hi][1] - geometry[lo][1]) * f,
    };
  }
  function routeProgressKm(geometry, cum, lat, lon) {
    let best = { off: Infinity, at: 0 };
    let acc = 0;
    for (let i = 0; i < geometry.length - 1; i++) {
      const la1 = geometry[i][0], lo1 = geometry[i][1];
      const la2 = geometry[i + 1][0], lo2 = geometry[i + 1][1];
      const seg = cum[i + 1] - cum[i];
      const dlat = la2 - la1, dlon = lo2 - lo1, den = dlat * dlat + dlon * dlon;
      const f = den === 0 ? 0 : Math.max(0, Math.min(1, ((lat - la1) * dlat + (lon - lo1) * dlon) / den));
      const off = haversine(lat, lon, la1 + f * dlat, lo1 + f * dlon);
      if (off < best.off) best = { off, at: acc + seg * f };
      acc += seg;
    }
    return best;
  }
  function traveledGeometry(geometry, cum, km) {
    if (!geometry || !geometry.length) return [];
    const out = [geometry[0]];
    const total = cum[cum.length - 1];
    if (km >= total) return geometry.slice();
    for (let i = 1; i < geometry.length; i++) {
      if (cum[i] <= km) out.push(geometry[i]);
      else { const p = pointAtKm(geometry, cum, km); out.push([p.lat, p.lon]); break; }
    }
    return out;
  }

  /* ---- mapa de conducción · MapLibre GL + teselas vectoriales CARTO ---- */
  const DRIVE_STYLES = {
    dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  };
  const EMPTY_FC = { type: "FeatureCollection", features: [] };
  const CLEAR_TILE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
  const DRIVE_ZOOM = 15.6;

  function driveStyleUrl() {
    return document.documentElement.getAttribute("data-theme") === "light"
      ? DRIVE_STYLES.light : DRIVE_STYLES.dark;
  }
  function routeBounds(g) {
    let west = 180, east = -180, south = 90, north = -90;
    (g || []).forEach((p) => {
      const la = +p[0], lo = +p[1];
      if (!Number.isFinite(la) || !Number.isFinite(lo)) return;
      west = Math.min(west, lo); east = Math.max(east, lo);
      south = Math.min(south, la); north = Math.max(north, la);
    });
    return west <= east ? [[west, south], [east, north]] : null;
  }
  function circlePolygon(lat, lon, radiusM) {
    const dLat = radiusM / 111320;
    const dLon = radiusM / (111320 * Math.max(0.15, Math.cos(lat * Math.PI / 180)));
    const ring = [];
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * Math.PI * 2;
      ring.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
    }
    return { type: "Polygon", coordinates: [ring] };
  }
  function pointFeatures(rows, props) {
    return { type: "FeatureCollection", features: (rows || []).filter((r) =>
      Number.isFinite(+r.lat) && Number.isFinite(+r.lon)).map((r) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [+r.lon, +r.lat] },
      properties: props(r) || {},
    })) };
  }
  function lineFeature(geometry) {
    if (!geometry || geometry.length < 2) return EMPTY_FC;
    return { type: "FeatureCollection", features: [{
      type: "Feature", properties: {},
      geometry: { type: "LineString", coordinates: geometry.map((p) => [+p[1], +p[0]]) },
    }] };
  }
  function mapEsc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function drivePopup(e, html) {
    const d = state.drive;
    if (!d || !d.map || !e.features || !e.features.length) return;
    if (d.popup) d.popup.remove();
    d.popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "250px", offset: 14 })
      .setLngLat(e.features[0].geometry.coordinates).setHTML(html).addTo(d.map);
  }
  function setDriveData(id, data) {
    const s = state.drive && state.drive.map && state.drive.map.getSource(id);
    if (s) s.setData(data);
  }
  function radarFrame() {
    const frames = (trip().radar && trip().radar.frames) || [];
    return frames.find((f) => f.kind === "nowcast" && f.url) ||
      frames.filter((f) => f.url).slice(-1)[0] || null;
  }
  function ensureDriveLayers() {
    const d = state.drive, m = d && d.map;
    if (!m || !m.isStyleLoaded()) return false;
    if (m.getSource("drive-radar")) return true;

    const frame = radarFrame();
    m.addSource("drive-radar", {
      type: "raster", tiles: [frame ? frame.url : CLEAR_TILE], tileSize: 256,
      attribution: '<a href="https://www.rainviewer.com/">Weather data by RainViewer</a>',
    });
    m.addLayer({ id: "drive-radar", type: "raster", source: "drive-radar",
      paint: { "raster-opacity": 0.55 } });

    m.addSource("drive-route", { type: "geojson", data: EMPTY_FC });
    m.addLayer({ id: "drive-route-casing", type: "line", source: "drive-route",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#07101f", "line-width": 10, "line-opacity": 0.85 } });
    m.addLayer({ id: "drive-route-line", type: "line", source: "drive-route",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#5ad1e6", "line-width": 5, "line-opacity": 0.96 } });

    m.addSource("drive-traveled", { type: "geojson", data: EMPTY_FC });
    m.addLayer({ id: "drive-traveled-line", type: "line", source: "drive-traveled",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffb347", "line-width": 5, "line-opacity": 0.98 } });

    [["drive-cameras", "#ffb347", 6], ["drive-services", "#8fd4ff", 4],
     ["drive-alerts", "#ff8080", 5], ["drive-roadfacts", "#ffe08a", 5],
     ["drive-coastal", "#6fd3ff", 5]].forEach(([id, color, radius]) => {
      m.addSource(id, { type: "geojson", data: EMPTY_FC });
      const paint = { "circle-radius": radius, "circle-color": color,
        "circle-stroke-color": "#0b1020", "circle-stroke-width": 2, "circle-stroke-opacity": 0.9 };
      if (id === "drive-services") paint["circle-color"] =
        ["match", ["get", "kind"], "fuel", "#ffb347", "charging_station", "#4ade9b",
         "toll_booth", "#ff8080", "#8fd4ff"];
      if (id === "drive-roadfacts") paint["circle-color"] =
        ["match", ["get", "kind"], "speed_camera", "#ff5f6d", "#ffe08a"];
      m.addLayer({ id, type: "circle", source: id, paint });
    });

    m.addSource("drive-accuracy", { type: "geojson", data: EMPTY_FC });
    m.addLayer({ id: "drive-accuracy-fill", type: "fill", source: "drive-accuracy",
      paint: { "fill-color": "#5ad1e6", "fill-opacity": 0.12 } });
    m.addLayer({ id: "drive-accuracy-line", type: "line", source: "drive-accuracy",
      paint: { "line-color": "#5ad1e6", "line-width": 1, "line-opacity": 0.5 } });
    return true;
  }
  function rebuildRadar() {
    const d = state.drive, m = d && d.map;
    if (!m || !m.isStyleLoaded()) return;
    const frame = radarFrame();
    if (m.getLayer("drive-radar")) m.removeLayer("drive-radar");
    if (m.getSource("drive-radar")) m.removeSource("drive-radar");
    const before = m.getLayer("drive-route-casing") ? "drive-route-casing" : undefined;
    m.addSource("drive-radar", {
      type: "raster", tiles: [frame ? frame.url : CLEAR_TILE], tileSize: 256,
      attribution: '<a href="https://www.rainviewer.com/">Weather data by RainViewer</a>',
    });
    m.addLayer({ id: "drive-radar", type: "raster", source: "drive-radar",
      paint: { "raster-opacity": 0.55 } }, before);
    applyLayerVisibility();
  }
  let satelliteRetryTimer = null;
  function scheduleSatelliteRetry(attempt = 0) {
    if (satelliteRetryTimer) return;
    const step = () => {
      satelliteRetryTimer = null;
      const t0 = trip(), m = state.drive && state.drive.map;
      const box = $("dlSatellite");
      if (!m || !box || !box.checked || !t0.satellite || !t0.satellite.ok) return;
      try {
        if (ensureSatelliteLayer()) { applyLayerVisibility(); return; }
      } catch (_) { /* el estilo aún no admite fuentes: se reintenta */ }
      if (attempt < 14) satelliteRetryTimer = setTimeout(() => step(attempt + 1), 500);
    };
    satelliteRetryTimer = setTimeout(step, 300);
  }
  function ensureSatelliteLayer() {
    const d = state.drive, m = d && d.map, t0 = trip();
    const sat = t0.satellite;
    if (!m || !m.isStyleLoaded() || !sat || !sat.ok || !sat.tiles || !sat.tiles.length) return false;
    if (m.getSource("drive-satellite")) return true;
    m.addSource("drive-satellite", {
      type: "raster", tiles: sat.tiles, tileSize: sat.tileSize || 256,
      minzoom: 0, maxzoom: sat.maxzoom || 6,
      attribution: '<a href="' + (sat.attributionUrl || "https://gibs.earthdata.nasa.gov/") +
        '" target="_blank" rel="noopener">' + (sat.attribution || "NASA GIBS") + "</a>",
    });
    const before = m.getLayer("drive-route-casing") ? "drive-route-casing" : undefined;
    m.addLayer({ id: "drive-satellite", type: "raster", source: "drive-satellite",
      paint: { "raster-opacity": 0.42 } }, before);
    return true;
  }
  async function refreshSatellite() {
    const t0 = trip();
    if (t0.satelliteLoading) return;
    t0.satelliteLoading = true;
    try {
      const j = await apiJson("/api/satellite");
      t0.satellite = j;
      if ($("dlSatellite") && $("dlSatellite").checked) ensureSatelliteLayer();
      if (j.ok) pushChip("satellite", "◈", "Satélite GOES-East",
        `${j.timeLabel || j.time} · NASA GIBS`, "info");
    } catch (_) {
      t0.satellite = { ok: false, frames: [] };
    } finally {
      t0.satelliteLoading = false;
      applyLayerVisibility();
    }
  }
  function syncDriveSources(all = false) {
    const t0 = trip(), d = state.drive;
    if (!d || !d.map || !ensureDriveLayers()) return;
    if (all) {
      const g = (t0.route && t0.route.geometry) || [];
      setDriveData("drive-route", lineFeature(g));
      setDriveData("drive-cameras", pointFeatures(t0.route && t0.route.cameras, (c) => ({
        id: c.id, name: c.name, atKm: c.atKm, offRouteKm: c.offRouteKm,
      })));
      setDriveData("drive-services", pointFeatures(t0.services && t0.services.services, (s) => ({
        kind: s.kind, name: s.name, label: s.label, url: s.url,
      })));
      setDriveData("drive-alerts", pointFeatures((t0.layers || []).filter((it) =>
        String(it.type || "").indexOf("camar") < 0), (it) => ({
        label: it.label || it.type || "Aviso", type: it.type || "",
      })));
      setDriveData("drive-roadfacts", pointFeatures(t0.roadfacts && t0.roadfacts.items, (it) => ({
        id: it.id, name: it.name, kind: it.kind, limit: it.limit, url: it.url,
      })));
      const coast = [];
      const st = t0.coastal && t0.coastal.station;
      if (st && st.near) coast.push({ lat: st.lat, lon: st.lon, name: st.name,
        detail: t0.coastal.waterLevel ? `Nivel ${t0.coastal.waterLevel.valueM.toFixed(2)} m` : "Estación NOAA",
        url: st.url });
      (t0.coastal && t0.coastal.storms || []).forEach((s) => {
        if (Number.isFinite(s.lat) && Number.isFinite(s.lon)) coast.push({
          lat: s.lat, lon: s.lon, name: s.name, detail: s.classification || "Tormenta activa", url: s.url,
        });
      });
      setDriveData("drive-coastal", pointFeatures(coast, (c) => ({
        name: c.name, detail: c.detail, url: c.url,
      })));
    }
    const p = t0.pos || ((t0.route && t0.route.geometry && t0.route.geometry.length)
      ? pointAtKm(t0.route.geometry, t0.cum || routeCumulative(t0.route.geometry), t0.progressKm) : null);
    setDriveData("drive-traveled", lineFeature(traveledGeometry(
      (t0.route && t0.route.geometry) || [], t0.cum || routeCumulative((t0.route && t0.route.geometry) || []),
      t0.progressKm || 0)));
    setDriveData("drive-accuracy", p ? { type: "FeatureCollection", features: [{
      type: "Feature", properties: {},
      geometry: circlePolygon(p.lat, p.lon, Math.min(200, Math.max(20, t0.accuracyM || 60))),
    }] } : EMPTY_FC);
  }
  function applyLayerVisibility() {
    const d = state.drive, m = d && d.map;
    if (!m) return;
    const on = (id) => !!(($(id) && $(id).checked) || false);
    const t0 = trip();
    const vis = {
      "drive-cameras": on("dlCameras"),
      "drive-services": on("dlServices"),
      "drive-alerts": on("dlAlerts") || on("dlSensors"),
      "drive-radar": on("dlRadar"),
      "drive-satellite": on("dlSatellite"),
      "drive-roadfacts": on("dlRoad"),
      "drive-coastal": on("dlCoastal"),
    };
    Object.keys(vis).forEach((id) => {
      if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", vis[id] ? "visible" : "none");
    });
    const ra = $("driveAttrRadar");
    if (ra) ra.hidden = !vis["drive-radar"];
    const sa = $("driveAttrSatellite");
    if (sa) sa.hidden = !(vis["drive-satellite"] && t0.satellite && t0.satellite.ok);
    const st = $("driveSatelliteTime");
    if (st) st.textContent = t0.satellite && t0.satellite.timeLabel
      ? " · " + t0.satellite.timeLabel : "";
    if (vis["drive-satellite"]) {
      if (!t0.satellite) refreshSatellite();
      else if (t0.satellite.ok && !m.getSource("drive-satellite")) {
        try {
          if (!m.isStyleLoaded() || !ensureSatelliteLayer()) scheduleSatelliteRetry();
        } catch (_) { scheduleSatelliteRetry(); }
      }
    }
    if (t0.contextLoading) return;
    if (vis["drive-radar"] && !t0.radar) refreshRadar();
    if (vis["drive-roadfacts"] && !t0.roadfacts && t0.route) refreshRoadFacts();
    if (vis["drive-coastal"] && !t0.coastal && t0.route) refreshCoastal();
  }
  function focusDrivePos(animate = true) {
    const t0 = trip(), d = state.drive;
    if (!d || !d.map || !t0.pos) return;
    d.map.easeTo({ center: [t0.pos.lon, t0.pos.lat], zoom: DRIVE_ZOOM,
      duration: animate ? 650 : 0, essential: true });
  }
  async function refreshRadar() {
    const t0 = trip();
    if (!t0.active || t0.radarLoading) return;
    t0.radarLoading = true;
    t0.radar = { ok: false, frames: [] };
    try {
      const j = await apiJson("/api/radar");
      t0.radar = j;
      rebuildRadar();
      if (j.frames && j.frames.length) pushChip("radar", "⛆", "Radar en vivo",
        `${j.frames.length} imágenes · RainViewer · ${j.cached ? "caché" : "actualizado"}`, "info");
    } catch (_) {
      t0.radar = { ok: false, frames: [] };
      rebuildRadar();
    } finally { t0.radarLoading = false; }
  }
  async function refreshRoadFacts() {
    const t0 = trip();
    if (!t0.route || t0.roadLoading) return;
    t0.roadLoading = true;
    t0.roadfacts = { ok: false, items: [] };
    try {
      const j = await apiJson("/api/roadfacts", { geometry: t0.route.geometry });
      t0.roadfacts = j;
      syncDriveSources(true);
      refreshRoadLimit();
      if (j.count) pushChip("road", "⛔", `${j.cameras} cámaras de velocidad · ${j.limits} límites`,
        "OpenStreetMap · no sustituye la señalización", "warn");
    } catch (_) { /* los hechos viales son contexto: la ruta no depende de ellos */ }
    finally { t0.roadLoading = false; }
  }
  async function refreshCoastal() {
    const t0 = trip();
    if (!t0.route || t0.coastLoading) return;
    t0.coastLoading = true;
    t0.coastal = { ok: false, station: null, storms: [] };
    try {
      const p = t0.pos || pointAtKm(t0.route.geometry, t0.cum, t0.totalKm / 2);
      const j = await apiJson(`/api/coastal?lat=${p.lat}&lon=${p.lon}`);
      t0.coastal = j;
      syncDriveSources(true);
      const st = j.station;
      if (st && st.near && j.waterLevel) pushChip("tide", "≈", `Marea · ${shortName(st.name, 24)}`,
        `${j.waterLevel.valueM.toFixed(2)} m · NOAA CO-OPS`, "info");
      if (j.storms && j.storms.length) pushChip("storm", "◈", `${j.storms.length} tormenta(s) activa(s)`,
        j.storms.map((s) => s.name).join(", ") + " · NHC", "warn");
    } catch (_) { /* el contexto costero es opcional */ }
    finally { t0.coastLoading = false; }
  }
  function refreshRoadLimit() {
    const t0 = trip(), box = $("driveLimit"), val = $("driveLimitValue");
    if (!box || !val) return;
    const items = (t0.roadfacts && t0.roadfacts.items) || [];
    const p = t0.pos;
    let best = null;
    if (p) items.forEach((it) => {
      const dist = haversine(p.lat, p.lon, it.lat, it.lon);
      if (dist <= 1.5 && (!best || dist < best.dist)) best = { it, dist };
    });
    if (!best || !best.it.limit) { box.hidden = true; return; }
    val.textContent = String(best.it.limit).replace(/[^0-9]/g, "").slice(0, 3) || "📷";
    box.title = `${best.it.name} · ${best.it.limit || "cámara"} · ${Math.round(best.dist * 1000)} m · OpenStreetMap`;
    box.hidden = false;
  }
  function initDriveMap() {
    if (state.drive && state.drive.map) return;
    if (!window.maplibregl || !$("driveMap")) return;
    const map = new maplibregl.Map({
      container: "driveMap", style: driveStyleUrl(),
      center: [-74.6085, 40.6209], zoom: DRIVE_ZOOM, minZoom: 5, maxZoom: 18,
      attributionControl: false, dragRotate: false, touchPitch: false,
      pitchWithRotate: false, fadeDuration: 120,
    });
    const node = document.createElement("div");
    node.className = "drive-pos"; node.setAttribute("aria-hidden", "true");
    node.innerHTML = "<i></i><b></b>";
    const marker = new maplibregl.Marker({ element: node, anchor: "center" })
      .setLngLat([-74.6085, 40.6209]).addTo(map);
    state.drive = { map, marker, popup: null };
    map.on("style.load", () => {
      if (ensureDriveLayers()) { syncDriveSources(true); applyLayerVisibility(); }
      // Un segundo intento corto cubre el cambio de tema: algunas fuentes
      // propias solo pueden añadirse cuando el estilo ya está completamente cargado.
      setTimeout(() => applyLayerVisibility(), 500);
    });
    map.on("dragstart", () => { trip().follow = false; });
    map.on("click", () => { if (state.drive.popup) { state.drive.popup.remove(); state.drive.popup = null; } });
    map.on("click", "drive-cameras", (e) => {
      const id = e.features[0].properties.id;
      const c = ((trip().route && trip().route.cameras) || []).find((x) => String(x.id) === String(id));
      if (c) openSpotlight(c);
    });
    map.on("click", "drive-services", (e) => {
      const p = e.features[0].properties;
      drivePopup(e, `<b>${mapEsc(p.name || p.label)}</b><br><small>${mapEsc(p.label || "Servicio")} · OpenStreetMap</small>` +
        (p.url ? `<br><a href="${mapEsc(p.url)}" target="_blank" rel="noopener">Ver en OSM</a>` : ""));
    });
    map.on("click", "drive-alerts", (e) => {
      const p = e.features[0].properties;
      drivePopup(e, `<b>${mapEsc(p.label)}</b><br><small>${mapEsc(p.type || "Aviso")} · fuente pública</small>`);
    });
    map.on("click", "drive-roadfacts", (e) => {
      const p = e.features[0].properties;
      drivePopup(e, `<b>${mapEsc(p.name)}</b><br><small>${p.kind === "speed_camera" ? "Cámara de velocidad" : "Límite"}${p.limit ? " · " + mapEsc(p.limit) : ""} · OpenStreetMap</small>` +
        `<br><a href="${mapEsc(p.url)}" target="_blank" rel="noopener">Ver en OSM</a>`);
    });
    map.on("click", "drive-coastal", (e) => {
      const p = e.features[0].properties;
      drivePopup(e, `<b>${mapEsc(p.name)}</b><br><small>${mapEsc(p.detail)} · NOAA</small>` +
        `<br><a href="${mapEsc(p.url)}" target="_blank" rel="noopener">Fuente oficial</a>`);
    });
    ["drive-cameras", "drive-services", "drive-alerts", "drive-roadfacts", "drive-coastal"].forEach((id) => {
      map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
    });
    // Sondeo legible para verificaciones y diagnóstico, sin exponer datos del usuario.
    window.__driveMapDebug = () => ({
      zoom: map.getZoom(), center: map.getCenter(), loaded: map.loaded(),
      follow: trip().follow, style: (map.style && map.style.url) || "",
      tilesLoaded: map.areTilesLoaded ? map.areTilesLoaded() : null,
      layers: ["drive-radar", "drive-satellite", "drive-route-line", "drive-cameras", "drive-services",
        "drive-alerts", "drive-roadfacts", "drive-coastal"].filter((id) => !!map.getLayer(id)),
      visible: ["drive-radar", "drive-satellite", "drive-route-line", "drive-cameras", "drive-roadfacts", "drive-coastal"]
        .filter((id) => map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none"),
      tiles: map.style && map.style.sources ? Object.keys(map.style.sources).length : 0,
      roadCount: (trip().roadfacts && trip().roadfacts.count) || 0,
      radarCount: (trip().radar && trip().radar.frames && trip().radar.frames.length) || 0,
      satelliteTime: trip().satellite && trip().satellite.ok ? trip().satellite.time : null,
      satelliteSource: !!map.getSource("drive-satellite"),
      satelliteRetry: !!satelliteRetryTimer,
      coastalStation: trip().coastal && trip().coastal.station
        ? trip().coastal.station.name : null,
      baseSource: !!map.getSource("protomaps"),
      baseTiles: (() => { const s = map.getSource("protomaps"); return s
        ? Object.values(s._tiles || {}).map((t) => t.state).slice(0, 8) : []; })(),
    });
  }
  function refreshDriveTheme() {
    const d = state.drive;
    if (!d || !d.map) return;
    try {
      // setStyle descarta las fuentes propias. El evento `style.load` ya
      // restaura las capas base, pero `idle` garantiza que el estilo nuevo
      // esté listo antes de volver a añadir la capa satelital opcional.
      d.map.once("idle", () => applyLayerVisibility());
      d.map.setStyle(driveStyleUrl());
    } catch (_) {}
  }
  function drawTripMap() {
    const t0 = trip(), d = state.drive;
    if (!d || !d.map || !t0.route || !t0.route.geometry || t0.route.geometry.length < 2) return;
    syncDriveSources(true);
    applyLayerVisibility();
    const p = t0.pos || pointAtKm(t0.route.geometry, t0.cum || routeCumulative(t0.route.geometry), t0.progressKm);
    if (p) { t0.pos = p; d.marker.setLngLat([p.lon, p.lat]); if (t0.follow) focusDrivePos(false); }
    refreshRoadLimit();
  }
  function updateDrivePos() {
    const t0 = trip(), d = state.drive;
    if (!t0.route || !d || !d.map) return;
    const p = t0.mode === "gps" && state.geo
      ? { lat: state.geo.lat, lon: state.geo.lon }
      : pointAtKm(t0.route.geometry, t0.cum, t0.progressKm);
    t0.pos = p;
    d.marker.setLngLat([p.lon, p.lat]);
    syncDriveSources(false);
    refreshRoadLimit();
    if (t0.follow) focusDrivePos(true);
  }

  /* ---- Ubicación actual (Nominatim reverse, con caché en servidor) ---- */
  async function refreshHere(force = false) {
    const t0 = trip();
    if (!t0.active || !t0.pos || t0.hereBusy) return;
    const p = t0.pos;
    const moved = !t0.hereAt || haversine(p.lat, p.lon, t0.hereAt.lat, t0.hereAt.lon) > 1.2;
    const stale = Date.now() - (t0.hereAtTime || 0) > 45000;
    if (!force && !moved && !stale) return;
    t0.hereBusy = true;
    try {
      const j = await fetch(`/api/reverse?lat=${p.lat}&lon=${p.lon}`).then((r) => r.json());
      if (!t0.active || j.ok === false || !j.place) return;
      t0.here = j.place.road || j.place.city || j.place.label;
      t0.hereAt = { lat: p.lat, lon: p.lon };
      t0.hereAtTime = Date.now();
      const el = $("driveHere");
      el.textContent = t0.here ? "Estás en " + shortName(t0.here, 30) : "";
      el.title = (j.place.label || "") + " · " +
        ((j.place.source && j.place.source.label) || "OpenStreetMap");
    } catch (_) { /* la vía actual es contextual: la ruta no depende de ella */ }
    finally { t0.hereBusy = false; }
  }

  /* ---- HUD, chips y bitácora ---- */
  function refreshDriveHud() {
    const t0 = trip();
    $("driveDestName").textContent = t0.to ? shortName(t0.to.name, 34) : "Elige un destino";
    $("driveDestLabel").textContent = t0.to ? "Viajando hacia" : "¿A dónde vas?";
    $("driveHere").textContent = t0.here ? "Estás en " + shortName(t0.here, 30) : "";
    if (t0.route && t0.totalKm > 0) {
      const left = Math.max(0, t0.totalKm - t0.progressKm);
      const mins = Math.max(0, Math.round(t0.durationMin * (left / Math.max(0.1, t0.totalKm))));
      $("driveEta").textContent = new Date(Date.now() + mins * 60000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      $("driveLeft").textContent = `${fmtDist(left)} · ${mins} min`;
      $("driveProgressBar").style.width = Math.min(100, Math.max(0, t0.progressKm / t0.totalKm * 100)) + "%";
      const next = (t0.route.cameras || []).find((c) => c.atKm > t0.progressKm + 0.02);
      $("driveNext").textContent = next ? `${fmtDist(Math.max(0, next.atKm - t0.progressKm))} · ${shortName(next.name, 14)}` : "—";
    } else {
      $("driveEta").textContent = "—";
      $("driveLeft").textContent = "—";
      $("driveNext").textContent = "—";
      $("driveProgressBar").style.width = "0%";
    }
    $("driveMusicName").textContent = t0.music ? t0.music.name : "Sin seleccionar";
    $("driveMusicLabel").textContent = t0.music ? (t0.music.category || "Banda sonora") : "Banda sonora";
    const logo = $("driveMusicLogo");
    if (t0.music && t0.music.logo) { logo.src = t0.music.logo; logo.hidden = false; }
    else logo.hidden = true;
    const audio = $("radioAudio");
    $("btnDriveMusic").textContent = (t0.music && state.radioNow === t0.music.id && audio && !audio.paused) ? "❚❚" : "▶";
    const sim = $("btnSimToggle");
    sim.textContent = t0.running ? "❚❚ Pausar" : "▶ Simular";
    sim.classList.toggle("accent", !t0.running);
    $("btnGpsTrip").classList.toggle("on", t0.mode === "gps");
  }
  function pushChip(key, icon, title, detail, kind, priority = 5) {
    const host = $("driveChips");
    if (!host) return;
    Array.from(host.children).forEach((n) => { if (n.dataset.chip === key) n.remove(); });
    const box = el("div", "drive-chip" + (kind ? " " + kind : ""));
    box.dataset.chip = key;
    box.dataset.priority = String(priority);
    box.appendChild(el("span", "dc-ico", icon));
    const copy = el("div", "dc-copy");
    copy.appendChild(el("b", null, title));
    if (detail) copy.appendChild(el("span", null, detail));
    box.appendChild(copy);
    host.appendChild(box);
    while (host.children.length > 5) {
      const victim = Array.from(host.children).reduce((a, b) =>
        Number(b.dataset.priority) < Number(a.dataset.priority) ? b : a);
      victim.remove();
    }
  }
  function renderContextChips() {
    const t0 = trip();
    if (!t0.active || !t0.route) return;
    const cur = (t0.weather && t0.weather.current) || {};
    const prof = profileNow();
    if (t0.prefs.alerts && prof.alerts) {
      pushChip("weather", cur.animation === "rain" ? "☂" : (cur.animation === "clear" ? "☀" : "☁"),
        `${cur.temperatureC !== null && cur.temperatureC !== undefined ? Math.round(cur.temperatureC) + "° · " : ""}${cur.description || "Clima en vivo"}`,
        `NWS + Open-Meteo${t0.weather && t0.weather.air && t0.weather.air.usAqi != null ? " · AQI " + t0.weather.air.usAqi : ""}`, "info", 8);
      const alerts = (t0.weather && t0.weather.alerts) || [];
      if (alerts.length) pushChip("wxalert", "⚠", `${alerts.length} alerta(s) NWS activas`,
        alerts.map((a) => a.event).join(", "), "warn", 9);
      if (t0.corridor) pushChip("corridor", t0.corridor.level === "green" ? "✓" : "⚠",
        `${t0.corridor.label} · ${t0.corridor.score}/100`,
        (t0.corridor.reasons || [])[0] || "Reglas deterministas sobre fuentes públicas",
        t0.corridor.level === "green" ? "good" : "warn", 7);
    }
    if (t0.prefs.sensors && prof.sensors) {
      const rows = [...((t0.sensors && t0.sensors.usgs) || []), ...((t0.sensors && t0.sensors.additional) || [])];
      if (rows.length) pushChip("sensors", "◉", `${rows.length} sensores públicos`,
        `USGS / NOAA · confianza ${t0.sensors && t0.sensors.confidence ? t0.sensors.confidence : "—"}`, "info", 6);
      if (t0.services && t0.services.count) pushChip("services", "⛽", `${t0.services.count} servicios en ruta`,
        "Repostaje, carga y áreas de servicio · OpenStreetMap", "info", 6);
      if (t0.events && t0.events.count) pushChip("events", "⚑", `${t0.events.count} eventos 511NJ`,
        "Avisos oficiales capturados, no una predicción", "warn", 6);
    }
    if (t0.radar && t0.radar.frames && t0.radar.frames.length) pushChip("radar", "⛆", "Radar en vivo",
      `${t0.radar.frames.length} imágenes · RainViewer · ${t0.radar.cached ? "caché" : "actualizado"}`, "info", 6);
    if (t0.roadfacts && t0.roadfacts.count) pushChip("road", "⛔",
      `${t0.roadfacts.cameras} cámaras de velocidad · ${t0.roadfacts.limits} límites`,
      "OpenStreetMap · no sustituye la señalización", "warn", 7);
    if (t0.coastal) {
      const st = t0.coastal.station;
      if (st && st.near && t0.coastal.waterLevel) pushChip("tide", "≈", `Marea · ${shortName(st.name, 24)}`,
        `${t0.coastal.waterLevel.valueM.toFixed(2)} m · NOAA CO-OPS`, "info", 7);
      if (t0.coastal.storms && t0.coastal.storms.length) pushChip("storm", "◈",
        `${t0.coastal.storms.length} tormenta(s) activa(s)`,
        t0.coastal.storms.map((s) => s.name).join(", ") + " · NHC", "warn", 9);
    }
    if (t0.music) pushChip("music", "♪", t0.music.name,
      `Banda sonora · ${t0.music.frequency || t0.music.category || "en vivo"}`, "info", 2);
    pushChip("camcount", "▣", `${(t0.route.cameras || []).length} cámaras en la ruta`,
      "Aparecerán solas unos segundos antes de pasar", "good", 3);
  }
  function tripLog(kind, title, detail) {
    const t0 = trip();
    t0.log.push({
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      kind, title, detail: detail || "",
    });
    if (t0.log.length > 60) t0.log.shift();
  }
  function renderTripLog() {
    const host = $("tripLogBody"), t0 = trip();
    host.replaceChildren();
    if (!t0.log.length) { host.appendChild(el("div", "empty", "Aún no hay eventos en esta ruta.")); return; }
    const list = el("div", "log-list");
    t0.log.slice().reverse().forEach((entry) => {
      const box = el("div", "log-item");
      box.appendChild(el("time", null, entry.time));
      const copy = el("div");
      copy.appendChild(el("b", null, entry.title));
      if (entry.detail) copy.appendChild(el("p", null, entry.detail));
      box.appendChild(copy);
      list.appendChild(box);
    });
    host.appendChild(list);
  }
  function voice(msg) {
    const t0 = trip();
    if (!t0.prefs.voice || !window.speechSynthesis) return;
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(msg));
      u.lang = "es-ES"; u.rate = 1.05;
      speechSynthesis.speak(u);
    } catch (_) { /* la voz es opcional */ }
  }

  /* ---- configuración del viaje ---- */
  function renderTripProfiles() {
    const host = $("tripProfiles"), t0 = trip();
    host.replaceChildren();
    TRIP_PROFILES.forEach((p) => {
      const b = el("button", "profile-card" + (t0.profile === p.id ? " on" : ""));
      b.type = "button";
      b.appendChild(el("span", "pf-ico", p.icon));
      b.appendChild(el("b", null, p.name));
      b.appendChild(el("small", null, p.desc));
      b.addEventListener("click", () => {
        t0.profile = p.id; saveTripPrefs(); renderTripProfiles();
        toast(`Estilo «${p.name}» seleccionado.`);
      });
      host.appendChild(b);
    });
  }
  function renderTripMusic() {
    const host = $("tripMusicList"), t0 = trip();
    host.replaceChildren();
    const none = el("button", "music-card" + (!t0.musicId ? " on" : ""));
    none.type = "button";
    const nc = el("div", "mc");
    nc.appendChild(el("b", null, "Sin música"));
    nc.appendChild(el("small", null, "Conducir en silencio"));
    none.appendChild(nc);
    none.appendChild(el("span", "mc-tag", "—"));
    none.addEventListener("click", () => {
      t0.musicId = ""; t0.music = null; saveTripPrefs(); renderTripMusic(); refreshDriveHud();
    });
    host.appendChild(none);
    const stations = ((state.radio && state.radio.stations) || []).filter((s) => s.available !== false);
    stations.forEach((s) => {
      const b = el("button", "music-card" + (t0.musicId === s.id ? " on" : ""));
      b.type = "button";
      const img = el("img");
      img.src = s.logo; img.alt = ""; img.loading = "lazy";
      img.onerror = () => { img.style.visibility = "hidden"; };
      b.appendChild(img);
      const mc = el("div", "mc");
      mc.appendChild(el("b", null, s.name));
      mc.appendChild(el("small", null, `${s.category || "Radio"} · ${s.frequency || "en vivo"}`));
      b.appendChild(mc);
      b.appendChild(el("span", "mc-tag", s.codec || "live"));
      b.addEventListener("click", () => {
        t0.musicId = s.id; t0.music = s; saveTripPrefs(); renderTripMusic(); refreshDriveHud();
      });
      host.appendChild(b);
    });
    if (!stations.length) host.appendChild(el("div", "trip-hint", "Cargando emisoras verificadas…"));
  }
  function renderTripSetup() {
    const t0 = trip();
    renderTripProfiles();
    renderTripMusic();
    const q = $("tripQuick");
    q.replaceChildren();
    QUICK_DESTS.forEach((name) => {
      const b = el("button", "chip ghost", name.replace(", NJ", "").replace(", DE", "").replace(", PA", ""));
      b.type = "button";
      b.title = name;
      b.addEventListener("click", async () => {
        $("tripDest").value = name;
        const p = await geocodePlace(name);
        if (p) setDestination(p); else toast("No se pudo resolver ese lugar ahora.");
      });
      q.appendChild(b);
    });
    if (t0.to) {
      const r = $("tripDestResolved");
      r.hidden = false;
      r.textContent = `Destino actual: ${t0.to.name} · ${t0.to.lat.toFixed(4)}, ${t0.to.lon.toFixed(4)}`;
    } else $("tripDestResolved").hidden = true;
    $("tripPrefCameras").checked = t0.prefs.cameras;
    $("tripPrefAlerts").checked = t0.prefs.alerts;
    $("tripPrefSensors").checked = t0.prefs.sensors;
    $("tripPrefVoice").checked = t0.prefs.voice;
    if (!state.radio) loadRadio().then(renderTripMusic).catch(() => {
      $("tripMusicList").replaceChildren(el("div", "trip-hint", "Las emisoras no están disponibles ahora; puedes conducir sin música."));
    });
  }
  function openTripSetup() {
    renderTripSetup();
    $("tripSetup").hidden = false;
    setTimeout(() => $("tripDest").focus(), 80);
  }

  /* ---- arranque, simulación y GPS ---- */
  async function resolveOrigin() {
    const t0 = trip();
    if ($("tripUseGeo").checked && state.geo) {
      return { name: "Mi ubicación", lat: state.geo.lat, lon: state.geo.lon };
    }
    const text = $("tripOrigin").value.trim();
    if (text) {
      const p = await geocodePlace(text);
      if (p) return { name: shortName(p.name, 34), lat: p.lat, lon: p.lon };
    }
    if (state.geo) return { name: "Mi ubicación", lat: state.geo.lat, lon: state.geo.lon };
    return { name: "Somerville (sin GPS)", lat: 40.6209, lon: -74.6085 };
  }
  async function startTrip() {
    if (!trip().to) { await confirmDest(); }
    const t0 = trip();
    if (!t0.to) return;
    $("btnTripGo").disabled = true;
    $("btnTripGo").textContent = "Calculando ruta…";
    t0.from = await resolveOrigin();
    const prof = profileNow();
    try {
      const j = await apiJson("/api/ai/route", {
        from: `${t0.from.lat},${t0.from.lon}`,
        to: `${t0.to.lat},${t0.to.lon}`,
        bufferKm: prof.bufferKm, limit: 40, useGeo: false,
      });
      t0.route = j;
      t0.cum = routeCumulative(j.geometry);
      t0.totalKm = j.distanceKm;
      t0.durationMin = j.durationMin;
      t0.progressKm = 0;
      t0.pos = { lat: j.start.lat, lon: j.start.lon };
      t0.active = true; t0.finished = false; t0.running = true; t0.mode = "sim";
      t0.follow = true; t0.startedAt = Date.now(); t0.lastTick = performance.now();
      t0.log = []; t0.chipKeys = new Set(); t0.seenCams = new Set();
      t0.here = ""; t0.hereAt = null; t0.hereAtTime = 0; t0.hereBusy = false;
      t0.services = null; t0.weather = null; t0.corridor = null; t0.sensors = null; t0.layers = [];
      t0.contextLoading = true;
      $("tripSetup").hidden = true;
      $("camSpotlight").hidden = true;
      pushChip("start", "➜", "Viaje iniciado", `${fmtDist(t0.totalKm)} · ~${Math.round(t0.durationMin)} min · ${prof.name}`, "good", 10);
      tripLog("inicio", "Viaje iniciado", `${t0.from.name} → ${shortName(t0.to.name, 40)} · ${prof.name}`);
      voice(`Ruta iniciada hacia ${shortName(t0.to.name, 40)}. ${Math.round(t0.durationMin)} minutos estimados.`);
      refreshDriveHud();
      drawTripMap();
      refreshHere(true);
      clearInterval(t0.spotTimer);
      if (state.tripTick) clearInterval(state.tripTick);
      state.tripTick = setInterval(tick, 1000);
      loadTripContext();
    } catch (e) {
      toast("No se pudo calcular la ruta: " + e.message, 5000);
    } finally {
      $("btnTripGo").disabled = false;
      $("btnTripGo").textContent = "Iniciar experiencia ➜";
    }
  }
  async function loadTripContext() {
    const t0 = trip();
    if (!t0.route) return;
    const mid = pointAtKm(t0.route.geometry, t0.cum, t0.totalKm / 2);
    const jobs = [
      apiJson(`/api/weather/live?lat=${mid.lat}&lon=${mid.lon}`)
        .then((j) => { t0.weather = j; renderContextChips(); }).catch(() => {}),
      apiJson(`/api/sensors?lat=${mid.lat}&lon=${mid.lon}`)
        .then((j) => { t0.sensors = j; renderContextChips(); }).catch(() => {}),
      apiJson("/api/ai/corridor", { lat: mid.lat, lon: mid.lon })
        .then((j) => { t0.corridor = j; renderContextChips(); }).catch(() => {}),
      apiJson("/api/trip/services", { geometry: t0.route.geometry })
        .then((j) => { t0.services = j; renderContextChips(); }).catch(() => {}),
      apiJson(`/api/ai/layers?lat=${mid.lat}&lon=${mid.lon}&infra=1&radiusKm=12`)
        .then((j) => { t0.layers = j.layers || []; }).catch(() => {}),
      apiJson("/api/events")
        .then((j) => { t0.events = j; renderContextChips(); }).catch(() => {}),
      refreshRadar(),
      refreshRoadFacts(),
      refreshCoastal(),
    ];
    await Promise.all(jobs);
    t0.contextLoading = false;
    if (!t0.active) return;
    drawTripMap();
    renderContextChips();
  }
  function tick() {
    const t0 = trip();
    if (!t0.active || !t0.route || !t0.running || t0.spotlight) {
      if (t0.active) t0.lastTick = performance.now();
      return;
    }
    const now = performance.now();
    const dt = Math.min(3, Math.max(0, (now - (t0.lastTick || now)) / 1000));
    t0.lastTick = now;
    if (t0.mode === "sim") t0.progressKm += t0.speed * dt / 3600;
    else if (t0.geoAtKm !== null && t0.geoAtKm !== undefined) t0.progressKm = Math.max(t0.progressKm, t0.geoAtKm);
    if (t0.progressKm >= t0.totalKm) {
      t0.progressKm = t0.totalKm;
      updateDrivePos(); refreshDriveHud(); endTrip(true);
      return;
    }
    updateDrivePos();
    refreshHere();
    checkSpotlight();
    checkContextChips();
    refreshDriveHud();
  }
  function checkSpotlight() {
    const t0 = trip(), prof = profileNow();
    if (t0.spotlight || !t0.prefs.cameras || !prof.camera || !t0.route) return;
    const lead = Math.max(0.25, t0.speed / 3600 * 14);
    const minAt = Math.min(0.8, t0.totalKm * 0.06);
    const maxOff = Math.min(3, prof.bufferKm);
    const c = (t0.route.cameras || []).find((x) =>
      !t0.seenCams.has(x.id) && x.atKm > minAt &&
      Number.isFinite(x.offRouteKm) && x.offRouteKm <= maxOff &&
      x.atKm <= t0.progressKm + lead && x.atKm >= t0.progressKm - 0.2);
    if (c) { t0.seenCams.add(c.id); openSpotlight(c); }
  }
  function checkContextChips() {
    const t0 = trip();
    if (!t0.route) return;
    const pct = t0.progressKm / Math.max(0.1, t0.totalKm);
    if (pct >= 0.25 && !t0.chipKeys.has("q1")) {
      t0.chipKeys.add("q1");
      const nextSvc = ((t0.services && t0.services.services) || [])[0];
      if (t0.prefs.sensors && profileNow().sensors && nextSvc) {
        pushChip("svcnext", "⛽", `Pronto: ${shortName(nextSvc.name, 26)}`, `${nextSvc.label} · OpenStreetMap`, "info");
      }
    }
    if (pct >= 0.5 && !t0.chipKeys.has("q2")) {
      t0.chipKeys.add("q2");
      const a = (t0.weather && t0.weather.air) || {};
      if (t0.prefs.alerts && profileNow().alerts) {
        pushChip("air", "❋", `Calidad del aire · AQI ${a.usAqi !== null && a.usAqi !== undefined ? a.usAqi : "—"}`,
          `PM2.5 ${a.pm25 !== null && a.pm25 !== undefined ? a.pm25 : "—"} μg/m³ · Open-Meteo`, "info");
      }
    }
    if (pct >= 0.8 && !t0.chipKeys.has("q3")) {
      t0.chipKeys.add("q3");
      pushChip("almost", "⌁", "Estás llegando", `Faltan ${fmtDist(Math.max(0, t0.totalKm - t0.progressKm))}`, "good");
      voice("Estás llegando a destino.");
    }
  }

  /* ---- cámara emergente ---- */
  function openSpotlight(c) {
    const t0 = trip();
    if (!c || !c.stream) return;
    if (state.drive && state.drive.map && t0.follow) {
      state.drive.map.easeTo({ center: [c.lon, c.lat], duration: 500, essential: true });
    }
    t0.spotlight = c;
    t0.spotCount = profileNow().spotSec;
    $("spotName").textContent = c.name;
    $("spotMeta").textContent = `${c.source || "Fuente oficial"} · a ${fmtDist(Math.max(0, c.atKm - t0.progressKm))} de tu posición · ${fmtDist(c.offRouteKm)} de la ruta`;
    $("spotSource").textContent = `Video público oficial · ${c.source || "511NJ / DelDOT"}`;
    $("spotCount").textContent = String(t0.spotCount);
    $("camSpotlight").hidden = false;
    const v = $("spotVideo");
    try { v.pause(); v.removeAttribute("src"); v.load(); } catch (_) {}
    if (state.drive.spotHls) { try { state.drive.spotHls.destroy(); } catch (_) { } state.drive.spotHls = null; }
    const url = proxyUrl(c);
    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: true, enableWorker: true, maxBufferLength: 10 });
      state.drive.spotHls = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => { v.play().catch(() => {}); });
      hls.on(Hls.Events.ERROR, (_, data) => { if (data && data.fatal) $("spotSource").textContent = "Este video no responde ahora; puedes continuar con la ruta."; });
      hls.loadSource(url); hls.attachMedia(v);
    } else {
      v.src = url;
      v.play().catch(() => {});
    }
    clearInterval(t0.spotTimer);
    t0.spotTimer = setInterval(() => {
      t0.spotCount -= 1;
      $("spotCount").textContent = String(Math.max(0, t0.spotCount));
      if (t0.spotCount <= 0) closeSpotlight(true);
    }, 1000);
    tripLog("camara", "Cámara en la ruta", `${c.name} · ${c.source || "fuente oficial"} · ${fmtDist(c.offRouteKm)} fuera de la ruta`);
    voice(`Cámara en la ruta: ${shortName(c.name, 32)}`);
  }
  function closeSpotlight(resume) {
    const t0 = trip();
    clearInterval(t0.spotTimer);
    t0.spotTimer = null;
    if (state.drive && state.drive.spotHls) {
      try { state.drive.spotHls.destroy(); } catch (_) {}
      state.drive.spotHls = null;
    }
    const v = $("spotVideo");
    try { v.pause(); v.removeAttribute("src"); v.load(); } catch (_) {}
    $("camSpotlight").hidden = true;
    if (t0.spotlight) {
      tripLog("camara_fin", "Volviendo al mapa", `Cámara ${shortName(t0.spotlight.name, 26)} · la ruta continúa`);
    }
    t0.spotlight = null;
    t0.lastTick = performance.now();
    if (resume) t0.running = true;
    refreshDriveHud();
  }

  /* ---- GPS real y controles ---- */
  function stopGps() {
    const t0 = trip();
    if (t0.geoWatch !== null && t0.geoWatch !== undefined && navigator.geolocation) {
      try { navigator.geolocation.clearWatch(t0.geoWatch); } catch (_) {}
    }
    t0.geoWatch = null;
  }
  function toggleGps() {
    const t0 = trip();
    if (t0.mode === "gps") {
      stopGps();
      t0.mode = "sim"; t0.geoAtKm = null;
      toast("Simulación reactivada.");
    } else {
      if (!navigator.geolocation) { toast("Este navegador no ofrece GPS."); return; }
      if (!t0.route) { toast("Primero inicia un viaje."); return; }
      t0.geoWatch = navigator.geolocation.watchPosition((pos) => {
        state.geo = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        const pr = routeProgressKm(t0.route.geometry, t0.cum, state.geo.lat, state.geo.lon);
        t0.geoAtKm = pr.at;
        if (pr.off > 0.8 && !t0.chipKeys.has("offroute")) {
          t0.chipKeys.add("offroute");
          pushChip("offroute", "↯", "Fuera de la ruta", `A ${fmtDist(pr.off)} del trazado · se recalcula al continuar`, "warn");
        }
        t0.accuracyM = Math.min(200, Math.max(20, pos.coords.accuracy || 60));
        syncDriveSources(false);
      }, (err) => {
        toast("No se pudo usar el GPS: " + (err.message || "permiso denegado"), 4200);
        stopGps(); t0.mode = "sim";
      }, { enableHighAccuracy: true, maximumAge: 3000, timeout: 15000 });
      t0.mode = "gps"; t0.follow = true; t0.running = true;
      toast("GPS real activado. El mapa seguirá tu posición.", 4200);
    }
    refreshDriveHud();
  }
  function pauseTrip() {
    const t0 = trip();
    t0.running = false;
    stopGps();
    if (t0.mode === "gps") t0.mode = "sim";
    if (t0.spotlight) closeSpotlight(false);
    refreshDriveHud();
  }
  function endTrip(completed) {
    const t0 = trip();
    t0.running = false; t0.active = false; t0.finished = true;
    t0.here = ""; t0.hereAt = null; t0.hereAtTime = 0;
    $("driveHere").textContent = "";
    if (state.tripTick) { clearInterval(state.tripTick); state.tripTick = null; }
    stopGps();
    if (t0.spotlight) closeSpotlight(false);
    const elapsed = t0.startedAt ? Math.max(1, Math.round((Date.now() - t0.startedAt) / 60000)) : 0;
    const cams = t0.log.filter((x) => x.kind === "camara").length;
    tripLog("fin", completed ? "Destino alcanzado" : "Viaje finalizado",
      `${fmtDist(t0.progressKm)} recorridos · ${cams} cámaras mostradas`);
    $("tripSummaryBody").replaceChildren();
    const grid = el("div", "summary-grid");
    [["Distancia", fmtDist(t0.progressKm)], ["Tiempo", elapsed + " min"],
     ["Cámaras", String(cams)], ["Estilo", profileNow().name],
     ["Música", t0.music ? shortName(t0.music.name, 16) : "Sin música"],
     ["Ruta", t0.route ? t0.route.summary.slice(0, 60) : "—"]].forEach(([k, v]) => {
      const box = el("div"); box.appendChild(el("small", null, k)); box.appendChild(el("b", null, v)); grid.appendChild(box);
    });
    $("tripSummaryBody").appendChild(grid);
    $("tripSummaryBody").appendChild(el("p", "summary-note",
      "Datos reales de fuentes públicas: OSRM para la ruta, 511NJ/DelDOT para cámaras, NWS y Open-Meteo para clima y calidad del aire, USGS/NOAA para sensores y OpenStreetMap para servicios. Sin datos inventados."));
    $("tripSummary").hidden = false;
    refreshDriveHud();
    voice(completed ? "Has llegado a destino." : "Viaje finalizado.");
  }

  /* ---- onboarding ---- */
  function maybeWizard() {
    const q = new URLSearchParams(location.search);
    if (q.get("nowizard") === "1" || q.get("mode") === "admin") return;
    if (getLS(LS.wizard) !== "1") setTimeout(() => openWizard(false), 250);
  }
  function openStart() {
    const pref = getLS(LS.start);
    if (pref === "trip") { setTab("viaje"); openTripSetup(); return; }
    if (pref === "data") { setTab(state.adminTab || "camaras"); maybeWizard(); return; }
    $("startModal").hidden = false;
    setTimeout(() => { const b = $("btnStartTrip"); if (b) b.focus(); }, 60);
  }
  function chooseStart(kind) {
    $("startModal").hidden = true;
    if ($("startRemember").checked) setLS(LS.start, kind);
    if (kind === "trip") { setTab("viaje"); openTripSetup(); }
    else { setTab(state.adminTab || "camaras"); maybeWizard(); }
  }

  /* ---- cableado de la experiencia ---- */
  function wireTrip() {
    loadTripPrefs();
    $("btnStartTrip").addEventListener("click", () => chooseStart("trip"));
    $("btnStartData").addEventListener("click", () => chooseStart("data"));
    $("btnTripSetupClose").addEventListener("click", () => { $("tripSetup").hidden = true; });
    $("btnTripGo").addEventListener("click", startTrip);
    let deb = null;
    $("tripDest").addEventListener("input", (e) => {
      clearTimeout(deb);
      deb = setTimeout(() => fetchDestSuggest(e.target.value.trim()), 450);
    });
    $("tripDest").addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); confirmDest(); }
    });
    $("btnDriveData").addEventListener("click", () => setTab(state.adminTab || "camaras"));
    $("btnDriveDest").addEventListener("click", openTripSetup);
    $("btnDriveProfile").addEventListener("click", openTripSetup);
    $("btnDriveRecenter").addEventListener("click", () => {
      const t0 = trip(), d = state.drive;
      t0.follow = true;
      if (d && d.map) {
        if (t0.pos) d.map.easeTo({ center: [t0.pos.lon, t0.pos.lat], zoom: DRIVE_ZOOM,
          duration: 600, essential: true });
        else if (t0.route) {
          const b = routeBounds(t0.route.geometry);
          if (b) d.map.fitBounds(b, { padding: 80, maxZoom: 14 });
        }
      }
      toast("Mapa centrado en tu posición.");
    });
    $("btnDriveOverview").addEventListener("click", () => {
      const t0 = trip(), d = state.drive;
      if (!d || !d.map || !t0.route) { toast("Inicia un viaje para ver la ruta completa."); return; }
      const b = routeBounds(t0.route.geometry);
      if (!b) return;
      t0.follow = false;
      d.map.fitBounds(b, { padding: { top: 120, bottom: 220, left: 36, right: 36 }, maxZoom: 14,
        duration: 700, essential: true });
      toast("Ruta completa · toca ◎ para volver a tu posición.");
    });
    $("btnDriveLayers").addEventListener("click", () => {
      const p = $("driveLayersPanel"); p.hidden = !p.hidden;
    });
    ["dlCameras", "dlServices", "dlAlerts", "dlSensors", "dlRadar", "dlSatellite", "dlRoad", "dlCoastal"].forEach((id) => {
      $(id).addEventListener("change", applyLayerVisibility);
    });
    $("btnDriveVoice").addEventListener("click", () => {
      const t0 = trip();
      t0.prefs.voice = !t0.prefs.voice;
      $("tripPrefVoice").checked = t0.prefs.voice;
      $("btnDriveVoice").classList.toggle("on", t0.prefs.voice);
      saveTripPrefs();
      toast(t0.prefs.voice ? "Narración activada." : "Narración desactivada.");
      if (t0.prefs.voice) voice("Narración activada.");
    });
    $("btnDriveMusic").addEventListener("click", () => {
      const t0 = trip(), audio = $("radioAudio");
      if (!t0.music) { openTripSetup(); toast("Elige una emisora en el paso 3."); return; }
      if (state.radioNow === t0.music.id && audio && !audio.paused) audio.pause();
      else playRadio(t0.music);
      setTimeout(refreshDriveHud, 120);
    });
    $("radioAudio").addEventListener("play", refreshDriveHud);
    $("radioAudio").addEventListener("pause", refreshDriveHud);
    $("btnSimToggle").addEventListener("click", () => {
      const t0 = trip();
      if (!t0.active) { toast("Inicia un viaje para simularlo."); return; }
      if (t0.mode === "gps") { stopGps(); t0.mode = "sim"; t0.geoAtKm = null; }
      if (t0.spotlight) closeSpotlight(false);
      t0.running = !t0.running;
      t0.lastTick = performance.now();
      refreshDriveHud();
      toast(t0.running ? "Simulación en marcha." : "Simulación en pausa.");
    });
    $("driveSpeed").addEventListener("change", (e) => {
      trip().speed = parseFloat(e.target.value) || 90;
      toast("Velocidad de simulación: " + e.target.value + " km/h.");
    });
    $("btnGpsTrip").addEventListener("click", toggleGps);
    $("btnTripLog").addEventListener("click", () => { renderTripLog(); $("tripLogModal").hidden = false; });
    $("btnTripLogClose").addEventListener("click", () => { $("tripLogModal").hidden = true; });
    $("btnTripEnd").addEventListener("click", () => { if (trip().active) endTrip(false); else toast("No hay un viaje en curso."); });
    $("btnSpotSkip").addEventListener("click", () => closeSpotlight(true));
    $("btnSpotOpen").addEventListener("click", () => {
      const c = trip().spotlight;
      closeSpotlight(false);
      pauseTrip();
      if (c) { selectCamera(c, true); setTab("visor"); }
    });
    $("btnSummaryClose").addEventListener("click", () => { $("tripSummary").hidden = true; });
    $("btnTripAgain").addEventListener("click", () => {
      $("tripSummary").hidden = true;
      setTab("viaje"); openTripSetup();
    });
    $("btnTripToData").addEventListener("click", () => {
      $("tripSummary").hidden = true;
      setTab(state.adminTab || "camaras");
    });
    [["tripPrefCameras", "cameras"], ["tripPrefAlerts", "alerts"],
     ["tripPrefSensors", "sensors"], ["tripPrefVoice", "voice"]].forEach(([id, key]) => {
      $(id).addEventListener("change", (e) => {
        trip().prefs[key] = e.target.checked;
        if (key === "voice") $("btnDriveVoice").classList.toggle("on", e.target.checked);
        saveTripPrefs();
      });
    });
    [["tripSetup", "btnTripSetupClose"], ["tripLogModal", "btnTripLogClose"], ["tripSummary", "btnSummaryClose"]]
      .forEach(([modal, btn]) => {
        $(modal).addEventListener("click", (e) => {
          if (e.target === $(modal) || e.target.id === btn) $(modal).hidden = true;
        });
      });
    $("driveLayersPanel").addEventListener("click", (e) => { if (e.target.classList.contains("eyebrow")) e.stopPropagation(); });
    $("btnDriveVoice").classList.toggle("on", trip().prefs.voice);
  }

  /* ------------------------------------------------------------------ */
  /* Cableado                                                            */
  /* ------------------------------------------------------------------ */
  function wire() {
    let debounce = null;
    $("q").addEventListener("input", (e) => {
      clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value; render(); }, 120);
    });
    $("zone").addEventListener("change", (e) => { state.zone = e.target.value; render(); });
    $("tour").addEventListener("change", (e) => { state.tour = e.target.value; render(); });
    $("sort").addEventListener("change", (e) => {
      state.sort = e.target.value;
      if (state.sort === "dist" && !state.geo) {
        toast("Primero usa tu GPS para ordenar por distancia.");
        state.sort = "zone"; e.target.value = "zone";
      }
      render();
    });
    $("routeOnly").addEventListener("change", (e) => { state.routeOnly = e.target.checked; render(); });
    $("streamOnly").addEventListener("change", (e) => { state.streamOnly = e.target.checked; render(); });
    $("favOnly").addEventListener("change", (e) => { state.favOnly = e.target.checked; render(); });
    $("nearCount").addEventListener("change", (e) => { state.nearCount = parseInt(e.target.value, 10) || 10; render(); });
    $("radiusKm").addEventListener("change", () => { if (state.geo) loadNearby(); });
    $("btnVerifyLocal").addEventListener("click", () => loadNearby(true));
    $("btnGps").addEventListener("click", useGps);
    $("segCamaras").addEventListener("click", () => setTab("camaras"));
    $("segCerca").addEventListener("click", () => setTab("cerca"));
    $("segLocales").addEventListener("click", () => setTab("locales"));
    document.querySelectorAll(".tabbar .tab").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
    $("btnMapLocate").addEventListener("click", locateMap);
    $("btnMapFit").addEventListener("click", fitMap);
    $("mapVerified").addEventListener("change", renderMap);
    ["mapZones", "mapSensors", "mapRadio"].forEach((id) => {
      const node = $(id);
      if (!node) return;
      node.addEventListener("change", async () => {
        if (!node.checked) { renderMap(); return; }
        try {
          if (id === "mapSensors") await ensureSensors();
          if (id === "mapRadio" && !state.radio) await loadRadio();
        } catch (e) { toast("No se pudieron cargar las capas: " + e.message); }
        renderMap();
      });
    });

    /* Clima animado y herramientas combinadas */
    $("btnWx").addEventListener("click", async () => {
      $("wxOut").replaceChildren(el("div", "loading", "Consultando NWS, Open-Meteo y radio meteorológica…"));
      try { await loadWeather(); toast("Clima actualizado con datos reales."); }
      catch (e) { toast("No se pudo consultar el clima: " + e.message, 4800); }
    });
    $("wxPlace").addEventListener("change", () => $("btnWx").click());
    $("btnCorridor").addEventListener("click", loadCorridor);
    $("btnSensors").addEventListener("click", loadSensors);

    /* Radio en vivo */
    $("radioCategory").addEventListener("change", (e) => {
      state.radioCategory = e.target.value; renderRadioList();
    });
    $("btnRadioRefresh").addEventListener("click", async () => {
      try { await loadRadio(true); toast("Emisoras verificadas de nuevo."); }
      catch (e) { toast(e.message, 4800); }
    });
    $("btnRadioStop").addEventListener("click", () => stopRadio(true));
    $("radioAudio").addEventListener("play", () => $("radioEq").classList.add("on"));
    $("radioAudio").addEventListener("pause", () => $("radioEq").classList.remove("on"));

    $("btnRefresh").addEventListener("click", async () => {
      const kind = $("refreshKind")?.value || "de";
      const label = { de: "DelDOT", nj: "511NJ", all: "ambas fuentes" }[kind];
      toast(`Consultando ${label}…`);
      try { await postRefresh(kind, true); }
      catch (e) { toast("No se pudo iniciar la actualización: " + e.message, 4800); }
    });
    $("btnPlay").addEventListener("click", () => { if (state.selected) playCamera(state.selected); });
    $("btnShot").addEventListener("click", shot);
    $("btnShare").addEventListener("click", shareCamera);
    $("btnFav").addEventListener("click", () => toggleFav(state.selected));
    $("btnCompare").addEventListener("click", () => {
      if (!state.selected) return;
      compareOpen(nearbyForCompare(state.selected));
    });
    $("btnContext").addEventListener("click", () => explainContext(state.selected));
    $("btnReport").addEventListener("click", () => reportButton(state.selected));
    $("btnZoomIn").addEventListener("click", () => setZoom(state.zoom + 0.25));
    $("btnZoomOut").addEventListener("click", () => setZoom(state.zoom - 0.25));
    $("btnZoomReset").addEventListener("click", resetZoom);
    $("btnMute").addEventListener("click", () => {
      const v = $("video"); v.muted = !v.muted;
      $("btnMute").innerHTML = (v.muted ? "🔇" : "🔊") + " <span>Sonido</span>";
      toast(v.muted ? "Sonido silenciado." : "Sonido activado.");
    });
    $("btnFull").addEventListener("click", () => {
      const st = $("stage");
      if (document.fullscreenElement) document.exitFullscreen();
      else if (st.requestFullscreen) st.requestFullscreen();
      else if (v.requestFullscreen) v.requestFullscreen();
    });
    $("video").addEventListener("playing", () => {
      $("btnShot").disabled = false; $("btnMute").disabled = false; $("btnFull").disabled = false;
      $("btnMute").innerHTML = ($("video").muted ? "🔇" : "🔊") + " <span>Sonido</span>";
    });

    const v = $("video");
    let dragging = false, sx = 0, sy = 0, px = 0, py = 0;
    v.addEventListener("pointerdown", (e) => {
      if (state.zoom <= 1) return;
      dragging = true; sx = e.clientX; sy = e.clientY; px = state.panX; py = state.panY;
      v.setPointerCapture(e.pointerId);
    });
    v.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const st = $("stage"), mx = (state.zoom - 1) * st.clientWidth / 2, my = (state.zoom - 1) * st.clientHeight / 2;
      state.panX = Math.max(-mx, Math.min(mx, px + e.clientX - sx));
      state.panY = Math.max(-my, Math.min(my, py + e.clientY - sy));
      applyZoom();
    });
    const endDrag = () => { dragging = false; };
    v.addEventListener("pointerup", endDrag); v.addEventListener("pointercancel", endDrag);

    $("btnSources").addEventListener("click", () => { renderSources(state.meta); $("sources").hidden = false; });
    $("btnCloseSources").addEventListener("click", () => { $("sources").hidden = true; });
    $("sources").addEventListener("click", (e) => { if (e.target === $("sources")) $("sources").hidden = true; });

    /* IA explicable */
    $("btnAiAsk").addEventListener("click", askAi);
    $("aiQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") askAi(); });
    document.querySelectorAll(".ai-example").forEach((b) => b.addEventListener("click", () => {
      $("aiQuery").value = b.dataset.q || "";
      askAi();
    }));
    $("btnRoute").addEventListener("click", calcRoute);
    $("routeUseGeo").addEventListener("click", () => {
      if (!state.geo) { toast("Primero pulsa «Usar mi GPS»."); return; }
      $("routeFrom").value = `${state.geo.lat.toFixed(5)},${state.geo.lon.toFixed(5)}`;
      toast("Origen fijado a tu ubicación real.");
    });
    $("btnRouteMap").addEventListener("click", () => {
      if (!state.routeData) return;
      state.aiIds = new Set(state.routeData.cameras.map((c) => c.id));
      setTab("mapa"); render();
      setTimeout(fitMap, 60);
      toast("Ruta y cámaras del trayecto dibujadas en el mapa.", 4200);
    });
    $("btnBrief").addEventListener("click", makeBrief);
    $("btnAlerts").addEventListener("click", loadAlerts);
    $("btnGroups").addEventListener("click", makeGroups);
    $("btnContextAi").addEventListener("click", () => explainContext(state.selected));
    $("btnCompareAi").addEventListener("click", () => {
      const c = state.selected;
      compareOpen(c ? nearbyForCompare(c) : state.cameras.filter((x) => x.stream).slice(0, 4).map((x) => x.id));
    });
    $("mapLayers").addEventListener("change", (e) => {
      if (e.target.checked) loadMapLayers();
      else { state.layerItems = []; $("mapLayerInfo").hidden = true; renderMap(); }
    });
    $("btnCloseCompare").addEventListener("click", closeCompare);
    $("compareModal").addEventListener("click", (e) => { if (e.target === $("compareModal")) closeCompare(); });

    /* Tours narrados */
    $("btnNarrate").addEventListener("click", narrate);
    $("btnSpeak").addEventListener("click", speakTour);
    $("btnStopSpeak").addEventListener("click", () => stopSpeak());
    $("btnMobile").addEventListener("click", openMobile);
    $("btnCloseMobile").addEventListener("click", () => { $("mobileModal").hidden = true; });
    $("mobileModal").addEventListener("click", (e) => { if (e.target === $("mobileModal")) $("mobileModal").hidden = true; });
    $("btnCopyMobile").addEventListener("click", copyMobile);

    $("btnWizard").addEventListener("click", () => openWizard(true));
    $("wClose").addEventListener("click", () => closeWizard(true));
    $("wSkip").addEventListener("click", () => closeWizard(true));
    $("wPrev").addEventListener("click", () => { if (state.wiz > 0) { state.wiz--; renderWizard(); } });
    $("wNext").addEventListener("click", () => {
      if (state.wiz < WIZARD.length - 1) { state.wiz++; renderWizard(); }
      else { closeWizard(true); toast("Guía cerrada. Ya puedes explorar el inventario."); }
    });
    $("overlay").addEventListener("click", (e) => { if (e.target === $("overlay")) closeWizard(true); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!$("overlay").hidden) closeWizard(true);
      else if (!$("sources").hidden) $("sources").hidden = true;
      else if (!$("mobileModal").hidden) $("mobileModal").hidden = true;
    });
  }

  /* ------------------------------------------------------------------ */
  /* Arranque                                                            */
  /* ------------------------------------------------------------------ */
  async function init() {
    initTheme(); wire(); wireTrip();
    loadAiStats().catch(() => {});
    loadWeather(true).catch(() => {});
    setInterval(() => {
      if (state.radioNow && !document.hidden) refreshRadioMeta(state.radioNow);
    }, 30000);
    if (matchMedia("(max-width:560px)").matches) $("filterBox").open = false;
    const q = new URLSearchParams(location.search);
    if (q.get("nowizard") !== "1" && q.get("mode") !== "admin") setTimeout(() => openStart(), 450);
    try { await loadCameras(false); }
    catch (e) {
      $("list").replaceChildren(el("div", "empty", "No se pudo cargar el inventario: " + e.message));
      toast("No se pudo contactar con el servidor local.", 6000);
    }
    setInterval(ping, 20000);
    setInterval(() => { if (!document.hidden) postRefresh("de", false).catch(() => {}); }, 5 * 60 * 1000);
  }
  init();
})();
