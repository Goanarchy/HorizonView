"""Auditoría geométrica y de estados IA/Radio/Tours a 390x844 (celular).

Comprueba que ningún elemento quede fuera del ancho, recortado, y que los
paneles nuevos (IA, Radio, clima animado, sensores, corredor, zonas locales,
comparador y capas del mapa) se rendericen sin errores de JavaScript.
"""
import json
import subprocess
import tempfile
import time

import requests

from verify_mobile import CHROME, BASE, CDP, PORT

GEO_JS = r"""(() => {
  const vw = innerWidth, vh = innerHeight, fuera = [], recort = [];
  document.querySelectorAll('body *').forEach(e => {
    if (e.closest('[hidden]') || e.closest('.aurora') || e.closest('.leaflet-container') ||
        e.closest('.wscene')) return;  // escena climática decorativa: sombras y pseuodos salen del cajón a propósito
    // Las franjas con scroll horizontal (pronóstico por horas) se recorren con
    // el dedo: sus hijos pueden quedar fuera del viewport sin estar recortados.
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll') return;
    }
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return;
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const name = e.tagName.toLowerCase() + '.' + String(e.className || '').split(' ').join('.');
    if (r.right > vw + 1.5 || r.left < -1.5) fuera.push({n:name, l:Math.round(r.left), r:Math.round(r.right)});
    // Elipsis intencional y campos de texto nativos no cuentan como recorte visual.
    if (e.children.length === 0 && e.tagName !== 'INPUT' && cs.textOverflow !== 'ellipsis' &&
        e.scrollWidth > e.clientWidth + 2 && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll')
      recort.push({n:name, sw:e.scrollWidth, cw:e.clientWidth});
  });
  const small = [...document.querySelectorAll('button,a,select,input')]
    .filter(e => !e.closest('[hidden]') && getComputedStyle(e).display !== 'none')
    .map(e => ({n:e.tagName.toLowerCase()+'.'+String(e.className||'').split(' ').join('.'), h:Math.round(e.getBoundingClientRect().height)}))
    .filter(x => x.h > 0 && x.h < 40);
  return JSON.stringify({ancho:vw, alto:vh, scroll:document.documentElement.scrollWidth,
    fuera:fuera.slice(0,12), recortados:recort.length, detalleRecortes:recort.slice(0,6),
    pequenos:small.slice(0,8), tabbar:getComputedStyle(document.querySelector('.tabbar')).display});
})()"""

FAIL = []


def audit(c, label, wait=0.4):
    time.sleep(wait)
    raw = c.js(GEO_JS)
    try:
        d = json.loads(raw)
    except Exception:
        FAIL.append(label + ": respuesta de auditoría no válida")
        print(label + ": ERROR " + str(raw)[:200])
        return {}
    print(label + ": " + json.dumps(d, ensure_ascii=False))
    if d.get("fuera"):
        FAIL.append("%s: %d elemento(s) fuera del ancho" % (label, len(d["fuera"])))
    if d.get("recortados"):
        FAIL.append("%s: %d elemento(s) recortados" % (label, d["recortados"]))
    return d


def probe(c, expr):
    if isinstance(expr, dict):
        js_expr = "{" + ", ".join("%s:(%s)" % (json.dumps(k), v) for k, v in expr.items()) + "}"
    else:
        js_expr = str(expr)
    raw = c.js("JSON.stringify(" + js_expr + ")")
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": str(raw)[:200]}


def main():
    profile = tempfile.mkdtemp(prefix="horizonview_audit_")
    p = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={PORT}",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        page = next(x for x in requests.get(f"http://127.0.0.1:{PORT}/json", timeout=5).json() if x["type"] == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Runtime.enable")
        c.call("Log.enable")
        c.call("Network.enable")
        c.call("Page.enable")
        c.call("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True,
        })
        c.call("Page.navigate", {"url": BASE + "/?nowizard=1&theme=dark"})
        time.sleep(7)
        audit(c, "OSCURO 390", 0)

        c.js("document.getElementById('btnTheme').click()")
        audit(c, "CLARO 390", 0.6)
        c.js("document.getElementById('btnTheme').click()")

        for tab, label in (("cerca", "CERCA 390"), ("locales", "LOCALES 390"),
                           ("mapa", "MAPA 390"), ("ia", "IA 390"),
                           ("radio", "RADIO 390"), ("tours", "TOURS 390")):
            c.js("document.querySelector('.tabbar .tab[data-tab=%s]').click()" % tab)
            audit(c, label, 0.8 if tab != "mapa" else 4)

        # Asistente en lenguaje natural.
        c.js("document.querySelector('.tabbar .tab[data-tab=ia]').click()")
        c.js("document.querySelector('.ai-example').click()")
        time.sleep(10)
        print("IA_PREGUNTA:", json.dumps(probe(c, {
            "explicacion": "!document.getElementById('aiExplain').hidden",
            "resultados": "document.querySelectorAll('#aiResults .ai-result').length",
            "fuentes": "document.querySelectorAll('#aiExplain a').length",
        }), ensure_ascii=False))
        audit(c, "IA_PREGUNTA 390", 0)

        # Copiloto de ruta.
        c.js("(()=>{document.getElementById('routeFrom').value='Newark, NJ';"
             "document.getElementById('routeTo').value='Trenton, NJ';"
             "document.getElementById('btnRoute').click()})()")
        time.sleep(10)
        print("IA_RUTA:", json.dumps(probe(c, {
            "bloques": "document.querySelectorAll('#routeOut .ai-block').length",
            "camaras": "document.querySelectorAll('#routeOut .ai-result').length",
            "texto": "document.getElementById('routeOut').textContent.slice(0,90)",
        }), ensure_ascii=False))
        audit(c, "IA_RUTA 390", 0)

        # Alertas y agrupación de favoritos.
        c.js("document.getElementById('btnAlerts').click()")
        time.sleep(10)
        print("IA_ALERTAS:", json.dumps(probe(c, {
            "bloques": "document.querySelectorAll('#alertsOut .ai-block').length",
            "texto": "document.getElementById('alertsOut').textContent.slice(0,90)",
        }), ensure_ascii=False))
        audit(c, "IA_ALERTAS 390", 0)

        c.js("document.getElementById('btnGroups').click()")
        time.sleep(3)
        print("IA_GRUPOS:", json.dumps(probe(c, {
            "bloques": "document.querySelectorAll('#groupsOut .ai-block').length",
            "texto": "document.getElementById('groupsOut').textContent.slice(0,90)",
        }), ensure_ascii=False))
        audit(c, "IA_GRUPOS 390", 0)

        # Contexto: se abre una cámara desde el resultado de IA y se explica.
        c.js("(()=>{const b=document.querySelector('#aiResults .ai-result button');"
             "if(b)b.click(); else document.querySelector('#list .item')?.click()})()")
        time.sleep(1)
        c.js("document.querySelector('.tabbar .tab[data-tab=ia]').click()")
        c.js("document.getElementById('btnContextAi').click()")
        time.sleep(12)
        print("IA_CONTEXTO:", json.dumps(probe(c, {
            "bloques": "document.querySelectorAll('#contextOut .ai-block').length",
            "texto": "document.getElementById('contextOut').textContent.slice(0,90)",
        }), ensure_ascii=False))
        audit(c, "IA_CONTEXTO 390", 0)

        # Comparador con videos reales en vivo.
        c.js("document.getElementById('btnCompareAi').click()")
        time.sleep(10)
        print("COMPARADOR:", json.dumps(probe(c, {
            "abierto": "!document.getElementById('compareModal').hidden",
            "tarjetas": "document.querySelectorAll('#compareGrid .compare-card').length",
            "videos": "document.querySelectorAll('#compareGrid video').length",
        }), ensure_ascii=False))
        audit(c, "COMPARADOR 390", 0)
        c.js("document.getElementById('btnCloseCompare').click()")

        # Tours narrados (categoría aparte).
        c.js("document.querySelector('.tabbar .tab[data-tab=tours]').click()")
        c.js("(()=>{const s=document.getElementById('tourNarr');"
             "s.value='NJ Turnpike Tour';document.getElementById('btnNarrate').click()})()")
        time.sleep(6)
        print("TOURS_NARRADOS:", json.dumps(probe(c, {
            "pasos": "document.querySelectorAll('#tourOut .tour-step').length",
            "bloques": "document.querySelectorAll('#tourOut .ai-block').length",
            "voz": "!document.getElementById('btnSpeak').disabled",
        }), ensure_ascii=False))
        audit(c, "TOURS_NARRADOS 390", 0)

        # Capas IA sobre el mapa.
        c.js("document.querySelector('.tabbar .tab[data-tab=mapa]').click()")
        time.sleep(3)
        c.js("(()=>{const e=document.getElementById('mapLayers');e.checked=true;"
             "e.dispatchEvent(new Event('change'))})()")
        time.sleep(20)
        print("MAPA_CAPAS:", json.dumps(probe(c, {
            "info": "document.getElementById('mapLayerInfo').textContent.slice(0,140)",
            "visible": "!document.getElementById('mapLayerInfo').hidden",
            "contador": "document.getElementById('mapCount').textContent",
        }), ensure_ascii=False))
        audit(c, "MAPA_CAPAS 390", 0)

        # Clima animado en tiempo real (tile del resumen + tarjeta IA).
        c.js("document.querySelector('.tabbar .tab[data-tab=ia]').click()")
        c.js("document.getElementById('btnWx').click()")
        time.sleep(14)
        print("CLIMA:", json.dumps(probe(c, {
            "animTile": "document.getElementById('weatherTile').dataset.anim",
            "temp": "document.getElementById('wxTemp').textContent",
            "desc": "document.getElementById('wxDesc').textContent",
            "bloques": "document.querySelectorAll('#wxOut .ai-block').length",
            "horas": "document.querySelectorAll('#wxOut .wx-hour').length",
            "nwr": "document.getElementById('wxOut').textContent.includes('MHz')",
        }), ensure_ascii=False))
        audit(c, "CLIMA 390", 0)

        # Herramientas combinadas: corredor (reglas) y sensores/frecuencias.
        c.js("document.getElementById('btnCorridor').click()")
        time.sleep(22)
        print("CORREDOR:", json.dumps(probe(c, {
            "medidor": "document.querySelector('#combinedOut .corridor-gauge')?.textContent",
            "bloques": "document.querySelectorAll('#combinedOut .ai-block').length",
            "fuentes": "document.querySelectorAll('#combinedOut a').length",
        }), ensure_ascii=False))
        audit(c, "CORREDOR 390", 0)

        c.js("document.getElementById('btnSensors').click()")
        time.sleep(14)
        print("SENSORES:", json.dumps(probe(c, {
            "bloques": "document.querySelectorAll('#combinedOut .ai-block').length",
            "texto": "document.getElementById('combinedOut').textContent.slice(0,100)",
        }), ensure_ascii=False))
        audit(c, "SENSORES 390", 0)

        # Radio: categorías, emisoras verificadas, logos y audio en vivo.
        c.js("document.querySelector('.tabbar .tab[data-tab=radio]').click()")
        time.sleep(14)
        print("RADIO:", json.dumps(probe(c, {
            "estado": "document.getElementById('radioStatus').textContent",
            "emisoras": "document.querySelectorAll('#radioList .station').length",
            "categorias": "document.getElementById('radioCategory').options.length",
            "logos": "document.querySelectorAll('#radioList img.station-logo').length",
        }), ensure_ascii=False))
        audit(c, "RADIO_LISTA 390", 0)

        c.js("(()=>{const b=document.querySelector('#radioList .station button');if(b)b.click()})()")
        time.sleep(8)
        print("RADIO_AUDIO:", json.dumps(probe(c, {
            "reproductor": "!document.getElementById('radioPlayer').hidden",
            "src": "(document.getElementById('radioAudio').currentSrc||'').slice(0,60)",
            "nombre": "document.getElementById('radioPlayerName').textContent",
            "meta": "document.getElementById('radioNow').textContent.slice(0,60)",
        }), ensure_ascii=False))
        audit(c, "RADIO_PLAYER 390", 0)
        c.js("document.getElementById('btnRadioStop').click()")

        # Metadata ICY real: WBGO (audio/mpeg) actualiza radioNow/radioMetaAt
        # desde /api/radio/metadata, sin textos inventados por la interfaz.
        c.js("(()=>{const card=[...document.querySelectorAll('#radioList .station')]"
             ".find(x=>x.textContent.includes('WBGO'));"
             "const b=card&&card.querySelector('button');if(b)b.click()})()")
        time.sleep(12)
        print("RADIO_ICY:", json.dumps(probe(c, {
            "nombre": "document.getElementById('radioPlayerName').textContent",
            "meta": "document.getElementById('radioNow').textContent.slice(0,70)",
            "at": "document.getElementById('radioMetaAt').textContent.slice(0,70)",
            "reales": "document.getElementById('radioMetaAt').textContent.includes('Metadatos reales')",
        }), ensure_ascii=False))
        audit(c, "RADIO_ICY 390", 0)
        c.js("document.getElementById('btnRadioStop').click()")

        # Capas combinadas sobre el mapa: zonas, sensores y radio.
        c.js("document.querySelector('.tabbar .tab[data-tab=mapa]').click()")
        time.sleep(3)
        c.js("(()=>{['mapZones','mapSensors','mapRadio'].forEach(id=>{"
             "const e=document.getElementById(id);e.checked=true;"
             "e.dispatchEvent(new Event('change'))})})()")
        time.sleep(16)
        print("MAPA_EXTRAS:", json.dumps(probe(c, {
            "contador": "document.getElementById('mapCount').textContent.slice(0,180)",
            "zonas": "document.getElementById('mapZones').checked",
            "sensores": "document.getElementById('mapSensors').checked",
            "radio": "document.getElementById('mapRadio').checked",
        }), ensure_ascii=False))
        audit(c, "MAPA_EXTRAS 390", 4)

        # Chips de zonas locales en Cámaras y filtro por zona. Se recarga para
        # que no queden filtros IA de las pruebas anteriores (aislar el caso).
        c.js("location.reload()")
        time.sleep(7)
        c.js("document.querySelector('.tabbar .tab[data-tab=camaras]').click()")
        time.sleep(1)
        print("ZONAS_LOCALES:", json.dumps(probe(c, {
            "barra": "!document.getElementById('localZoneBar').hidden",
            "chips": "document.querySelectorAll('#localZoneChips .zchip').length",
            "info": "document.getElementById('localZoneInfo').textContent",
        }), ensure_ascii=False))
        c.js("(()=>{const chips=document.querySelectorAll('#localZoneChips .zchip');"
             "if(chips[1])chips[1].click()})()")
        time.sleep(1)
        print("ZONA_FILTRO:", json.dumps(probe(c, {
            "activo": "document.querySelector('#localZoneChips .zchip.on')?.textContent",
            "filas": "document.querySelectorAll('#list .item').length",
        }), ensure_ascii=False))
        audit(c, "ZONA_FILTRO 390", 0)

        c.js("document.getElementById('btnWizard').click()")
        audit(c, "GUIA 390", 0.8)

        print("HTTP_ERRORES:", json.dumps(c.responses[:10], ensure_ascii=False))
        print("ERRORES:", json.dumps(c.errors, ensure_ascii=False))
        if c.errors:
            FAIL.append("%d error(es) de JavaScript" % len(c.errors))
        print("AUDITORIA: %s incidencias" % len(FAIL))
        for f in FAIL:
            print("  - " + f)
    finally:
        p.terminate()
        try:
            p.wait(timeout=6)
        except Exception:
            p.kill()


if __name__ == "__main__":
    main()
