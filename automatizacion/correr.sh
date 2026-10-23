#!/usr/bin/env bash
# Corre la revisión completa desde la raíz del repositorio (en la nube de Claude, donde SofaScore responde).
# Uso: bash automatizacion/correr.sh                 -> hoy y ayer
#      bash automatizacion/correr.sh --fecha 2026-10-13 --clave mourino --forzar
set -euo pipefail
cd "$(dirname "$0")/.."
# Python: el más nuevo que haya (en la nube, python3 puede ser 3.11 con las dependencias en 3.13); todo corre e instala con el mismo
PY="$(command -v python3.13 || command -v python3.12 || command -v python3)"
"$PY" -c "import numpy, scipy, matplotlib, playwright, rembg, cv2, pymatting; cv2.dnn_superres" 2>/dev/null \
  || { echo "Instalando dependencias (rembg, opencv, pymatting...): puede tardar varios minutos"; \
       timeout 1200 "$PY" -m pip install --progress-bar off --break-system-packages -r automatizacion/requirements.txt \
       || echo "AVISO: la instalación de dependencias no terminó (se sigue igual; las caras pueden salir sin recortar)"; }
# Playwright tiene que coincidir con el Chromium de la nube (/opt/pw-browsers); si no, busca la versión que sí
"$PY" automatizacion/ajustar_playwright.py || true
if [ $# -eq 0 ]; then set -- --dias 2; fi
rm -rf salida_hoy
"$PY" automatizacion/infografia_sofascore.py automatizacion/jugadores.json "$@" \
  --procesados automatizacion/procesados.json --salida salida_hoy
GITHUB_REPOSITORY=tuscxm/celestes-por-el-mundo GITHUB_REPOSITORY_OWNER=tuscxm \
  "$PY" automatizacion/publicar.py salida_hoy
