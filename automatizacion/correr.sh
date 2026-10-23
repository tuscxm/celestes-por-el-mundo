#!/usr/bin/env bash
# Corre la revisión completa desde la raíz del repositorio (en la nube de Claude, donde SofaScore responde).
# Uso: bash automatizacion/correr.sh                 -> hoy y ayer
#      bash automatizacion/correr.sh --fecha 2026-10-13 --clave mourino --forzar
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c "import numpy, scipy, matplotlib, playwright, rembg, cv2, pymatting; cv2.dnn_superres" 2>/dev/null \
  || { echo "Instalando dependencias (rembg, opencv, pymatting...): puede tardar varios minutos"; \
       timeout 1200 pip install --progress-bar off --break-system-packages -r automatizacion/requirements.txt \
       || echo "AVISO: la instalación de dependencias no terminó (se sigue igual; las caras pueden salir sin recortar)"; }
if [ $# -eq 0 ]; then set -- --dias 2; fi
rm -rf salida_hoy
python3 automatizacion/infografia_sofascore.py automatizacion/jugadores.json "$@" \
  --procesados automatizacion/procesados.json --salida salida_hoy
GITHUB_REPOSITORY=tuscxm/celestes-por-el-mundo GITHUB_REPOSITORY_OWNER=tuscxm \
  python3 automatizacion/publicar.py salida_hoy
