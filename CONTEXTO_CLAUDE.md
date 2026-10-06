# Contexto para Claude: extracción de capacitadores STPS

> Resumen de una conversación previa con Claude Code (sesión en la nube).
> Pégalo o ábrelo en Claude dentro de VS Code para continuar donde nos quedamos.

## Quién soy y qué necesito

- Soy estudiante universitario. **No soy desarrollador**: explícame todo paso a paso,
  en español, con comandos listos para copiar y pegar.
- Uso **Mac** y **VS Code** (con la terminal integrada).
- Tarea: armar una base de datos con contenido real. Elegí el padrón público de
  **Agentes Capacitadores Externos de la STPS**:
  https://agentes.stps.gob.mx/Buscador/BuscadorAgente.aspx

## Lo que ya se hizo

Repositorio: `diegobhr/WP-User-Task`, rama `claude/stps-capacitadores-scraping-ge15hr`.

| Archivo | Qué hace |
|---|---|
| `scraper_stps.py` | Abre el buscador con Playwright (Chromium), pulsa "Buscar", lee la tabla de resultados más grande (GridView de ASP.NET) y recorre la paginación (`__doPostBack ... 'Page$N'`). Guarda `capacitadores_stps.csv` y copia cada página visitada en `debug/`. |
| `cargar_sqlite.py` | Carga un CSV en SQLite (tabla `capacitadores`). Detecta separador (`,` `;` `|` tab) y codificación (UTF-8 / latin-1). |
| `descargar_datos_abiertos.py` | Descarga el CSV de datos abiertos de la STPS (`datosabiertos.stps.gob.mx/Datos/DGCAPL/Registro_Agentes_Externos.csv`) a `estadisticas_stps.csv`. |
| `README.md` | Instrucciones de uso. |

Opciones del scraper:

- `--headful`: muestra el navegador.
- `--max-paginas N`: límite de páginas, para pruebas.
- `--iterar-select auto|<css>`: hace una búsqueda por cada opción de un `<select>`, por ejemplo por cada estado, si el buscador exige un filtro.
- `--boton '<css>'`: selector del botón de búsqueda si no se detecta solo.
- `--pausa S`: segundos entre peticiones (por defecto 1.5).
- `--timeout MS`: tiempo máximo de espera por página.
- `--chromium RUTA`: usar un Chrome ya instalado.

## Lo que se sabe / limitaciones

- Desde la sesión en la nube **no se pudo acceder** a ningún sitio del gobierno
  (stps.gob.mx, datos.gob.mx). Por eso el scraper **nunca se ha probado
  contra el sitio real**: los selectores del botón y de la tabla se detectan
  de forma heurística.
- Sí se probó contra una **página simulada** local (select de estados, botón
  "Buscar", GridView con 3 páginas): extrajo todo correctamente, con y sin
  `--iterar-select auto`, y la carga a SQLite funcionó. Se corrigió una
  condición de carrera: ahora `click_y_esperar` espera a que el contenido
  de la página cambie después de cada postback.
- El CSV de **datos abiertos** parece contener **conteos agregados** (agentes por
  entidad/periodo/modalidad), **no** el listado individual. Para el listado
  (nombre, RFC, registro, entidad…) hay que usar el scraper.
- El padrón incluye datos de personas físicas: usarlo solo para la tarea, no
  publicarlo. `.gitignore` excluye `*.csv`, `*.db` y `debug/`.

## Instalación que me explicaron (Mac + VS Code)

1. Instalar Python desde python.org y ejecutar `Install Certificates.command`.
2. Instalar la extensión "Python" de Microsoft en VS Code.
3. Descargar el ZIP de la rama y abrir la carpeta en VS Code.
4. En la terminal de VS Code:
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install playwright
   playwright install chromium
   ```
5. Prueba:
   ```
   python scraper_stps.py --headful --max-paginas 2
   ```
   Si dice "No se obtuvieron filas", agregar `--iterar-select auto`.
6. Cada vez que reabra VS Code: `source venv/bin/activate` (debe verse `(venv)`).

## Siguientes pasos (aquí quedamos)

1. **Correr la prueba del paso 5** y revisar el resultado:
   - Si funciona → revisar que las columnas de `capacitadores_stps.csv` tengan sentido.
   - Si falla → revisar el error y `debug/inicio.html` para ajustar los
     selectores en `scraper_stps.py` (función `boton_busqueda`,
     `tabla_resultados` o `siguiente_pagina`).
2. Extracción completa: `python scraper_stps.py` (con `--iterar-select auto` si hizo falta).
3. Cargar a SQLite: `python cargar_sqlite.py capacitadores_stps.csv capacitadores.db`
   y explorar con DB Browser for SQLite.
4. (Opcional) Diseñar un esquema más normalizado para la tarea (p. ej. tablas
   `entidades`, `capacitadores`, `estadisticas`) a partir del CSV real.

**Claude: como ya puedes ver mi computadora y la página real, empieza por correr
o ayudarme a correr el paso 1 y ajusta el scraper con lo que encuentres.
Explícame cada cosa de forma sencilla.**
