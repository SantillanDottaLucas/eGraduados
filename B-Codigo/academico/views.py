from django.shortcuts import render
from .servicios.moduloAnalitico import *
from .servicios.moduloEstadistica.consulta_estadisticas import *
from .servicios.moduloEstadistica.graficador_estadistico import *
from .models import Graduado, Carrera
from datetime import date
import csv
from django.http import HttpResponse



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
    fechaFin= date.today()
    return render(request,"academico/estadisticas.html", {'fechaFin':fechaFin})

def estadisticas_promedios(request):
    tipo_promedio = request.GET.get("promedio")
    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fechaInicio = request.GET.get("fechaInicio")
    fechaFin= request.GET.get("fechaFin")

    resultado_promedio =consultar_promedios(tipo_promedio, filtro, carrera, escuela, fechaInicio, fechaFin)

    datos = {'promedio':resultado_promedio['promedio'],
            'varianza':resultado_promedio['varianza']         
    }
    return render(
        request, 
        'academico/estadisticas.html',
        {'datos_promedios':datos}
       )

def estadisticas_totales(request):

    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fechaInicio = request.GET.get("fechaInicio")
    fechaFin= request.GET.get("fechaFin")

    resultado_total = consultar_total(filtro, carrera, escuela, fechaInicio, fechaFin)
    datos_totales = graficar_total(resultado_total)

    return render(request, 'academico/estadisticas.html', {'resultado_total':resultado_total,'datos_totales':datos_totales})

def estadisticas_tiempos(request):

    return render(request, 'academico/estadisticas.html', {'resultado_tiempo':resultado_tiempo,'datos_tiempos':datos_tiempos})



def lista_graduados(request):
    graduados = Graduado.objects.all()

    escuelas = Carrera.objects.filter(
        'escuela', flat=True
    ).distinct()

    carreras = Carrera.objects.all()


    return render(request, 'academico/lista_graduados.html',{
        'graduados':graduados,
        'escuelas':escuelas,
        'carreras':carreras
    })

def descargar_graduados(request):
    graduados = consultar_graduados(request)

    respuesta = Httpresponse