"""
Carga en SQLite el CSV de scraper_stps.py o de descargar_datos_abiertos.py
(detecta separador , ; | o tabulador y codificación UTF-8 o latin-1).

Uso:
    python cargar_sqlite.py capacitadores_stps.csv capacitadores.db
"""

import csv
import io
import re
import sqlite3
import sys
import unicodedata


def nombre_columna(texto, i):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"\W+", "_", texto).strip("_").lower()
    return texto or f"col_{i}"


def main(csv_path="capacitadores_stps.csv", db_path="capacitadores.db"):
    try:
        texto = open(csv_path, encoding="utf-8-sig", newline="").read()
    except UnicodeDecodeError:
        texto = open(csv_path, encoding="latin-1", newline="").read()
    dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;|\t")
    lector = csv.reader(io.StringIO(texto, newline=""), dialecto)
    encabezados = next(lector)
    filas = [f + [""] * (len(encabezados) - len(f)) for f in lector if any(f)]
    filas = [f[:len(encabezados)] for f in filas]

    columnas, usados = [], set()
    for i, h in enumerate(encabezados):
        c = nombre_columna(h, i)
        while c in usados:
            c += "_"
        usados.add(c)
        columnas.append(c)

    con = sqlite3.connect(db_path)
    con.execute("DROP TABLE IF EXISTS capacitadores")
    con.execute(
        "CREATE TABLE capacitadores (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        + ", ".join(f'"{c}" TEXT' for c in columnas) + ")"
    )
    con.executemany(
        f"INSERT INTO capacitadores ({', '.join(chr(34) + c + chr(34) for c in columnas)}) "
        f"VALUES ({', '.join('?' * len(columnas))})",
        filas,
    )
    con.commit()
    print(f"{len(filas)} filas en {db_path}, tabla 'capacitadores' con columnas: "
          + ", ".join(columnas))
    con.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
