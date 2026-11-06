#!/usr/bin/env python3
"""
Guarda el trabajo de la IA: une data/ia_respuesta.json con docs/ia.json.

Formato de data/ia_respuesta.json (todo opcional):
{
  "titulos":  {"<id>": "Titular claro, en castellano, que se entienda de un vistazo"},
  "enfoques": {"<id>": {"enfoque": "...", "preguntas": ["...", "..."], "llamar": ["...", "..."]}},
  "tribunales": {"<id>": "Qué ha pasado, en una o dos frases"},
  "eustat":   [{"titulo": "...", "dato_alava": "...", "fecha": "AAAA-MM-DD", "enlace": "https://..."}],
  "buzon":    {"resumen": "...", "destacados": [{"titulo": "...", "por_que": "...", "area": "..."}]}
}
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
resp_f = RAIZ / "data" / "ia_respuesta.json"
ia_f = RAIZ / "docs" / "ia.json"
if not resp_f.exists():
    sys.exit("No existe data/ia_respuesta.json")
resp = json.loads(resp_f.read_text(encoding="utf-8"))
ia = json.loads(ia_f.read_text(encoding="utf-8")) if ia_f.exists() else {}
datos = json.loads((RAIZ / "docs" / "datos.json").read_text(encoding="utf-8"))
vivos = {i["id"] for i in datos["items"]}


def limpio(t, n=220):
    t = " ".join(str(t or "").split())
    return t[:n]


for clave, n in (("titulos", 180), ("tribunales", 420)):
    d = {k: v for k, v in (ia.get(clave) or {}).items() if k in vivos}
    for k, v in (resp.get(clave) or {}).items():
        if k in vivos and limpio(v):
            d[k] = limpio(v, n)
    ia[clave] = d

enf = {k: v for k, v in (ia.get("enfoques") or {}).items() if k in vivos}
for k, v in (resp.get("enfoques") or {}).items():
    if k in vivos and isinstance(v, dict) and v.get("enfoque"):
        enf[k] = {"enfoque": limpio(v["enfoque"], 400),
                  "preguntas": [limpio(q, 220) for q in (v.get("preguntas") or [])][:4],
                  "llamar": [limpio(q, 120) for q in (v.get("llamar") or [])][:4]}
ia["enfoques"] = enf

if resp.get("eustat") is not None:
    ia["eustat"] = [{k: limpio(e.get(k), 400) for k in ("titulo", "dato_alava", "fecha", "enlace")}
                    for e in resp["eustat"] if e.get("dato_alava")][:8]
if resp.get("buzon"):
    b = resp["buzon"]
    ia["buzon"] = {"resumen": limpio(b.get("resumen"), 500),
                   "destacados": [{k: limpio(x.get(k), 220) for k in ("titulo", "por_que", "area")}
                                  for x in (b.get("destacados") or [])][:5]}
ia["actualizado"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
ia_f.write_text(json.dumps(ia, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"ia.json: {len(ia['titulos'])} titulares, {len(ia['enfoques'])} enfoques, "
      f"{len(ia.get('tribunales', {}))} tribunales, {len(ia.get('eustat', []))} datos de Eustat")
