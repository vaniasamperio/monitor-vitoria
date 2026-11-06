#!/usr/bin/env python3
"""
Resumen del día para la redacción de SER Vitoria.

- Escribe docs/reunion.html: una página limpia e imprimible para la reunión de la mañana.
- Con --enviar, lo manda además por correo desde el Gmail de la redacción
  (GMAIL_USER, GMAIL_APP_PASSWORD) a CORREO_DESTINOS (varias direcciones separadas por comas).
  Solo envía si en Madrid son las 7 (el flujo se lanza a dos horas UTC por el cambio de hora);
  --forzar lo envía a cualquier hora.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:                                    # pragma: no cover
    MADRID = timezone(timedelta(hours=1))

RAIZ = Path(__file__).resolve().parent.parent
WEB = "https://vaniasamperio.github.io/monitor-vitoria/"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def e(t) -> str:
    return html.escape(str(t or ""), quote=True)


def ref(i: dict) -> datetime:
    for k in ("fecha", "visto"):
        if i.get(k):
            try:
                return datetime.fromisoformat(i[k])
            except ValueError:
                pass
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def construye(datos: dict, ia: dict, ahora: datetime) -> tuple[str, str]:
    """Devuelve (asunto, html)."""
    hoy = ahora.astimezone(MADRID).date()
    k = hoy.isoformat()
    titulos = ia.get("titulos", {})
    tit = lambda i: titulos.get(i["id"]) or i.get("titulo_claro") or i["titulo"]
    nombre_f = {f["id"]: f["nombre"] for f in datos.get("fuentes", [])}
    items = datos.get("items", [])
    secciones = []

    def bloque(titulo: str, cuerpo: str, nota: str = "") -> None:
        if cuerpo:
            secciones.append(f'<h2 style="font:700 17px Georgia,serif;color:#1d3a3a;margin:22px 0 6px;border-bottom:2px solid #e9a23b;padding-bottom:3px">'
                             f'{e(titulo)}{f" <span style=font-weight:400;font-size:13px;color:#777>{e(nota)}</span>" if nota else ""}</h2>{cuerpo}')

    def li(texto: str, enlace: str = "", detalle: str = "") -> str:
        t = f'<a href="{e(enlace)}" style="color:#14213d;text-decoration:none;font-weight:600">{e(texto)}</a>' if enlace else f"<b>{e(texto)}</b>"
        return f'<li style="margin:0 0 7px">{t}{f"<br><span style=color:#666;font-size:13px>{e(detalle)}</span>" if detalle else ""}</li>'

    ul = lambda filas: f'<ul style="padding-left:18px;margin:4px 0">{"".join(filas)}</ul>' if filas else ""

    # 1. datos vivos
    vivos = datos.get("vivos") or {}
    filas = []
    for a in (vivos.get("avisos") or [])[:5]:
        filas.append(li(f"⚠ {a['titulo']}", a.get("enlace", ""), a.get("detalle", "")))
    if vivos.get("embalses"):
        filas.append(li("Embalses: " + " · ".join(f"{x['nombre']} {x['porcentaje']}%" for x in vivos["embalses"]),
                        vivos["embalses"][0].get("enlace", ""), vivos.get("embalses_nota", "")))
    for t in (vivos.get("trafico") or [])[:4]:
        filas.append(li(f"🚗 {t['titulo']}", "", t.get("detalle", "")))
    if vivos.get("aire"):
        filas.append(li(f"Aire: {vivos['aire']}"))
    bloque("Datos del día", ul(filas))

    # 2. agenda de hoy
    cal = datos.get("calendario", [])
    hoy_ev = [c for c in cal if (c["fecha"] == k or c.get("hasta") == k) and c.get("tipo") not in ("dia", "efemeride")]
    cultura = [c for c in hoy_ev if c.get("categoria") == "cultura" and c.get("tipo") == "agenda"]
    resto = sorted([c for c in hoy_ev if c not in cultura], key=lambda c: (c.get("hora") or "99", c["titulo"]))
    vistos, filas = set(), []
    for c in resto:
        clave = re.sub(r"\W+", "", c["titulo"].lower())[:50]
        if clave in vistos:
            continue
        vistos.add(clave)
        det = (c.get("lugar") or c.get("frase") or "")[:140]
        if re.sub(r"\W+", "", det.lower())[:40] in re.sub(r"\W+", "", c["titulo"].lower()):
            det = ""                                  # la frase solo repite el título
        filas.append(li(f"{c.get('hora') or 'Todo el día'} · {c['titulo']}", c.get("enlace", ""), det))
    efem = [c for c in cal if c["fecha"] == k and c.get("tipo") in ("efemeride", "dia")]
    if efem:
        filas.append(li("Efemérides y días: " + " · ".join(c["titulo"] for c in efem[:4])))
    bloque("Agenda de hoy", ul(filas[:18]), f"y {len(cultura)} actividades culturales" if cultura else "")

    # 3. lo más relevante
    lim = datetime.fromisoformat(datos["actualizado"]) - timedelta(hours=30)
    cand = sorted([i for i in items if i["seccion"] in ("instituciones", "pueblos", "boletines", "asociaciones")
                   and not i.get("rutina") and i.get("alava") and ref(i) >= lim],
                  key=lambda i: (-(i.get("relevancia") or 0), -ref(i).timestamp()))
    por, top = {}, []
    for i in cand:
        por[i["fuente"]] = por.get(i["fuente"], 0) + 1
        if por[i["fuente"]] <= 2:
            top.append(i)
        if len(top) >= 10:
            break
    bloque("Lo más relevante", ul([li(tit(i), i["enlace"], nombre_f.get(i["fuente"], "")) for i in top]))

    # 4. sucesos
    s = ia.get("sucesos") or {}
    fresco = s.get("resumen") and s.get("fecha") and datetime.fromisoformat(s["fecha"]) >= ahora - timedelta(hours=30)
    if fresco:
        bloque("Sucesos", f'<p style="margin:4px 0;line-height:1.5">{e(s["resumen"])}</p>')
    else:
        suc = sorted([i for i in items if i.get("suceso") and i.get("alava") and i["fuente"] not in ("tsjpv", "correo-cendoj")
                      and ref(i) >= lim], key=lambda i: -ref(i).timestamp())[:5]
        bloque("Sucesos", ul([li(tit(i), i["enlace"], nombre_f.get(i["fuente"], "")) for i in suc]))

    # 5. tribunales
    trib = ia.get("tribunales", {})
    tr = sorted([i for i in items if i["fuente"] in ("tsjpv", "correo-cendoj") and ref(i) >= lim - timedelta(hours=24)],
                key=lambda i: -ref(i).timestamp())[:8]
    bloque("Tribunales", ul([li(tit(i), i["enlace"], trib.get(i["id"], "")) for i in tr]))

    # 6. plazos: vence hoy / próximos días / ¿se ha cumplido?
    seg = sorted([c for c in cal if c.get("seguimiento") and k <= (c.get("hasta") or c["fecha"]) <= (hoy + timedelta(days=3)).isoformat()],
                 key=lambda c: c.get("hasta") or c["fecha"])
    pasados = [c for c in cal if c.get("seguimiento") and (hoy - timedelta(days=3)).isoformat() <= (c.get("hasta") or c["fecha"]) < k]
    filas = [li(("HOY · " if (c.get("hasta") or c["fecha"]) == k else f"{(c.get('hasta') or c['fecha'])[8:10]}/{(c.get('hasta') or c['fecha'])[5:7]} · ") + c["titulo"],
                c.get("enlace", ""), (c.get("frase") or "")[:140]) for c in seg[:8]]
    filas += [li("¿Se ha cumplido? · " + c["titulo"], c.get("enlace", ""), (c.get("frase") or "")[:140]) for c in pasados[:4]]
    bloque("Plazos y obras para seguir", ul(filas))

    # 7. buzón ciudadano
    bz = ia.get("buzon") or {}
    if bz.get("destacados"):
        bloque("Buzón ciudadano", ul([li(x["titulo"], "", x.get("por_que", "")) for x in bz["destacados"][:3]]))

    # 8. dinero público (si hay)
    din = [i for i in items if i["seccion"] == "dinero" and ref(i) >= lim]
    din.sort(key=lambda i: (-(i.get("importe") or 0), -ref(i).timestamp()))
    bloque("Dinero público", ul([li(tit(i), i["enlace"], i.get("resumen", "")[:150]) for i in din[:6]]))

    asunto = f"Radar SER Vitoria · {fecha_larga(hoy)}"
    cuerpo = "".join(secciones) or "<p>Hoy todavía no hay novedades.</p>"
    pagina = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{e(asunto)}</title>
<style>@media print{{.noimprimir{{display:none}} a{{color:#000}}}} body{{max-width:760px;margin:0 auto;padding:18px;font:15px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#222}}</style></head>
<body><div style="background:#1d3a3a;color:#fff;padding:14px 18px;border-radius:8px">
<div style="font:700 21px Georgia,serif">Radar SER Vitoria</div>
<div style="opacity:.85;font-size:14px">{e(fecha_larga(hoy).capitalize())} · actualizado {e(datetime.fromisoformat(datos['actualizado']).astimezone(MADRID).strftime('%H:%M'))}</div></div>
{cuerpo}
<p class="noimprimir" style="margin-top:26px;font-size:13px;color:#777">Todo, con más detalle, en <a href="{WEB}">{WEB}</a>.
<a href="javascript:print()" style="margin-left:10px">Imprimir</a></p></body></html>"""
    return asunto, pagina


def envia(asunto: str, cuerpo: str) -> None:
    usuario, clave = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    destinos = [d.strip() for d in (os.environ.get("CORREO_DESTINOS") or usuario or "").split(",") if d.strip()]
    if not (usuario and clave and destinos):
        print("Correo sin configurar: no se envía.")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = asunto, f"Radar SER Vitoria <{usuario}>", ", ".join(destinos)
    texto = re.sub(r"<[^>]+>", " ", re.sub(r"</(li|p|h2)>", "\n", cuerpo))
    msg.attach(MIMEText(html.unescape(re.sub(r"[ \t]+", " ", texto)), "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(usuario, clave.replace(" ", ""))
        s.sendmail(usuario, destinos, msg.as_string())
    print(f"Enviado a {len(destinos)} dirección(es).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enviar", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    datos = json.loads((RAIZ / "docs" / "datos.json").read_text(encoding="utf-8"))
    ia_f = RAIZ / "docs" / "ia.json"
    ia = json.loads(ia_f.read_text(encoding="utf-8")) if ia_f.exists() else {}
    ahora = datetime.now(timezone.utc)
    asunto, pagina = construye(datos, ia, ahora)
    (RAIZ / "docs" / "reunion.html").write_text(pagina, encoding="utf-8")
    print(f"docs/reunion.html escrito ({len(pagina) // 1024} KB)")
    if a.enviar:
        if not a.forzar and ahora.astimezone(MADRID).hour != 7:
            print("No son las 7 en Madrid: no se envía.")
            return
        envia(asunto, pagina)


if __name__ == "__main__":
    sys.exit(main())
