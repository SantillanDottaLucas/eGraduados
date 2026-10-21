from django.shortcuts import render
from .servicios.moduloAnalitico import *
from .servicios.moduloEstadistica.consulta_estadisticas import *
from .servicios.moduloEstadistica.graficador_estadistico import *
from .models import Graduado
from datetime import date


# Create your views here.
#Redirigir al index
def index(request):
    return render(request,"academico/index.html")

#Generar un analítico si el método es POST. Si es un GET, reenvia al html generacion_titulos
def generacion_titulos(request):

    if request.method == 'POST': #SI EL REQUEST ES UN POST, GENERA EL ANALÍTICO

        nombre = request.POST['nombre']
        apellido = request.POST['apellido']
        legajo = request.POST['legajo']

        archivo_notas = request.FILES['archivo_notas']

        # Más adelante:
        # analitico = generar_analitico(...)

    return render(
        request,
        'academico/generacion_titulos.html'
    )

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
    datos_promedios= graficar_promedio(resultado_promedio['promedio'])

    return render(
        request, 
        'academico/estadisticas.html',
        {
            'resultado_promedio':resultado_promedio['promedio'],
            'datos_promedios':datos_promedios,
            'varianza_promedios': resultado_promedio['varianza']
            })

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

    contexto = {'graduados':graduados}

    return render(request, 'academico/lista_graduados.html',contexto)