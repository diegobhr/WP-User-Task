#!/bin/bash
# Por cada término: 1) lista de agentes  2) ficha con teléfono/correo. Luego el siguiente.
cd ~/WP-User-Task
for T in CAP CON ASE SER INS EDU; do
  echo "=== $T: lista ==="
  .venv/bin/python scraper_stps.py --pausa 1 --texto "$T" --salida debug/_tmp.csv
  echo "=== $T: contacto ==="
  .venv/bin/python detalle_stps.py --entrada "terminos/texto_$T.csv" --pausa 1
  echo "=== $T: COMPLETO ==="
done
echo "=== TODOS LOS TÉRMINOS COMPLETOS ==="
