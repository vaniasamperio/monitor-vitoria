"""
Calendario: saca fechas futuras de los textos (eventos, plazos, fin de obras,
inicios previstos...), interpreta las convocatorias de prensa y añade las
efemérides de efemerides.yaml.

Todo se hace con reglas (sin IA), así que puede haber algún falso positivo:
cada entrada lleva la frase original para que el periodista la valore.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
RX_MES = "|".join(MESES)
DIA_SEM = r"(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)"

RX_RANGO = re.compile(
    rf"\b(?:del|desde el|entre el)\s+(?:{DIA_SEM},?\s+)?(\d{{1,2}})(?:\s+de\s+({RX_MES}))?"
    rf"\s+(?:al|y el|hasta el)\s+(?:{DIA_SEM},?\s+)?(\d{{1,2}})\s+de\s+({RX_MES})(?:\s+(?:de|del)\s+(20\d\d))?", re.I)
RX_FECHA = re.compile(
    rf"\b(?:{DIA_SEM},?\s+)?(\d{{1,2}})\s+de\s+({RX_MES})(?:\s+(?:de|del)\s+(1\d\d\d|20\d\d))?\b", re.I)
RX_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b")
RX_HORA = re.compile(r"\b(?:a las\s+)?(\d{1,2})[:.](\d{2})\s*(?:h|horas)?\b", re.I)

# Tipos, de más a menos específico. Palabras sin tildes y en minúscula.
TIPOS = [
    ("efemeride", "Efeméride", ["aniversario", "centenario", "se cumplen", "cumple", "efemeride", "conmemora"]),
    ("obras", "Obras · seguimiento", ["obra", "termin", "finaliz", "conclu", "cortad", "cerrad", "cerrar",
                                      "corte de", "trafico", "desvio", "reabr", "reapertura", "urbaniz", "reforma"]),
    ("plazo", "Plazo", ["plazo", "solicitud", "inscrip", "matricul", "alegacion", "presentar", "convocatoria",
                        "bases", "ayudas", "subvencion"]),
    ("movilizacion", "Movilización", ["huelga", "paro", "concentracion", "manifestacion", "movilizacion", "protesta"]),
    ("previsto", "Previsto", ["comenz", "empez", "arranc", "inici", "entrara en vigor", "a partir del",
                              "abrira", "pondra en marcha", "previsto", "preve", "estara listo", "licita"]),
    ("evento", "Evento", ["presenta", "jornada", "congreso", "concierto", "festival", "exposicion", "charla",
                          "conferencia", "feria", "fiesta", "acto", "homenaje", "taller", "encuentro",
                          "inaugura", "estreno", "mercado", "carrera", "pleno", "comision", "visita",
                          "semana", "dia mundial", "dia internacional", "celebra", "cita", "programa"]),
]
SEGUIMIENTO = {"plazo", "obras", "previsto"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _frases(texto: str) -> list[str]:
    trozos = re.split(r"(?<=[.;:!?])\s+|\n+", texto)
    return [t.strip() for t in trozos if len(t.strip()) > 12]


def _tipo(frase: str) -> str:
    n = _norm(frase)
    for clave, _, palabras in TIPOS:
        if any(p in n for p in palabras):
            return clave
    return "fecha"


def _fecha(dia: int, mes: int, año: int | None, base: date) -> date | None:
    try:
        if año:
            return date(año, mes, dia)
        f = date(base.year, mes, dia)
        if f < base - timedelta(days=45):     # "el 15 de enero" escrito en diciembre
            f = date(base.year + 1, mes, dia)
        return f
    except ValueError:
        return None


def _id(*p) -> str:
    return hashlib.sha1("|".join(map(str, p)).encode()).hexdigest()[:14]


def extrae(item: dict, texto: str, base: date, max_fechas: int = 4) -> list[dict]:
    """Fechas futuras citadas en el texto de una noticia."""
    eventos, vistos = [], set()
    limite = base + timedelta(days=540)
    for frase in _frases(texto):
        if len(eventos) >= max_fechas:
            break
        encontrados = []
        for m in RX_RANGO.finditer(frase):
            d1, m1, d2, m2, a = m.groups()
            mes2 = MESES[m2.lower()]
            mes1 = MESES[m1.lower()] if m1 else mes2
            f1 = _fecha(int(d1), mes1, int(a) if a else None, base)
            f2 = _fecha(int(d2), mes2, int(a) if a else None, base)
            if f1 and f2 and f2 >= f1:
                encontrados.append((f1, f2, m.span()))
        ocupados = [s for *_, s in encontrados]
        for m in RX_FECHA.finditer(frase):
            if any(a <= m.start() < b for a, b in ocupados):
                continue
            d, mes, a = m.groups()
            año = int(a) if a else None
            if año and año < base.year - 1:
                # fecha histórica: solo interesa si se habla de un aniversario
                if _tipo(frase) == "efemeride":
                    f = _fecha(int(d), MESES[mes.lower()], None, base)
                    if f:
                        encontrados.append((f, None, m.span(), f.year - año))
                continue
            f = _fecha(int(d), MESES[mes.lower()], año, base)
            if f:
                encontrados.append((f, None, m.span()))
        for e in encontrados:
            f1, f2, span = e[0], e[1], e[2]
            if f1 < base or f1 > limite:
                continue
            tipo = _tipo(frase)
            if f1 in vistos:          # una entrada por día y noticia
                continue
            vistos.add(f1)
            hora = None
            h = RX_HORA.search(frase[span[1]:span[1] + 40])
            if h and 6 <= int(h.group(1)) <= 23:
                hora = f"{int(h.group(1)):02d}:{h.group(2)}"
            ev = {"id": _id(item["id"], f1, tipo), "fecha": f1.isoformat(), "hasta": f2.isoformat() if f2 else None,
                  "hora": hora, "tipo": tipo, "titulo": item["titulo"], "frase": frase[:260],
                  "enlace": item["enlace"], "fuente": item["fuente"], "origen": item["id"],
                  "seguimiento": tipo in SEGUIMIENTO}
            if len(e) > 3:
                ev["años"] = e[3]
            eventos.append(ev)
    return eventos


def convocatorias(item: dict, texto: str, base: date) -> list[dict]:
    """Convocatorias de prensa del Ayuntamiento: Título / Participan / Día / Hora / Lugar."""
    out, actual = [], None
    for linea in [l.strip(" •\t") for l in texto.split("\n")]:
        if not linea:
            continue
        n = _norm(linea)
        if n.startswith(("dia:", "eguna:")):
            if actual:
                m = RX_FECHA.search(linea)
                if m:
                    actual["fecha"] = _fecha(int(m.group(1)), MESES[m.group(2).lower()],
                                             int(m.group(3)) if m.group(3) else None, base)
        elif n.startswith(("hora:", "ordua:")):
            if actual:
                h = RX_HORA.search(linea)
                actual["hora"] = f"{int(h.group(1)):02d}:{h.group(2)}" if h else None
        elif n.startswith(("lugar:", "tokia:")):
            if actual:
                actual["lugar"] = linea.split(":", 1)[1].strip()
        elif n.startswith(("participa", "asisten", "intervienen")):
            if actual:
                actual["quien"] = linea.split(":", 1)[-1].strip()
        elif not n.startswith(("recuerda", "os esperamos", "la agenda")) and len(linea) > 12:
            if actual and actual.get("fecha"):
                out.append(actual)
            actual = {"titulo": linea.rstrip(".")}
    if actual and actual.get("fecha"):
        out.append(actual)
    eventos = []
    for c in out:
        frase = " · ".join(x for x in [c.get("quien") and f"Participan: {c['quien']}", c.get("lugar")] if x)
        eventos.append({"id": _id(item["id"], c["titulo"], c["fecha"]), "fecha": c["fecha"].isoformat(), "hasta": None,
                        "hora": c.get("hora"), "tipo": "convocatoria", "titulo": c["titulo"], "frase": frase,
                        "lugar": c.get("lugar"), "enlace": item["enlace"], "fuente": item["fuente"],
                        "origen": item["id"], "seguimiento": False})
    return eventos


def de_agenda(item: dict, base: date) -> list[dict]:
    """Elementos de agendas (plenos, comisiones, actividades): su fecha es la del acto."""
    texto = item.get("resumen", "")
    m = RX_NUM.findall(texto)
    hora, hasta = None, None
    if m:
        try:
            f1 = date(int(m[0][2]), int(m[0][1]), int(m[0][0]))
            if len(m) > 1:
                hasta = date(int(m[1][2]), int(m[1][1]), int(m[1][0]))
        except ValueError:
            return []
    elif item.get("fecha"):
        dt = datetime.fromisoformat(item["fecha"]).astimezone(MADRID)
        f1 = dt.date()
        if dt.strftime("%H:%M") != "00:00":
            hora = dt.strftime("%H:%M")
    else:
        return []
    if (hasta or f1) < base:
        return []
    return [{"id": _id(item["id"], f1), "fecha": f1.isoformat(),
             "hasta": hasta.isoformat() if hasta and hasta != f1 else None,
             "hora": hora, "tipo": "agenda", "titulo": item["titulo"], "frase": "", "enlace": item["enlace"],
             "fuente": item["fuente"], "origen": item["id"], "seguimiento": False}]


def efemerides(cfg: dict, desde: date, hasta: date) -> list[dict]:
    out = []
    for año in range(desde.year, hasta.year + 1):
        for e in cfg.get("fijas", []) or []:
            mes, dia = map(int, e["fecha"].split("-"))
            try:
                f = date(año, mes, dia)
            except ValueError:
                continue
            if desde <= f <= hasta:
                out.append({"id": _id("fija", f, e["texto"]), "fecha": f.isoformat(), "hasta": None, "hora": None,
                            "tipo": "dia", "titulo": e["texto"], "frase": "", "enlace": e.get("enlace", ""),
                            "fuente": "efemerides", "origen": None, "seguimiento": False, "categoria": "efemerides"})
        for e in cfg.get("aniversarios", []) or []:
            mes, dia = map(int, e["fecha"].split("-"))
            try:
                f = date(año, mes, dia)
            except ValueError:
                continue
            n = año - int(e["año"])
            if desde <= f <= hasta and n > 0:
                redondo = n % 25 == 0 or (n < 100 and n % 10 == 0)
                out.append({"id": _id("aniv", f, e["texto"]), "fecha": f.isoformat(), "hasta": None, "hora": None,
                            "tipo": "efemeride", "titulo": f"{n} años: {e['texto']} ({e['año']})", "frase": "",
                            "enlace": e.get("enlace", ""), "fuente": "efemerides", "origen": None, "categoria": "efemerides",
                            "seguimiento": False, "años": n, "redondo": redondo})
    return out


ETIQUETAS = {clave: etiqueta for clave, etiqueta, _ in TIPOS}
ETIQUETAS.update({"fecha": "Fecha citada", "convocatoria": "Convocatoria de prensa", "agenda": "Agenda",
                  "dia": "Día señalado"})
