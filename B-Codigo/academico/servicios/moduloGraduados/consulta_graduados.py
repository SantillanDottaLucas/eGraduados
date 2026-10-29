from models import Graduado

def consulta_graduados(request):
    graduados = Graduado.objecst.all()
    
