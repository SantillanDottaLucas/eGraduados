from academico.models import *
from django.db.models import Avg, Variance, Count
from statistics import mean, pvariance

    #Carolina + Lucas por siempre

# Calcula el promedio x escuela, x carrera o para todos 
def consultar_promedios(tipoPromedio, filtro, carrera, escuela, fechaInicio, fechaFin):
    if filtro == 'todos':
        graduados= Graduado.objects.filter(
            analiticos__fecha_egreso_carrera__range= [fechaInicio,fechaFin]
        ).aggregate(
        promedio = Avg(tipoPromedio),
        varianza=Variance(tipoPromedio)
        )
    elif filtro == 'escuela':
        escuelaNombre = escuela
        graduados = Carrera.objects.filter(
            escuela=escuelaNombre,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).aggregate(  #Devuelve un único valor. Si hago Values devuelve un diccionario
            promedio= Avg(
                "nombresTitulos__analiticos__graduado__" + tipoPromedio
                ),
            varianza= Variance("nombresTitulos__analiticos__graduado__" + tipoPromedio)    
        )
    elif filtro == 'carrera':
        carreraId = carrera
        graduados = Carrera.objects.filter(
            codigo_carrera = carreraId,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).aggregate(
            promedio= Avg(
                "nombresTitulos__analiticos__graduado__" + tipoPromedio
            ),
            varianza=Variance("nombresTitulos__analiticos__graduado__" + tipoPromedio)
        )
    return graduados


def consultar_total(filtro, carrera, escuela, fechaInicio, fechaFin):
    if filtro == 'todos': #DEVUELVE TOTAL DE GRADUADOS (no se diferencia por carrera o por escuela)
        graduados= total_escuelas(fechaInicio, fechaFin) 
    elif filtro == 'escuela': #DEVUELVE CANTIDAD DE GRADUADOS POR ESCUELA
        graduados = total_carreras_escuela(escuela, fechaInicio, fechaFin)
    elif filtro == 'carrera':
        carreraId = carrera
        graduados = GraduadoCarrera.objects.filter(
            codigo_carrera = carrera,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).count()
    return graduados

def total_carreras_escuela(escuela, fechaInicio, fechaFin):
    carreras = Carrera.objects.filter( #Consulta BASE
        escuela = escuela,
        nombresTitulos__analiticos__fecha_egreso_carrera__range= [fechaInicio, fechaFin]
    ).distinct()

    graduados_por_carrera = carreras.annotate( #Separado por escuela
        total_carrera = Count('nombresTitulos__analiticos__graduado', distinct=True)
    ).values('codigo_carrera', 'nombre_carrera', 'total_carrera')

    total_por_carrera = list(graduados_por_carrera)

    graduados_escuela = carreras.aggregate( #Datos de la escuela
        total = Count('nombresTitulos__analiticos__graduado', distinct=True)
    ).aggregate(
        total_escuela=Count('nombresTitulos__analiticos__graduado', distinct=True)
    )

    cantidades= [
        carrera['total_carrera']
        for carrera in total_por_carrera
                 ]
    promedio = mean(cantidades) if cantidades else None
    varianza = pvariance(cantidades) if cantidades else None

    return {
        'total_escuela': graduados_escuela['total_escuela'],
        'promedio_por_carrera':promedio,
        'varianza_carreras':varianza,
        'total_por_carrera':total_por_carrera
    }

def total_escuelas(fechaInicio, fechaFin):
    #Total
    total = Graduado.objects.filter(
        nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
    ).distinct().count()
    #

    graduados_por_escuela= Carrera.objects.filter(
        nombresTitulos__analiticos__fecha_egreso_carrera__range=[fechaInicio,fechaFin]
        ).values(
            'escuela'
        ).annotate(
            total_escuela=Count('nombresTitulos__analiticos__graduado', distinct=True)
        ).order_by('escuela')

    total_por_escuela = list(graduados_por_escuela)

    cantidades=[
        escuela['total_escuela']
        for escuela in total_por_escuela
    ]

    promedio = mean(cantidades) if cantidades else None
    varianza = pvariance(cantidades) if cantidades else None

    graduados_por_escuela= "as"
    return {
        'total':total,
        'promedio_por_escuela':promedio,
        'varianza_escuelas':varianza,
        'total_por_escuela':total_por_escuela
    }




