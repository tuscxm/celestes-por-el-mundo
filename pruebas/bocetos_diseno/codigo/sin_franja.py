"""Boceto: la parte de abajo sin la franja del jugador (propuesta del 23/10/2026).

En vez de marcar una franja fija en el mapa y mostrar solo lo de esa franja ("POR EL CENTRO 5/69"), el mapa va
sin franja (con los remates marcados) y al lado un bloque "DÓNDE JUGÓ" que sirve para cualquier puesto:
porcentaje de sus acciones por la izquierda, el centro y la derecha (la mayor en dorado), en campo rival y los
toques en el área rival. Lo demás (SU PARTIDO, TOTALES, TEMPORADA) queda igual. render_v3.py no cambia.

Uso, desde la raíz del repositorio:  python3 pruebas/bocetos_diseno/codigo/sin_franja.py piquerez 2026-10-21
No le hace pedidos a API-Football. Deja el PNG en pruebas/bocetos_diseno/.
"""
import datetime, glob, json, os, shutil, subprocess, sys, tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
AUTO = os.path.join(RAIZ, "automatizacion")
sys.path.insert(0, AUTO)
import fuentes, respaldo_auto
from mapa_sofascore import dibujar_horizontal

fuentes._AF_SIN_PLAN = "boceto: sin pedidos a API-Football"


def donde_jugo(calor, st):
    """Filas del bloque DÓNDE JUGÓ, sacadas de las acciones del mapa de calor (x 0-100 hacia el arco rival,
    y 0-100 con 0 = costado derecho del equipo) y de los toques en el área rival que da la fuente."""
    n = len(calor)
    lados = [("Por la izquierda", sum(1 for p in calor if p["y"] > 200 / 3)),
             ("Por el centro", sum(1 for p in calor if 100 / 3 <= p["y"] <= 200 / 3)),
             ("Por la derecha", sum(1 for p in calor if p["y"] < 100 / 3))]
    mayor = max(k for _, k in lados)
    filas = [[t, f"{round(k * 100 / n)}%", k == mayor] for t, k in lados]
    filas.append(["En campo rival", f"{round(sum(1 for p in calor if p['x'] > 50) * 100 / n)}%", False])
    if st.get("touches_opp_box") is not None:
        filas.append(["Toques en el área rival", str(st["touches_opp_box"]), False])
    return filas


def main(clave, fecha_s):
    fecha = datetime.date.fromisoformat(fecha_s)
    j = next(x for x in json.load(open(os.path.join(AUTO, "jugadores.json"))) if x["clave"] == clave)
    tmp = tempfile.mkdtemp()
    respaldo_auto.armar(j, {fecha}, tmp, None, forzar=True)          # infografía actual (con franja)
    jp = next(p for p in glob.glob(os.path.join(tmp, "*.json")) if not p.endswith("resumen.json"))
    d = json.load(open(jp))[0]
    p = next(x for x in fuentes.fotmob(j, {fecha})[0] if x.get("minutos"))
    mapa = os.path.join(tmp, "mapas", f"{clave}_{fecha_s}_sin_franja.png")
    os.makedirs(os.path.dirname(mapa), exist_ok=True)
    dibujar_horizontal(p["calor"], mapa, None, remates=p.get("remates_mapa"))
    d["heat_img"] = os.path.relpath(mapa, tmp)
    d["zona"] = {"titulo": "DÓNDE JUGÓ", "filas": donde_jugo(p["calor"], p.get("stats") or {})}
    d["archivo"] = d["archivo"] + "_sin_franja"
    jp2 = os.path.join(tmp, d["archivo"] + ".json")
    json.dump([d], open(jp2, "w"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(AUTO, "render_v3.py"), jp2], check=True)
    destino = os.path.join(RAIZ, "pruebas", "bocetos_diseno")
    for archivo, nombre in ((jp[:-5] + ".png", f"5_actual_{clave}.png"), (jp2[:-5] + ".png", f"6_sin_franja_{clave}.png")):
        shutil.copy2(archivo, os.path.join(destino, nombre))
        print("OK", os.path.join(destino, nombre))


if __name__ == "__main__":
    main(*sys.argv[1:3])
