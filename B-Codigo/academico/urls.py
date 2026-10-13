from django.urls import path
from . import views

# El primer campo indica a donde entro
urlpatterns=[
    path("",views.index, name="index"),
    path("generacion-titulos/", views.generacion_titulos, name="generacion_titulos"),
    path("estadisticas/", views.estadisticas, name="estadisticas"),
    path("estdisticas/", views.estadisticas_promedios, name="estadisticas_promedios"),
    path("estadisticas/",views.estadisticas_totales, name="estadisticas_totales"),
    path("estadisticas/",views.estadisticas_tiempos, name="estadisticas_tiempos")
]