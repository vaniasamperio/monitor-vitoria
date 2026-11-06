#!/usr/bin/env python3
"""Sondeo del buscador del CENDOJ (solo diagnóstico, se lanza a mano). Respeta robots.txt y el crawl-delay de 5 s."""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urljoin
import requests

OUT = Path("diagnostico"); OUT.mkdir(exist_ok=True)
UA = "MonitorHoyPorHoyVitoria/1.0 (consulta periodistica, uso personal)"
s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
log = []
def guarda(nombre, r):
    (OUT / nombre).write_bytes(r.content)
    log.append({"f": nombre, "url": r.url, "http": r.status_code, "bytes": len(r.content), "tipo": r.headers.get("content-type")})
    time.sleep(5)

modo = sys.argv[1] if len(sys.argv) > 1 else "1"
BASE = "https://www.poderjudicial.es/search/"
if modo == "1":
    r = s.get(BASE + "indexAN.jsp", timeout=30); guarda("index.html", r)
    for src in sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', r.text))):
        if "search" in src or "cendoj" in src.lower() or "buscador" in src.lower() or src.startswith("js/"):
            u = urljoin(r.url, src)
            try:
                guarda("js_" + re.sub(r"[^a-zA-Z0-9.]+", "_", src)[-60:], s.get(u, timeout=30))
            except Exception as e:
                log.append({"f": src, "error": str(e)})
else:
    pruebas = json.loads(Path("monitor/sondeo_cendoj.json").read_text())
    s.get(BASE + "indexAN.jsp", timeout=30); time.sleep(5)
    for i, p in enumerate(pruebas):
        try:
            r = s.request(p.get("metodo", "POST"), urljoin(BASE, p["url"]), data=p.get("datos"), timeout=40,
                          headers={"X-Requested-With": "XMLHttpRequest"} if p.get("ajax") else None)
            guarda(f"prueba{i}.html", r)
        except Exception as e:
            log.append({"f": f"prueba{i}", "error": str(e)})
(OUT / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
print(json.dumps(log, ensure_ascii=False, indent=1))
