#!/usr/bin/env python3
"""Genera crm_agentes_capacitadores.csv (UTF-8, coma) listo para importar a un CRM.
Solo agentes con teléfono (obligatorio); el correo es opcional.
Une detalle_stps.csv con los archivos de terminos/ y quita duplicados por RFC."""
import csv, glob, re

lista = {}
for f in sorted(glob.glob("terminos/*.csv")):
    for r in csv.DictReader(open(f, newline="", encoding="utf-8-sig")):
        lista.setdefault(r["RFC"].strip(), r)

def partir(valor, patron):
    partes = [p.strip() for p in re.split(patron, valor or "") if p.strip()]
    return (partes[0] if partes else ""), "; ".join(partes[1:])

COLS = ["nombre_empresa", "rfc", "telefono", "telefono_alterno", "correo", "correo_alterno",
        "calle", "colonia", "cp", "municipio", "estado", "tipo_agente", "tipo_institucion",
        "estatus", "registro_imss", "fuente"]
vistos, filas, sin_tel = set(), [], 0
for d in csv.DictReader(open("detalle_stps.csv", newline="", encoding="utf-8-sig")):
    rfc = d["rfc"].strip()
    if rfc in vistos:
        continue
    vistos.add(rfc)
    tel, tel2 = partir(d["telefono"], r"[,;/]|\s+Y\s+|\s{2,}")
    if not re.search(r"\d{6,}", re.sub(r"\D", "", tel)):
        sin_tel += 1
        continue
    mail, mail2 = partir(d["correo"].lower(), r"[,;\s]+")
    l = lista.get(rfc, {})
    filas.append({
        "nombre_empresa": d["nombre"], "rfc": rfc, "telefono": tel, "telefono_alterno": tel2,
        "correo": mail, "correo_alterno": mail2, "calle": d["calle"], "colonia": d["colonia"],
        "cp": d["cp"], "municipio": d["municipio"], "estado": d["entidad"],
        "tipo_agente": l.get("Tipo de agente", ""), "tipo_institucion": d["tipo_institucion"],
        "estatus": l.get("Estatus", ""), "registro_imss": d["imss"],
        "fuente": "STPS - Agentes Capacitadores Externos"})
with open("crm_agentes_capacitadores.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(filas)
print(f"{len(filas)} agentes exportados | descartados sin teléfono: {sin_tel} | "
      f"con correo: {sum(1 for r in filas if r['correo'])}")
