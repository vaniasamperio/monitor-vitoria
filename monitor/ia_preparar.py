#!/usr/bin/env python3
"""
Prepara el trabajo diario de la IA (lo ejecuta la tarea programada de Claude).

Lee docs/datos.json y docs/ia.json y escribe data/ia_pendiente.json con:
  - titulos:  elementos recientes y relevantes que aún no tienen titular claro
  - ideas:    ideas de temas que aún no tienen enfoque propio
  - buzon:    resumen del buzón ciudadano (para destacar lo que se repite)
  - tribunales: notas del TSJPV recientes (para contar qué ha pasado)
  - sucesos:  partes policiales y sucesos de Álava de las últimas 36 horas (para el parte del día)
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
datos = json.loads((RAIZ / "docs" / "datos.json").read_text(encoding="utf-8"))
ia_f = RAIZ / "docs" / "ia.json"
ia = json.loads(ia_f.read_text(encoding="utf-8")) if ia_f.exists() else {}
hechos_t = set((ia.get("titulos") or {}).keys())
hechos_e = set((ia.get("enfoques") or {}).keys())
nombres = {f["id"]: f["nombre"] for f in datos["fuentes"]}
ahora = datetime.fromisoformat(datos["actualizado"])
limite = ahora - timedelta(days=3)


def ref(i):
    return datetime.fromisoformat(i.get("fecha") or i["visto"])


titulos = []
for i in datos["items"]:
    if i["seccion"] not in ("instituciones", "pueblos", "boletines", "asociaciones"):
        continue
    if i["id"] in hechos_t or i.get("rutina") or not i.get("alava") or ref(i) < limite:
        continue
    titulos.append({"id": i["id"], "fuente": nombres.get(i["fuente"], i["fuente"]), "titulo": i["titulo"],
                    "texto": (i.get("resumen") or "")[:350], "organismo": i.get("organismo", ""),
                    "municipios": i.get("municipios", []), "relevancia": i.get("relevancia", 0)})
titulos.sort(key=lambda x: -x["relevancia"])
titulos = titulos[:220]

ideas = [i for i in datos["items"] if i["seccion"] == "ideas" and not i.get("alava") and i["id"] not in hechos_e]
ideas.sort(key=lambda i: -(i.get("puntos") or 0))
ideas = [{"id": i["id"], "medio": nombres.get(i["fuente"], i["fuente"]), "titulo": i["titulo"],
          "texto": (i.get("resumen") or "")[:500], "temas": i.get("temas", [])} for i in ideas[:25]]

tribunales = [{"id": i["id"], "titulo": i["titulo"], "texto": (i.get("resumen") or "")[:600], "enlace": i["enlace"]}
              for i in datos["items"] if i["fuente"] == "tsjpv" and ref(i) >= ahora - timedelta(days=7)]

sucesos = [{"id": i["id"], "fuente": nombres.get(i["fuente"], i["fuente"]), "titulo": i["titulo"],
            "texto": (i.get("resumen") or "")[:400], "municipios": i.get("municipios", [])}
           for i in datos["items"] if i.get("suceso") and i.get("alava") and ref(i) >= ahora - timedelta(hours=36)]

salida = {"generado": ahora.isoformat(), "titulos": titulos, "ideas": ideas,
          "buzon": datos.get("buzon", [])[:12], "tribunales": tribunales, "sucesos": sucesos[:60]}
(RAIZ / "data").mkdir(exist_ok=True)
(RAIZ / "data" / "ia_pendiente.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Pendiente: {len(titulos)} titulares, {len(ideas)} ideas, {len(salida['buzon'])} áreas del buzón, "
      f"{len(tribunales)} notas de tribunales, {len(sucesos)} sucesos -> data/ia_pendiente.json")
