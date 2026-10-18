#!/usr/bin/env bash
# Corre la revisión completa desde la raíz del repositorio (en la nube de Claude, donde SofaScore responde).
# Uso: bash automatizacion/correr.sh                 -> hoy y ayer
#      bash automatizacion/correr.sh --fecha 2026-10-13 --clave mourino --forzar
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c "import numpy, scipy, matplotlib, playwright, rembg, cv2; cv2.dnn_superres" 2>/dev/null \
  || pip install -q --break-system-packages -r automatizacion/requirements.txt
if [ $# -eq 0 ]; then set -- --dias 2; fi
rm -rf salida_hoy
python3 automatizacion/infografia_sofascore.py automatizacion/jugadores.json "$@" \
  --procesados automatizacion/procesados.json --salida salida_hoy
GITHUB_REPOSITORY=tuscxm/celestes-por-el-mundo GITHUB_REPOSITORY_OWNER=tuscxm \
  python3 automatizacion/publicar.py salida_hoy
