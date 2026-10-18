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


def armar(j, fechas, salida, proc_path):
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
    for d in fm:
        af = fuentes.del_partido(extra, d["fecha"], d["visita"] if fuentes.mismo_equipo(d["local"], _club(j)) else d["local"]).get("api_football") or {}
        b = {"clave": j["clave"], "fecha": d["fecha"], "fuente_respaldo": "FotMob", "apellido": j["placa"].split()[-1].title(),
             "equipo": _club(j), "avisos": [f"SofaScore no respondió; fuentes: " + ", ".join(f"{k} {v}" for k, v in extra["estado"].items())]}
        seleccion = "uruguay" in (fuentes.norm(d["local"]) + " " + fuentes.norm(d["visita"]))
        b["partido"] = {"local": d["local"], "visita": d["visita"], "goles_local": d.get("goles_local"), "goles_visita": d.get("goles_visita"),
                        "torneo": d.get("torneo") or "", "ronda": f"Jornada {d['ronda']}" if str(d.get("ronda") or "").isdigit() else (d.get("ronda") or ""),
                        "seleccion": seleccion,
                        "local_es_su_equipo": fuentes.mismo_equipo(d["local"], "Uruguay" if seleccion else _club(j))}
        if d.get("terminado") is False:
            b["estado"] = "no terminó"
        elif not d.get("minutos"):
            b["estado"] = "no jugó"
        else:
            b["estado"] = "jugó"
            st = d.get("stats") or {}
            notas = [d.get("nota"), af.get("nota")]
            b["nota"] = fuentes.promedio(notas)
            if len([x for x in notas if x]) > 1:
                b["avisos"].append(f"Nota = promedio de fotmob {d.get('nota')} · api_football {af.get('nota')} → {b['nota']}")
            b.update({"titular": bool(d.get("titular")), "minutos": d["minutos"], "dorsal": d.get("dorsal"),
                      "posicion": puesto(d.get("posicion_id")), "formacion": d.get("formacion") or ""})
            if d.get("entro") and not d.get("titular"):
                b["entro"] = {"minuto": d["entro"]["minuto"], "por": d["entro"]["por"]}
            ao = af.get("notas_once") or {}
            tj = d.get("tarjetas") or {}
            b["once"] = [[[p[0], p[1], fuentes.promedio([d["notas_once"].get(p[0]), ao.get(p[0])]), tj.get(str(p[2])) or {}] for p in linea]
                         for linea in d.get("once") or []]
            mia = tj.get(str(j.get("fotmob_id"))) or {}
            if mia.get("roja"): b["roja"] = mia["roja"]

            def frac(k):
                v = st.get(k)
                return f"{v[0]}/{v[1]}" if isinstance(v, (list, tuple)) and v[1] is not None else None
            am, ro = d.get("amarillas") or 0, d.get("rojas") or 0
            tarj = "0" if not (am or ro) else " + ".join(x for x in [f"{am} amarilla" + ("s" if am > 1 else "") if am else "", "roja" if ro else ""] if x)
            sp = [["Goles", d.get("goles"), bool(d.get("goles"))], ["Asistencias", d.get("asistencias"), bool(d.get("asistencias"))]]
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
            b["estadisticas"] = es[:10]
            # temporada: FotMob (+ nota promediada con API-Football si la trae)
            tm = []
            for comp, v in (d.get("temporada") or {}).items():
                otras = [x.get("nota") for c2, x in (af.get("temporada") or {}).items() if _comp(c2) == _comp(comp)]
                tm.append([comp.upper(), " "])
                if v.get("pj") is not None: tm.append(["PJ (tit.) · Min.", f"{v['pj']} ({v.get('tit', '?')}) · {v.get('min', '?')}"])
                nota_t = fuentes.promedio([v.get("nota")] + otras)
                if nota_t: tm.append(["Nota media", f"{nota_t:.2f}"])
                if v.get("goles") is not None: tm.append(["Goles · Asist. · Amar.", f"{v['goles']} · {v.get('asist', 0)} · {v.get('amarillas', 0)}"])
                b["temporada_sub"] = (v.get("season") or "").replace("20", "", 1).replace("/20", "/") if v.get("season") else ""
            b["temporada"] = tm
            lp = []
            if d.get("goles"): lp.append(f"{d['goles']} gol" + ("es" if d["goles"] > 1 else ""))
            if d.get("asistencias"): lp.append(f"{d['asistencias']} asistencia" + ("s" if d["asistencias"] > 1 else ""))
            if isinstance(st.get("accurate_passes"), (list, tuple)): lp.append(f"{st['accurate_passes'][0]}/{st['accurate_passes'][1]} pases")
            if st.get("duel_won"): lp.append(f"{st['duel_won']} duelo" + ("s ganados" if st["duel_won"] > 1 else " ganado"))
            if st.get("recoveries"): lp.append(f"{st['recoveries']} recuperaci" + ("ones" if st["recoveries"] > 1 else "ón"))
            b["linea_posteo"] = " · ".join(lp)
            if not b["posicion"]: b["avisos"].append("No se pudo saber el puesto en el que jugó")
        os.makedirs(os.path.join(salida, "respaldo"), exist_ok=True)
        jp = os.path.join(salida, "respaldo", f"{j['clave']}_{d['fecha']}.json")
        json.dump(b, open(jp, "w"), ensure_ascii=False, indent=1)
        cmd = [sys.executable, os.path.join(AQUI, "armar_besoccer.py"), jp, "--salida", salida]
        if proc_path: cmd += ["--procesados", proc_path]
        subprocess.run(cmd, check=True)
    return True


def _club(j):
    return j.get("club") or next((v for k, v in (j.get("equipos") or {}).items() if k != "7"), "")


def _comp(n):
    from infografia_sofascore import comp_clave
    return comp_clave(n)
