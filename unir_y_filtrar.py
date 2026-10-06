#!/usr/bin/env python3
"""Une la lista (capacitadores_stps.csv) con las fichas (detalle_stps.csv) en
SQLite. Crea la tabla `agentes` (todos) y la vista `agentes_con_contacto`
(solo los que tienen teléfono o fax; el correo es opcional).

Uso: python unir_y_filtrar.py [capacitadores.db]
"""
import csv
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "capacitadores.db"
leer = lambda ruta: list(csv.DictReader(open(ruta, newline="", encoding="utf-8-sig")))
lista, detalle = leer("capacitadores_stps.csv"), {r["rfc"]: r for r in leer("detalle_stps.csv")}

con = sqlite3.connect(db)
con.executescript("""
DROP VIEW IF EXISTS agentes_con_contacto; DROP TABLE IF EXISTS agentes;
CREATE TABLE agentes (rfc TEXT PRIMARY KEY, nombre TEXT, tipo_agente TEXT, estatus TEXT,
  programas INTEGER, instructores INTEGER, imss TEXT, tipo_institucion TEXT, cp TEXT,
  entidad TEXT, municipio TEXT, colonia TEXT, calle TEXT, localidad TEXT,
  telefono TEXT, fax TEXT, correo TEXT);
""")
for r in lista:
    d = detalle.get(r["RFC"], {})
    con.execute("INSERT OR IGNORE INTO agentes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        r["RFC"], r["Nombre o razón social"], r["Tipo de agente"], r["Estatus"],
        r["Programas o cursos"], r["Plantilla de instructores"],
        *(d.get(k, "") for k in ("imss", "tipo_institucion", "cp", "entidad", "municipio",
                                 "colonia", "calle", "localidad", "telefono", "fax", "correo"))))
con.execute("""CREATE VIEW agentes_con_contacto AS SELECT * FROM agentes
  WHERE TRIM(COALESCE(telefono,'')) <> '' OR TRIM(COALESCE(fax,'')) <> ''""")
con.commit()
q = lambda s: con.execute(s).fetchone()[0]
print("agentes:", q("SELECT COUNT(*) FROM agentes"),
      "| con teléfono o fax:", q("SELECT COUNT(*) FROM agentes_con_contacto"),
      "| de ellos con correo:",
      q("SELECT COUNT(*) FROM agentes_con_contacto WHERE TRIM(COALESCE(correo,''))<>''"))
