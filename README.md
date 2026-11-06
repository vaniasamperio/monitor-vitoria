# Monitor de fuentes · Hoy por Hoy Vitoria

Una página web que se actualiza sola cada mañana con:

- **Instituciones**: notas de prensa del Ayuntamiento de Vitoria-Gasteiz, avisos de movilidad, sala de prensa de la Diputación Foral de Álava, Irekia (Gobierno Vasco) y BOPV. Del Gobierno Vasco y el BOPV se queda solo con lo que menciona Álava, aunque se puede ver todo.
- **Agenda y convocatorias**: las convocatorias de prensa del Ayuntamiento (con hora y lugar) y los plenos y comisiones de los próximos días.
- **Ideas de temas**: temas de fondo que cuentan medios de otros territorios y que se pueden bajar a Vitoria o Álava, con pistas de fuentes locales para el ángulo. Se descartan el fútbol, los sucesos y la política de partidos.
- **Ya publicado**: lo que ha sacado la prensa local, para no repetir.
- **Guardados**: cada persona marca con ☆ lo que le interesa y copia la lista para la reunión de contenidos.

Es gratis y no necesita cuenta de Claude ni de nada: solo el enlace. Funciona en el móvil.

---

## Instalación (una sola vez, unos 15 minutos)

Hace falta una cuenta de GitHub. Lo ideal es que sea **de la emisora** o de alguien que se quede, porque la página quedará colgada de esa cuenta.

### 1. Crear el repositorio
1. Entra en <https://github.com/new>.
2. Nombre: `monitor-vitoria` (o el que quieras; formará parte del enlace).
3. Márcalo como **Public** (las Pages gratuitas lo exigen; todo lo que contiene es información pública).
4. Pulsa **Create repository**.

### 2. Subir los archivos
1. En el repositorio recién creado, pulsa **uploading an existing file**.
2. Arrastra **todo el contenido** de la carpeta `monitor-ser-vitoria` (no la carpeta, lo que hay dentro).
3. Pulsa **Commit changes**.

> ⚠️ La carpeta `.github` empieza por punto y algunos ordenadores la ocultan. Comprueba que en GitHub aparece `.github/workflows/actualizar.yml`. Si no aparece: **Add file → Create new file**, escribe como nombre `.github/workflows/actualizar.yml`, pega dentro el contenido de ese archivo y guarda.

### 3. Dar permisos y activar la página
1. **Settings → Actions → General** → abajo, en *Workflow permissions*, marca **Read and write permissions** → **Save**.
2. **Settings → Pages** → en *Source* elige **GitHub Actions**.

### 4. Primera actualización
Es normal que en **Actions** ya aparezca una ejecución en rojo: se lanzó al subir los archivos, antes de activar Pages. No pasa nada.

1. Pestaña **Actions** → a la izquierda **Actualizar monitor** → botón **Run workflow** → **Run workflow**.
2. Espera 2-3 minutos hasta que salga el check verde.
3. El enlace de la página aparece en **Settings → Pages** (será algo como `https://NOMBRE.github.io/monitor-vitoria/`). Ese es el enlace para la redacción.

A partir de ahí se actualiza sola:
- todos los días hacia las 6:15 (7:15 en verano),
- y los laborables también hacia las 10:45 y las 16:30 (para pillar las convocatorias del día siguiente).

---

## Uso diario

- Abre el enlace. Arriba pone cuándo se actualizó.
- **NUEVO** en ámbar = ha entrado en las últimas 24 horas.
- Buscador: filtra todas las pestañas a la vez (“vivienda”, “Zabalgana”, “Etxebarria”…).
- ☆ guarda un elemento en *Guardados* (se guarda en ese navegador). *Copiar lista* lo deja listo para pegar en el correo o el WhatsApp.

## Mantenimiento (sin programar)

Todo se hace desde la web de GitHub, con el icono del lápiz ✏️:

| Quiero… | Qué hago |
|---|---|
| Actualizar ahora | Actions → Actualizar monitor → Run workflow |
| Añadir una fuente con RSS | Editar `fuentes.yaml`, copiar un bloque y cambiar `id`, `nombre` y `url` |
| Quitar una fuente | En `fuentes.yaml`, añadirle `activa: false` |
| Afinar las ideas de temas | Editar `temas.yaml`: palabras clave, pistas locales, palabras que descartan |
| Saber si algo falla | Pestaña **Fuentes** de la página: cada fuente sale en verde o rojo |

Si una fuente sale en rojo varios días seguidos, casi siempre es que esa web ha cambiado la dirección de su RSS. Busca la nueva y cámbiala en `fuentes.yaml`.

Si GitHub envía un correo diciendo que ha desactivado el workflow por inactividad, entra en **Actions** y pulsa **Enable workflow**.

## Fuentes que no se leen automáticamente

El **BOTHA**, la sala de prensa completa de la Diputación y otras webs no permiten la lectura automática. Por eso aparecen como enlaces de consulta manual en la pestaña *Fuentes*. La Diputación se lee solo desde su portada, que muestra las últimas notas.

---

## Para quien sepa algo de programación

- `monitor/run.py`: lee las fuentes, clasifica y genera `docs/datos.json`. Guarda el histórico (21 días) en `data/historico.json`.
- `docs/index.html`: la página (HTML + JS sin dependencias). Lee `datos.json`.
- `.github/workflows/actualizar.yml`: ejecución programada y publicación en GitHub Pages.
- Pruebas sin internet: `python tests/crea_fixtures.py && python monitor/run.py --fixtures tests/fixtures` y después `python -m http.server -d docs`.

Creado por Vania para la redacción de SER Vitoria (noviembre de 2026).
