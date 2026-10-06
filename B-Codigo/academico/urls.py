from django.urls import path
from . import views

# El primer campo indica a donde entro
urlpatterns=[
    path("",views.index, name="index"),
    path("generacion-titulos/", views.generacion_titulos, name="generacion_titulos"),
    path("estadisticas/", views.estadisticas, name="estadisticas")
]