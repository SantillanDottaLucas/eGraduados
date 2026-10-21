from academico.models import *
from django.db.models import Avg, Variance, Count

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
    if filtro == 'todos':
        graduados= Graduado.objects.filter(
            analiticos__fecha_egreso_carrera__range= [fechaInicio,fechaFin]
        ).count()
    elif filtro == 'escuela': #DEVUELVE CANTIDAD DE GRADUADOS POR ESCUELA
        graduados = total_carreras_escuela(escuela, fechaInicio, fechaFin)
        escuelaNombre = escuela
        graduados = Carrera.objects.filter(
            escuela=escuelaNombre,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).annotate(
            total_escuela=Count('nombresTitulos__analiticos__graduado', distinc=True)
        )
    elif filtro == 'carrera':
        carreraId = carrera
        graduados = Carrera.objects.filter(
            codigo_carrera = carreraId,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).count()
    return graduados

def total_carreras_escuela(escuela, fechaInicio, fechaFin):
    carreras = Carrera.objects.filter(
        escuelaNombre = escuela,
        nombresTitulos__analiticos__fecha_egreso_carrera_range= [fechaInicio, fechaFin]
    )

    graduados_por_carrera = carreras.annotate(
        total_carrera = Count('nombresTitulos__analiticos__graduado', distinct=True)
    ).values('codigo_carrera', 'nombre', 'total_carrera')

    graduados_escuela = carreras.annotate(
        total = Count('nombresTitulos__analiticos__graduado', distinct=True)
    ).aggregate(
        total_escuela=Count( )
    )



