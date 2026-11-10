
# academico/servicios/graficador_estadistico.py
#
# Prepara los datos de cada estadística para los gráficos
# de Chart.js (formato etiquetas / valores).


def _limpiar(resultado):
    """Devuelve (etiquetas, valores) de un resultado."""

    if not isinstance(resultado, dict):
        return [], []

    return (
        resultado.get("etiquetas") or [],
        resultado.get("valores") or [],
    )


def graficar_promedio(resultado):
    """
    Prepara los datos del promedio académico para el gráfico.

    Según el filtro, muestra el promedio por escuela, por
    carrera o el promedio de una única carrera. La varianza
    se consulta por separado y se muestra en el HTML.
    """

    etiquetas, valores = _limpiar(resultado)

    return {
        "etiquetas": etiquetas,
        "valores": [
            round(float(valor), 2) if valor is not None else None
            for valor in valores
        ],
    }


def graficar_total(resultado):
    """
    Prepara los datos para el gráfico de cantidad de graduados.

    Según el filtro seleccionado:
    - Todos: cantidad de graduados por escuela.
    - Escuela: cantidad de graduados por carrera.
    - Carrera: total de graduados de esa carrera.
    """

    etiquetas, valores = _limpiar(resultado)

    return {
        "etiquetas": etiquetas,
        "valores": [
            int(valor) for valor in valores
            if valor is not None
        ],
    }


def graficar_tiempos(resultado):
    """
    Prepara los datos de duración de las carreras para el gráfico.

    Las etiquetas identifican cada registro y los valores representan
    los años transcurridos entre el ingreso y el egreso de la carrera.
    """

    etiquetas, valores = _limpiar(resultado)

    return {
        "etiquetas": etiquetas,
        "valores": [
            float(valor) if valor is not None else None
            for valor in valores
        ],
    }


def graficar_graduados_por_anio(resultado):
    """
    Prepara los datos de graduados por año de egreso.

    Las etiquetas son los años y los valores la cantidad de
    graduados que egresaron en cada uno.
    """

    etiquetas, valores = _limpiar(resultado)

    return {
        "etiquetas": etiquetas,
        "valores": [
            int(valor) for valor in valores
            if valor is not None
        ],
    }
