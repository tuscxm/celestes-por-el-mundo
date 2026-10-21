# Agente de infografías · Celestes por el mundo (v5, varias fuentes + GitHub)

Desde el 15/10/2026 este repositorio de GitHub (tuscxm/celestes-por-el-mundo) es la única fuente: scripts, jugadores, `procesados.json` y todas las infografías. La tarea programada de Claude ("Infografías Celestes por el mundo (nube)") corre todos los días a las 18:26 de Uruguay en la nube (SofaScore no le responde a los servidores de GitHub, sí a la nube de Claude), sin depender de ninguna computadora.

## Fuentes de datos (no se nombran en las infografías)
- **SofaScore** (api.sofascore.com) es la fuente principal: partido, alineación con nota de cada jugador, estadísticas, mapa de calor, temporada, caras y escudos. Responde desde la nube de Claude, no desde GitHub.
- **Fuentes extra** (`automatizacion/fuentes.py`), se consultan todas cuando el jugador tiene un partido terminado en las fechas revisadas:
  - **FotMob** (www.fotmob.com/api/data): nota, minutos, estadísticas, alineación con notas, cambios y temporada. Sin clave.
  - **API-Football** (v3.football.api-sports.io): nota, minutos y estadísticas por jugador, notas del once y nota de la temporada. Con clave (secreto de red del entorno, encabezado `x-apisports-key`, o variable `API_FOOTBALL_KEY`). **Nunca más de 100 pedidos por día (UTC)**: el contador está en `automatizacion/cuotas.json` y se sube con cada revisión.
  - **football-data.org**: **no se usa desde el 21/10/2026** (solo traía resultado, fecha y jornada, que ya dan las otras fuentes; el usuario no cargó su clave). La función queda en `fuentes.py` por si se vuelve a sumar.
  - **TheSportsDB** (www.thesportsdb.com): resultado y alineación. Clave pública gratuita "123" o `THESPORTSDB_KEY`.
  - **Understat** (understat.com): minutos, xG, xA, tiros y pases clave. Solo LaLiga (no cubre Portugal).
  - **zerozero** (www.zerozero.pt): minutos y resultado de la ficha del jugador.
  - Si a un jugador le falta el ID de API-Football o de football-data.org, el script lo busca una sola vez por el nombre del club (`club`) y lo guarda en `jugadores.json`.
  - Los IDs de cada fuente están en `jugadores.json` (`fotmob_id`, `apifootball_equipo`, `footballdata_equipo`, `understat_equipo`, `club`).
  - **BeSoccer** (es.besoccer.com): no deja entrar a los scripts. **Antes de correr el script**, la tarea de Claude lee con WebFetch las páginas de partidos de cada jugador (ver "BeSoccer como fuente diaria") y deja lo leído en `automatizacion/besoccer_hoy.json`. El script lo toma como una fuente más (nota, minutos, goles, tarjetas, notas del once).
- **Desde cuándo**: las fuentes extra (incluida BeSoccer como fuente diaria) se usan para los partidos **del 18/10/2026 en adelante** (`DESDE` en `fuentes.py`). Los partidos anteriores quedan como estaban (solo SofaScore).
- **Tarjetas**: las rojas (y amarillas) se ven en la cancha junto a la cara de cada jugador; si el protagonista fue expulsado, también al lado de su foto grande, "EXPULSADO AL <minuto>" bajo los minutos y "🟥 Expulsado al <minuto>'" en el texto del posteo.
- **Caras** (desde el 18/10/2026, v2): `caras.py` agranda la foto con superresolución (FSRCNN x4, `modelos/FSRCNN_x4.pb`) y recorta con dos modelos de rembg: `u2net_human_seg` (silueta entera de la persona: nunca come piel clara ni hombros) e `isnet-general-use` (detalle del pelo). Con la unión arma un trimapa y hace matting de forma cerrada con pymatting (transparencia pelo por pelo, también el blanco entre rulos, y color sin aureola). Los hombros salen de la silueta de personas, alisados. El contorno negro va solo por afuera de la figura (sin puntos ni líneas sueltas). Si el matting falla, usa el método anterior. Los modelos BiRefNet/BRIA no entran en la memoria de la nube (se probaron: se cortan).
- **Resolución**: `render_v3.py` saca el PNG a 2160x2700 (mismo diseño de 1080x1350, al doble de nitidez). Los escudos se agrandan a 600 px con superresolución y el mapa de calor se dibuja a 230 dpi.
- **Tarjetas en las tarjetas de datos**: "Su partido", el cuadro de la posición ("Como mediocentro", etc.) y "Temporada" muestran amarillas y rojas con su dibujo (`2[A] · 1[R]` en los datos).
- **El 3-5-2 de la cuenta** (desde el 21/10/2026, campo `rol_352` de `jugadores.json`): las estadísticas separadas se arman como si su equipo jugara 3-5-2. Zagueros: J. M. Rodríguez, F. González, Cáceres, R. Araújo, J. M. Giménez, Mouriño (y Boselli, Piquerez). Carrileros por derecha: Valverde, Amaro, Canobbio; por izquierda: M. Araújo, J. M. Sanabria. Internos: Bernal, Bentancur, Ugarte (y Torreira, F. Díaz). Enganche: Zalazar, Brizuela. Delanteros: Á. Rodríguez, Petit, Satriano, Merentiel, Darwin Núñez. El puesto define la franja (carrileros por su banda, el resto por el centro) y suma lo de ese puesto en TOTALES y en el bloque de la franja, además de lo que le toque por dónde jugó el partido: enganche → todo; delantero → lo de ataque; carrilero o interno → lo de volante (carrileros también son `mixto`).
- **Su franja de la cancha** (campo `zona` de `jugadores.json`, sale del puesto en el 3-5-2): carrileros por derecha `derecha`, por izquierda `izquierda`, el resto `centro`. En la tarjeta del mapa de calor, debajo del mapa, va "POR LA DERECHA / POR EL CENTRO / POR LA IZQUIERDA" con lo que hizo en esa franja: acciones (puntos del mapa de calor), pases precisos, pases clave, regates, recuperaciones, intercepciones · despejes y conducciones. Sale de las acciones con ubicación de SofaScore (rating-breakdown y mapa de calor; y < 33 derecha, 33-67 centro, > 67 izquierda, siempre desde el lado de su equipo). Duelos, faltas y toques no se pueden separar por franja: no van. Si no hay datos con ubicación, no se muestra y queda en los avisos.
- **Volantes, mediocentros y mixtos** (puesto mediocentro o volante por banda en el partido, o `"mixto": true` en `jugadores.json`: Valverde y Araújo): en TOTALES se suman "Pases al último tercio" (pases precisos / intentados que terminaron en el último tercio de la cancha) y "Recup. def · med · ata" (recuperaciones en cada tercio). Salen de las acciones con ubicación de SofaScore; si no están, no se muestran.
- **Lo de ataque en TOTALES** (remates al arco, afuera · bloqueados, al palo, xG, ocasiones claras falladas y creadas, pases clave, xA, centros): va si el jugador es delantero o está entre los 4 más adelantados de su equipo en ese partido (por posición media). **Todo junto** (ataque + último tercio + recuperaciones por tercio) va siempre a los que juegan en la línea del enganche (la línea detrás de los delanteros en dibujos de 4 líneas, como el "3" del 4-2-3-1) y a los dos de afuera de una línea de 4 volantes. Si no entra todo, se sacan primero velocidad, sprints, distancia y otros de defensa; las tarjetas van siempre.
- **En el bloque de la franja** se repite lo de TOTALES pero solo de esa franja: "Pases al último tercio" (si lleva lo de volante), "Remates al arco" (si lleva lo de ataque; sale del mapa de remates, que mide el ancho al revés, ya contemplado) y "Asistencias" (solo si se puede saber sin suponer: si no tuvo, o si todas sus jugadas de pase clave registradas están dentro o todas fuera de la franja; si no, no se muestra).
- **Competiciones**: se arma la infografía de cualquier partido oficial del jugador (liga, copas nacionales, Champions, Europa League, Conference League, Copa Libertadores y Copa Sudamericana). En TEMPORADA van la liga y, si juega alguna, la copa internacional (primero la del partido que se muestra); entran dos competiciones.
- **Cómo se combinan**:
  - **Datos fijos** (resultado, minutos, goles, asistencias, pases, tarjetas, xG...): se usa SofaScore; si SofaScore no lo trae, el de otra fuente. Si las fuentes no coinciden, queda en los avisos (nunca en la infografía).
  - **Valoraciones** (nota del partido, nota media de la temporada y las estrellas de la cancha, que salen de la nota): **promedio de todas las fuentes que traen nota** (SofaScore, FotMob, API-Football; BeSoccer si se usó). El aviso dice qué notas se promediaron.
  - Si una fuente no responde o no trae algo, se sigue sin ella. Nunca se inventa ni se estima.
- **Respaldo automático**: si SofaScore no responde, `respaldo_auto.py` arma la infografía con FotMob (y la nota promediada con API-Football). Si FotMob tampoco sirve, queda el error y se usa **BeSoccer** a mano (ver "Respaldo con BeSoccer").
- Para que las fuentes respondan desde la nube, sus dominios tienen que estar en **Allowed domains** del entorno (claude.ai/code → selector de entorno → Cloud → Default → engranaje → Network access: Custom). Las claves van en **Network secrets** del mismo diálogo.
- Ni la infografía ni el texto del posteo dicen de dónde salen los datos. El aviso trae una sección "Fuentes consultadas" de uso interno.

## Diseño (render_v3.py)
Desde el 18/10/2026: fondo con los colores del club, rayas diagonales y dos escudos de marca de agua (`fondo` en el JSON: rayas por defecto; hay variantes guardadas sol, franja y bandera sin usar); detrás de la cancha de la formación va el escudo del club en silueta blanca; cancha de la formación más chica; abajo, una fila con el MAPA DE CALOR grande y acostado (ataca hacia la derecha, el costado derecho del equipo queda abajo; su franja marcada con un recuadro dorado y el resto apenas oscurecido) con el bloque "POR LA DERECHA / EL CENTRO / LA IZQUIERDA" al lado, más la TEMPORADA; y otra fila con SU PARTIDO y TOTALES a dos columnas, que son siempre los números de todo el partido (solo el bloque del mapa de calor es de la franja). Todas las caras llevan una línea de contorno negra.
Fondo con los colores del club (campo `fondo` de cada camiseta en `jugadores.json`: color 1, color 2, acento), escudo grande de marca de agua, cancha oscura con las caras recortadas del once (estrellas según la nota de cada uno: 8+ = 5, 7,3+ = 4, 6,7+ = 3, 6+ = 2), cara grande del jugador con placa y escudo, minutos y nota, y abajo las tarjetas: su partido, su juego según la posición, mapa de calor y temporada. Tipografía Barlow Condensed (en `fuentes/`, licencia OFL).
Para la imagen grande, en partidos del club, se usa primero la foto oficial que esté en `fotos_oficiales/<clave>.png|jpg` (o la URL directa del campo `foto_oficial` de `jugadores.json`, si la red la deja bajar); si no hay, la de la fuente de datos. Las caras salen de la foto del jugador y se les saca el fondo con rembg. Las de los jugadores seguidos se guardan en `caras/` y los escudos en `escudos/`, para usarlas aunque falle la fuente. Si no hay foto, se usa la figura ilustrada.

Si entró de suplente, la infografía lo marca: la etiqueta dice "SUPLENTE · ENTRÓ DE <puesto>", el recuadro de minutos dice en qué minuto entró, y en la cancha su cara aparece sobre el jugador al que reemplazó, con "⇄ ENTRA <apellido> <minuto>" encima de la cara del que salió (no debajo de la placa, para no pisar la línea de abajo). El apellido de las placas toma las tildes del nombre de `jugadores.json` ("Caceres" → "CÁCERES"). El texto del posteo y el aviso también lo dicen.

## Jugadores
Están en `automatizacion/jugadores.json`. Cada uno tiene `sofascore_id`, placa, altura, pie, nacimiento y colores de camiseta (club y Uruguay, clave "7").

| Jugador | Club | SofaScore | Puesto en el 3-5-2 | Franja |
|---|---|---|---|---|
| Federico Valverde | Real Madrid | 831808 | carrilero | derecha (mixto) |
| Facundo Bernal | Real Betis | 1177404 | interno | centro |
| Santiago Mouriño | Villarreal | 1468046 | zaguero | centro |
| Maximiliano Araújo | Sporting CP | 929193 | carrilero | izquierda (mixto) |
| Álvaro Rodríguez | Bournemouth | 1154587 | delantero | centro |
| Facundo González | Racing de Santander | 1085103 | zaguero | centro |
| Sebastián Cáceres | Celta de Vigo | 924889 | zaguero | centro |
| Gonzalo Petit | Cádiz | 1482378 | delantero | centro |
| Rodrigo Bentancur | Tottenham | 791190 | interno | centro |
| Martín Satriano | Getafe | 973536 | delantero | centro |
| Sebastián Boselli | Getafe | 1392092 | zaguero | centro |
| Juan Manuel Rodríguez | Cagliari | 1485391 | zaguero | centro |
| Rodrigo Zalazar | Sporting CP | 966575 | enganche | centro |
| Miguel Merentiel | Boca Juniors | 892275 | delantero | centro |
| José María Giménez | Deportivo de La Coruña | 325355 | zaguero | centro |
| Kevin Amaro | Genk | 1392533 | carrilero | derecha (mixto) |
| Ronald Araújo | Liverpool (cedido por el Barcelona) | 925097 | zaguero | centro |
| Juan Manuel Sanabria | Real Salt Lake | 874568 | carrilero | izquierda (mixto) |
| Manuel Ugarte | Manchester United | 846425 | interno | centro |
| Agustín Canobbio | Fluminense | 846413 | carrilero | derecha (mixto) |
| Darwin Núñez | Diriyah | 924871 | delantero | centro |
| Fabricio Díaz | Al-Gharafa | 1017428 | interno | centro |
| Lucas Torreira | Galatasaray | 754794 | interno | centro |
| Thiago Brizuela | Liverpool (Uruguay) | 2311172 | enganche | centro |
| Joaquín Piquerez | Palmeiras | 881110 | zaguero | centro |

Para sumar un jugador, se agrega un bloque con su `sofascore_id`. Se saca de https://api.sofascore.com/api/v1/search/all?q=Nombre%20Apellido.

## Regla
Si el jugador jugó (más de 0 minutos), se arma la infografía y se indica si fue TITULAR o SUPLENTE. Si no jugó o su equipo no jugó, no se arma nada y solo se avisa. Cada partido se procesa una sola vez (`procesados.json`).

## Qué hace cada día
1. La tarea de Claude trae el repositorio y corre `bash automatizacion/correr.sh` (hoy y ayer, hora de Uruguay). Eso instala lo que falte, corre `infografia_sofascore.py` y después `publicar.py`.
   - Por cada partido terminado en el que jugaron deja PNG, JSON, `_copy.txt`, mapa de calor y figura.
   - La infografía trae: alineación con caras y el jugador resaltado; minutos y nota; "Su partido"; el cuadro según dónde jugó (decidido por su posición media); el mapa de calor real; y la temporada por competición.
   - Nunca se inventa nada: lo que SofaScore no trae se omite y queda en "avisos". Si SofaScore no responde, sale como error (nunca como "sin partido").
2. `publicar.py` guarda las infografías ordenadas por tipo, jugador y partido (desde el 21/10/2026):
   - `salida/png/<jugador>/<fecha> · <rival> · <competencia>/` la imagen, `salida/json/...` los datos y `salida/txt/...` el texto del posteo (`_copy.txt`). La carpeta del jugador lleva las iniciales del nombre y el apellido (`S. Mouriño`, `J. M. Rodríguez`, `Á. Rodríguez`) para que no se mezclen apellidos repetidos. Ej.: `salida/png/S. Mouriño/2026-10-20 · Liverpool FC · Champions League/Mourino_LiverpoolFC-Villarreal_2026-10-20.png`.
   - Los mapas de calor siguen en `mapas/` y las figuras en `salida/fotos/`. Además actualiza `procesados.json`, `ultima_revision.json` y la galería del README, y si hubo infografías nuevas o errores escribe `avisos/<fecha_hora>.md` (primera línea = título, que empieza por quién jugó).
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

## BeSoccer como fuente diaria (partidos del 18/10/2026 en adelante)
Antes de `correr.sh`, para cada jugador:
1. Abrí con WebFetch `<besoccer>` de `jugadores.json` con `/jugador/partidos/` en lugar de `/jugador/` (si el jugador no tiene `besoccer`, buscalo en es.besoccer.com, y si lo encontrás seguro —mismo nombre, club y nacionalidad uruguaya— agregá la URL a `jugadores.json`). Buscá partidos de hoy y ayer (hora de Uruguay) que ya hayan terminado.
2. Si jugó, abrí la página del partido y la de `/alineaciones` para leer su nota, minutos, goles, asistencias, tarjetas y las notas del once (por dorsal).
3. Escribí `automatizacion/besoccer_hoy.json` (reemplazá el anterior) solo con lo leído. Lo que no aparezca, no lo pongas:
```json
{"fecha_revision": "2026-10-18",
 "jugadores": {"bernal": [{"fecha": "2026-10-18", "local": "Real Betis", "visita": "Sevilla", "goles_local": 1, "goles_visita": 0,
                           "minutos": 90, "titular": true, "nota": 7.2, "goles": 0, "asistencias": 1, "amarillas": 1, "rojas": 0,
                           "notas_once": {"1": 6.8, "6": 7.2}}]}}
```
Si nadie jugó o BeSoccer no responde, dejá `{"fecha_revision": "<hoy>", "jugadores": {}}`. Nunca inventes ni estimes.

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
