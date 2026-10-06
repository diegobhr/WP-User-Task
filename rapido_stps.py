#!/usr/bin/env python3
"""Versión rápida: lista de agentes + ficha de contacto con peticiones HTTP
directas (sin navegador). Reproduce los postbacks de ASP.NET.

Por cada página de resultados (20 agentes) hace 1 petición de paginación y
1 por agente para su ficha, reutilizando el estado de esa página.

Uso:
    python rapido_stps.py --texto CAP,CON,ASE --hilos 3
    python rapido_stps.py --texto CAP --limite 40      # prueba

Salidas (igual que antes): terminos/texto_<T>.csv y detalle_stps.csv.
Es reanudable: salta los RFC que ya están en detalle_stps.csv.
"""
import argparse
import csv
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from detalle_stps import CAMPOS, COLUMNAS, parsear

URL = "https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx"
TERMINOS_DIR = Path("terminos")
CAMPO_NOMBRE = "ctl00$MainContent$tbRazonSocial"
BOTON = ("ctl00$MainContent$brnConsultar", "Consultar")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

escritura = threading.Lock()
imprimir = threading.Lock()


def log(msg):
    with imprimir:
        print(msg, flush=True)


def formulario(soup):
    """Valores actuales de todos los campos del <form> (como los enviaría el navegador)."""
    datos = {}
    for el in soup.select("form input[name], form select[name], form textarea[name]"):
        nombre, tipo = el["name"], (el.get("type") or "").lower()
        if el.name == "input":
            if tipo in ("submit", "button", "image", "file"):
                continue
            if tipo in ("checkbox", "radio") and not el.has_attr("checked"):
                continue
            datos[nombre] = el.get("value", "")
        elif el.name == "select":
            op = el.select_one("option[selected]") or el.select_one("option")
            datos[nombre] = op.get("value", op.get_text(strip=True)) if op else ""
        else:
            datos[nombre] = el.get_text()
    return datos


class Cliente:
    def __init__(self, pausa, timeout, semaforo):
        self.http = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"},
                                 timeout=timeout, follow_redirects=True)
        self.pausa, self.semaforo, self.base = pausa, semaforo, URL

    def pedir(self, datos=None, url=URL):
        for intento in range(1, 5):
            try:
                with self.semaforo:
                    r = (self.http.post(url, data=datos) if datos is not None
                         else self.http.get(url))
                    time.sleep(self.pausa)
                if r.status_code == 200:
                    return BeautifulSoup(r.text, "lxml")
                err = f"HTTP {r.status_code}"
            except httpx.HTTPError as e:
                err = type(e).__name__
            time.sleep(2 * intento)
        raise RuntimeError(f"falló la petición ({err})")

    def postback(self, soup, destino, extra=None):
        datos = formulario(soup)
        datos["__EVENTTARGET"], datos["__EVENTARGUMENT"] = destino, ""
        datos.update(extra or {})
        form = soup.select_one("form")
        url = urljoin(self.base, form.get("action") or "") if form else URL
        return self.pedir(datos, url)


def filas_resultado(soup):
    """[(encabezados, [(celdas, destino_btnDatos), ...])] de la tabla de resultados."""
    tabla = soup.select_one("table#mytable")
    if not tabla:
        return [], []
    enc = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tabla.select("tr th")]
    filas = []
    for tr in tabla.select("tr"):
        a = tr.select_one("a[id$=btnDatos]")
        if not a:
            continue
        m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
        celdas = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        filas.append((celdas, m.group(1) if m else None))
    return enc, filas


def enlace_pagina(soup, actual):
    """Destino del postback hacia la página actual+1 (o 'Siguiente')."""
    for sufijo in (f"navegador_lnk{actual + 1}", "navegador_lnkSiguiente"):
        a = soup.select_one(f"a[id$={sufijo}]")
        if a:
            m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
            if m:
                return m.group(1)
    return None


def ficha(cli, soup, destino):
    s = cli.postback(soup, destino)
    texto = s.get_text("\n")
    if "Datos del agente capacitador" not in texto:
        raise RuntimeError("la respuesta no es una ficha")
    d = parsear("\n".join(l.strip() for l in texto.splitlines() if l.strip()))
    fila = {c: "" for c in COLUMNAS}
    fila["nombre"] = d.get("Nombre o razón social", "")
    for etiqueta, col in CAMPOS.items():
        fila[col] = re.sub(r"\s+", " ", d.get(etiqueta, "")).strip()
    return fila


def procesar_termino(termino, args, hechos, w_detalle, f_detalle, semaforo):
    cli = Cliente(args.pausa, args.timeout, semaforo)
    soup = cli.pedir()
    soup = cli.postback(soup, "", {CAMPO_NOMBRE: termino, BOTON[0]: BOTON[1]})
    etiqueta = "texto_" + re.sub(r"\W+", "_", termino)
    encabezados, lista, nuevas, errores, pagina = [], [], 0, 0, 1
    while True:
        enc, filas = filas_resultado(soup)
        encabezados = encabezados or enc
        if not filas:
            break
        if lista and filas[0][0] == lista[-len(filas)]:
            break  # el paginador no avanzó
        for celdas, destino in filas:
            lista.append(celdas)
            idx = encabezados.index("RFC") if "RFC" in encabezados else 1
            rfc = celdas[idx].strip() if len(celdas) > idx else ""
            if not rfc or rfc in hechos or not destino:
                continue
            if args.limite and nuevas >= args.limite:
                break
            try:
                d = ficha(cli, soup, destino)
            except Exception as e:  # noqa: BLE001
                errores += 1
                log(f"[{termino}] {rfc} ERROR: {str(e)[:60]}")
                continue
            d["rfc"] = rfc
            with escritura:
                if rfc in hechos:
                    continue
                hechos.add(rfc)
                w_detalle.writerow(d)
                f_detalle.flush()
            nuevas += 1
        log(f"[{termino}] página {pagina}: {len(lista)} en lista, {nuevas} fichas nuevas, "
            f"{errores} errores")
        if args.limite and nuevas >= args.limite:
            break
        destino = enlace_pagina(soup, pagina)
        if not destino:
            break
        soup = cli.postback(soup, destino)
        pagina += 1
    TERMINOS_DIR.mkdir(exist_ok=True)
    with open(TERMINOS_DIR / f"{etiqueta}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(encabezados)
        w.writerows(lista)
    log(f"=== {termino} COMPLETO: {len(lista)} en lista, {nuevas} fichas nuevas, {errores} errores ===")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--texto", required=True, help="términos de 3+ letras separados por coma")
    ap.add_argument("--hilos", type=int, default=3, help="términos en paralelo (máx. 4)")
    ap.add_argument("--pausa", type=float, default=0.2, help="segundos tras cada petición")
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--limite", type=int, default=0, help="fichas nuevas por término (prueba)")
    ap.add_argument("--salida", default="detalle_stps.csv")
    args = ap.parse_args()
    args.hilos = max(1, min(args.hilos, 4))

    salida = Path(args.salida)
    hechos = set()
    if salida.exists():
        with open(salida, newline="", encoding="utf-8-sig") as f:
            hechos = {r["rfc"] for r in csv.DictReader(f)}
    print(f"{len(hechos)} fichas ya hechas", flush=True)

    nuevo = not salida.exists()
    terminos = [t.strip() for t in args.texto.split(",") if t.strip()]
    semaforo = threading.Semaphore(args.hilos)
    with open(salida, "a", newline="", encoding="utf-8-sig") as f_detalle:
        w = csv.DictWriter(f_detalle, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        with ThreadPoolExecutor(max_workers=args.hilos) as pool:
            futuros = [pool.submit(procesar_termino, t, args, hechos, w, f_detalle, semaforo)
                       for t in terminos]
            for t, fu in zip(terminos, futuros):
                try:
                    fu.result()
                except Exception as e:  # noqa: BLE001
                    log(f"[{t}] ABORTADO: {e}")
    print("Listo.")


if __name__ == "__main__":
    sys.exit(main())
