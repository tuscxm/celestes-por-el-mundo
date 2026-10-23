"""Deja instalada la versión de Playwright más nueva que puede abrir el Chromium que trae la nube.

En la nube de Claude el Chromium viene instalado en /opt/pw-browsers y no se puede bajar otro: cada versión de
Playwright pide una build exacta de Chromium. requirements.txt fija la que corresponde hoy; si la nube cambia de
Chromium, esto prueba las versiones de Playwright de la más nueva a la más vieja y se queda con la primera que lo abre.
Uso: python3 automatizacion/ajustar_playwright.py   (lo llama correr.sh antes de armar las infografías)
"""
import re, subprocess, sys

PRUEBA = """
import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as p:
        b = await p.chromium.launch(); print(b.version); await b.close()
asyncio.run(m())
"""
MAX_INTENTOS = 15


def abre():
    r = subprocess.run([sys.executable, "-c", PRUEBA], capture_output=True, text=True, timeout=120)
    return r.stdout.strip() if r.returncode == 0 else None


def version():
    r = subprocess.run([sys.executable, "-m", "pip", "show", "playwright"], capture_output=True, text=True)
    m = re.search(r"^Version: (\S+)", r.stdout, re.M)
    return m.group(1) if m else "no instalada"


def main():
    chromium = abre()
    if chromium:
        print(f"Playwright {version()} abre Chromium {chromium}")
        return
    print(f"Playwright {version()} no abre el Chromium de la nube; busco la versión que sí")
    r = subprocess.run([sys.executable, "-m", "pip", "index", "versions", "playwright"], capture_output=True, text=True)
    m = re.search(r"Available versions: (.*)", r.stdout)
    versiones = [v.strip() for v in m.group(1).split(",")] if m else []
    for v in versiones[:MAX_INTENTOS]:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", f"playwright=={v}"],
                       capture_output=True)
        chromium = abre()
        if chromium:
            print(f"Playwright {v} abre Chromium {chromium}: actualizá requirements.txt a playwright=={v}")
            return
    print("AVISO: ninguna versión de Playwright abre el Chromium de la nube; las infografías no se van a poder dibujar")


if __name__ == "__main__":
    main()
