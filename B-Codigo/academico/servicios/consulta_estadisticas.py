from academico.models import *
from django.db.models import Avg

            #Carolina + Lucas por siempre

def consultar_promedios(tipoPromedio, filtro, carrera, escuela, fechaInicio, fechaFin):
    if filtro == 'todos':
        graduados= Graduado.objects.filter(
            analiticos__fecha_egreso_carrera__range= [fechaInicio,fechaFin]
        ).aggregate(
        promedio = Avg(tipoPromedio)
        )
    elif filtro == 'escuela':
        escuelaNombre = escuela
        graduados = Carrera.objects.filter(
            escuela=escuelaNombre,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).aggregate(  #Devuelve un único valor. Si hago Values devuelve un diccionario
            promedio= Avg(
                "nombresTitulos__analiticos__graduado__" + tipoPromedio
                )
        )
    elif filtro == 'carrera':
        carreraId = carrera
        graduados = Carrera.objects.filter(
            codigo_carrera = carreraId,
            nombresTitulos__analiticos__fecha_egreso_carrera__range = [fechaInicio, fechaFin]
        ).aggregate(
            promedio= Avg(
                "nombresTitulos__analiticos__graduado__" + tipoPromedio
            )
        )
    return graduados