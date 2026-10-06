#!/usr/bin/env python3
"""Segunda fase: abre la ficha "Datos del agente" de cada RFC y guarda
teléfono, correo, IMSS, domicilio completo, etc.

Entrada : CSV del scraper (columna "RFC"), por defecto capacitadores_stps.csv
Salida  : detalle_stps.csv (se agrega fila por fila; si se corta, al volver a
          ejecutar continúa donde se quedó).

Uso:
    python detalle_stps.py --limite 5          # prueba con 5 agentes
    python detalle_stps.py                     # todos
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx"
CAMPO_RFC = "#ctl00_MainContent_tbRFC"
BOTON = "#ctl00_MainContent_brnConsultar"
CAMPOS = {
    "Registro patronal del IMSS": "imss",
    "Tipo de institución": "tipo_institucion",
    "Codigo Postal": "cp",
    "Entidad Federativa": "entidad",
    "Municipio o Delegación": "municipio",
    "Colonia": "colonia",
    "Calle": "calle",
    "Localidad": "localidad",
    "Telefono": "telefono",
    "Fax": "fax",
    "Correo electrónico": "correo",
}
COLUMNAS = ["rfc", "nombre"] + list(CAMPOS.values())


def parsear(texto):
    """Pares 'Etiqueta:' -> valor (la línea siguiente, si no es otra etiqueta)."""
    lineas = [l.strip() for l in texto.splitlines()]
    datos = {}
    for i, l in enumerate(lineas):
        etiqueta = l.rstrip(":").strip()
        if l.endswith(":") or etiqueta in CAMPOS:
            etiqueta = l.split(":")[0].strip()
            valor = ""
            resto = l.split(":", 1)[1].strip() if ":" in l else ""
            if resto:
                valor = resto
            else:
                for sig in lineas[i + 1:i + 3]:
                    if sig.startswith("*"):
                        break
                    if sig and not sig.endswith(":") and sig.split(":")[0] not in CAMPOS:
                        valor = sig
                        break
                    if sig.endswith(":") or sig.split(":")[0] in CAMPOS:
                        break
            datos[etiqueta] = valor
    return datos


def abrir_ficha(page, rfc, nombre, timeout):
    """Busca por RFC; si el sitio no lo encuentra (pasa con RFC de 10 caracteres),
    busca por nombre y abre la fila cuyo RFC coincide."""
    page.goto(URL, wait_until="networkidle")
    page.fill(CAMPO_RFC, rfc)
    page.click(BOTON)
    try:
        page.wait_for_selector("[id$=btnDatos]", timeout=8_000)
        page.click("[id$=btnDatos]")
        return
    except Exception:  # noqa: BLE001
        pass
    page.goto(URL, wait_until="networkidle")
    page.fill("#ctl00_MainContent_tbRazonSocial", nombre[:60])
    page.click(BOTON)
    page.wait_for_selector("[id$=btnDatos]", timeout=timeout)
    filas = page.locator("table#mytable tr", has=page.locator("[id$=btnDatos]"))
    for i in range(filas.count()):
        if rfc in filas.nth(i).inner_text():
            filas.nth(i).locator("[id$=btnDatos]").click()
            return
    raise RuntimeError("RFC no aparece en la búsqueda por nombre")


def consultar(page, rfc, nombre, timeout):
    abrir_ficha(page, rfc, nombre, timeout)
    page.wait_for_selector("text=Datos del agente capacitador", timeout=timeout)
    page.wait_for_load_state("networkidle")
    texto = page.inner_text("body")
    d = parsear(texto)
    fila = {col: "" for col in COLUMNAS}
    fila["rfc"] = rfc
    fila["nombre"] = d.get("Nombre o razón social", "")
    for etiqueta, col in CAMPOS.items():
        fila[col] = re.sub(r"\s+", " ", d.get(etiqueta, "")).strip()
    return fila


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", default="capacitadores_stps.csv")
    ap.add_argument("--salida", default="detalle_stps.csv")
    ap.add_argument("--limite", type=int, default=0, help="0 = todos")
    ap.add_argument("--pausa", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=30_000)
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    with open(args.entrada, newline="", encoding="utf-8-sig") as f:
        nombres = {r["RFC"].strip(): r.get("Nombre o razón social", "")
                   for r in csv.DictReader(f) if r.get("RFC", "").strip()}
    rfcs = list(nombres)

    salida = Path(args.salida)
    hechos = set()
    if salida.exists():
        with open(salida, newline="", encoding="utf-8-sig") as f:
            hechos = {r["rfc"] for r in csv.DictReader(f)}
    pendientes = [r for r in rfcs if r not in hechos]
    if args.limite:
        pendientes = pendientes[:args.limite]
    print(f"{len(rfcs)} RFC únicos, {len(hechos)} ya hechos, {len(pendientes)} por hacer",
          flush=True)
    if not pendientes:
        return

    nuevo = not salida.exists()
    with sync_playwright() as p, open(salida, "a", newline="", encoding="utf-8-sig") as out:
        w = csv.DictWriter(out, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        navegador = p.chromium.launch(headless=not args.headful)
        page = navegador.new_page(locale="es-MX")
        page.set_default_timeout(args.timeout)
        errores = 0
        for n, rfc in enumerate(pendientes, 1):
            for intento in (1, 2):
                try:
                    fila = consultar(page, rfc, nombres[rfc], args.timeout)
                    w.writerow(fila)
                    out.flush()
                    print(f"[{n}/{len(pendientes)}] {rfc} tel={fila['telefono'] or '-'} "
                          f"correo={fila['correo'] or '-'}", flush=True)
                    break
                except Exception as e:  # noqa: BLE001
                    if intento == 2:
                        errores += 1
                        print(f"[{n}/{len(pendientes)}] {rfc} ERROR: {str(e)[:80]}",
                              file=sys.stderr, flush=True)
                    else:
                        time.sleep(3)
            time.sleep(args.pausa)
        navegador.close()
    print(f"Listo. Errores: {errores}")


if __name__ == "__main__":
    main()
