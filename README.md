# Celestes por el mundo · infografías

Todos los días a las 18:30 (hora de Uruguay) GitHub revisa en SofaScore si **Valverde, Bernal, Mouriño, Araújo** jugaron hoy o ayer
y arma una infografía por cada partido. No depende de ninguna computadora prendida. **No publica nada**: la publicación la hacés vos.

Cuando hay infografías nuevas (o un error), se abre un aviso en [Issues](../../issues) y GitHub te manda un mail.
Cerrá el aviso cuando la publiques o la descartes.

**Última revisión:** 2026-10-15 09:28-03:00 (hora de Uruguay) · fechas 2026-10-14

- **Valverde** jugó 90' (titular, nota 6.8, de mediocentro) en AS Roma 3-4 Real Madrid · UEFA Champions League
- **Bernal** jugó 9' (suplente, nota 6.5, de mediocentro) en Real Betis 3-2 FC Porto · UEFA Champions League
- Mouriño: sin partido hoy ni ayer
- Araújo: sin partido hoy ni ayer

## Últimas infografías (5 en total, todas en [`salida/`](salida))

<table>
<tr><td align="center" valign="top" width="33%"><a href="salida/Valverde_ASRoma-RealMadrid_2026-10-14.png"><img src="salida/Valverde_ASRoma-RealMadrid_2026-10-14.png" width="300"></a><br><sub>FEDERICO VALVERDE · AS Roma 3-4 Real Madrid<br>2026-10-14 · <a href="salida/Valverde_ASRoma-RealMadrid_2026-10-14_copy.txt">texto del posteo</a></sub></td><td align="center" valign="top" width="33%"><a href="salida/Bernal_RealBetis-FCPorto_2026-10-14.png"><img src="salida/Bernal_RealBetis-FCPorto_2026-10-14.png" width="300"></a><br><sub>FACUNDO BERNAL · Real Betis 3-2 FC Porto<br>2026-10-14 · <a href="salida/Bernal_RealBetis-FCPorto_2026-10-14_copy.txt">texto del posteo</a></sub></td><td align="center" valign="top" width="33%"><a href="salida/Mourino_Villarreal-SSCNapoli_2026-10-13.png"><img src="salida/Mourino_Villarreal-SSCNapoli_2026-10-13.png" width="300"></a><br><sub>SANTIAGO MOURIÑO · Villarreal 3-1 SSC Napoli<br>2026-10-13 · <a href="salida/Mourino_Villarreal-SSCNapoli_2026-10-13_copy.txt">texto del posteo</a></sub></td></tr>
<tr><td align="center" valign="top" width="33%"><a href="salida/Araujo_RCLens-SportingCP_2026-10-13.png"><img src="salida/Araujo_RCLens-SportingCP_2026-10-13.png" width="300"></a><br><sub>MAXIMILIANO ARAÚJO · RC Lens 0-2 Sporting CP<br>2026-10-13 · <a href="salida/Araujo_RCLens-SportingCP_2026-10-13_copy.txt">texto del posteo</a></sub></td><td align="center" valign="top" width="33%"><a href="salida/Mourino_Villarreal-Betis_2026-09-14.png"><img src="salida/Mourino_Villarreal-Betis_2026-09-14.png" width="300"></a><br><sub>Mourino Villarreal-Betis 2026-09-14<br>2026-09-14 · <a href="salida/Mourino_Villarreal-Betis_2026-09-14_copy.txt">texto del posteo</a></sub></td></tr>
</table>

## Cómo se usa

- **Correrlo ahora o para una fecha puntual:** pestaña [Actions](../../actions/workflows/infografias.yml) → *Run workflow*. Podés poner una fecha (AAAA-MM-DD), un jugador (`valverde`, `bernal`, `mourino`, `araujo`) y marcar *forzar* para rehacer una que ya estaba.
- **Sumar o sacar jugadores:** editá [`automatizacion/jugadores.json`](automatizacion/jugadores.json) (cómo, en [`automatizacion/AGENTE.md`](automatizacion/AGENTE.md)).
- **Qué ya se procesó:** [`automatizacion/procesados.json`](automatizacion/procesados.json). Si borrás una línea, ese partido se vuelve a armar.
- Los mapas de calor quedan en [`mapas/`](mapas) y las figuras en [`salida/fotos/`](salida/fotos).

Datos: SofaScore. Las figuras son ilustraciones, no fotos de los jugadores.
