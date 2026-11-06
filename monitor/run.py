#!/usr/bin/env python3
"""
Monitor de fuentes · Hoy por Hoy Vitoria

Lee las fuentes de fuentes.yaml, clasifica lo que encuentra (temas.yaml),
detecta municipios de Álava, puntúa la relevancia, construye el calendario
(calendario.py + efemerides.yaml) y genera docs/datos.json para la web.

Uso:
    python monitor/run.py                 # lectura normal (internet)
    python monitor/run.py --fixtures DIR  # pruebas con páginas guardadas en DIR
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calendario  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
HISTORICO = RAIZ / "data" / "historico.json"
SALIDA = RAIZ / "docs" / "datos.json"
MADRID = ZoneInfo("Europe/Madrid")

DIAS_HISTORICO = 21
DIAS_IDEAS = 7
MAX_RESUMEN = 420
UMBRAL_IDEA = 5.0
USER_AGENT = "MonitorHoyPorHoyVitoria/1.0 (lector RSS para uso periodistico)"
BONITO = {"cada vez mas": "cada vez más", "estadistica": "estadística", "radiografia": "radiografía",
          "deficit": "déficit", "record": "récord", "en los ultimos anos": "en los últimos años", "%": "porcentajes"}

# ---------------------------------------------------------------- Álava
# Municipio -> cuadrilla, con las variantes con que aparece escrito
MUNICIPIOS = {
    "Añana": ("Añana", ["añana", "gesaltza"]),
    "Armiñón": ("Añana", ["arminon"]),
    "Berantevilla": ("Añana", ["berantevilla"]),
    "Iruña de Oca": ("Añana", ["iruna de oca", "iruna oka", "nanclares"]),
    "Kuartango": ("Añana", ["kuartango", "cuartango"]),
    "Lantarón": ("Añana", ["lantaron"]),
    "Ribera Alta": ("Añana", ["ribera alta", "erriberagoitia"]),
    "Ribera Baja": ("Añana", ["ribera baja", "erribera beitia", "rivabellosa"]),
    "Valdegovía": ("Añana", ["valdegovia", "gaubea"]),
    "Zambrana": ("Añana", ["zambrana"]),
    "Amurrio": ("Ayala", ["amurrio"]),
    "Artziniega": ("Ayala", ["artziniega", "arceniega"]),
    "Ayala": ("Ayala", ["ayala", "aiara"]),
    "Laudio/Llodio": ("Ayala", ["llodio", "laudio"]),
    "Okondo": ("Ayala", ["okondo", "oquendo"]),
    "Arraia-Maeztu": ("Montaña Alavesa", ["arraia-maeztu", "arraya-maestu", "maeztu"]),
    "Bernedo": ("Montaña Alavesa", ["bernedo"]),
    "Campezo": ("Montaña Alavesa", ["campezo", "kanpezu"]),
    "Valle de Arana": ("Montaña Alavesa", ["valle de arana", "harana"]),
    "Lagrán": ("Montaña Alavesa", ["lagran"]),
    "Peñacerrada": ("Montaña Alavesa", ["penacerrada", "urizaharra"]),
    "Baños de Ebro": ("Rioja Alavesa", ["banos de ebro", "manueta"]),
    "Elciego": ("Rioja Alavesa", ["elciego", "eltziego"]),
    "Elvillar": ("Rioja Alavesa", ["elvillar", "bilar"]),
    "Kripan": ("Rioja Alavesa", ["kripan", "cripan"]),
    "Labastida": ("Rioja Alavesa", ["labastida", "bastida"]),
    "Laguardia": ("Rioja Alavesa", ["laguardia", "biasteri"]),
    "Lanciego": ("Rioja Alavesa", ["lanciego", "lantziego"]),
    "Lapuebla de Labarca": ("Rioja Alavesa", ["lapuebla de labarca"]),
    "Leza": ("Rioja Alavesa", ["leza"]),
    "Moreda de Álava": ("Rioja Alavesa", ["moreda"]),
    "Navaridas": ("Rioja Alavesa", ["navaridas"]),
    "Oyón-Oion": ("Rioja Alavesa", ["oyon", "oion"]),
    "Samaniego": ("Rioja Alavesa", ["samaniego"]),
    "Villabuena de Álava": ("Rioja Alavesa", ["villabuena", "eskuernaga"]),
    "Yécora": ("Rioja Alavesa", ["yecora", "iekora"]),
    "Agurain/Salvatierra": ("Llanada Alavesa", ["salvatierra", "agurain"]),
    "Alegría-Dulantzi": ("Llanada Alavesa", ["alegria-dulantzi", "dulantzi"]),
    "Asparrena": ("Llanada Alavesa", ["asparrena", "araia"]),
    "Barrundia": ("Llanada Alavesa", ["barrundia"]),
    "Elburgo": ("Llanada Alavesa", ["elburgo", "burgelu"]),
    "Iruraiz-Gauna": ("Llanada Alavesa", ["iruraiz"]),
    "San Millán": ("Llanada Alavesa", ["san millan", "donemiliaga"]),
    "Zalduondo": ("Llanada Alavesa", ["zalduondo", "zalduendo"]),
    "Aramaio": ("Gorbeialdea", ["aramaio", "aramayona"]),
    "Arratzua-Ubarrundia": ("Gorbeialdea", ["arratzua", "ubarrundia"]),
    "Legutio": ("Gorbeialdea", ["legutio", "legutiano", "villarreal de alava"]),
    "Urkabustaiz": ("Gorbeialdea", ["urkabustaiz", "urcabustaiz", "izarra"]),
    "Zigoitia": ("Gorbeialdea", ["zigoitia", "cigoitia"]),
    "Zuia": ("Gorbeialdea", ["zuia", "zuya", "murgia"]),
    "Vitoria-Gasteiz": ("Vitoria-Gasteiz", ["vitoria", "gasteiz"]),
}
ALAVA_GENERAL = ["alava", "araba", "alaves", "alavesa", "alaveses", "alavesas", "llanada", "rioja alavesa",
                 "montana alavesa", "cuadrilla de", "txagorritxu", "foronda", "salburua", "zabalgana", "lakua",
                 "judimendi", "abetxuko", "arasur", "jundiz", "zaramaga", "sansomendi", "arana", "errekaleor"]


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower()


def patron(palabras: list[str]) -> re.Pattern | None:
    trozos = []
    for p in palabras:
        p = normaliza(str(p)).strip()
        if not p:
            continue
        esc = re.escape(p)
        if not re.search(r"\w", p):
            trozos.append(esc)
        elif len(p) <= 4:
            trozos.append(rf"\b{esc}\b")
        else:
            trozos.append(rf"\b{esc}")
    return re.compile("|".join(trozos)) if trozos else None


RX_MUNI = [(nombre, cuadrilla, re.compile(r"\b(" + "|".join(re.escape(v) for v in variantes) + r")\b"))
           for nombre, (cuadrilla, variantes) in MUNICIPIOS.items()]
RX_ALAVA_GENERAL = patron(ALAVA_GENERAL)
RX_EUSKADI = patron(["euskadi", "pais vasco", "vasco", "vasca", "vascos", "vascas", "bizkaia", "vizcaya", "gipuzkoa",
                     "guipuzcoa", "bilbao", "donostia", "san sebastian", "lehendakari", "osakidetza", "ertzaintza",
                     "pradales", "eusko", "euskera", "euskal", "lanbide", "eitb"])

# Relevancia: lo que suele ser noticia y lo que es trámite
RX_NOTICIA = patron(["presupuesto", "subvencion", "ayudas", "ordenanza", "impuesto", "tasa", "plan ", "licitac",
                     "adjudica", "obras", "inversion", "millones", "convocatoria", "oferta publica de empleo",
                     "huelga", "cierre", "cierra", "apertura", "abre", "inaugur", "nuevo", "nueva",
                     "por primera vez", "aprobacion definitiva", "aprobacion inicial", "mocion", "denuncia",
                     "protesta", "reclama", "vecinos", "vecinal", "sequia", "incendio", "vivienda",
                     "residencia", "colegio", "centro de salud", "estudio", "informe", "encuesta",
                     "premio", "record", "acuerdo", "convenio", "proyecto", "reforma", "rehabilitacion",
                     "fiestas", "festival", "jornadas", "presenta", "denuncia", "alerta"])
RX_SUCESO = patron(["detenido", "detenida", "detenidos", "detencion", "arrestad", "robo", "robos", "hurto", "atraco",
                    "agresion", "agredid", "apunal", "herido", "herida", "heridos", "fallecid", "muere", "muerto",
                    "atropell", "colision", "choque", "incendio", "rescate", "rescatad", "desaparecid",
                    "policia local", "ertzaintza", "guardia civil", "estafa", "droga", "incautad", "bomberos",
                    "sos deiak", "pelea", "reyerta", "accidente de trafico", "salida de via", "vuelco"])
RX_JUDICIAL = patron(["juicio", "condena", "condenad", "sentencia", "audiencia provincial", "juzgado", "fiscalia",
                      "absuelto", "absuelta", "procesad", "acusad"])
RX_RUTINA = patron(["notificacion", "notificaciones", "citacion", "emplazamiento", "edicto", "cedula",
                    "embargo", "padron", "nombramiento", "nombra ", "delegacion de funciones",
                    "correccion de errores", "cuenta general", "cese ", "jubilacion", "comision de servicios",
                    "toma de posesion", "personal eventual", "deslinde", "operaciones de reconocimiento",
                    "expediente de credito", "modificacion de credito", "transferencia de credito",
                    "requerimiento", "procedimiento ordinario", "procedimiento abreviado", "recurso contencioso",
                    "aprobacion del calendario fiscal", "exposicion publica de la cuenta", "baja de oficio",
                    "inscripcion padronal", "rectificacion", "anuncio de cobranza"])


# ---------------------------------------------------------------- utilidades
def coincidencias(rx, texto: str) -> set[str]:
    return set(m.group(0) for m in rx.finditer(texto)) if rx else set()


def html_a_texto(fragmento: str) -> str:
    if not fragmento:
        return ""
    sopa = BeautifulSoup(fragmento, "html.parser")
    for t in sopa(["script", "style", "iframe", "img", "figure"]):
        t.decompose()
    for t in sopa.find_all(["br"]):
        t.replace_with("\n")
    for t in sopa.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "tr"]):
        t.insert_before("\n" + ("• " if t.name == "li" else ""))
        t.insert_after("\n")
    texto = html.unescape(sopa.get_text())
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    texto = re.sub(r"La entrada .* se public[oó] primero en .*$", "", texto, flags=re.S)
    texto = re.sub(r"The post .* appeared first on .*$", "", texto, flags=re.S)
    return texto.strip()


def recorta(texto: str, n: int = MAX_RESUMEN) -> str:
    texto = texto.strip()
    return texto if len(texto) <= n else texto[:n].rsplit(" ", 1)[0] + "…"


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def de_iso(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def ident(*partes: str) -> str:
    return hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- descarga
_robots: dict = {}
ses = requests.Session()
ses.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})


def robots_permite(url: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = ses.get(base + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    try:
        return _robots[base].can_fetch(USER_AGENT, url)
    except Exception:
        return True


def descarga(url: str, fixtures: Path | None, fid: str, accept: str | None = None) -> bytes:
    if fixtures:
        for ext in (".xml", ".html", ".json"):
            f = fixtures / f"{fid}{ext}"
            if f.exists():
                return f.read_bytes()
        raise FileNotFoundError(f"no hay fixture para {fid}")
    if not robots_permite(url):
        raise PermissionError("la web pide no ser leída automáticamente (robots.txt)")
    ultimo = None
    for intento in range(3):
        try:
            r = ses.get(url, timeout=25, headers={"Accept": accept} if accept else None)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            ultimo = e
            time.sleep(3 * (intento + 1))
    raise ultimo


# ---------------------------------------------------------------- lectores
def lee_rss(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    feed = feedparser.parse(contenido)
    if feed.bozo and not feed.entries:
        raise ValueError(f"feed ilegible: {feed.bozo_exception}")
    items = []
    for e in feed.entries[: fuente.get("max", 60)]:
        titulo = html_a_texto(e.get("title", "")).replace("\n", " ").strip()
        enlace = e.get("link") or e.get("id") or ""
        if not titulo or not enlace:
            continue
        resumen = e.get("summary", "") or ""
        cuerpo = e.content[0].get("value", "") if e.get("content") else ""
        fecha = None
        for campo in ("published_parsed", "updated_parsed"):
            if e.get(campo):
                fecha = datetime(*e[campo][:6], tzinfo=timezone.utc)
                break
        mt = re.match(r"^(20\d\d)-(\d\d)-(\d\d):\s*(.+)$", titulo)
        if mt:
            titulo = mt.group(4)
            fecha = fecha or datetime(int(mt.group(1)), int(mt.group(2)), int(mt.group(3)), tzinfo=MADRID)
            th = re.search(r"\b(\d{1,2})[:.](\d{2})\s*h", html_a_texto(resumen))
            if th and 6 <= int(th.group(1)) <= 23:
                fecha = fecha.replace(hour=int(th.group(1)), minute=int(th.group(2)))
        texto_res = html_a_texto(resumen or cuerpo)
        items.append({"titulo": titulo, "enlace": enlace, "texto": texto_res,
                      "texto_largo": html_a_texto(cuerpo) if cuerpo else texto_res,
                      "fecha": fecha, "categorias": [t.get("term", "") for t in e.get("tags", []) if t.get("term")]})
    return items


FECHA_DMY = re.compile(r"\b(\d{1,2})[ ./-](\d{1,2})[ ./-](20\d\d)\b")


def lee_html(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    """Webs sin RSS: enlaces que contienen 'patron_enlace'."""
    sopa = BeautifulSoup(contenido, "html.parser")
    patron_enlace = fuente.get("patron_enlace", "")
    base = fuente.get("base") or fuente["url"]
    vistos: dict = {}
    for a in sopa.find_all("a", href=True):
        if patron_enlace not in a["href"]:
            continue
        enlace = urljoin(base, a["href"]).split("?")[0]
        titulo = " ".join(a.get_text(" ").split())
        if len(titulo) < 15 or titulo.lower().startswith(("seguir leyendo", "leer m", "ver m")):
            titulo = ""
        bloque = a.find_parent(["article", "li", "div"])
        tb = " ".join(bloque.get_text(" ").split()) if bloque else ""
        it = vistos.setdefault(enlace, {"titulo": "", "enlace": enlace, "texto": "", "_b": "", "fecha": None, "categorias": []})
        if titulo and len(titulo) > len(it["titulo"]):
            it["titulo"] = titulo
        if tb and (not it["_b"] or len(tb) < len(it["_b"])):
            it["_b"] = tb
    out = []
    for it in vistos.values():
        b = it.pop("_b")
        if not it["titulo"]:
            continue
        m = FECHA_DMY.search(b)
        if m:
            d, mes, a_ = map(int, m.groups())
            try:
                it["fecha"] = datetime(a_, mes, d, tzinfo=MADRID)
            except ValueError:
                pass
            b = b[:m.start()]
        if not it["fecha"]:                      # fecha en la dirección (EFE: /2026-11-06/, Europa Press: -20261106...)
            m = re.search(r"/(20\d\d)-(\d\d)-(\d\d)/", it["enlace"]) or re.search(r"-(20\d\d)(\d\d)(\d\d)(\d\d)(\d\d)\d*\.html", it["enlace"])
            if m:
                g = list(map(int, m.groups()))
                try:
                    it["fecha"] = datetime(g[0], g[1], g[2], *(g[3:5] if len(g) > 3 else (0, 0)), tzinfo=MADRID)
                except ValueError:
                    pass
        it["texto"] = " ".join(b.replace(it["titulo"], " ").split()).strip(" ·|-")
        if len(it["texto"]) < 30:                 # restos de maquetación ("marcatime", "Leer más"…)
            it["texto"] = ""
        it["texto_largo"] = it["texto"]
        out.append(it)
    return out


def lee_diputacion(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    """Sala de prensa de la Diputación (portada): bloques journal-content-article."""
    sopa = BeautifulSoup(contenido, "html.parser")
    out = []
    for blq in sopa.select("div.journal-content-article"):
        a = blq.find("a", href=re.compile(r"/web/arabapress/-/"))
        h = blq.find(["h3", "h2", "h4"])
        if not a or not h:
            continue
        sub = blq.find("em")
        cats = blq.get_text(" ", strip=True)
        m = FECHA_DMY.search(cats)
        fecha = None
        if m:
            d, mes, a_ = map(int, m.groups())
            try:
                fecha = datetime(a_, mes, d, tzinfo=MADRID)
            except ValueError:
                pass
        texto = sub.get_text(" ", strip=True) if sub else ""
        out.append({"titulo": h.get_text(" ", strip=True), "enlace": urljoin(fuente["url"], a["href"]),
                    "texto": texto, "texto_largo": texto, "fecha": fecha, "categorias": []})
    if not out:                       # si cambian la maqueta, lector genérico
        return lee_html(contenido, {**fuente, "patron_enlace": "/web/arabapress/-/"}, hoy)
    return out


def lee_botha(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    """Portada del BOTHA: sumario completo del boletín del día, con su jerarquía."""
    sopa = BeautifulSoup(contenido, "html.parser")
    texto_pag = sopa.get_text(" ")
    m = re.search(r"Bolet[ií]n\s*n[ºo°]\s*(\d+)\s*del\s*\w+,\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(20\d\d)", texto_pag, re.I)
    fecha = None
    numero = m.group(1) if m else ""
    if m:
        mes = calendario.MESES.get(m.group(3).lower())
        if mes:
            fecha = datetime(int(m.group(4)), mes, int(m.group(2)), 7, 0, tzinfo=MADRID)
    cur: dict = {}
    out = []
    for e in sopa.find_all(lambda t: (t.name == "div" and "titulo_bloque_resultados" in (t.get("class") or []))
                           or (t.name == "span" and (t.get("id") or "").endswith("lblAnuResumen"))):
        if e.name == "div":
            nivel = int(re.sub(r"\D", "", e.get("id") or "") or 0)
            cur[nivel] = e.get_text(" ", strip=True)
            for k in [k for k in cur if k > nivel]:
                del cur[k]
            continue
        a = e.find("a", href=True)
        titulo = (a or e).get_text(" ", strip=True)
        if not titulo:
            continue
        pdf = None
        if a:
            mm = re.search(r"Boletines/(\d{4})/(\d+)/([\w]+_C)\.xml", a["href"])
            if mm:
                pdf = f"https://www.araba.eus/botha/Boletines/{mm.group(1)}/{mm.group(2)}/{mm.group(3)}.pdf"
        organismo = cur.get(3) or cur.get(2) or ""
        org_bonito = organismo if not organismo.isupper() else organismo.title().replace(" De ", " de ").replace(" Del ", " del ")
        if cur.get(2) and cur.get(3) and cur[2] not in ("Municipios", "Cuadrillas", "Concejos"):
            org_bonito = f"{cur[2]} · {org_bonito}"
        out.append({"titulo": titulo, "enlace": pdf or "https://www.araba.eus/botha/inicio/SGBO5001.aspx",
                    "texto": org_bonito, "texto_largo": titulo, "bloque": cur.get(1, ""),
                    "fecha": fecha, "categorias": [cur.get(1, ""), organismo], "organismo": organismo,
                    "boletin": f"BOTHA nº {numero}"})
    return out


def lee_boe(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    """Sumario del BOE (API de datos abiertos): solo lo que menciona Álava."""
    d = json.loads(contenido)
    out = []

    def recorre(o, ctx):
        if isinstance(o, dict):
            ctx2 = dict(ctx)
            if "nombre" in o and "codigo" in o:
                ctx2["dep"] = o["nombre"]
            if "titulo" in o and "identificador" in o:
                texto = f"{o['titulo']} {ctx2.get('dep', '')}"
                if coincidencias(RX_ALAVA_GENERAL, normaliza(texto)) or re.search(r"vitoria|gasteiz", normaliza(texto)):
                    url = o.get("url_html") or (o.get("url_pdf") or {}).get("texto")
                    out.append({"titulo": o["titulo"], "enlace": url, "texto": ctx2.get("dep", ""),
                                "texto_largo": o["titulo"], "fecha": datetime.combine(hoy, datetime.min.time(), MADRID),
                                "categorias": [ctx2.get("dep", "")], "organismo": ctx2.get("dep", "")})
            for v in o.values():
                recorre(v, ctx2)
        elif isinstance(o, list):
            for v in o:
                recorre(v, ctx)
    recorre(d, {})
    return out


MES_ABREV = {"urt": 1, "ots": 2, "mar": 3, "api": 4, "mai": 5, "eka": 6, "uzt": 7, "abu": 8, "ira": 9, "urr": 10,
             "aza": 11, "abe": 12, "ene": 1, "feb": 2, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9,
             "oct": 10, "nov": 11, "dic": 12}
RX_ABREV = re.compile(r"\b(" + "|".join(MES_ABREV) + r")\.?\s+(\d{1,2})\b", re.I)          # "AZA 15"
RX_DMA = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MES_ABREV) + r")\.?\s+(20\d\d)\b", re.I)   # "04 nov. 2026"
PREFIJOS = re.compile(r"^(berria irakurri|leer noticia|leer m[aá]s|irakurri gehiago|gehiago irakurri)\s*", re.I)


def lee_liferay(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    """Webs municipales de la plataforma foral (Liferay): enlaces '/-/' a contenidos."""
    sopa = BeautifulSoup(contenido, "html.parser")
    vistos: dict = {}
    for a in sopa.find_all("a", href=True):
        h = a["href"]
        if "/-/" not in h or "/-/reg/" in h:
            continue
        enlace = urljoin(fuente["url"], h).split("?")[0]
        titulo = PREFIJOS.sub("", " ".join(a.get_text(" ").split()))
        if len(titulo) < 12 or titulo.lower().startswith(("seguir leyendo", "leer m", "ver m", "gehiago", "irakurri")):
            titulo = ""
        bloque = a.find_parent(["article", "li", "div"])
        tb = " ".join(bloque.get_text(" ").split()) if bloque else ""
        it = vistos.setdefault(enlace, {"titulo": "", "enlace": enlace, "texto": "", "_b": "", "fecha": None, "categorias": []})
        if titulo and len(titulo) > len(it["titulo"]):
            it["titulo"] = titulo
        if tb and len(tb) < 600 and (not it["_b"] or len(tb) > len(it["_b"])):
            it["_b"] = tb
    out = []
    for it in vistos.values():
        b = it.pop("_b")
        if not it["titulo"]:
            continue
        # fecha de publicación ("04 nov. 2026") en el titular o el bloque
        m = RX_DMA.search(it["titulo"]) or RX_DMA.search(b)
        if m:
            try:
                it["fecha"] = datetime(int(m.group(3)), MES_ABREV[m.group(2).lower()], int(m.group(1)), tzinfo=MADRID)
            except ValueError:
                pass
            it["titulo"] = " ".join(RX_DMA.sub(" ", it["titulo"]).split())
        else:
            m = FECHA_DMY.search(b)
            if m:
                d, mes, a_ = map(int, m.groups())
                try:
                    it["fecha"] = datetime(a_, mes, d, tzinfo=MADRID)
                except ValueError:
                    pass
        # fecha de un acto ("AZA 15"): va al calendario
        ev = RX_ABREV.search(b.replace(it["titulo"], " "))
        if ev and not m:
            try:
                f = date(hoy.year, MES_ABREV[ev.group(1).lower()], int(ev.group(2)))
                if f < hoy - timedelta(days=120):
                    f = f.replace(year=hoy.year + 1)
                it["evento"] = f.isoformat()
            except ValueError:
                pass
        # programas de cursos pasados ("2023-2024"): fuera
        años = [int(x) for x in re.findall(r"\b(20\d\d)\b", it["titulo"] + " " + b[:200])]
        if años and max(años) < hoy.year:
            continue
        resto = b.replace(it["titulo"], " ")
        resto = RX_ABREV.sub(" ", FECHA_DMY.sub(" ", resto))
        resto = PREFIJOS.sub("", " ".join(resto.split()).strip(" ·|-"))
        it["texto"] = recorta(resto, 300)
        it["texto_largo"] = it["texto"]
        out.append(it)
    return out[:25]


# ---------------------------------------------------------------- titulares claros (reglas)
INFINITIVOS = {"aprobar": "aprueba", "conceder": "concede", "convocar": "convoca", "autorizar": "autoriza",
               "adjudicar": "adjudica", "modificar": "modifica", "declarar": "declara", "desestimar": "desestima",
               "estimar": "estima", "ordenar": "ordena", "resolver": "resuelve", "establecer": "establece",
               "regular": "regula", "aceptar": "acepta", "ratificar": "ratifica", "designar": "designa",
               "prorrogar": "prorroga", "iniciar": "inicia", "someter": "somete", "dar": "da"}
RX_CABECERA = re.compile(
    r"^(?:(moci[oó]n|decreto foral|decreto|acuerdo|orden foral|orden|resoluci[oó]n|norma foral|ley|anuncio|edicto|"
    r"instrucci[oó]n|circular|proposici[oó]n no de ley)\b\s*(?:n\.?[ºo°]\s*)?[\d/\-]*\s*,?\s*(?:de\s+\d{1,2}\s+de\s+\w+(?:\s+de\s+\d{4})?)?"
    r"(?:,?\s*(?:del|de la|de los)\s+[^.,]{3,90})?[.,]?\s*)", re.I)
RX_FORMULA = re.compile(r"^(?:al objeto de|por (?:la|el) que se|por (?:la|el) que|relativ[oa] a|sobre|para)\s+", re.I)


def _verbo(t: str) -> str:
    m = re.match(r"^(\w+)\b(.*)$", t)
    if m and m.group(1).lower() in INFINITIVOS:
        return INFINITIVOS[m.group(1).lower()] + m.group(2)
    return t


def actor(it: dict, fuente: dict) -> str:
    org = normaliza(it.get("organismo", "") + " " + it.get("texto", ""))
    if fuente.get("tipo") == "botha":
        if "juntas generales" in org:
            return "Juntas Generales"
        if "diputacion" in org or "departamento" in org or "consejo de gobierno" in org or "foral" in org:
            return "Diputación"
        if it.get("municipios"):
            return it["municipios"][0]
        if "cuadrilla" in org:
            return it.get("organismo", "").title().replace(" De ", " de ").replace(" La ", " la ")
        if "junta administrativa" in org:
            return "Concejo de " + it.get("organismo", "").title().split(" De ", 1)[-1].replace(" De ", " de ").replace(" Del ", " del ")
    return ""


def titulo_claro(it: dict, fuente: dict) -> str:
    """Quita la jerga de los boletines: números de expediente, fechas y fórmulas."""
    t = " ".join(it["titulo"].split())
    if fuente.get("seccion") not in ("boletines",) and len(t) < 140:
        return t
    m = RX_CABECERA.match(t)
    tipo = ""
    if m and m.group(1):
        tipo = m.group(1).lower()
        t = t[m.end():]
    t = RX_FORMULA.sub("", t).strip(" .,-")
    t = re.sub(r"\s+del ayuntamiento de [\w\-áéíóúñ/ ]+$", "", t, flags=re.I)
    t = re.sub(r"\b(ordenanza(?: fiscal| municipal)?) reguladora\b", r"\1", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" .,-")
    if not t:
        return it["titulo"]
    if tipo.startswith("moci"):
        t = "moción para " + t[0].lower() + t[1:]
    else:
        t = _verbo(t[0].lower() + t[1:]) if not t[:3].isupper() else t
    quien = actor(it, fuente)
    if quien and not normaliza(t).startswith(normaliza(quien)):
        verbo = re.match(r"^(" + "|".join(INFINITIVOS.values()) + r")\b", t)
        t = f"{quien} {t}" if verbo else f"{quien}: {t}"
    t = t[0].upper() + t[1:]
    if len(t) < 30 and not quien:          # demasiado corto: mejor el original
        return it["titulo"]
    if len(t) > 150:
        t = t[:150].rsplit(" ", 1)[0] + "…"
    return t or it["titulo"]


# ---------------------------------------------------------------- buzón ciudadano
RX_HACE = re.compile(r"hace\s+(\d+)\s+(minuto|hora|d[ií]a)", re.I)
RX_FH = re.compile(r"(\d{2})/(\d{2})/(20\d\d)\s+(\d{2}):(\d{2})")


def lee_buzon_area(contenido: bytes, area: str, ahora: datetime) -> list[dict]:
    sopa = BeautifulSoup(contenido, "html.parser")
    out, vistos = [], set()
    for a in sopa.find_all("a", href=re.compile(r"verComentarios")):
        titulo = " ".join(a.get_text(" ").split())
        enlace = urljoin("https://www.vitoria-gasteiz.org/wb021/was/", a["href"])
        mid = re.search(r"claveAsuntoCom=(\d+)", a["href"])
        if not titulo or not mid or mid.group(1) in vistos:
            continue
        vistos.add(mid.group(1))
        fila = a
        for _ in range(6):                       # subir hasta el bloque que trae la fecha
            fila = fila.parent
            if fila is None or RX_FH.search(fila.get_text(" ")) or RX_HACE.search(fila.get_text(" ")):
                break
        texto = " ".join(fila.get_text(" ").split()) if fila else ""
        cuerpo = texto.replace(titulo, "", 1)
        cuerpo = re.split(r"hace\s+\d+|\d{2}/\d{2}/20\d\d", cuerpo)[0].strip(" :")
        if cuerpo.startswith("Buzón Ciudadano") or "Del 1 al 20 de un total" in cuerpo:
            cuerpo = ""                           # cabecera de la página, no la queja
        fecha = None
        m = RX_FH.search(texto)
        if m:
            d, mo, y, h, mi = map(int, m.groups())
            fecha = datetime(y, mo, d, h, mi, tzinfo=MADRID)
        else:
            m = RX_HACE.search(texto)
            if m:
                n, u = int(m.group(1)), m.group(2).lower()
                fecha = ahora - (timedelta(minutes=n) if u.startswith("min") else timedelta(hours=n) if u.startswith("hor") else timedelta(days=n))
        out.append({"titulo": titulo.strip("\u200b "), "enlace": enlace, "texto": recorta(cuerpo, 260), "texto_largo": "",
                    "fecha": fecha, "categorias": [area], "area": area})
    return out


RX_LUGAR = re.compile(r"\b(?:calle|c/|c\.|plaza|pza\.?|avenida|avda\.?|av\.|paseo|parque|portal de|camino|rotonda|"
                      r"barrio|bulevar|travesía|pasaje|kalea|plazuela)\s+((?:de\s+(?:la\s+|los\s+|las\s+)?)?[A-ZÁÉÍÓÚÑ0-9][\wáéíóúñü\-\.]*"
                      r"(?:\s+(?:de|del|la|las|los|y|[A-ZÁÉÍÓÚÑ0-9][\wáéíóúñü\-\.]*)){0,3})", re.I)
BARRIOS = ["zabalgana", "salburua", "lakua", "arriaga", "judimendi", "zaramaga", "sansomendi", "abetxuko", "arana",
           "adurtza", "ariznabarra", "aranbizkarra", "txagorritxu", "gazalbide", "el pilar", "coronacion", "desamparados",
           "casco viejo", "alde zaharra", "ensanche", "lovaina", "san martin", "mendizorrotza", "armentia", "betoño",
           "santa lucia", "santiago", "errekaleor", "jundiz", "ali", "gamarra", "ibaiondo", "aldaia", "mariturri",
           "borinbizkarra", "elejalde", "arkaiate", "larrein", "ibaialde", "goikolarra", "anglo vasco", "abendaño"]
RX_BARRIO = re.compile(r"\b(" + "|".join(re.escape(b) for b in BARRIOS) + r")\b")
VACIAS = set("de del la las los el en y a por para con sin que una uno un no se su al lo hay muy mas más ya".split())


def resumen_buzon(items: list[dict], ahora: datetime) -> list[dict]:
    """Por área: quejas de la última semana, tendencia y lugares o frases que se repiten."""
    from collections import Counter, defaultdict
    hace7, hace14 = ahora - timedelta(days=7), ahora - timedelta(days=14)
    por_area = defaultdict(list)
    for it in items:
        por_area[it.get("area") or it.get("resumen", "")].append(it)
    out = []
    for area, l in por_area.items():
        sem = [i for i in l if (de_iso(i["fecha"]) or de_iso(i["visto"])) >= hace7]
        ant = [i for i in l if hace14 <= (de_iso(i["fecha"]) or de_iso(i["visto"])) < hace7]
        lugares, frases = Counter(), Counter()
        for i in sem:
            t = i["titulo"]
            for m in RX_LUGAR.finditer(t):
                lugares[" ".join(m.group(0).split()).rstrip(".").title().replace(" De ", " de ").replace(" Del ", " del ")] += 1
            for m in RX_BARRIO.finditer(normaliza(t)):
                lugares[m.group(1).title()] += 1
            pal = [w for w in re.findall(r"[a-záéíóúñü]+", t.lower()) if w not in VACIAS and len(w) > 2]
            for k in range(len(pal) - 1):
                if pal[k] != pal[k + 1]:
                    frases[pal[k] + " " + pal[k + 1]] += 1
        rep_l = [(k, v) for k, v in lugares.most_common(4) if v >= 2]
        rep_f = [(k, v) for k, v in frases.most_common(3) if v >= 3]
        if not sem:
            continue
        sem.sort(key=lambda i: i["fecha"] or i["visto"], reverse=True)
        out.append({"area": area, "semana": len(sem), "anterior": len(ant),
                    "lugares": [{"t": k, "n": v} for k, v in rep_l], "frases": [{"t": k, "n": v} for k, v in rep_f],
                    "ejemplos": [{"t": i["titulo"], "e": i["enlace"], "f": i["fecha"] or i["visto"],
                                  "x": (i.get("resumen") or "")[:160]} for i in sem[:6]],
                    "url": None})
    out.sort(key=lambda x: (len(x["lugares"]) + len(x["frases"]), x["semana"]), reverse=True)
    return out



# Kulturklik (agenda cultural de Euskadi, API abierta del Gobierno Vasco)
RX_KK_COLA = re.compile(r"\s*[\(\[]\s*\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
                        r"octubre|noviembre|diciembre)[^)\]]*[\)\]]\s*$", re.I)
KK_DESTACAR = {5: "Presentación", 6: "Conferencia", 10: "Jornada"}   # lo que más le sirve a un periodista


def lee_kulturklik(contenido: bytes, fuente: dict, hoy: date) -> list[dict]:
    datos = json.loads(contenido)
    out, hasta_max = [], hoy + timedelta(days=fuente.get("dias", 60))
    for e in datos.get("items", []):
        try:
            f1 = date.fromisoformat(e["startDate"][:10])
            f2 = date.fromisoformat((e.get("endDate") or e["startDate"])[:10])
        except (KeyError, ValueError):
            continue
        if f2 < hoy or f1 > hasta_max or (f2 - f1).days > 120:   # fuera exposiciones permanentes
            continue
        nombre = html.unescape(e.get("nameEs") or e.get("nameEu") or "").strip()
        nombre = RX_KK_COLA.sub("", re.sub(r"^Entradas\s+", "", nombre)).strip() or nombre
        if not nombre:
            continue
        tipo_n = int(e.get("type") or 0)
        tipo_txt = e.get("typeEs") or ""
        if tipo_n in KK_DESTACAR and not normaliza(nombre).startswith(normaliza(KK_DESTACAR[tipo_n])[:6]):
            nombre = f"{KK_DESTACAR[tipo_n]}: {nombre}"
        lugar = e.get("establishmentEs") or e.get("placeEs") or ""
        muni = e.get("municipalityEs") or ""
        hora = None
        m = re.match(r"\s*(\d{1,2})[:.](\d{2})", e.get("openingHoursEs") or "")
        if m and f1 == f2:
            hora = f"{int(m.group(1)):02d}:{m.group(2)}"
        frase = " · ".join(x for x in (tipo_txt, lugar, muni if muni != "Vitoria-Gasteiz" else "", e.get("priceEs") or "") if x)
        enlace = e.get("sourceUrlEs") or e.get("purchaseUrlEs") or e.get("urlEventEs") or "https://www.kulturklik.euskadi.eus/"
        desc = html_a_texto(e.get("descriptionEs") or "")
        # en Vitoria la agenda municipal ya trae muchos actos; aquí, en lugar visible solo lo que sale de lo habitual
        out.append({"titulo": nombre, "enlace": enlace, "texto": frase + (". " + desc if desc else ""),
                    "texto_largo": "", "fecha": datetime.combine(f1, datetime.min.time(), MADRID),
                    "categorias": [tipo_txt], "municipio_kk": muni, "clave": f"kk{e.get('id')}",
                    "cal_ev": {"fecha": f1.isoformat(), "hasta": f2.isoformat() if f2 != f1 else None, "hora": hora,
                               "tipo": "evento" if tipo_n in KK_DESTACAR else "agenda", "frase": frase[:200]}})
    return out


# Correo de la redacción (Gmail propio): notas de prensa y alertas del CENDOJ que llegan por mail.
# Se lee por IMAP con una contraseña de aplicación guardada como secreto en GitHub (GMAIL_USER, GMAIL_APP_PASSWORD).
# Solo se miran los remitentes de la lista blanca de cada fuente; el resto del buzón no se toca.
_CORREOS = None


def _dominio(remitente: str) -> str:
    m = re.search(r"@([\w.-]+)", remitente or "")
    return m.group(1).lower() if m else ""


RX_REENVIO = re.compile(r"^\s*(rv|fw|fwd|reenv|i)\s*:", re.I)
RX_DE_ORIGINAL = re.compile(r"(?:^|\n|>)\s*(?:\*\s*)?(?:de|from|nork)\s*:\s*\**[^\n<]*<?\s*([\w.+-]+@[\w.-]+)", re.I)


def dominios_de(c: dict) -> list[str]:
    """Dominio del remitente y, si es un reenvío, también el del remitente original que aparece en el cuerpo."""
    doms = [_dominio(c["de"])]
    if RX_REENVIO.match(c["asunto"]) or "forwarded message" in (c["texto"] or "").lower() or "mensaje reenviado" in (c["texto"] or "").lower():
        cuerpo = c["texto"] or BeautifulSoup(c["html"] or "", "html.parser").get_text("\n")
        doms += [m.lower().split("@")[1] for m in RX_DE_ORIGINAL.findall(cuerpo)[:3]]
    return doms


def correos_recientes(dias: int = 4) -> list[dict]:
    """Descarga una vez por ejecución los correos de los últimos días (solo lectura, no marca nada como leído)."""
    global _CORREOS
    if _CORREOS is not None:
        return _CORREOS
    import email, imaplib
    from email.header import decode_header, make_header
    from email.utils import parsedate_to_datetime
    usuario, clave = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    _CORREOS = []
    if not (usuario and clave):
        return _CORREOS
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    imap.login(usuario, clave.replace(" ", ""))
    imap.select("INBOX", readonly=True)
    desde = (datetime.now(MADRID) - timedelta(days=dias)).strftime("%d-%b-%Y")
    _, datos = imap.search(None, "SINCE", desde)
    for num in (datos[0].split() if datos and datos[0] else [])[-300:]:
        _, partes = imap.fetch(num, "(BODY.PEEK[])")
        msg = email.message_from_bytes(partes[0][1])
        texto, html_ = "", ""
        for parte in msg.walk():
            if parte.get_content_maintype() == "multipart" or parte.get_filename():
                continue
            carga = parte.get_payload(decode=True) or b""
            cs = parte.get_content_charset() or "utf-8"
            if parte.get_content_type() == "text/plain" and not texto:
                texto = carga.decode(cs, "replace")
            elif parte.get_content_type() == "text/html" and not html_:
                html_ = carga.decode(cs, "replace")
        try:
            fecha = parsedate_to_datetime(msg.get("Date")).astimezone(MADRID)
        except Exception:
            fecha = datetime.now(MADRID)
        _CORREOS.append({"de": str(make_header(decode_header(msg.get("From", "")))),
                         "asunto": " ".join(str(make_header(decode_header(msg.get("Subject", "")))).split()),
                         "id": msg.get("Message-ID", "") or f"n{num.decode()}",
                         "fecha": fecha.isoformat(), "texto": texto, "html": html_})
    imap.logout()
    return _CORREOS


RX_ENLACE_CUENTA = re.compile(r"activat|activar|password|contrase|login|registro|verif|unsubscribe|token", re.I)
RX_ASUNTO_RUIDO = re.compile(r"^\s*((re|rv|fw|fwd|reenv)\s*:\s*)+|\s*\[(nota de prensa|prentsa oharra)\]\s*", re.I)


ROJ_TIPO = {"S": "Sentencia", "A": "Auto"}
ROJ_ORGANO = [("TSJ PV", "del TSJ del País Vasco"), ("AP VI", "de la Audiencia Provincial de Álava"),
              ("JP VI", "del Juzgado de lo Penal de Vitoria"), ("JSO VI", "del Juzgado de lo Social de Vitoria"),
              ("JCA VI", "del Juzgado de lo Contencioso de Vitoria"), ("JM VI", "del Juzgado de lo Mercantil de Vitoria"),
              ("JPI VI", "de un Juzgado de Primera Instancia de Vitoria"), ("JI VI", "de un Juzgado de Instrucción de Vitoria"),
              ("JVM VI", "del Juzgado de Violencia sobre la Mujer de Vitoria"), ("JMN VI", "del Juzgado de Menores de Vitoria"),
              ("JVP VI", "del Juzgado de Vigilancia Penitenciaria de Vitoria"), ("TS", "del Tribunal Supremo"), ("AN", "de la Audiencia Nacional")]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def titulo_roj(texto: str, enlace: str) -> str:
    """'ROJ: SAP VI 1506/2026 - ECLI…' -> 'Sentencia de la Audiencia Provincial de Álava 1506/2026 (publicada el 4 de noviembre)'."""
    m = re.search(r"ROJ:\s*([SA])([A-Z]+(?:\s[A-Z]{2})?)\s+(\d+/\d{4})", texto)
    if not m:
        return texto
    tipo, codigo, num = ROJ_TIPO.get(m.group(1), "Resolución"), m.group(2).strip(), m.group(3)
    organo = next((o for c, o in ROJ_ORGANO if codigo == c.replace(" ", " ")), f"({codigo})")
    f = re.search(r"/(20\d\d)(\d\d)(\d\d)(?:$|[/?])", enlace)
    fecha = f" (publicada el {int(f.group(3))} de {MESES_ES[int(f.group(2)) - 1]})" if f else ""
    return f"{tipo} {organo} {num}{fecha}"


def lee_correo(contenido: bytes, fuente: dict) -> list[dict]:
    out = []
    for c in json.loads(contenido):
        cuerpo_html = BeautifulSoup(c["html"], "html.parser") if c["html"] else None
        cuerpo = " ".join((c["texto"] or (cuerpo_html.get_text(" ") if cuerpo_html else "")).split())
        enlaces = [(a.get_text(" ", strip=True), a["href"]) for a in (cuerpo_html.find_all("a", href=True) if cuerpo_html else [])
                   if a["href"].startswith("http")] or [("", u) for u in re.findall(r"https?://[^\s<>\"]+", c["texto"] or "")]
        fecha = datetime.fromisoformat(c["fecha"])
        respaldo = "https://mail.google.com/mail/u/0/#search/" + requests.utils.quote(f'subject:"{c["asunto"][:60]}"')
        if fuente.get("modo") == "alertas":
            # alertas del CENDOJ: una entrada por resolución enlazada
            vistos = set()
            anclas = cuerpo_html.find_all("a", href=True) if cuerpo_html else []
            for a in anclas:
                href, txt = a["href"], a.get_text(" ", strip=True)
                if "poderjudicial.es" not in href or "openDocument" not in href or href in vistos:
                    continue
                vistos.add(href)
                # lo que acompaña al enlace en la alerta (órgano, sección, materia…), si lo hay
                bloque = a.find_parent(["tr", "li", "p"]) or a.parent
                contexto = " ".join(bloque.get_text(" ").split()).replace(txt, "").strip(" -·|") if bloque else ""
                contexto = re.sub(r"ECLI:\S+", "", contexto).strip(" -·|")
                out.append({"titulo": titulo_roj(txt, href) if txt else c["asunto"], "enlace": href,
                            "texto": (re.sub(r"\s*-\s*ECLI:\S+", "", txt) + (". " + contexto if contexto else ""))[:500], "texto_largo": "",
                            "fecha": fecha, "categorias": ["CENDOJ"]})
            continue                                  # sin resoluciones (avisos de cuenta, etc.): no se publica
        titulo = RX_ASUNTO_RUIDO.sub("", c["asunto"]).strip() or c["asunto"]
        propio = next((h for t, h in enlaces if _dominio("@" + re.sub(r"^https?://(www\.)?", "", h).split("/")[0])
                       in fuente.get("remitentes", []) and not re.search(r"unsubscribe|baja|logo|facebook|twitter|instagram", h, re.I)
                       and not RX_ENLACE_CUENTA.search(h)), None)
        out.append({"titulo": titulo, "enlace": propio or respaldo, "texto": cuerpo[:700], "texto_largo": cuerpo[:3000],
                    "fecha": fecha, "categorias": ["correo"], "clave": "mail" + c["id"]})
    return out

LECTORES = {"liferay": lee_liferay, "rss": lee_rss, "html": lee_html, "diputacion": lee_diputacion, "botha": lee_botha, "boe": lee_boe,
            "kulturklik": lee_kulturklik, "correo": lambda c, f, h: lee_correo(c, f)}


# ---------------------------------------------------------------- clasificación
class Clasificador:
    def __init__(self, temas_cfg: dict):
        self.temas = [(t["nombre"], patron(t.get("palabras", [])), t.get("pistas", []))
                      for t in temas_cfg.get("temas", [])]
        self.preguntas = {t["nombre"]: t.get("preguntas", []) for t in temas_cfg.get("temas", [])}
        self.rx_fondo = patron(temas_cfg.get("fondo", []))
        self.rx_excluir = patron(temas_cfg.get("excluir", []))

    def municipios(self, texto_n: str) -> list[str]:
        return [n for n, _, rx in RX_MUNI if rx.search(texto_n)]

    def clasifica(self, it: dict, fuente: dict) -> None:
        tit_n = normaliza(it["titulo"])
        texto = normaliza(f"{it['titulo']} {it['titulo']} {it.get('texto', '')[:1500]}")
        inicio = normaliza(f"{it['titulo']} {it.get('texto', '')[:400]}")
        org_n = normaliza(it.get("organismo", ""))

        # municipios: primero el organismo (BOTHA), luego la fuente, luego el texto
        munis = self.municipios(org_n) if org_n else []
        if not munis and it.get("municipio_kk"):
            munis = self.municipios(normaliza(it["municipio_kk"]))[:1]
        if not munis and fuente.get("municipio"):
            munis = [fuente["municipio"]]
        if not munis:
            munis = [m for m in self.municipios(inicio) if m != "Vitoria-Gasteiz"] or self.municipios(inicio)[:1]
        it["municipios"] = munis[:3]
        it["cuadrilla"] = MUNICIPIOS[munis[0]][0] if munis else fuente.get("cuadrilla")
        it["alava"] = bool(fuente.get("local")) or bool(munis) or bool(coincidencias(RX_ALAVA_GENERAL, inicio))

        temas = []
        for nombre, rx, _ in self.temas:
            hits = coincidencias(rx, texto)
            if hits:
                temas.append((len(hits) + sum(1 for h in hits if h in tit_n), nombre))
        temas.sort(reverse=True)
        it["temas"] = [n for _, n in temas[:3]]

        # relevancia 0-10 (para ordenar y para la portada)
        base = {"alta": 4, "media": 3, "baja": 1}.get(fuente.get("prioridad", "media"), 3)
        rel = base + min(len(coincidencias(RX_NOTICIA, tit_n)), 3)
        rutina = bool(coincidencias(RX_RUTINA, tit_n))
        if rutina:
            rel -= 4
        if not fuente.get("local") and it["alava"]:
            rel += 1
        if fuente["seccion"] in ("instituciones", "pueblos", "boletines", "asociaciones") and not it["alava"]:
            rel -= 3
        it["relevancia"] = max(0, min(10, rel))
        it["rutina"] = rutina

        if fuente["seccion"] == "ideas":
            fondo = coincidencias(self.rx_fondo, texto)
            excl = coincidencias(self.rx_excluir, normaliza(it["titulo"] + " " + it.get("texto", "")[:400]))
            p = min(sum(x for x, _ in temas[:2]), 6) + min(len(fondo), 3) * 1.5 - len(excl) * 4
            if it["alava"]:
                p -= 3
            it["puntos"] = round(p, 1)
            it["senales"] = [BONITO.get(s, s) for s in sorted(fondo)][:4]

    def pistas(self) -> dict:
        return {n: {"pistas": p, "preguntas": self.preguntas.get(n, [])} for n, _, p in self.temas}


def es_suceso(it: dict, fuente: dict) -> bool:
    """Partes policiales, emergencias y tribunales de Álava (para la pestaña Sucesos)."""
    if fuente.get("seccion") == "sucesos":
        return True
    if fuente.get("seccion") not in ("instituciones", "pueblos", "teletipos") or not it.get("alava") or fuente.get("tipo") == "botha":
        return False
    t = normaliza(it.get("titulo", ""))
    if "tribunal calificador" in t:
        return False
    return bool(coincidencias(RX_SUCESO, t) or (fuente["seccion"] != "pueblos" and coincidencias(RX_JUDICIAL, t)))


def tipo_item(it: dict, fuente: dict) -> str:
    if fuente.get("fecha_es_evento"):
        return "agenda"
    cats = " ".join(it.get("categorias", [])).lower()
    if "convocatoria" in cats or it["titulo"].lower().startswith(("convocatorias de prensa", "previsiones de")):
        return "convocatoria"
    return "noticia"


# ---------------------------------------------------------------- histórico
def carga_json(ruta: Path, defecto):
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"AVISO: {ruta.name} dañado, se empieza de cero", file=sys.stderr)
    return defecto


def guarda_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(ruta)


# ---------------------------------------------------------------- principal
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path)
    ap.add_argument("--ahora")
    args = ap.parse_args()

    cfg = yaml.safe_load((RAIZ / "fuentes.yaml").read_text(encoding="utf-8"))
    temas_cfg = yaml.safe_load((RAIZ / "temas.yaml").read_text(encoding="utf-8"))
    efem_cfg = yaml.safe_load((RAIZ / "efemerides.yaml").read_text(encoding="utf-8")) if (RAIZ / "efemerides.yaml").exists() else {}
    clasif = Clasificador(temas_cfg)
    ahora = de_iso(args.ahora) if args.ahora else ahora_utc()
    hoy = ahora.astimezone(MADRID).date()

    hist = carga_json(HISTORICO, {"items": {}, "calendario": {}})
    items_hist: dict = hist.get("items", {})
    cal_hist: dict = hist.get("calendario", {})
    estado = []
    lecturas: dict = hist.get("lecturas", {})                # última lectura de cada fuente (para las que van más despacio)
    estado_previo = {f["id"]: f for f in carga_json(SALIDA, {}).get("fuentes", [])}

    def grupo_de(f):
        return {k: f[k] for k in ("grupo", "etiqueta", "extra") if f.get(k)}

    for fuente in cfg.get("fuentes", []):
        if fuente.get("activa", True) is False:
            continue
        fuente.setdefault("seccion", "instituciones")
        # algunas fuentes no hace falta leerlas cada hora (agenda, ideas, buzón…): campo "cada" en horas
        ultima = de_iso(lecturas.get(fuente["id"]))
        if (fuente.get("cada") and ultima and not args.fixtures and fuente["id"] in estado_previo
                and ahora - ultima < timedelta(hours=fuente["cada"]) - timedelta(minutes=10)):
            estado.append({**estado_previo[fuente["id"]], "nuevos": 0})
            continue
        lecturas[fuente["id"]] = iso(ahora)
        inicio = time.time()
        url = fuente["url"].replace("{HOY}", hoy.strftime("%Y%m%d"))
        if fuente.get("tipo") == "buzon":
            nuevos_b, fallos_b = [], 0
            for clave_area, nombre_area in (fuente.get("areas") or {}).items():
                u = url.replace("{AREA}", str(clave_area))
                try:
                    nuevos_b += lee_buzon_area(descarga(u, args.fixtures, f"buzon-{clave_area}"), nombre_area, ahora)
                except Exception as e:
                    fallos_b += 1
                    print(f"  buzón área {clave_area}: {type(e).__name__}", file=sys.stderr)
                time.sleep(0.5 if not args.fixtures else 0)
            n_n = 0
            for it in nuevos_b:
                clave = ident("buzon", it["enlace"])
                previo = items_hist.get(clave)
                items_hist[clave] = {"id": clave, "fuente": "buzon", "seccion": "buzon", "tipo": "queja",
                                     "titulo": it["titulo"], "enlace": it["enlace"], "resumen": it["texto"],
                                     "area": it["area"], "fecha": iso(it["fecha"]),
                                     "visto": previo["visto"] if previo else iso(ahora), "alava": True,
                                     "municipios": ["Vitoria-Gasteiz"], "cuadrilla": "Vitoria-Gasteiz",
                                     "temas": [], "relevancia": 0, "rutina": False, "cal": True}
                n_n += 0 if previo else 1
            ok_b = fallos_b < len(fuente.get("areas") or {}) or not fuente.get("areas")
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], **grupo_de(fuente), "url": url.replace("{AREA}", "18"),
                           "seccion": fuente["seccion"], "local": True, "ok": ok_b, "leidos": len(nuevos_b),
                           "nuevos": n_n, **({} if ok_b else {"error": "no se pudo leer ninguna área"})})
            print(f"{'OK  ' if ok_b else 'FALLO'} buzon {len(nuevos_b):>3} quejas leídas, {n_n} nuevas, {fallos_b} áreas con fallo")
            continue
        if fuente.get("tipo") == "correo":
            if not os.environ.get("GMAIL_USER") and not args.fixtures:
                continue                              # buzón aún sin configurar: no se muestra
        try:
            if fuente.get("tipo") == "correo":
                if args.fixtures:
                    crudo = descarga(url, args.fixtures, fuente["id"])
                else:
                    doms = tuple(fuente.get("remitentes", []))
                    crudo = json.dumps([c for c in correos_recientes()
                                        if doms and any(d.endswith(doms) for d in dominios_de(c))]).encode()
            elif "{PAGINA}" in url:                     # APIs paginadas (Kulturklik): se juntan las páginas
                todos = []
                for pag in range(1, fuente.get("paginas", 5) + 1):
                    trozo = json.loads(descarga(url.replace("{PAGINA}", str(pag)), args.fixtures,
                                                fuente["id"] + ("" if pag == 1 else f"-{pag}"), fuente.get("accept")))
                    todos += trozo.get("items", [])
                    if pag >= (trozo.get("totalPages") or 1) or args.fixtures:
                        break
                    time.sleep(0.5)
                crudo = json.dumps({"items": todos}).encode()
                url = url.replace("{PAGINA}", "1")
            else:
                try:
                    crudo = descarga(url, args.fixtures, fuente["id"], fuente.get("accept"))
                except Exception as e_d:
                    if fuente.get("tipo") == "boe" and "404" in str(e_d):
                        crudo = b'{"data": {}}'               # aún no hay BOE de hoy (sale de madrugada / no sale en festivo)
                    elif not fuente.get("alternativa"):
                        raise
                    else:
                        url = fuente["alternativa"]
                        crudo = descarga(url, args.fixtures, fuente["id"], fuente.get("accept"))
            nuevos = LECTORES[fuente.get("tipo", "rss")](crudo, fuente, hoy)
            n_nuevos = 0
            for it in nuevos:
                clasif.clasifica(it, fuente)
                tipo = tipo_item(it, fuente)
                clave = (ident(fuente["id"], it["clave"]) if it.get("clave")
                         else ident(fuente["id"], normaliza(it["titulo"])) if fuente.get("clave_por_titulo")
                         else ident(fuente["id"], it["enlace"], it["titulo"] if fuente.get("tipo") == "botha" else ""))
                previo = items_hist.get(clave)
                reg = {
                    "id": clave, "fuente": fuente["id"], "seccion": fuente["seccion"], "tipo": tipo,
                    "titulo": it["titulo"], "titulo_claro": titulo_claro(it, fuente), "enlace": it["enlace"],
                    "resumen": recorta(it["texto"], 1800 if tipo == "convocatoria" else MAX_RESUMEN),
                    "fecha": iso(it["fecha"]), "visto": previo["visto"] if previo else iso(ahora),
                    "alava": it["alava"], "temas": it["temas"], "municipios": it["municipios"],
                    "cuadrilla": it["cuadrilla"], "relevancia": it["relevancia"], "rutina": it["rutina"],
                    "cal": bool(previo and previo.get("cal")),
                }
                for extra in ("organismo", "boletin", "bloque"):
                    if it.get(extra):
                        reg[extra] = it[extra]
                if "puntos" in it:
                    reg["puntos"], reg["senales"] = it["puntos"], it["senales"]
                if not previo:
                    n_nuevos += 1
                items_hist[clave] = reg

                # ---- calendario a partir de este elemento
                if not (previo and previo.get("cal")) or fuente.get("fecha_es_evento") or tipo == "convocatoria":
                    reg["cal"] = True
                    base_f = (de_iso(reg["fecha"]) or ahora).astimezone(MADRID).date()
                    evs = []
                    if it.get("cal_ev"):
                        ce = it["cal_ev"]
                        evs = [{"id": ident(clave, ce["fecha"]), "fecha": ce["fecha"], "hasta": ce["hasta"],
                                "hora": ce["hora"], "tipo": ce["tipo"], "titulo": it["titulo"], "frase": ce["frase"],
                                "enlace": reg["enlace"], "fuente": fuente["id"], "origen": clave, "seguimiento": False}]
                    elif tipo == "agenda":
                        evs = calendario.de_agenda(reg, hoy)
                    elif tipo == "convocatoria":
                        evs = calendario.convocatorias(reg, html_a_texto(it.get("texto_largo", "")) or reg["resumen"], base_f)
                    elif it.get("evento"):
                        evs = [{"id": ident(clave, it["evento"]), "fecha": it["evento"], "hasta": None, "hora": None,
                                "tipo": "evento", "titulo": it["titulo"], "frase": reg["resumen"][:200],
                                "enlace": reg["enlace"], "fuente": fuente["id"], "origen": clave, "seguimiento": False}]
                    elif fuente["seccion"] != "ideas" and fuente.get("calendario", True):
                        texto_cal = it["titulo"] + ". " + (it.get("texto_largo") or it.get("texto", ""))
                        if fuente["seccion"] == "boletines":
                            texto_cal = it["titulo"]
                        if it["alava"]:
                            evs = calendario.extrae(reg, texto_cal[:6000], base_f)
                    for ev in evs:
                        ev["categoria"] = fuente.get("categoria_cal") or {
                            "instituciones": "institucional", "boletines": "institucional", "pueblos": "pueblos",
                            "asociaciones": "asociaciones", "agenda": "institucional", "medios": "medios",
                            "teletipos": "medios", "sucesos": "institucional"}.get(fuente["seccion"], "otros")
                        ev["alava"] = reg["alava"]
                        ev["municipios"] = reg["municipios"]
                        cal_hist[ev["id"]] = ev
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], **grupo_de(fuente), "url": url, "seccion": fuente["seccion"],
                           "local": bool(fuente.get("local")), "ok": True, "leidos": len(nuevos), "nuevos": n_nuevos,
                           "segundos": round(time.time() - inicio, 1)})
            print(f"OK   {fuente['id']:<26} {len(nuevos):>3} leídos, {n_nuevos:>3} nuevos")
        except Exception as e:
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], **grupo_de(fuente), "url": url, "seccion": fuente["seccion"],
                           "local": bool(fuente.get("local")), "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})
            print(f"FALLO {fuente['id']:<25} {type(e).__name__}: {e}", file=sys.stderr)

    # duplicados del Ayuntamiento (misma nota en dos feeds)
    por_enlace: dict = {}
    for clave, it in sorted(items_hist.items(), key=lambda kv: kv[1]["seccion"] != "agenda"):
        if it["fuente"].startswith("ayto-") and it["fuente"] != "ayto-movilidad":
            if it["enlace"] in por_enlace and por_enlace[it["enlace"]] != clave:
                it["duplicado"] = True
            else:
                por_enlace[it["enlace"]] = clave
    items_hist = {k: v for k, v in items_hist.items() if not v.get("duplicado")}

    # poda
    limite = ahora - timedelta(days=DIAS_HISTORICO)
    def vigente(it):
        if it["tipo"] == "agenda":
            f = de_iso(it["fecha"])
            return bool(f and f >= ahora - timedelta(days=2))
        return de_iso(it["visto"]) >= limite
    items_hist = {k: v for k, v in items_hist.items() if vigente(v)}
    cal_hist = {k: v for k, v in cal_hist.items()
                if date.fromisoformat(v.get("hasta") or v["fecha"]) >= hoy - timedelta(days=45)
                and not (v.get("fuente") == "kulturklik" and v.get("hasta")
                         and (date.fromisoformat(v["hasta"]) - date.fromisoformat(v["fecha"])).days > 120)}

    limite_ideas = ahora - timedelta(days=DIAS_IDEAS)
    quejas = [i for i in items_hist.values() if i["seccion"] == "buzon"
              and (de_iso(i["fecha"]) or de_iso(i["visto"])) >= ahora - timedelta(days=14)]
    buzon = resumen_buzon(quejas, ahora)
    publicados, ideas_pub = [], []
    solo_cal = {f["id"] for f in cfg.get("fuentes", []) if f.get("solo_calendario")}
    cfg_f = {f["id"]: f for f in cfg.get("fuentes", [])}
    for it in items_hist.values():
        it.pop("suceso", None)
        if es_suceso(it, cfg_f.get(it["fuente"], {})):
            it["suceso"] = True
    for it in items_hist.values():
        if it["seccion"] == "buzon" or it["fuente"] in solo_cal:
            continue
        if it["fuente"].startswith("correo") and RX_ENLACE_CUENTA.search(it.get("enlace") or ""):
            continue                                  # enlaces de activación o de contraseña: nunca a la página
        if it["seccion"] == "teletipos":
            if (de_iso(it["fecha"]) or de_iso(it["visto"])) < ahora - timedelta(days=3):
                continue
            # de los teletipos nacionales, solo lo que toca a Álava o a Euskadi
            if cfg_f.get(it["fuente"], {}).get("filtro") == "euskadi" and not it.get("alava") \
                    and not coincidencias(RX_EUSKADI, normaliza(it["titulo"] + " " + (it.get("resumen") or "")[:300])):
                continue
        if it["seccion"] == "ideas":
            ref = de_iso(it["fecha"]) or de_iso(it["visto"])
            if ref < limite_ideas or (not it["alava"] and it.get("puntos", 0) < UMBRAL_IDEA):
                continue
            if not it["alava"]:
                ideas_pub.append(it)
                continue
        publicados.append(it)

    ideas_pub.sort(key=lambda i: -(i.get("puntos") or 0))
    por_medio, ideas_sel = {}, []
    for i in ideas_pub:                               # variedad: como mucho 4 temas por medio
        por_medio[i["fuente"]] = por_medio.get(i["fuente"], 0) + 1
        if por_medio[i["fuente"]] <= 4:
            ideas_sel.append(i)
    publicados += ideas_sel[:80]                      # solo las 80 mejores ideas

    # fuera duplicados (mismo enlace o mismo título) y actos de agenda ya pasados
    def _norm(t):
        return re.sub(r"[^a-z0-9]+", "", normaliza(t or "").lower())[:70]
    publicados.sort(key=lambda i: (i.get("visto") or ""), reverse=True)
    # una nota que llega por correo y también está en la web se queda solo con la de la web
    tit_web = {_norm(i.get("titulo"))[:45] for i in publicados if cfg_f.get(i["fuente"], {}).get("tipo") != "correo"}
    publicados = [i for i in publicados if cfg_f.get(i["fuente"], {}).get("tipo") != "correo"
                  or _norm(i.get("titulo"))[:45] not in tit_web]
    vistos_pub, limpios = set(), []
    for it in publicados:
        ev = it.get("evento")
        if ev and date.fromisoformat(ev[:10]) < hoy - timedelta(days=14):
            continue
        if it["seccion"] == "medios":                 # sección retirada: restos del histórico
            continue
        claves = {("e", it.get("enlace") or it["id"]),
                  ("t", it.get("fuente"), it.get("organismo") or "", " ".join(it.get("municipios") or []),
                   _norm(it.get("titulo"))[:50])}
        if claves & vistos_pub:
            continue
        vistos_pub |= claves
        limpios.append(it)
    publicados = limpios

    # calendario publicado: efemérides (este mes y los 3 siguientes) + lo extraído
    desde = hoy.replace(day=1) - timedelta(days=31)
    hasta = (hoy.replace(day=1) + timedelta(days=130))
    cal = list(cal_hist.values()) + calendario.efemerides(efem_cfg or {}, desde, hasta)
    cal.sort(key=lambda e: (e["fecha"], e.get("hora") or "99"))

    guarda_json(HISTORICO, {"actualizado": iso(ahora), "items": items_hist, "calendario": cal_hist, "lecturas": lecturas})
    guarda_json(SALIDA, {
        "actualizado": iso(ahora),
        "fuentes": estado,
        "manuales": cfg.get("enlaces_manuales", []),
        "pistas": clasif.pistas(),
        "cuadrillas": sorted({c for c, _ in MUNICIPIOS.values()}),
        "municipios": {n: c for n, (c, _) in MUNICIPIOS.items()},
        "tipos_calendario": calendario.ETIQUETAS,
        "items": sorted(publicados, key=lambda i: i["fecha"] or i["visto"], reverse=True),
        "buzon": buzon,
        "calendario": cal,
    })
    fallos = sum(1 for s in estado if not s["ok"])
    print(f"\n{len(publicados)} elementos · {len(cal)} fechas en calendario · {len(estado) - fallos} fuentes OK · {fallos} con fallo")
    return 1 if estado and fallos == len(estado) else 0


if __name__ == "__main__":
    sys.exit(main())
