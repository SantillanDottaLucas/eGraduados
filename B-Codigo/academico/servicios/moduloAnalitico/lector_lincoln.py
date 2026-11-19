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


# Sólo se exigen las columnas imprescindibles para identificar una
# fila. El resto se lee si está presente; si falta, queda vacío y la
# previsualización lo muestra en el panel de datos faltantes.
COLUMNAS_REQUERIDAS = ("nombre_materia", "tipo")

# El Lincoln real no siempre usa los mismos encabezados (por ejemplo
# «acta_final» vs. «acta_respaldatoria»). Se aceptan alias.
ALIAS_COLUMNAS = {
    "nombre_materia": (
        "nombre_materia",
        "materia_nombre",
        "espacio_curricular",
        "asignatura",
    ),
    "tipo": ("tipo", "tipo_examen"),
    "nota_final": ("nota_final", "nota", "nota_examen"),
    "acta_final": (
        "acta_final",
        "acta_respaldatoria",
        "acta",
    ),
    "fecha_examen": ("fecha_examen", "fecha"),
    "materia": ("materia", "codigo_materia", "cod_materia"),
    "nro_inscripcion": (
        "nro_inscripcion",
        "legajo",
        "nro_legajo",
    ),
    "nombre_alumno": ("nombre_alumno", "alumno"),
    "carrera": ("carrera", "nombre_carrera"),
    "res_final": ("res_final", "resolucion_final"),
    "ano_curs": ("ano_curs", "anio_cursado", "año_curs"),
}

TIPOS_FINALES = ("final", "equivalencia")


def _columna(datos, clave):
    """Devuelve la primera columna disponible para una clave."""

    for alias in ALIAS_COLUMNAS.get(clave, (clave,)):
        if alias in datos.columns:
            return datos[alias]

    return None


def _valor_fila(fila, clave):
    """Devuelve el valor de la primera columna disponible en la fila."""

    for alias in ALIAS_COLUMNAS.get(clave, (clave,)):
        if alias in fila.index:
            return fila[alias]

    return None


def _primer_valor(serie):
    """Primer valor no nulo de una columna, como texto limpio."""

    if serie is None:
        return ""

    limpia = serie.dropna()

    return _normalizar_texto(limpia.iloc[0]) if not limpia.empty else ""


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
        clave for clave in COLUMNAS_REQUERIDAS
        if _columna(datos, clave) is None
    ]

    if faltantes:
        raise ErrorLincoln(
            "No parece un certificado Lincoln: faltan las columnas "
            + ", ".join(faltantes)
            + "."
        )

    legajo = _primer_valor(_columna(datos, "nro_inscripcion"))
    alumno = _primer_valor(_columna(datos, "nombre_alumno"))
    carrera = _primer_valor(_columna(datos, "carrera"))

    examenes = []
    descartados = []

    for _, fila in datos.iterrows():
        tipo = _normalizar_texto(_valor_fila(fila, "tipo")).lower()

        if not any(tipo.startswith(prefijo) for prefijo in TIPOS_FINALES):
            # Los parciales de cursado no se listan en el analítico.
            continue

        es_equivalencia = tipo.startswith("equivalencia")

        nombre_materia = _normalizar_texto(
            _valor_fila(fila, "nombre_materia")
        )
        codigo = _normalizar_codigo(_valor_fila(fila, "materia"))
        nota = _parsear_nota(_valor_fila(fila, "nota_final"))
        acta = _normalizar_texto(_valor_fila(fila, "acta_final"))
        res_final = _normalizar_texto(_valor_fila(fila, "res_final"))
        fecha = _parsear_fecha(_valor_fila(fila, "fecha_examen"))

        if es_equivalencia:
            # Las equivalencias respaldan con la resolución
            # (res_final), no con la acta del examen.
            acta = res_final if res_final else "EQUIVALENCIA"

        if not nombre_materia:
            # Sin nombre no se puede identificar la asignatura.
            descartados.append(f"Fila {_ + 2} (sin materia)")
            continue

        anio_valor = _valor_fila(fila, "ano_curs")

        try:
            anio_cursado = (
                int(float(anio_valor))
                if anio_valor is not None and not pd.isna(anio_valor)
                else None
            )
        except (TypeError, ValueError):
            anio_cursado = None

        examenes.append({
            "codigo_materia": codigo,
            "nombre_materia": nombre_materia,
            "fecha_examen": fecha,
            "nota": nota,
            "acta_respaldatoria": acta,
            "tipo": (
                "Equivalencia"
                if es_equivalencia
                else _normalizar_texto(_valor_fila(fila, "tipo"))
            ),
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
    Asocia un registro Lincoln a una materia del catálogo.
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
