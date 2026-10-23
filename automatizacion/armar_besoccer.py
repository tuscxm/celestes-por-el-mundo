"""Respaldo: arma la infografía con datos de BeSoccer cuando SofaScore no respondió.

BeSoccer no deja entrar a los scripts desde la nube, así que los datos los lee la tarea de Claude
con su herramienta web y los escribe en un JSON con el formato de besoccer_plantilla.json.
Este script arma la infografía con la misma plantilla (render_v3.py), escribe el texto del posteo,
actualiza salida_hoy/resumen.json (reemplaza el "error" de ese jugador) y procesados.json.

Uso: python3 automatizacion/armar_besoccer.py datos_bs.json --salida salida_hoy --procesados automatizacion/procesados.json
Nunca inventa: lo que falte en el JSON (null o ausente) no se muestra."""
import json, os, sys, shutil, subprocess, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from infografia_sofascore import MESES, estrellas, tema
import fuentes

ROLES = {"arquero": "COMO ARQUERO", "lateral derecho": "COMO LATERAL DERECHO", "lateral izquierdo": "COMO LATERAL IZQUIERDO",
         "defensor central": "COMO DEFENSOR CENTRAL", "mediocentro": "COMO MEDIOCENTRO", "volante por derecha": "COMO VOLANTE POR DERECHA",
         "volante por izquierda": "COMO VOLANTE POR IZQUIERDA", "delantero": "COMO DELANTERO"}


def sin_tildes(t):
    for a, b in (("ñ", "n"), ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("Ñ", "N"), ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")):
        t = t.replace(a, b)
    return t


def main():
    a = sys.argv[1:]
    def opt(k, dflt=None):
        return a[a.index(k) + 1] if k in a else dflt
    b = json.load(open(a[0]))
    salida = os.path.abspath(opt("--salida", "salida_hoy")); os.makedirs(salida, exist_ok=True)
    proc_path = opt("--procesados")
    jugs = {j["clave"]: j for j in json.load(open(os.path.join(AQUI, "jugadores.json")))}
    j = jugs[b["clave"]]
    fecha = datetime.date.fromisoformat(b["fecha"])
    pa = b.get("partido") or {}
    info = {"estado": b.get("estado", "jugó"), "fecha": b["fecha"], "fuente_respaldo": True,
            "partido": (f"{pa.get('local','')} {pa.get('goles_local','')}-{pa.get('goles_visita','')} {pa.get('visita','')}".strip()
                        + (f" ({fuentes.texto_tanda(pa['tanda'])})" if pa.get("tanda") else "")),
            "torneo": pa.get("torneo", "")}
    avisos = list(b.get("avisos") or []) + ([] if b.get("estado", "jugó") != "jugó" else [f"Armada con datos de respaldo ({b.get('fuente_respaldo', 'BeSoccer')}): hay menos estadísticas que de costumbre, revisala antes de publicar"])

    if info["estado"] == "jugó":
        seleccion = bool(pa.get("seleccion"))
        cams = j.get("camiseta", {})
        cam = (cams.get("7") if seleccion else next((v for k, v in cams.items() if k != "7"), None)) or next(iter(cams.values()))
        apellido = b.get("apellido") or j["placa"].split()[-1].title()
        cara = os.path.join(AQUI, "caras", f"{j['clave']}.png")
        cara = cara if os.path.exists(cara) else None
        if not seleccion:
            from caras import cara_oficial
            cara = cara_oficial(j["clave"], os.path.join(salida, "recursos"), j.get("foto_oficial")) or cara
        if not cara and j.get("sofascore_id"):
            # sin cara guardada: se baja la de SofaScore (img.sofascore.com responde aunque la API no) y queda en caras/
            from caras import cara as bajar_cara
            cara = bajar_cara(j["sofascore_id"], os.path.join(salida, "recursos"), j["clave"])
        esc = os.path.join(AQUI, "escudos", ("uruguay" if seleccion else f"club_{j['clave']}") + ".png")
        esc = esc if os.path.exists(esc) else None
        # escudo del rival, si está guardado (escudos/fotmob_<id>.png, lo baja respaldo_auto.py)
        esc_rival = b.get("escudo_rival") if b.get("escudo_rival") and os.path.exists(b["escudo_rival"]) else None
        fig = None
        if not cara:
            from figura import figura
            os.makedirs(os.path.join(salida, "fotos"), exist_ok=True)
            fig = os.path.join(salida, "fotos", f"{j['clave']}_{fecha}.svg")
            open(fig, "w").write(figura(os.path.join(AQUI, "fotos", "bernal_espalda_ancho.svg"), apellido, b.get("dorsal", ""), cam))
            avisos.append("No hay foto guardada del jugador: se usó la figura ilustrada")
        local_es_mio = bool(pa.get("local_es_su_equipo", True))
        once = []
        for linea in b.get("once") or []:
            once.append([{"dorsal": p[0], "nombre": p[1], "cara": cara if str(p[0]) == str(b.get("dorsal")) else None,
                          "estrellas": estrellas(float(p[2])) if len(p) > 2 and p[2] else 0, "yo": str(p[0]) == str(b.get("dorsal")),
                          # tarjetas (opcional, 4.º elemento): {"roja": "54’"} o {"amarillas": 1}
                          "roja": (p[3] or {}).get("roja") if len(p) > 3 and isinstance(p[3], dict) else None,
                          "amarillas": (p[3] or {}).get("amarillas") if len(p) > 3 and isinstance(p[3], dict) else None} for p in linea])
        if not once:
            avisos.append("Sin alineación en el respaldo: la cancha va vacía")
        pos0 = ROLES.get((b.get("posicion") or "").lower(), "SU JUEGO")
        en = b.get("entro") or {}
        sustitucion = None
        if en.get("por") and not b.get("titular"):
            mins = f"{en.get('minuto')}’" if en.get("minuto") is not None else ""
            sustitucion = {"minuto": mins, "por": en["por"], "apellido": apellido, "cara": cara,
                           "rol": pos0.replace("COMO ", "").lower() if pos0 != "SU JUEGO" else ""}
            for linea in once:
                for f in linea:
                    if en["por"].lower() in f["nombre"].lower() or f["nombre"].lower() in en["por"].lower():
                        f["sale"] = True
        nota = b.get("nota")
        generales = [[x[0], str(x[1]), bool(x[2]) if len(x) > 2 else False] for x in (b.get("su_partido") or [])]
        nac = j.get("nacimiento")
        edad = None
        if nac:
            bd = datetime.date.fromisoformat(nac); edad = fecha.year - bd.year - ((fecha.month, fecha.day) < (bd.month, bd.day))
        pos = ROLES.get((b.get("posicion") or "").lower(), "SU JUEGO")
        perfil = [["DORSAL", b.get("dorsal") or "—"], ["EDAD", f"{edad} años" if edad else "—"], ["ALTURA", j.get("altura", "—")],
                  ["PIE", j.get("pie", "—")], ["POSICIÓN", pos.replace("COMO ", "").title()]]
        archivo = sin_tildes(f"{apellido}_{pa.get('local','').replace(' ', '')}-{pa.get('visita','').replace(' ', '')}_{fecha}")
        d = {"archivo": archivo, "nombre": j["placa"], "apellido": apellido, "dorsal": b.get("dorsal"),
             "local": pa.get("local", ""), "visita": pa.get("visita", ""), "goles_local": pa.get("goles_local", ""), "goles_visita": pa.get("goles_visita", ""),
             "escudo_local": esc if local_es_mio else esc_rival, "escudo_visita": esc_rival if local_es_mio else esc, "escudo_club": esc,
             "meta": " · ".join(x for x in [pa.get("torneo", "").upper(), (pa.get("ronda") or "").upper(),
                                            f"PENALES {pa['tanda']['local']}-{pa['tanda']['visita']}" if pa.get("tanda") else "",
                                            f"{fecha.day} {MESES[fecha.month-1]} {fecha.year}"] if x),
             "condicion": "TITULAR" if b.get("titular") else "SUPLENTE",
             "minutos": f"{b.get('minutos', '')}’", "nota": f"{float(nota):.1f}" if nota else None, "estrellas": estrellas(float(nota)) if nota else 0,
             "tema": tema(cam, {}), "sustitucion": sustitucion, "formacion": b.get("formacion", ""), "once": once, "cara": cara, "foto": fig,
             "generales": generales, "pos_titulo": pos, "posicion": [[x[0], str(x[1]), bool(x[2]) if len(x) > 2 else False] for x in (b.get("estadisticas") or [])],
             "extra": {"titulo": "TEMPORADA", "sub": b.get("temporada_sub", ""), "filas": [[k, str(v), False] for k, v in (b.get("temporada") or [])]},
             "heat_img": b.get("heat_img"), "heat_horizontal": True, "zona": b.get("zona"), "perfil": perfil, "roja": b.get("roja")}
        jp = os.path.join(salida, archivo + ".json")
        json.dump([d], open(jp, "w"), ensure_ascii=False, indent=1)
        subprocess.run([sys.executable, os.path.join(AQUI, "render_v3.py"), jp], check=True)
        club_tag = "Uruguay" if seleccion else "".join(ch for ch in (b.get("equipo") or pa.get("local", "")) if ch.isalnum())
        copy = (f"🇺🇾 {j['placa']} · {pa.get('local','')} {pa.get('goles_local','')}-{pa.get('goles_visita','')} {pa.get('visita','')}"
                + (f" ({fuentes.texto_tanda(pa['tanda'], largo=True)})" if pa.get("tanda") else "") + "\n")
        copy += f"⏱ {b.get('minutos','')}'" + (f" · ⭐ {float(nota):.1f}" if nota else "") + "\n"
        if sustitucion:
            copy += f"🔁 Entró" + (f" al {en.get('minuto')}'" if en.get("minuto") is not None else "") + f" por {en['por']}" + (f", como {sustitucion['rol']}" if sustitucion["rol"] else "") + "\n"
        if b.get("roja"):
            copy += "🟥 Expulsado" + (f" al {str(b['roja']).replace('’', chr(39))}" if isinstance(b["roja"], str) else "") + "\n"
        if b.get("linea_posteo"):
            copy += b["linea_posteo"] + "\n"
        copy += f"#CelestesPorElMundo #Uruguay #{club_tag}\n"
        open(os.path.join(salida, archivo + "_copy.txt"), "w").write(copy)
        info.update({"titular": bool(b.get("titular")), "minutos": b.get("minutos"), "nota": float(nota) if nota else None,
                     "rol": pos, "entro": ({"minuto": sustitucion["minuto"], "por": sustitucion["por"]} if sustitucion else None), "archivo": archivo, "png": archivo + ".png", "mapa": None, "figura": None})
    info["avisos"] = avisos

    # resumen.json: reemplaza el error de este jugador
    rp = os.path.join(salida, "resumen.json")
    res = json.load(open(rp)) if os.path.exists(rp) else {"revisado": datetime.datetime.now().isoformat(timespec="minutes"), "fechas": [b["fecha"]], "jugadores": []}
    ent = next((x for x in res["jugadores"] if x["clave"] == j["clave"]), None)
    if not ent:
        ent = {"clave": j["clave"], "nombre": j["placa"], "partidos": []}; res["jugadores"].append(ent)
    ent["partidos"] = [p for p in ent["partidos"] if p.get("estado") != "error" and p.get("fecha") != b["fecha"]] + [info]
    json.dump(res, open(rp, "w"), ensure_ascii=False, indent=1)
    if proc_path and info["estado"] == "jugó":
        pr = set(json.load(open(proc_path))) if os.path.exists(proc_path) else set()
        pr.add(f"{j['clave']}_{b['fecha']}")
        json.dump(sorted(pr), open(proc_path, "w"), indent=1)
    print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
