"""Fuentes de datos extra (además de SofaScore) para las infografías de "Celestes por el mundo".

Fuentes: FotMob, API-Football, football-data.org, TheSportsDB, Understat y zerozero.
Ninguna se nombra en la infografía ni en el texto del posteo.

Reglas:
- Nunca se inventa ni se estima un dato: si una fuente no responde o no trae algo, no se usa.
- Datos fijos (resultado, minutos, goles, pases, tarjetas...): se usa el de la fuente principal y,
  si falta, el de otra fuente. Las diferencias entre fuentes quedan en los avisos.
- Valoraciones (nota del partido, nota media de la temporada y, con ellas, las estrellas):
  promedio de todas las fuentes que traen nota (SofaScore, FotMob, API-Football).
- API-Football: nunca más de 100 pedidos por día (UTC). El contador vive en automatizacion/cuotas.json,
  que se sube al repositorio con cada revisión. Tope interno: LIMITE_API_FOOTBALL.
- football-data.org: nunca más de 10 pedidos por minuto (se espera lo necesario entre pedidos).

Claves: API-Football y football-data.org piden clave. Se leen de las variables de entorno
API_FOOTBALL_KEY y FOOTBALL_DATA_KEY o las agrega el proxy de la nube (secreto de red del entorno).
TheSportsDB usa THESPORTSDB_KEY o la clave pública gratuita "123".
"""
import json, os, re, time, html, gzip, datetime, urllib.request, urllib.error, urllib.parse, unicodedata
from collections import deque

AQUI = os.path.dirname(os.path.abspath(__file__))
CUOTAS = os.path.join(AQUI, "cuotas.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
LIMITE_API_FOOTBALL = 100          # pedidos por día UTC: nunca más que esto
LIMITE_FOOTBALL_DATA_MIN = 10      # pedidos por minuto


# ----------------------------------------------------------------- utilidades
def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", t).strip()


def mismo_nombre(a, b):
    """True si los nombres coinciden (apellido o nombre completo, sin tildes)."""
    a, b = norm(a), norm(b)
    if not a or not b: return False
    if a == b or a in b or b in a: return True
    return a.split()[-1] == b.split()[-1] and a.split()[0][0] == b.split()[0][0]


def mismo_equipo(a, b):
    a, b = norm(a).replace(" fc", "").replace("fc ", ""), norm(b).replace(" fc", "").replace("fc ", "")
    return bool(a and b) and (a == b or a in b or b in a)


def http(url, headers=None, timeout=25, crudo=False):
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        crudo_b = r.read()
        if r.headers.get("Content-Encoding", "").lower() == "gzip" or crudo_b[:2] == b"\x1f\x8b":
            crudo_b = gzip.decompress(crudo_b)  # Understat manda gzip aunque no se pida
        cuerpo = crudo_b.decode("utf-8", "replace")
        if crudo:
            return cuerpo, dict(r.headers)
        return json.loads(cuerpo)


def fnum(v):
    try:
        return float(v) if v not in (None, "", "-") else None
    except (TypeError, ValueError):
        return None


def promedio(valores):
    v = [x for x in valores if x is not None and x > 0]
    return round(sum(v) / len(v), 2) if v else None


# ----------------------------------------------------------------- cuotas
def _cuotas():
    try:
        return json.load(open(CUOTAS))
    except Exception:
        return {}


def _usar(fuente, limite):
    """Suma un pedido al contador del día (UTC). Devuelve False si ya se llegó al límite."""
    c = _cuotas()
    hoy = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    e = c.get(fuente) or {}
    if e.get("fecha_utc") != hoy:
        e = {"fecha_utc": hoy, "usados": 0}
    if e["usados"] >= limite:
        return False
    e["usados"] += 1
    c[fuente] = e
    json.dump(c, open(CUOTAS, "w"), indent=1)
    return True


def _agotar(fuente):
    c = _cuotas(); hoy = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    c[fuente] = {"fecha_utc": hoy, "usados": LIMITE_API_FOOTBALL}
    json.dump(c, open(CUOTAS, "w"), indent=1)


class SinCuota(Exception):
    pass


class SinPlan(Exception):
    """El plan de la API no cubre lo pedido (p. ej. el plan gratis de API-Football no trae la temporada actual)."""
    pass


_AF_SIN_PLAN = None  # si el plan no cubre la temporada, no se gastan más pedidos en esta corrida


# ----------------------------------------------------------------- FotMob
FM = "https://www.fotmob.com/api/data"


def _tipo_remate(t):
    """Tipo de un remate de FotMob para marcarlo en el mapa: gol / bloqueado / al_arco / afuera (incluye palo)."""
    if t.get("eventType") == "Goal" and not t.get("isOwnGoal"):
        return "gol"
    if t.get("isBlocked"):
        return "bloqueado"
    return "al_arco" if t.get("isOnTarget") else "afuera"


def fotmob(j, fechas):
    """Partidos del jugador en `fechas` (date) según FotMob. Devuelve lista de dicts normalizados."""
    pid = j.get("fotmob_id")
    if not pid:
        return [], "sin fotmob_id en jugadores.json"
    pd = http(f"{FM}/playerData?id={pid}")
    out = []
    for m in pd.get("recentMatches") or []:
        utc = (m.get("matchDate") or {}).get("utcTime")
        if not utc: continue
        f = datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(_TZ()).date()
        if f not in fechas: continue
        r = {"fuente": "fotmob", "fecha": str(f), "partido_id": m.get("id"),
             "local": m["teamName"] if m.get("isHomeTeam") else m.get("opponentTeamName"),
             "visita": m.get("opponentTeamName") if m.get("isHomeTeam") else m["teamName"],
             "goles_local": m.get("homeScore"), "goles_visita": m.get("awayScore"), "torneo": m.get("leagueName"),
             "minutos": m.get("minutesPlayed"), "jugo": bool(m.get("playedInMatch")), "banco": bool(m.get("onBench")),
             "nota": fnum((m.get("ratingProps") or {}).get("rating")), "goles": m.get("goals"), "asistencias": m.get("assists"),
             "amarillas": m.get("yellowCards"), "rojas": m.get("redCards"), "notas_once": {}, "stats": {}}
        try:
            md = http(f"{FM}/matchDetails?matchId={m['id']}")
            c = md.get("content") or {}
            hdr = md.get("header") or {}
            r["terminado"] = bool((hdr.get("status") or {}).get("finished"))
            lado = "homeTeam" if m.get("isHomeTeam") else "awayTeam"
            eq = (c.get("lineup") or {}).get(lado) or {}
            r["formacion"] = eq.get("formation")
            r["ronda"] = (md.get("general") or {}).get("matchRound")
            titulares = eq.get("starters") or []
            for p in titulares + (eq.get("subs") or []):
                nt = fnum((p.get("performance") or {}).get("rating"))
                if p.get("shirtNumber") and nt:
                    r["notas_once"][str(p["shirtNumber"])] = nt
                if str(p.get("id")) == str(pid):
                    r["dorsal"] = str(p.get("shirtNumber") or "")
                    r["titular"] = p in titulares
                    r["posicion_id"] = p.get("positionId")
            r["rival_id"] = m.get("opponentTeamId")
            r["liga_id"] = m.get("leagueId")
            # ubicación de cada titular en el dibujo: verticalLayout x (0 = costado derecho del equipo, 1 = izquierdo)
            r["dibujo"] = {str(p.get("id")): {"pos": p.get("positionId"), "x": (p.get("verticalLayout") or {}).get("x"),
                                              "y": (p.get("verticalLayout") or {}).get("y")} for p in titulares}
            # once por líneas (del arco al ataque, de izquierda a derecha como se ve en la cancha)
            filas = {}
            for p in titulares:
                vl = p.get("verticalLayout") or {}
                if vl.get("y") is None: filas = {}; break
                filas.setdefault(round(vl["y"], 2), []).append(p)
            r["once"] = [[[str(p.get("shirtNumber") or ""), p.get("lastName") or p.get("name"), p.get("id")]
                          for p in sorted(filas[y], key=lambda q: -(q.get("verticalLayout") or {}).get("x", 0))]
                         for y in sorted(filas)] if filas else []
            # tarjetas de cada jugador (para la cancha) y, si entró, minuto y a quién reemplazó
            r["tarjetas"] = {}
            for ev in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []:
                if ev.get("type") == "Card" and (ev.get("player") or {}).get("id"):
                    t = r["tarjetas"].setdefault(str(ev["player"]["id"]), {"amarillas": 0, "roja": None})
                    mi = f"{ev.get('time')}+{ev['overloadTime']}’" if ev.get("overloadTime") else f"{ev.get('time')}’"
                    if ev.get("card") == "Yellow": t["amarillas"] += 1
                    elif ev.get("card") in ("Red", "YellowRed"): t["roja"] = mi
                sw = ev.get("swap") or []
                if ev.get("type") == "Substitution" and len(sw) == 2 and str(sw[0].get("id")) == str(pid):
                    ot = ev.get("overloadTime")
                    r["entro"] = {"minuto": f"{ev.get('time')}+{ot}" if ot else ev.get("time"),
                                  "por": (sw[1].get("name") or "").split(" ")[-1], "por_id": sw[1].get("id")}
            ps = (c.get("playerStats") or {}).get(str(pid)) or {}
            r["puesto_habitual"] = ps.get("usualPosition")      # 0 arquero, 1 defensor, 2 volante, 3 delantero
            r["remates"] = ps.get("shotmap")                     # cada remate con x (0-105, ataca a la derecha) e y (0-68)
            # remates en la escala del mapa de calor (abajo). Su y viene al revés que la del mapa de calor
            # (comprobado con 5 partidos y más de 80 jugadores): y = y_remate / 68 * 100.
            r["remates_mapa"] = [{"x": round(t["x"] / 105 * 100, 2), "y": round(t["y"] / 68 * 100, 2), "tipo": _tipo_remate(t)}
                                 for t in r["remates"] or [] if t.get("x") is not None and t.get("y") is not None]
            # mapa de calor del partido: círculos en una cancha de 105 x 68 que ataca a la derecha, con el costado
            # derecho del equipo ABAJO (y alto). Se pasa a la escala de SofaScore: x 0-100 hacia el arco rival,
            # y 0-100 con 0 = costado derecho del equipo.
            r["calor"] = None
            if c.get("heatmapUrl") and ps.get("optaId"):
                try:
                    hm = http("https://www.fotmob.com" + c["heatmapUrl"])
                    circ = ((hm.get("players") or {}).get(f"p{ps['optaId']}") or "")
                    pts = re.findall(r'cx="([\d.]+)" cy="([\d.]+)"', circ)
                    r["calor"] = [{"x": round(float(a) / 105 * 100, 2), "y": round(100 - float(b) / 68 * 100, 2)} for a, b in pts]
                except Exception as ex:
                    r["aviso_calor"] = f"sin mapa de calor ({type(ex).__name__})"
            for bloque in ps.get("stats") or []:
                for _, v in (bloque.get("stats") or {}).items():
                    k, s = v.get("key"), v.get("stat") or {}
                    if k and "value" in s:
                        r["stats"][k] = (s["value"], s.get("total")) if s.get("type") == "fractionWithPercentage" else s["value"]
            nota_fina = r["stats"].get("rating_title")
            if isinstance(nota_fina, (int, float)):
                r["nota"] = round(float(nota_fina), 2)
        except Exception as ex:
            r["aviso"] = f"sin detalle del partido ({ex!r})"
        out.append(r)
    # temporada: nota media de la liga principal
    ml = pd.get("mainLeague") or {}
    temp = {}
    if ml.get("leagueName"):
        st = {x.get("localizedTitleId") or x.get("title"): x.get("value") for x in ml.get("stats") or []}
        temp[ml["leagueName"]] = {"nota": fnum(st.get("rating")), "pj": st.get("matches_uppercase"), "tit": st.get("started"),
                                  "min": st.get("minutes_played"), "goles": st.get("goals"), "asist": st.get("assists"),
                                  "amarillas": st.get("yellow_cards"), "rojas": st.get("red_cards"), "season": ml.get("season")}
    # copas internacionales de la temporada (Champions, Europa, Conference, Libertadores, Sudamericana)
    copas = {}
    torneos = ((pd.get("statSeasons") or [{}])[0] or {}).get("tournaments") or []
    for t in torneos:
        nm = norm(t.get("name") or "")
        if not any(k in nm for k in ("champions league", "europa league", "conference league", "libertadores", "sudamericana")):
            continue
        if "concacaf" in nm or "afc" in nm.split() or "caf" in nm.split(): continue
        try:
            x = http(f"{FM}/playerStats?playerId={pid}&seasonId={t['entryId']}&isFirstSeason=false")
        except Exception:
            continue
        v = {i.get("localizedTitleId"): i.get("statValue") for i in ((x.get("topStatCard") or {}).get("items") or [])}
        for sec in ((x.get("statsSection") or {}).get("items") or []):
            for i in sec.get("items") or []:
                v.setdefault(i.get("localizedTitleId"), i.get("statValue"))
        ent = lambda k: int(float(v[k])) if v.get(k) not in (None, "") else None
        copas[t["name"]] = {"nota": fnum(v.get("rating")), "pj": ent("matches_uppercase"), "tit": ent("player_started_matches"),
                            "min": ent("minutes_played"), "goles": ent("goals"), "asist": ent("assists"),
                            "amarillas": ent("yellow_cards"), "rojas": ent("red_cards"),
                            "season": ((pd.get("statSeasons") or [{}])[0] or {}).get("seasonName"), "liga_id": t.get("tournamentId"), "copa": True}
    for r in out:
        r["temporada"] = temp
        r["copas"] = copas
    return out, None


def _TZ():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/Montevideo")


# ----------------------------------------------------------------- API-Football
AF = "https://v3.football.api-sports.io"


def _af(path):
    global _AF_SIN_PLAN
    if _AF_SIN_PLAN:
        raise SinPlan(_AF_SIN_PLAN)
    if not _usar("api_football", LIMITE_API_FOOTBALL):
        raise SinCuota("API-Football: ya se usaron los 100 pedidos de hoy")
    h = {"Accept": "application/json"}
    if os.environ.get("API_FOOTBALL_KEY"):
        h["x-apisports-key"] = os.environ["API_FOOTBALL_KEY"]
    cuerpo, cab = http(AF + path, h, crudo=True)
    d = json.loads(cuerpo)
    rest = {k.lower(): v for k, v in cab.items()}.get("x-ratelimit-requests-remaining")
    if rest is not None and str(rest).isdigit() and int(rest) <= 0:
        _agotar("api_football")
    err = d.get("errors")
    if err:
        msg = "; ".join(f"{k}: {v}" for k, v in err.items()) if isinstance(err, dict) else str(err)
        if "token" in str(err).lower() or "key" in str(err).lower():
            raise RuntimeError("API-Football: falta la clave (secreto de red o API_FOOTBALL_KEY)")
        if "request" in msg.lower() and "limit" in msg.lower():
            _agotar("api_football")
        if "free plans do not have access" in msg.lower():
            _AF_SIN_PLAN = "el plan gratis de API-Football no cubre esta temporada (" + msg + ")"
            raise SinPlan(_AF_SIN_PLAN)
        raise RuntimeError("API-Football: " + msg)
    return d.get("response") or []


def _guardar_id(clave, campo, valor):
    """Guarda en jugadores.json un ID encontrado solo (así no se vuelve a gastar un pedido en buscarlo)."""
    ruta = os.path.join(AQUI, "jugadores.json")
    J = json.load(open(ruta))
    for x in J:
        if x["clave"] == clave and not x.get(campo):
            x[campo] = valor
    json.dump(J, open(ruta, "w"), ensure_ascii=False, indent=1)


def api_football(j, fechas, equipo_af=None):
    eq = equipo_af or j.get("apifootball_equipo")
    if not eq and j.get("club"):
        # se busca una sola vez (1 pedido) y queda guardado
        for t in _af(f"/teams?search={urllib.parse.quote(j['club'].split(' de ')[0])}"):
            if mismo_equipo(t["team"]["name"], j["club"]) or mismo_equipo(t["team"]["name"], j["club"].split(" de ")[0]):
                eq = t["team"]["id"]; _guardar_id(j["clave"], "apifootball_equipo", eq); j["apifootball_equipo"] = eq; break
    if not eq:
        return [], "sin apifootball_equipo en jugadores.json"
    # El plan gratis no deja usar last=N: se piden los partidos entre las fechas, por temporada (1 pedido por temporada).
    # Temporada = año en que empieza: en Europa la de agosto a mayo; en enero-junio también la del año (ligas de año calendario).
    desde, hasta = min(fechas), max(fechas)
    fx, vistos = [], set()
    for temporada in sorted({f.year if f.month >= 7 else f.year - 1 for f in fechas} | {f.year for f in fechas}):
        for f in _af(f"/fixtures?team={eq}&season={temporada}&from={desde}&to={hasta}&timezone=America/Montevideo"):
            if f["fixture"]["id"] not in vistos:
                vistos.add(f["fixture"]["id"]); fx.append(f)
    out = []
    for f in fx:
        fecha = datetime.date.fromisoformat(f["fixture"]["date"][:10])
        if fecha not in fechas: continue
        st = (f["fixture"].get("status") or {}).get("short")
        r = {"fuente": "api_football", "fecha": str(fecha), "partido_id": f["fixture"]["id"],
             "local": f["teams"]["home"]["name"], "visita": f["teams"]["away"]["name"],
             "goles_local": f["goals"]["home"], "goles_visita": f["goals"]["away"], "torneo": f["league"]["name"],
             "ronda": f["league"].get("round"), "terminado": st in ("FT", "AET", "PEN"), "notas_once": {}, "stats": {}}
        if not r["terminado"]:
            out.append(r); continue
        for t in _af(f"/fixtures/players?fixture={f['fixture']['id']}&team={eq}"):
            for p in t.get("players") or []:
                s = (p.get("statistics") or [{}])[0]
                g = s.get("games") or {}
                nt = fnum(g.get("rating"))
                if g.get("number") and nt:
                    r["notas_once"][str(g["number"])] = nt
                yo = (j.get("apifootball_id") and p["player"]["id"] == j["apifootball_id"]) or \
                     (not j.get("apifootball_id") and mismo_nombre(p["player"]["name"], j["placa"]))
                if not yo: continue
                r.update({"dorsal": str(g.get("number") or ""), "minutos": g.get("minutes"), "titular": not g.get("substitute"),
                          "jugo": bool(g.get("minutes")), "nota": nt, "goles": (s.get("goals") or {}).get("total"),
                          "asistencias": (s.get("goals") or {}).get("assists"), "amarillas": (s.get("cards") or {}).get("yellow"),
                          "rojas": (s.get("cards") or {}).get("red")})
                pa = s.get("passes") or {}
                du = s.get("duels") or {}
                ta = s.get("tackles") or {}
                r["stats"] = {"pases": pa.get("total"), "pases_precisos": pa.get("accuracy"), "pases_clave": pa.get("key"),
                              "duelos": du.get("total"), "duelos_ganados": du.get("won"), "entradas": ta.get("total"),
                              "intercepciones": ta.get("interceptions"), "faltas": (s.get("fouls") or {}).get("committed")}
                if not j.get("apifootball_id"):
                    r["apifootball_id"] = p["player"]["id"]
        # temporada (1 pedido): nota media por competición
        pid = j.get("apifootball_id") or r.get("apifootball_id")
        if pid and r.get("jugo"):
            temp = {}
            try:
                for x in _af(f"/players?id={pid}&season={f['league']['season']}"):
                    for s in x.get("statistics") or []:
                        g = s.get("games") or {}
                        if (s.get("team") or {}).get("id") != eq: continue
                        temp[s["league"]["name"]] = {"nota": fnum(g.get("rating")), "pj": g.get("appearences"),
                                                     "tit": g.get("lineups"), "min": g.get("minutes")}
            except SinCuota:
                raise
            except Exception as ex:
                r["aviso"] = f"sin temporada ({ex!r})"
            r["temporada"] = temp
        out.append(r)
    return out, None


# ----------------------------------------------------------------- football-data.org
FD = "https://api.football-data.org/v4"
_fd_pedidos = deque()


def _fd(path):
    # nunca más de 10 por minuto: además dejamos 6,5 s entre pedidos
    while len(_fd_pedidos) >= LIMITE_FOOTBALL_DATA_MIN and time.time() - _fd_pedidos[0] < 60:
        time.sleep(60.5 - (time.time() - _fd_pedidos[0]))
    while _fd_pedidos and time.time() - _fd_pedidos[0] >= 60:
        _fd_pedidos.popleft()
    if _fd_pedidos and time.time() - _fd_pedidos[-1] < 6.5:
        time.sleep(6.5 - (time.time() - _fd_pedidos[-1]))
    _fd_pedidos.append(time.time())
    h = {}
    if os.environ.get("FOOTBALL_DATA_KEY"):
        h["X-Auth-Token"] = os.environ["FOOTBALL_DATA_KEY"]
    return http(FD + path, h)


def football_data(j, fechas):
    eq = j.get("footballdata_equipo")
    if not eq and j.get("club"):
        # se busca una sola vez en las ligas del plan gratis que puede jugar y queda guardado
        for comp in ("PD", "PL", "SA", "PPL", "BL1", "FL1", "DED"):
            try:
                for t in _fd(f"/competitions/{comp}/teams").get("teams") or []:
                    if any(mismo_equipo(t.get(c), j["club"].split(" de ")[0]) for c in ("name", "shortName")):
                        eq = t["id"]; break
            except Exception:
                continue
            if eq:
                _guardar_id(j["clave"], "footballdata_equipo", eq); j["footballdata_equipo"] = eq; break
    if not eq:
        return [], "sin footballdata_equipo en jugadores.json"
    d1, d2 = min(fechas), max(fechas)
    d = _fd(f"/teams/{eq}/matches?dateFrom={d1}&dateTo={d2 + datetime.timedelta(days=1)}")
    out = []
    for m in d.get("matches") or []:
        f = datetime.datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).astimezone(_TZ()).date()
        if f not in fechas: continue
        ft = (m.get("score") or {}).get("fullTime") or {}
        out.append({"fuente": "football_data", "fecha": str(f), "local": m["homeTeam"].get("shortName") or m["homeTeam"]["name"],
                    "visita": m["awayTeam"].get("shortName") or m["awayTeam"]["name"], "goles_local": ft.get("home"),
                    "goles_visita": ft.get("away"), "torneo": (m.get("competition") or {}).get("name"),
                    "jornada": m.get("matchday"), "terminado": m.get("status") == "FINISHED"})
    return out, None


# ----------------------------------------------------------------- TheSportsDB
def thesportsdb(j, fechas):
    k = os.environ.get("THESPORTSDB_KEY", "123")
    base = f"https://www.thesportsdb.com/api/v1/json/{k}"
    tid = j.get("thesportsdb_equipo")
    if not tid:
        nombre = j.get("club", "")
        for t in (http(f"{base}/searchteams.php?t={urllib.parse.quote(nombre)}") or {}).get("teams") or []:
            if t.get("strSport") == "Soccer":
                tid = t["idTeam"]; break
    if not tid:
        return [], "no se encontró el equipo"
    out = []
    for e in (http(f"{base}/eventslast.php?id={tid}") or {}).get("results") or []:
        f = e.get("dateEventLocal") or e.get("dateEvent")
        if not f or datetime.date.fromisoformat(f) not in fechas: continue
        r = {"fuente": "thesportsdb", "fecha": f, "partido_id": e.get("idEvent"), "local": e.get("strHomeTeam"),
             "visita": e.get("strAwayTeam"), "goles_local": fnum(e.get("intHomeScore")), "goles_visita": fnum(e.get("intAwayScore")),
             "torneo": e.get("strLeague"), "jornada": e.get("intRound"), "terminado": e.get("strStatus") in ("Match Finished", "FT")}
        try:
            lu = (http(f"{base}/lookuplineup.php?id={e['idEvent']}") or {}).get("lineup") or []
            for p in lu:
                if mismo_nombre(p.get("strPlayer"), j["placa"]):
                    r["titular"] = p.get("strSubstitute") == "No"
                    r["dorsal"] = str(p.get("intSquadNumber") or "")
        except Exception:
            pass
        out.append(r)
    return out, None


# ----------------------------------------------------------------- Understat (solo ligas grandes: LaLiga sí, Portugal no)
US = "https://understat.com"


def _understat_datos(ruta_json, ruta_html, variable):
    """Desde fines de 2025 Understat sirve los datos aparte (getTeamData/..., getMatchData/...; piden X-Requested-With).
    Si eso falla, se prueba el formato viejo: la variable JSON.parse('...') dentro de la página."""
    try:
        return http(f"{US}/{ruta_json}", {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest",
                                          "Referer": f"{US}/{ruta_html}"})
    except (urllib.error.HTTPError, ValueError):
        pass
    txt = http(f"{US}/{ruta_html}", {"Accept": "text/html"}, crudo=True)[0]
    mm = re.search(variable + r"\s*=\s*JSON\.parse\('(.*?)'\)", txt)
    return json.loads(mm.group(1).encode().decode("unicode_escape")) if mm else None


def understat(j, fechas):
    eq = j.get("understat_equipo")
    if not eq:
        return [], "sin understat_equipo (Understat no cubre esa liga)"
    out = []
    for anio in sorted({f.year if f.month >= 7 else f.year - 1 for f in fechas}):
        d = _understat_datos(f"getTeamData/{eq}/{anio}", f"team/{eq}/{anio}", "datesData")
        partidos = d.get("dates") if isinstance(d, dict) else d
        if not isinstance(partidos, list):
            return [], "formato de página no reconocido"
        for p in partidos:
            if not p.get("isResult"): continue
            f = datetime.date.fromisoformat(p["datetime"][:10])
            if f not in fechas: continue
            r = {"fuente": "understat", "fecha": str(f), "partido_id": p["id"], "local": p["h"]["title"], "visita": p["a"]["title"],
                 "goles_local": fnum(p["goals"]["h"]), "goles_visita": fnum(p["goals"]["a"]), "terminado": True, "stats": {}}
            d2 = _understat_datos(f"getMatchData/{p['id']}", f"match/{p['id']}", "rostersData")
            ro = d2.get("rosters", d2) if isinstance(d2, dict) else None
            if ro:
                for lado in ("h", "a"):
                    for x in (ro.get(lado) or {}).values():
                        if mismo_nombre(x.get("player"), j["placa"]):
                            r.update({"minutos": int(x.get("time") or 0), "jugo": int(x.get("time") or 0) > 0,
                                      "goles": int(x.get("goals") or 0), "asistencias": int(x.get("assists") or 0)})
                            r["stats"] = {"xg": fnum(x.get("xG")), "xa": fnum(x.get("xA")), "tiros": int(x.get("shots") or 0),
                                          "pases_clave": int(x.get("key_passes") or 0)}
            out.append(r)
    return out, None


# ----------------------------------------------------------------- zerozero
ZZ = "https://www.zerozero.pt"


def zerozero(j, fechas):
    """Lee la ficha del jugador en zerozero: partidos recientes con minutos (solo lo que la página muestra)."""
    url = j.get("zerozero")
    if not url:
        txt = http(f"{ZZ}/pesquisa?search_string={urllib.parse.quote(j['placa'].title())}", {"Accept": "text/html"}, crudo=True)[0]
        m = re.search(r'href="(/jogador/[^"]+)"', txt)
        if not m:
            return [], "no se encontró al jugador"
        url = ZZ + html.unescape(m.group(1))
    txt = http(url, {"Accept": "text/html"}, crudo=True)[0]
    out = []
    # filas de partidos: fecha AAAA-MM-DD, enlace al partido, resultado N-N y minutos "NN'"
    for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", txt, re.S):
        mf = re.search(r"(20\d\d-\d\d-\d\d)", fila)
        if not mf: continue
        f = datetime.date.fromisoformat(mf.group(1))
        if f not in fechas: continue
        limpio = re.sub(r"<[^>]+>", " ", fila)
        mr = re.search(r"(\d+)\s*-\s*(\d+)", limpio)
        mi = re.search(r"(\d{1,3})\s*'", limpio)
        out.append({"fuente": "zerozero", "fecha": str(f), "minutos": int(mi.group(1)) if mi else None,
                    "jugo": bool(mi and int(mi.group(1)) > 0), "resultado": f"{mr.group(1)}-{mr.group(2)}" if mr else None})
    if not out and "jogador" not in txt:
        return [], "formato de página no reconocido"
    return out, None


# ----------------------------------------------------------------- BeSoccer (lo lee la tarea de Claude con WebFetch)
BESOCCER_HOY = os.path.join(AQUI, "besoccer_hoy.json")


def besoccer(j, fechas):
    """BeSoccer no deja entrar a los scripts: antes de correr el script, la tarea de Claude lee las páginas con su
    herramienta web y deja los datos en automatizacion/besoccer_hoy.json (formato en AGENTE.md). Acá solo se leen."""
    if not os.path.exists(BESOCCER_HOY):
        return [], "no hay besoccer_hoy.json (la tarea no leyó BeSoccer)"
    d = json.load(open(BESOCCER_HOY))
    out = []
    for p in (d.get("jugadores") or {}).get(j["clave"]) or []:
        if not p.get("fecha") or datetime.date.fromisoformat(p["fecha"]) not in fechas: continue
        q = {k: v for k, v in p.items() if v is not None}
        q.update({"fuente": "besoccer", "nota": fnum(p.get("nota")),
                  "notas_once": {str(k): fnum(v) for k, v in (p.get("notas_once") or {}).items() if fnum(v)}})
        out.append(q)
    return out, None


# ----------------------------------------------------------------- todo junto
# Las fuentes extra (y BeSoccer como fuente más) se usan para los partidos desde esta fecha en adelante.
DESDE = datetime.date(2026, 10, 18)
# football-data.org quedó fuera desde el 21/10/2026 (solo trae resultado, fecha y jornada, que ya están): la función
# sigue abajo por si se quiere volver a sumar, agregándola a esta lista.
FUENTES = [("fotmob", fotmob), ("besoccer", besoccer), ("api_football", api_football),
           ("thesportsdb", thesportsdb), ("understat", understat), ("zerozero", zerozero)]


def consultar(j, fechas, solo=None):
    """Consulta todas las fuentes extra para un jugador. Nunca levanta excepción.
    Devuelve {"partidos": {fuente: [..]}, "estado": {fuente: "ok" | "error: ..." | "sin datos: ..."}}"""
    res, est = {}, {}
    fechas = {f for f in fechas if f >= DESDE}
    if not fechas:
        return {"partidos": {}, "estado": {}}
    for nombre, fn in FUENTES:
        if solo and nombre not in solo: continue
        try:
            ps, motivo = fn(j, fechas)
            res[nombre] = ps
            est[nombre] = "ok" if motivo is None else f"sin datos: {motivo}"
        except SinCuota as ex:
            res[nombre] = []; est[nombre] = f"cuota: {ex}"
        except SinPlan as ex:
            res[nombre] = []; est[nombre] = f"sin datos: {ex}"
        except urllib.error.HTTPError as ex:
            res[nombre] = []
            est[nombre] = (f"error HTTP {ex.code}: falta la clave o no es válida" if ex.code in (401, 403) and nombre in ("api_football", "football_data")
                           else f"error HTTP {ex.code}")
        except Exception as ex:
            res[nombre] = []
            est[nombre] = ("error: dominio no habilitado en la red de la nube" if "Tunnel connection failed: 403" in str(ex)
                           else f"error: {type(ex).__name__}: {str(ex)[:120]}")
    return {"partidos": res, "estado": est}


def del_partido(extra, fecha, rival=None):
    """De lo consultado, los datos de cada fuente para el partido de esa fecha (y ese rival, si se da)."""
    out = {}
    for fuente, ps in (extra or {}).get("partidos", {}).items():
        for p in ps:
            if p.get("fecha") != str(fecha): continue
            if rival and p.get("local") and p.get("visita") and not (mismo_equipo(rival, p["local"]) or mismo_equipo(rival, p["visita"])):
                continue
            out[fuente] = p
            break
    return out
