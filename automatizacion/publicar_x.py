"""Publica en X las infografías nuevas: la imagen con el texto del posteo (en un hilo corto si no entra en un posteo).

Corre en GitHub (.github/workflows/publicar_x.yml), no en la nube de Claude: las claves de X son secretos del repositorio.
Uso: python3 automatizacion/publicar_x.py --registro publicados_x.json [--probar] [--lista nuevas.txt] [--lista-avisos avisos.txt] [png ...]
     python3 automatizacion/publicar_x.py --registro publicados_x.json --probar --ultima
Claves (secretos del repositorio): X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
  (OAuth 1.0a de la cuenta que publica; la app de X tiene que tener permiso "Read and write").
Variable X_PREMIUM=si: un solo posteo con el texto completo (si la cuenta de X tiene Premium; si X lo rechaza, va en hilo).
--probar: arma los textos y revisa las claves, sin publicar nada.
--lista-avisos: los avisos de la corrida; lo que la revisión visual puso en "## No publicar en X" no se publica.
El registro (automatizacion/publicados_x.json en main) guarda qué se publicó y el enlace; lo ya publicado no se repite."""
import argparse, base64, datetime, glob, io, json, os, re, sys, time, unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.x.com/2"
LIMITE = 280
LIMITE_PREMIUM = 25000
MAX_IMAGEN = 4_900_000  # X acepta imágenes de hasta 5 MB
CLAVES = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")
PISTAS = {401: "las claves de X no son válidas: revisá los cuatro secretos X_...",
          402: "no hay crédito en la cuenta de desarrollador de X",
          403: "X no deja publicar: la app tiene que tener permiso \"Read and write\" (y el Access Token generado después de ese cambio), o ese texto ya estaba publicado",
          429: "X frenó los pedidos (límite o sin crédito); probá más tarde"}


def peso(texto):
    """Largo como lo cuenta X: el alfabeto latino (con tildes) pesa 1; emojis y el resto, 2.
    Las banderas se cuentan de más (4 en vez de 2): es más seguro."""
    n = 0
    for c in unicodedata.normalize("NFC", texto):
        o = ord(c)
        if o == 0xFE0F:
            continue
        n += 1 if o <= 4351 or 8192 <= o <= 8205 or 8208 <= o <= 8223 or 8242 <= o <= 8247 else 2
    return n


def partes(copy):
    """Párrafos del texto del posteo y sus hashtags (las últimas líneas que son solo de #)."""
    copy = re.sub(r"https?://\S+", "", copy)  # un posteo con enlace cuesta mucho más en X
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", copy.strip()) if p.strip()]
    tags = []
    if parrafos:
        lineas = parrafos[-1].splitlines()
        while lineas and all(w.startswith("#") for w in lineas[-1].split()):
            tags = lineas.pop().split() + tags
        parrafos[-1] = "\n".join(lineas).strip()
        if not parrafos[-1]:
            parrafos.pop()
    return parrafos, tags


def oraciones(p):
    """[(separador, oración)] de un párrafo; el separador es el que tenía antes (espacio o salto de línea)."""
    t = re.split(r"(?<=[.!?…])(\s+)", p)
    return [("", t[0])] + [("\n" if "\n" in t[i] else " ", t[i + 1]) for i in range(1, len(t) - 1, 2)]


def trozos(p, limite):
    """Un párrafo entero si entra en un posteo; si no, sus oraciones (y una oración que no entra, sus palabras)."""
    if peso(p) <= limite:
        return [("\n\n", p)]
    res = []
    for sep, o in oraciones(p):
        res += [(sep, o)] if peso(o) <= limite else [(sep if i == 0 else " ", w) for i, w in enumerate(o.split(" "))]
    return res


def hilo(copy, limite=LIMITE):
    """Reparte el texto del posteo en posteos de hasta `limite`. Un párrafo no se corta salvo que no entre solo.
    La pregunta de cierre va si entra (o su última oración, la pregunta); si no, en un posteo aparte.
    Los hashtags van en el primero (el de la imagen); si no entran, en el último; si tampoco, los que entren en el primero."""
    parrafos, tags = partes(copy)
    cierre = parrafos.pop() if len(parrafos) > 2 and any(p.startswith("🧩") for p in parrafos[:-1]) else None
    posteos = []
    for p in parrafos:
        tr = trozos(p, limite)
        for i, (sep, t) in enumerate(tr):
            nuevo = i == 0 and len(tr) > 1  # un párrafo cortado empieza en un posteo nuevo
            if posteos and not nuevo and peso(posteos[-1] + sep + t) <= limite:
                posteos[-1] += sep + t
            else:
                posteos.append(t)
    if cierre:
        pregunta = cierre[cierre.rfind("¿"):] if "¿" in cierre else oraciones(cierre)[-1][1]
        for c in (cierre, pregunta):
            if posteos and peso(posteos[-1] + "\n\n" + c) <= limite:
                posteos[-1] += "\n\n" + c
                break
        else:
            posteos += [t for _, t in trozos(cierre, limite)]
    if tags and posteos:
        t = " ".join(tags)
        destino = next((i for i in dict.fromkeys((0, len(posteos) - 1)) if peso(posteos[i] + "\n\n" + t) <= limite), None)
        if destino is None:
            while tags and peso(posteos[0] + "\n\n" + " ".join(tags)) > limite:
                tags.pop()
            destino, t = 0, " ".join(tags)
        if t:
            posteos[destino] += "\n\n" + t
    return posteos


def texto_alt(copy):
    """Texto alternativo de la imagen: las dos primeras líneas del posteo, sin emojis."""
    lineas = [re.sub(r"[^\w\s'·.,:()/-]", "", ln.replace("⭐", "nota")).strip() for ln in copy.strip().splitlines()[:2]]
    return "Infografía: " + ". ".join(ln for ln in lineas if ln) + ". Su partido, mapa de calor y temporada."


def ruta_copy(png):
    rel = os.path.relpath(os.path.dirname(os.path.abspath(png)), os.path.join(RAIZ, "salida", "png"))
    return os.path.join(RAIZ, "salida", "txt", rel, os.path.basename(png)[:-4] + "_copy.txt")


def _norm(t):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode())


def no_publicar(avisos):
    """Lo que la revisión visual anotó en "## No publicar en X": nombres de archivo (sin .png) o, si no, apellidos."""
    fuera = set()
    for f in avisos:
        dentro = False
        for ln in open(f, encoding="utf-8"):
            if ln.startswith("## "):
                dentro = _norm(ln) == "nopublicarenx"
            elif dentro:
                m = re.match(r"\s*[-*]\s*`?([^\s`:,]+)", ln)
                if m:
                    fuera.add(m.group(1).removesuffix(".png"))
    return fuera


def marcada(archivo, fuera):
    return any(f == archivo if "_" in f else _norm(f) == _norm(archivo.split("_")[0]) for f in fuera)


def fecha(png):
    m = re.search(r"_(\d{4}-\d{2}-\d{2})", os.path.basename(png))
    return m.group(1) if m else ""


def ultima():
    pngs = [p for p in glob.glob(os.path.join(RAIZ, "salida", "png", "**", "*.png"), recursive=True)
            if fecha(p) and not os.path.basename(p).startswith(("PRUEBA", "EJEMPLO"))]
    return max(pngs, key=lambda p: (fecha(p), p))


def revisar(r, que):
    if not r.ok:
        raise RuntimeError(f"{que}: HTTP {r.status_code} ({PISTAS.get(r.status_code, 'error de X')}) {r.text[:400]}")
    return r.json()


def sesion():
    from requests_oauthlib import OAuth1Session
    return OAuth1Session(os.environ["X_API_KEY"], client_secret=os.environ["X_API_SECRET"],
                         resource_owner_key=os.environ["X_ACCESS_TOKEN"], resource_owner_secret=os.environ["X_ACCESS_SECRET"])


def subir(s, png, alt):
    datos = open(png, "rb").read()
    if len(datos) > MAX_IMAGEN:
        from PIL import Image
        b = io.BytesIO()
        Image.open(png).convert("RGB").save(b, "JPEG", quality=92)
        datos = b.getvalue()
    d = revisar(s.post(f"{API}/media/upload", json={"media": base64.b64encode(datos).decode(), "media_category": "tweet_image"},
                       timeout=180), "subir la imagen")
    mid = d["data"]["id"]
    r = s.post(f"{API}/media/metadata", json={"id": mid, "metadata": {"alt_text": {"text": alt[:1000]}}}, timeout=60)
    if not r.ok:
        print(f"  (no se pudo poner el texto alternativo: HTTP {r.status_code})")
    return mid


def postear(s, texto, media=None, responde_a=None):
    cuerpo = {"text": texto}
    if media:
        cuerpo["media"] = {"media_ids": [media]}
    if responde_a:
        cuerpo["reply"] = {"in_reply_to_tweet_id": responde_a}
    return revisar(s.post(f"{API}/tweets", json=cuerpo, timeout=60), "publicar")["data"]["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pngs", nargs="*")
    ap.add_argument("--lista", help="archivo con una ruta de PNG por línea")
    ap.add_argument("--lista-avisos", help="archivo con una ruta de aviso por línea")
    ap.add_argument("--ultima", action="store_true", help="la infografía más nueva de salida/png")
    ap.add_argument("--registro", required=True)
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args()
    leer = lambda f: [ln.strip() for ln in open(f, encoding="utf-8") if ln.strip()] if f else []
    pngs = list(dict.fromkeys(a.pngs + leer(a.lista) + ([ultima()] if a.ultima else [])))
    pngs = [p for p in pngs if p.endswith(".png") and not os.path.basename(p).startswith(("PRUEBA", "EJEMPLO"))]
    pngs.sort(key=fecha)
    fuera = no_publicar(leer(a.lista_avisos))
    registro = json.load(open(a.registro, encoding="utf-8")) if os.path.exists(a.registro) and os.path.getsize(a.registro) else {}
    premium = os.environ.get("X_PREMIUM", "").strip().lower() in ("si", "sí", "true", "1")
    faltan = [c for c in CLAVES if not os.environ.get(c)]
    resumen, errores = [], 0
    if not pngs:
        print("No hay infografías nuevas para X.")
        return 0
    if faltan and not a.probar:
        print(f"::notice::No se publica en X: faltan los secretos {', '.join(faltan)}")
        return 0
    s = None if faltan else sesion()
    if a.probar and s:
        try:
            yo = revisar(s.get(f"{API}/users/me", timeout=30), "revisar las claves")["data"]
            print(f"Claves de X bien: publica como @{yo['username']}")
            resumen.append(f"Claves de X bien: publica como **@{yo['username']}**\n")
        except Exception as e:
            errores += 1
            print(f"ERROR {e}")
            resumen.append(f"ERROR {e}\n")

    def guardar():
        with open(a.registro, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=1)
            f.write("\n")

    for png in pngs:
        rel = os.path.relpath(os.path.abspath(png), RAIZ)
        archivo = os.path.basename(png)[:-4]
        if rel in registro and not a.probar:
            print(f"{archivo}: ya estaba publicada ({registro[rel].get('enlace', '')})")
            continue
        if marcada(archivo, fuera):
            print(f"{archivo}: no se publica (la revisión visual la puso en \"No publicar en X\")")
            resumen.append(f"- **{archivo}**: no se publicó (la revisión visual la puso en *No publicar en X*)")
            continue
        cp = ruta_copy(png)
        if not os.path.exists(png) or not os.path.exists(cp):
            errores += 1
            print(f"ERROR {archivo}: falta {'la imagen' if not os.path.exists(png) else 'el texto del posteo'}")
            resumen.append(f"- **{archivo}**: ERROR, falta {'la imagen' if not os.path.exists(png) else 'el texto del posteo'}")
            continue
        copy = open(cp, encoding="utf-8").read().strip()
        largo = premium and peso(copy) <= LIMITE_PREMIUM
        textos = [re.sub(r"https?://\S+", "", copy).strip()] if largo else hilo(copy)
        print(f"\n== {archivo} ({len(textos)} posteo{'s' if len(textos) > 1 else ''})")
        for t in textos:
            print(f"--- [{peso(t)}]\n{t}")
        if a.probar:
            resumen.append(f"- **{archivo}** ({len(textos)} posteos):\n" + "".join(f"\n```\n{t}\n```\n" for t in textos))
            continue
        try:
            mid = subir(s, png, texto_alt(copy))
            try:
                ids = [postear(s, textos[0], media=mid)]
            except RuntimeError as e:
                if not largo:
                    raise
                print(f"  X no aceptó el posteo largo ({e}); va en hilo")
                textos = hilo(copy)
                ids = [postear(s, textos[0], media=mid)]
            enlace = f"https://x.com/i/status/{ids[0]}"
            registro[rel] = {"publicado": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                             "enlace": enlace, "posteos": ids}
            guardar()
            for t in textos[1:]:
                time.sleep(2)
                ids.append(postear(s, t, responde_a=ids[-1]))
                registro[rel]["posteos"] = ids
                guardar()
            print(f"  publicada: {enlace}")
            resumen.append(f"- **{archivo}**: {enlace} ({len(ids)} posteos)")
        except Exception as e:
            errores += 1
            print(f"ERROR {archivo}: {e}")
            resumen.append(f"- **{archivo}**: ERROR {e}")
        time.sleep(5)
    if a.probar and faltan:
        errores += 1
        print(f"ERROR: faltan los secretos {', '.join(faltan)}")
        resumen.append(f"\nERROR: faltan los secretos {', '.join(faltan)}")
    if os.environ.get("GITHUB_STEP_SUMMARY") and resumen:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(("## Prueba de X (no se publicó nada)\n\n" if a.probar else "## Publicado en X\n\n") + "\n".join(resumen) + "\n")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
