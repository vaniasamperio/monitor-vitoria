"""Genera feeds de prueba con la estructura real de cada fuente
(titulares reales vistos el 05-06/11/2026), para probar sin internet."""
from pathlib import Path

F = Path(__file__).parent / "fixtures"
F.mkdir(exist_ok=True)


def rss(titulo, items, encoding="utf-8"):
    cuerpo = []
    for it in items:
        cats = "".join(f"<category><![CDATA[{c}]]></category>" for c in it.get("cats", []))
        desc = f"<description><![CDATA[{it.get('desc', '')}]]></description>" if it.get("desc") else ""
        cuerpo.append(f"<item><title><![CDATA[{it['t']}]]></title><link>{it['l']}</link>"
                      f"<guid>{it['l']}</guid><pubDate>{it['d']}</pubDate>{cats}{desc}</item>")
    xml = (f"<?xml version='1.0' encoding='{encoding}'?><rss version='2.0'><channel>"
           f"<title>{titulo}</title><link>https://example.org</link><description>{titulo}</description>"
           + "".join(cuerpo) + "</channel></rss>")
    return xml.encode(encoding)


B = "https://blogs.vitoria-gasteiz.org/medios/2026/11/"
conv = {"t": "Convocatorias de prensa (09-11-2026)", "l": B + "06/convocatorias-de-prensa-09-11-2026/",
        "d": "Fri, 06 Nov 2026 14:31:18 +0000", "cats": ["Convocatorias"],
        "desc": "<p><strong>Presentación de Ilustrazioaren Eguna</strong></p><p>Participan: Sonia Díaz de Corcuera, "
                "Kike Martínez-Inchausti y Estíbaliz Zearsolo</p><ul><li>Día: lunes, 9 de noviembre</li><li>Hora: 11:30"
                "</li><li>Lugar: Sala Ortuño, Centro Cultural Montehermoso</li></ul><p><strong>Entrega de diplomas de la X "
                "edición de la Quincena del corazón-Bihotz Araba</strong></p><p>Participan: Maider Etxebarria y Kepa Urigoitia"
                "</p><ul><li>Día: lunes, 9 de noviembre</li><li>Hora: 12:00</li><li>Lugar: Salón de recepciones de la Casa "
                "Consistorial</li></ul>"}
notas = [
    conv,
    {"t": "Montes Solidarios encenderá la Navidad en Vitoria-Gasteiz", "l": B + "06/montes-solidarios/",
     "d": "Fri, 06 Nov 2026 12:01:02 +0000", "cats": ["Notas de prensa", "Navidad"],
     "desc": "<p>La iniciativa solidaria vuelve a iluminar la ciudad durante las fiestas.</p>"},
    {"t": "El Ayuntamiento y Mercedes Benz acometerán la reforma de un tramo de la calle Zurrupitieta con una inversión cercana a los 1,2 millones de euros",
     "l": B + "06/zurrupitieta/", "d": "Fri, 06 Nov 2026 11:38:12 +0000", "cats": ["Notas de prensa"],
     "desc": "<p>Las obras mejorarán la urbanización del polígono de Júndiz.</p>"},
    {"t": "El 46,3% de las personas encuestadas en Vitoria-Gasteiz utiliza la bicicleta al menos una vez por semana",
     "l": B + "05/bicicleta-encuesta/", "d": "Thu, 05 Nov 2026 10:12:00 +0000", "cats": ["Notas de prensa"],
     "desc": "<p>Es uno de los datos de la encuesta de movilidad municipal.</p>"},
    {"t": "El Ayuntamiento edita una guía práctica para orientar y ayudar a las familias ante posibles casos de acoso escolar",
     "l": B + "05/guia-acoso-escolar/", "d": "Thu, 05 Nov 2026 09:40:00 +0000", "cats": ["Notas de prensa"]},
]
(F / "ayto-notas.xml").write_bytes(rss("Notas de prensa", notas))
(F / "ayto-convocatorias.xml").write_bytes(rss("Convocatorias – Notas de prensa", [conv]))

M = "https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?idioma=es&uid="
(F / "ayto-movilidad.xml").write_bytes(rss("Movilidad y transporte", [
    {"t": "Aviso de TUVISA: servicio de autobuses afectado por las obras en Portal de Legutiano hasta el 30 de mayo de 2027", "l": M + "a1", "d": "Wed, 04 Nov 2026 23:00:00 GMT"},
    {"t": "Aviso de TUVISA: servicio de autobuses afectado por las obras en Portal de Legutiano hasta el 30 de mayo de 2027", "l": M + "a2", "d": "Tue, 03 Nov 2026 23:00:00 GMT"},
    {"t": "Servicio especial de TUVISA para el concierto de Homenaje a Mecano (6 de noviembre) y de Raphael (7 de noviembre) en el Buesa Arena", "l": M + "a3", "d": "Mon, 02 Nov 2026 23:00:00 GMT"},
]))

A = "https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?idioma=es&uid=app_ib004_"
(F / "ayto-agenda.xml").write_bytes(rss("Agenda institucional", [
    {"t": "Junta de Gobierno Local", "l": A + "11087", "d": "Fri, 06 Nov 2026 08:00 GMT"},
    {"t": "Comisión de Políticas Sociales y Juventud e Igualdad y Convivencia", "l": A + "11012", "d": "Mon, 09 Nov 2026 08:00 GMT"},
    {"t": "Comisión de Promoción Económica, Empleo, Comercio y Turismo y Sociedades Públicas", "l": A + "11013", "d": "Tue, 10 Nov 2026 08:00 GMT"},
    {"t": "Comisión de Hacienda", "l": A + "11099", "d": "Tue, 10 Nov 2026 09:00 GMT"},
    {"t": "Comisión de Euskera, Cultura y Educación y Deporte, Salud y Cooperación", "l": A + "11014", "d": "Tue, 10 Nov 2026 11:00 GMT"},
]))

I = "https://www.irekia.euskadi.eus/es/news/"
(F / "irekia.xml").write_bytes(rss("Irekia - Noticias", [
    {"t": "El Lehendakari Imanol Pradales ha recibido a las y los integrantes de la Euskal Pilota Selekzioa", "l": I + "114067", "d": "Thu, 05 Nov 2026 18:19:13 +0100"},
    {"t": "Andoitz Korta: \"el compromiso del Gobierno Vasco es que Vicinay tenga un proyecto industrial de futuro\"", "l": I + "114060", "d": "Thu, 05 Nov 2026 17:36:30 +0100"},
    {"t": "Osakidetza y la Asociación Contra el Cáncer en Álava fortalecen el apoyo a pacientes oncológicos de la Llanada alavesa con un nuevo punto de atención en Agurain", "l": I + "114058", "d": "Thu, 05 Nov 2026 14:36:24 +0100",
     "desc": "<p>El nuevo punto de atención estará en el centro de salud de Agurain.</p>"},
    {"t": "Pérez Iglesias destaca el papel de la política científica para conectar la proyección global de las universidades y el compromiso con lo local", "l": I + "114049", "d": "Thu, 05 Nov 2026 14:22:00 +0100"},
]))

P = "https://www.euskadi.eus/y22-bopv/es/bopv2/datos/2026/11/"
(F / "bopv.xml").write_bytes(rss("Boletín Nº 212, fecha 05/11/2026", [
    {"t": "RESOLUCIÓN de 26 de octubre de 2026, del rector de la Universidad del País Vasco, por la que se nombra profesor", "l": P + "2604666a.shtml", "d": "Thu, 05 Nov 2026 00:00:00 +0100"},
    {"t": "ANUNCIO de la Delegación Territorial de Vivienda de Álava sobre la adjudicación de viviendas de protección oficial en Vitoria-Gasteiz", "l": P + "2604680a.shtml", "d": "Thu, 05 Nov 2026 00:00:00 +0100"},
    {"t": "RESOLUCIÓN de 28 de octubre de 2026, del secretario general de Acción Exterior, ayudas a la Diáspora Vasca", "l": P + "2604670a.shtml", "d": "Thu, 05 Nov 2026 00:00:00 +0100"},
], encoding="iso-8859-1"))

(F / "diputacion.html").write_text("""<html><body><div class="lista">
<div class="item"><a href="/es/web/arabapress/-/la-diputacion-foral-anima-a-las-familias-a-informarse-sobre-la-adopcion"><img src="x.jpg"></a>
<h3><a href="/es/web/arabapress/-/la-diputacion-foral-anima-a-las-familias-a-informarse-sobre-la-adopcion">La Diputación Foral anima a las familias a informarse sobre la adopción de hermanas y hermanos, menores con necesidades especiales y la adopción abierta</a></h3>
<p><em>Charla informativa para familias interesadas</em></p><span>La Diputación Foral · 06 11 2026 · Servicios sociales</span>
<a href="/es/web/arabapress/-/la-diputacion-foral-anima-a-las-familias-a-informarse-sobre-la-adopcion">Seguir leyendo</a></div>
<div class="item"><h3><a href="/es/web/arabapress/-/haziaraba-lleva-el-arte">Haziaraba lleva el arte a la pequeña infancia de nueve municipios alaveses</a></h3>
<span>La Diputación Foral · 06 11 2026</span></div>
<div class="item"><h3><a href="/es/web/arabapress/-/ramiro-gonzalez-borgona">Ramiro González reivindica el modelo de Borgoña para avanzar en la diferenciación de los vinos de Rioja Alavesa dentro de la DOCa Rioja</a></h3>
<span>La Diputación Foral · 06 11 2026 · Agricultura y ganadería</span></div>
</div></body></html>""", encoding="utf-8")

(F / "gasteizhoy.xml").write_bytes(rss("Gasteiz Hoy", [
    {"t": "La estafa de WhatsApp que pide dinero a tus contactos ya suma 65 casos en Álava", "l": "https://www.gasteizhoy.com/estafa-whatsapp/", "d": "Thu, 05 Nov 2026 17:41:54 +0000"},
    {"t": "Baskonia sigue en el pozo de la Euroliga tras caer en Estambul", "l": "https://www.gasteizhoy.com/baskonia/", "d": "Thu, 05 Nov 2026 20:07:38 +0000"},
]))

E = "https://www.eldiario.es/"
(F / "eldiario-navarra.xml").write_bytes(rss("elDiario.es - Navarra", [
    {"t": "Navarra negocia con fondos buitre la compra de 600 viviendas que perdieron la protección oficial", "l": E + "navarra/fondos-viviendas", "d": "Fri, 06 Nov 2026 08:10:00 +0000",
     "desc": "El Gobierno foral quiere recuperar para el alquiler asequible pisos que salieron del régimen de protección. Los datos muestran que cada vez más familias no pueden pagar el alquiler."},
    {"t": "Navarra cierra el verano con 14 rodajes de producciones audiovisuales en pleno auge por el incentivo fiscal", "l": E + "navarra/rodajes", "d": "Thu, 05 Nov 2026 10:00:00 +0000",
     "desc": "El sector audiovisual crece gracias a los incentivos y atrae a productoras de cine y series."},
]))
(F / "eldiario-cyl.xml").write_bytes(rss("elDiario.es - Castilla y León", [
    {"t": "Vox retira tres preguntas críticas con los consejeros del PP horas después de registrarlas en las Cortes de Castilla y León", "l": E + "cyl/vox", "d": "Fri, 06 Nov 2026 09:00:00 +0000"},
    {"t": "La Fiscalía investiga una agresión sexual de un menor a otro en un piso tutelado de Burgos", "l": E + "cyl/fiscalia", "d": "Thu, 05 Nov 2026 12:00:00 +0000"},
    {"t": "Uno de cada tres pueblos de Soria ya no tiene bar: así se vive la soledad no deseada en el medio rural", "l": E + "cyl/pueblos-sin-bar", "d": "Wed, 04 Nov 2026 07:30:00 +0000",
     "desc": "Un informe de la Diputación revela que la despoblación deja a los mayores sin espacios de encuentro."},
]))
(F / "eldiario-euskadi.xml").write_bytes(rss("elDiario.es - Euskadi", [
    {"t": "Pradales activa el modo electoral en la última sesión de control del Parlamento Vasco antes de las generales", "l": E + "euskadi/pradales", "d": "Fri, 06 Nov 2026 09:36:24 +0000"},
    {"t": "EH Bildu y el consejero Martínez pugnan por el gasto en derivaciones a la privada de la Sanidad vasca", "l": E + "euskadi/derivaciones", "d": "Thu, 05 Nov 2026 20:46:05 +0000"},
    {"t": "Las listas de espera para el psicólogo infantil se duplican en Bizkaia: familias que esperan seis meses", "l": E + "euskadi/psicologo-infantil", "d": "Wed, 04 Nov 2026 06:00:00 +0000",
     "desc": "Un estudio de las asociaciones de familias denuncia la falta de profesionales de salud mental infantil en Osakidetza."},
]))
# eldiario-aragon y otros sin fixture -> simulan una fuente caída
print("fixtures listos en", F)
