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
- **Boletines (BOTHA, BOPV, BOE)**: el titular tiene que decir qué se decide, sobre qué cosa concreta y dónde, para que se entienda sin abrir el enlace. Busca el objeto al final del título original (el proyecto, la obra, la ayuda, la ordenanza, el lugar) y ponlo delante. Nombra bien al organismo: si lo firma una delegación del Gobierno Vasco, es el Gobierno Vasco, no la Diputación.
  - Mal: "Diputación: transición Energética y Sostenibilidad de Álava, por la que se concede autorización administrativa previa…"
  - Bien: "Gobierno Vasco saca a información pública dos plantas solares en Vitoria: 'Lovaina Solar' y 'Zaramaga FV'"
  - Mal: "Oficio Circular 9/2026. Asunto: declaración jurada de elaboración"
  - Bien: "La DOCa Rioja pide a bodegas y compradores de mosto la declaración jurada de elaboración de la vendimia"

**tribunales** (`{"id": "qué ha pasado"}`)
- Una o dos frases claras: qué se ha decidido, a quién afecta y si toca Álava.

**explicaciones** (`{"id": "qué es y qué supone"}`) — para la lista `explicar` (anuncios del tablón de la sede electrónica del Ayuntamiento de Vitoria)
- Pon también un titular en `titulos` para cada uno: qué se decide, sobre qué y dónde (≤110 caracteres).
- La explicación, en una o dos frases: qué se aprueba o se anuncia, a quién afecta, y si hay plazo para alegar o pedir algo, hasta cuándo.
- Usa `texto_botha` cuando venga; si está vacío, explica solo con el título, la ficha y el origen, sin inventar. Si no se puede saber de qué trata (p. ej. "Trámite de información pública" sin más), dilo así: "El tablón no da más detalle; hay que abrir el documento".
- Nunca nombres de personas particulares (arquitectos, propietarios, solicitantes). Cargos públicos, empresas e instituciones sí.

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

**tribunales**: las alertas del CENDOJ que llegan por correo (fuente `correo-cendoj`) solo traen el número de resolución; el texto está tras un captcha y no se debe intentar abrir ni saltar. Para esas, escribe nota solo si la misma resolución aparece en una nota del TSJPV o en un teletipo (cuéntalo con esa información); si no, no escribas nada.

**sucesos** (`{"resumen": "...", "destacados": [{"titulo", "detalle", "id"}]}`)
- Es el "parte del día" de Álava a partir de `sucesos` (Policía Local, Ertzaintza, emergencias, teletipos y tribunales de las últimas 36 horas).
- `resumen`: tres o cuatro frases, como lo contaría un boletín de radio: lo más grave primero, con lugar y hora si se sabe.
- `destacados`: cuatro como máximo, con el `id` del elemento original y en `detalle` una frase con lo esencial.
- Agrupa lo que sea el mismo hecho contado por varias fuentes. Si no hay nada relevante, no escribas `sucesos`.
- Nunca pongas nombres de detenidos, víctimas ni menores, aunque salgan en el original; solo edad y sexo si los da la fuente.

## Formato de `data/ia_respuesta.json`

```json
{
  "titulos": {"abc123": "Titular claro"},
  "tribunales": {"def456": "Qué ha pasado"},
  "enfoques": {"ghi789": {"enfoque": "...", "preguntas": ["...", "...", "..."], "llamar": ["...", "..."]}},
  "eustat": [{"titulo": "...", "dato_alava": "...", "fecha": "2026-11-07", "enlace": "https://..."}],
  "buzon": {"resumen": "...", "destacados": [{"titulo": "...", "por_que": "...", "area": "..."}]},
  "sucesos": {"resumen": "...", "destacados": [{"titulo": "...", "detalle": "...", "id": "..."}]}
}
```
