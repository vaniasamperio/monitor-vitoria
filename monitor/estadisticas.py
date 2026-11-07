"""
Cifras oficiales de Álava que salen cada mes o cada trimestre, ya redactadas para contar.

- INE (API Tempus3, servicios.ine.es): IPC, EPA, hoteles, compraventa de viviendas, hipotecas, sociedades,
  nacimientos y viviendas turísticas. Series de Araba/Álava, con el dato de España cuando sirve para comparar.
- SEPE (datos abiertos): paro registrado y contratos por municipio (Álava y Vitoria-Gasteiz).

Eustat no se lee: su web pide a los programas automáticos que no la lean (robots.txt). Sus notas de prensa entran
si llegan al Gmail de la redacción.

recoge(descarga, ahora, previo) -> dict con "cifras" (lista) y la caché del SEPE. "visto" marca cuándo apareció
por primera vez el dato de cada periodo, para avisar de lo nuevo.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:                                    # pragma: no cover
    MADRID = timezone(timedelta(hours=1))

INE_SERIE = "https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{cod}?nult={n}"
INE_TABLA = "https://www.ine.es/jaxiT3/Tabla.htm?t={t}"
SEPE_CSV = "https://sede.sepe.gob.es/es/portaltrabaja/resources/sede/datos_abiertos/datos/{que}_por_municipios_{anyo}_csv.csv"
SEPE_WEB = "https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/datos-estadisticos/municipios.html"
VITORIA = "01059"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]

# id, tema, nombre, serie de Álava, frecuencia (M mensual, T trimestral, F fecha de referencia), tabla INE,
# series auxiliares
INE = [
    {"id": "ipc", "tema": "Precios", "nombre": "IPC", "serie": "IPC305743", "freq": "M", "tabla": 76143,
     "aux": {"mensual": "IPC305745", "espana": "IPC290750"}},
    {"id": "epa", "tema": "Empleo", "nombre": "Tasa de paro (EPA)", "serie": "EPA458948", "freq": "T", "tabla": 65349,
     "aux": {"espana": "EPA453100"}},
    {"id": "hoteles", "tema": "Turismo", "nombre": "Viajeros en hoteles", "serie": "EOT1787", "freq": "M", "tabla": 2074,
     "aux": {"pernoctaciones": "EOT1790", "ocupacion": "EOT399"}},
    {"id": "vivienda", "tema": "Vivienda", "nombre": "Compraventa de viviendas", "serie": "ETDP1526", "freq": "M", "tabla": 6150,
     "aux": {"nueva": "ETDP1525", "usada": "ETDP1524"}},
    {"id": "hipotecas", "tema": "Vivienda", "nombre": "Hipotecas sobre viviendas", "serie": "HPT34614", "freq": "M", "tabla": 76317,
     "aux": {"importe": "HPT34561"}},
    {"id": "vtur", "tema": "Vivienda", "nombre": "Viviendas turísticas", "serie": "VTE5", "freq": "F", "tabla": 39364,
     "aux": {"plazas": "VTE83"}},
    {"id": "sociedades", "tema": "Empresas", "nombre": "Sociedades mercantiles creadas", "serie": "SM24891", "freq": "M", "tabla": 6295},
    {"id": "nacimientos", "tema": "Población", "nombre": "Nacimientos", "serie": "EMN177", "freq": "M", "tabla": 46682,
     "aux": {"acumulado": "EMN176"}},
]


# ---------------------------------------------------------------- utilidades
def num(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, dec: int = 1, signo: bool = True) -> str:
    s = num(abs(x), dec) + " %"
    return (("+" if x > 0 else "−" if x < 0 else "") + s) if signo else s


def var(a: float, b: float | None) -> float | None:
    return (a - b) / b * 100 if b else None


def _periodo(p: dict, freq: str) -> tuple[int, int]:
    """(año, mes o trimestre) de un dato del INE."""
    fk, anyo = p.get("FK_Periodo"), p.get("Anyo")
    if freq == "M" and fk and 1 <= fk <= 12:
        return anyo, fk
    if freq == "T" and fk and 19 <= fk <= 22:
        return anyo, fk - 18
    f = datetime.fromtimestamp(p["Fecha"] / 1000, MADRID)
    return (f.year, (f.month - 1) // 3 + 1) if freq == "T" else (f.year, f.month)


def texto_periodo(anyo: int, k: int, freq: str) -> str:
    if freq == "T":
        return f"{['primer', 'segundo', 'tercer', 'cuarto'][k - 1]} trimestre de {anyo}"
    return f"{MESES[k - 1]} de {anyo}"


def _serie(descarga, cod: str, n: int, freq: str) -> dict:
    d = json.loads(descarga(INE_SERIE.format(cod=cod, n=n)))
    return {_periodo(p, freq): p["Valor"] for p in d.get("Data", []) if p.get("Valor") is not None and not p.get("Secreto")}


def _ultimo(serie: dict):
    k = max(serie)
    return k, serie[k]


def _hace_un_ano(serie: dict, k: tuple, freq: str):
    if freq == "F":                                     # el mismo mes del año anterior, o el más cercano
        cand = [x for x in serie if x[0] == k[0] - 1]
        return serie[min(cand, key=lambda x: abs(x[1] - k[1]))] if cand else None
    return serie.get((k[0] - 1, k[1]))


def _anterior(serie: dict, k: tuple):
    prev = [x for x in serie if x < k]
    return serie[max(prev)] if prev else None


def sube_baja(x: float | None, en_femenino: bool = False) -> str:
    if x is None:
        return ""
    if abs(x) < 0.05:
        return "igual que hace un año"
    if 97 <= x <= 103:
        return "el doble que hace un año"
    if -52 <= x <= -48:
        return "la mitad que hace un año"
    return f"un {pct(x, signo=False)} {'más' if x > 0 else 'menos'} que hace un año"


# ---------------------------------------------------------------- INE
def _ine(descarga, ind: dict) -> dict:
    f = ind["freq"]
    n = 14 if f == "M" else 6 if f == "T" else 4
    s = _serie(descarga, ind["serie"], n, f)
    k, v = _ultimo(s)
    aux = {}
    for nombre, cod in (ind.get("aux") or {}).items():
        try:
            aux[nombre] = _serie(descarga, cod, n, f)
        except Exception:
            aux[nombre] = {}
    # un dato que lleva meses sin actualizarse no se presenta como novedad
    hoy = datetime.now(MADRID)
    meses_atras = (hoy.year - k[0]) * 12 + hoy.month - (k[1] * 3 if f == "T" else k[1])
    if meses_atras > (9 if f == "T" else 6 if f == "M" else 18):
        raise ValueError(f"dato antiguo ({k})")
    per = texto_periodo(k[0], k[1], "M" if f == "F" else f)
    yoy = var(v, _hace_un_ano(s, k, f))
    i = ind["id"]
    det = ""
    if i == "ipc":
        es = aux["espana"].get(k)
        m = aux["mensual"].get(k)
        frase = (f"Los precios {'suben' if v > 0 else 'bajan'} un {pct(v, signo=False)} en Álava en un año "
                 f"(dato de {MESES[k[1] - 1]})")
        frase += f"; en España, {pct(es, signo=False)}." if es is not None else "."
        det = f"En el mes: {pct(m)}." if m is not None else ""
        valor = pct(v)
    elif i == "epa":
        es = aux["espana"].get(k)
        ant = _anterior(s, k)
        hace = _hace_un_ano(s, k, f)
        frase = f"La tasa de paro de la EPA en Álava es del {pct(v, 2, False)} en el {per}"
        if ant is not None:
            d = v - ant
            frase += f" ({'+' if d > 0 else '−' if d < 0 else ''}{num(abs(d), 2)} puntos sobre el trimestre anterior)"
        frase += f". España: {pct(es, 2, False)}." if es is not None else "."
        det = f"Hace un año: {pct(hace, 2, False)}." if hace is not None else ""
        valor = pct(v, 2, False)
    elif i == "hoteles":
        oc = aux["ocupacion"].get(k)
        pn = aux["pernoctaciones"].get(k)
        frase = f"Los hoteles de Álava recibieron {num(v)} viajeros en {per}" + (f", {sube_baja(yoy)}." if yoy is not None else ".")
        det = " · ".join(x for x in [f"{num(pn)} pernoctaciones" if pn else "",
                                     f"ocupación por plazas del {pct(oc, signo=False)}" if oc else ""] if x)
        valor = num(v)
    elif i == "vivienda":
        nu, us = aux["nueva"].get(k), aux["usada"].get(k)
        frase = f"Se vendieron {num(v)} viviendas en Álava en {per}" + (f", {sube_baja(yoy)}." if yoy is not None else ".")
        det = f"{num(nu)} nuevas y {num(us)} de segunda mano." if nu is not None and us is not None else ""
        valor = num(v)
    elif i == "hipotecas":
        imp = aux["importe"].get(k)
        frase = f"Se firmaron {num(v)} hipotecas sobre viviendas en Álava en {per}" + (f", {sube_baja(yoy)}." if yoy is not None else ".")
        det = f"Importe total: {num(imp / 1000, 1)} millones de euros; unos {num(round(imp / v) * 1000)} € de media." if imp and v else ""
        valor = num(v)
    elif i == "vtur":
        pl = aux["plazas"].get(k)
        frase = f"Álava tiene {num(v)} viviendas turísticas" + (f", {sube_baja(yoy)}" if yoy is not None else "") + \
                (f", con {num(pl)} plazas." if pl else ".")
        det = f"Dato de {per}."
        valor = num(v)
    elif i == "sociedades":
        frase = f"Se crearon {num(v)} sociedades mercantiles en Álava en {per}" + (f", {sube_baja(yoy)}." if yoy is not None else ".")
        valor = num(v)
    elif i == "nacimientos":
        ac = aux["acumulado"].get(k)
        frase = f"Nacieron {num(v)} bebés en Álava en {per}" + (f", {sube_baja(yoy)}." if yoy is not None else ".")
        det = f"En lo que va de año: {num(ac)}." if ac else ""
        valor = num(v)
    else:
        frase, valor = f"{ind['nombre']}: {num(v)} ({per}).", num(v)
    return {"id": i, "tema": ind["tema"], "nombre": ind["nombre"], "valor": valor, "periodo": per,
            "clave": f"{k[0]}-{k[1]:02d}", "frase": frase, "detalle": det,
            "variacion": round(yoy, 1) if yoy is not None else None,
            "fuente": "INE", "enlace": INE_TABLA.format(t=ind["tabla"])}


# ---------------------------------------------------------------- SEPE
def _entero(x: str) -> int:
    x = (x or "").strip()
    if x.startswith("<"):
        return 2                                         # "<5": el SEPE no da la cifra exacta
    try:
        return int(x.replace(".", ""))
    except ValueError:
        return 0


def _sepe_meses(contenido: bytes) -> dict:
    """{aaaamm: {"alava": n, "vitoria": n, "aprox": bool, "munis": {nombre: n}}} de las filas de Álava."""
    try:
        txt = contenido.decode("utf-8")
    except UnicodeDecodeError:
        txt = contenido.decode("cp1252", errors="replace")
    filas = list(csv.reader(io.StringIO(txt), delimiter=";"))
    out: dict = {}
    for f in filas[2:]:
        if len(f) < 9 or f[4].strip() not in ("1", "01"):
            continue
        mes, cod, muni, total = f[0].strip(), f[6].strip(), f[7].strip(), f[8].strip()
        d = out.setdefault(mes, {"alava": 0, "vitoria": None, "aprox": False, "munis": {}})
        n = _entero(total)
        d["alava"] += n
        d["aprox"] = d["aprox"] or total.startswith("<")
        d["munis"][muni] = n
        if cod == VITORIA:
            d["vitoria"] = n
    return out


def _sepe_indef(contenido: bytes) -> dict:
    """Contratos: {aaaamm: (total Álava, indefinidos Álava)}."""
    try:
        txt = contenido.decode("utf-8")
    except UnicodeDecodeError:
        txt = contenido.decode("cp1252", errors="replace")
    out: dict = {}
    for f in list(csv.reader(io.StringIO(txt), delimiter=";"))[2:]:
        if len(f) < 15 or f[4].strip() not in ("1", "01"):
            continue
        t, i = out.get(f[0].strip(), (0, 0))
        out[f[0].strip()] = (t + _entero(f[8]), i + sum(_entero(f[j]) for j in (9, 11, 12, 14)))
    return out


def _sepe(descarga, ahora: datetime, cache: dict) -> tuple[list[dict], dict]:
    anyo = ahora.year
    cache = dict(cache or {})
    paro = {k: v for k, v in (cache.get("paro") or {}).items()}
    contr = {k: tuple(v) for k, v in (cache.get("contratos") or {}).items()}
    for a in (anyo, anyo - 1):
        if a == anyo or not any(k.startswith(str(a)) for k in paro):        # el año anterior, una sola vez
            try:
                paro.update(_sepe_meses(descarga(SEPE_CSV.format(que="Paro", anyo=a))))
            except Exception as e:
                if a == anyo:
                    raise
                print(f"  estadísticas/sepe {a}: {type(e).__name__}")
        if a == anyo or not any(k.startswith(str(a)) for k in contr):
            try:
                contr.update(_sepe_indef(descarga(SEPE_CSV.format(que="Contratos", anyo=a))))
            except Exception as e:
                print(f"  estadísticas/sepe contratos {a}: {type(e).__name__}")
    # se guardan 14 meses
    meses = sorted(paro)[-14:]
    paro = {k: paro[k] for k in meses}
    contr = {k: contr[k] for k in sorted(contr)[-14:]}
    cifras = []
    if meses:
        k = meses[-1]
        d = paro[k]
        a, m = int(k[:4]), int(k[4:])
        per = f"{MESES[m - 1]} de {a}"
        ant = paro.get(meses[-2]) if len(meses) > 1 else None
        hace = paro.get(f"{a - 1}{m:02d}")
        frase = f"El paro registrado en Álava se sitúa en {num(d['alava'])} personas en {per}"
        partes = []
        if ant:
            dm = d["alava"] - ant["alava"]
            partes.append(f"{'+' if dm > 0 else '−' if dm < 0 else ''}{num(abs(dm))} en el mes")
        if hace:
            vy = var(d['alava'], hace['alava'])
            partes.append("igual que hace un año" if abs(vy) < 0.05 else f"{pct(vy)} en un año")
        frase += f" ({', '.join(partes)})." if partes else "."
        det = []
        if d.get("vitoria") is not None:
            v = f"Vitoria-Gasteiz: {num(d['vitoria'])}"
            if ant and ant.get("vitoria"):
                dv = d["vitoria"] - ant["vitoria"]
                v += f" ({'+' if dv > 0 else '−' if dv < 0 else ''}{num(abs(dv))} en el mes)"
            det.append(v)
        otros = sorted(((n, c) for n, c in d["munis"].items() if n.strip().lower() != "vitoria-gasteiz"), key=lambda x: -x[1])[:4]
        if otros:
            det.append("Después: " + ", ".join(f"{n} {num(c)}" for n, c in otros))
        if d.get("aprox"):
            det.append("El total de Álava suma los municipios; en los más pequeños el SEPE solo dice «menos de 5».")
        cifras.append({"id": "paro", "tema": "Empleo", "nombre": "Paro registrado", "valor": num(d["alava"]), "periodo": per,
                       "clave": k, "frase": frase, "detalle": ". ".join(det), "fuente": "SEPE", "enlace": SEPE_WEB,
                       "variacion": round(var(d["alava"], hace["alava"]), 1) if hace else None,
                       "municipios": {n: c for n, c in sorted(d["munis"].items(), key=lambda x: -x[1])}})
    if contr:
        k = sorted(contr)[-1]
        t, i = contr[k]
        a, m = int(k[:4]), int(k[4:])
        hace = contr.get(f"{a - 1}{m:02d}")
        frase = f"Se firmaron {num(t)} contratos de trabajo en Álava en {MESES[m - 1]} de {a}" + \
                (f", {sube_baja(var(t, hace[0]))}." if hace else ".")
        cifras.append({"id": "contratos", "tema": "Empleo", "nombre": "Contratos", "valor": num(t),
                       "periodo": f"{MESES[m - 1]} de {a}", "clave": k, "frase": frase,
                       "detalle": f"Indefinidos (iniciales y convertidos): {pct(i / t * 100, signo=False)}." if t else "",
                       "fuente": "SEPE", "enlace": SEPE_WEB, "variacion": round(var(t, hace[0]), 1) if hace else None})
    return cifras, {"paro": paro, "contratos": contr}


# ---------------------------------------------------------------- todo junto
ORDEN = ["paro", "contratos", "epa", "ipc", "vivienda", "hipotecas", "vtur", "hoteles", "sociedades", "nacimientos"]


def recoge(descarga, ahora: datetime, previo: dict | None, cada_horas: int = 6) -> dict:
    previo = previo or {}
    if previo.get("leido") and ahora - datetime.fromisoformat(previo["leido"]) < timedelta(hours=cada_horas):
        return previo
    ant = {c["id"]: c for c in previo.get("cifras", [])}
    cifras, fallos = [], []
    for ind in INE:
        try:
            cifras.append(_ine(descarga, ind))
        except ValueError as e:                        # dato caducado: fuera
            print(f"  estadísticas/{ind['id']}: {e}")
        except Exception as e:
            fallos.append(ind["id"])
            if ind["id"] in ant:
                cifras.append(ant[ind["id"]])
            print(f"  estadísticas/{ind['id']}: {type(e).__name__}: {str(e)[:120]}")
    cache = previo.get("sepe") or {}
    try:
        sepe, cache = _sepe(descarga, ahora, cache)
        cifras += sepe
    except Exception as e:
        fallos.append("sepe")
        cifras += [ant[k] for k in ("paro", "contratos") if k in ant]
        print(f"  estadísticas/sepe: {type(e).__name__}: {str(e)[:120]}")
    for c in cifras:                                   # cuándo apareció este dato por primera vez
        p = ant.get(c["id"])
        c["visto"] = p["visto"] if p and p.get("clave") == c["clave"] and p.get("visto") else ahora.isoformat(timespec="seconds")
        if not p:                                      # primera lectura: no es "nuevo"
            c["visto"] = "2000-01-01T00:00:00+00:00"
    cifras.sort(key=lambda c: ORDEN.index(c["id"]) if c["id"] in ORDEN else 99)
    print(f"OK   estadísticas: {len(cifras)} cifras" + (f" (fallan: {', '.join(fallos)})" if fallos else ""))
    return {"leido": ahora.isoformat(timespec="seconds"), "cifras": cifras, "sepe": cache}
