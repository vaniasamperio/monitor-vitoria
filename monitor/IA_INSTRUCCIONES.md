# Instrucciones para la revisión diaria con IA

Lo ejecuta cada mañana una tarea programada de Claude. El objetivo es que el monitor le sirva a un periodista de un vistazo: titulares que se entiendan, enfoques de verdad para las ideas y lo importante del buzón, los tribunales y Eustat.

## Pasos

1. En la raíz del repositorio, ejecuta `python3 monitor/ia_preparar.py`. Crea `data/ia_pendiente.json`.
2. Lee `data/ia_pendiente.json` y escribe `data/ia_respuesta.json` con el formato de abajo.
3. Ejecuta `python3 monitor/ia_guardar.py`.
4. `git add docs/ia.json`, haz commit con el mensaje `IA: titulares y enfoques AAAA-MM-DD`, después `git pull --rebase` y `git push`. La página se publica sola.

## Qué escribir

Siempre en castellano (traduce si el original está en euskera), en tono de redacción de radio, sin inventar nada que no esté en el texto.

**titulos** (`{"id": "titular"}`)
- Quién + qué ha pasado, 110 caracteres como máximo. Ejemplo: "Juntas Generales piden declarar Álava zona de sequía y ayudas para el campo".
- Sin números de expediente, fechas de resolución ni fórmulas ("por la que se…", "al objeto de…").
- Si el lugar importa, ponlo ("Okondo regulará el cambio de lonjas a viviendas").
- Si un elemento no aporta nada (trámite, aviso interno), no le pongas titular.

**tribunales** (`{"id": "qué ha pasado"}`)
- Una o dos frases claras: qué se ha decidido, a quién afecta y si toca Álava.

**enfoques** (`{"id": {"enfoque": "...", "preguntas": [...], "llamar": [...]}}`)
- `enfoque`: un ángulo concreto para Vitoria o Álava, en una o dos frases. Barrio, pueblo, colectivo o dato concreto; no vale "ver si pasa aquí".
- `preguntas`: tres preguntas que se haría un periodista de verdad sobre ese tema en Álava, concretas y distintas entre sí. Nada de "¿Hay datos de Álava?".
- `llamar`: dos o tres fuentes concretas de Álava, por cargo o entidad (por ejemplo, "Servicio municipal de Personas Mayores", "UAGA", "AV Zabalgana Batuz"). Sin inventar nombres de personas.

**eustat** (lista)
- Busca en la web (WebSearch) las estadísticas de Eustat publicadas en los dos últimos días, en Irekia o en prensa. No entres en eustat.eus, porque la web pide no ser leída por programas.
- Para cada una: `titulo`, `dato_alava` (el dato de Álava tal y como lo da la fuente, sin calcular nada), `fecha` y `enlace`.
- Si no hay nada nuevo, deja la lista vacía (`[]`).

**buzon** (`{"resumen": "...", "destacados": [{"titulo", "por_que", "area"}]}`)
- Con las áreas y los ejemplos de `buzon`, señala lo que se repite: el mismo problema o la misma calle o barrio en varias quejas, o un área que se dispara.
- `resumen`: dos frases. `destacados`: tres como máximo, y en `por_que` di las cifras (por ejemplo, "4 quejas en 3 días en la calle Txiribia").
- No incluyas datos personales de quien se queja.

## Formato de `data/ia_respuesta.json`

```json
{
  "titulos": {"abc123": "Titular claro"},
  "tribunales": {"def456": "Qué ha pasado"},
  "enfoques": {"ghi789": {"enfoque": "...", "preguntas": ["...", "...", "..."], "llamar": ["...", "..."]}},
  "eustat": [{"titulo": "...", "dato_alava": "...", "fecha": "2026-11-07", "enlace": "https://..."}],
  "buzon": {"resumen": "...", "destacados": [{"titulo": "...", "por_que": "...", "area": "..."}]}
}
```
