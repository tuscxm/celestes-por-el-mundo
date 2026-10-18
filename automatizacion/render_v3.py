"""Plantilla v3 'Celestes por el mundo': colores del club, cancha oscura y caras recortadas.
Uso: python3 render_v3.py datos.json  -> <archivo>.png al lado del json.

Campos de cada bloque del json (lista):
 archivo, nombre (placa grande), apellido (placa del jugador), dorsal,
 local, visita, goles_local, goles_visita, escudo_local, escudo_visita, escudo_club (rutas o null),
 meta (texto bajo el marcador), condicion ("TITULAR"/"SUPLENTE"),
 minutos, nota (texto o null), estrellas (0-5),
 tema {c1, c2, acento}  (fondo con los colores del club),
 formacion, once: líneas del arco al ataque, cada una de izquierda a derecha:
   {"dorsal", "nombre", "cara" (ruta o null), "estrellas", "yo" (bool)}
 cara (ruta a la cara recortada del jugador) o foto (figura de respaldo, svg/png),
 generales [[etiqueta, valor, dorado]], pos_titulo, posicion [[...]],
 extra {titulo, sub, filas}, heat_img (ruta) o null, perfil [[etiqueta, valor]].
Las rutas son relativas al json. Nunca muestra de dónde salen los datos."""
import json, os, sys, asyncio, base64, mimetypes, html as H

from playwright.async_api import async_playwright

if os.path.isdir("/opt/pw-browsers"):  # nube de Claude
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

AQUI = os.path.dirname(os.path.abspath(__file__))
W, HH = 1080, 1350


def b64(path):
    if not path or not os.path.exists(path):
        return None
    mt = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mt};base64," + base64.b64encode(open(path, "rb").read()).decode()


def fuentes():
    css = ""
    for w in (500, 600, 700, 800, 900):
        p = os.path.join(AQUI, "fuentes", f"barlow-condensed-latin-{w}-normal.woff2")
        if os.path.exists(p):
            css += (f"@font-face{{font-family:'BC';font-weight:{w};src:url(data:font/woff2;base64,"
                    f"{base64.b64encode(open(p, 'rb').read()).decode()}) format('woff2')}}\n")
    return css


def txt_sobre(hexa):
    h = hexa.lstrip("#"); r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return "#111" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#fff"


def esc(s):
    return H.escape(str(s)) if s is not None else ""


def estrellas_html(n, size=13):
    if not n:
        return ""
    return f'<div class="stars" style="font-size:{size}px">' + "★" * int(n) + "</div>"


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;position:relative;overflow:hidden;font-family:'BC','Barlow Condensed','Inter',Arial,sans-serif;color:#fff;
 background:#15181b}
.bg{position:absolute;inset:0;background:
   radial-gradient(ellipse 70% 45% at 50% 0%,rgba(255,255,255,.28),transparent 70%),
   linear-gradient(150deg,var(--c1) 0%,var(--c1) 38%,var(--c2) 100%)}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,0) 52%,rgba(10,12,14,.55) 72%,rgba(10,12,14,.92) 100%)}
.wm{position:absolute;left:50%;top:150px;width:1000px;height:1000px;transform:translateX(-50%);object-fit:contain;opacity:.16;
 filter:drop-shadow(0 20px 60px rgba(0,0,0,.35))}
.brand{position:absolute;top:30px;left:50%;transform:translateX(-50%);background:rgba(15,18,21,.62);border-radius:10px;
 padding:7px 18px;font-weight:800;font-size:21px;letter-spacing:4px;color:#9fd6f7;white-space:nowrap}
h1{position:absolute;top:70px;width:100%;text-align:center;font-weight:900;line-height:1;white-space:nowrap;text-transform:uppercase;letter-spacing:1px;
 text-shadow:0 4px 0 rgba(0,0,0,.22),0 0 2px rgba(0,0,0,.35),0 10px 28px rgba(0,0,0,.45)}
.score{position:absolute;top:192px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:16px;background:rgba(15,18,21,.78);
 border-radius:16px;padding:8px 22px;white-space:nowrap}
.score img{width:52px;height:52px;object-fit:contain}
.score .t{font-weight:800;font-size:34px;letter-spacing:.5px;text-transform:uppercase}
.score .r{font-weight:900;font-size:40px;background:var(--acento);color:var(--acento-txt);border-radius:10px;padding:0 14px;line-height:52px}
.meta{position:absolute;top:276px;width:100%;text-align:center;font-weight:700;font-size:21px;letter-spacing:3px;text-transform:uppercase;
 text-shadow:0 2px 8px rgba(0,0,0,.5)}
.meta .tag{background:#fff;color:#111;border-radius:6px;padding:1px 9px;margin-left:6px}
.meta .tag.sup{background:#f2c14e}
.pitch{position:absolute;left:24px;top:322px;width:520px;height:500px}
.form{position:absolute;left:10px;top:-2px;background:rgba(15,18,21,.8);border-radius:8px;padding:3px 10px;font-weight:800;font-size:17px;letter-spacing:2px;color:#9fd6f7;z-index:5}
.slot{position:absolute;display:flex;flex-direction:column;align-items:center;transform:translateX(-50%)}
.slot .ph{position:relative;display:flex;justify-content:center;align-items:flex-end}
.slot .ph::before{content:"";position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);width:140%;height:120%;
 background:radial-gradient(ellipse 50% 55% at 50% 70%,rgba(255,255,255,.30),rgba(255,255,255,0) 70%)}
.slot .ph img{position:relative;object-fit:cover;object-position:top}
.slot .num{position:relative;border-radius:50%;background:#e9ecef;color:#111;font-weight:900;display:flex;align-items:center;justify-content:center;border:3px solid #111}
.plate{position:relative;display:flex;align-items:center;margin-top:-4px;z-index:2}
.plate .n{background:#fff;color:#14171a;font-weight:800;text-transform:uppercase;white-space:nowrap;padding:2px 9px 1px 7px;transform:skewX(-8deg);
 box-shadow:0 3px 8px rgba(0,0,0,.35);overflow:hidden;text-overflow:ellipsis}
.plate .n span{display:inline-block;transform:skewX(8deg)}
.plate .cr{border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;margin-left:-6px;box-shadow:0 2px 6px rgba(0,0,0,.35)}
.plate .cr img{object-fit:contain}
.yo .plate .n{background:#f2c14e}
.slot.sale .ph > img,.slot.sale .ph > .num{opacity:.45;filter:grayscale(.6)}
.slot .entra{position:absolute;right:-26px;top:-14px;border-radius:50%;border:3px solid #f2c14e;background:rgba(20,22,25,.85);overflow:hidden;
 box-shadow:0 0 0 4px rgba(242,193,78,.3),0 4px 10px rgba(0,0,0,.4);z-index:3}
.slot .entra img{width:100%;height:100%;object-fit:cover;object-position:top}
.chip{background:#f2c14e;color:#14171a;font-weight:900;font-size:13px;letter-spacing:.5px;border-radius:6px;padding:1px 7px;margin-top:3px;white-space:nowrap;
 box-shadow:0 3px 8px rgba(0,0,0,.35);text-transform:uppercase}
.tile .x{font-weight:800;font-size:19px;letter-spacing:1px;color:#f2c14e;margin-top:4px;text-transform:uppercase}
.tab{background:#1b1e21;border-radius:0 0 7px 7px;padding:0 8px 1px;margin-top:-1px}
.stars{color:#f2c14e;letter-spacing:1px;line-height:1.1}
.hero{position:absolute;left:560px;top:318px;width:496px;height:360px}
.hero .glow{position:absolute;left:8px;right:8px;top:0;bottom:30px;background:radial-gradient(ellipse 50% 55% at 50% 62%,rgba(255,255,255,.55),rgba(255,255,255,0) 72%)}
.hero .face{position:absolute;left:50%;top:0;transform:translateX(-50%);width:300px;height:300px;object-fit:cover;object-position:top;
 -webkit-mask-image:linear-gradient(180deg,#000 82%,transparent 100%)}
.hero .fig{position:absolute;left:50%;top:-6px;transform:translateX(-50%);height:300px;border-radius:18px}
.hero .plate{position:absolute;left:50%;top:268px;transform:translateX(-50%)}
.hero .plate .n{font-size:44px;padding:2px 20px 0 16px}
.hero .plate .cr{width:66px;height:66px;margin-left:-10px}
.hero .plate .cr img{width:52px;height:52px}
.hero .dorsal{position:absolute;right:18px;top:16px;font-weight:900;font-size:64px;color:rgba(255,255,255,.92);text-shadow:0 4px 16px rgba(0,0,0,.45)}
.hero .tab{position:absolute;left:50%;top:328px;transform:translateX(-50%);padding:1px 14px 3px}
.tiles{position:absolute;left:576px;top:690px;width:480px;display:flex;gap:16px}
.tile{flex:1;height:132px;background:rgba(15,18,21,.84);border-radius:18px;display:flex;flex-direction:column;align-items:center;justify-content:center}
.tile .v{font-weight:900;font-size:76px;line-height:.95}
.tile .l{font-weight:700;font-size:18px;letter-spacing:4px;color:#b8c2c9;margin-top:6px}
.cards{position:absolute;left:24px;right:24px;top:838px;height:442px;display:flex;gap:16px}
.card.calor{flex:1.45}
.card{flex:1;background:rgba(15,18,21,.86);border-radius:18px;padding:16px 16px 12px;min-width:0;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;left:0;top:0;right:0;height:5px;background:var(--acento)}
.card h3{font-weight:800;font-size:21px;letter-spacing:1.5px;color:#9fd6f7;margin:2px 0 8px;white-space:nowrap;display:flex;justify-content:space-between;align-items:baseline}
.card h3 small{font-size:14px;color:#b8c2c9;letter-spacing:1px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:6px;font-weight:600;font-size:19px;padding:6px 0 5px;border-bottom:1px solid rgba(255,255,255,.07);white-space:nowrap}
.row:last-child{border-bottom:none}
.row span{overflow:hidden;text-overflow:ellipsis;color:#e6ebee}
.row b{font-weight:800;font-size:20px}
.row.h span{font-weight:800;color:#fff;letter-spacing:1px}
.gold{color:#f2c14e}
.heat{display:flex;justify-content:center}
.heat img{height:360px;border-radius:10px}
.heat.chica img{height:186px}
.zt{font-weight:800;font-size:19px;letter-spacing:1.5px;color:#f2c14e;margin:8px 0 2px}
.foot{position:absolute;left:28px;right:28px;bottom:16px;display:flex;justify-content:space-between;align-items:center}
.wordmark{font-weight:900;font-size:30px;letter-spacing:1px;text-transform:uppercase;line-height:1}
.wordmark i{font-style:normal;color:#9fd6f7}
.wordmark::after{content:"";display:block;height:4px;width:70%;margin-top:3px;border-radius:2px;background:linear-gradient(90deg,#9fd6f7,#9fd6f7 50%,#fff 50%,#fff)}
.hash{font-weight:700;font-size:20px;letter-spacing:2px;color:#cfd8de}
.tarj{position:absolute;right:-4px;top:6px;display:flex;gap:0;z-index:4}
.tarj i{display:block;width:17px;height:23px;border-radius:3px;border:1.5px solid rgba(0,0,0,.6);box-shadow:0 2px 5px rgba(0,0,0,.5)}
.tarj i + i{margin-left:-7px;transform:rotate(12deg)}
.tarj i.am{background:#f7d117}.tarj i.ro{background:#e0252b}
.hero .tarj{left:auto;right:26px;top:100px}
.hero .tarj i{width:30px;height:42px;border-radius:5px;border-width:2px}
.hero .tarj i + i{margin-left:-12px}
.tile .x.rojo{color:#ff5a5f}
.mc{display:inline-block;width:11px;height:15px;border-radius:2px;margin-left:3px;vertical-align:-1px;border:1px solid rgba(0,0,0,.5)}
.mc.am{background:#f7d117}.mc.ro{background:#e0252b}
.row.c{font-size:17.5px;padding:2px 0 2px}.row.c b{font-size:18.5px}
"""


def pitch_html(d, base, escudo_club):
    w, h = 520, 500
    top_w, bot_w = 408, 520
    lines = d.get("once") or []
    pts = f"{(w-top_w)/2},0 {w-(w-top_w)/2},0 {w},{h} 0,{h}"
    def X(xr, y):  # xr en 0..1 dentro de la cancha, y en px
        ww = top_w + (bot_w - top_w) * y / h
        return (w - ww) / 2 + xr * ww
    ln = 'stroke="rgba(255,255,255,.85)" stroke-width="3" fill="none"'
    def L(x1, y1, x2, y2):
        return f'<line x1="{X(x1,y1)}" y1="{y1}" x2="{X(x2,y2)}" y2="{y2}" {ln}/>'
    def box(xa, xb, y0, y1):
        return (L(xa, y0, xa, y1) + L(xb, y0, xb, y1) + L(xa, y1, xb, y1))
    svg = (f'<svg width="{w}" height="{h}" style="position:absolute;left:0;top:0">'
           f'<defs><radialGradient id="g" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#4a4e52"/><stop offset="1" stop-color="#26292c"/></radialGradient>'
           f'<pattern id="rings" width="{w}" height="{h}" patternUnits="userSpaceOnUse">'
           + "".join(f'<ellipse cx="{w/2}" cy="{h/2}" rx="{r*1.25}" ry="{r}" fill="none" stroke="rgba(255,255,255,.035)" stroke-width="18"/>' for r in range(40, 420, 46))
           + f'</pattern></defs>'
           f'<polygon points="{pts}" fill="url(#g)"/><polygon points="{pts}" fill="url(#rings)"/>'
           f'<polygon points="{pts}" {ln} stroke-linejoin="round"/>'
           + L(0, h/2, 1, h/2)
           + f'<ellipse cx="{w/2}" cy="{h/2}" rx="{0.13*(top_w+bot_w)/2}" ry="{0.13*(top_w+bot_w)/2*0.62}" {ln}/>'
           + box(.2, .8, 0, 92) + box(.36, .64, 0, 34)
           + box(.2, .8, h, h-100) + box(.36, .64, h, h-38)
           + "</svg>")
    out = svg
    if d.get("formacion"):
        out += f'<div class="form">{esc(d["formacion"])}</div>'
    n = len(lines)
    if n == 0:
        return out
    cr = b64(escudo_club)
    for i, line in enumerate(lines):
        # i=0 arquero (abajo) ... n-1 ataque (arriba)
        y_face_bottom = (h - 50) - i * ((h - 50 - 80) / max(1, n - 1))
        k = len(line)
        persp = y_face_bottom / h
        size = int((62 + 14 * persp) * (0.9 if n >= 5 else 1))
        for j, p in enumerate(line):
            xr = (j + 1) / (k + 1) if k > 1 else 0.5
            if k >= 4:
                xr = 0.08 + 0.84 * j / (k - 1)
            x = X(xr, y_face_bottom)
            nombre = esc(p.get("nombre", "")).upper()
            fs = 13.5 if len(nombre) <= 8 else (12.5 if len(nombre) <= 11 else 11)
            img = b64(p.get("cara"))
            ph = (f'<img src="{img}" style="width:{size}px;height:{size}px">' if img else
                  f'<div class="num" style="width:{size-16}px;height:{size-16}px;font-size:{int(size*.32)}px">{esc(p.get("dorsal",""))}</div>')
            crest = f'<div class="cr" style="width:24px;height:24px"><img src="{cr}" style="width:19px;height:19px"></div>' if cr else ""
            st = estrellas_html(p.get("estrellas"), 11)
            sub = d.get("sustitucion") if p.get("sale") else None
            entra = ""
            if sub:
                ci = b64(sub.get("cara"))
                entra = (f'<div class="entra" style="width:{int(size*.72)}px;height:{int(size*.72)}px">'
                         + (f'<img src="{ci}">' if ci else '') + '</div>')
            out += (f'<div class="slot{" yo" if p.get("yo") else ""}{" sale" if sub else ""}" style="left:{x}px;top:{y_face_bottom - size}px;z-index:{(40 if sub else 10)+i}">'
                    f'<div class="ph">{ph}{entra}{tarjetas_html(p)}</div>'
                    f'<div class="plate"><div class="n" style="font-size:{fs}px;max-width:{int(104 if k<=3 else 92)}px"><span>{nombre}</span></div>{crest}</div>'
                    + (f'<div class="tab">{st}</div>' if st else "")
                    + (f'<div class="chip">⇄ Entra {esc(sub.get("apellido",""))} {esc(sub.get("minuto",""))}</div>' if sub else "") + '</div>')
    return out


def tarjetas_html(p):
    """Tarjetas del jugador: roja (con o sin amarilla antes) o amarillas."""
    if p.get("roja"):
        return '<div class="tarj">' + ('<i class="am"></i>' if p.get("amarillas") else '') + '<i class="ro"></i></div>'
    if p.get("amarillas"):
        return '<div class="tarj">' + '<i class="am"></i>' * min(2, int(p["amarillas"])) + '</div>'
    return ""


def valor_html(v):
    """Valor de una fila; [A] y [R] se dibujan como tarjeta amarilla y roja."""
    return esc(v).replace("[A]", '<i class="mc am"></i>').replace("[R]", '<i class="mc ro"></i>')


def rows(items, compacto=False):
    out = ""
    for it in items:
        k, v = it[0], it[1]
        g = it[2] if len(it) > 2 else False
        if v == " " or v == "":
            out += f'<div class="row h{" c" if compacto else ""}"><span>{k}</span></div>'
        else:
            out += f'<div class="row{" c" if compacto else ""}"><span>{k}</span><b class="{"gold" if g else ""}">{valor_html(v)}</b></div>'
    return out


def html(d, base):
    t = d.get("tema") or {}
    c1, c2, ac = t.get("c1", "#2a6fb0"), t.get("c2", "#0d2440"), t.get("acento", "#6fb7e6")
    nombre = esc(d["nombre"])
    size = min(124, int(1000 / max(1, len(d["nombre"])) * 1.9))
    el, ev, ec = b64(d.get("escudo_local")), b64(d.get("escudo_visita")), d.get("escudo_club")
    wm = b64(ec)
    cara = b64(d.get("cara"))
    foto = b64(d.get("foto"))
    hero_img = (f'<img class="face" src="{cara}">' if cara else (f'<img class="fig" src="{foto}">' if foto else ""))
    crc = b64(ec)
    cards = []
    if d.get("generales"):
        cards.append(f'<div class="card"><h3>SU PARTIDO</h3>{rows(d["generales"][:10])}</div>')
    if d.get("posicion"):
        cards.append(f'<div class="card"><h3>TOTALES</h3>{rows(d["posicion"][:10])}</div>')
    zona = d.get("zona") or {}
    zrows = (f'<div class="zt">{esc(zona["titulo"])}</div>' + rows(zona["filas"], len(zona["filas"]) > 4)) if zona.get("filas") else ""
    if d.get("heat_img") and b64(os.path.join(base, d["heat_img"])):
        hi = b64(os.path.join(base, d["heat_img"]))
        if zrows:
            cards.append(f'<div class="card calor"><h3>MAPA DE CALOR</h3><div class="heat chica"><img src="{hi}"></div>{zrows}</div>')
        else:
            cards.append(f'<div class="card calor"><h3>MAPA DE CALOR</h3><div class="heat"><img src="{hi}"></div></div>')
    elif zrows:
        cards.append(f'<div class="card calor"><h3>{esc(zona["titulo"])}</h3>{rows(zona["filas"])}</div>')
    ex = d.get("extra") or {}
    if ex.get("filas"):
        fe = ex["filas"][:10]
        cards.append(f'<div class="card"><h3>{esc(ex.get("titulo","TEMPORADA"))}<small>{esc(ex.get("sub",""))}</small></h3>{rows(fe, len(fe) > 9)}</div>')
    if len(cards) < 4 and d.get("perfil"):
        cards.insert(min(2, len(cards)), f'<div class="card"><h3>PERFIL</h3>{rows([[k, v, False] for k, v in d["perfil"]])}</div>')
    cond = d.get("condicion", "")
    if d.get("sustitucion") and d["sustitucion"].get("rol"):
        cond = f'SUPLENTE · ENTRÓ DE {d["sustitucion"]["rol"].upper()}'
    meta = esc(d.get("meta", "")) + (f'<span class="tag{" sup" if cond.startswith("SUPLENTE") else ""}">{esc(cond)}</span>' if cond else "")
    nota_v = d.get("nota") or "—"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fuentes()}{CSS}
:root{{--c1:{c1};--c2:{c2};--acento:{ac};--acento-txt:{txt_sobre(ac)}}}</style></head><body>
<div class="bg"></div>
{f'<img class="wm" src="{wm}">' if wm else ''}
<div class="shade"></div>
<div class="brand">CELESTES POR EL MUNDO</div>
<h1 style="font-size:{size}px">{nombre}</h1>
<div class="score">{f'<img src="{el}">' if el else ''}<span class="t">{esc(d["local"])}</span>
 <span class="r">{esc(d.get("goles_local",""))} – {esc(d.get("goles_visita",""))}</span>
 <span class="t">{esc(d["visita"])}</span>{f'<img src="{ev}">' if ev else ''}</div>
<div class="meta">{meta}</div>
<div class="pitch">{pitch_html(d, base, ec)}</div>
<div class="hero"><div class="glow"></div>{hero_img}{tarjetas_html({"roja": d.get("roja"), "amarillas": d.get("amarillas_hero")}) if d.get("roja") else ""}
 {f'<div class="dorsal">{esc(d.get("dorsal",""))}</div>' if d.get("dorsal") else ''}
 <div class="plate yo"><div class="n"><span>{esc(d.get("apellido","")).upper()}</span></div>{f'<div class="cr"><img src="{crc}"></div>' if crc else ''}</div>
 {f'<div class="tab">{estrellas_html(d.get("estrellas"), 24)}</div>' if d.get("estrellas") else ''}
</div>
<div class="tiles"><div class="tile"><div class="v">{esc(d["minutos"])}</div><div class="l">MINUTOS</div>{(f'<div class="x">Entró al {esc(d["sustitucion"]["minuto"])}</div>') if d.get("sustitucion") else ''}{(f'<div class="x rojo">Expulsado' + (f' al {esc(d["roja"])}' if isinstance(d.get("roja"), str) else '') + '</div>') if d.get("roja") else ''}</div>
 <div class="tile"><div class="v gold">{esc(nota_v)}</div><div class="l">NOTA</div></div></div>
<div class="cards">{''.join(cards[:4])}</div>
<div class="foot"><div class="wordmark">Celestes <i>por el</i> mundo</div><div class="hash">#CELESTESPORELMUNDO</div></div>
</body></html>"""


def _abs(d, base):
    for k in ("escudo_local", "escudo_visita", "escudo_club", "cara", "foto"):
        if d.get(k) and not os.path.isabs(d[k]):
            d[k] = os.path.join(base, d[k])
    for line in d.get("once") or []:
        for p in line:
            if p.get("cara") and not os.path.isabs(p["cara"]):
                p["cara"] = os.path.join(base, p["cara"])
    return d


async def main(path):
    data = json.load(open(path))
    base = os.path.dirname(os.path.abspath(path))
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": HH})
        for d in data:
            d = _abs(dict(d), base)
            h = os.path.join(base, d["archivo"] + ".html")
            open(h, "w").write(html(d, base))
            await pg.goto("file://" + h)
            await pg.wait_for_timeout(150)
            await pg.screenshot(path=os.path.join(base, d["archivo"] + ".png"))
            os.remove(h)
            print("OK", os.path.join(base, d["archivo"] + ".png"))
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
