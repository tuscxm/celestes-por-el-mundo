"""Parte de abajo de la infografía según el puesto (diseño del 23/10/2026) y texto del posteo con el 3-5-2.

- SU PARTIDO: todo lo que hizo (goles, asistencias, toques, pases, duelos, regates, recuperaciones, defensa, faltas, tarjetas).
- ESPERADOS Y MÁS: lo esperado (xG, xA...) y lo que no entra en SU PARTIDO ni en el perfil.
- MAPA DE CALOR con los remates, la barra de dónde jugó (izquierda / centro / derecha y campo rival),
  SU ZONA (la franja donde más jugó, con porcentajes) y el PERFIL del puesto en que jugó ese partido
  (delantero, enganche, volante por fuera, mediocentro, defensor central o lateral), solo con lo de ese puesto.
- TEMPORADA: igual que antes.
Texto del posteo: qué hizo y cómo encajaría en una Uruguay 3-5-2 con enganche (rol_352 de jugadores.json),
solo con números reales del partido que le juegan a favor.

Los datos son los de FotMob (fuentes.fotmob): stats, calor (acciones del mapa), remates_mapa y posicion_id.
Escala del mapa: x 0-100 hacia el arco rival, y 0-100 con 0 = costado derecho del equipo.
"""
import os

from mapa_sofascore import dibujar_horizontal

PERFILES = {
    "delantero": "PERFIL DE DELANTERO", "enganche": "PERFIL DE ENGANCHE", "por_fuera": "PERFIL DE VOLANTE POR FUERA",
    "mediocentro": "PERFIL DE MEDIOCENTRO", "central": "PERFIL DE DEFENSOR CENTRAL", "lateral": "PERFIL DE LATERAL",
}
LADOS = {"izquierda": "POR LA IZQUIERDA", "centro": "POR EL CENTRO", "derecha": "POR LA DERECHA"}
EN_LADO = {"izquierda": lambda y: y > 200 / 3, "centro": lambda y: 100 / 3 <= y <= 200 / 3, "derecha": lambda y: y < 100 / 3}


def fr(v, minimo_dorado=60):
    """[a, b] -> ('a/b (p%)', dorado si el porcentaje es alto)."""
    if not isinstance(v, (list, tuple)) or len(v) != 2 or not v[1]:
        return None
    p = round(v[0] * 100 / v[1])
    return f"{v[0]}/{v[1]} ({p}%)", p >= minimo_dorado


def stats_sofascore(s, st_fotmob=None):
    """Estadísticas de SofaScore con las claves de FotMob (SofaScore manda; lo que no trae, de FotMob).
    SofaScore no manda las que valen 0, así que las cuentas que faltan van en 0."""
    st = dict(st_fotmob or {})
    def n(k): return s.get(k) or 0
    def par(a, b):
        return [n(a), s[b]] if s.get(b) else None
    for k_fm, k_ss in (("goals", "goals"), ("assists", "goalAssist"), ("touches", "touches"), ("recoveries", "ballRecovery"),
                       ("interceptions", "interceptionWon"), ("matchstats.headers.tackles", "totalTackle"), ("clearances", "totalClearance"),
                       ("fouls", "fouls"), ("was_fouled", "wasFouled"), ("dispossessed", "dispossessed"), ("chances_created", "keyPass"),
                       ("Offsides", "totalOffside"), ("dribbled_past", "challengeLost"), ("duel_won", "duelWon"), ("duel_lost", "duelLost"),
                       ("ShotsOnTarget", "onTargetScoringAttempt"), ("ShotsOffTarget", "shotOffTarget"), ("blocked_shots", "blockedScoringAttempt")):
        st[k_fm] = n(k_ss)
    st["total_shots"] = s.get("totalShots") if s.get("totalShots") is not None else st["ShotsOnTarget"] + st["ShotsOffTarget"] + st["blocked_shots"]
    for k_fm, a, b in (("accurate_passes", "accuratePass", "totalPass"), ("long_balls_accurate", "accurateLongBalls", "totalLongBalls"),
                       ("accurate_crosses", "accurateCross", "totalCross"), ("dribbles_succeeded", "wonContest", "totalContest")):
        v = par(a, b)
        if v: st[k_fm] = v
    if s.get("aerialWon") or s.get("aerialLost"):
        st["aerials_won"] = [n("aerialWon"), n("aerialWon") + n("aerialLost")]
    for k_fm, k_ss in (("expected_goals", "expectedGoals"), ("expected_assists", "expectedAssists")):
        if isinstance(s.get(k_ss), (int, float)): st[k_fm] = s[k_ss]
    return st


def tipo_perfil(dj, posicion_id):
    """Perfil del puesto en que jugó ese partido (dj = respaldo_auto.donde_jugo). El enganche es el del medio de la
    línea de tres detrás de la punta (positionId 84-86 de FotMob)."""
    pu = dj.get("puesto")
    if pu == "delantero": return "delantero"
    if pu == "enganche": return "enganche"  # suplente cuyo puesto principal es el de enganche
    if pu in ("volante por izquierda", "volante por derecha"): return "por_fuera"
    if pu == "defensor central": return "central"
    if pu in ("lateral izquierdo", "lateral derecho"): return "lateral"
    if pu == "mediocentro": return "enganche" if posicion_id in (84, 85, 86) and dj.get("enganche") else "mediocentro"
    return None


def filas_perfil(t, st):
    """Filas del perfil (solo las del puesto) y las claves usadas (para no repetirlas en ESPERADOS Y MÁS)."""
    def num(k, umbral):
        return (str(st[k]), st[k] >= umbral) if st.get(k) is not None else None
    duelos = [st.get("duel_won"), (st.get("duel_won") or 0) + (st.get("duel_lost") or 0)] if st.get("duel_won") is not None else None
    al_arco = [st.get("ShotsOnTarget") or 0, st.get("total_shots")] if st.get("total_shots") else None
    c = {
        "remates": ("Remates al arco", fr(al_arco, 50)),
        "goles_xg": ("Goles · xG", (f"{st.get('goals', 0)} · {st['expected_goals']:.2f}".replace(".", ","), False) if st.get("expected_goals") is not None else None),
        "area": ("Toques en el área rival", num("touches_opp_box", 5)),
        "duelos": ("Duelos ganados", fr(duelos)),
        "regates": ("Regates", fr(st.get("dribbles_succeeded"))),
        "aereos": ("Duelos aéreos ganados", fr(st.get("aerials_won"))),
        "ocasiones": ("Ocasiones creadas", num("chances_created", 2)),
        "tercio": ("Pases al último tercio", num("passes_into_final_third", 5)),
        "rompen": ("Pases que rompen líneas", num("line_breaking_passes", 5)),
        "pases": ("Pases precisos", fr(st.get("accurate_passes"), 85)),
        "largos": ("Pases largos precisos", fr(st.get("long_balls_accurate"))),
        "centros": ("Centros precisos", fr(st.get("accurate_crosses"), 40)),
        "recup": ("Recuperaciones", num("recoveries", 6)),
        "suelo": ("Duelos en el piso", fr(st.get("ground_duels_won"))),
        "despejes": ("Despejes", num("clearances", 5)),
        "interc": ("Intercepciones", num("interceptions", 3)),
        "xa": ("Asistencias esperadas (xA)", (f"{st['expected_assists']:.2f}".replace(".", ","), st["expected_assists"] >= 0.3) if st.get("expected_assists") is not None else None),
        "regateado": ("Lo regatearon", (str(st["dribbled_past"]), False) if st.get("dribbled_past") is not None else None),
    }
    orden = {
        "delantero": ["remates", "goles_xg", "area", "duelos", "regates"],
        "enganche": ["ocasiones", "tercio", "rompen", "regates", "xa"],
        "por_fuera": ["centros", "regates", "tercio", "duelos", "recup"],
        "mediocentro": ["pases", "largos", "rompen", "recup", "suelo"],
        "central": ["aereos", "duelos", "despejes", "interc", "largos"],
        "lateral": ["duelos", "centros", "recup", "tercio", "regateado"],
    }[t]
    return [[c[k][0], c[k][1][0], c[k][1][1]] for k in orden if c[k][1]], set(orden)


def su_partido(st, filas_base):
    """SU PARTIDO con todo lo que hizo. De filas_base (las que ya arma el script) se toman 'Penal en la tanda' y 'Tarjetas'."""
    def n(k): return st.get(k)
    duelos = [n("duel_won"), (n("duel_won") or 0) + (n("duel_lost") or 0)] if n("duel_won") is not None else None
    filas = [["Goles", n("goals"), bool(n("goals"))], ["Asistencias", n("assists"), bool(n("assists"))]]
    filas += [list(r) for r in filas_base if r[0] == "Penal en la tanda"]
    for et, v in (("Toques", n("touches")), ("Pases precisos", fr(n("accurate_passes"), 101)), ("Duelos ganados", fr(duelos, 101)),
                  ("Duelos aéreos ganados", fr(n("aerials_won"), 101)), ("Regates", fr(n("dribbles_succeeded"), 101)),
                  ("Recuperaciones", n("recoveries")), ("Intercepciones", n("interceptions")), ("Entradas", n("matchstats.headers.tackles")),
                  ("Despejes", n("clearances")), ("Faltas cometidas", n("fouls")), ("Faltas recibidas", n("was_fouled")),
                  ("Pérdidas de balón", n("dispossessed"))):
        if v is None: continue
        filas.append([et, v[0] if isinstance(v, tuple) else v, False])
    filas += [list(r) for r in filas_base if r[0] == "Tarjetas"]
    return [[k, str(v), bool(g[0]) if g else False] for k, v, *g in filas if v is not None][:16]


def esperados(st, ya):
    """ESPERADOS (columna 1) y MÁS DEL PARTIDO (columna 2, lo que no está en SU PARTIDO ni en el perfil)."""
    def x(v): return f"{v:.2f}".replace(".", ",")
    f = [["ESPERADOS", " "]]
    for et, k in (("Goles esperados (xG)", "expected_goals"), ("xG sin penales", "expected_goals_non_penalty"),
                  ("xG de sus remates al arco", "expected_goals_on_target_variant"), ("Asistencias esperadas (xA)", "expected_assists"),
                  ("xG + xA", "xg_and_xa")):
        if st.get(k) is not None: f.append([et, x(st[k]), False])
    mas = [["MÁS DEL PARTIDO", " "]]
    if st.get("total_shots"):
        mas.append(["Remates arco/fuera/bloq.", f"{st.get('ShotsOnTarget', 0)} · {st.get('ShotsOffTarget', 0)} · {st.get('blocked_shots', 0)}", False])
    for et, k, clave in (("Ocasiones creadas", "chances_created", "ocasiones"), ("Pases al último tercio", "passes_into_final_third", "tercio"),
                         ("Pases que rompen líneas", "line_breaking_passes", "rompen"), ("Toques en el área rival", "touches_opp_box", "area"),
                         ("Fuera de juego", "Offsides", None), ("Lo regatearon", "dribbled_past", "regateado"), ("Remates que tapó", "shot_blocks", None)):
        if st.get(k) is not None and clave not in ya: mas.append([et, str(st[k]), False])
    for et, k, clave in (("Pases largos precisos", "long_balls_accurate", "largos"), ("Centros precisos", "accurate_crosses", "centros"),
                         ("Duelos en el piso", "ground_duels_won", "suelo")):
        v = fr(st.get(k), 101)
        if v and clave not in ya: mas.append([et, v[0], False])
    return (f if len(f) > 1 else []), (mas[:8] if len(mas) > 1 else [])


def zonas(calor, remates):
    """Dónde jugó: % por lado, la franja donde más jugó (con sus acciones, campo rival y remates) y % en campo rival."""
    n = len(calor)
    cuenta = {l: [q for q in calor if en(q["y"])] for l, en in EN_LADO.items()}
    lado = max(cuenta, key=lambda k: len(cuenta[k]))
    k = len(cuenta[lado]); m = sum(1 for q in cuenta[lado] if q["x"] > 50)
    filas = [["Acciones", f"{k}/{n} ({round(k * 100 / n)}%)", True], ["En campo rival", f"{m}/{k} ({round(m * 100 / k)}%)" if k else "0", False]]
    rz = [r for r in remates or [] if EN_LADO[lado](r["y"])]
    if rz:
        filas.append(["Remates · al arco", f"{len(rz)} · {sum(1 for r in rz if r['tipo'] in ('gol', 'al_arco'))}", False])
    pct = {l: round(len(v) * 100 / n) for l, v in cuenta.items()}
    return lado, filas, pct, round(sum(1 for q in calor if q["x"] > 50) * 100 / n)


def armar(j, p, dj, salida, mapa_rel, filas_base, calor=None):
    """Datos de la parte de abajo para render_v3 ("abajo") y lo que necesita el texto del posteo.
    p: partido de FotMob del jugador; dj: respaldo_auto.donde_jugo(p, fotmob_id); mapa_rel: ruta del mapa (relativa a salida);
    filas_base: SU PARTIDO que ya arma el script; calor: puntos del mapa si se quieren otros que los de FotMob.
    Devuelve None si FotMob no trae estadísticas del jugador."""
    st = p.get("stats") or {}
    if not st:
        return None
    tipo = tipo_perfil(dj, p.get("posicion_id"))
    pf, ya = filas_perfil(tipo, st) if tipo else ([], set())
    esp, mas = esperados(st, ya | ({"area"} if tipo == "delantero" else set()))
    ab = {"su_partido": su_partido(st, filas_base), "esperados": esp, "mas": mas,
          "perfil": {"titulo": PERFILES[tipo], "filas": pf} if pf else None}
    calor = calor if calor is not None else (p.get("calor") or [])
    info = {"tipo": tipo, "puesto": "enganche" if tipo == "enganche" else (dj.get("puesto") or ""), "lado": None}
    if len(calor) >= 5:
        # remates en el mapa: solo si están todos los que cuenta la estadística y los goles coinciden
        rm = p.get("remates_mapa") or []
        tiros = p.get("remates")
        completos = isinstance(tiros, list) and (st.get("total_shots") is None or len(tiros) == st.get("total_shots")) \
            and (st.get("goals") is None or sum(1 for r in rm if r["tipo"] == "gol") == st.get("goals"))
        os.makedirs(os.path.dirname(os.path.join(salida, mapa_rel)), exist_ok=True)
        dibujar_horizontal(calor, os.path.join(salida, mapa_rel), None, remates=rm if completos else None)
        lado, zf, pct, rival = zonas(calor, rm if completos else [])
        ab.update({"heat_img": mapa_rel, "lados": pct, "campo_rival": rival, "zona": {"titulo": f"SU ZONA: {LADOS[lado]}", "filas": zf}})
        info.update({"lado": lado, "pct": pct, "rival": rival, "remates_marcados": bool(rm) and completos})
    return {"abajo": ab, "info": info, "st": st}


# ----------------------------------------------------------------- texto del posteo: Uruguay 3-5-2 con enganche
def hechos(st, info):
    """Lo que juega a favor en cada rol (solo números reales y positivos)."""
    def par(k):
        v = st.get(k)
        return (v[0], v[1], round(v[0] * 100 / v[1])) if isinstance(v, (list, tuple)) and len(v) == 2 and v[1] else None
    def cant(n, uno, varios): return f"{n} {uno if n == 1 else varios}"
    h = {}
    v = par("accurate_passes")
    if v and v[1] >= 10: h["pases"] = f"{v[0]}/{v[1]} pases ({v[2]}%)"
    v = par("long_balls_accurate")
    if v and v[0] >= 2 and v[2] >= 50: h["largos"] = f"{v[0]}/{v[1]} pases largos"
    if st.get("duel_won") is not None:
        t = st["duel_won"] + (st.get("duel_lost") or 0)
        if t and st["duel_won"] * 2 >= t: h["duelos"] = f"{st['duel_won']}/{t} duelos ganados"
    v = par("aerials_won")
    if v and v[0] and v[2] >= 50: h["aereos"] = f"{v[0]}/{v[1]} por arriba"
    for k, uno, varios in (("recoveries", "recuperación", "recuperaciones"), ("interceptions", "intercepción", "intercepciones"),
                           ("clearances", "despeje", "despejes"), ("passes_into_final_third", "pase al último tercio", "pases al último tercio"),
                           ("line_breaking_passes", "pase que rompió líneas", "pases que rompieron líneas"),
                           ("chances_created", "ocasión creada", "ocasiones creadas"), ("touches_opp_box", "toque en el área rival", "toques en el área rival"),
                           ("goals", "gol", "goles")):
        if st.get(k): h[k] = cant(st[k], uno, varios)
    v = par("dribbles_succeeded")
    if v and v[0]: h["regates"] = f"{v[0]}/{v[1]} regates"
    v = par("accurate_crosses")
    if v and v[0]: h["centros"] = f"{v[0]}/{v[1]} centros precisos"
    if st.get("total_shots") and st.get("ShotsOnTarget"): h["remates"] = f"{st['ShotsOnTarget']} de {st['total_shots']} remates al arco"
    if info.get("lado"):
        h["lado"] = f"{info['pct'][info['lado']]}% de sus acciones {dict(izquierda='por la izquierda', centro='por el centro', derecha='por la derecha')[info['lado']]}"
        if info["rival"] >= 50: h["rival"] = f"{info['rival']}% en campo rival"
    return h


def lista(xs):
    xs = [x for x in xs if x]
    return ", ".join(xs[:-1]) + (" y " if len(xs) > 1 else "") + xs[-1] if xs else ""


ROLES_352 = {
    "zaguero": (["pases", "largos", "duelos", "aereos", "interceptions", "recoveries", "clearances"],
                "Lo vemos de zaguero{lado} en la línea de tres: {hechos}. Con tres atrás, un central que sale limpio le suma un pase "
                "para encontrar al enganche y deja a los carrileros libres para pasar."),
    "carrilero": (["lado", "rival", "passes_into_final_third", "centros", "regates", "recoveries"],
                  "Sería carrilero{lado}: {hechos}. En el 3-5-2 toda la banda es suya, y con tres centrales atrás puede pasar sin dejar la espalda sola."),
    "interno": (["pases", "line_breaking_passes", "recoveries", "duelos", "interceptions"],
                "Sería uno de los dos internos: {hechos}. Es el que sostiene y hace circular para que el enganche reciba de frente."),
    "enganche": (["goals", "chances_created", "passes_into_final_third", "line_breaking_passes", "regates", "touches_opp_box"],
                 "Es el 10 que pide el sistema: {hechos}. Suelto detrás de dos puntas, con dos internos que lo cubren, Uruguay junta a los que definen."),
    "delantero": (["goals", "remates", "touches_opp_box", "duelos", "regates"],
                  "Sería uno de los dos de punta: {hechos}. Con un enganche que lo habilite y otro 9 al lado, deja de pelear solo contra los centrales."),
}
CIERRE_352 = "Tres atrás, dos carrileros, dos internos, un 10 suelto y dos puntas. ¿Lo jugarías así? 👇"


def texto_352(j, armado):
    """Cuerpo del posteo (va después del encabezado con el partido, los minutos y la nota): qué hizo y cómo encajaría
    en una Uruguay 3-5-2 con enganche. Devuelve una lista de líneas."""
    st, info = armado["st"], armado["info"]
    hs = hechos(st, info)
    claves, plantilla = ROLES_352.get(j.get("rol_352"), ([], ""))
    # si el rol usa de qué lado jugó (carrilero), eso va en el párrafo del 3-5-2 y no se repite arriba
    primeras = [k for k in ("lado", "goals", "pases", "duelos", "recoveries", "passes_into_final_third", "chances_created")
                if not (k == "lado" and "lado" in claves)]
    partido = lista([hs.get(k) for k in primeras if hs.get(k)][:4])
    lado = {"izquierda": " por izquierda", "derecha": " por derecha"}.get(info.get("lado"), "")
    rol = plantilla.format(lado=lado, hechos=lista([hs[k] for k in claves if hs.get(k)][:3])) if plantilla else ""
    # sin puesto conocido (por ejemplo, un suplente en el respaldo) no se dice "de titular": va lo que hizo y nada más
    puesto = info.get("puesto")
    if puesto:
        lineas = [f"Jugó de {puesto}: {partido}." if partido else f"Jugó de {puesto}."]
    else:
        lineas = [f"En su partido: {partido}."] if partido else []
    if rol and "{hechos}" not in rol and ": ." not in rol:
        lineas += ["", "🧩 ¿Y en una Uruguay 3-5-2 con enganche?", rol, "", CIERRE_352]
    return lineas
