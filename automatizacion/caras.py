"""Caras recortadas (sin fondo) y escudos para la plantilla v3.

cara(player_id, carpeta)  -> ruta a un PNG con fondo transparente, o None
escudo(team_id, carpeta)  -> ruta al PNG del escudo, o None
Las caras de los jugadores seguidos se guardan también en automatizacion/caras/<clave>.png,
para tenerlas aunque falle la fuente (por ejemplo, cuando se arma con BeSoccer)."""
import io, os, shutil, urllib.request
import numpy as np
from PIL import Image, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "https://api.sofascore.com/api/v1"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
_sesion = None


def _bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def _sin_fondo(im):
    """Saca el fondo con rembg (modelo de personas). Si no está, borra el blanco conectado al borde."""
    global _sesion
    try:
        from rembg import remove, new_session
        if _sesion is None:
            _sesion = new_session("u2net_human_seg")
        return remove(im, session=_sesion)
    except Exception:
        from scipy.ndimage import label
        a = np.asarray(im.convert("RGB")).astype(int)
        claro = (a.min(axis=2) > 235)
        lab, _ = label(claro)
        borde = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
        fondo = np.isin(lab, list(borde))
        alfa = Image.fromarray(np.where(fondo, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.2))
        out = im.convert("RGBA"); out.putalpha(alfa)
        return out


def cara(pid, carpeta, clave=None):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"cara_{pid}.png")
    if os.path.exists(ruta):
        return ruta
    try:
        im = Image.open(io.BytesIO(_bajar(f"{BASE}/player/{pid}/image"))).convert("RGB")
        if im.size[0] < 60:
            raise ValueError("imagen muy chica")
        im = im.resize((450, 450), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
        _sin_fondo(im).save(ruta)
        if clave:
            os.makedirs(os.path.join(AQUI, "caras"), exist_ok=True)
            shutil.copy2(ruta, os.path.join(AQUI, "caras", f"{clave}.png"))
        return ruta
    except Exception:
        if clave and os.path.exists(os.path.join(AQUI, "caras", f"{clave}.png")):
            return os.path.join(AQUI, "caras", f"{clave}.png")
        return None


def escudo(tid, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"escudo_{tid}.png")
    if os.path.exists(ruta):
        return ruta
    cache = os.path.join(AQUI, "escudos", f"{tid}.png")
    try:
        im = Image.open(io.BytesIO(_bajar(f"{BASE}/team/{tid}/image"))).convert("RGBA")
        im.save(ruta)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        im.save(cache)
        return ruta
    except Exception:
        return cache if os.path.exists(cache) else None
