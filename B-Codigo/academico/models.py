from django.db import models
from django.db.models import Q

# Create your models here.

class Graduado(models.Model):
    legajo_graduado = models.CharField(max_length=14, primary_key=True)
    dni_graduado = models.CharField(max_length=9, unique=True)
    fecha_ingreso_universidad = models.DateField()
    promedio_sin_aplazo= models.DecimalField(max_digits=4, decimal_places=2)
    promedio_con_aplazo= models.DecimalField(max_digits=4, decimal_places=2, null=True, blank= True)

    class Meta:
        constraints= [
            models.CheckConstraint(
                condition=Q(promedio_sin_aplazo__gte=1) & Q(promedio_sin_aplazo__lte=10),
                name='promedio_sin_aplazo'                
            ),
            models.CheckConstraint(
                condition=(
                    Q(promedio_con_aplazo__isnull=True) |
                    Q(promedio_con_aplazo__gte=1) & Q(promedio_con_aplazo__lte=10)),
                name='promedio_con_aplazo'
            )            
        ]

    def __str__(self):
        return self.legajo_graduado


class Carrera(models.Model):
    codigo_carrera = models.CharField(max_length=4, primary_key=True)
    nombre_carrera= models.CharField(max_length=50)
    escuela= models.CharField(max_length=100)
    resolucion_nacional= models.CharField(max_length=8, null=True, blank=True)
    notas= models.CharField(max_length=5, null=True, blank=True)

    def __str__(self):
        return f"{self.codigo_carrera}, {self.nombre_carrera}, {self.escuela}"

class PlanEstudios(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='planes')
    codigo_plan = models.CharField(max_length=10)
    vigente = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['carrera'],
                name= 'fk_plan_carrera'
            )
        ]

class Materia(models.Model):
    codigo_materia=models.CharField(max_length=6, primary_key=True)
    nombre_materia=models.CharField(max_length=100)
    anio=models.CharField(max_length=1)

    def __str__(self):
        return f"{self.codigo_materia}, {self.nombre_materia}"


#ACLARACIÓN IMPORTANTE: Esto más que un "examen" representa una MESA DE EXAMEN. Se le pone examen para seguir el 
#nombre que se encuentra en el analítico
class Examen(models.Model): 
    class TipoExamen(models.TextChoices):
            EQUIVALENCIA= 'EQUIV','Equivalencia'
            EXAMEN='EXAM','Examen'
    tipo=models.CharField(max_length=20, choices=TipoExamen, default=TipoExamen.EXAMEN)
    acta_respaldatoria= models.CharField(max_length=20, primary_key=True)
    fecha_examen= models.DateField()
    materia=models.ForeignKey(Materia, on_delete=models.CASCADE, related_name="examenes")
    

    def __str__(self):
        return f"{self.acta_respaldatoria},{self.tipo}"

class CarreraNombreTitulo(models.Model):
    carrera=models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='nombresTitulos')
    nombre_titulos=models.CharField(max_length=100)

    def __str__(self):
        return f"{self.carrera.nombre_carrera}, {self.titulos}"

class Analitico(models.Model):
    graduado= models.ForeignKey(Graduado,on_delete=models.CASCADE, related_name='analiticos')
    titulo_carrera=models.ForeignKey(CarreraNombreTitulo, on_delete=models.PROTECT, related_name='analiticos')
    ciudad_secundario= models.CharField(max_length=200, null=True)
    provincia_secundario=models.CharField(max_length=200, null=True)
    nombre_secundario=models.CharField(max_length=200, null=True)
    titulo_secundario=models.CharField(max_length=200, null=True)
    fecha_egreso_carrera=models.DateField()

    class Meta: #meta son las restricciones
        constraints=[
            models.UniqueConstraint( #restricción de UNIQUE para que no se repitan los siguientes campos
                fields=['graduado','titulo_carrera'], #campos que NO pueden repetirse
                name='fk_analitico'
            )
        ]

    def __str__(self):
        return f"Analitico - {self.graduado} ({self.titulo_carrera.nombre_titulos})"

class GraduadoCarrera(models.Model):
    carrera=models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='graduados_asociados')
    graduado=models.ForeignKey(Graduado, on_delete=models.CASCADE, related_name='carreras_asociadas')
    fecha_ingreso_carrera= models.DateField()

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['graduado','carrera'],
                name='unique_graduado_carrera'
            )
        ]

    
class PlanMateria(models.Model):
    materia= models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='carreras_asociadas')
    plan= models.ForeignKey(PlanEstudios, on_delete=models.CASCADE, related_name='materias_asociadas')
    orden = models.CharField(max_length=2)

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['materia','plan'],
                name='unique_plan_materia'
            )
        ]

class ExamenGraduado(models.Model):
    examen=models.ForeignKey(Examen, on_delete=models.CASCADE,related_name='graduados_asociados')
    graduado=models.ForeignKey(Graduado, on_delete=models.CASCADE, related_name='examenes_asociados')
    nota= models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['examen','graduado'],
                name='unique_examen_graduado'
            ),
            models.CheckConstraint(
                condition=Q(nota__gte=1) & Q(nota__lte=10),
                name='notra_entre_uno_y_diez'
            )
        ]

class GraduadoApellido (models.Model):
    graduado=models.ForeignKey(Graduado, on_delete=models.CASCADE, related_name='apellidos_asociados')
    apellido = models.CharField(max_length=50)

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['apellido','graduado'],
                name='unique_apellido_graduado'
            )
        ]

class GraduadoNombre (models.Model):
    graduado=models.ForeignKey(Graduado, on_delete=models.CASCADE, related_name='nombres_asociados')
    nombre = models.CharField(max_length=50)

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['nombre','graduado'],
                name='unique_nombre_graduado'
            )
        ]

class GraduadoMateria(models.Model):
    graduado=models.ForeignKey(Graduado, on_delete=models.CASCADE, related_name='materias_asociadas')
    materia= models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='graduados_asociados')
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['graduado','materia'],
                name='unique_graduado_materia'
            )
        ]

class CarerraResolucionInstitucional(models.Model):
    carrera= models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='resoluciones_relacionadas')
    resolucion_institucional= models.CharField(max_length=10)


