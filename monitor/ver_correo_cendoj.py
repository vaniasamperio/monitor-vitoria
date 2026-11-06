"""Diagnóstico de una sola vez: estructura de las alertas del CENDOJ (sin direcciones ni cabeceras personales)."""
import re, sys
sys.path.insert(0, "monitor")
import run
from bs4 import BeautifulSoup
for c in run.correos_recientes(6):
    if not any(d.endswith(("poderjudicial.es", "cgpj.es")) for d in run.dominios_de(c)):
        continue
    t = c["texto"] or BeautifulSoup(c["html"] or "", "html.parser").get_text("\n")
    t = "\n".join(l for l in t.splitlines() if l.strip() and "@" not in l
                  and not re.match(r"\s*\**\s*(de|from|para|to|cc|enviado|sent|asunto|subject)\s*:", l, re.I))
    print("=== correo CENDOJ ===")
    print(t[:2500])
    print("enlaces distintos:", sorted({re.sub(r"[0-9a-f]{20,}", "<id>", h) for h in re.findall(r'href="([^"]+)"', c["html"] or "")})[:15])
