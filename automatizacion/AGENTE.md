# Agente de infografías · Celestes por el mundo (v4, SofaScore + GitHub)

Desde el 15/10/2026 este repositorio de GitHub (tuscxm/celestes-por-el-mundo) es la única fuente: scripts, jugadores, `procesados.json` y todas las infografías. La tarea programada de Claude corre todos los días a las 18:30 de Uruguay en la nube (SofaScore no le responde a los servidores de GitHub, sí a la nube de Claude), sin depender de ninguna computadora.

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

## Qué hace cada día
1. La tarea de Claude trae el repositorio y corre `bash automatizacion/correr.sh` (hoy y ayer, hora de Uruguay). Eso instala lo que falte, corre `infografia_sofascore.py` y después `publicar.py`.
   - Por cada partido terminado en el que jugaron deja PNG, JSON, `_copy.txt`, mapa de calor y figura.
   - La infografía trae: alineación con el jugador resaltado; minutos y nota de SofaScore; "Su partido"; el cuadro según dónde jugó (decidido por su posición media); el mapa de calor real; y la temporada por competición.
   - Nunca se inventa nada: lo que SofaScore no trae se omite y queda en "avisos". Si SofaScore no responde, sale como error (nunca como "sin partido").
2. `publicar.py` guarda todo en `salida/`, `mapas/` y `salida/fotos/`, actualiza `procesados.json`, `ultima_revision.json` y la galería del README, y si hubo infografías nuevas o errores escribe `avisos/<fecha_hora>.md` (primera línea = título, que empieza por quién jugó).
3. Claude mira cada PNG (textos cortados o encimados, jugador resaltado, números razonables). Si ve un problema, lo agrega al aviso.
4. Claude hace commit y push. Al llegar un archivo nuevo a `avisos/`, el workflow `aviso.yml` abre un issue y GitHub manda el mail.
5. `control.yml` revisa a las 23:30 que la revisión del día haya llegado; si no, abre un issue.
6. **No publica nada.** La publicación en Instagram se hace solo con la aprobación del usuario.

## Para correrlo a mano con una fecha
`bash automatizacion/correr.sh --fecha 2026-09-14 --clave mourino --forzar` (en la nube de Claude o en una compu con Python).

## Texto del posteo (lo genera el script en `_copy.txt`)
🇺🇾 {NOMBRE} · {Local} {goles}-{goles} {Visitante}
⏱ {minutos}' · ⭐ {nota} (SofaScore)
{goles, asistencias, pases, duelos, recuperaciones}
#CelestesPorElMundo #Uruguay #{club}
