from datetime import date

from django.shortcuts import render
from django.http import HttpResponse

from .models import Carrera, Escuela

from academico.servicios.moduloCarga.carga_datos import CargaDatos

from .servicios.moduloAnalitico import *

from .servicios.moduloEstadistica.consulta_estadisticas import (
    consultar_promedios,
    consultar_total,
    consultar_tiempos,
)

from .servicios.moduloEstadistica.graficador_estadistico import (
    graficar_promedio,
    graficar_total,
    graficar_tiempos,
)

from .servicios.moduloGraduados.consulta_graduados import (
    obtener_graduados_filtrados,
)

from .servicios.moduloGraduados.exportar_graduados import (
    generar_excel_graduados,
)


# ==========================================
# 1. PÁGINAS PRINCIPALES
# ==========================================

def index(request):
    return render(request, "academico/index.html")


def generacion_analiticos(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "")
        apellido = request.POST.get("apellido", "")
        legajo = request.POST.get("legajo", "")
        archivo_notas = request.FILES.get("archivo_notas")

        # Pendiente: implementar la generación del analítico.

    return render(request, "academico/generacion_analiticos.html")


def titulo_en_tramite(request):
    return render(request, "academico/titulo_en_tramite.html")


# ==========================================
# 2. CONTEXTO COMPARTIDO
# ==========================================

def obtener_contexto_base():
    """
    Obtiene las carreras, escuelas y la fecha actual.
    Carrera referencia a Escuela mediante id_escuela.
    """
    carreras = Carrera.objects.all().order_by("nombre_carrera")
    escuelas = Escuela.objects.all().order_by("nombre_escuela")

    return {
        "carreras": carreras,
        "escuelas": escuelas,
        "fechaFin": date.today(),
    }


# ==========================================
# 3. ESTADÍSTICAS
# ==========================================

def estadisticas(request):
    contexto = obtener_contexto_base()

    # Valores iniciales: todas las carreras, todas las escuelas
    # y sin restricción de fechas.
    filtro = "todos"
    carrera = None
    escuela = None
    fecha_inicio = None
    fecha_fin = None

    # Consultar las tres estadísticas.
    resultado_promedios = consultar_promedios(
        "promedio_sin_aplazo",
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    resultado_total = consultar_total(
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    resultado_tiempos = consultar_tiempos(
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    # Preparar los datos para Chart.js.
    contexto.update({
        "datos_promedios": graficar_promedio(resultado_promedios),
        "datos_totales": graficar_total(resultado_total),
        "datos_tiempos": graficar_tiempos(resultado_tiempos),
    })

    return render(
        request,
        "academico/estadisticas.html",
        contexto,
    )


def estadisticas_promedios(request):
    tipo_promedio = request.GET.get(
        "promedio",
        "promedio_sin_aplazo",
    )
    filtro = request.GET.get("filtro", "todos")
    carrera = request.GET.get("carrera") or None
    escuela = request.GET.get("escuela") or None
    fecha_inicio = request.GET.get("fechaInicio") or None
    fecha_fin = request.GET.get("fechaFin") or None

    resultado = consultar_promedios(
        tipo_promedio,
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_promedio": resultado["promedio"],
        "varianza_promedios": resultado["varianza"],
        "datos_promedios": graficar_promedio(resultado),
    })

    return render(
        request,
        "academico/estadisticas.html",
        contexto,
    )


def estadisticas_totales(request):
    filtro = request.GET.get("filtro", "todos")
    carrera = request.GET.get("carrera") or None
    escuela = request.GET.get("escuela") or None
    fecha_inicio = request.GET.get("fechaInicio") or None
    fecha_fin = request.GET.get("fechaFin") or None

    resultado_total = consultar_total(
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_total": resultado_total,
        "datos_totales": graficar_total(resultado_total),
    })

    return render(
        request,
        "academico/estadisticas.html",
        contexto,
    )


def estadisticas_tiempos(request):
    filtro = request.GET.get("filtro", "todos")
    carrera = request.GET.get("carrera") or None
    escuela = request.GET.get("escuela") or None
    fecha_inicio = request.GET.get("fechaInicio") or None
    fecha_fin = request.GET.get("fechaFin") or None

    resultado_tiempo = consultar_tiempos(
        filtro,
        carrera,
        escuela,
        fecha_inicio,
        fecha_fin,
    )

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_tiempo": resultado_tiempo,
        "datos_tiempos": graficar_tiempos(resultado_tiempo),
    })

    return render(
        request,
        "academico/estadisticas.html",
        contexto,
    )


# ==========================================
# 4. LISTADO DE GRADUADOS
# ==========================================

def lista_graduados(request):
    graduados = obtener_graduados_filtrados(request.GET)

    contexto = obtener_contexto_base()
    contexto["graduados"] = graduados

    return render(
        request,
        "academico/lista_graduados.html",
        contexto,
    )


# ==========================================
# 5. EXPORTACIÓN A EXCEL
# ==========================================

def exportar_graduados(request):
    graduados = obtener_graduados_filtrados(request.GET)

    contenido = generar_excel_graduados(graduados)

    respuesta = HttpResponse(
        contenido,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="graduados.xlsx"'
    )

    return respuesta

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def cargar_datos(request):

    if request.method == "GET":
        return render(
            request,
            "academico/cargar_datos.html"
        )

    archivo = request.FILES.get("archivo_excel")

    if not archivo:
        return JsonResponse(
            {
                "exito": False,
                "mensaje": "No se recibió ningún archivo."
            },
            status=400
        )

    extension = archivo.name.rsplit(".", 1)[-1].lower()

    if "." not in archivo.name or extension not in ["xlsx", "xls"]:
        return JsonResponse(
            {
                "exito": False,
                "mensaje": "El archivo debe tener formato .xlsx o .xls."
            },
            status=400
        )

    try:
        resultado = CargaDatos.cargar_excel(archivo)

        return JsonResponse({
            "exito": True,
            "mensaje": (
                f"Carga completada. "
                f"Filas procesadas: {resultado['filas_procesadas']}. "
                f"Graduados nuevos: {resultado['graduados_nuevos']}. "
                f"Graduados actualizados: "
                f"{resultado['graduados_actualizados']}."
            ),
            "resultado": resultado,
        })

    except ValueError as error:
        return JsonResponse({
            "exito": False,
            "mensaje": str(error),
        }, status=400)
