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

# Relevancia: lo que suele ser noticia y lo que es trámite
RX_NOTICIA = patron(["presupuesto", "subvencion", "ayudas", "ordenanza", "impuesto", "tasa", "plan ", "licitac",
                     "adjudica", "obras", "inversion", "millones", "convocatoria", "oferta publica de empleo",
                     "huelga", "cierre", "cierra", "apertura", "abre", "inaugur", "nuevo", "nueva",
                     "por primera vez", "aprobacion definitiva", "aprobacion inicial", "mocion", "denuncia",
                     "protesta", "reclama", "vecinos", "vecinal", "sequia", "incendio", "vivienda",
                     "residencia", "colegio", "centro de salud", "estudio", "informe", "encuesta",
                     "premio", "record", "acuerdo", "convenio", "proyecto", "reforma", "rehabilitacion",
                     "fiestas", "festival", "jornadas", "presenta", "denuncia", "alerta"])
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
        it["texto"] = " ".join(b.replace(it["titulo"], " ").split()).strip(" ·|-")
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


LECTORES = {"liferay": lee_liferay, "rss": lee_rss, "html": lee_html, "diputacion": lee_diputacion, "botha": lee_botha, "boe": lee_boe}


# ---------------------------------------------------------------- clasificación
class Clasificador:
    def __init__(self, temas_cfg: dict):
        self.temas = [(t["nombre"], patron(t.get("palabras", [])), t.get("pistas", []))
                      for t in temas_cfg.get("temas", [])]
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
        return {n: p for n, _, p in self.temas}


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

    for fuente in cfg.get("fuentes", []):
        if fuente.get("activa", True) is False:
            continue
        fuente.setdefault("seccion", "instituciones")
        inicio = time.time()
        url = fuente["url"].replace("{HOY}", hoy.strftime("%Y%m%d"))
        try:
            try:
                crudo = descarga(url, args.fixtures, fuente["id"], fuente.get("accept"))
            except Exception:
                if not fuente.get("alternativa"):
                    raise
                url = fuente["alternativa"]
                crudo = descarga(url, args.fixtures, fuente["id"], fuente.get("accept"))
            nuevos = LECTORES[fuente.get("tipo", "rss")](crudo, fuente, hoy)
            n_nuevos = 0
            for it in nuevos:
                clasif.clasifica(it, fuente)
                tipo = tipo_item(it, fuente)
                clave = (ident(fuente["id"], normaliza(it["titulo"])) if fuente.get("clave_por_titulo")
                         else ident(fuente["id"], it["enlace"], it["titulo"] if fuente.get("tipo") == "botha" else ""))
                previo = items_hist.get(clave)
                reg = {
                    "id": clave, "fuente": fuente["id"], "seccion": fuente["seccion"], "tipo": tipo,
                    "titulo": it["titulo"], "enlace": it["enlace"],
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
                    if tipo == "agenda":
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
                            "asociaciones": "asociaciones", "agenda": "institucional", "medios": "medios"}.get(fuente["seccion"], "otros")
                        ev["alava"] = reg["alava"]
                        ev["municipios"] = reg["municipios"]
                        cal_hist[ev["id"]] = ev
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], "url": url, "seccion": fuente["seccion"],
                           "local": bool(fuente.get("local")), "ok": True, "leidos": len(nuevos), "nuevos": n_nuevos,
                           "segundos": round(time.time() - inicio, 1)})
            print(f"OK   {fuente['id']:<26} {len(nuevos):>3} leídos, {n_nuevos:>3} nuevos")
        except Exception as e:
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], "url": url, "seccion": fuente["seccion"],
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
                if date.fromisoformat(v.get("hasta") or v["fecha"]) >= hoy - timedelta(days=45)}

    limite_ideas = ahora - timedelta(days=DIAS_IDEAS)
    publicados = []
    for it in items_hist.values():
        if it["seccion"] == "ideas":
            ref = de_iso(it["fecha"]) or de_iso(it["visto"])
            if ref < limite_ideas or (not it["alava"] and it.get("puntos", 0) < UMBRAL_IDEA):
                continue
        publicados.append(it)

    # calendario publicado: efemérides (este mes y los 3 siguientes) + lo extraído
    desde = hoy.replace(day=1) - timedelta(days=31)
    hasta = (hoy.replace(day=1) + timedelta(days=130))
    cal = list(cal_hist.values()) + calendario.efemerides(efem_cfg or {}, desde, hasta)
    cal.sort(key=lambda e: (e["fecha"], e.get("hora") or "99"))

    guarda_json(HISTORICO, {"actualizado": iso(ahora), "items": items_hist, "calendario": cal_hist})
    guarda_json(SALIDA, {
        "actualizado": iso(ahora),
        "fuentes": estado,
        "manuales": cfg.get("enlaces_manuales", []),
        "pistas": clasif.pistas(),
        "cuadrillas": sorted({c for c, _ in MUNICIPIOS.values()}),
        "municipios": {n: c for n, (c, _) in MUNICIPIOS.items()},
        "tipos_calendario": calendario.ETIQUETAS,
        "items": sorted(publicados, key=lambda i: i["fecha"] or i["visto"], reverse=True),
        "calendario": cal,
    })
    fallos = sum(1 for s in estado if not s["ok"])
    print(f"\n{len(publicados)} elementos · {len(cal)} fechas en calendario · {len(estado) - fallos} fuentes OK · {fallos} con fallo")
    return 1 if estado and fallos == len(estado) else 0


if __name__ == "__main__":
    sys.exit(main())
