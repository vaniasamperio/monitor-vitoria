"""
Datos vivos de Álava para la portada y el correo de la mañana:
  - avisos meteorológicos de AEMET para las zonas de Álava (RSS oficial),
  - incidencias de tráfico en Álava (API de tráfico de Open Data Euskadi),
  - nivel de los embalses de Ullíbarri y Urrúnaga (embalses.net, datos semanales del Ministerio),
  - calidad del aire de ayer en las estaciones de Álava (API de calidad del aire de Open Data Euskadi).
Cada parte falla por separado: si una no responde, se conserva lo último que se leyó.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _MADRID = ZoneInfo("Europe/Madrid")
except Exception:                                    # pragma: no cover
    _MADRID = timezone(timedelta(hours=1))

from bs4 import BeautifulSoup

AEMET = "https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/rss/CAP_AFAE_wah_RSS.xml"
AEMET_WEB = "https://www.aemet.es/es/eltiempo/prediccion/avisos?w=hoy&p=7501&k=pva"
TRAFICO = "https://api.euskadi.eus/traffic/v1.0/incidences?_page={P}"
EMBALSES = [("Ullíbarri-Gamboa", "https://www.embalses.net/pantano-1149-ullivarri.html"),
            ("Urrúnaga", "https://www.embalses.net/pantano-1153-urrunaga.html")]
AIRE_EST = "https://api.euskadi.eus/air-quality/stations?_elements=200"
AIRE_DIA = "https://api.euskadi.eus/air-quality/measurements/daily/stations/{ID}/from/{D}/to/{D}"

NIVELES_TRAFICO = {"Amarillo", "Rojo", "Negro"}
TIPOS_TRAFICO = re.compile(r"accidente|meteorol|puerto|vialidad|nieve|hielo|corte|retenci", re.I)


def _avisos(descarga) -> list[dict]:
    x = descarga(AEMET).decode("utf-8", "replace")
    out, vistos = [], set()
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        guid = re.search(r"<guid[^>]*>(.*?)</guid>", it, re.S)
        if not guid or "AFAZ7501" not in guid.group(1):          # 75 = País Vasco, 01 = Álava
            continue
        tit = html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1)).strip()
        des = html.unescape(re.search(r"<description>(.*?)</description>", it, re.S).group(1)).strip()
        tit = re.sub(r"^Aviso\.\s*", "", tit)                      # "Nivel amarillo. Lluvias. Llanada alavesa"
        if "verde" in tit.lower() or tit in vistos:
            continue
        vistos.add(tit)
        des = re.sub(r"\s*CET \(UTC\+1\)|\s*CEST \(UTC\+2\)", "", des)
        out.append({"titulo": tit, "detalle": des[:220], "enlace": AEMET_WEB})
    return out[:6]


def _registrada(ini: datetime, ahora: datetime) -> str:
    hoy = (ahora.astimezone(_MADRID) if ahora.tzinfo else ahora).date()
    if ini.date() == hoy:
        return f"registrada a las {ini:%H:%M}"
    if ini.date() == hoy - timedelta(days=1):
        return f"registrada ayer a las {ini:%H:%M}"
    return f"registrada el {ini:%d/%m} a las {ini:%H:%M}"


def _trafico(descarga, ahora: datetime) -> list[dict]:
    out = []
    for p in (1, 2, 3):
        d = json.loads(descarga(TRAFICO.replace("{P}", str(p))))
        for i in d.get("incidences", []):
            if (i.get("province") or "").upper() != "ARABA":
                continue
            tipo, nivel = i.get("incidenceType") or "", i.get("incidenceLevel") or ""
            causa = i.get("cause") or ""
            if nivel not in NIVELES_TRAFICO and not TIPOS_TRAFICO.search(tipo + " " + causa):
                continue
            if re.search(r"aver[ií]a", causa, re.I) and nivel not in ("Rojo", "Negro"):
                continue                                           # un coche averiado no es noticia
            try:
                ini = datetime.fromisoformat(i["startDate"])
                ini = ini.replace(tzinfo=_MADRID) if ini.tzinfo is None else ini.astimezone(_MADRID)
            except (KeyError, ValueError):
                continue
            if tipo.lower().startswith("obras") and ahora - ini > timedelta(days=2):
                continue                                           # obras largas: no son noticia cada día
            if ahora - ini > timedelta(hours=36):
                continue
            via = " ".join(x for x in (i.get("road"), f"km {i['pkStart'].rstrip('0').rstrip('.')}" if i.get("pkStart") else "") if x)
            out.append({"titulo": f"{i.get('cause') or tipo} en {via} ({i.get('cityTown') or 'Álava'})",
                        "detalle": " · ".join(x for x in (tipo, f"nivel {nivel.lower()}" if nivel else "",
                                                          f"dirección {i['direction'].title()}" if i.get("direction") else "",
                                                          _registrada(ini, ahora)) if x),
                        "registrada": ini.isoformat()})
    return out[:6]


def _embalses(descarga) -> tuple[list[dict], str]:
    out, nota = [], ""
    for nombre, url in EMBALSES:
        t = " ".join(BeautifulSoup(descarga(url), "html.parser").get_text(" ").split())
        m = re.search(r"Agua embalsada \((\d\d-\d\d-\d{4})\):\s*([\d.,]+)\s*hm\s*3\s*([\d.,]+)\s*%", t)
        if not m:
            continue
        hace = re.search(r"Misma Semana \(\d{4}\):\s*[\d.,]+\s*hm\s*3\s*([\d.,]+)\s*%", t)
        media = re.search(r"Med\. 10 Años\):\s*[\d.,]+\s*hm\s*3\s*([\d.,]+)\s*%", t)
        pct = float(m.group(3).replace(".", "").replace(",", "."))
        out.append({"nombre": nombre, "porcentaje": round(pct, 1), "hm3": m.group(2), "fecha": m.group(1), "enlace": url,
                    "hace_un_ano": float(hace.group(1).replace(",", ".")) if hace else None,
                    "media_10": float(media.group(1).replace(",", ".")) if media else None})
    if out:
        partes = []
        for e in out:
            if e["hace_un_ano"] is not None:
                dif = e["porcentaje"] - e["hace_un_ano"]
                partes.append(f"{e['nombre']} {'+' if dif >= 0 else ''}{dif:.0f} puntos frente a hace un año")
        nota = f"Datos semanales del Ministerio ({out[0]['fecha']}). " + "; ".join(partes)
    return out, nota


def _aire(descarga, ahora: datetime) -> str:
    est = json.loads(descarga(AIRE_EST))
    alava = [(f["properties"]["id"], f["properties"]["name"].title(), f["properties"]["location"]["municipality"])
             for f in est.get("features", []) if f["properties"]["location"].get("countyId") == "01"]
    ayer = (ahora - timedelta(days=1)).date().isoformat()
    cuenta, malas = {}, []
    for ide, nombre, muni in alava:
        try:
            d = json.loads(descarga(AIRE_DIA.replace("{ID}", ide).replace("{D}", ayer)))
            q = d[0]["station"][0].get("airQualityStation") or "Sin datos"
        except Exception:
            continue
        cuenta[q] = cuenta.get(q, 0) + 1
        if q.lower() in ("mejorable", "mala", "muy mala", "desfavorable", "muy desfavorable", "regular"):
            malas.append(f"{nombre} ({muni}): {q.lower()}")
    if not cuenta:
        return ""
    resumen = ", ".join(f"{n} {q.lower()}" for q, n in sorted(cuenta.items(), key=lambda x: -x[1]) if q != "Sin datos")
    return f"Ayer en {sum(cuenta.values())} estaciones de Álava: {resumen}." + (f" Ojo: {'; '.join(malas)}." if malas else "")


def recoge(descarga, ahora: datetime, previo: dict | None) -> dict:
    """descarga(url) -> bytes. previo: los datos vivos de la lectura anterior (para lo que va más despacio)."""
    previo = previo or {}
    vivos = {"actualizado": ahora.isoformat(timespec="seconds")}
    for clave, fn in (("avisos", lambda: _avisos(descarga)), ("trafico", lambda: _trafico(descarga, ahora))):
        try:
            vivos[clave] = fn()
        except Exception as e:
            vivos[clave] = previo.get(clave, [])
            print(f"  vivos/{clave}: {type(e).__name__}: {e}")
    # embalses (semanal) y aire (diario): cada 6 horas basta
    lento = previo.get("lento")
    if lento and ahora - datetime.fromisoformat(lento) < timedelta(hours=6):
        for k in ("embalses", "embalses_nota", "aire", "lento"):
            if k in previo:
                vivos[k] = previo[k]
    else:
        vivos["lento"] = ahora.isoformat(timespec="seconds")
        try:
            vivos["embalses"], vivos["embalses_nota"] = _embalses(descarga)
        except Exception as e:
            vivos["embalses"], vivos["embalses_nota"] = previo.get("embalses", []), previo.get("embalses_nota", "")
            print(f"  vivos/embalses: {type(e).__name__}: {e}")
        try:
            vivos["aire"] = _aire(descarga, ahora)
        except Exception as e:
            vivos["aire"] = previo.get("aire", "")
            print(f"  vivos/aire: {type(e).__name__}: {e}")
    print(f"OK   vivos: {len(vivos.get('avisos', []))} avisos, {len(vivos.get('trafico', []))} incidencias, "
          f"{len(vivos.get('embalses', []))} embalses, aire: {'sí' if vivos.get('aire') else 'no'}")
    return vivos
