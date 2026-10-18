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
import json, os, re, time, html, datetime, urllib.request, urllib.error, urllib.parse, unicodedata
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
        cuerpo = r.read().decode("utf-8", "replace")
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


# ----------------------------------------------------------------- FotMob
FM = "https://www.fotmob.com/api/data"


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
            # once por líneas (del arco al ataque, de izquierda a derecha como se ve en la cancha)
            filas = {}
            for p in titulares:
                vl = p.get("verticalLayout") or {}
                if vl.get("y") is None: filas = {}; break
                filas.setdefault(round(vl["y"], 2), []).append(p)
            r["once"] = [[[str(p.get("shirtNumber") or ""), p.get("lastName") or p.get("name"), p.get("id")]
                          for p in sorted(filas[y], key=lambda q: -(q.get("verticalLayout") or {}).get("x", 0))]
                         for y in sorted(filas)] if filas else []
            # si entró: minuto y a quién reemplazó
            for ev in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []:
                sw = ev.get("swap") or []
                if ev.get("type") == "Substitution" and len(sw) == 2 and str(sw[0].get("id")) == str(pid):
                    ot = ev.get("overloadTime")
                    r["entro"] = {"minuto": f"{ev.get('time')}+{ot}" if ot else ev.get("time"),
                                  "por": (sw[1].get("name") or "").split(" ")[-1], "por_id": sw[1].get("id")}
            ps = (c.get("playerStats") or {}).get(str(pid)) or {}
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
    for r in out:
        r["temporada"] = temp
    return out, None


def _TZ():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/Montevideo")


# ----------------------------------------------------------------- API-Football
AF = "https://v3.football.api-sports.io"


def _af(path):
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
        raise RuntimeError("API-Football: " + msg)
    return d.get("response") or []


def api_football(j, fechas, equipo_af=None):
    eq = equipo_af or j.get("apifootball_equipo")
    if not eq:
        return [], "sin apifootball_equipo en jugadores.json"
    fx = _af(f"/fixtures?team={eq}&last=3&timezone=America/Montevideo")
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
def understat(j, fechas):
    eq = j.get("understat_equipo")
    if not eq:
        return [], "sin understat_equipo (Understat no cubre esa liga)"
    out = []
    for anio in sorted({f.year if f.month >= 7 else f.year - 1 for f in fechas}):
        txt = http(f"https://understat.com/team/{eq}/{anio}", {"Accept": "text/html"}, crudo=True)[0]
        mm = re.search(r"datesData\s*=\s*JSON\.parse\('(.*?)'\)", txt)
        if not mm:
            return [], "formato de página no reconocido"
        partidos = json.loads(mm.group(1).encode().decode("unicode_escape"))
        for p in partidos:
            if not p.get("isResult"): continue
            f = datetime.date.fromisoformat(p["datetime"][:10])
            if f not in fechas: continue
            r = {"fuente": "understat", "fecha": str(f), "partido_id": p["id"], "local": p["h"]["title"], "visita": p["a"]["title"],
                 "goles_local": fnum(p["goals"]["h"]), "goles_visita": fnum(p["goals"]["a"]), "terminado": True, "stats": {}}
            t2 = http(f"https://understat.com/match/{p['id']}", {"Accept": "text/html"}, crudo=True)[0]
            m2 = re.search(r"rostersData\s*=\s*JSON\.parse\('(.*?)'\)", t2)
            if m2:
                ro = json.loads(m2.group(1).encode().decode("unicode_escape"))
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


# ----------------------------------------------------------------- todo junto
FUENTES = [("fotmob", fotmob), ("api_football", api_football), ("football_data", football_data),
           ("thesportsdb", thesportsdb), ("understat", understat), ("zerozero", zerozero)]


def consultar(j, fechas, solo=None):
    """Consulta todas las fuentes extra para un jugador. Nunca levanta excepción.
    Devuelve {"partidos": {fuente: [..]}, "estado": {fuente: "ok" | "error: ..." | "sin datos: ..."}}"""
    res, est = {}, {}
    for nombre, fn in FUENTES:
        if solo and nombre not in solo: continue
        try:
            ps, motivo = fn(j, fechas)
            res[nombre] = ps
            est[nombre] = "ok" if motivo is None else f"sin datos: {motivo}"
        except SinCuota as ex:
            res[nombre] = []; est[nombre] = f"cuota: {ex}"
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
