# Monitor de fuentes · Hoy por Hoy Vitoria

Una página web que se actualiza sola y reúne lo que pasa en Vitoria y en Álava, para que la redacción no tenga que entrar cada día en decenas de webs:

- **Hoy**: la portada para ver el día en dos vistazos. Agenda de hoy y de mañana (convocatorias de prensa con hora y lugar, plenos y comisiones, actos de pueblos y asociaciones), lo más relevante de las últimas horas, los próximos 7 días y lo que hay que seguir (plazos, fines de obra, inicios previstos).
- **Calendario**: un calendario mensual que se rellena solo con las fechas que aparecen en las noticias ("las obras terminarán el 30 de mayo", "del 13 de noviembre al 22 de diciembre"…), las convocatorias, las agendas municipales y las efemérides de `efemerides.yaml`.
- **Instituciones**: Ayuntamiento de Vitoria, Diputación, Juntas Generales, Gobierno Vasco (solo lo que toca Álava), Ararteko, Euskotren.
- **Pueblos de Álava**: por cuadrillas. Webs municipales que se pueden leer, cuadrillas y **todo lo que cada ayuntamiento y concejo publica en el BOTHA**, además de lo que otras instituciones dicen de cada pueblo.
- **Boletines**: BOTHA del día completo; del BOPV y del BOE, lo que afecta a Álava. Los trámites rutinarios se ocultan.
- **Asociaciones**: vecinales, colectivos y entidades, con la agenda de Elkarteak.org.
- **Ideas de temas** y **Ya publicado**, para buscar ángulos y no repetir.
- **Guardados**: cada persona marca con ☆ y copia la lista para la reunión.

Es gratis y no necesita cuenta de Claude: solo el enlace. Funciona en el móvil.

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
| Añadir una efeméride o fecha fija | Editar `efemerides.yaml` |
| Buscar RSS de webs nuevas | Actions → **Explorar fuentes** → Run workflow (el informe queda en la rama `diagnostico`) |
| Saber si algo falla | Pestaña **Fuentes** de la página: cada fuente sale en verde o rojo |

Si una fuente sale en rojo varios días seguidos, casi siempre es que esa web ha cambiado la dirección de su RSS. Busca la nueva y cámbiala en `fuentes.yaml`.

Si GitHub envía un correo diciendo que ha desactivado el workflow por inactividad, entra en **Actions** y pulsa **Enable workflow**.

## Fuentes que no se leen automáticamente

El programa respeta el `robots.txt` de cada web: si una web pide no ser leída por programas (Laudio, Eustat, Kanpezu…), no se lee y aparece en "Mirar a mano".

Muchas asociaciones vecinales solo publican en redes sociales, que no se pueden leer gratis de forma automática; sus contactos están en "Mirar a mano". Las fechas del calendario se sacan con reglas, sin IA: cada una muestra la frase de la que sale para comprobarla.

---

## Para quien sepa algo de programación

- `monitor/run.py`: lee las fuentes, detecta municipios y cuadrillas, puntúa la relevancia y genera `docs/datos.json`. Histórico de 21 días en `data/historico.json`.
- `monitor/calendario.py`: extracción de fechas, convocatorias y efemérides.
- `monitor/descubrir.py`: explorador de RSS (workflow *Explorar fuentes*).
- `docs/index.html`: la página (HTML + JS sin dependencias). Lee `datos.json`.
- `.github/workflows/actualizar.yml`: ejecución programada y publicación en GitHub Pages.
- Pruebas sin internet: `python tests/crea_fixtures.py && python monitor/run.py --fixtures tests/fixtures` y después `python -m http.server -d docs`.

Creado por Vania para la redacción de SER Vitoria (noviembre de 2026).

## Correo de la redacción (Gmail propio)

La página puede leer un Gmail creado para la redacción: notas de prensa que llegan por correo y alertas del CENDOJ.
Solo mira los remitentes que aparecen en `fuentes.yaml` (campo `remitentes` de las fuentes `correo-…`); el resto del buzón no se toca ni se publica.

1. Crea la cuenta de Gmail y activa la verificación en dos pasos.
2. En https://myaccount.google.com/apppasswords crea una «contraseña de aplicación» (16 letras).
3. En GitHub, en este repositorio: Settings → Secrets and variables → Actions → New repository secret. Crea dos:
   - `GMAIL_USER`: la dirección completa del Gmail.
   - `GMAIL_APP_PASSWORD`: la contraseña de aplicación.
4. Pide a los gabinetes de prensa que añadan ese Gmail a sus listas y crea en el CENDOJ una alerta (búsqueda de Álava) que avise a ese correo.

Para añadir un remitente nuevo, pon su dominio en la lista `remitentes` de la fuente que corresponda.
La página es pública: no metas en esa lista remitentes personales.
