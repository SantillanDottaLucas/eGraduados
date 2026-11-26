import pandas as pd


def _primero(datos, clave):
    """Primer valor no nulo de una columna opcional."""

    if clave not in datos.columns:
        return ""

    serie = datos[clave].dropna()

    return serie.iloc[0] if not serie.empty else ""


def leer_excel(archivo):
    """
    Lector heredado de planillas de exámenes.

    El DNI no formaba parte de este formato: se expone vacío para
    que el flujo principal use siempre la identidad elegida por el
    usuario. El «legajo» se conserva como dato histórico.
    """

    datos = pd.read_excel(archivo)
    datos.columns = [
        str(columna).strip().lower()
        for columna in datos.columns
    ]

    materias = []

    for _, fila in datos.iterrows():
        tipo = str(fila.get("tipo", "") or "").strip()
        acta = fila.get("acta_final", "")

        if tipo == "Equivalencia":
            acta = fila.get("res_final", "")

        materias.append({
            "nombre_materia": fila.get("nombre_materia", ""),
            "fecha_regular": fila.get("fecha_regular", ""),
            "fecha_examen": fila.get("fecha_examen", ""),
            "codigo_materia": fila.get("materia", ""),
            "acta_respaldatoria": acta,
            "tipo": tipo,
        })

    return {
        "carrera": _primero(datos, "carrera"),
        "dni": _primero(datos, "dni"),
        "legajo": _primero(datos, "legajo"),
        "nombre_alumno": _primero(datos, "nombre_alumno"),
        "materias": materias,
    }
