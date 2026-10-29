from django.shortcuts import render
from .servicios.moduloAnalitico import *
from .servicios.moduloEstadistica.consulta_estadisticas import *
from .servicios.moduloEstadistica.graficador_estadistico import *
from .models import Graduado, Carrera
from datetime import date
from django.http import HttpResponse
from academico.servicios.moduloGraduados.consulta_graduados import (
    obtener_graduados_filtrados
)
from academico.servicios.moduloGraduados.exportar_graduados import (
    generar_csv_graduados
)




# Create your views here.
#Redirigir al index
def index(request):
    return render(request,"academico/index.html")

#Generar un analítico si el método es POST. Si es un GET, reenvia al html generacion_titulos
def generacion_analiticos(request):

    if request.method == 'POST': #SI EL REQUEST ES UN POST, GENERA EL ANALÍTICO

        nombre = request.POST['nombre']
        apellido = request.POST['apellido']
        legajo = request.POST['legajo']

        archivo_notas = request.FILES['archivo_notas']

        # Más adelante:
        # analitico = generar_analitico(...)

    return render(
        request,
        'academico/generacion_analiticos.html'
    )

def titulo_en_tramite(request):
    return render(request, 'academico/titulo_en_tramite.html')

#Redirige a estadísticas
def estadisticas(request):
    contexto = obtener_contexto_base()

    return render(
        request,
        "academico/estadisticas.html",
        contexto
    )

def estadisticas_promedios(request):
    tipo_promedio = request.GET.get("promedio")
    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fecha_inicio = request.GET.get("fechaInicio")
    fecha_fin = request.GET.get("fechaFin")

    resultado = consultar_promedios(
        tipo_promedio, filtro, carrera, escuela,fecha_inicio, fecha_fin
    )

    datos_promedios = graficar_promedio(resultado)

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_promedio": resultado["promedio"],
        "varianza_promedios": resultado["varianza"],
        "datos_promedios": datos_promedios,
    })

    return render(request, "academico/estadisticas.html", contexto)

def estadisticas_totales(request):
    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fecha_inicio = request.GET.get("fechaInicio")
    fecha_fin = request.GET.get("fechaFin")

    resultado_total = consultar_total(
        filtro, carrera, escuela, fecha_inicio, fecha_fin
    )

    datos_totales = graficar_total(resultado_total)

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_total": resultado_total,
        "datos_totales": datos_totales,
    })

    return render(request, "academico/estadisticas.html", contexto)

def estadisticas_tiempos(request):
    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fecha_inicio = request.GET.get("fechaInicio")
    fecha_fin = request.GET.get("fechaFin")

    resultado_tiempo = consultar_tiempos(
        filtro, carrera, escuela, fecha_inicio, fecha_fin
    )

    datos_tiempos = graficar_tiempos(resultado_tiempo)

    contexto = obtener_contexto_base()
    contexto.update({
        "resultado_tiempo": resultado_tiempo,
        "datos_tiempos": datos_tiempos,
    })

    return render(request, "academico/estadisticas.html", contexto)

def obtener_contexto_base():
    carreras = Carrera.objects.all().order_by("nombre_carrera")

    escuelas = (
        Carrera.objects
        .exclude(escuela="")
        .values_list("escuela", flat=True)
        .distinct()
        .order_by("escuela")
    )

    return {
        "carreras": carreras,
        "escuelas": escuelas,
        "fechaFin": date.today(),
    }


def lista_graduados(request):
    graduados = obtener_graduados_filtrados(request.GET)

    escuelas = (
        Carrera.objects
        .exclude(escuela='')
        .values_list('escuela', flat=True)
        .distinct()
        .order_by('escuela')
    )

    carreras = Carrera.objects.all().order_by('nombre_carrera')

    return render(
        request,
        'academico/lista_graduados.html',
        {
            'graduados': graduados,
            'escuelas': escuelas,
            'carreras': carreras,
        }
    )


def descargar_graduados(request):
    graduados = obtener_graduados_filtrados(request.GET)

    contenido = generar_csv_graduados(graduados)

    respuesta = HttpResponse(
        contenido,
        content_type='text/csv; charset=utf-8'
    )

    respuesta['Content-Disposition'] = (
        'attachment; filename="graduados.csv"'
    )

    return respuesta