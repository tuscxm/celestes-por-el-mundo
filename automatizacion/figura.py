"""Genera la figura ilustrada de espaldas con la camiseta del equipo, el apellido y el dorsal.
Uso: python3 figura.py plantilla.svg salida.svg APELLIDO DORSAL '{"tipo":"rayas|liso|aros","c1":"#..","c2":"#..","texto":"#..","short":"#.."}'"""
import sys, json, re

def figura(tpl, apellido, dorsal, cam):
    s = open(tpl).read()
    c1, c2 = cam["c1"], cam["c2"]
    if cam["tipo"] == "rayas":
        pat = f'<pattern id="str" width="44" height="10" patternUnits="userSpaceOnUse" x="6"><rect width="44" height="10" fill="{c2}"/><rect width="22" height="10" fill="{c1}"/></pattern>'
    elif cam["tipo"] == "aros":
        pat = f'<pattern id="str" width="10" height="56" patternUnits="userSpaceOnUse" y="10"><rect width="10" height="56" fill="{c2}"/><rect width="10" height="28" fill="{c1}"/></pattern>'
    else:
        pat = f'<pattern id="str" width="10" height="10" patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="{c1}"/></pattern>'
    s = re.sub(r'<pattern id="str".*?</pattern>', pat, s, flags=re.S)
    s = s.replace('fill="#0a8b47"', f'fill="{c1 if cam["tipo"] != "liso" else cam["texto"]}"')
    tx = cam["texto"]
    claro = int(tx[1:3], 16) + int(tx[3:5], 16) + int(tx[5:7], 16) > 450
    borde = "#0b1f15" if claro else "#f3f6f3"
    s = s.replace('stroke="#f3f6f3" stroke-width="7"', f'stroke="{borde}" stroke-width="7"')
    s = s.replace('stroke="#f3f6f3" stroke-width="10"', f'stroke="{borde}" stroke-width="10"')
    s = s.replace('<textPath href="#arc" startOffset="50%">BERNAL</textPath>', f'<textPath href="#arc" startOffset="50%">{apellido.upper()}</textPath>')
    s = re.sub(r'(<text font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size=")34(" letter-spacing="3" )fill="#0b1f15"',
               lambda m: m.group(1) + str(34 if len(apellido) <= 6 else max(20, int(34 * 5.6 / len(apellido)))) + m.group(2) + f'fill="{tx}"', s)
    s = re.sub(r'fill="#0b1f15" stroke="[^"]+" stroke-width="10" paint-order="stroke">6</text>',
               f'fill="{tx}" stroke="{borde}" stroke-width="10" paint-order="stroke">{dorsal}</text>', s)
    if len(str(dorsal)) > 1:
        s = s.replace('font-size="190"', 'font-size="160"')
    return s

if __name__ == "__main__":
    tpl, out, ap, num, cam = sys.argv[1:6]
    open(out, "w").write(figura(tpl, ap, num, json.loads(cam)))
    print("OK", out)
