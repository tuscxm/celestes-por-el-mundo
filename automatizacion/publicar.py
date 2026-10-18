"""Después de cada corrida: guarda lo nuevo en el repositorio, actualiza la galería del README
y deja listo el aviso si hubo infografías nuevas o errores.

Uso: GITHUB_REPOSITORY=tuscxm/celestes-por-el-mundo GITHUB_REPOSITORY_OWNER=tuscxm python3 automatizacion/publicar.py salida_hoy
Lee  salida_hoy/resumen.json (lo escribe infografia_sofascore.py).
Mueve PNG/JSON/_copy.txt a salida/, mapas a mapas/, figuras a salida/fotos/.
Escribe automatizacion/ultima_revision.json, README.md, y si corresponde avisos/<fecha_hora>.md
(primera línea = título). Al subirlo, el workflow .github/workflows/aviso.yml abre un issue y GitHub manda el mail."""
import json, os, re, shutil, sys, glob, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
DUENO = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
RAMA = os.environ.get("GITHUB_REF_NAME", "main")
CORRIDA = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
           if os.environ.get("GITHUB_RUN_ID") else "")
MAX_GALERIA = 24


def apodo(nombre):
    return nombre.split()[-1].title()


def mover(salida_hoy):
    for f in glob.glob(os.path.join(salida_hoy, "*")):
        b = os.path.basename(f)
        if b.endswith((".png", "_copy.txt")) or (b.endswith(".json") and b != "resumen.json"):
            shutil.copy2(f, os.path.join(RAIZ, "salida", b))
    for sub, dest in (("mapas", "mapas"), ("fotos", os.path.join("salida", "fotos"))):
        os.makedirs(os.path.join(RAIZ, dest), exist_ok=True)
        for f in glob.glob(os.path.join(salida_hoy, sub, "*")):
            shutil.copy2(f, os.path.join(RAIZ, dest, os.path.basename(f)))


def linea_jugador(j, p):
    n = apodo(j["nombre"])
    e = p.get("estado", "")
    if e == "jugó":
        nota = f", nota {p['nota']:.1f}" if p.get("nota") else ""
        rol = p.get("rol", "").replace("COMO ", "de ").lower()
        en = p.get("entro") or {}
        ent = f", entró al {en.get('minuto','').replace('’', chr(39))} por {en['por']}" if en.get("por") else ""
        return (f"**{n}** jugó {p['minutos']}' ({'titular' if p.get('titular') else 'suplente'}{ent}{nota}, {rol}) "
                f"en {p['partido']} · {p.get('torneo', '')}")
    if e == "sin partido en esas fechas":
        return f"{n}: sin partido hoy ni ayer"
    if e == "no jugó":
        return f"{n}: no jugó en {p.get('partido', '')} ({'suplente sin entrar' if p.get('suplente') else 'no entró'})"
    if e == "error":
        return f"{n}: ERROR al revisar {p.get('partido', '')} → `{p.get('error', '')}`"
    return f"{n}: {e} · {p.get('partido', '')}".rstrip(" ·")


def url_img(ruta):
    return f"https://github.com/{REPO}/blob/{RAMA}/{ruta}?raw=true" if REPO else ruta


def aviso(resumen, salida_hoy):
    jugaron, resto, avisos, errores, bloques = [], [], [], [], []
    for j in resumen["jugadores"]:
        for p in j["partidos"]:
            ln = linea_jugador(j, p)
            if p.get("estado") == "jugó":
                jugaron.append((j, p, ln))
                for a in p.get("avisos", []):
                    avisos.append(f"{apodo(j['nombre'])}: {a}")
            else:
                resto.append(ln)
                if p.get("estado") == "error":
                    errores.append(ln)
    if not jugaron and not errores:
        return False
    if jugaron:
        partes = []
        for j, p, _ in jugaron:
            nota = f", nota {p['nota']:.1f}" if p.get("nota") else ""
            partes.append(f"{apodo(j['nombre'])} jugó {p['minutos']}' ({'titular' if p.get('titular') else 'suplente'}{nota}) en {p['partido']}")
        titulo = "; ".join(partes) + ("; infografía lista" if len(jugaron) == 1 else "; infografías listas")
    else:
        titulo = "⚠️ Infografías: hubo un error al revisar los partidos"
    if errores and jugaron:
        titulo += " (con errores)"
    md = []
    if DUENO:
        md.append(f"@{DUENO}\n")
    if jugaron:
        md.append("## Quién jugó")
        md += [f"- {ln}" for _, _, ln in jugaron]
    if resto:
        md.append("\n## El resto")
        md += [f"- {ln}" for ln in resto]
    if avisos:
        md.append("\n## Avisos")
        md += [f"- {a}" for a in avisos]
    fu = [(j, p) for j, p, _ in jugaron if p.get("fuentes")]
    if fu:
        md.append("\n## Fuentes consultadas (uso interno, no va en el posteo)")
        for j, p in fu:
            md.append(f"- {apodo(j['nombre'])}: " + " · ".join(f"{k} {v}" for k, v in p["fuentes"].items()))
    for j, p, _ in jugaron:
        png = f"salida/{p['png']}"
        copy_path = os.path.join(RAIZ, "salida", p["archivo"] + "_copy.txt")
        copy = open(copy_path).read().strip() if os.path.exists(copy_path) else ""
        md.append(f"\n## {apodo(j['nombre'])} · {p['partido']}")
        md.append(f"![{p['archivo']}]({url_img(png)})")
        md.append(f"[Abrir la imagen en tamaño completo](https://github.com/{REPO}/blob/{RAMA}/{png})" if REPO else "")
        if copy:
            md.append("\nTexto para el posteo:\n```\n" + copy + "\n```")
    md.append("\n---\nNo se publicó nada en Instagram. Cerrá este aviso cuando la publiques o la descartes.")
    if CORRIDA:
        md.append(f"Detalle de la corrida: {CORRIDA}")
    os.makedirs(os.path.join(RAIZ, "avisos"), exist_ok=True)
    nombre = resumen["revisado"][:16].replace("T", "_").replace(":", "")
    ruta = os.path.join(RAIZ, "avisos", nombre + ".md")
    open(ruta, "w").write(titulo[:250].replace("\n", " ") + "\n\n" + "\n".join(md))
    print("aviso en", os.path.relpath(ruta, RAIZ))
    return True


def galeria():
    items = []
    for png in glob.glob(os.path.join(RAIZ, "salida", "*.png")):
        b = os.path.basename(png)[:-4]
        m = re.search(r"_(\d{4}-\d{2}-\d{2})(?:_|$)", b)
        if not m or b.startswith(("PRUEBA", "EJEMPLO")):
            continue
        cp = os.path.join(RAIZ, "salida", b + "_copy.txt")
        primera = open(cp).read().splitlines()[0] if os.path.exists(cp) else b.replace("_", " ")
        items.append((m.group(1), b, primera, os.path.exists(cp)))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return items[:MAX_GALERIA], len(items)


def readme(ultima):
    items, total = galeria()
    filas, celdas = [], []
    for fecha, b, primera, tiene_copy in items:
        texto = primera.replace("🇺🇾 ", "")
        celdas.append(f'<td align="center" valign="top" width="33%"><a href="salida/{b}.png"><img src="salida/{b}.png" width="300"></a><br>'
                      f'<sub>{texto}<br>{fecha}' + (f' · <a href="salida/{b}_copy.txt">texto del posteo</a>' if tiene_copy else '') + '</sub></td>')
        if len(celdas) == 3:
            filas.append("<tr>" + "".join(celdas) + "</tr>"); celdas = []
    if celdas:
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    rev = ""
    if ultima:
        rev = f"**Última revisión:** {ultima['revisado'].replace('T', ' ')} (hora de Uruguay) · fechas {', '.join(ultima['fechas'])}\n\n"
        rev += "\n".join(f"- {l}" for l in ultima["lineas"]) + "\n"
    return f"""# Celestes por el mundo · infografías

Todos los días a las 18:30 (hora de Uruguay) una tarea programada de Claude revisa si **{', '.join(ultima['jugadores']) if ultima else 'los jugadores'}** jugaron hoy o ayer
y arma una infografía por cada partido, la revisa y la guarda acá. Corre en la nube: no depende de ninguna computadora prendida. **No publica nada**: la publicación la hacés vos.

Cuando hay infografías nuevas (o un error), se abre un aviso en [Issues](../../issues) y GitHub te manda un mail.
Si a las 23:30 la revisión del día no llegó, GitHub también abre un aviso.
Cerrá el aviso cuando la publiques o la descartes.

{rev}
## Últimas infografías ({total} en total, todas en [`salida/`](salida))

<table>
{chr(10).join(filas)}
</table>

## Cómo se usa

- **Correrlo ahora o para una fecha puntual:** en Claude, abrí la tarea programada *Infografías Celestes por el mundo* y usá *Run now*, o pedíselo a Claude en un chat (por ejemplo: "armá la de Mouriño del 13/10").
- SofaScore no le responde a los servidores de GitHub, por eso los datos se bajan desde la nube de Claude y GitHub solo guarda, muestra y avisa.
- **Sumar o sacar jugadores:** editá [`automatizacion/jugadores.json`](automatizacion/jugadores.json) (cómo, en [`automatizacion/AGENTE.md`](automatizacion/AGENTE.md)).
- **Qué ya se procesó:** [`automatizacion/procesados.json`](automatizacion/procesados.json). Si borrás una línea, ese partido se vuelve a armar.
- Los mapas de calor quedan en [`mapas/`](mapas) y las figuras en [`salida/fotos/`](salida/fotos).

Datos: SofaScore. Las figuras son ilustraciones, no fotos de los jugadores.
"""


def main():
    salida_hoy = sys.argv[1]
    resumen = json.load(open(os.path.join(salida_hoy, "resumen.json")))
    mover(salida_hoy)
    lineas = [linea_jugador(j, p) for j in resumen["jugadores"] for p in j["partidos"]]
    ultima = {"revisado": resumen["revisado"], "fechas": resumen["fechas"], "lineas": lineas,
              "jugadores": [apodo(j["nombre"]) for j in resumen["jugadores"]]}
    json.dump(ultima, open(os.path.join(RAIZ, "automatizacion", "ultima_revision.json"), "w"), ensure_ascii=False, indent=1)
    hay = aviso(resumen, salida_hoy)
    open(os.path.join(RAIZ, "README.md"), "w").write(readme(ultima))
    print("aviso:", hay)
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
