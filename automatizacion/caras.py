"""Caras recortadas (sin fondo) y escudos para la plantilla v3.

cara(player_id, carpeta)  -> ruta a un PNG con fondo transparente, o None
escudo(team_id, carpeta)  -> ruta al PNG del escudo, o None
Las caras de los jugadores seguidos se guardan también en automatizacion/caras/<clave>.png,
para tenerlas aunque falle la fuente (por ejemplo, cuando se arma con BeSoccer)."""
import io, os, shutil, urllib.request
import numpy as np
from PIL import Image, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "https://img.sofascore.com/api/v1"  # las imágenes salen de img.; api. le da 403 a la nube
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
_sesion = None


def _bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


_sesiones = {}


def _mascara(im, modelo):
    from rembg import remove, new_session
    if modelo not in _sesiones:
        _sesiones[modelo] = new_session(modelo)
    return np.asarray(remove(im, session=_sesiones[modelo], only_mask=True)).astype(float) / 255.0


def _sin_fondo(im):
    """Saca el fondo (v2, 18/10/2026).
    1) Dos modelos: u2net_human_seg (silueta de persona completa: hombros y cara enteros, nunca come piel clara)
       e isnet-general-use (detalle del pelo). Se usa la unión, la figura más grande y sin agujeros.
    2) Trimapa: núcleo seguro (erosión), fondo seguro (afuera de la figura dilatada, más el color del fondo
       conectado al borde) y una banda angosta de duda en el contorno.
    3) Matting de forma cerrada (pymatting) en la banda: transparencia real pelo por pelo, también en el blanco
       que queda entre los rulos; y estimación del color de la persona sin el fondo mezclado (sin aureola).
    Si algo falla, usa el método anterior."""
    try:
        return _sin_fondo_matting(im)
    except Exception as ex:  # noqa
        print("  aviso: recorte con matting falló, uso el anterior:", ex)
        return _sin_fondo_v1(im)


def _sin_fondo_matting(im):
    from scipy import ndimage as ndi
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    im = im.convert("RGB")
    a = np.asarray(im).astype(float)
    H, W = a.shape[:2]; lado = min(H, W)
    m_h = _mascara(im, "u2net_human_seg")
    m_i = _mascara(im, "isnet-general-use")
    base = np.maximum(m_h, m_i) > 0.5
    lab, nl = ndi.label(base)
    if nl > 1:
        tam = ndi.sum(base, lab, range(1, nl + 1)); base = lab == (1 + int(np.argmax(tam)))
    base = ndi.binary_fill_holes(base)
    if base.sum() < 0.05 * H * W:
        raise ValueError("máscara vacía")
    # color del fondo (bordes de arriba y costados) y fondo conectado al borde
    k = max(2, lado // 60)
    borde = np.concatenate([a[:k].reshape(-1, 3), a[:, :k].reshape(-1, 3), a[:, -k:].reshape(-1, 3)])
    bg = np.median(borde, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    lowd = dist < 18
    semillas = np.zeros_like(lowd); semillas[0, :] = True
    h7 = int(H * 0.7); semillas[:h7, 0] = True; semillas[:h7, -1] = True
    # trimapa
    r_in, r_out = max(3, int(lado * 0.014)), max(3, int(lado * 0.012))
    nucleo = ndi.binary_erosion(base, iterations=r_in)
    nucleo_h = ndi.binary_erosion(m_h > 0.5, iterations=r_in)          # cara/hombros seguros del modelo de personas
    # el fondo claro no entra en la cara/hombros seguros: con fondo blanco y piel clara se comía mejillas y orejas
    fondo = ndi.binary_propagation(semillas & lowd & ~nucleo_h, mask=lowd & ~nucleo_h)
    seguro_fg = (nucleo | nucleo_h) & ~fondo
    seguro_bg = ~ndi.binary_dilation(base, iterations=r_out) | (fondo & ~ndi.binary_erosion(base, iterations=r_in * 3))
    tri = np.full((H, W), 0.5)
    tri[seguro_bg] = 0.0
    tri[seguro_fg] = 1.0
    # los hombros que tocan el borde de abajo: siempre persona
    tri[-max(2, lado // 100):][base[-max(2, lado // 100):]] = 1.0
    img = a / 255.0
    alfa = estimate_alpha_cf(img, tri, laplacian_kwargs={"epsilon": 1e-6}, cg_kwargs={"maxiter": 2000})
    alfa = np.clip(alfa, 0, 1)
    # sin motas sueltas: solo lo conectado a la figura principal
    sol = alfa > 0.15
    lab, nl = ndi.label(sol)
    if nl > 1:
        tam = ndi.sum(sol, lab, range(1, nl + 1)); keep = lab == (1 + int(np.argmax(tam)))
        alfa = np.where(keep, alfa, 0.0)
    # hombros y camiseta (abajo): la camiseta clara se confunde con el fondo blanco -> silueta del modelo de
    # personas, alisada (contorno prolijo), con transición suave hacia la zona de la cabeza
    r = max(3, lado // 80)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]; disco = xx * xx + yy * yy <= r * r
    hom = ndi.binary_closing(ndi.binary_opening(m_h > 0.5, structure=disco), structure=disco)
    hom = ndi.gaussian_filter(hom.astype(float), max(1.0, lado / 400)) 
    hom = np.clip((hom - 0.5) * 4 + 0.5, 0, 1)
    peso = np.clip((np.arange(H)[:, None] / H - 0.58) / 0.08, 0, 1) * np.ones((1, W))
    alfa = alfa * (1 - peso) + hom * peso
    alfa = np.where(alfa < 0.04, 0.0, np.where(alfa > 0.97, 1.0, alfa))
    fg = estimate_foreground_ml(img, alfa)
    return Image.fromarray(np.dstack([np.clip(fg * 255, 0, 255), alfa * 255]).astype("uint8"), "RGBA")


def _sin_fondo_v1(im):
    """Saca el fondo (método anterior). 1) rembg (modelo isnet-general-use, el que mejor respeta el pelo) da la máscara de la persona.
    2) Lo que tiene el color del fondo y está conectado al borde de arriba o de los costados se borra aunque el
       modelo lo haya incluido (el blanco entre rulos, los halos alrededor de la cabeza).
    3) En el borde, la transparencia sale de la distancia al color del fondo y se le saca al color el fondo
       mezclado (sin aureola clara). 4) Se come 1 px del borde y se suaviza.
    Si rembg no está, borra el fondo claro conectado al borde."""
    global _sesion
    from scipy import ndimage as ndi
    im = im.convert("RGB")
    a = np.asarray(im).astype(float)
    H, W = a.shape[:2]; lado = min(H, W)
    try:
        from rembg import remove, new_session
        if _sesion is None:
            _sesion = new_session("isnet-general-use")
        m = np.asarray(remove(im, session=_sesion, only_mask=True)).astype(float) / 255.0
    except Exception:
        m = None
    k = max(2, lado // 60)
    borde = np.concatenate([a[:k].reshape(-1, 3), a[:, :k].reshape(-1, 3), a[:, -k:].reshape(-1, 3)])
    bg = np.median(borde, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    lowd = dist < 32
    semillas = np.zeros_like(lowd); semillas[0, :] = True
    h7 = int(H * 0.62); semillas[:h7, 0] = True; semillas[:h7, -1] = True
    fondo = ndi.binary_propagation(semillas & lowd, mask=lowd)
    if m is None:
        m = (~fondo).astype(float)
    duro = ndi.binary_fill_holes(m > 0.5)
    # hombros/camiseta (parte de abajo): contorno parejo, sin flecos blancos sueltos
    r = max(2, lado // 120)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]; disco = xx * xx + yy * yy <= r * r
    abajo = np.zeros_like(duro); abajo[int(H * 0.6):] = True
    liso = ndi.binary_closing(ndi.binary_opening(duro, structure=disco), structure=disco)
    duro = np.where(abajo, liso, duro)
    lab, nl = ndi.label(duro)
    if nl > 1:
        tam = ndi.sum(duro, lab, range(1, nl + 1)); duro = lab == (1 + int(np.argmax(tam)))
    interior = ndi.binary_erosion(duro, iterations=max(1, int(lado * 0.012)))
    soporte = ndi.binary_dilation(duro, iterations=max(1, int(lado * 0.02)))
    aw = np.clip((dist - 10) / 55.0, 0, 1)
    alfa = np.where(interior, 1.0, np.where(soporte, np.minimum(aw, m + 0.6), 0.0))
    cerca = ndi.binary_dilation(fondo, iterations=2) & ~fondo
    alfa = np.where(fondo, 0.0, alfa)
    alfa = np.where(cerca, np.minimum(alfa, np.clip((dist - 14) / 60.0, 0, 1)), alfa)
    interior = interior & ~ndi.binary_dilation(fondo, iterations=3)
    # en la mitad de arriba (pelo, orejas): lo claro y sin color del borde es fondo o reflejo blanco -> afuera
    claro = (a.min(axis=2) > bg.mean() - 12) & ((a.max(axis=2) - a.min(axis=2)) < 22)
    claro_suave = (a.max(axis=2) - a.min(axis=2)) < 26   # gris/blanco, sin color de piel
    arriba = np.zeros_like(claro); arriba[:int(H * 0.6)] = True
    borde_ext = soporte & ~ndi.binary_erosion(duro, iterations=max(1, int(lado * 0.02)))
    alfa = np.where(arriba & borde_ext & claro, 0.0, alfa)
    # huecos de fondo encerrados entre el pelo (no tocan el borde de la imagen): manchas claras que llegan al contorno
    bolsillo = (dist < 62) & claro_suave & arriba & soporte
    labb, nb = ndi.label(bolsillo)
    if nb:
        franja = soporte & ~ndi.binary_erosion(duro, iterations=max(2, int(lado * 0.06)))
        toca = np.unique(labb[franja & bolsillo]); toca = toca[toca > 0]
        quitar = np.isin(labb, toca)
        alfa = np.where(quitar, 0.0, alfa); interior = interior & ~quitar
    # matting en el borde: cada píxel es mezcla del color de la persona más cercano y el fondo -> su proporción
    nucleo = ndi.binary_erosion(duro, iterations=max(2, int(lado * 0.03)))
    if nucleo.any():
        idx = ndi.distance_transform_edt(~nucleo, return_indices=True)[1]
        fgl = a[idx[0], idx[1]]
        dv = fgl - bg; den = (dv ** 2).sum(axis=2)
        am = np.clip(((a - bg) * dv).sum(axis=2) / np.maximum(den, 1), 0, 1)
        cabeza = np.zeros_like(interior); cabeza[:int(H * 0.6)] = True
        usar = (den >= 45 ** 2) & ~interior & soporte & cabeza
        alfa = np.where(usar, np.minimum(alfa, am), alfa)
        a = np.where(usar[..., None], fgl, a)   # el borde toma el color de la persona más cercano (sin aureola ni sombra)
    alfa = ndi.minimum_filter(alfa, size=3)
    alfa = ndi.gaussian_filter(alfa, 0.7)
    alfa[interior] = 1.0
    al = np.clip(alfa, 1e-3, 1)[..., None]
    fg = np.where(alfa[..., None] > 0.98, a, np.clip((a - (1 - al) * bg) / al, 0, 255))
    return Image.fromarray(np.dstack([fg, alfa * 255]).astype("uint8"), "RGBA")


_sr = None


def _contorno(im, grosor=None):
    """Línea de contorno negra alrededor de la persona: tapa cualquier resto claro del recorte.
    Mitad del grosor va por dentro del borde y mitad por fuera; donde la figura toca el borde de la imagen
    (hombros abajo) no se dibuja."""
    from scipy import ndimage as ndi
    im = im.convert("RGBA")
    a = np.asarray(im).astype(float)
    H, W = a.shape[:2]
    g = grosor or max(3, min(H, W) // 105)
    m = a[..., 3] > 110
    if not m.any():
        return im
    # una sola figura y sin agujeros: el contorno va solo por afuera (sin puntos ni líneas sueltas)
    lab, nl = ndi.label(m)
    if nl > 1:
        tam = ndi.sum(m, lab, range(1, nl + 1)); m = lab == (1 + int(np.argmax(tam)))
    m = ndi.binary_fill_holes(m)
    # contorno parejo: sin dientes de 1-2 px que el trazo negro exagera
    m = ndi.binary_opening(ndi.binary_closing(m, iterations=2), iterations=1)
    m = ndi.gaussian_filter(m.astype(float), max(1.0, min(H, W) / 300)) > 0.5
    a[..., 3] = np.where(m, np.maximum(a[..., 3], 0), 0)
    dentro = m & ~ndi.binary_erosion(m, iterations=max(1, g // 2 + 1), border_value=1)
    fuera = ndi.binary_dilation(m, iterations=max(1, g - g // 2)) & ~m
    banda = ndi.gaussian_filter((dentro | fuera).astype(float), 0.7)
    banda = np.clip(banda * 1.3, 0, 1)
    rgb = a[..., :3] * (1 - banda[..., None]) + 8 * banda[..., None]
    alfa = np.maximum(a[..., 3], banda * 255)
    return Image.fromarray(np.dstack([rgb, alfa]).astype("uint8"), "RGBA")


def _agrandar(im, lado=600):
    """Agranda la foto chica (150 px) con superresolución FSRCNN x4 (modelos/FSRCNN_x4.pb); si no se puede, LANCZOS."""
    global _sr
    try:
        import cv2
        if _sr is None:
            _sr = cv2.dnn_superres.DnnSuperResImpl_create()
            _sr.readModel(os.path.join(AQUI, "modelos", "FSRCNN_x4.pb")); _sr.setModel("fsrcnn", 4)
        a = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
        b = Image.fromarray(cv2.cvtColor(_sr.upsample(a), cv2.COLOR_BGR2RGB))
        return b.resize((lado, lado), Image.LANCZOS) if b.size != (lado, lado) else b
    except Exception:
        return im.resize((lado, lado), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=2))


def cara(pid, carpeta, clave=None):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"cara_{pid}.png")
    if os.path.exists(ruta):
        return ruta
    try:
        im = Image.open(io.BytesIO(_bajar(f"{BASE}/player/{pid}/image"))).convert("RGB")
        if im.size[0] < 60:
            raise ValueError("imagen muy chica")
        im = _agrandar(im)
        _contorno(_sin_fondo(im)).save(ruta)
        if clave:
            os.makedirs(os.path.join(AQUI, "caras"), exist_ok=True)
            shutil.copy2(ruta, os.path.join(AQUI, "caras", f"{clave}.png"))
        return ruta
    except Exception:
        if clave and os.path.exists(os.path.join(AQUI, "caras", f"{clave}.png")):
            return os.path.join(AQUI, "caras", f"{clave}.png")
        return None


def cara_oficial(clave, carpeta, url=None):
    """Foto oficial del jugador (web del club), en mejor calidad que la de la fuente de datos.
    Se usa la que esté en automatizacion/fotos_oficiales/<clave>.(png|jpg|jpeg|webp).
    Si jugadores.json trae "foto_oficial" (URL directa a la imagen) y se puede bajar, se guarda ahí primero.
    Devuelve la ruta a la versión recortada (sin fondo) o None."""
    dest_dir = os.path.join(AQUI, "fotos_oficiales")
    if url:
        try:
            datos = _bajar(url)
            Image.open(io.BytesIO(datos))  # que sea una imagen
            os.makedirs(dest_dir, exist_ok=True)
            open(os.path.join(dest_dir, f"{clave}.png" if url.lower().endswith(".png") else f"{clave}.jpg"), "wb").write(datos)
        except Exception:
            pass
    fuente = next((os.path.join(dest_dir, f"{clave}.{ext}") for ext in ("png", "jpg", "jpeg", "webp")
                   if os.path.exists(os.path.join(dest_dir, f"{clave}.{ext}"))), None)
    if not fuente:
        return None
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"oficial_{clave}.png")
    if os.path.exists(ruta):
        return ruta
    try:
        im = Image.open(fuente)
        transparente = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 250
        im = im.convert("RGBA") if transparente else _sin_fondo(im.convert("RGB")).convert("RGBA")
        bbox = im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
        if bbox:
            im = im.crop(bbox)
        w, h = im.size  # cuadrado desde arriba: cabeza y hombros, como las caras de la cancha
        lado = min(w, h)
        im = im.crop(((w - lado) // 2, 0, (w - lado) // 2 + lado, lado)).resize((700, 700), Image.LANCZOS)
        _contorno(im).save(ruta)
        return ruta
    except Exception:
        return None


def _escudo_hd(im, lado=600):
    """Escudo de 150 px agrandado a 600 con superresolución (color) y LANCZOS (transparencia), para que
    se vea nítido en el PNG al doble de resolución (marcas de agua, marcador, cancha)."""
    im = im.convert("RGBA")
    if im.size[0] >= lado:
        return im
    alfa = im.getchannel("A")
    # el color de los píxeles transparentes se rellena con el vecino opaco (sin bordes negros al agrandar)
    from scipy import ndimage as ndi
    a = np.asarray(im).astype(float)
    op = a[..., 3] > 8
    if op.any() and not op.all():
        idx = ndi.distance_transform_edt(~op, return_indices=True)[1]
        a[..., :3] = a[idx[0], idx[1], :3]
    rgb = _agrandar(Image.fromarray(a[..., :3].astype("uint8"), "RGB"), lado)
    al = alfa.resize((lado, lado), Image.LANCZOS)
    out = rgb.convert("RGBA"); out.putalpha(al)
    return out


def escudo(tid, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"escudo_{tid}.png")
    if os.path.exists(ruta):
        return ruta
    cache = os.path.join(AQUI, "escudos", f"{tid}.png")
    try:
        im = Image.open(io.BytesIO(_bajar(f"{BASE}/team/{tid}/image"))).convert("RGBA")
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        im.save(cache)
        _escudo_hd(im).save(ruta)
        return ruta
    except Exception:
        if os.path.exists(cache):
            try:
                _escudo_hd(Image.open(cache)).save(ruta)
                return ruta
            except Exception:
                return cache
        return None
