"""Infografías 'Celestes por el mundo' armadas solo con datos reales de SofaScore. Corre en la nube.

Uso:
  python3 infografia_sofascore.py jugadores.json [--dias 2] [--fecha AAAA-MM-DD] [--clave mourino]
                                  [--procesados procesados.json] [--salida carpeta] [--forzar]

- Sin --fecha revisa los partidos de los últimos --dias días (hora de Montevideo, hoy incluido).
- Por cada jugador y partido terminado que no esté en procesados.json: si jugó (>0 min) arma
  <salida>/<Archivo>.png, .json, _copy.txt, mapas/<clave>_<fecha>.png y fotos/<clave>_<fecha>.svg.
- Al final escribe <salida>/resumen.json con el estado de cada jugador (jugó / no jugó / no terminó / sin partido)
  y los avisos. Nunca inventa datos: lo que SofaScore no trae se omite y se avisa.
Necesita al lado: render_v2.py, figura.py, mapa_sofascore.py, fotos/bernal_espalda_ancho.svg."""
import json, os, sys, subprocess, datetime
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from mapa_sofascore import get, dibujar, dibujar_horizontal
from figura import figura
from caras import cara, escudo, cara_oficial
import fuentes

TZ = ZoneInfo("America/Montevideo")
MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
# copas internacionales que se muestran en TEMPORADA además de la liga del club
COPAS_EUROPEAS = {7: "CHAMPIONS LEAGUE", 679: "EUROPA LEAGUE", 17015: "CONFERENCE LEAGUE",
                  384: "COPA LIBERTADORES", 480: "COPA SUDAMERICANA"}
NOMBRES_TORNEO = {"CONMEBOL Libertadores": "COPA LIBERTADORES", "CONMEBOL Sudamericana": "COPA SUDAMERICANA",
                  "Liga Profesional de Fútbol": "LIGA PROFESIONAL", "LaLiga": "LALIGA", "UEFA Champions League": "CHAMPIONS LEAGUE", "UEFA Europa League": "EUROPA LEAGUE",
                  "UEFA Europa Conference League": "CONFERENCE LEAGUE", "UEFA Conference League": "CONFERENCE LEAGUE",
                  "Liga Portugal Betclic": "LIGA PORTUGAL", "Liga Portugal": "LIGA PORTUGAL",
                  "International Friendly Games": "AMISTOSO INTERNACIONAL", "Copa del Rey": "COPA DEL REY"}
PAISES = {"Uruguay": "Uruguay", "Japan": "Japón", "South Korea": "Corea del Sur", "India": "India", "Brazil": "Brasil",
          "Argentina": "Argentina", "Spain": "España", "Portugal": "Portugal", "France": "Francia", "Germany": "Alemania",
          "England": "Inglaterra", "Italy": "Italia", "United States": "Estados Unidos", "Mexico": "México",
          "Colombia": "Colombia", "Chile": "Chile", "Paraguay": "Paraguay", "Peru": "Perú", "Ecuador": "Ecuador",
          "Bolivia": "Bolivia", "Venezuela": "Venezuela", "Morocco": "Marruecos", "Netherlands": "Países Bajos"}

def estrellas(r):
    """Nota del partido -> estrellas (como en las alineaciones con caras)."""
    if not r: return 0
    return 5 if r >= 8 else 4 if r >= 7.3 else 3 if r >= 6.7 else 2 if r >= 6 else 1

def _lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def tema(cam, equipo):
    """Colores del fondo: los de jugadores.json ("fondo") o, si no están, los del club."""
    if cam and cam.get("fondo"):
        c1, c2 = cam["fondo"][:2]; ac = cam["fondo"][2] if len(cam["fondo"]) > 2 else "#9fd6f7"
        return {"c1": c1, "c2": c2, "acento": ac}
    tc = equipo.get("teamColors") or {}
    p, s2 = tc.get("primary", "#2a6fb0"), tc.get("secondary", "#0d2440")
    if _lum(p) > 0.85: p, s2 = s2, "#0d1726"
    return {"c1": p, "c2": s2 if _lum(s2) < 0.85 else "#0d1726", "acento": "#9fd6f7"}

def nombre_equipo(t):
    return PAISES.get(t["name"], t["name"]) if t.get("national") else t["name"]

def fecha_local(e):
    return datetime.datetime.fromtimestamp(e["startTimestamp"], datetime.timezone.utc).astimezone(TZ).date()

def apellido(p):
    return p.get("lastName") or p.get("shortName", p["name"]).split(" ")[-1]

def corto(p):
    s = p.get("shortName") or p["name"]
    return s.split(". ", 1)[1] if ". " in s else s

def n(s, k):
    """Contador de SofaScore: si la clave no está, SofaScore lo omite porque es 0."""
    return int(s.get(k) or 0)

def lineas(formacion, titulares):
    try:
        tam = [1] + [int(x) for x in formacion.split("-")]
    except Exception:
        tam = []
    if sum(tam) != len(titulares):
        return None
    out, i = [], 0
    for t in tam:
        out.append(titulares[i:i + t]); i += t
    return out

def rol(pos, y):
    """pos: G/D/M/F de SofaScore. y: posición media a lo ancho (0 = costado derecho del equipo)."""
    if pos == "G":
        return "arquero", "COMO ARQUERO"
    if pos == "D":
        if y is not None and y < 30: return "lateral", "COMO LATERAL DERECHO"
        if y is not None and y > 70: return "lateral", "COMO LATERAL IZQUIERDO"
        return "central", "COMO DEFENSOR CENTRAL"
    if pos == "M":
        if y is not None and y < 25: return "banda", "COMO VOLANTE POR DERECHA"
        if y is not None and y > 75: return "banda", "COMO VOLANTE POR IZQUIERDA"
        return "mediocentro", "COMO MEDIOCENTRO"
    if pos == "F":
        return "delantero", "COMO DELANTERO"
    return "otro", "SU JUEGO"

def filas_posicion(r, s):
    f = []
    def frac(lbl, a, b, gold=False):
        if s.get(b): f.append([lbl, f"{n(s, a)}/{n(s, b)}", gold])
    def cnt(lbl, k, gold=False):
        f.append([lbl, str(n(s, k)), gold])
    def opt(lbl, k, fmt, gold=False):
        if s.get(k) is not None: f.append([lbl, fmt(s[k]), gold])
    if s.get("totalPass"):
        f.append(["Pases precisos", f"{n(s,'accuratePass')}/{n(s,'totalPass')}", False])
        f.append(["Precisión de pase", f"{round(n(s,'accuratePass')*100/n(s,'totalPass'))}%", True])
    if r in ("lateral", "central", "arquero"):
        if r == "arquero":
            cnt("Atajadas", "saves", True); cnt("Despejes", "totalClearance")
            frac("Pases largos precisos", "accurateLongBalls", "totalLongBalls")
        else:
            frac("Pases en campo rival", "accurateOppositionHalfPasses", "totalOppositionHalfPasses")
            if r == "lateral": frac("Centros precisos", "accurateCross", "totalCross")
            else: frac("Pases largos precisos", "accurateLongBalls", "totalLongBalls")
            frac("Entradas ganadas", "wonTackle", "totalTackle")
            cnt("Intercepciones", "interceptionWon"); cnt("Recuperaciones", "ballRecovery", True); cnt("Despejes", "totalClearance")
    elif r == "mediocentro":
        cnt("Pases clave", "keyPass", True); frac("Pases largos precisos", "accurateLongBalls", "totalLongBalls")
        cnt("Recuperaciones", "ballRecovery", True); cnt("Intercepciones", "interceptionWon")
        frac("Entradas ganadas", "wonTackle", "totalTackle"); frac("Regates exitosos", "wonContest", "totalContest")
    else:
        cnt("Pases clave", "keyPass", True); frac("Regates exitosos", "wonContest", "totalContest")
        frac("Centros precisos", "accurateCross", "totalCross")
        opt("Goles esperados (xG)", "expectedGoals", lambda v: f"{v:.2f}".replace(".", ","))
        cnt("Recuperaciones", "ballRecovery")
    if s.get("ballCarriesCount"):
        f.append(["Conducciones", f"{n(s,'ballCarriesCount')} ({round(s.get('totalBallCarriesDistance') or 0)} m)", False])
    opt("Distancia", "kilometersCovered", lambda v: f"{v:.2f} km".replace(".", ","))
    opt("Sprints", "numberOfSprints", lambda v: str(v))
    opt("Velocidad máxima", "topSpeed", lambda v: f"{v:.1f} km/h".replace(".", ","), True)
    return f[:10]

def temporada(pid, team_id, year, actual=None):
    """Bloques por competición del club en la temporada `year`: liga del club + copa europea si juega."""
    avisos = []
    try:
        liga_id = get(f"/team/{team_id}").get("team", {}).get("primaryUniqueTournament", {}).get("id")
    except Exception:
        liga_id = None
    try:
        ts = get(f"/player/{pid}/statistics/seasons").get("uniqueTournamentSeasons", [])
    except Exception:
        return [], ["Sin temporada en SofaScore"]
    filas = []
    # liga primero; después la copa del partido que se muestra (si es una copa); después las otras copas. Entran 2.
    orden = sorted(ts, key=lambda t: (t["uniqueTournament"]["id"] != liga_id, t["uniqueTournament"]["id"] != actual,
                                      t["uniqueTournament"]["id"] not in COPAS_EUROPEAS))
    bloques = 0
    for t in orden:
        if bloques >= 2: break
        ut = t["uniqueTournament"]
        if ut["id"] != liga_id and ut["id"] not in COPAS_EUROPEAS:
            continue
        season = next((s for s in t["seasons"] if s.get("year") == year), None)
        if not season:
            continue
        try:
            S = get(f"/player/{pid}/unique-tournament/{ut['id']}/season/{season['id']}/statistics/overall").get("statistics", {})
        except Exception:
            avisos.append(f"Sin estadísticas de {ut['name']}"); continue
        if not S.get("appearances"):
            continue
        nom = COPAS_EUROPEAS.get(ut["id"]) or NOMBRES_TORNEO.get(ut["name"], ut["name"].upper())
        bloques += 1
        filas += [[nom, " ", False],
                  ["PJ (tit.) · Min.", f"{n(S,'appearances')} ({n(S,'matchesStarted')}) · {n(S, 'minutesPlayed')}", False]]
        if S.get("rating"): filas.append(["Nota media", f"{S['rating']:.2f}", True])
        filas.append(["Goles · Asist.", f"{n(S,'goals')} · {n(S,'assists')}", False])
        filas.append(["Tarjetas", tarjetas_txt(n(S, 'yellowCards'), n(S, 'redCards') + n(S, 'yellowRedCards')), False])
    return filas[:10], avisos

def comp_clave(nombre):
    """Nombre de competición -> clave común entre fuentes (para promediar notas de la temporada)."""
    t = fuentes.norm(nombre)
    if "champions" in t: return "champions"
    if "conference" in t: return "conference"
    if "europa" in t: return "europa"
    if "libertadores" in t: return "libertadores"
    if "sudamericana" in t: return "sudamericana"
    if "laliga" in t or "la liga" in t or "primera division" in t: return "laliga"
    if "portugal" in t or "primeira" in t: return "portugal"
    return t


def notas_temporada(filas, datos):
    """Nota media de cada competición = promedio de todas las fuentes que la traen. Se toca solo esa fila."""
    otras = {}
    for d in (datos or {}).values():
        for comp, v in (d.get("temporada") or {}).items():
            if v.get("nota"): otras.setdefault(comp_clave(comp), []).append(v["nota"])
    out, comp, i = [], None, 0
    while i < len(filas):
        f = filas[i]; out.append(f)
        if f[1] == " ":
            comp = comp_clave(f[0])
        elif f[0] == "Nota media" and comp in otras:
            prom = fuentes.promedio([float(f[1])] + otras[comp])
            out[-1] = ["Nota media", f"{prom:.2f}", f[2]]
        elif f[0].startswith("PJ") and comp in otras and not (i + 1 < len(filas) and filas[i + 1][0] == "Nota media"):
            out.append(["Nota media", f"{fuentes.promedio(otras[comp]):.2f}", True])
        i += 1
    return out[:10]


def comparar(nombre, principal, otros, avisos):
    """Datos fijos: se usa el principal. Si otra fuente dice distinto, queda en los avisos (no en la infografía)."""
    dif = {f: v for f, v in otros.items() if v is not None and principal is not None and str(v) != str(principal)}
    if dif:
        avisos.append(f"Las fuentes no coinciden en {nombre}: SofaScore {principal} · " + " · ".join(f"{f} {v}" for f, v in dif.items()) + " (se usó SofaScore)")


def tarjetas_txt(amarillas, rojas):
    """Texto con las dos tarjetas: '2[A] · 1[R]' (la plantilla dibuja [A] amarilla y [R] roja)."""
    return f"{amarillas or 0}[A] · {rojas or 0}[R]"


ZONAS = {"derecha": ("POR LA DERECHA", lambda y: y < 100 / 3), "centro": ("POR EL CENTRO", lambda y: 100 / 3 <= y <= 200 / 3),
         "izquierda": ("POR LA IZQUIERDA", lambda y: y > 200 / 3)}


def por_zona(zona, puntos, rb, tiros=None, s=None, ataque=False, volante=False):
    """Lo que hizo en una franja de la cancha (a lo ancho, desde su equipo: y < 33 derecha, 33-67 centro, > 67 izquierda).
    puntos: mapa de calor; rb: rating-breakdown de SofaScore (cada acción con su ubicación). Solo datos con ubicación."""
    if zona not in ZONAS: return None
    titulo, en = ZONAS[zona]
    f = []
    if puntos:
        k = sum(1 for p in puntos if en(p["y"]))
        f.append(["Acciones", f"{k}/{len(puntos)} ({round(k * 100 / len(puntos))}%)", True])
    def acc(cat, tipo=None):
        return [e for e in (rb or {}).get(cat) or [] if (tipo is None or e.get("eventActionType") == tipo)
                and (e.get("playerCoordinates") or {}).get("y") is not None and en(e["playerCoordinates"]["y"])]
    pa = acc("passes")
    if (rb or {}).get("passes") is not None and pa:
        f.append(["Pases precisos", f"{sum(1 for e in pa if e.get('outcome'))}/{len(pa)}", False])
    if volante and (rb or {}).get("passes") is not None:
        ut = [e for e in pa if (e.get("passEndCoordinates") or {}).get("x", 0) >= 200 / 3]
        f.append(["Pases al último tercio", f"{sum(1 for e in ut if e.get('outcome'))}/{len(ut)}", True])
    if ataque and tiros is not None:
        # el mapa de remates mide el ancho al revés que el resto (y alto = costado derecho): se da vuelta
        tz = [t for t in tiros if (t.get("playerCoordinates") or {}).get("y") is not None and en(100 - t["playerCoordinates"]["y"])]
        f.append(["Remates al arco", f"{sum(1 for t in tz if t.get('shotType') in ('goal', 'save'))}/{len(tz)}", True])
    if ataque and s is not None and (rb or {}).get("passes") is not None:
        # asistencias en la franja: solo si se puede saber sin suponer (todas las jugadas de pase clave registradas
        # están dentro o todas fuera de la franja, y están todas las que cuenta la estadística)
        asis = n(s, "goalAssist")
        kp_all = [e for e in rb["passes"] if e.get("keypass")]
        kp_in = [e for e in pa if e.get("keypass")]
        if asis == 0:
            f.append(["Asistencias", "0", False])
        elif len(kp_all) == n(s, "keyPass") and len(kp_in) in (0, len(kp_all)):
            f.append(["Asistencias", str(asis if kp_in else 0), True])
    kp = sum(1 for e in pa if e.get("keypass"))
    if kp: f.append(["Pases clave", str(kp), True])
    dr = acc("dribbles")
    if dr: f.append(["Regates exitosos", f"{sum(1 for e in dr if e.get('outcome'))}/{len(dr)}", False])
    if (rb or {}).get("defensive") is not None:
        f.append(["Recuperaciones", str(len(acc("defensive", "ball-recovery"))), False])
        it, de = len(acc("defensive", "interception")), len(acc("defensive", "clearance"))
        if it or de: f.append(["Intercep. · Despejes", f"{it} · {de}", False])
    if (rb or {}).get("ball-carries") is not None:
        f.append(["Conducciones", str(len(acc("ball-carries"))), False])
    for d in ("Conducciones", "Intercep. · Despejes", "Regates exitosos"):
        if len(f) <= 7: break
        f = [x for x in f if x[0] != d]
    return {"titulo": titulo, "filas": f[:7]} if f else None


def extras_volante(rb):
    """Para volantes, mediocentros y jugadores mixtos (Valverde, Araújo): pases que llegaron al último tercio y
    recuperaciones en cada tercio de la cancha (defensa · medio · ataque). Solo con acciones que traen ubicación
    (x a lo largo: 0 su arco, 100 el arco rival)."""
    f = {}
    if not rb: return f
    pa = [e for e in rb.get("passes") or [] if (e.get("passEndCoordinates") or {}).get("x") is not None]
    if rb.get("passes") is not None:
        ut = [e for e in pa if e["passEndCoordinates"]["x"] >= 200 / 3]
        f["ultimo_tercio"] = ["Pases al último tercio", f"{sum(1 for e in ut if e.get('outcome'))}/{len(ut)}", True]
    if rb.get("defensive") is not None:
        rec = [e for e in rb["defensive"] if e.get("eventActionType") == "ball-recovery" and (e.get("playerCoordinates") or {}).get("x") is not None]
        t = [sum(1 for e in rec if lo <= e["playerCoordinates"]["x"] < hi) for lo, hi in ((0, 100 / 3), (100 / 3, 200 / 3), (200 / 3, 101))]
        f["recup_zonas"] = ["Recup. def · med · ata", f"{t[0]} · {t[1]} · {t[2]}", False]
    return f


def filas_ataque(s):
    """Pases peligrosos, asistencias y todo lo de remates (para delanteros y los más adelantados)."""
    f = []
    tiros = n(s, "totalShots") if "totalShots" in s else n(s, "onTargetScoringAttempt") + n(s, "shotOffTarget") + n(s, "blockedScoringAttempt")
    f.append(["Remates al arco", f"{n(s, 'onTargetScoringAttempt')}/{tiros}", True])
    f.append(["Remates afuera · bloq.", f"{n(s, 'shotOffTarget')} · {n(s, 'blockedScoringAttempt')}", False])
    if n(s, "hitWoodwork"): f.append(["Remates al palo", str(n(s, "hitWoodwork")), True])
    if s.get("expectedGoals") is not None: f.append(["Goles esperados (xG)", f"{s['expectedGoals']:.2f}".replace(".", ","), False])
    f.append(["Ocasiones claras falladas", str(n(s, "bigChanceMissed")), False])
    f.append(["Pases clave", str(n(s, "keyPass")), True])
    f.append(["Ocasiones claras creadas", str(n(s, "bigChanceCreated")), True])
    if s.get("expectedAssists") is not None: f.append(["Asistencias esperadas (xA)", f"{s['expectedAssists']:.2f}".replace(".", ","), False])
    if s.get("totalCross"): f.append(["Centros precisos", f"{n(s, 'accurateCross')}/{n(s, 'totalCross')}", False])
    return f


# filas que se sacan primero cuando no entran en TOTALES
DESCARTABLES = ["Velocidad máxima", "Sprints", "Distancia", "Pases en campo rival", "Despejes", "Pases largos precisos",
                "Entradas ganadas", "Intercepciones", "Conducciones", "Regates exitosos", "Recuperaciones"]


def armar_totales(base, ataque, volante, tarjetas, tope=14):
    """TOTALES: pases, después lo de ataque y lo de volante si corresponde, el resto, y las tarjetas al final."""
    pases = [x for x in base if x[0] in ("Pases precisos", "Precisión de pase")]
    resto = [x for x in base if x[0] not in ("Pases precisos", "Precisión de pase")]
    filas = pases + (volante.get("ultimo_tercio") and [volante["ultimo_tercio"]] or []) + ataque + resto
    if volante.get("recup_zonas"):
        i = next((k for k, x in enumerate(filas) if x[0] == "Recuperaciones"), len(filas) - 1) + 1
        filas.insert(i, volante["recup_zonas"])
    vistas, sin_rep = set(), []
    for x in filas:
        if x[0] not in vistas: vistas.add(x[0]); sin_rep.append(x)
    filas = sin_rep
    for d in DESCARTABLES:
        if len(filas) < tope: break
        filas = [x for x in filas if x[0] != d]
    return filas[:tope - 1] + [["Tarjetas", tarjetas, False]]


def club_de(jug, player):
    """Equipo del club del jugador según SofaScore (para la temporada)."""
    t = player.get("team") or {}
    return t.get("id")

def armar_partido(j, e, salida, plantilla_fig, extra=None):
    pid = j["sofascore_id"]; avisos = []
    lu = get(f"/event/{e['id']}/lineups")
    lado, yo = None, None
    for side in ("home", "away"):
        for p in lu.get(side, {}).get("players", []):
            if p["player"]["id"] == pid:
                lado, yo = side, p
    if not yo:
        return {"estado": "no convocado"}
    st = yo.get("statistics") or {}
    try:
        s = get(f"/event/{e['id']}/player/{pid}/statistics").get("statistics") or st
    except Exception:
        s = st
    minutos = s.get("minutesPlayed") or st.get("minutesPlayed") or 0
    if not minutos:
        return {"estado": "no jugó", "suplente": bool(yo.get("substitute"))}
    titular = not yo.get("substitute")
    fecha = fecha_local(e)
    clave = j["clave"]
    equipo = e["homeTeam"] if lado == "home" else e["awayTeam"]
    rival = e["awayTeam"] if lado == "home" else e["homeTeam"]
    datos = fuentes.del_partido(extra, fecha, rival["name"])

    # Posiciones medias (para ordenar la cancha y saber si jugó de lateral o de central)
    try:
        _ap = get(f"/event/{e['id']}/average-positions").get(lado, [])
        avg = {p["player"]["id"]: p.get("averageY") for p in _ap}
        avgx = {p["player"]["id"]: p.get("averageX") for p in _ap}
    except Exception:
        avg, avgx = {}, {}
    # Mapa de calor
    mapa = None
    try:
        puntos = get(f"/event/{e['id']}/player/{pid}/heatmap").get("heatmap", [])
    except Exception:
        puntos = []
    y_med = avg.get(pid)
    if y_med is None and puntos:
        y_med = sum(p["y"] for p in puntos) / len(puntos)
    if len(puntos) >= 5:
        os.makedirs(os.path.join(salida, "mapas"), exist_ok=True)
        mapa = f"mapas/{clave}_{fecha}.png"
        dibujar_horizontal(puntos, os.path.join(salida, mapa), j.get("zona"))
        json.dump({"fuente": "SofaScore", "credito": "Datos: SofaScore", "evento": e["id"], "toques": len(puntos)},
                  open(os.path.join(salida, mapa[:-4] + ".json"), "w"))
    else:
        avisos.append("SofaScore no tiene mapa de calor de este partido: se muestra el perfil")

    r, pos_titulo = rol(yo.get("position") or yo["player"].get("position"), y_med)
    # Su franja de la cancha (jugadores.json "zona": derecha / centro / izquierda)
    try:
        rb = get(f"/event/{e['id']}/player/{pid}/rating-breakdown")
    except Exception:
        rb = None
    zona = por_zona(j.get("zona"), puntos, rb)
    if j.get("zona") and not zona:
        avisos.append("No hay datos con ubicación para separar lo que hizo " + ZONAS.get(j["zona"], ("",))[0].lower())

    # Alineación
    tit = [p for p in lu[lado]["players"] if not p.get("substitute")]
    form = lu[lado].get("formation", "")
    ls = lineas(form, tit)
    if ls is None:
        avisos.append("No se pudo dibujar la formación"); ls = [tit]
    def orden(l):
        if all(avg.get(p["player"]["id"]) is not None for p in l):
            return sorted(l, key=lambda p: -avg[p["player"]["id"]])
        return list(reversed(l))  # SofaScore lista de derecha a izquierda
    recursos = os.path.join(salida, "recursos")
    def ficha(p):
        dor = str(p.get("jerseyNumber") or p.get("shirtNumber") or "")
        # estrellas: promedio de las notas de todas las fuentes (por dorsal)
        rt = fuentes.promedio([(p.get("statistics") or {}).get("rating")] + [d.get("notas_once", {}).get(dor) for d in datos.values()])
        return {"dorsal": p.get("jerseyNumber") or p.get("shirtNumber") or "", "nombre": corto(p["player"]),
                "cara": cara(p["player"]["id"], recursos, clave if p["player"]["id"] == pid else None),
                "estrellas": estrellas(rt), "yo": p["player"]["id"] == pid, "pid": p["player"]["id"]}
    once = [[ficha(p) for p in orden(l)] for l in ls]
    dorsal = str(yo.get("jerseyNumber") or yo.get("shirtNumber") or yo["player"].get("jerseyNumber") or "")
    if minutos < 20:
        avisos.append(f"Jugó solo {minutos} minutos: hay pocos datos, revisar si vale la pena publicarla")

    # Incidencias: goles y tarjetas del jugador
    goles, amar, roja = 0, 0, 0
    sustitucion = None
    tarjetas_eq = {}   # id -> {"amarillas": n, "roja": minuto}  (para mostrarlas en la cancha)
    min_roja = None
    try:
        incs = get(f"/event/{e['id']}/incidents").get("incidents", [])
        for i in incs:
            if i.get("incidentType") != "card" or not (i.get("player") or {}).get("id"): continue
            t = tarjetas_eq.setdefault(i["player"]["id"], {"amarillas": 0, "roja": None})
            mi = f"{i.get('time')}+{i['addedTime']}’" if i.get("addedTime") else f"{i.get('time')}’"
            if i.get("incidentClass") == "yellow": t["amarillas"] += 1
            elif i.get("incidentClass") in ("red", "yellowRed"):
                t["roja"] = mi
                if i.get("incidentClass") == "yellowRed": t["amarillas"] = max(t["amarillas"], 1)
        for i in incs:
            if i.get("incidentType") == "substitution" and (i.get("playerIn") or {}).get("id") == pid:
                po = i.get("playerOut") or {}
                t = i.get("time"); ad = i.get("addedTime")
                sustitucion = {"minuto": f"{t}+{ad}’" if ad else f"{t}’", "por": corto(po) if po.get("name") else "",
                               "por_id": po.get("id")}
        for i in incs:
            if (i.get("player") or {}).get("id") != pid: continue
            if i.get("incidentType") == "goal" and i.get("incidentClass") != "ownGoal": goles += 1
            if i.get("incidentType") == "card":
                if i.get("incidentClass") == "yellow": amar += 1
                elif i.get("incidentClass") in ("red", "yellowRed"):
                    roja += 1; min_roja = tarjetas_eq.get(pid, {}).get("roja")
    except Exception:
        goles = n(s, "goals"); avisos.append("Sin incidencias: goles de las estadísticas y tarjetas sin confirmar")
    for l in once:
        for f in l:
            tj = tarjetas_eq.get(f.get("pid")) or {}
            if tj.get("roja"): f["roja"] = tj["roja"]
            if tj.get("amarillas"): f["amarillas"] = tj["amarillas"]
    if sustitucion:
        for l in once:
            for f in l:
                if f.get("pid") == sustitucion["por_id"]:
                    f["sale"] = True
    elif not titular:
        avisos.append("No se encontró el cambio en el que entró")
    tarjetas = tarjetas_txt(amar, roja)

    generales = [["Goles", str(goles), goles > 0], ["Asistencias", str(n(s, "goalAssist")), n(s, "goalAssist") > 0],
                 ["Tiros (al arco)", f"{n(s,'totalShots') if 'totalShots' in s else n(s,'onTargetScoringAttempt')+n(s,'shotOffTarget')+n(s,'blockedScoringAttempt')} ({n(s,'onTargetScoringAttempt')})", False],
                 ["Toques", str(n(s, "touches")), False],
                 ["Duelos ganados", f"{n(s,'duelWon')}/{n(s,'duelWon')+n(s,'duelLost')}", False],
                 ["Duelos aéreos ganados", f"{n(s,'aerialWon')}/{n(s,'aerialWon')+n(s,'aerialLost')}", False],
                 ["Faltas cometidas", str(n(s, "fouls")), False], ["Tarjetas", tarjetas, False],
                 ["Pérdidas de balón", str(n(s, "possessionLostCtrl")), False]]

    # Jugador, temporada y figura
    player = get(f"/player/{pid}").get("player", {})
    year = (e.get("season") or {}).get("year")
    club_id = club_de(j, player)
    ut_actual = (e["tournament"].get("uniqueTournament") or {}).get("id")
    filas_t, av = temporada(pid, club_id, year, ut_actual) if (club_id and year and not equipo.get("national")) else ([], [])
    if equipo.get("national") and club_id:
        # partido de selección: temporada del club en curso
        try:
            evs = get(f"/team/{club_id}/events/last/0").get("events", [])
            y2 = (evs[-1].get("season") or {}).get("year") if evs else None
            filas_t, av = temporada(pid, club_id, y2) if y2 else ([], [])
            year = y2 or year
        except Exception:
            pass
    avisos += av
    filas_t = notas_temporada(filas_t, datos)
    if not filas_t:
        filas_t = [["Sin datos de temporada", " ", False]]; avisos.append("Sin temporada por competición")
    cams = j.get("camiseta", {})
    cam = (cams.get("7") if equipo.get("national") else next((v for k, v in cams.items() if k != "7"), None)) or next(iter(cams.values()))
    mi_cara = cara(pid, recursos, clave)
    if not equipo.get("national"):  # foto oficial del club (mejor calidad) para la imagen grande
        mi_cara = cara_oficial(clave, recursos, j.get("foto_oficial")) or mi_cara
    fig = None
    if not mi_cara:
        # sin foto: figura ilustrada de respaldo
        os.makedirs(os.path.join(salida, "fotos"), exist_ok=True)
        fig = f"fotos/{clave}_{fecha}.svg"
        open(os.path.join(salida, fig), "w").write(figura(plantilla_fig, apellido(player), dorsal, cam))
        avisos.append("No se consiguió la foto del jugador: se usó la figura ilustrada")

    nac = j.get("nacimiento")
    edad = None
    if nac:
        b = datetime.date.fromisoformat(nac); edad = fecha.year - b.year - ((fecha.month, fecha.day) < (b.month, b.day))
    valor = (player.get("proposedMarketValueRaw") or {}).get("value")
    perfil = [["DORSAL", dorsal], ["EDAD", f"{edad} años" if edad else "—"], ["ALTURA", j.get("altura", "—")],
              ["PIE", j.get("pie", "—")], ["POSICIÓN", pos_titulo.replace("COMO ", "").title()],
              ["VALOR", f"{valor/1e6:.1f} M€".replace(".", ",") if valor else "—"]]

    torneo = NOMBRES_TORNEO.get(e["tournament"].get("uniqueTournament", {}).get("name", e["tournament"]["name"]),
                                e["tournament"]["name"].upper())
    ri = e.get("roundInfo") or {}
    RONDAS = {"final": "FINAL", "semifinals": "SEMIFINALES", "semifinal": "SEMIFINAL", "quarterfinals": "CUARTOS DE FINAL",
              "round of 16": "OCTAVOS DE FINAL", "round of 32": "16AVOS DE FINAL", "playoff round": "REPECHAJE",
              "knockout round play-offs": "PLAYOFF", "qualification": "CLASIFICACIÓN", "group stage": "FASE DE GRUPOS"}
    ronda = ri.get("name") or ""
    ronda = RONDAS.get(ronda.lower(), ronda).upper() or (f"JORNADA {ri['round']}" if ri.get("round") else "")
    home, away = nombre_equipo(e["homeTeam"]), nombre_equipo(e["awayTeam"])
    hs, as_ = e.get("homeScore", {}).get("current"), e.get("awayScore", {}).get("current")
    # Valoración: promedio de las notas de todas las fuentes que la traen
    notas = {"sofascore": s.get("rating")}
    notas.update({f: d.get("nota") for f, d in datos.items() if d.get("nota")})
    rating = fuentes.promedio(notas.values())
    if not rating: avisos.append("No hay nota del jugador en este partido")
    elif len([v for v in notas.values() if v]) > 1:
        avisos.append("Nota = promedio de " + " · ".join(f"{f} {v:.2f}" for f, v in notas.items() if v) + f" → {rating:.2f}")
    # Datos fijos: se usa SofaScore; las diferencias con las otras fuentes van a los avisos
    comparar("minutos", minutos, {f: d.get("minutos") for f, d in datos.items()}, avisos)
    comparar("goles", goles, {f: d.get("goles") for f, d in datos.items()}, avisos)
    comparar("asistencias", n(s, "goalAssist"), {f: d.get("asistencias") for f, d in datos.items()}, avisos)
    comparar("rojas", roja, {f: d.get("rojas") for f, d in datos.items()}, avisos)
    comparar("resultado", f"{hs}-{as_}", {f: f"{int(d['goles_local'])}-{int(d['goles_visita'])}" for f, d in datos.items()
                                          if d.get("goles_local") is not None and d.get("goles_visita") is not None and fuentes.mismo_equipo(d.get("local"), e["homeTeam"]["name"])}, avisos)
    fm_pases = (datos.get("fotmob") or {}).get("stats", {}).get("accurate_passes")
    af_st = (datos.get("api_football") or {}).get("stats") or {}
    comparar("pases precisos", f"{n(s,'accuratePass')}/{n(s,'totalPass')}" if s.get("totalPass") else None,
             {"fotmob": f"{fm_pases[0]}/{fm_pases[1]}" if isinstance(fm_pases, (list, tuple)) else None,
              "api_football": f"{af_st['pases_precisos']}/{af_st['pases']}" if af_st.get("pases") else None}, avisos)
    # xG: si SofaScore no lo trae y otra fuente sí, se completa (dato fijo)
    pos_filas = filas_posicion(r, s)
    # Dónde jugó en el dibujo: enganche / volante por afuera de una línea de 4 -> todo; delantero o entre
    # los 4 más adelantados -> lo de ataque; mediocentro, volante o mixto -> lo de volante.
    linea_i = next((k for k, l in enumerate(ls) if any(p["player"]["id"] == pid for p in l)), None) if len(ls) > 1 else None
    enganche = linea_i is not None and len(ls) >= 5 and linea_i == len(ls) - 2
    por_afuera = False
    if linea_i is not None and 2 <= linea_i <= len(ls) - 2 and len(ls[linea_i]) == 4:
        lo = orden(ls[linea_i]); por_afuera = lo[0]["player"]["id"] == pid or lo[-1]["player"]["id"] == pid
    campo = [p for p in tit if (p.get("position") or p["player"].get("position")) != "G"]
    if all(avgx.get(p["player"]["id"]) is not None for p in campo) and campo:
        adelantados = [p["player"]["id"] for p in sorted(campo, key=lambda p: -avgx[p["player"]["id"]])[:4]]
    else:
        adelantados = [p["player"]["id"] for l in reversed(ls[1:] if len(ls) > 1 else []) for p in l][:4]
    todas = enganche or por_afuera
    con_ataque = todas or r == "delantero" or (titular and pid in adelantados)
    con_volante = todas or r in ("mediocentro", "banda") or j.get("mixto")
    pos_filas = armar_totales(pos_filas, filas_ataque(s) if con_ataque else [],
                              extras_volante(rb) if con_volante else {}, tarjetas)
    # el bloque de su franja suma lo mismo que TOTALES (remates, asistencias, último tercio) pero de esa franja
    tiros = None
    if con_ataque:
        try:
            tiros = get(f"/event/{e['id']}/shotmap/player/{pid}").get("shotmap", [])
        except Exception:
            tiros = None
    zona = por_zona(j.get("zona"), puntos, rb, tiros, s, con_ataque, con_volante) or zona
    if r == "delantero" and s.get("expectedGoals") is None:
        xg = (datos.get("understat") or {}).get("stats", {}).get("xg")
        if xg is None: xg = (datos.get("fotmob") or {}).get("stats", {}).get("expected_goals")
        if isinstance(xg, (int, float)) and len(pos_filas) < 10:
            pos_filas.append(["Goles esperados (xG)", f"{xg:.2f}".replace(".", ","), False])
    archivo = f"{apellido(player)}_{home.replace(' ', '')}-{away.replace(' ', '')}_{fecha}".replace("ñ", "n").replace("ú", "u").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o")
    esc_club = escudo(equipo["id"], recursos)
    if esc_club:  # copia para cuando haya que armarla con BeSoccer
        import shutil
        os.makedirs(os.path.join(AQUI, "escudos"), exist_ok=True)
        shutil.copy2(esc_club, os.path.join(AQUI, "escudos", ("uruguay" if equipo.get("national") else f"club_{clave}") + ".png"))
    d = {"archivo": archivo, "nombre": j["placa"], "apellido": apellido(player), "dorsal": dorsal,
         "local": home, "visita": away, "goles_local": hs, "goles_visita": as_,
         "escudo_local": escudo(e["homeTeam"]["id"], recursos), "escudo_visita": escudo(e["awayTeam"]["id"], recursos),
         "escudo_club": esc_club,
         "meta": " · ".join(x for x in [torneo, ronda, f"{fecha.day} {MESES[fecha.month-1]} {fecha.year}"] if x),
         "condicion": "TITULAR" if titular else "SUPLENTE",
         "minutos": f"{minutos}’", "nota": f"{rating:.1f}" if rating else None, "estrellas": estrellas(rating),
         "tema": tema(cam, equipo), "formacion": form, "once": once,
         "cara": mi_cara, "foto": os.path.join(salida, fig) if fig else None,
         "sustitucion": ({"minuto": sustitucion["minuto"], "por": sustitucion["por"], "apellido": apellido(player), "cara": mi_cara,
                          "rol": pos_titulo.replace("COMO ", "").lower()} if sustitucion else None),
         "generales": generales, "pos_titulo": pos_titulo, "posicion": pos_filas,
         "extra": {"titulo": "TEMPORADA", "sub": str(year) if year else "", "filas": filas_t},
         "heat_img": mapa, "heat_horizontal": True, "zona": zona, "perfil": perfil, "notas_por_fuente": notas, "amarillas_hero": amar,
         "roja": (min_roja or True) if roja else None}
    jp = os.path.join(salida, archivo + ".json")
    json.dump([d], open(jp, "w"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(AQUI, "render_v3.py"), jp], check=True)

    linea = []
    if goles: linea.append(f"{goles} gol" + ("es" if goles > 1 else ""))
    if n(s, "goalAssist"): linea.append(f"{n(s,'goalAssist')} asistencia" + ("s" if n(s, "goalAssist") > 1 else ""))
    if s.get("totalPass"): linea.append(f"{n(s,'accuratePass')}/{n(s,'totalPass')} pases")
    if n(s, "duelWon"): linea.append(f"{n(s,'duelWon')} duelo" + ("s" if n(s, "duelWon") > 1 else "") + " ganado" + ("s" if n(s, "duelWon") > 1 else ""))
    if n(s, "ballRecovery"): linea.append(f"{n(s,'ballRecovery')} recuperaci" + ("ones" if n(s, "ballRecovery") > 1 else "ón"))
    club_tag = "".join(ch for ch in (equipo["name"] if not equipo.get("national") else "Uruguay") if ch.isalnum())
    copy = (f"🇺🇾 {j['placa']} · {home} {hs}-{as_} {away}\n"
            f"⏱ {minutos}' · ⭐ {rating:.1f}\n" if rating else f"🇺🇾 {j['placa']} · {home} {hs}-{as_} {away}\n⏱ {minutos}'\n")
    if roja:
        copy += "🟥 Expulsado" + (f" al {min_roja.replace('’', chr(39))}" if isinstance(min_roja, str) else "") + "\n"
    if sustitucion:
        copy += f"🔁 Entró al {sustitucion['minuto'].replace('’', chr(39))} por {sustitucion['por']}, como {pos_titulo.replace('COMO ', '').lower()}\n"
    copy += (" · ".join(linea) + "\n" if linea else "") + f"#CelestesPorElMundo #Uruguay #{club_tag}\n"
    open(os.path.join(salida, archivo + "_copy.txt"), "w").write(copy)
    return {"estado": "jugó", "titular": titular, "minutos": minutos, "nota": rating, "rol": pos_titulo, "notas_por_fuente": notas,
            "archivo": archivo, "png": archivo + ".png", "mapa": mapa, "figura": fig, "avisos": avisos,
            "entro": ({"minuto": sustitucion["minuto"], "por": sustitucion["por"]} if sustitucion else None),
            "roja": (min_roja or True) if roja else None}

def main():
    a = sys.argv[1:]
    def opt(k, dflt=None):
        return a[a.index(k) + 1] if k in a else dflt
    jugs = json.load(open(a[0]))
    salida = os.path.abspath(opt("--salida", "salida_hoy")); os.makedirs(salida, exist_ok=True)
    proc_path = opt("--procesados"); procesados = set(json.load(open(proc_path))) if proc_path and os.path.exists(proc_path) else set()
    hoy = datetime.datetime.now(TZ).date()
    if opt("--fecha"):
        fechas = {datetime.date.fromisoformat(opt("--fecha"))}
    else:
        fechas = {hoy - datetime.timedelta(days=i) for i in range(int(opt("--dias", "2")))}
    plantilla_fig = os.path.join(AQUI, "fotos", "bernal_espalda_ancho.svg")
    respaldos = []
    resumen = {"revisado": datetime.datetime.now(TZ).isoformat(timespec="minutes"), "fechas": sorted(str(f) for f in fechas), "jugadores": []}
    for j in jugs:
        if opt("--clave") and j["clave"] != opt("--clave"): continue
        evs, err = [], None
        for page in (0, 1):
            try: evs += get(f"/player/{j['sofascore_id']}/events/last/{page}").get("events", [])
            except Exception as ex:
                if page == 0: err = repr(ex)
                break
        if err:
            # Si SofaScore no responde se avisa como error (nunca como "sin partido") y se prueba el respaldo
            # automático con las otras fuentes al final (respaldo_auto.py).
            resumen["jugadores"].append({"clave": j["clave"], "nombre": j["placa"],
                                         "partidos": [{"estado": "error", "partido": "(no se pudo consultar SofaScore)", "error": err}]})
            respaldos.append(j)
            continue
        try: evs += get(f"/player/{j['sofascore_id']}/events/next/0").get("events", [])
        except Exception: pass
        vistos, partidos = set(), []
        # Otras fuentes: solo si hay algún partido terminado de este jugador en las fechas (ahorra pedidos)
        extra = None
        if any(fecha_local(e) in fechas and e["status"]["type"] == "finished" for e in evs):
            extra = fuentes.consultar(j, fechas)
        for e in evs:
            if e["id"] in vistos or fecha_local(e) not in fechas: continue
            vistos.add(e["id"])
            info = {"partido": f"{nombre_equipo(e['homeTeam'])} {e.get('homeScore',{}).get('current','')}-{e.get('awayScore',{}).get('current','')} {nombre_equipo(e['awayTeam'])}",
                    "torneo": e["tournament"]["name"], "fecha": str(fecha_local(e)), "evento": e["id"]}
            tipo = e["status"]["type"]
            if tipo != "finished":
                info["estado"] = "no terminó" if tipo == "inprogress" else ("no empezó" if tipo == "notstarted" else tipo)
            elif (f"{j['clave']}_{e['id']}" in procesados or f"{j['clave']}_{fecha_local(e)}" in procesados) and "--forzar" not in a:
                info["estado"] = "ya procesado"
            else:
                try:
                    info.update(armar_partido(j, e, salida, plantilla_fig, extra))
                    if extra and extra.get("estado"): info["fuentes"] = extra["estado"]
                    procesados.add(f"{j['clave']}_{e['id']}")
                    if info.get("estado") == "jugó": procesados.add(f"{j['clave']}_{fecha_local(e)}")
                except Exception as ex:
                    info["estado"] = "error"; info["error"] = repr(ex)
            partidos.append(info)
        resumen["jugadores"].append({"clave": j["clave"], "nombre": j["placa"], "partidos": partidos or [{"estado": "sin partido en esas fechas"}]})
    if proc_path:
        json.dump(sorted(procesados), open(proc_path, "w"), indent=1)
    json.dump(resumen, open(os.path.join(salida, "resumen.json"), "w"), ensure_ascii=False, indent=1)
    # Respaldo automático para los jugadores en los que SofaScore no respondió
    for j in respaldos:
        try:
            import respaldo_auto
            respaldo_auto.armar(j, fechas, salida, proc_path)
            resumen = json.load(open(os.path.join(salida, "resumen.json")))
        except Exception as ex:
            print(f"respaldo automático de {j['clave']} falló: {ex!r}")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
