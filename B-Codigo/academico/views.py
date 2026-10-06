from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request,"academico/index.html")

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
def estadisticas(request):
    return render(request,"academico/estadisticas.html")
