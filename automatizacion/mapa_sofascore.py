"""Mapa de calor real del jugador en un partido, con los toques que publica SofaScore.
Uso: python3 mapa_sofascore.py jugadores.json <clave> <AAAA-MM-DD> [carpeta_salida]
Deja <carpeta_salida>/mapas/<clave>_<fecha>.png y <clave>_<fecha>.json (fuente, partido, cantidad de toques).
Si SofaScore no tiene el mapa, no deja nada y sale con código 2 (la plantilla muestra el perfil).
Necesita el campo "sofascore_id" del jugador en jugadores.json. Corre en la nube (api.sofascore.com)."""
import json, os, sys, datetime, urllib.request
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Circle, Arc
from scipy.ndimage import gaussian_filter

API = "https://api.sofascore.com/api/v1"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

def buscar_partido(pid, fecha):
    for page in (0, 1):
        try:
            evs = get(f"/player/{pid}/events/last/{page}").get("events", [])
        except Exception:
            break
        for e in evs:
            d = datetime.datetime.fromtimestamp(e["startTimestamp"], datetime.timezone.utc).date()
            if d == fecha:
                return e
    return None

def dibujar(puntos, salida):
    L, W = 105.0, 68.0
    # SofaScore: x 0..100 a lo largo (arco propio en 0, ataca hacia 100), y 0..100 a lo ancho con
    # y=0 en el costado DERECHO del equipo (verificado con posiciones medias: lateral derecho y≈15,
    # lateral izquierdo y≈81). Cancha vertical con el ataque hacia arriba: derecha del equipo a la derecha.
    xs = (100 - np.array([p["y"] for p in puntos])) / 100 * W
    ys = np.array([p["x"] for p in puntos]) / 100 * L
    H, _, _ = np.histogram2d(ys, xs, bins=[210, 136], range=[[0, L], [0, W]])
    H = gaussian_filter(H, sigma=9)
    H = H / H.max() if H.max() > 0 else H
    cmap = LinearSegmentedColormap.from_list("calor", [(0, (1, .88, .4, 0)), (.18, (1, .88, .4, .35)),
                                                       (.45, (1, .7, .12, .7)), (.75, (1, .35, .12, .85)), (1, (.85, .08, .08, .95))])
    fig = plt.figure(figsize=(W / 20, L / 20), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-2, W + 2); ax.set_ylim(-2, L + 2); ax.axis("off")
    fig.patch.set_facecolor("#1f5a3c"); ax.set_facecolor("#1f5a3c")
    ax.imshow(H, extent=[0, W, 0, L], origin="lower", cmap=cmap, interpolation="bilinear", zorder=2, aspect="auto")
    lw, c = 1.4, (1, 1, 1, .8)
    ax.add_patch(Rectangle((0, 0), W, L, fill=False, lw=lw, ec=c, zorder=3))
    ax.plot([0, W], [L / 2, L / 2], lw=lw, c=c, zorder=3)
    ax.add_patch(Circle((W / 2, L / 2), 9.15, fill=False, lw=lw, ec=c, zorder=3))
    for y0, s in ((0, 1), (L, -1)):
        ax.add_patch(Rectangle(((W - 40.3) / 2, y0 if s > 0 else y0 - 16.5), 40.3, 16.5, fill=False, lw=lw, ec=c, zorder=3))
        ax.add_patch(Rectangle(((W - 18.3) / 2, y0 if s > 0 else y0 - 5.5), 18.3, 5.5, fill=False, lw=lw, ec=c, zorder=3))
        ax.add_patch(Arc((W / 2, y0 + s * 11), 18.3, 18.3, theta1=37 if s > 0 else 217, theta2=143 if s > 0 else 323, lw=lw, ec=c, zorder=3))
    ax.annotate("", xy=(W - 3, L - 4), xytext=(W - 3, L - 16), arrowprops=dict(arrowstyle="-|>", color=(1, 1, 1, .75), lw=1.6), zorder=4)
    fig.savefig(salida, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)

def main(jug_path, clave, fecha_s, base="."):
    jugs = json.load(open(jug_path))
    j = next(x for x in jugs if x["clave"] == clave)
    pid = j.get("sofascore_id")
    if not pid:
        print("FALTA sofascore_id en jugadores.json para", clave); sys.exit(2)
    fecha = datetime.date.fromisoformat(fecha_s)
    e = buscar_partido(pid, fecha)
    if not e:
        print("SIN PARTIDO en SofaScore para", clave, fecha_s); sys.exit(2)
    try:
        puntos = get(f"/event/{e['id']}/player/{pid}/heatmap").get("heatmap", [])
    except Exception as ex:
        print("SIN MAPA en SofaScore:", ex); sys.exit(2)
    if len(puntos) < 5:
        print("SIN MAPA en SofaScore (", len(puntos), "puntos)"); sys.exit(2)
    os.makedirs(os.path.join(base, "mapas"), exist_ok=True)
    png = os.path.join(base, "mapas", f"{clave}_{fecha_s}.png")
    dibujar(puntos, png)
    meta = {"fuente": "SofaScore", "credito": "Datos: SofaScore", "evento": e["id"], "toques": len(puntos),
            "partido": f'{e["homeTeam"]["name"]} {e.get("homeScore", {}).get("current")}-{e.get("awayScore", {}).get("current")} {e["awayTeam"]["name"]}'}
    json.dump(meta, open(png[:-4] + ".json", "w"), ensure_ascii=False)
    print("OK", png, meta)

if __name__ == "__main__":
    main(*sys.argv[1:])
