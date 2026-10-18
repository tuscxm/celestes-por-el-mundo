# Agente de infografías · Celestes por el mundo (v5, varias fuentes + GitHub)

Desde el 15/10/2026 este repositorio de GitHub (tuscxm/celestes-por-el-mundo) es la única fuente: scripts, jugadores, `procesados.json` y todas las infografías. La tarea programada de Claude ("Infografías Celestes por el mundo (nube)") corre todos los días a las 18:26 de Uruguay en la nube (SofaScore no le responde a los servidores de GitHub, sí a la nube de Claude), sin depender de ninguna computadora.

## Fuentes de datos (no se nombran en las infografías)
- **SofaScore** (api.sofascore.com) es la fuente principal: partido, alineación con nota de cada jugador, estadísticas, mapa de calor, temporada, caras y escudos. Responde desde la nube de Claude, no desde GitHub.
- **Fuentes extra** (`automatizacion/fuentes.py`), se consultan todas cuando el jugador tiene un partido terminado en las fechas revisadas:
  - **FotMob** (www.fotmob.com/api/data): nota, minutos, estadísticas, alineación con notas, cambios y temporada. Sin clave.
  - **API-Football** (v3.football.api-sports.io): nota, minutos y estadísticas por jugador, notas del once y nota de la temporada. Con clave (secreto de red del entorno, encabezado `x-apisports-key`, o variable `API_FOOTBALL_KEY`). **Nunca más de 100 pedidos por día (UTC)**: el contador está en `automatizacion/cuotas.json` y se sube con cada revisión.
  - **football-data.org** (api.football-data.org): resultado, fecha y jornada (el plan gratis no trae jugadores). Con clave (encabezado `X-Auth-Token` o `FOOTBALL_DATA_KEY`). **Nunca más de 10 pedidos por minuto** (el script espera 6,5 s entre pedidos).
  - **TheSportsDB** (www.thesportsdb.com): resultado y alineación. Clave pública gratuita "123" o `THESPORTSDB_KEY`.
  - **Understat** (understat.com): minutos, xG, xA, tiros y pases clave. Solo LaLiga (no cubre Portugal).
  - **zerozero** (www.zerozero.pt): minutos y resultado de la ficha del jugador.
  - Los IDs de cada fuente están en `jugadores.json` (`fotmob_id`, `apifootball_equipo`, `footballdata_equipo`, `understat_equipo`, `club`).
- **Cómo se combinan**:
  - **Datos fijos** (resultado, minutos, goles, asistencias, pases, tarjetas, xG...): se usa SofaScore; si SofaScore no lo trae, el de otra fuente. Si las fuentes no coinciden, queda en los avisos (nunca en la infografía).
  - **Valoraciones** (nota del partido, nota media de la temporada y las estrellas de la cancha, que salen de la nota): **promedio de todas las fuentes que traen nota** (SofaScore, FotMob, API-Football; BeSoccer si se usó). El aviso dice qué notas se promediaron.
  - Si una fuente no responde o no trae algo, se sigue sin ella. Nunca se inventa ni se estima.
- **Respaldo automático**: si SofaScore no responde, `respaldo_auto.py` arma la infografía con FotMob (y la nota promediada con API-Football). Si FotMob tampoco sirve, queda el error y se usa **BeSoccer** a mano (ver "Respaldo con BeSoccer").
- Para que las fuentes respondan desde la nube, sus dominios tienen que estar en **Allowed domains** del entorno (claude.ai/code → selector de entorno → Cloud → Default → engranaje → Network access: Custom). Las claves van en **Network secrets** del mismo diálogo.
- Ni la infografía ni el texto del posteo dicen de dónde salen los datos. El aviso trae una sección "Fuentes consultadas" de uso interno.

## Diseño (render_v3.py)
Fondo con los colores del club (campo `fondo` de cada camiseta en `jugadores.json`: color 1, color 2, acento), escudo grande de marca de agua, cancha oscura con las caras recortadas del once (estrellas según la nota de cada uno: 8+ = 5, 7,3+ = 4, 6,7+ = 3, 6+ = 2), cara grande del jugador con placa y escudo, minutos y nota, y abajo las tarjetas: su partido, su juego según la posición, mapa de calor y temporada. Tipografía Barlow Condensed (en `fuentes/`, licencia OFL).
Para la imagen grande, en partidos del club, se usa primero la foto oficial que esté en `fotos_oficiales/<clave>.png|jpg` (o la URL directa del campo `foto_oficial` de `jugadores.json`, si la red la deja bajar); si no hay, la de la fuente de datos. Las caras salen de la foto del jugador y se les saca el fondo con rembg. Las de los cuatro jugadores se guardan en `caras/` y los escudos en `escudos/`, para usarlas aunque falle la fuente. Si no hay foto, se usa la figura ilustrada.

Si entró de suplente, la infografía lo marca: la etiqueta dice "SUPLENTE · ENTRÓ DE <puesto>", el recuadro de minutos dice en qué minuto entró, y en la cancha su cara aparece sobre el jugador al que reemplazó, con "⇄ ENTRA <apellido> <minuto>". El texto del posteo y el aviso también lo dicen.

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
   - La infografía trae: alineación con caras y el jugador resaltado; minutos y nota; "Su partido"; el cuadro según dónde jugó (decidido por su posición media); el mapa de calor real; y la temporada por competición.
   - Nunca se inventa nada: lo que SofaScore no trae se omite y queda en "avisos". Si SofaScore no responde, sale como error (nunca como "sin partido").
2. `publicar.py` guarda todo en `salida/`, `mapas/` y `salida/fotos/`, actualiza `procesados.json`, `ultima_revision.json` y la galería del README, y si hubo infografías nuevas o errores escribe `avisos/<fecha_hora>.md` (primera línea = título, que empieza por quién jugó).
3. Claude mira cada PNG (textos cortados o encimados, jugador resaltado, números razonables). Si ve un problema, lo agrega al aviso.
4. Claude hace commit y push. Al llegar un archivo nuevo a `avisos/`, el workflow `aviso.yml` abre un issue y GitHub manda el mail.
5. `control.yml` revisa a las 23:30 que la revisión del día haya llegado; si no, abre un issue.
6. **No publica nada.** La publicación en Instagram se hace solo con la aprobación del usuario.

## Respaldo con BeSoccer (cuando SofaScore y FotMob no responden)
Si en `salida_hoy/resumen.json` un jugador sigue con `"estado": "error"` (el respaldo automático tampoco pudo):
1. Abrí con la herramienta web su página de partidos: `<besoccer>` de `jugadores.json` con `/jugador/partidos/` en lugar de `/jugador/` (ej.: https://es.besoccer.com/jugador/partidos/santiago-mourino-3240357). Buscá partidos de las fechas revisadas (hoy y ayer, hora de Uruguay).
2. Si no hubo partido, o no jugó (banco / no convocado), o no terminó: armá el JSON solo con `clave`, `fecha` y `estado` y corrélo igual (así el aviso queda bien).
3. Si jugó: abrí la página del partido (`/partido/...`) y la de `/alineaciones`, y la ficha del jugador para la temporada. Completá una copia de `automatizacion/besoccer_plantilla.json`:
   - `once`: el once inicial dividido en líneas según la formación, del arco al ataque, en el orden que muestra la página; cada jugador `[dorsal, apellido, nota]`.
   - `posicion`: BeSoccer abrevia en español: POR arquero, LD lateral derecho, LI lateral izquierdo, DFC defensor central, MCD/MC/MCO mediocentro, MD/ED volante por derecha, MI/EI volante por izquierda, DC delantero.
   - `minutos`: 90 si jugó completo; si salió o entró, el minuto del cambio.
   - Si entró de suplente: `titular` false y `entro` con el minuto y el apellido del jugador al que reemplazó (sale en la página de eventos o de alineaciones). `posicion` es el puesto en el que entró.
   - Lo que no aparezca: no lo pongas. Nunca inventes ni estimes.
4. Corré `python3 automatizacion/armar_besoccer.py <tu_json> --salida salida_hoy --procesados automatizacion/procesados.json` y después otra vez `GITHUB_REPOSITORY=tuscxm/celestes-por-el-mundo GITHUB_REPOSITORY_OWNER=tuscxm python3 automatizacion/publicar.py salida_hoy`.

## Para correrlo a mano con una fecha
`bash automatizacion/correr.sh --fecha 2026-09-14 --clave mourino --forzar` (en la nube de Claude o en una compu con Python).

## Texto del posteo (lo genera el script en `_copy.txt`)
```
🇺🇾 {NOMBRE} · {Local} {goles}-{goles} {Visitante}
⏱ {minutos}' · ⭐ {nota}
🔁 Entró al {minuto}' por {jugador que salió}, como {puesto}   (solo si fue suplente)
{goles, asistencias, pases, duelos, recuperaciones}
#CelestesPorElMundo #Uruguay #{club}
```
Sin mencionar la fuente de los datos.
