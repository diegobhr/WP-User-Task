"""
Carga el CSV generado por scraper_stps.py en una base SQLite.

Uso:
    python cargar_sqlite.py capacitadores_stps.csv capacitadores.db
"""

import csv
import re
import sqlite3
import sys
import unicodedata


def nombre_columna(texto, i):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"\W+", "_", texto).strip("_").lower()
    return texto or f"col_{i}"


def main(csv_path="capacitadores_stps.csv", db_path="capacitadores.db"):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        encabezados = next(lector)
        filas = list(lector)

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
