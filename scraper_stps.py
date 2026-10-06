"""
Extractor del buscador de Agentes Capacitadores Externos de la STPS.

    https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx

El sitio es ASP.NET WebForms (postbacks con __VIEWSTATE), así que en lugar de
reproducir las peticiones a mano se usa un navegador real (Playwright):

  1. Abre el buscador.
  2. (Opcional) Recorre cada opción de un <select> (p. ej. Entidad Federativa)
     cuando el sitio no permite buscar sin filtros.
  3. Pulsa el botón de búsqueda.
  4. Lee la tabla de resultados más grande de la página (GridView).
  5. Avanza por la paginación (__doPostBack ... 'Page$N') hasta el final.

Las páginas visitadas se guardan en ./debug/ para poder ajustar los selectores
si el sitio cambia.

Uso:
    pip install playwright && playwright install chromium
    python scraper_stps.py                       # búsqueda sin filtros
    python scraper_stps.py --iterar-select auto  # una búsqueda por cada estado
    python scraper_stps.py --headful --max-paginas 2   # prueba rápida, viendo el navegador
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = "https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx"
DEBUG_DIR = Path("debug")
PATRON_BOTON = re.compile(r"buscar|consultar|search", re.I)


def limpiar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def firma(page):
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:  # la página está navegando
        return None


def esperar_postback(page, timeout):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PWTimeout:
        pass


def click_y_esperar(page, elemento, timeout):
    """Clic que dispara un postback (completo o UpdatePanel) y espera a que el
    contenido de la página realmente cambie."""
    antes = firma(page)
    elemento.click()
    limite = time.monotonic() + timeout / 1000
    while time.monotonic() < limite:
        page.wait_for_timeout(300)
        ahora = firma(page)
        if ahora is not None and ahora != antes:
            break
    esperar_postback(page, timeout)


def boton_busqueda(page, selector):
    if selector:
        return page.locator(selector).first
    candidatos = page.locator(
        "input[type=submit], input[type=button], button, a[href*='__doPostBack']"
    )
    for i in range(candidatos.count()):
        c = candidatos.nth(i)
        texto = (c.get_attribute("value") or "") + " " + (c.inner_text() or "")
        texto += " " + (c.get_attribute("id") or "")
        if PATRON_BOTON.search(texto) and c.is_visible():
            return c
    raise RuntimeError(
        "No se encontró el botón de búsqueda; usa --boton '<selector css>'. "
        "Revisa debug/inicio.html para ver los ids."
    )


def tabla_resultados(page):
    """Devuelve (encabezados, filas) de la tabla con más filas de datos."""
    return page.evaluate(
        r"""() => {
        const limpio = t => (t || '').replace(/\s+/g, ' ').trim();
        let mejor = null;
        for (const tabla of document.querySelectorAll('table')) {
            // ignorar tablas que contienen otras tablas (layout) salvo el pager
            const filas = [...tabla.rows].filter(tr =>
                tr.closest('table') === tabla &&
                !tr.querySelector("a[href*='Page$']") &&
                !tr.querySelector('table'));
            const datos = filas.filter(tr => tr.cells.length >= 2 &&
                                             [...tr.cells].some(c => c.tagName === 'TD'));
            if (!mejor || datos.length > mejor.datos.length) {
                const th = filas.find(tr => tr.querySelector('th'));
                mejor = {
                    encabezados: th ? [...th.cells].map(c => limpio(c.innerText)) : [],
                    datos: datos.filter(tr => tr !== th)
                                .map(tr => [...tr.cells].map(c => limpio(c.innerText))),
                };
            }
        }
        return mejor ? [mejor.encabezados, mejor.datos] : [[], []];
    }"""
    )


def siguiente_pagina(page, actual):
    """Link del pager hacia la página actual+1 (incluye el '...' de GridView)."""
    for patron in (f"Page${actual + 1}'", "Page$Next'",
                   f"navegador$lnk{actual + 1}'", "navegador$lnkSiguiente'"):
        link = page.locator(f"a[href*=\"{patron}\"]")
        if link.count():
            return link.first
    return None


def extraer_busqueda(page, args, etiqueta):
    click_y_esperar(page, boton_busqueda(page, args.boton), args.timeout)
    filas_totales, encabezados, pagina = [], [], 1
    while True:
        (DEBUG_DIR / f"{etiqueta}_p{pagina}.html").write_text(page.content(), "utf-8")
        enc, filas = tabla_resultados(page)
        encabezados = encabezados or enc
        if filas and filas_totales and filas[0] == filas_totales[-len(filas)]:
            break  # el pager no avanzó: ya estamos en la última página
        filas_totales.extend(filas)
        print(f"  [{etiqueta}] página {pagina}: {len(filas)} filas "
              f"(acumulado {len(filas_totales)})", flush=True)
        if args.max_paginas and pagina >= args.max_paginas:
            break
        link = siguiente_pagina(page, pagina)
        if link is None:
            break
        time.sleep(args.pausa)
        click_y_esperar(page, link, args.timeout)
        pagina += 1
    return encabezados, filas_totales


def elegir_select(page, selector):
    if selector != "auto":
        return page.locator(selector).first
    selects = page.locator("select")
    mejor, n_mejor = None, 0
    for i in range(selects.count()):
        n = selects.nth(i).locator("option").count()
        if n > n_mejor:
            mejor, n_mejor = selects.nth(i), n
    if mejor is None:
        raise RuntimeError("La página no tiene <select> que recorrer.")
    return mejor


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default="capacitadores_stps.csv")
    ap.add_argument("--boton", help="selector CSS del botón de búsqueda (auto si se omite)")
    ap.add_argument("--iterar-select", metavar="SELECTOR|auto",
                    help="hacer una búsqueda por cada opción de este <select>")
    ap.add_argument("--texto", help="términos (3+ letras) separados por coma; una búsqueda por "
                    "cada uno en el campo de nombre. El sitio exige al menos uno.")
    ap.add_argument("--campo", default="#ctl00_MainContent_tbRazonSocial",
                    help="selector CSS del campo donde se escribe --texto")
    ap.add_argument("--max-paginas", type=int, default=0, help="0 = sin límite")
    ap.add_argument("--pausa", type=float, default=1.5,
                    help="segundos entre peticiones (sé amable con el servidor)")
    ap.add_argument("--timeout", type=int, default=60_000, help="ms por postback")
    ap.add_argument("--headful", action="store_true", help="mostrar el navegador")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--chromium", help="ruta a un ejecutable de Chromium/Chrome ya instalado")
    args = ap.parse_args()

    DEBUG_DIR.mkdir(exist_ok=True)
    encabezados, registros = [], []

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=not args.headful,
                                      executable_path=args.chromium)
        page = navegador.new_page(locale="es-MX")
        page.set_default_timeout(args.timeout)
        page.goto(args.url, wait_until="networkidle")
        (DEBUG_DIR / "inicio.html").write_text(page.content(), "utf-8")

        if args.texto:
            for termino in [t.strip() for t in args.texto.split(",") if t.strip()]:
                page.goto(args.url, wait_until="networkidle")
                page.fill(args.campo, termino)
                etiqueta = "texto_" + re.sub(r"\W+", "_", termino)
                print(f"Buscando '{termino}'", flush=True)
                enc, filas = extraer_busqueda(page, args, etiqueta)
                encabezados = encabezados or enc
                registros.extend(filas)
                time.sleep(args.pausa)
        elif args.iterar_select:
            opciones = elegir_select(page, args.iterar_select).locator("option")
            valores = [(opciones.nth(i).get_attribute("value"),
                        limpiar(opciones.nth(i).inner_text()))
                       for i in range(opciones.count())]
            valores = [(v, t) for v, t in valores
                       if v not in (None, "", "0", "-1") and not t.lower().startswith("selec")]
            print(f"Recorriendo {len(valores)} opciones del filtro")
            for valor, texto in valores:
                page.goto(args.url, wait_until="networkidle")
                elegir_select(page, args.iterar_select).select_option(valor)
                esperar_postback(page, args.timeout)  # algunos selects hacen AutoPostBack
                etiqueta = re.sub(r"\W+", "_", texto)[:40] or valor
                enc, filas = extraer_busqueda(page, args, etiqueta)
                encabezados = encabezados or enc
                registros.extend([texto] + f for f in filas)
                time.sleep(args.pausa)
            encabezados = ["Filtro"] + encabezados
        else:
            encabezados, registros = extraer_busqueda(page, args, "busqueda")

        navegador.close()

    # quitar duplicados conservando el orden
    vistos, unicos = set(), []
    for r in registros:
        clave = tuple(r)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(r)

    if not unicos:
        sys.exit("No se obtuvieron filas. Revisa los HTML en debug/ "
                 "(quizá el buscador exige un filtro: prueba --iterar-select auto).")

    ancho = max(len(r) for r in unicos)
    if len(encabezados) != ancho:
        encabezados = (encabezados + [f"col_{i}" for i in range(ancho)])[:ancho]
    with open(args.salida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(encabezados)
        w.writerows(r + [""] * (ancho - len(r)) for r in unicos)
    print(f"\n{len(unicos)} registros guardados en {args.salida}")


if __name__ == "__main__":
    main()
