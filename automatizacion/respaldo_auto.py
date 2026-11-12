"""Respaldo automático cuando SofaScore no responde: arma la infografía con FotMob (alineación, notas,
estadísticas y temporada) y promedia las notas con las otras fuentes que las traen (API-Football).
Escribe el JSON con el formato de besoccer_plantilla.json y corre armar_besoccer.py, que arma la infografía,
actualiza resumen.json (reemplaza el "error") y procesados.json.

Si FotMob tampoco sirve, no hace nada: queda el error y la tarea de Claude prueba con BeSoccer (AGENTE.md).
Nunca inventa: lo que las fuentes no traen no se pone."""
import json, os, sys, subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import fuentes

# positionId de FotMob -> puesto (solo los que están claros; si no, queda "SU JUEGO")
# torneos de selecciones (nombres de FotMob) en español
TORNEOS = {"Friendlies": "Amistoso internacional", "World Cup": "Mundial", "Copa America": "Copa América",
           "World Cup Qualification CONMEBOL": "Eliminatorias", "World Cup Qualification": "Eliminatorias"}

def puesto(pid):
    if pid is None: return ""
    if pid == 11: return "arquero"
    if pid == 32: return "lateral derecho"
    if pid == 38: return "lateral izquierdo"
    if 33 <= pid <= 37: return "defensor central"
    if pid in (82, 83): return "volante por derecha"
    if pid in (87, 88): return "volante por izquierda"
    if 50 <= pid <= 79 or pid in (84, 85, 86): return "mediocentro"
    if pid >= 100: return "delantero"
    return ""


RONDAS = {"final": "Final", "semi-finals": "Semifinal", "semi-final": "Semifinal", "semifinals": "Semifinal",
          "quarter-finals": "Cuartos de final", "quarter-final": "Cuartos de final", "quarterfinals": "Cuartos de final",
          "round of 16": "Octavos de final", "round of 32": "Dieciseisavos de final", "playoff": "Repechaje",
          "play-off": "Repechaje", "playoffs": "Repechaje", "knockout round play-offs": "Repechaje",
          "league stage": "Fase de liga", "group stage": "Fase de grupos", "3rd place": "Tercer puesto",
          "third place": "Tercer puesto", "preliminary round": "Ronda preliminar", "qualification": "Clasificación"}


def ronda(r):
    """Jornada / fase en español. Lo que no se sabe traducir se deja como viene."""
    r = str(r or "").strip()
    if not r: return ""
    if r.isdigit(): return f"Jornada {r}"
    t = r.lower()
    if t in RONDAS: return RONDAS[t]
    if t.startswith("round ") and t[6:].isdigit(): return f"Jornada {t[6:]}"
    return r


def dibujo_lineas(dib):
    """Titulares por línea (del arco al ataque), cada línea de derecha a izquierda (x de FotMob)."""
    filas = {}
    for i, v in (dib or {}).items():
        if v.get("y") is None or v.get("x") is None: return []
        filas.setdefault(round(v["y"], 2), []).append((v["x"], i))
    return [[i for _, i in sorted(filas[y])] for y in sorted(filas)]


def donde_jugo(d, fid):
    """Puesto del partido y qué lleva en TOTALES, con lo que trae FotMob (sin suponer).
    Titular: su positionId y su lugar en el dibujo. Suplente: su puesto habitual (FotMob no da dónde entró)."""
    ls = dibujo_lineas(d.get("dibujo"))
    linea_i = next((k for k, l in enumerate(ls) if fid in l), None) if d.get("titular") else None
    r = puesto(d.get("posicion_id")) if d.get("titular") else ""
    por_afuera = enganche = False
    if linea_i is not None:
        l = ls[linea_i]
        # en una línea de 4 volantes (ni la de defensa ni la de ataque), los de las puntas son volantes por banda
        if 2 <= linea_i <= len(ls) - 2 and len(l) == 4 and fid in (l[0], l[-1]):
            por_afuera = True
            r = "volante por derecha" if fid == l[0] else "volante por izquierda"
        enganche = len(ls) >= 5 and linea_i == len(ls) - 2
    habitual = False
    if not r and not d.get("titular"):
        r = {0: "arquero", 1: "", 2: "", 3: "delantero"}.get(d.get("puesto_habitual"), "")
        habitual = bool(r)
    # los 4 más adelantados del equipo (por línea del dibujo)
    adelantados = [i for l in reversed(ls[1:]) for i in l][:4] if ls else []
    return {"puesto": r, "enganche": enganche, "por_afuera": por_afuera, "adelantado": fid in adelantados, "habitual": habitual}


def stats_como_sofascore(st):
    """Estadísticas de FotMob con las claves de SofaScore (para usar las mismas filas que el script principal)."""
    s = {}
    def v(k):
        x = st.get(k)
        return x[0] if isinstance(x, (list, tuple)) else x
    for k_fm, k_ss in (("ShotsOnTarget", "onTargetScoringAttempt"), ("ShotsOffTarget", "shotOffTarget"), ("blocked_shots", "blockedScoringAttempt"),
                       ("total_shots", "totalShots"), ("big_chance_missed_title", "bigChanceMissed"), ("chances_created", "keyPass"),
                       ("big_chance_created_team_title", "bigChanceCreated"), ("hit_woodwork", "hitWoodwork")):
        if v(k_fm) is not None: s[k_ss] = v(k_fm)
    for k_fm, k_ss in (("expected_goals", "expectedGoals"), ("expected_assists", "expectedAssists")):
        if isinstance(v(k_fm), (int, float)): s[k_ss] = float(v(k_fm))
    if isinstance(st.get("accurate_crosses"), (list, tuple)) and st["accurate_crosses"][1] is not None:
        s["accurateCross"], s["totalCross"] = st["accurate_crosses"]
    return s


def armar(j, fechas, salida, proc_path, forzar=False):
    extra = fuentes.consultar(j, fechas)
    fm = extra["partidos"].get("fotmob") or []
    if extra["estado"].get("fotmob") != "ok":
        print(f"respaldo {j['clave']}: FotMob no sirve ({extra['estado'].get('fotmob')})"); return False
    rp = os.path.join(salida, "resumen.json")
    if not fm:
        # FotMob respondió y no tiene partidos en esas fechas
        res = json.load(open(rp))
        for x in res["jugadores"]:
            if x["clave"] == j["clave"]:
                x["partidos"] = [{"estado": "sin partido en esas fechas", "respaldo": "FotMob (SofaScore no respondió)"}]
        json.dump(res, open(rp, "w"), ensure_ascii=False, indent=1)
        return True
    procesados = set(json.load(open(proc_path))) if proc_path and os.path.exists(proc_path) else set()
    for d in fm:
        if f"{j['clave']}_{d['fecha']}" in procesados and d.get("minutos") and not forzar:
            # ya se armó en una revisión anterior: no se rehace (igual que el script principal)
            res = json.load(open(rp))
            for x in res["jugadores"]:
                if x["clave"] == j["clave"]:
                    x["partidos"] = [p for p in x["partidos"] if p.get("estado") != "error" and p.get("fecha") != d["fecha"]] + [
                        {"estado": "ya procesado", "fecha": d["fecha"],
                         "partido": f"{d['local']} {d.get('goles_local')}-{d.get('goles_visita')} {d['visita']}"}]
            json.dump(res, open(rp, "w"), ensure_ascii=False, indent=1)
            continue
        dp = fuentes.del_partido(extra, d["fecha"], d["visita"] if fuentes.mismo_equipo(d["local"], _club(j)) else d["local"])
        af = dp.get("api_football") or {}
        bs = dp.get("besoccer") or {}
        b = {"clave": j["clave"], "fecha": d["fecha"], "fuente_respaldo": "FotMob", "apellido": fuentes.apellido(j["placa"]),
             "equipo": _club(j), "avisos": [f"SofaScore no respondió; fuentes: " + ", ".join(f"{k} {v}" for k, v in extra["estado"].items())]}
        seleccion = "uruguay" in (fuentes.norm(d["local"]) + " " + fuentes.norm(d["visita"]))
        b["partido"] = {"local": d["local"], "visita": d["visita"], "goles_local": d.get("goles_local"), "goles_visita": d.get("goles_visita"),
                        "torneo": TORNEOS.get(d.get("torneo"), d.get("torneo") or ""), "ronda": ronda(d.get("ronda")), "tanda": d.get("tanda"),
                        "seleccion": seleccion,
                        "local_es_su_equipo": fuentes.mismo_equipo(d["local"], "Uruguay" if seleccion else _club(j))}
        if d.get("terminado") is False:
            b["estado"] = "no terminó"
        elif not d.get("minutos"):
            b["estado"] = "no jugó"
        else:
            b["estado"] = "jugó"
            st = d.get("stats") or {}
            notas = [d.get("nota"), af.get("nota"), bs.get("nota")]
            b["nota"] = fuentes.promedio(notas)
            if len([x for x in notas if x]) > 1:
                b["avisos"].append(f"Nota = promedio de fotmob {d.get('nota')} · api_football {af.get('nota')} · besoccer {bs.get('nota')} → {b['nota']}")
            er = None
            if not seleccion:
                rival = d["visita"] if fuentes.mismo_equipo(d["local"], _club(j)) else d["local"]
                # si el rival es el club de otro de los jugadores seguidos, su escudo ya está guardado
                er = next((os.path.join(AQUI, "escudos", f"club_{o['clave']}.png") for o in json.load(open(os.path.join(AQUI, "jugadores.json")))
                           if o["clave"] != j["clave"] and _club(o) and fuentes.mismo_equipo(rival, _club(o))
                           and os.path.exists(os.path.join(AQUI, "escudos", f"club_{o['clave']}.png"))), None)
            # el de otra selección, o el de un club que no es de los seguidos, sale de FotMob
            er = er or (escudo_fotmob(d["rival_id"]) if d.get("rival_id") else None)
            if er: b["escudo_rival"] = er
            fid = str(j.get("fotmob_id"))
            dj = donde_jugo(d, fid)
            b.update({"titular": bool(d.get("titular")), "minutos": d["minutos"], "dorsal": d.get("dorsal"),
                      "posicion": dj["puesto"], "formacion": d.get("formacion") or ""})
            if dj["habitual"]:
                b["avisos"].append(f"Entró de suplente: el puesto ({dj['puesto']}) es su puesto habitual, no se sabe dónde entró")
            if d.get("entro") and not d.get("titular"):
                b["entro"] = {"minuto": d["entro"]["minuto"], "por": d["entro"]["por"]}
            ao = af.get("notas_once") or {}
            bo = {str(k): v for k, v in (bs.get("notas_once") or {}).items()}
            tj = d.get("tarjetas") or {}
            b["once"] = [[[p[0], p[1], fuentes.promedio([d["notas_once"].get(p[0]), ao.get(p[0]), bo.get(str(p[0]))]), tj.get(str(p[2])) or {}] for p in linea]
                         for linea in d.get("once") or []]
            mia = tj.get(str(j.get("fotmob_id"))) or {}
            if mia.get("roja"): b["roja"] = mia["roja"]

            def frac(k):
                v = st.get(k)
                return f"{v[0]}/{v[1]}" if isinstance(v, (list, tuple)) and v[1] is not None else None
            am, ro = d.get("amarillas") or 0, d.get("rojas") or 0
            tarj = f"{am}[A] · {ro}[R]"
            sp = [["Goles", d.get("goles"), bool(d.get("goles"))], ["Asistencias", d.get("asistencias"), bool(d.get("asistencias"))]]
            # penal en la tanda: no es gol ni remate del partido, va aparte
            pateo = (d.get("tanda") or {}).get("pateo")
            if pateo:
                sp.append(["Penal en la tanda", pateo["resultado"].capitalize(), pateo["resultado"] == "convirtió"])
                b["avisos"].append(f"Hubo tanda de penales ({d['tanda']['local']}-{d['tanda']['visita']}): {pateo['resultado']} su penal "
                                   f"(el {pateo['orden']}º de la tanda, quedó {pateo['marcador']}); no cuenta como gol ni como remate")
            elif d.get("tanda"):
                b["avisos"].append(f"Hubo tanda de penales ({d['tanda']['local']}-{d['tanda']['visita']}) y no pateó")
            if st.get("touches") is not None: sp.append(["Toques", st["touches"]])
            if st.get("duel_won") is not None and st.get("duel_lost") is not None:
                sp.append(["Duelos ganados", f"{st['duel_won']}/{st['duel_won'] + st['duel_lost']}"])
            if frac("aerials_won"): sp.append(["Duelos aéreos ganados", frac("aerials_won")])
            if st.get("fouls") is not None: sp.append(["Faltas cometidas", st["fouls"]])
            sp.append(["Tarjetas", tarj])
            if d.get("amarillas") is None and d.get("rojas") is None: sp.pop()
            b["su_partido"] = [x for x in sp if x[1] is not None]
            es = []
            if isinstance(st.get("accurate_passes"), (list, tuple)) and st["accurate_passes"][1]:
                a_, t_ = st["accurate_passes"]
                es += [["Pases precisos", f"{a_}/{t_}"], ["Precisión de pase", f"{round(a_ * 100 / t_)}%"]]
            for lbl, k in (("Pases clave", "chances_created"), ("Pases largos precisos", None), ("Recuperaciones", "recoveries"),
                           ("Intercepciones", "interceptions"), ("Entradas", "matchstats.headers.tackles"), ("Despejes", "clearances")):
                if k is None:
                    if frac("long_balls_accurate"): es.append([lbl, frac("long_balls_accurate")])
                elif st.get(k) is not None:
                    es.append([lbl, st[k]])
            # TOTALES según dónde jugó (como el script principal): enganche o volante por afuera de una línea de 4 -> todo;
            # delantero o entre los 4 más adelantados -> lo de ataque; mediocentro, volante o mixto -> lo de volante.
            from infografia_sofascore import filas_ataque, armar_totales, ZONAS
            rol352 = j.get("rol_352")
            todas = dj["enganche"] or dj["por_afuera"] or rol352 == "enganche"
            con_ataque = todas or dj["puesto"] == "delantero" or (d.get("titular") and dj["adelantado"]) or rol352 == "delantero"
            con_volante = todas or dj["puesto"] in ("mediocentro", "volante por derecha", "volante por izquierda") or j.get("mixto") \
                or rol352 in ("carrilero", "interno")
            ss = stats_como_sofascore(st)
            ataque = []
            if con_ataque:
                # FotMob no manda las claves de remates cuando no remató: si además su mapa de remates está vacío, son 0
                if "totalShots" not in ss and d.get("remates") == []:
                    ss.update({"onTargetScoringAttempt": 0, "shotOffTarget": 0, "blockedScoringAttempt": 0, "totalShots": 0, "bigChanceMissed": 0})
                if all(k in ss for k in ("onTargetScoringAttempt", "shotOffTarget", "totalShots")):
                    if "blockedScoringAttempt" not in ss and ss["onTargetScoringAttempt"] + ss["shotOffTarget"] == ss["totalShots"]:
                        ss["blockedScoringAttempt"] = 0
                    if "blockedScoringAttempt" in ss:
                        ataque = filas_ataque(ss)
                    else:
                        ataque = [x for x in filas_ataque(ss) if x[0] != "Remates afuera · bloq."]
                else:
                    b["avisos"].append("Sin remates en el respaldo: TOTALES va sin lo de ataque")
                # lo que FotMob no trae no se muestra (filas_ataque pone 0 cuando la clave falta)
                falta = {"Ocasiones claras falladas": "bigChanceMissed", "Ocasiones claras creadas": "bigChanceCreated", "Pases clave": "keyPass"}
                ataque = [x for x in ataque if x[0] not in falta or falta[x[0]] in ss]
            volante = {}
            if con_volante and isinstance(st.get("passes_into_final_third"), int):
                volante["ultimo_tercio"] = ["Pases al último tercio", str(st["passes_into_final_third"]), True]
            if d.get("amarillas") is not None or d.get("rojas") is not None:
                es = armar_totales([[k, str(v), False] for k, v in es], ataque, volante, tarj)
            else:
                es = armar_totales([[k, str(v), False] for k, v in es], ataque, volante, "")[:-1]
            b["estadisticas"] = es
            # mapa de calor y su franja (acciones del mapa de calor y, si lleva lo de ataque, remates al arco)
            calor = d.get("calor") or []
            tiros = d.get("remates")
            # los remates se marcan en el mapa solo si están todos los que cuenta la estadística y los goles marcados
            # son los goles del jugador (FotMob a veces trae como gol uno anulado o de la tanda de penales)
            rm = d.get("remates_mapa") or []
            completos = isinstance(tiros, list) and (ss.get("totalShots") is None or len(tiros) == ss.get("totalShots")) \
                and (d.get("goles") is None or sum(1 for r in rm if r["tipo"] == "gol") == d.get("goles"))
            if rm and not completos:
                b["avisos"].append("No se marcaron los remates en el mapa: no coinciden con la estadística del partido")
            if len(calor) >= 5:
                from mapa_sofascore import dibujar_horizontal
                os.makedirs(os.path.join(salida, "mapas"), exist_ok=True)
                mapa = f"mapas/{j['clave']}_{d['fecha']}.png"
                dibujar_horizontal(calor, os.path.join(salida, mapa), j.get("zona"),
                                   remates=rm if completos else None)
                b["heat_img"] = mapa
                if j.get("zona") in ZONAS:
                    titulo, en = ZONAS[j["zona"]]
                    k = sum(1 for p in calor if en(p["y"]))
                    zf = [["Acciones", f"{k}/{len(calor)} ({round(k * 100 / len(calor))}%)", True]]
                    # remates: solo si el mapa de remates trae todos los que cuenta la estadística. Su ancho viene al
                    # revés que el del mapa de calor (comprobado con 5 partidos): y = y_remate / 68 * 100
                    if con_ataque and isinstance(tiros, list) and len(tiros) == ss.get("totalShots"):
                        tz = [t for t in tiros if t.get("y") is not None and en(t["y"] / 68 * 100)]
                        zf.append(["Remates al arco", f"{sum(1 for t in tz if t.get('isOnTarget') and not t.get('isBlocked'))}/{len(tz)}", True])
                    if con_ataque and d.get("asistencias") == 0:
                        zf.append(["Asistencias", "0", False])
                    b["zona"] = {"titulo": titulo, "filas": zf}
            else:
                b["avisos"].append("No hay mapa de calor de este partido en el respaldo: se muestra el perfil" + (f" ({d['aviso_calor']})" if d.get("aviso_calor") else ""))
            # temporada: FotMob (+ nota promediada con API-Football si la trae)
            tm = []
            comps = dict(d.get("temporada") or {})
            copas = d.get("copas") or {}
            # la competición del partido primero; después la liga o la copa internacional que juegue (entran dos)
            # (la del partido se busca por el id del torneo; las fases previas, "Qualification", solo si no hay otra)
            de_este = next((c for c, v in copas.items() if d.get("liga_id") and v.get("liga_id") == d.get("liga_id")), None) \
                or next((c for c, v in copas.items() if fuentes.norm(c) == fuentes.norm(d.get("torneo") or "")), None)
            if de_este:
                comps = {de_este: copas[de_este], **comps}
            elif copas:
                c0 = sorted(copas, key=lambda c: "qualif" in fuentes.norm(c))[0]; comps[c0] = copas[c0]
            for comp, v in list(comps.items())[:2]:
                otras = [x.get("nota") for c2, x in (af.get("temporada") or {}).items() if _comp(c2) == _comp(comp)]
                tm.append([comp.upper(), " "])
                if v.get("pj") is not None: tm.append(["PJ (tit.) · Min.", f"{v['pj']} ({v.get('tit', '?')}) · {v.get('min', '?')}"])
                nota_t = fuentes.promedio([v.get("nota")] + otras)
                if nota_t: tm.append(["Nota media", f"{nota_t:.2f}"])
                if v.get("goles") is not None: tm.append(["Goles · Asist.", f"{v['goles']} · {v.get('asist', 0)}"])
                if v.get("amarillas") is not None or v.get("rojas") is not None:
                    tm.append(["Tarjetas", f"{v.get('amarillas') or 0}[A] · {v.get('rojas') or 0}[R]"])
                if "temporada_sub" not in b:
                    b["temporada_sub"] = (v.get("season") or "").replace("20", "", 1).replace("/20", "/") if v.get("season") else ""
            b["temporada"] = tm
            lp = []
            if d.get("goles"): lp.append(f"{d['goles']} gol" + ("es" if d["goles"] > 1 else ""))
            if d.get("asistencias"): lp.append(f"{d['asistencias']} asistencia" + ("s" if d["asistencias"] > 1 else ""))
            if pateo: lp.append(f"{pateo['resultado']} su penal en la tanda")
            if isinstance(st.get("accurate_passes"), (list, tuple)): lp.append(f"{st['accurate_passes'][0]}/{st['accurate_passes'][1]} pases")
            if st.get("duel_won"): lp.append(f"{st['duel_won']} duelo" + ("s ganados" if st["duel_won"] > 1 else " ganado"))
            if st.get("recoveries"): lp.append(f"{st['recoveries']} recuperaci" + ("ones" if st["recoveries"] > 1 else "ón"))
            b["linea_posteo"] = " · ".join(lp)
            # parte de abajo por puesto y texto del 3-5-2 (abajo_puesto.py); si falla, sale con el diseño anterior
            try:
                import abajo_puesto
                ap = abajo_puesto.armar(j, d, dj, salida, f"mapas/{j['clave']}_{d['fecha']}.png", b.get("su_partido") or [])
                if ap:
                    b["abajo"] = ap["abajo"]
                    b["heat_img"] = ap["abajo"].get("heat_img") or b.get("heat_img")
                    b["texto_352"] = abajo_puesto.texto_352(j, ap)
            except Exception as ex:
                b["avisos"].append(f"No se pudo armar la parte de abajo por puesto ({type(ex).__name__}: {ex}); sale con el diseño anterior")
            if not b["posicion"]: b["avisos"].append("No se pudo saber el puesto en el que jugó")
        os.makedirs(os.path.join(salida, "respaldo"), exist_ok=True)
        jp = os.path.join(salida, "respaldo", f"{j['clave']}_{d['fecha']}.json")
        json.dump(b, open(jp, "w"), ensure_ascii=False, indent=1)
        cmd = [sys.executable, os.path.join(AQUI, "armar_besoccer.py"), jp, "--salida", salida]
        if proc_path: cmd += ["--procesados", proc_path]
        subprocess.run(cmd, check=True)
    return True


def escudo_fotmob(team_id):
    """Escudo de un equipo desde FotMob (se guarda en escudos/fotmob_<id>.png). Si la red no lo deja, None."""
    ruta = os.path.join(AQUI, "escudos", f"fotmob_{team_id}.png")
    if os.path.exists(ruta): return ruta
    try:
        import urllib.request
        req = urllib.request.Request(f"https://images.fotmob.com/image_resources/logo/teamlogo/{team_id}.png",
                                     headers={"User-Agent": fuentes.UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            datos = r.read()
        if datos[:4] != b"\x89PNG": return None
        open(ruta, "wb").write(datos)
        return ruta
    except Exception:
        return None


def _club(j):
    return j.get("club") or next((v for k, v in (j.get("equipos") or {}).items() if k != "7"), "")


def _comp(n):
    from infografia_sofascore import comp_clave
    return comp_clave(n)
