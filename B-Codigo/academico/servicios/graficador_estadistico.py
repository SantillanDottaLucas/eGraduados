def graficar_promedio(resultado, tipoGrafico):
    dato= {
        'etiquetas': ['promedio'], #Basicamente las "barras del gráfico". Para comparar Sistemas enfermeria, etc.
        'valores': resultado['promedio']  if resultado['promedio'] is not None else 0 #Por un valor invalido
    }
    return dato