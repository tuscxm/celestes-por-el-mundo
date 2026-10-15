# Agente de infografías · Celestes por el mundo (v4, SofaScore + GitHub)

Desde el 15/10/2026 todo corre en GitHub Actions (`.github/workflows/infografias.yml`), todos los días a las 18:30 de Uruguay, sin depender de ninguna computadora. Este repositorio es la única fuente: scripts, jugadores, `procesados.json` y todas las infografías.

## Fuente de datos
Todo sale de **SofaScore** (api.sofascore.com), que responde desde la nube: partido, alineación, estadísticas del jugador, nota, mapa de calor y temporada por competición. Ya no hacen falta API-Football ni BeSoccer (esos scripts quedan en la carpeta por si se quieren volver a usar).

## Jugadores
Están en `automatizacion/jugadores.json`. Cada uno tiene `sofascore_id`, placa, altura, pie, nacimiento y colores de camiseta (club y Uruguay, clave "7").

| Jugador | Club | SofaScore |
|---|---|---|
| Federico Valverde | Real Madrid | 831808 |
| Facundo Bernal | Real Betis | 1177404 |
| Santiago Mouriño | Villarreal | 1468046 |
| Maximiliano Araújo | Sporting CP | 929193 |

Para sumar un jugador, se agrega un bloque con su `sofascore_id`. Se saca de https://api.sofascore.com/api/v1/search/all?q=Nombre%20Apellido.

## Regla
Si el jugador jugó (más de 0 minutos), se arma la infografía y se indica si fue TITULAR o SUPLENTE. Si no jugó o su equipo no jugó, no se arma nada y solo se avisa. Cada partido se procesa una sola vez (`procesados.json`).

## Qué hace cada día (GitHub Actions)
1. Instala Python, Playwright (Chromium) y la fuente Inter.
2. Corre `python automatizacion/infografia_sofascore.py automatizacion/jugadores.json --dias 2 --procesados automatizacion/procesados.json --salida salida_hoy`: revisa hoy y ayer (hora de Uruguay). Por cada partido terminado en el que jugaron deja PNG, JSON, `_copy.txt`, mapa de calor y figura, y un `resumen.json` con el estado de cada jugador.
   - La infografía trae: alineación con el jugador resaltado; minutos y nota de SofaScore; "Su partido"; el cuadro según dónde jugó (decidido por su posición media); el mapa de calor real; y la temporada por competición.
   - Nunca se inventa nada: lo que SofaScore no trae se omite y queda en "avisos".
3. `automatizacion/publicar.py` guarda todo en `salida/`, `mapas/` y `salida/fotos/`, actualiza `procesados.json`, `ultima_revision.json` y la galería del README, y hace commit.
4. Si hubo infografías nuevas o errores, abre un issue que empieza por quién jugó (con las imágenes y el texto del posteo). GitHub lo manda por mail. Si la corrida entera falla, también abre un issue.
5. **No publica nada.** La publicación en Instagram se hace solo con la aprobación del usuario.

## Para correrlo a mano con una fecha
En GitHub: Actions → *Infografías diarias* → *Run workflow*, con fecha, jugador y *forzar*.
En una compu: `python3 automatizacion/infografia_sofascore.py automatizacion/jugadores.json --fecha 2026-09-14 --clave mourino --salida prueba --forzar`

## Texto del posteo (lo genera el script en `_copy.txt`)
🇺🇾 {NOMBRE} · {Local} {goles}-{goles} {Visitante}
⏱ {minutos}' · ⭐ {nota} (SofaScore)
{goles, asistencias, pases, duelos, recuperaciones}
#CelestesPorElMundo #Uruguay #{club}
