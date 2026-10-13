from django.shortcuts import render
from .servicios.consulta_estadisticas import * #Punto inicial para buscar dentro de la misma carpeta
from .servicios.graficador_estadistico import *

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
    return render(request,"academico/estadisticas.html")

def estadisticas_promedios(request):
    tipo_promedio = request.GET.get("promedio")
    filtro = request.GET.get("filtro")
    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    fechaInicio = request.GET.get("fechaInicio")
    fechaFin= request.GET.get("fechaFin")

    dato =consultar_promedios(tipo_promedio, filtro, carrera, escuela, fechaInicio, fechaFin)

    datos_promedios= graficar_promedio(dato)

    return render(request, 'academico/estadisticas.html',{'datos_promedios':datos_promedios})

def estadisticas_totales(request):

    carrera = request.GET.get("carrera")
    escuela = request.GET.get("escuela")
    anioIngreso = request.GET.get("anioIngreso")
    anioEgreso= request.GET.get("anioEgreso")

    dato = consultar_total(carrera,escuela,anioIngreso, anioEgreso)
    datos_totales = graficar_total(dato)

    return render(request, 'academico/estadisticas.html', {'datos_totales':datos_totales})

def estadisticas_tiempos(request):

    return render(request, 'academico/estadisticas.html', {'datos_tiempos':datos_tiempos})