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
from mapa_sofascore import get, dibujar
from figura import figura

TZ = ZoneInfo("America/Montevideo")
MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
COPAS_EUROPEAS = {7: "CHAMPIONS LEAGUE", 679: "EUROPA LEAGUE", 17015: "CONFERENCE LEAGUE"}
NOMBRES_TORNEO = {"LaLiga": "LALIGA", "UEFA Champions League": "CHAMPIONS LEAGUE", "UEFA Europa League": "EUROPA LEAGUE",
                  "UEFA Europa Conference League": "CONFERENCE LEAGUE", "UEFA Conference League": "CONFERENCE LEAGUE",
                  "Liga Portugal Betclic": "LIGA PORTUGAL", "Liga Portugal": "LIGA PORTUGAL",
                  "International Friendly Games": "AMISTOSO INTERNACIONAL", "Copa del Rey": "COPA DEL REY"}
PAISES = {"Uruguay": "Uruguay", "Japan": "Japón", "South Korea": "Corea del Sur", "India": "India", "Brazil": "Brasil",
          "Argentina": "Argentina", "Spain": "España", "Portugal": "Portugal", "France": "Francia", "Germany": "Alemania",
          "England": "Inglaterra", "Italy": "Italia", "United States": "Estados Unidos", "Mexico": "México",
          "Colombia": "Colombia", "Chile": "Chile", "Paraguay": "Paraguay", "Peru": "Perú", "Ecuador": "Ecuador",
          "Bolivia": "Bolivia", "Venezuela": "Venezuela", "Morocco": "Marruecos", "Netherlands": "Países Bajos"}

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
    opt("Distancia recorrida", "kilometersCovered", lambda v: f"{v:.2f} km".replace(".", ","))
    opt("Sprints", "numberOfSprints", lambda v: str(v))
    opt("Velocidad máxima", "topSpeed", lambda v: f"{v:.1f} km/h".replace(".", ","), True)
    return f[:10]

def temporada(pid, team_id, year):
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
    orden = sorted(ts, key=lambda t: (t["uniqueTournament"]["id"] != liga_id, t["uniqueTournament"]["id"] not in COPAS_EUROPEAS))
    for t in orden:
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
        filas += [[f"<b>{nom}</b>", " ", False],
                  ["Partidos (titular)", f"{n(S,'appearances')} ({n(S,'matchesStarted')})", False],
                  ["Minutos", str(n(S, "minutesPlayed")), False]]
        if S.get("rating"): filas.append(["Nota media", f"{S['rating']:.2f}", True])
        filas.append(["Goles · Asist. · Amar.", f"{n(S,'goals')} · {n(S,'assists')} · {n(S,'yellowCards')}", False])
    return filas[:10], avisos

def club_de(jug, player):
    """Equipo del club del jugador según SofaScore (para la temporada)."""
    t = player.get("team") or {}
    return t.get("id")

def armar_partido(j, e, salida, plantilla_fig):
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

    # Posiciones medias (para ordenar la cancha y saber si jugó de lateral o de central)
    try:
        avg = {p["player"]["id"]: p.get("averageY") for p in get(f"/event/{e['id']}/average-positions").get(lado, [])}
    except Exception:
        avg = {}
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
        dibujar(puntos, os.path.join(salida, mapa))
        json.dump({"fuente": "SofaScore", "credito": "Datos: SofaScore", "evento": e["id"], "toques": len(puntos)},
                  open(os.path.join(salida, mapa[:-4] + ".json"), "w"))
    else:
        avisos.append("SofaScore no tiene mapa de calor de este partido: se muestra el perfil")

    r, pos_titulo = rol(yo.get("position") or yo["player"].get("position"), y_med)

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
    once = [[[p.get("jerseyNumber") or p.get("shirtNumber") or "", corto(p["player"])] for p in orden(l)] for l in ls]
    dorsal = str(yo.get("jerseyNumber") or yo.get("shirtNumber") or yo["player"].get("jerseyNumber") or "")
    if not titular:
        avisos.append("Entró de suplente: no aparece en la cancha del once inicial")
    if minutos < 20:
        avisos.append(f"Jugó solo {minutos} minutos: hay pocos datos, revisar si vale la pena publicarla")

    # Incidencias: goles y tarjetas del jugador
    goles, amar, roja = 0, 0, 0
    try:
        for i in get(f"/event/{e['id']}/incidents").get("incidents", []):
            if (i.get("player") or {}).get("id") != pid: continue
            if i.get("incidentType") == "goal" and i.get("incidentClass") != "ownGoal": goles += 1
            if i.get("incidentType") == "card":
                if i.get("incidentClass") == "yellow": amar += 1
                elif i.get("incidentClass") in ("red", "yellowRed"): roja += 1
    except Exception:
        goles = n(s, "goals"); avisos.append("Sin incidencias: goles de las estadísticas y tarjetas sin confirmar")
    tarjetas = "0" if not (amar or roja) else " + ".join(x for x in [f"{amar} amarilla" + ("s" if amar > 1 else "") if amar else "", "roja" if roja else ""] if x)

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
    filas_t, av = temporada(pid, club_id, year) if (club_id and year and not equipo.get("national")) else ([], [])
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
    if not filas_t:
        filas_t = [["Sin datos de temporada", " ", False]]; avisos.append("Sin temporada por competición")
    cams = j.get("camiseta", {})
    cam = (cams.get("7") if equipo.get("national") else next((v for k, v in cams.items() if k != "7"), None)) or next(iter(cams.values()))
    os.makedirs(os.path.join(salida, "fotos"), exist_ok=True)
    fig = f"fotos/{clave}_{fecha}.svg"
    open(os.path.join(salida, fig), "w").write(figura(plantilla_fig, apellido(player), dorsal, cam))

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
    ronda = (ri.get("name") or "").upper() or (f"JORNADA {ri['round']}" if ri.get("round") else "")
    home, away = nombre_equipo(e["homeTeam"]), nombre_equipo(e["awayTeam"])
    hs, as_ = e.get("homeScore", {}).get("current"), e.get("awayScore", {}).get("current")
    rating = s.get("rating")
    if not rating: avisos.append("SofaScore no tiene nota del jugador en este partido")
    archivo = f"{apellido(player)}_{home.replace(' ', '')}-{away.replace(' ', '')}_{fecha}".replace("ñ", "n").replace("ú", "u").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o")
    d = {"archivo": archivo, "nombre": j["placa"], "marcador": f"{home.upper()} {hs} — {as_} {away.upper()}",
         "meta": " · ".join(x for x in [torneo, ronda, f"{fecha.day} {MESES[fecha.month-1]} {fecha.year}", "TITULAR" if titular else "SUPLENTE"] if x),
         "minutos": f"{minutos}’", "nota": f"{rating:.1f}" if rating else None, "nota_label": "NOTA SOFASCORE",
         "formacion": form, "once": once, "jugador_dorsal": dorsal if titular else "__",
         "generales": generales, "pos_titulo": pos_titulo, "mediocentro": filas_posicion(r, s),
         "extra": {"titulo": "TEMPORADA", "sub": f"{year} · SofaScore" if year else "SofaScore", "filas": filas_t},
         "heat": None, "heat_img": mapa, "heat_credito": "Datos: SofaScore" if mapa else "", "perfil": perfil,
         "foto": fig, "credito_foto": "", "muestra": [],
         "fuente": "Partido, temporada y mapa de calor: SofaScore · Figura ilustrativa, no es una foto del jugador"}
    jp = os.path.join(salida, archivo + ".json")
    json.dump([d], open(jp, "w"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(AQUI, "render_v2.py"), jp], check=True)

    linea = []
    if goles: linea.append(f"{goles} gol" + ("es" if goles > 1 else ""))
    if n(s, "goalAssist"): linea.append(f"{n(s,'goalAssist')} asistencia" + ("s" if n(s, "goalAssist") > 1 else ""))
    if s.get("totalPass"): linea.append(f"{n(s,'accuratePass')}/{n(s,'totalPass')} pases")
    if n(s, "duelWon"): linea.append(f"{n(s,'duelWon')} duelo" + ("s" if n(s, "duelWon") > 1 else "") + " ganado" + ("s" if n(s, "duelWon") > 1 else ""))
    if n(s, "ballRecovery"): linea.append(f"{n(s,'ballRecovery')} recuperaci" + ("ones" if n(s, "ballRecovery") > 1 else "ón"))
    club_tag = "".join(ch for ch in (equipo["name"] if not equipo.get("national") else "Uruguay") if ch.isalnum())
    copy = (f"🇺🇾 {j['placa']} · {home} {hs}-{as_} {away}\n"
            f"⏱ {minutos}' · ⭐ {rating:.1f} (SofaScore)\n" if rating else f"🇺🇾 {j['placa']} · {home} {hs}-{as_} {away}\n⏱ {minutos}'\n")
    copy += (" · ".join(linea) + "\n" if linea else "") + f"#CelestesPorElMundo #Uruguay #{club_tag}\n"
    open(os.path.join(salida, archivo + "_copy.txt"), "w").write(copy)
    return {"estado": "jugó", "titular": titular, "minutos": minutos, "nota": rating, "rol": pos_titulo,
            "archivo": archivo, "png": archivo + ".png", "mapa": mapa, "figura": fig, "avisos": avisos}

def main():
    a = sys.argv[1:]
    def opt(k, dflt=None):
        return a[a.index(k) + 1] if k in a else dflt
    jugs = json.load(open(a[0]))
    salida = opt("--salida", "salida_hoy"); os.makedirs(salida, exist_ok=True)
    proc_path = opt("--procesados"); procesados = set(json.load(open(proc_path))) if proc_path and os.path.exists(proc_path) else set()
    hoy = datetime.datetime.now(TZ).date()
    if opt("--fecha"):
        fechas = {datetime.date.fromisoformat(opt("--fecha"))}
    else:
        fechas = {hoy - datetime.timedelta(days=i) for i in range(int(opt("--dias", "2")))}
    plantilla_fig = os.path.join(AQUI, "fotos", "bernal_espalda_ancho.svg")
    resumen = {"revisado": datetime.datetime.now(TZ).isoformat(timespec="minutes"), "fechas": sorted(str(f) for f in fechas), "jugadores": []}
    for j in jugs:
        if opt("--clave") and j["clave"] != opt("--clave"): continue
        evs = []
        for page in (0, 1):
            try: evs += get(f"/player/{j['sofascore_id']}/events/last/{page}").get("events", [])
            except Exception: break
        try: evs += get(f"/player/{j['sofascore_id']}/events/next/0").get("events", [])
        except Exception: pass
        vistos, partidos = set(), []
        for e in evs:
            if e["id"] in vistos or fecha_local(e) not in fechas: continue
            vistos.add(e["id"])
            info = {"partido": f"{nombre_equipo(e['homeTeam'])} {e.get('homeScore',{}).get('current','')}-{e.get('awayScore',{}).get('current','')} {nombre_equipo(e['awayTeam'])}",
                    "torneo": e["tournament"]["name"], "fecha": str(fecha_local(e)), "evento": e["id"]}
            tipo = e["status"]["type"]
            if tipo != "finished":
                info["estado"] = "no terminó" if tipo == "inprogress" else ("no empezó" if tipo == "notstarted" else tipo)
            elif f"{j['clave']}_{e['id']}" in procesados and "--forzar" not in a:
                info["estado"] = "ya procesado"
            else:
                try:
                    info.update(armar_partido(j, e, salida, plantilla_fig))
                    procesados.add(f"{j['clave']}_{e['id']}")
                except Exception as ex:
                    info["estado"] = "error"; info["error"] = repr(ex)
            partidos.append(info)
        resumen["jugadores"].append({"clave": j["clave"], "nombre": j["placa"], "partidos": partidos or [{"estado": "sin partido en esas fechas"}]})
    if proc_path:
        json.dump(sorted(procesados), open(proc_path, "w"), indent=1)
    json.dump(resumen, open(os.path.join(salida, "resumen.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
