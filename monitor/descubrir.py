#!/usr/bin/env python3
"""
Explorador de fuentes: comprueba qué webs tienen RSS y si permiten la lectura
automática (robots.txt). Genera diagnostico/informe.json y guarda muestras
de páginas en diagnostico/muestras/ para programar lectores.

Se ejecuta en GitHub Actions con el workflow "Explorar fuentes".
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "diagnostico"
UA = "MonitorHoyPorHoyVitoria/1.0 (lector RSS para uso periodistico)"
RUTAS_FEED = ["feed/", "rss", "rss.xml", "es/rss", "es/feed/", "feed", "index.php/feed/",
              "es/noticias/rss", "noticias/rss", "rss/noticias", "es/rss.xml", "atom.xml",
              "?format=feed&type=rss", "index.php/es/?format=feed&type=rss", "es/?format=feed&type=rss",
              "actualidad/feed/", "noticias/feed/", "es/noticias?format=feed&type=rss", "eu/feed/",
              "es/actualidad?format=feed&type=rss", "index.php?format=feed&type=rss"]

ses = requests.Session()
ses.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})


def wikidata_municipios() -> list[dict]:
    q = """
    SELECT ?m ?mLabel ?ine ?web WHERE {
      ?m wdt:P772 ?ine . FILTER(STRSTARTS(?ine, "01") && STRLEN(?ine) = 5)
      OPTIONAL { ?m wdt:P856 ?web }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es,eu,en". }
    }"""
    r = ses.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, timeout=60)
    r.raise_for_status()
    filas = {}
    for b in r.json()["results"]["bindings"]:
        ine = b["ine"]["value"]
        f = filas.setdefault(ine, {"nombre": b["mLabel"]["value"], "ine": ine, "webs": set(), "categoria": "ayuntamiento"})
        if "web" in b:
            f["webs"].add(b["web"]["value"])
    out = []
    for f in sorted(filas.values(), key=lambda x: x["nombre"]):
        webs = sorted(f.pop("webs"))
        f["web"] = webs[0] if webs else None
        f["otras_webs"] = webs[1:]
        out.append(f)
    return out


def permitido(url: str, cache: dict) -> bool | None:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = ses.get(base + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        cache[base] = rp
    try:
        return cache[base].can_fetch(UA, url)
    except Exception:
        return None


def prueba_feed(url: str) -> dict | None:
    try:
        r = ses.get(url, timeout=20)
        if r.status_code != 200:
            return None
        f = feedparser.parse(r.content)
        if not f.entries:
            return None
        fechas = [e.get("published_parsed") or e.get("updated_parsed") for e in f.entries]
        fechas = [time.strftime("%Y-%m-%d", x) for x in fechas if x]
        return {"url": r.url, "titulo": f.feed.get("title", ""), "entradas": len(f.entries),
                "ultima": max(fechas) if fechas else None,
                "ejemplos": [e.get("title", "")[:100] for e in f.entries[:3]]}
    except Exception:
        return None


def explora(c: dict, robots: dict) -> dict:
    res = dict(c)
    web = c.get("web")
    if not web:
        res["estado"] = "sin_web"
        return res
    directo = prueba_feed(web) if c.get("feed") else None
    if directo:
        directo["robots_ok"] = permitido(directo["url"], robots)
        res.update({"estado": "rss", "feeds": [directo], "url_final": web})
        return res
    try:
        r = ses.get(web, timeout=25, allow_redirects=True)
        res["http"] = r.status_code
        res["url_final"] = r.url
        sopa = BeautifulSoup(r.content, "html.parser")
        res["titulo_pagina"] = (sopa.title.get_text(" ", strip=True) if sopa.title else "")[:150]
        gen = sopa.find("meta", attrs={"name": "generator"})
        res["generador"] = gen.get("content", "")[:80] if gen else ""
        texto = sopa.get_text(" ", strip=True).lower()
        res["menciona_alava"] = bool(re.search(r"vitoria|gasteiz|álava|alava|araba", texto))
        res["robots_ok"] = permitido(r.url, robots)
        candidatos = []
        for l in sopa.find_all("link", rel=lambda v: v and "alternate" in v):
            if "rss" in (l.get("type") or "") or "atom" in (l.get("type") or ""):
                candidatos.append(urljoin(r.url, l.get("href", "")))
        for a in sopa.find_all("a", href=True):
            h = a["href"].lower()
            if ("rss" in h or "/feed" in h) and not h.startswith("mailto"):
                candidatos.append(urljoin(r.url, a["href"]))
        base = r.url if r.url.endswith("/") else r.url.rsplit("/", 1)[0] + "/"
        raiz = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}/"
        for ruta in RUTAS_FEED:
            candidatos += [urljoin(base, ruta), urljoin(raiz, ruta)]
        vistos, feeds = set(), []
        for u in candidatos:
            if u in vistos or len(feeds) >= 3:
                continue
            vistos.add(u)
            f = prueba_feed(u)
            if f and f["url"] not in [x["url"] for x in feeds]:
                f["robots_ok"] = permitido(f["url"], robots)
                feeds.append(f)
        res["feeds"] = feeds
        res["estado"] = "rss" if feeds else "sin_rss"
        if not feeds and r.status_code == 200:
            nombre = re.sub(r"[^a-z0-9]+", "-", c["nombre"].lower())[:40]
            (SALIDA / "muestras").mkdir(parents=True, exist_ok=True)
            (SALIDA / "muestras" / f"web-{nombre}.html").write_bytes(r.content[:400_000])
            # enlaces que parecen noticias, para valorar un lector html
            enl = []
            for a in sopa.find_all("a", href=True):
                t = " ".join(a.get_text(" ").split())
                if 25 <= len(t) <= 200 and re.search(r"notici|berri|actualidad|news|/20\d\d/", a["href"], re.I):
                    enl.append({"t": t[:120], "h": urljoin(r.url, a["href"])})
            res["enlaces_noticia"] = enl[:8]
    except Exception as e:
        res["estado"] = "error"
        res["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    return res


def main() -> int:
    SALIDA.mkdir(exist_ok=True)
    import os
    fichero = os.environ.get("CANDIDATOS", "candidatos.yaml")
    cfg = yaml.safe_load((RAIZ / "monitor" / fichero).read_text(encoding="utf-8"))
    import os
    try:
        if os.environ.get("SOLO_CANDIDATOS"):
            raise RuntimeError("solo candidatos")
        munis = wikidata_municipios()
        print(f"Wikidata: {len(munis)} municipios")
    except Exception as e:
        print("Wikidata falló:", e)
        munis = []
    lista = munis + cfg.get("candidatos", [])
    robots: dict = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(lambda c: explora(c, robots), lista))

    # muestras de páginas concretas
    (SALIDA / "muestras").mkdir(parents=True, exist_ok=True)
    muestras = []
    for m in cfg.get("muestras", []):
        url = m["url"].replace("{HOY}", date.today().strftime("%Y%m%d"))
        try:
            r = ses.get(url, timeout=30, headers={"Accept": m.get("accept", "*/*")})
            ext = "json" if "json" in r.headers.get("content-type", "") else ("xml" if "xml" in r.headers.get("content-type", "") else "html")
            (SALIDA / "muestras" / f"{m['id']}.{ext}").write_bytes(r.content[:2_000_000])
            muestras.append({"id": m["id"], "http": r.status_code, "bytes": len(r.content),
                             "robots_ok": permitido(url, robots), "tipo": r.headers.get("content-type")})
        except Exception as e:
            muestras.append({"id": m["id"], "error": str(e)[:150]})

    (SALIDA / "informe.json").write_text(json.dumps({"fuentes": resultados, "muestras": muestras},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    # resumen legible
    lin = ["# Informe de fuentes", ""]
    for r in resultados:
        f = r.get("feeds") or []
        marca = {"rss": "RSS", "sin_rss": "sin RSS", "sin_web": "sin web", "error": "ERROR"}.get(r.get("estado"), "?")
        lin.append(f"- [{marca}] {r['nombre']} ({r.get('categoria')}) {r.get('url_final') or r.get('web') or ''}"
                   + (f" -> {f[0]['url']} ({f[0]['entradas']} ent., última {f[0]['ultima']}, robots {f[0]['robots_ok']})" if f else "")
                   + (f" · {r.get('error')}" if r.get("error") else ""))
    lin += ["", "## Muestras"] + [f"- {m}" for m in muestras]
    (SALIDA / "informe.md").write_text("\n".join(lin), encoding="utf-8")
    print("\n".join(lin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
