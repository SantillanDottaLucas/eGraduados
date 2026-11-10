"""
Lector del «Certificado Lincoln» (exportación de notas en
formato .xls de Excel 2003 o .xlsx moderno).

Formato esperado (encabezado en la primera fila): una fila por
asignatura cursada, con campos como «nombre_materia», «tipo»,
«nota_final», «descr_final», «acta_final», «fecha_examen»,
«materia» (código numérico), «nro_inscripcion» (legajo) y
«nombre_alumno».

Sólo se toman los registros cuyo «tipo» empieza con «final»
(Final / Final Libre / Equivalencia), porque el analítico lista
exámenes finales (incluidas las desaprobaciones/recursadas).
"""

import re
import unicodedata
from datetime import date

import pandas as pd


COLUMNAS_REQUERIDAS = (
    "nombre_materia",
    "tipo",
    "nota_final",
    "acta_final",
    "fecha_examen",
    "materia",
    "nro_inscripcion",
)

TIPOS_FINALES = ("final", "equivalencia")


class ErrorLincoln(ValueError):
    """El archivo no es un certificado Lincoln válido."""


def _normalizar_texto(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip()


def _normalizar_codigo(valor):
    texto = _normalizar_texto(valor)

    if not texto:
        return ""

    # Lincoln guarda «1672» en vez de «1672» o «01672»;
    # se compara como entero cuando es posible.
    try:
        return str(int(float(texto)))
    except ValueError:
        return texto


def _parsear_fecha(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None

    fecha = pd.to_datetime(str(valor).strip(), format="%d/%m/%Y",
                           errors="coerce", dayfirst=True)

    if pd.isna(fecha):
        fecha = pd.to_datetime(str(valor).strip(), errors="coerce",
                               dayfirst=True)

    if pd.isna(fecha):
        return None

    return fecha.date()


def _parsear_nota(valor):
    try:
        numero = float(str(valor).strip())
    except (TypeError, ValueError):
        return None

    if pd.isna(numero):
        return None

    return int(numero)


def leer_lincoln(archivo):
    """
    Lee el certificado Lincoln y devuelve un dict con:

    {
        "legajo": str,
        "alumno": str,
        "carrera": str,
        "total_registros": int,
        "examenes": [
            {
                "codigo_materia": str,
                "nombre_materia": str,
                "fecha_examen": date | None,
                "nota": int,
                "acta_respaldatoria": str,
                "tipo": str,
                "anio_cursado": int | None,
            },
            ...
        ],
        "descartados": [texto, ...],
    }
    """

    nombre = getattr(archivo, "name", str(archivo)).lower()

    if nombre.endswith(".xls"):
        datos = pd.read_excel(archivo, engine="xlrd")

    elif nombre.endswith(".xlsx"):
        datos = pd.read_excel(archivo, engine="openpyxl")

    else:
        raise ErrorLincoln(
            "Formato no admitido. Se esperaba un archivo .xls o .xlsx."
        )

    if datos.empty:
        raise ErrorLincoln("El archivo no contiene registros.")

    datos.columns = [
        _normalizar_texto(columna).lower()
        for columna in datos.columns
    ]

    faltantes = [
        columna for columna in COLUMNAS_REQUERIDAS
        if columna not in datos.columns
    ]

    if faltantes:
        raise ErrorLincoln(
            "No parece un certificado Lincoln: faltan las columnas "
            + ", ".join(faltantes)
            + "."
        )

    legajo = _normalizar_texto(datos["nro_inscripcion"].dropna().iloc[0]) \
        if not datos["nro_inscripcion"].dropna().empty else ""

    alumno = _normalizar_texto(datos["nombre_alumno"].dropna().iloc[0]) \
        if not datos["nombre_alumno"].dropna().empty else ""

    carrera = _normalizar_texto(datos["carrera"].dropna().iloc[0]) \
        if not datos["carrera"].dropna().empty else ""

    examenes = []
    descartados = []

    for _, fila in datos.iterrows():
        tipo = _normalizar_texto(fila["tipo"]).lower()

        if not any(tipo.startswith(prefijo) for prefijo in TIPOS_FINALES):
            # Los parciales de cursado no se listan en el analítico.
            continue

        es_equivalencia = tipo.startswith("equivalencia")

        nombre_materia = _normalizar_texto(fila["nombre_materia"])
        codigo = _normalizar_codigo(fila["materia"])
        nota = _parsear_nota(fila["nota_final"])
        acta = _normalizar_texto(fila["acta_final"])
        res_final = _normalizar_texto(fila.get("res_final"))
        fecha = _parsear_fecha(fila["fecha_examen"])

        if es_equivalencia:
            # Las equivalencias respaldan con la resolución
            # (res_final), no con la acta del examen.
            acta = res_final if res_final else "EQUIVALENCIA"

        if not nombre_materia:
            # Sin materia no se puede ubicar en el plan.
            descartados.append(f"Fila {_ + 2} (sin materia)")
            continue

        try:
            anio_cursado = int(float(fila["ano_curs"])) \
                if not pd.isna(fila.get("ano_curs", None)) else None
        except (TypeError, ValueError):
            anio_cursado = None

        examenes.append({
            "codigo_materia": codigo,
            "nombre_materia": nombre_materia,
            "fecha_examen": fecha,
            "nota": nota,
            "acta_respaldatoria": acta,
            "tipo": _normalizar_texto(fila["tipo"]),
            "anio_cursado": anio_cursado,
        })

    return {
        "legajo": legajo,
        "alumno": alumno,
        "carrera": carrera,
        "total_registros": len(datos),
        "examenes": examenes,
        "descartados": descartados,
    }


def matcheo_materia(examen, materias):
    """
    Asocia un registro Lincoln a la materia del plan.
    Devuelve el objeto Materia o None.
    """

    if not materias:
        return None

    codigo = examen.get("codigo_materia") or ""

    if codigo:
        for materia in materias:
            if _normalizar_codigo(materia.codigo_materia) == codigo:
                return materia

    objetivo = _normalizar_texto(examen["nombre_materia"]).lower()

    for materia in materias:
        if _normalizar_texto(materia.nombre_materia).lower() == objetivo:
            return materia

    # Contención de texto como último recurso.
    for materia in materias:
        nombre = _normalizar_texto(materia.nombre_materia).lower()

        if objetivo and (objetivo in nombre or nombre in objetivo):
            return materia

    return None
