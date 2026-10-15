# Agente de infografías · Celestes por el mundo (v4, SofaScore + GitHub)

Desde el 15/10/2026 este repositorio de GitHub (tuscxm/celestes-por-el-mundo) es la única fuente: scripts, jugadores, `procesados.json` y todas las infografías. La tarea programada de Claude corre todos los días a las 18:30 de Uruguay en la nube (SofaScore no le responde a los servidores de GitHub, sí a la nube de Claude), sin depender de ninguna computadora.

## Fuentes de datos (no se nombran en las infografías)
- **SofaScore** (api.sofascore.com) es la fuente principal: partido, alineación con nota de cada jugador, estadísticas, mapa de calor, temporada, caras y escudos. Responde desde la nube de Claude, no desde GitHub.
- **BeSoccer** es el respaldo cuando SofaScore no responde. No deja entrar a los scripts: la tarea de Claude lo lee con su herramienta web (ver "Respaldo con BeSoccer").
- Ni la infografía ni el texto del posteo dicen de dónde salen los datos.

## Diseño (render_v3.py)
Si entró de suplente, la infografía lo marca: la etiqueta dice "SUPLENTE · ENTRÓ DE <puesto>", el recuadro de minutos dice en qué minuto entró, y en la cancha su cara aparece sobre el jugador al que reemplazó, con "⇄ ENTRA <apellido> <minuto>". El texto del posteo y el aviso también lo dicen.
Fondo con los colores del club (campo `fondo` de cada camiseta en `jugadores.json`: color 1, color 2, acento), escudo grande de marca de agua, cancha oscura con las caras recortadas del once (estrellas según la nota de cada uno: 8+ = 5, 7,3+ = 4, 6,7+ = 3, 6+ = 2), cara grande del jugador con placa y escudo, minutos y nota, y abajo las tarjetas: su partido, su juego según la posición, mapa de calor y temporada. Tipografía Barlow Condensed (en `fuentes/`, licencia OFL).
Las caras salen de la foto del jugador y se les saca el fondo con rembg. Las de los cuatro jugadores se guardan en `caras/` y los escudos en `escudos/`, para usarlas aunque falle la fuente. Si no hay foto, se usa la figura ilustrada.

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

## Respaldo con BeSoccer (cuando SofaScore no responde)
Si en `salida_hoy/resumen.json` un jugador figura con `"estado": "error"`:
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
🇺🇾 {NOMBRE} · {Local} {goles}-{goles} {Visitante}
⏱ {minutos}' · ⭐ {nota} (SofaScore)
{goles, asistencias, pases, duelos, recuperaciones}
#CelestesPorElMundo #Uruguay #{club}
