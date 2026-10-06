"""
Descarga el padrón oficial de Agentes Capacitadores Externos que la STPS
publica como datos abiertos (CSV). Es más rápido y confiable que el scraper.

Uso:
    python descargar_datos_abiertos.py            # guarda capacitadores_stps.csv
    python cargar_sqlite.py capacitadores_stps.csv capacitadores.db
"""

import sys
import urllib.request

URLS = [
    "https://datosabiertos.stps.gob.mx/Datos/DGCAPL/Registro_Agentes_Externos.csv",
    "http://datosabiertos.stps.gob.mx/Datos/DGCAPL/Registro_Agentes_Externos.csv",
]


def main(salida="capacitadores_stps.csv"):
    for url in URLS:
        try:
            print(f"Descargando {url} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                datos = r.read()
        except Exception as e:
            print(f"  falló: {e}")
            continue
        # el portal suele publicar en latin-1; se normaliza a UTF-8
        try:
            texto = datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = datos.decode("latin-1")
        with open(salida, "w", encoding="utf-8-sig", newline="") as f:
            f.write(texto)
        print(f"{texto.count(chr(10))} líneas guardadas en {salida}")
        return
    sys.exit("No se pudo descargar. Busca 'agentes capacitadores externos' en "
             "https://www.datos.gob.mx y usa scraper_stps.py como alternativa.")


if __name__ == "__main__":
    main(*sys.argv[1:])
