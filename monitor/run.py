#!/usr/bin/env python3
"""
Monitor de fuentes · Hoy por Hoy Vitoria

Lee las fuentes de fuentes.yaml, clasifica lo que encuentra con temas.yaml,
lo junta con el histórico (data/historico.json) y genera docs/datos.json,
que es lo que lee la página web (docs/index.html).

Uso:
    python monitor/run.py                 # lectura normal (internet)
    python monitor/run.py --fixtures DIR  # pruebas con feeds guardados en DIR
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HISTORICO = RAIZ / "data" / "historico.json"
SALIDA = RAIZ / "docs" / "datos.json"

DIAS_HISTORICO = 21          # cuánto tiempo se guarda cada noticia
DIAS_IDEAS = 7               # antigüedad máxima de las ideas de temas
MAX_RESUMEN = 420            # caracteres del resumen
UMBRAL_IDEA = 2.0            # puntuación mínima para que algo sea "idea"
USER_AGENT = "MonitorHoyPorHoyVitoria/1.0 (lector RSS para uso periodistico)"
MADRID = ZoneInfo("Europe/Madrid")
# Cómo se muestran algunas señales "de fondo" (en temas.yaml van sin tildes)
BONITO = {"cada vez mas": "cada vez más", "estadistica": "estadística", "radiografia": "radiografía",
          "deficit": "déficit", "record": "récord", "en los ultimos anos": "en los últimos años",
          "por primera vez": "por primera vez", "%": "porcentajes"}

# Municipios, comarcas y referencias de Álava (sin tildes, en minúscula)
ALAVA = [
    "alava", "araba", "vitoria", "gasteiz", "alaves", "alavesa", "alaveses", "alavesas",
    "llanada", "rioja alavesa", "montana alavesa", "valles alaveses", "cuadrilla de",
    "alegria-dulantzi", "dulantzi", "amurrio", "anana", "aramaio", "arminon", "arraia-maeztu",
    "maeztu", "arratzua", "ubarrundia", "artziniega", "asparrena", "araia", "aiara", "ayala",
    "banos de ebro", "barrundia", "berantevilla", "bernedo", "campezo", "kanpezu", "elburgo",
    "burgelu", "elciego", "elvillar", "erriberagoitia", "ribera alta", "valle de arana", "harana",
    "iruna oka", "nanclares", "iruraiz", "kripan", "kuartango", "labastida", "lagran", "laguardia",
    "lanciego", "lantaron", "lapuebla de labarca", "laudio", "llodio", "legutio", "leza",
    "moreda de alava", "navaridas", "okondo", "oyon", "oion", "penacerrada", "urizaharra",
    "ribera baja", "rivabellosa", "salvatierra", "agurain", "samaniego", "san millan",
    "donemiliaga", "urkabustaiz", "izarra", "valdegovia", "gaubea", "villabuena", "yecora",
    "zalduondo", "zambrana", "zigoitia", "zuia", "murgia", "txagorritxu", "foronda",
    "salburua", "zabalgana", "lakua", "judimendi", "abetxuko", "arasur", "jundiz",
]


# ---------------------------------------------------------------- utilidades
def normaliza(texto: str) -> str:
    """minúsculas y sin tildes, para comparar palabras."""
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower()


def patron(palabras: list[str]) -> re.Pattern | None:
    """Regex que encuentra cualquiera de las palabras.
    Palabras cortas (<=4 letras) deben coincidir enteras; las largas,
    por el principio ("viviend" -> viviendas)."""
    trozos = []
    for p in palabras:
        p = normaliza(str(p)).strip()
        if not p:
            continue
        esc = re.escape(p)
        if not re.search(r"\w", p):            # símbolos como "%"
            trozos.append(esc)
        elif len(p) <= 4:
            trozos.append(rf"\b{esc}\b")
        else:
            trozos.append(rf"\b{esc}")
    return re.compile("|".join(trozos)) if trozos else None


def coincidencias(rx: re.Pattern | None, texto: str) -> set[str]:
    return set(m.group(0) for m in rx.finditer(texto)) if rx else set()


def html_a_texto(fragmento: str) -> str:
    """Convierte HTML en texto conservando saltos de línea útiles."""
    if not fragmento:
        return ""
    sopa = BeautifulSoup(fragmento, "html.parser")
    for t in sopa(["script", "style", "iframe", "img", "figure"]):
        t.decompose()
    for t in sopa.find_all(["br"]):
        t.replace_with("\n")
    for t in sopa.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "tr"]):
        prefijo = "• " if t.name == "li" else ""
        t.insert_before("\n" + prefijo)
        t.insert_after("\n")
    texto = html.unescape(sopa.get_text())
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    texto = re.sub(r"La entrada .* se public[oó] primero en .*$", "", texto, flags=re.S)
    return texto.strip()


def recorta(texto: str, n: int = MAX_RESUMEN) -> str:
    texto = texto.strip()
    if len(texto) <= n:
        return texto
    return texto[:n].rsplit(" ", 1)[0] + "…"


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def de_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def ident(*partes: str) -> str:
    return hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- lectura
def descarga(url: str, fixtures: Path | None, fid: str) -> bytes:
    if fixtures:
        for ext in (".xml", ".html"):
            f = fixtures / f"{fid}{ext}"
            if f.exists():
                return f.read_bytes()
        raise FileNotFoundError(f"no hay fixture para {fid}")
    ultimo_error = None
    for intento in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT,
                                                        "Accept-Language": "es-ES,es;q=0.9"})
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:   # reintenta 2 veces
            ultimo_error = e
            time.sleep(3 * (intento + 1))
    raise ultimo_error


def lee_rss(contenido: bytes, fuente: dict) -> list[dict]:
    feed = feedparser.parse(contenido)
    if feed.bozo and not feed.entries:
        raise ValueError(f"feed ilegible: {feed.bozo_exception}")
    items = []
    for e in feed.entries:
        titulo = html_a_texto(e.get("title", "")).replace("\n", " ").strip()
        enlace = e.get("link") or e.get("id") or ""
        if not titulo or not enlace:
            continue
        cuerpo = ""
        if e.get("summary"):
            cuerpo = e.summary
        elif e.get("content"):
            cuerpo = e.content[0].get("value", "")
        fecha = None
        for campo in ("published_parsed", "updated_parsed"):
            if e.get(campo):
                fecha = datetime(*e[campo][:6], tzinfo=timezone.utc)
                break
        categorias = [t.get("term", "") for t in e.get("tags", []) if t.get("term")]
        items.append({
            "titulo": titulo,
            "enlace": enlace,
            "texto": html_a_texto(cuerpo),
            "fecha": fecha,
            "categorias": categorias,
        })
    return items


FECHA_HTML = re.compile(r"\b(\d{1,2})[ ./-](\d{1,2})[ ./-](20\d\d)\b")


def lee_html(contenido: bytes, fuente: dict) -> list[dict]:
    """Para webs sin RSS: recoge los enlaces que contienen 'patron_enlace'."""
    sopa = BeautifulSoup(contenido, "html.parser")
    patron_enlace = fuente.get("patron_enlace", "")
    base = fuente.get("base") or fuente["url"]
    vistos: dict[str, dict] = {}
    for a in sopa.find_all("a", href=True):
        if patron_enlace not in a["href"]:
            continue
        enlace = urljoin(base, a["href"]).split("?")[0]
        titulo = " ".join(a.get_text(" ").split())
        if len(titulo) < 15 or titulo.lower().startswith(("seguir leyendo", "leer m", "ver m")):
            titulo = ""
        bloque = a.find_parent(["article", "li", "div"])
        texto_bloque = " ".join(bloque.get_text(" ").split()) if bloque else ""
        item = vistos.setdefault(enlace, {"titulo": "", "enlace": enlace, "texto": "", "_bloque": "",
                                          "fecha": None, "categorias": []})
        if titulo and len(titulo) > len(item["titulo"]):
            item["titulo"] = titulo
        if texto_bloque and (not item["_bloque"] or len(texto_bloque) < len(item["_bloque"])):
            item["_bloque"] = texto_bloque   # el bloque más pequeño que contiene la noticia
    resultado = []
    for item in vistos.values():
        if not item["titulo"]:
            continue
        bloque = item.pop("_bloque")
        m = FECHA_HTML.search(bloque)
        if m:
            d, mes, a_ = map(int, m.groups())
            try:   # solo hay día: se guarda a medianoche de Madrid (la web no muestra hora)
                item["fecha"] = datetime(a_, mes, d, tzinfo=MADRID)
            except ValueError:
                pass
            bloque = bloque[:m.start()]           # lo que va tras la fecha son metadatos
        resto = bloque.replace(item["titulo"], " ")
        resto = re.sub(r"(Seguir leyendo|Leer más|Ver más).*$", "", resto)
        resto = re.sub(r"\b(La Diputación Foral|Diputación Foral de Álava)\s*[·|-]?\s*$", "", resto.strip())
        item["texto"] = " ".join(resto.split()).strip(" ·|-")
        resultado.append(item)
    return resultado


# ---------------------------------------------------------------- clasificación
class Clasificador:
    def __init__(self, temas_cfg: dict):
        self.rx_alava = patron(ALAVA)
        self.temas = [(t["nombre"], patron(t.get("palabras", [])), t.get("pistas", []))
                      for t in temas_cfg.get("temas", [])]
        self.rx_fondo = patron(temas_cfg.get("fondo", []))
        self.rx_excluir = patron(temas_cfg.get("excluir", []))

    def clasifica(self, item: dict, fuente: dict) -> None:
        texto = normaliza(f"{item['titulo']} {item['titulo']} {item.get('texto', '')[:1500]}")
        titulo_n = normaliza(item["titulo"])
        item["alava"] = bool(fuente.get("local")) or bool(coincidencias(self.rx_alava, texto))

        temas = []
        for nombre, rx, _ in self.temas:
            hits = coincidencias(rx, texto)
            if hits:
                # pesan más las palabras que aparecen en el titular
                peso = len(hits) + sum(1 for h in hits if h in titulo_n)
                temas.append((peso, nombre))
        temas.sort(reverse=True)
        item["temas"] = [n for _, n in temas[:3]]

        if fuente["seccion"] == "ideas":
            fondo = coincidencias(self.rx_fondo, texto)
            excl = coincidencias(self.rx_excluir, normaliza(item["titulo"] + " " + item.get("texto", "")[:400]))
            puntos = 0.0
            puntos += min(sum(p for p, _ in temas[:2]), 6) * 1.0
            puntos += min(len(fondo), 3) * 1.5
            puntos -= len(excl) * 4
            if item["alava"]:
                puntos -= 3      # si ya habla de Álava no es "idea para adaptar"
            item["puntos"] = round(puntos, 1)
            item["senales"] = [BONITO.get(s, s) for s in sorted(fondo)][:4]

    def pistas(self) -> dict:
        return {nombre: pistas for nombre, _, pistas in self.temas}


def tipo_item(item: dict, fuente: dict) -> str:
    if fuente["id"] == "ayto-agenda":
        return "agenda"
    cats = " ".join(item.get("categorias", [])).lower()
    if "convocatoria" in cats or item["titulo"].lower().startswith("convocatorias de prensa"):
        return "convocatoria"
    return "noticia"


# ---------------------------------------------------------------- histórico
def carga_historico() -> dict:
    if HISTORICO.exists():
        try:
            return json.loads(HISTORICO.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("AVISO: histórico dañado, se empieza de cero", file=sys.stderr)
    return {"items": {}}


def guarda_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


# ---------------------------------------------------------------- principal
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", type=Path, help="carpeta con feeds de prueba")
    ap.add_argument("--ahora", help="fecha simulada ISO (solo pruebas)")
    args = ap.parse_args()

    cfg = yaml.safe_load((RAIZ / "fuentes.yaml").read_text(encoding="utf-8"))
    temas_cfg = yaml.safe_load((RAIZ / "temas.yaml").read_text(encoding="utf-8"))
    clasif = Clasificador(temas_cfg)
    ahora = de_iso(args.ahora) if args.ahora else ahora_utc()

    hist = carga_historico()
    items_hist: dict = hist.get("items", {})
    estado = []

    for fuente in cfg.get("fuentes", []):
        if fuente.get("activa", True) is False:
            continue
        fuente.setdefault("seccion", "instituciones")
        inicio = time.time()
        try:
            crudo = descarga(fuente["url"], args.fixtures, fuente["id"])
            lector = lee_html if fuente.get("tipo") == "html" else lee_rss
            nuevos = lector(crudo, fuente)
            n_nuevos = 0
            for it in nuevos:
                clasif.clasifica(it, fuente)
                # Los avisos de movilidad repiten el mismo aviso con enlaces distintos:
                # para ellos la clave es el titular.
                clave = (ident(fuente["id"], normaliza(it["titulo"])) if fuente.get("clave_por_titulo")
                         else ident(fuente["id"], it["enlace"]))
                previo = items_hist.get(clave)
                registro = {
                    "id": clave,
                    "fuente": fuente["id"],
                    "seccion": fuente["seccion"],
                    "tipo": tipo_item(it, fuente),
                    "titulo": it["titulo"],
                    "enlace": it["enlace"],
                    "resumen": recorta(it["texto"], 1800 if tipo_item(it, fuente) == "convocatoria" else MAX_RESUMEN),
                    "fecha": iso(it["fecha"]),
                    "visto": previo["visto"] if previo else iso(ahora),
                    "alava": it["alava"],
                    "temas": it["temas"],
                    "categorias": it.get("categorias", [])[:4],
                }
                if "puntos" in it:
                    registro["puntos"] = it["puntos"]
                    registro["senales"] = it["senales"]
                if not previo:
                    n_nuevos += 1
                items_hist[clave] = registro
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], "url": fuente["url"],
                           "seccion": fuente["seccion"], "local": bool(fuente.get("local")),
                           "ok": True, "leidos": len(nuevos),
                           "nuevos": n_nuevos, "segundos": round(time.time() - inicio, 1)})
            print(f"OK   {fuente['id']:<22} {len(nuevos):>3} leídos, {n_nuevos:>3} nuevos")
        except Exception as e:   # una fuente caída no debe tumbar el resto
            estado.append({"id": fuente["id"], "nombre": fuente["nombre"], "url": fuente["url"],
                           "seccion": fuente["seccion"], "local": bool(fuente.get("local")), "ok": False,
                           "error": f"{type(e).__name__}: {str(e)[:200]}"})
            print(f"FALLO {fuente['id']:<21} {type(e).__name__}: {e}", file=sys.stderr)

    # Se eliminan las duplicadas (misma noticia en dos feeds del Ayuntamiento)
    por_enlace: dict[str, str] = {}
    for clave, it in sorted(items_hist.items(), key=lambda kv: kv[1]["seccion"] != "agenda"):
        if it["fuente"].startswith("ayto-") and it["fuente"] != "ayto-movilidad":
            if it["enlace"] in por_enlace and por_enlace[it["enlace"]] != clave:
                it["duplicado"] = True
            else:
                por_enlace[it["enlace"]] = clave
    items_hist = {k: v for k, v in items_hist.items() if not v.get("duplicado")}

    # Poda: fuera lo antiguo (salvo agenda futura)
    limite = ahora - timedelta(days=DIAS_HISTORICO)
    def vigente(it: dict) -> bool:
        if it["tipo"] == "agenda":
            f = de_iso(it["fecha"])
            return bool(f and f >= ahora - timedelta(days=2))
        return de_iso(it["visto"]) >= limite
    items_hist = {k: v for k, v in items_hist.items() if vigente(v)}

    # Las ideas solo de los últimos días y con puntuación suficiente
    limite_ideas = ahora - timedelta(days=DIAS_IDEAS)
    publicados = []
    for it in items_hist.values():
        if it["seccion"] == "ideas":
            ref = de_iso(it["fecha"]) or de_iso(it["visto"])
            if it.get("puntos", 0) < UMBRAL_IDEA or ref < limite_ideas:
                continue
        publicados.append(it)

    guarda_json(HISTORICO, {"actualizado": iso(ahora), "items": items_hist})
    guarda_json(SALIDA, {
        "actualizado": iso(ahora),
        "fuentes": estado,
        "manuales": cfg.get("enlaces_manuales", []),
        "pistas": clasif.pistas(),
        "items": sorted(publicados, key=lambda i: i["fecha"] or i["visto"], reverse=True),
    })
    fallos = sum(1 for s in estado if not s["ok"])
    print(f"\n{len(publicados)} elementos publicados · {len(estado) - fallos} fuentes OK · {fallos} con fallo")
    # Solo es error grave si fallan TODAS las fuentes
    return 1 if estado and fallos == len(estado) else 0


if __name__ == "__main__":
    sys.exit(main())
