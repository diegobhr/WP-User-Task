# Capacitadores STPS → base de datos

Extrae el padrón público de Agentes Capacitadores Externos del
[buscador de la STPS](https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx)
y lo carga en SQLite.

## Instalación

```bash
pip install playwright
playwright install chromium
```

## Opción A (recomendada): datos abiertos oficiales

La STPS publica el padrón completo en CSV
(`datosabiertos.stps.gob.mx/Datos/DGCAPL/Registro_Agentes_Externos.csv`):

```bash
python descargar_datos_abiertos.py
python cargar_sqlite.py capacitadores_stps.csv capacitadores.db
```

## Opción B: scraper del buscador

```bash
# 1. Prueba rápida (2 páginas, viendo el navegador)
python scraper_stps.py --headful --max-paginas 2

# 2. Extracción completa
python scraper_stps.py
#    si el buscador exige elegir un filtro (p. ej. entidad federativa):
python scraper_stps.py --iterar-select auto

# 3. Cargar a SQLite
python cargar_sqlite.py capacitadores_stps.csv capacitadores.db
sqlite3 capacitadores.db "SELECT COUNT(*) FROM capacitadores;"
```

Opciones útiles: `--boton '#idDelBoton'` si no detecta el botón de búsqueda,
`--iterar-select '#idDelSelect'` para elegir el filtro, `--pausa 2` para ir más
lento. Cada página visitada se guarda en `debug/` para revisar los selectores.

Los datos son públicos, pero usa una pausa razonable entre peticiones y no
publiques datos personales (nombres/RFC de personas físicas) fuera del curso.
