# Explicar las resoluciones del CENDOJ (tarea diaria en el ordenador de Vania)

Las alertas del CENDOJ llegan al Gmail de la redacción hacia las 8:10 y la página las recoge en la lectura de las 8:17
(fuente `correo-cendoj`). Esta tarea las explica. Necesita el **navegador integrado de la aplicación de Claude** del
ordenador de Vania, porque desde la nube el CENDOJ pide captcha.

1. `git pull`. En `docs/datos.json`, toma los elementos con `"fuente": "correo-cendoj"` cuyo `id` NO esté en
   `docs/ia.json` → `tribunales`. Si no hay ninguno, termina diciendo "Sin resoluciones nuevas".
2. Abre en el navegador integrado el `enlace` del primero (`preview_start`). Con `javascript_tool` ejecuta el contenido
   de `monitor/cendoj_pdf.js` y después `await window._cendoj([{id, url: enlace}, …])` con todos (máximo 25).
3. Si alguno devuelve `CAPTCHA`, para ahí: no intentes resolverlo ni saltarlo. Explica solo los que se hayan leído.
4. Escribe `data/ia_respuesta.json` con:
   - `titulos`: `{id: titular}` — qué ha pasado, en castellano llano, ≤110 caracteres. Ejemplo: "La Audiencia confirma
     el desahucio por precario pedido por Ensanche 21". Si hay varias del mismo tipo (p. ej. bancos y cláusulas suelo),
     dilo ("otro recurso…").
   - `tribunales`: `{id: "dos frases: qué se juzgaba y qué se decide, quién gana, si cabe recurso"}`.
   - Nunca nombres de personas físicas (partes, abogados, procuradores). Empresas e instituciones sí.
5. `python3 monitor/ia_guardar.py`, `git add docs/ia.json`, commit "IA: resoluciones CENDOJ AAAA-MM-DD", `git pull --rebase`, `git push`.
