
# academico/servicios/graficador_estadistico.py


def graficar_promedio(resultado):
    """
    Prepara los datos del promedio académico para el gráfico.

    La varianza se consulta por separado y se muestra en el HTML.
    """
    if not isinstance(resultado, dict):
        return {"etiquetas": [], "valores": []}

    promedio = resultado.get("promedio")

    return {
        "etiquetas": ["Promedio académico"] if promedio is not None else [],
        "valores": [float(promedio)] if promedio is not None else []
    }


def graficar_total(resultado):
    """
    Prepara los datos para el gráfico de cantidad de graduados.

    Según el filtro seleccionado:
    - Todos: cantidad de graduados por escuela.
    - Escuela: cantidad de graduados por carrera.
    - Carrera: total de graduados de esa carrera.
    """
    if not isinstance(resultado, dict):
        return {"etiquetas": [], "valores": []}

    etiquetas = resultado.get("etiquetas", [])
    valores = resultado.get("valores", [])

    return {
        "etiquetas": etiquetas,
        "valores": [
            int(valor) for valor in valores
            if valor is not None
        ]
    }


def graficar_tiempos(resultado):
    """
    Prepara los datos de duración de las carreras para el gráfico.

    Las etiquetas identifican cada registro y los valores representan
    los años transcurridos entre el ingreso y el egreso de la carrera.
    """
    if not isinstance(resultado, dict):
        return {"etiquetas": [], "valores": []}

    etiquetas = resultado.get("etiquetas", [])
    valores = resultado.get("valores", [])

    return {
        "etiquetas": etiquetas,
        "valores": [
            float(valor) if valor is not None else None
            for valor in valores
        ]
    }
