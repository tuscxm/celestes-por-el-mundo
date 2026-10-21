import json,re,sys,os
S=sys.argv[1]
d=json.load(open(S+'/datos_z.json')); rb=d['rb']; hm=d['hm']
css=re.search(r'<style>(.*?)</style>',open(S+'/boceto.html').read(),re.S).group(1)
W,H=400,258
def X(x): return x/100*W
def Y(y): return H*(1-y/100)
heat=''.join(f'<circle cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="14" fill="#ff5a1f" opacity=".42"/>' for p in hm)
mk=''
for e in rb['defensive']:
    c=e.get('playerCoordinates') or {}
    if c.get('x') is None: continue
    x,y=X(c['x']),Y(c['y']); t=e['eventActionType']
    if t=='ball-recovery': mk+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#f2c14e" stroke="#111" stroke-width="1.5"/>'
    elif t=='interception': mk+=f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" transform="rotate(45 {x:.1f} {y:.1f})" fill="#9fd6f7" stroke="#111" stroke-width="1.5"/>'
    elif t=='tackle': mk+=f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="#ff8a7a" stroke="#111" stroke-width="1.5"/>'
    elif t=='clearance': mk+=f'<path d="M{x:.1f},{y-8:.1f} L{x+7:.1f},{y+5:.1f} L{x-7:.1f},{y+5:.1f}Z" fill="#fff" stroke="#111" stroke-width="1.5"/>'
for e in rb.get('dribbles',[]):
    c=e['playerCoordinates']; x,y=X(c['x']),Y(c['y'])
    mk+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{"#c58bff" if e.get("outcome") else "none"}" stroke="#c58bff" stroke-width="2.5"/>'
for e in rb['passes']:
    if e.get('keypass'):
        a,b=e['playerCoordinates'],e['passEndCoordinates']
        mk+=f'<line x1="{X(a["x"]):.1f}" y1="{Y(a["y"]):.1f}" x2="{X(b["x"]):.1f}" y2="{Y(b["y"]):.1f}" stroke="#7CFC9A" stroke-width="3" marker-end="url(#fl)"/>'
lw='stroke="rgba(255,255,255,.55)" stroke-width="1.6" fill="none"'
cancha=f'''<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}"><defs><filter id="bl" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="13"/></filter>
<marker id="fl" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="#7CFC9A"/></marker>
<clipPath id="cp"><rect width="{W}" height="{H}" rx="8"/></clipPath></defs>
<rect width="{W}" height="{H}" rx="8" fill="#1d2328"/>
<g clip-path="url(#cp)"><g filter="url(#bl)">{heat}</g></g>
<rect x="{W/3:.1f}" y="0" width="{W/3:.1f}" height="{H}" fill="rgba(255,255,255,.03)"/>
<line x1="{W/3:.1f}" y1="0" x2="{W/3:.1f}" y2="{H}" stroke="rgba(242,193,78,.5)" stroke-dasharray="6 5" stroke-width="1.4"/>
<line x1="{2*W/3:.1f}" y1="0" x2="{2*W/3:.1f}" y2="{H}" stroke="rgba(242,193,78,.5)" stroke-dasharray="6 5" stroke-width="1.4"/>
<rect x="2" y="2" width="{W-4}" height="{H-4}" {lw}/><line x1="{W/2}" y1="2" x2="{W/2}" y2="{H-2}" {lw}/><circle cx="{W/2}" cy="{H/2}" r="40" {lw}/>
<rect x="2" y="{H*.2:.1f}" width="{W*.157:.1f}" height="{H*.6:.1f}" {lw}/><rect x="{W-2-W*.157:.1f}" y="{H*.2:.1f}" width="{W*.157:.1f}" height="{H*.6:.1f}" {lw}/>
{mk}</svg>'''
def bar(lbl,a,b,gold=False):
    p=round(100*a/b) if b else 0
    return f'<div class="bar"><div class="bl"><span>{lbl}</span><b>{a}<i>/{b}</i> <em class="{"g" if gold else ""}">{p}%</em></b></div><div class="tr"><div class="fi{" g" if gold else ""}" style="width:{p}%"></div></div></div>'
def clave(v,l,prom,sube):
    return f'<div class="clave"><div class="cv">{v}</div><div class="cl">{l}</div><div class="cp {"up" if sube else "dn"}">{"▲" if sube else "▼"} su promedio: {prom}</div></div>'
A='<span class="ca a"></span>'; R='<span class="ca r"></span>'
html=f'''<!doctype html><meta charset="utf-8"><style>{css}
body{{background:transparent}}
.wrap{{width:1080px;padding:0 24px;display:flex;flex-direction:column;gap:12px}}
.card{{padding:11px 16px 10px}} h3{{margin:0 0 7px;font-size:20px}}
.claves{{display:flex;gap:10px}}.clave{{flex:1;background:rgba(255,255,255,.06);border-radius:10px;padding:6px 10px;display:grid;grid-template-columns:auto 1fr;column-gap:12px;align-items:center}}
.fijo{{flex:0 0 84px;background:rgba(242,193,78,.13);border:1.5px solid rgba(242,193,78,.5);border-radius:10px;text-align:center;padding:4px 0}}.fv{{font-size:38px;font-weight:900;line-height:1}}.fl{{font-size:13px;font-weight:800;letter-spacing:1.2px;color:#f2c14e}}
.cv{{grid-row:span 2;font-size:38px;font-weight:900;line-height:1}}.cl{{font-size:15.5px;font-weight:800;letter-spacing:1px}}.cp{{font-size:14px;font-weight:700}}.cp.up{{color:#7CFC9A}}.cp.dn{{color:#ff8a7a}}
.mid{{display:flex;gap:14px}}.mapa{{flex:0 0 auto}}
.leyenda{{display:flex;gap:10px;font-size:13px;color:#c9d1d6;font-weight:600;margin-top:6px;flex-wrap:wrap}}.leyenda i{{display:inline-block;width:11px;height:11px;margin-right:4px;vertical-align:-1px}}
.tercios{{display:flex;margin-top:6px;border-radius:6px;overflow:hidden;font-size:14px;font-weight:800;text-align:center}}.tercios div{{padding:3px 0;color:#111}}
.que{{flex:1}}.grupo{{margin:5px 0 2px}}.bar{{margin:0 0 5px}}.bl{{font-size:16px}}
.linea{{display:flex;justify-content:space-between;font-size:16px;font-weight:600;padding:2px 0;border-bottom:1px solid rgba(255,255,255,.07)}}.linea b{{font-weight:800}}
.temp .t{{display:grid;grid-template-columns:1.6fr repeat(5,1fr);font-size:16px;font-weight:600;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.07);align-items:center}}
.temp .t.h{{font-size:12.5px;letter-spacing:1.2px;color:#8d989f;font-weight:800}}.temp .t span:not(:first-child){{text-align:center}}.temp b{{font-weight:800}}
</style><div class="wrap">
<div class="card"><h3>SU PARTIDO <small>3 CLAVES COMO ENGANCHE · VS. SU PROMEDIO POR PARTIDO EN LA TEMPORADA</small></h3>
<div class="claves"><div class="fijo"><div class="fv">0</div><div class="fl">GOLES</div></div><div class="fijo"><div class="fv">0</div><div class="fl">ASIST.</div></div>{clave(2,"PASES CLAVE","1,4",True)}{clave(1,"OCASIONES CLARAS CREADAS","0,3",True)}{clave("91%","PRECISIÓN DE PASE","81%",True)}</div></div>
<div class="mid">
<div class="card mapa"><h3>DÓNDE JUGÓ <small>67% POR LA DERECHA</small></h3>{cancha}
<div class="tercios"><div style="width:10%;background:#9fd6f7">10%</div><div style="width:49%;background:#d9e6ee">MEDIO 49%</div><div style="width:41%;background:#f2c14e">ATAQUE 41%</div></div>
<div class="leyenda"><span><i style="background:#7CFC9A;height:3px;vertical-align:3px"></i>Pase clave</span><span><i style="background:#c58bff;border-radius:50%"></i>Regate (○ fallido)</span><span><i style="background:#f2c14e;border-radius:50%"></i>Recup.</span><span><i style="background:#ff8a7a"></i>Entrada</span><span><i style="background:#fff;clip-path:polygon(50% 0,100% 100%,0 100%)"></i>Despeje</span></div></div>
<div class="card que"><h3>QUÉ HIZO</h3>
<div class="grupo">PASE</div>{bar("Pases precisos",20,22,True)}{bar("Pases al último tercio",10,14)}
<div class="grupo">CREACIÓN</div><div class="linea"><span>Pases clave · Ocasiones claras creadas</span><b>2 · 1</b></div><div class="linea"><span>Asistencias esperadas (xA) · Centros</span><b>0,13 · 1/3</b></div>
<div class="grupo">REMATE</div><div class="linea"><span>Remates (al arco)</span><b>0 (0)</b></div>
<div class="grupo">DUELOS Y REGATES</div>{bar("Duelos ganados",3,5)}<div class="linea"><span>Regates exitosos · Faltas recibidas</span><b>1/2 · 1</b></div>
<div class="grupo">DEFENSA Y PELOTA</div><div class="linea"><span>Recup. (def·med·ata) · Entradas · Despejes</span><b>1 (0·1·0) · 1/1 · 1</b></div><div class="linea" style="border:0"><span>Toques · Pérdidas · Faltas · Tarjetas</span><b>36 · 7 · 0 · 0{A} 0{R}</b></div>
</div></div>
<div class="card temp"><h3 style="margin-bottom:2px">TEMPORADA <small>26/27</small></h3>
<div class="t"><span><b>LIGA PORTUGAL</b></span><span>8 PJ (6 tit.)</span><span>534'</span><span>nota <b style="color:#f2c14e">7.06</b></span><span>2 G · 1 A</span><span>0{A} 0{R}</span></div>
<div class="t" style="border:0"><span><b>CHAMPIONS LEAGUE</b></span><span>1 PJ (1 tit.)</span><span>66'</span><span>nota <b style="color:#f2c14e">7.70</b></span><span>1 G · 0 A</span><span>0{A} 0{R}</span></div>
</div></div>'''
open(S+'/boceto_z.html','w').write(html)
