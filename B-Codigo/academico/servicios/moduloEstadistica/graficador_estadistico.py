# academico/servicios/graficador_estadistico.py

def graficar_promedio(resultado):
    """
    Prepara los datos para representar el promedio académico.
    La varianza se muestra como estadístico separado en el HTML.
    """
    promedio = resultado.get("promedio")

    return {
        "etiquetas": ["Promedio académico"] if promedio is not None else [],
        "valores": [float(promedio)] if promedio is not None else []
    }


def graficar_total(resultado):
    """
    Prepara los datos de cantidad de graduados.
    Las etiquetas y los valores dependen del filtro seleccionado:
    - Todos: cantidad por escuela.
    - Escuela: cantidad por carrera.
    - Carrera: total de graduados de esa carrera.
    """
    if not isinstance(resultado, dict):
        return {"etiquetas": [], "valores": []}

    etiquetas = resultado.get("etiquetas", [])
    valores = resultado.get("valores", [])

    return {
        "etiquetas": etiquetas,
        "valores": [int(valor) for valor in valores]
    }


def graficar_tiempos(resultado):
    """
    Prepara los datos de tiempo de graduación.

    La consulta debe devolver las claves 'etiquetas' y 'valores'.
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