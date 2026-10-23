"""Boceto (23/10/2026): parte de abajo reacomodada según el puesto, y texto del posteo sobre Uruguay en 3-5-2 con enganche.

Arriba queda igual (plantilla render_v3.py, que no se toca). Abajo:
- SU PARTIDO: más estadísticas de lo que hizo.
- ESPERADOS Y MÁS: lo esperado (xG, xA...) y lo que no entra en SU PARTIDO.
- MAPA DE CALOR (con remates) + barra "dónde jugó" (izquierda / centro / derecha y campo rival) +
  SU ZONA (la franja donde más jugó, con porcentajes) + PERFIL según el puesto en ese partido
  (delantero, enganche, volante por fuera, mediocentro, defensor central, lateral), solo con lo de ese puesto.
- TEMPORADA: igual que ahora.
El texto del posteo es una simulación: cómo encajaría en una Uruguay 3-5-2 con enganche (rol_352 de jugadores.json),
con los números reales de su partido.

Uso, desde la raíz:  python3 pruebas/bocetos_diseno/codigo/perfil_posicion.py darwin 2026-10-20 [zalazar 2026-09-09 ...]
No le hace pedidos a API-Football. Deja 7_perfil_<clave>.png y 7_perfil_<clave>_texto.txt en pruebas/bocetos_diseno/.
"""
import asyncio, datetime, glob, json, os, sys, tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
AUTO = os.path.join(RAIZ, "automatizacion")
DESTINO = os.path.join(RAIZ, "pruebas", "bocetos_diseno")
sys.path.insert(0, AUTO)
import fuentes, respaldo_auto, render_v3 as R
from mapa_sofascore import dibujar_horizontal
from playwright.async_api import async_playwright

fuentes._AF_SIN_PLAN = "boceto: sin pedidos a API-Football"
fuentes.DESDE = datetime.date(2000, 1, 1)   # solo en este boceto: deja usar partidos anteriores al 18/10

CSS_EXTRA = """
.cards.a .card.dos .row.c{font-size:15.5px;padding:0 0 .5px}.cards.a .card.dos .row.c b{font-size:17px}
.card.sp{flex:1.2}.card.esp{flex:1}.cols{display:flex;gap:26px}.cols > div{flex:1;min-width:0}
.card.calor2{flex:2.1;display:flex;flex-direction:column}
.calor2 .cuerpo{display:flex;gap:18px;flex:1;min-height:0}
.calor2 .izq{display:flex;flex-direction:column;gap:7px}
.calor2 .izq img{height:194px;border-radius:10px;box-shadow:0 6px 18px rgba(0,0,0,.35)}
.barra{display:flex;height:22px;border-radius:6px;overflow:hidden;font-weight:800;font-size:14px;letter-spacing:.5px}
.barra div{display:flex;align-items:center;justify-content:center;color:#14171a;background:#9aa4ab;white-space:nowrap;overflow:hidden}
.barra div.max{background:#f2c14e}.barra div + div{border-left:2px solid rgba(15,18,21,.86)}
.donde{display:flex;justify-content:space-between;font-weight:700;font-size:15px;color:#cfd8de;letter-spacing:.3px}
.donde b{color:#fff;font-weight:800}
.calor2 .der{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center}
.calor2 .der .zt{font-size:17px;margin:0 0 1px}
.calor2 .der .zt + .row{border-top:none}
.calor2 .der .row{font-size:16.5px;padding:3px 0 2px}.calor2 .der .row b{font-size:18px}
.calor2 .der .sep{height:8px}
"""

PERFILES = {
    "delantero": "PERFIL DE DELANTERO", "enganche": "PERFIL DE ENGANCHE", "por_fuera": "PERFIL DE VOLANTE POR FUERA",
    "mediocentro": "PERFIL DE MEDIOCENTRO", "central": "PERFIL DE DEFENSOR CENTRAL", "lateral": "PERFIL DE LATERAL",
}
LADOS = {"izquierda": "POR LA IZQUIERDA", "centro": "POR EL CENTRO", "derecha": "POR LA DERECHA"}


def fr(v, minimo_dorado=60):
    """[a, b] -> fila 'a/b (p%)' (dorado si el porcentaje es alto)."""
    if not isinstance(v, (list, tuple)) or len(v) != 2 or not v[1]:
        return None
    p = round(v[0] * 100 / v[1])
    return f"{v[0]}/{v[1]} ({p}%)", p >= minimo_dorado


def tipo_perfil(dj, p):
    pu = dj["puesto"]
    if pu == "delantero": return "delantero"
    if pu in ("volante por izquierda", "volante por derecha"): return "por_fuera"
    if pu == "defensor central": return "central"
    if pu in ("lateral izquierdo", "lateral derecho"): return "lateral"
    if pu == "mediocentro": return "enganche" if p.get("posicion_id") in (84, 85, 86) and dj.get("enganche") else "mediocentro"
    return None


def filas_perfil(t, st):
    duelos = [st.get("duel_won"), (st.get("duel_won") or 0) + (st.get("duel_lost") or 0)] if st.get("duel_won") is not None else None
    al_arco = [st.get("ShotsOnTarget") or 0, st.get("total_shots")] if st.get("total_shots") else None
    c = {
        "remates": ("Remates al arco", fr(al_arco, 50)),
        "goles_xg": ("Goles · xG", (f"{st.get('goals', 0)} · {st['expected_goals']:.2f}".replace(".", ","), False) if st.get("expected_goals") is not None else None),
        "area": ("Toques en el área rival", (str(st["touches_opp_box"]), st["touches_opp_box"] >= 5) if st.get("touches_opp_box") is not None else None),
        "duelos": ("Duelos ganados", fr(duelos)),
        "regates": ("Regates", fr(st.get("dribbles_succeeded"))),
        "aereos": ("Duelos aéreos ganados", fr(st.get("aerials_won"))),
        "ocasiones": ("Ocasiones creadas", (str(st["chances_created"]), st["chances_created"] >= 2) if st.get("chances_created") is not None else None),
        "tercio": ("Pases al último tercio", (str(st["passes_into_final_third"]), st["passes_into_final_third"] >= 5) if st.get("passes_into_final_third") is not None else None),
        "rompen": ("Pases que rompen líneas", (str(st["line_breaking_passes"]), st["line_breaking_passes"] >= 5) if st.get("line_breaking_passes") is not None else None),
        "pases": ("Pases precisos", fr(st.get("accurate_passes"), 85)),
        "largos": ("Pases largos precisos", fr(st.get("long_balls_accurate"))),
        "centros": ("Centros precisos", fr(st.get("accurate_crosses"), 40)),
        "recup": ("Recuperaciones", (str(st["recoveries"]), st["recoveries"] >= 6) if st.get("recoveries") is not None else None),
        "suelo": ("Duelos en el piso", fr(st.get("ground_duels_won"))),
        "despejes": ("Despejes", (str(st["clearances"]), st["clearances"] >= 5) if st.get("clearances") is not None else None),
        "interc": ("Intercepciones", (str(st["interceptions"]), st["interceptions"] >= 3) if st.get("interceptions") is not None else None),
        "entradas": ("Entradas", (str(st["matchstats.headers.tackles"]), st["matchstats.headers.tackles"] >= 3) if st.get("matchstats.headers.tackles") is not None else None),
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


def su_partido(st, base_rows):
    def n(k): return st.get(k)
    duelos = [n("duel_won"), (n("duel_won") or 0) + (n("duel_lost") or 0)] if n("duel_won") is not None else None
    filas = [["Goles", n("goals"), bool(n("goals"))], ["Asistencias", n("assists"), bool(n("assists"))]]
    filas += [r for r in base_rows if r[0] == "Penal en la tanda"]
    for et, v in (("Toques", n("touches")), ("Pases precisos", fr(n("accurate_passes"), 101)), ("Duelos ganados", fr(duelos, 101)),
                  ("Duelos aéreos ganados", fr(n("aerials_won"), 101)), ("Regates", fr(n("dribbles_succeeded"), 101)),
                  ("Recuperaciones", n("recoveries")), ("Intercepciones", n("interceptions")), ("Entradas", n("matchstats.headers.tackles")),
                  ("Despejes", n("clearances")), ("Faltas cometidas", n("fouls")), ("Faltas recibidas", n("was_fouled")),
                  ("Pérdidas de balón", n("dispossessed"))):
        if v is None: continue
        filas.append([et, v[0] if isinstance(v, tuple) else v, False])
    filas += [r for r in base_rows if r[0] == "Tarjetas"]
    return [[k, str(v), g] for k, v, g in filas if v is not None]


def esperados(st, ya):
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
    return f, (mas[:8] if len(mas) > 1 else [])


def zonas(calor, remates):
    n = len(calor)
    cuenta = {"izquierda": [q for q in calor if q["y"] > 200 / 3], "centro": [q for q in calor if 100 / 3 <= q["y"] <= 200 / 3],
              "derecha": [q for q in calor if q["y"] < 100 / 3]}
    lado = max(cuenta, key=lambda k: len(cuenta[k]))
    en = {"izquierda": lambda y: y > 200 / 3, "centro": lambda y: 100 / 3 <= y <= 200 / 3, "derecha": lambda y: y < 100 / 3}[lado]
    k = len(cuenta[lado]); m = sum(1 for q in cuenta[lado] if q["x"] > 50)
    filas = [["Acciones", f"{k}/{n} ({round(k * 100 / n)}%)", True], ["En campo rival", f"{m}/{k} ({round(m * 100 / k)}%)" if k else "0", False]]
    rz = [r for r in remates or [] if en(r["y"])]
    if rz:
        filas.append(["Remates · al arco", f"{len(rz)} · {sum(1 for r in rz if r['tipo'] in ('gol', 'al_arco'))}", False])
    pct = {l: round(len(v) * 100 / n) for l, v in cuenta.items()}
    return lado, filas, pct, round(sum(1 for q in calor if q["x"] > 50) * 100 / n)


def hechos(st, pct, lado, rival):
    """Lo que juega a favor en cada rol (solo números reales y positivos), para el texto."""
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
    h["lado"] = f"{pct[lado]}% de sus acciones {dict(izquierda='por la izquierda', centro='por el centro', derecha='por la derecha')[lado]}"
    if rival >= 50: h["rival"] = f"{rival}% en campo rival"
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


def texto_352(j, p, b, st, lado, pct, rival, tipo):
    """Texto del posteo (simulado): su partido + cómo encajaría en una Uruguay 3-5-2 con enganche (rol_352)."""
    nombre = j["placa"].title()
    pa = b["partido"]
    tanda = f" ({fuentes.texto_tanda(pa['tanda'], largo=True)})" if pa.get("tanda") else ""
    puesto = "enganche" if tipo == "enganche" else (respaldo_auto.donde_jugo(p, str(j["fotmob_id"]))["puesto"] or "titular")
    hs = hechos(st, pct, lado, rival)
    claves, plantilla = ROLES_352.get(j.get("rol_352"), ([], ""))
    # lo que dice el párrafo del 3-5-2 no se repite arriba (salvo los goles)
    del_rol = [k for k in claves if hs.get(k)][:3]
    primeras = [k for k in ("lado", "goals", "pases", "duelos", "recoveries", "passes_into_final_third", "chances_created") if k == "goals" or k not in del_rol]
    partido = lista([hs.get(k) for k in primeras if hs.get(k)][:4])
    usados = set()
    rol = plantilla.format(lado={"izquierda": " por izquierda", "derecha": " por derecha"}.get(lado, ""),
                           hechos=lista([hs[k] for k in claves if hs.get(k)][:3])) if plantilla else ""
    return "\n".join([
        f"🇺🇾 {nombre} · {pa['local']} {pa['goles_local']}-{pa['goles_visita']} {pa['visita']}{tanda}",
        f"⏱ {b['minutos']}' · ⭐ {b['nota']:.1f}" if b.get("nota") else f"⏱ {b['minutos']}'",
        "",
        f"Jugó de {puesto}: {partido}." if partido else f"Jugó de {puesto}.",
        "",
        "🧩 ¿Y en una Uruguay 3-5-2 con enganche?",
        rol,
        "",
        "Tres atrás, dos carrileros, dos internos, un 10 suelto y dos puntas. ¿Lo jugarías así? 👇",
        "#CelestesPorElMundo #Uruguay #352",
    ])


def armar(clave, fecha_s):
    fecha = datetime.date.fromisoformat(fecha_s)
    j = next(x for x in json.load(open(os.path.join(AUTO, "jugadores.json"))) if x["clave"] == clave)
    tmp = tempfile.mkdtemp()
    respaldo_auto.armar(j, {fecha}, tmp, None, forzar=True)
    jp = next(q for q in glob.glob(os.path.join(tmp, "*.json")) if not q.endswith("resumen.json"))
    d = json.load(open(jp))[0]
    b = json.load(open(glob.glob(os.path.join(tmp, "respaldo", "*.json"))[0]))
    p = next(x for x in fuentes.fotmob(j, {fecha})[0] if x.get("minutos"))
    st = p.get("stats") or {}
    dj = respaldo_auto.donde_jugo(p, str(j["fotmob_id"]))
    tipo = tipo_perfil(dj, p)
    mapa = os.path.join(tmp, "mapas", f"{clave}_{fecha_s}_perfil.png")
    os.makedirs(os.path.dirname(mapa), exist_ok=True)
    rm = p.get("remates_mapa") or []
    goles_ok = st.get("goals") is None or sum(1 for r in rm if r["tipo"] == "gol") == st.get("goals")
    dibujar_horizontal(p["calor"], mapa, None, remates=rm if goles_ok else None)
    lado, zf, pct, rival = zonas(p["calor"], rm)
    pf, ya = filas_perfil(tipo, st) if tipo else ([], set())
    sp = su_partido(st, d.get("generales") or [])
    esp = esperados(st, ya | {"area"} if tipo == "delantero" else ya)
    texto = texto_352(j, p, b, st, lado, pct, rival, tipo)

    barra = "".join(f'<div class="{"max" if pct[l] == max(pct.values()) else ""}" style="flex:{max(pct[l], 0.001)}">{f"{pct[l]}%" if pct[l] >= 10 else ""}</div>'
                    for l in ("izquierda", "centro", "derecha") if pct[l] > 0)
    izq = (f'<img src="{R.b64(mapa)}"><div class="barra">{barra}</div>'
           f'<div class="donde"><span>IZQ <b>{pct["izquierda"]}%</b> · CENTRO <b>{pct["centro"]}%</b> · DER <b>{pct["derecha"]}%</b></span>'
           f'<span>CAMPO RIVAL <b>{rival}%</b></span></div>')
    der = (f'<div class="zt">SU ZONA: {LADOS[lado]}</div>{R.rows(zf)}<div class="sep"></div>'
           + (f'<div class="zt">{PERFILES[tipo]}</div>{R.rows(pf)}' if pf else ""))
    ex = d.get("extra") or {}
    fila_b = (f'<div class="card calor2"><h3>MAPA DE CALOR<small>DÓNDE JUGÓ</small></h3><div class="cuerpo"><div class="izq">{izq}</div>'
              f'<div class="der">{der}</div></div></div>'
              f'<div class="card"><h3>{R.esc(ex.get("titulo", "TEMPORADA"))}<small>{R.esc(ex.get("sub", ""))}</small></h3>{R.rows(ex.get("filas", [])[:10], True)}</div>')
    fila_a = (f'<div class="card dos sp apretado"><h3>SU PARTIDO</h3><div class="lista">{R.rows(sp[:16], True)}</div></div>'
              f'<div class="card dos esp apretado"><h3>ESPERADOS Y MÁS</h3><div class="cols"><div>{R.rows(esp[0], True)}</div>'
              f'<div>{R.rows(esp[1], True)}</div></div></div>')
    d2 = dict(d); d2.update({"generales": [], "posicion": [], "zona": None, "heat_img": None, "extra": {}, "perfil": []})
    h = R.html(R._abs(d2, tmp), tmp)
    h = h.replace('<div class="cards a"></div>', f'<div class="cards a">{fila_a}</div>')
    h = h.replace('<div class="cards b"></div>', f'<div class="cards b">{fila_b}</div>')
    h = h.replace("</style></head>", CSS_EXTRA + "</style></head>")
    return h, texto


async def main(pares):
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": R.W, "height": R.HH}, device_scale_factor=R.ESCALA)
        for clave, fecha in pares:
            h, texto = armar(clave, fecha)
            hp = os.path.join(tempfile.mkdtemp(), "boceto.html")
            open(hp, "w").write(h)
            await pg.goto("file://" + hp)
            await pg.evaluate("document.fonts.ready")
            await pg.wait_for_timeout(300)
            png = os.path.join(DESTINO, f"7_perfil_{clave}.png")
            await pg.screenshot(path=png)
            open(png[:-4] + "_texto.txt", "w").write(texto + "\n")
            print("OK", png)
        await b.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(list(zip(a[::2], a[1::2]))))
