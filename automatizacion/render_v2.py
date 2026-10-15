"""Plantilla v2 'Celestes por el mundo' — solo datos del jugador.
Uso: python3 render_v2.py datos.json  -> <archivo>.png al lado del json.
Campos: archivo, nombre, marcador, meta, minutos, nota, nota_label, formacion, once (lista de líneas
de arco a ataque, cada línea de izquierda a derecha: [dorsal, nombre]), jugador_dorsal,
generales [[etiqueta, valor, dorado]], mediocentro [[...]], heat (lista de [x, y, peso] en 0..1, x=ancho, y=largo
con el arco propio abajo) o null, heat_img (ruta a una captura del mapa de calor, por ejemplo de la app
de BeSoccer; si está, tiene prioridad sobre heat), heat_credito (por defecto "Mapa: BeSoccer"), foto, credito_foto, muestra (lista de bloques con datos de muestra), fuente."""
import json, os, sys, asyncio, base64, mimetypes, math
from playwright.async_api import async_playwright

if os.path.isdir("/opt/pw-browsers"):  # nube de Claude; en GitHub Actions se usa la ruta por defecto
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:radial-gradient(ellipse at 50% 55%,#1d4a33 0%,#0f2a1d 45%,#0b1f15 100%);
 font-family:'Inter','Helvetica Neue',Arial,sans-serif;color:#eef3ee;position:relative;overflow:hidden}
.kicker{position:absolute;top:44px;width:100%;text-align:center;color:#7cc4f0;font-weight:800;letter-spacing:4px;font-size:19px}
h1{position:absolute;top:76px;width:100%;text-align:center;font-weight:900;letter-spacing:2px;line-height:1;white-space:nowrap}
.match{position:absolute;top:174px;width:100%;text-align:center;font-size:34px;font-weight:900;letter-spacing:1.5px}
.meta{position:absolute;top:220px;width:100%;text-align:center;font-size:17px;letter-spacing:3px;color:#b9c9bd}
.card{position:absolute;background:rgba(18,54,38,.92);border-radius:22px;padding:20px 22px}
.card h3{color:#7cc4f0;font-size:18px;font-weight:900;letter-spacing:1.5px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.card h3 small{font-size:12px;color:#b9c9bd;letter-spacing:1px}
.row{display:flex;justify-content:space-between;align-items:center;font-size:17px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}
.row:last-child{border-bottom:none}
.row b{font-weight:800}
.gold{color:#f2c14e!important}
.big{text-align:center;padding:12px 8px}
.big .n{font-size:52px;font-weight:900;line-height:1}
.big .l{font-size:12px;letter-spacing:2px;color:#b9c9bd;margin-top:8px;font-weight:700}
.photo{position:absolute;left:380px;top:384px;width:320px;height:420px;border:2px dashed #3d6b52;border-radius:24px;overflow:hidden;
 display:flex;align-items:center;justify-content:center;text-align:center;color:#6f8a78;font-weight:800;letter-spacing:2px;font-size:16px;line-height:1.6}
.photo.has{border:none}.photo img{width:100%;height:100%;object-fit:cover;object-position:top}
.photo .cr{position:absolute;bottom:8px;right:12px;font-size:11px;color:#dfe9e1;font-weight:600}
.stamp{position:absolute;top:8px;right:-6px;background:#e0564b;color:#fff;font-size:11px;font-weight:900;letter-spacing:1.5px;padding:3px 8px;border-radius:5px;transform:rotate(4deg)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px 16px;margin-top:8px}.lab{font-size:12px;letter-spacing:1.5px;color:#a9bbad;margin-bottom:4px}.val{font-size:23px;font-weight:800}
.foot{position:absolute;bottom:38px;width:100%;text-align:center;font-size:13.5px;color:#7cc4f0;line-height:1.6}
.foot .w{color:#e0564b;font-weight:800}
"""

def v(x, gold=False):
    if x in (None, ""):
        return '<b style="color:#6f8a78">—</b>'
    return f'<b class="{"gold" if gold else ""}">{x}</b>'

def rows(items):
    return "".join(f'<div class="row"><span>{k}</span>{v(val, g)}</div>' for k, val, g in items)

def pitch_svg(w, h, inner=""):
    # cancha vertical, arco propio abajo
    s = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
    s += f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="8" fill="#2c6a47" stroke="#cfe3d4" stroke-width="2"/>'
    s += inner
    ln = 'fill="none" stroke="#cfe3d4" stroke-width="2" opacity=".85"'
    s += f'<line x1="1" y1="{h/2}" x2="{w-1}" y2="{h/2}" {ln}/><circle cx="{w/2}" cy="{h/2}" r="{w*.14}" {ln}/>'
    bw, bh = w * .56, h * .15
    s += f'<rect x="{(w-bw)/2}" y="1" width="{bw}" height="{bh}" {ln}/><rect x="{(w-bw)/2}" y="{h-1-bh}" width="{bw}" height="{bh}" {ln}/>'
    gw, gh = w * .26, h * .055
    s += f'<rect x="{(w-gw)/2}" y="1" width="{gw}" height="{gh}" {ln}/><rect x="{(w-gw)/2}" y="{h-1-gh}" width="{gw}" height="{gh}" {ln}/>'
    return s + "</svg>"

def lineup_html(d, w, h):
    lines = d["once"]
    out = ""
    n = len(lines)
    for i, line in enumerate(lines):
        y = h - 34 - i * (h - 84) / (n - 1)
        for j, (num, name) in enumerate(line):
            x = w * (j + 1) / (len(line) + 1)
            slot = min(110, w / (len(line) + 1) * 1.05)
            me = str(num) == str(d["jugador_dorsal"])
            bg, fg, bd = ("#f2c14e", "#0b1f15", "#fff") if me else ("#eef3ee", "#0b1f15", "#0b1f15")
            size = 38 if me else 30
            glow = "box-shadow:0 0 0 5px rgba(242,193,78,.35);" if me else ""
            out += (f'<div style="position:absolute;left:{x-size/2}px;top:{y-size/2}px;width:{size}px;height:{size}px;border-radius:50%;'
                    f'background:{bg};color:{fg};border:2px solid {bd};{glow}display:flex;align-items:center;justify-content:center;'
                    f'font-weight:900;font-size:{15 if me else 13}px">{num}</div>'
                    f'<div style="position:absolute;left:{x-slot/2}px;top:{y+size/2+2}px;width:{slot}px;text-align:center;font-size:{(13 if me else 11.5) if len(name)<=8 else (11.5 if me else 10)}px;letter-spacing:-.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
                    f'font-weight:{900 if me else 700};color:{"#f2c14e" if me else "#eef3ee"};text-shadow:0 1px 2px #000">{name}</div>')
    return f'<div style="position:relative;width:{w}px;height:{h}px">{pitch_svg(w, h)}{out}</div>'

def heat_html(points, w, h):
    if not points:
        return f'<div style="position:relative;width:{w}px;height:{h}px">{pitch_svg(w, h)}<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#cfe3d4;font-weight:700;font-size:14px;text-align:center">Sin mapa de calor<br>en la fuente</div></div>'
    defs, blobs = "", ""
    for k, (x, y, p) in enumerate(points):
        cx, cy, r = x * w, (1 - y) * h, 34 + 26 * p
        defs += f'<radialGradient id="g{k}"><stop offset="0" stop-color="#ff3b1f" stop-opacity="{.55+.4*p:.2f}"/><stop offset=".45" stop-color="#ffb21f" stop-opacity="{.35+.3*p:.2f}"/><stop offset="1" stop-color="#ffe066" stop-opacity="0"/></radialGradient>'
        blobs += f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="url(#g{k})"/>'
    inner = f'<defs>{defs}</defs><g>{blobs}</g>'
    arrow = f'<div style="position:absolute;right:6px;top:6px;font-size:11px;color:#cfe3d4;font-weight:700">ATAQUE ↑</div>'
    return f'<div style="position:relative;width:{w}px;height:{h}px">{pitch_svg(w, h, inner)}{arrow}</div>'

def heat_img_html(src, credito, w, h):
    return (f'<div style="position:relative;width:{w}px;height:{h}px;border-radius:12px;overflow:hidden;background:#0b1f15">'
            f'<img src="{src}" style="width:100%;height:{h-22}px;object-fit:contain;display:block">'
            f'<div style="position:absolute;bottom:2px;right:6px;font-size:11.5px;color:#cfe3d4;font-weight:700">{credito}</div></div>')

def centro_inf(d, stamp, base="."):
    if d.get('heat_img'):
        p = d['heat_img'] if os.path.isabs(d['heat_img']) else os.path.join(base, d['heat_img'])
        return f'<div class="card" style="left:380px;top:818px;width:320px;height:434px">{stamp("heat")}<h3>MAPA DE CALOR</h3>{heat_img_html(img_data(p), d.get("heat_credito") or "Mapa: BeSoccer", 276, 370)}</div>'
    if d.get('heat') or not d.get('perfil'):
        return f'<div class="card" style="left:380px;top:818px;width:320px;height:434px">{stamp("heat")}<h3>MAPA DE CALOR</h3>{heat_html(d.get("heat"), 276, 370)}</div>'
    grid = "".join(f'<div><div class="lab">{k}</div><div class="val {"gold" if k=="DORSAL" else ""}">{v}</div></div>' for k, v in d['perfil'])
    return f'<div class="card" style="left:380px;top:818px;width:320px;height:434px"><h3>PERFIL</h3><div class="grid">{grid}</div></div>'

def img_data(path):
    mt = mimetypes.guess_type(path)[0] or ("image/svg+xml" if path.endswith(".svg") else "image/png")
    return f"data:{mt};base64," + base64.b64encode(open(path, "rb").read()).decode()

def html(d, base):
    m = set(d.get("muestra", []))
    stamp = lambda k: '<div class="stamp">MUESTRA</div>' if k in m else ""
    size = 86 if len(d["nombre"]) <= 16 else max(56, int(86 * 16 / len(d["nombre"])))
    foto = d.get("foto")
    if foto:
        p = foto if os.path.isabs(foto) else os.path.join(base, foto)
        cr = f'<div class="cr">📷 {d["credito_foto"]}</div>' if d.get("credito_foto") else ""
        photo = f'<div class="photo has"><img src="{img_data(p)}">{cr}</div>'
    else:
        photo = '<div class="photo">FOTO DE BERNAL<br>(uso libre<br>o con permiso)</div>'
    warn = '<br><span class="w">MAQUETA · los bloques marcados MUESTRA no son datos reales — no publicar</span>' if m else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="kicker">CELESTES POR EL MUNDO</div>
<h1 style="font-size:{size}px">{d['nombre']}</h1>
<div class="match">{d['marcador']}</div>
<div class="meta">{d['meta']}</div>

<div class="card" style="left:40px;top:264px;width:320px;height:540px"><h3>ALINEACIÓN <small>{d['formacion']}</small></h3>{lineup_html(d, 276, 470)}</div>
<div class="card" style="left:40px;top:818px;width:320px;height:434px">{stamp('extra')}<h3>{d['extra']['titulo']} <small>{d['extra'].get('sub','')}</small></h3>{rows(d['extra']['filas'])}</div>

<div class="card big" style="left:380px;top:264px;width:150px;height:104px"><div class="n">{d['minutos']}</div><div class="l">MINUTOS</div></div>
<div class="card big" style="left:542px;top:264px;width:158px;height:104px"><div class="n gold">{d.get('nota') or '—'}</div><div class="l">{d['nota_label']}</div></div>
{photo}
{centro_inf(d, stamp, base)}

<div class="card" style="left:720px;top:264px;width:320px;height:440px">{stamp('generales')}<h3>SU PARTIDO</h3>{rows(d['generales'])}</div>
<div class="card" style="left:720px;top:718px;width:320px;height:534px">{stamp('mediocentro')}<h3>{d.get('pos_titulo','COMO MEDIOCENTRO')}</h3>{rows(d['mediocentro'])}</div>

<div class="foot">{d['fuente']}{warn}</div>
</body></html>"""

async def main(path):
    data = json.load(open(path))
    base = os.path.dirname(os.path.abspath(path))
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1350})
        for d in data:
            h = os.path.join(base, d["archivo"] + ".html")
            open(h, "w").write(html(d, base))
            await pg.goto("file://" + h)
            await pg.screenshot(path=os.path.join(base, d["archivo"] + ".png"))
            print("OK", os.path.join(base, d["archivo"] + ".png"))
        await b.close()

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
