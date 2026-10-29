
from django.db import models


# ==========================================================
# ENUMERACIONES
# ==========================================================

class ResultadoExamen(models.TextChoices):
    APROBADO = "Aprobado", "Aprobado"
    REPROBADO = "Reprobado", "Reprobado"


class Cuatrimestre(models.TextChoices):
    PRIMERO = "1er", "1er"
    SEGUNDO = "2do", "2do"
    ANUAL = "A", "A"


# ==========================================================
# GRADUADO
# ==========================================================

class Graduado(models.Model):
    legajo_graduado = models.CharField(
        max_length=50,
        primary_key=True
    )
    dni = models.CharField(max_length=20, unique=True)
    fecha_ingreso_universidad = models.DateField()
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    class Meta:
        db_table = "GRADUADO"

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"


# ==========================================================
# ESCUELA Y CARRERA
# ==========================================================

class Escuela(models.Model):
    id_escuela = models.AutoField(primary_key=True)
    nombre_escuela = models.CharField(max_length=150, unique=True)

    class Meta:
        db_table = "ESCUELA"

    def __str__(self):
        return self.nombre_escuela


class Carrera(models.Model):
    codigo_carrera = models.CharField(
        max_length=50,
        primary_key=True
    )
    nombre_carrera = models.CharField(max_length=150)

    id_escuela = models.ForeignKey(
        Escuela,
        on_delete=models.PROTECT,
        db_column="id_escuela",
        related_name="carreras"
    )

    class Meta:
        db_table = "CARRERA"

    def __str__(self):
        return self.nombre_carrera


# ==========================================================
# PLAN DE ESTUDIOS Y MATERIA
# ==========================================================

class PlanEstudios(models.Model):
    codigo_plan = models.CharField(
        max_length=50,
        primary_key=True
    )

    codigo_carrera = models.ForeignKey(
        Carrera,
        on_delete=models.PROTECT,
        db_column="codigo_carrera",
        related_name="planes_estudio"
    )

    class Meta:
        db_table = "PLAN_ESTUDIOS"

    def __str__(self):
        return self.codigo_plan


class Materia(models.Model):
    codigo_materia = models.CharField(
        max_length=50,
        primary_key=True
    )
    nombre_materia = models.CharField(max_length=150)

    class Meta:
        db_table = "MATERIA"

    def __str__(self):
        return self.nombre_materia


# ==========================================================
# EXAMEN
# ==========================================================

class Examen(models.Model):
    acta_respaldatoria = models.CharField(
        max_length=50,
        primary_key=True
    )
    tipo_examen = models.CharField(max_length=100)
    fecha_examen = models.DateField()

    codigo_materia = models.ForeignKey(
        Materia,
        on_delete=models.PROTECT,
        db_column="codigo_materia",
        related_name="examenes"
    )

    class Meta:
        db_table = "EXAMEN"

    def __str__(self):
        return self.acta_respaldatoria


# ==========================================================
# TITULO
# ==========================================================

class Titulo(models.Model):
    id_titulo = models.AutoField(primary_key=True)
    nombre_titulo = models.CharField(max_length=150, unique=True)

    codigo_carrera = models.ForeignKey(
        Carrera,
        on_delete=models.PROTECT,
        db_column="codigo_carrera",
        related_name="titulos"
    )

    class Meta:
        db_table = "TITULO"

    def __str__(self):
        return self.nombre_titulo


# ==========================================================
# PROVINCIA Y CIUDAD
# ==========================================================

class Provincia(models.Model):
    id_provincia = models.AutoField(primary_key=True)
    nombre_provincia = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "PROVINCIA"

    def __str__(self):
        return self.nombre_provincia


class Ciudad(models.Model):
    id_ciudad = models.AutoField(primary_key=True)
    nombre_ciudad = models.CharField(max_length=100, unique=True)

    id_provincia = models.ForeignKey(
        Provincia,
        on_delete=models.PROTECT,
        db_column="id_provincia",
        related_name="ciudades"
    )

    class Meta:
        db_table = "CIUDAD"

    def __str__(self):
        return self.nombre_ciudad


# ==========================================================
# DATOS DE NACIMIENTO
# ==========================================================

class DatosNacimiento(models.Model):
    id_datos = models.AutoField(primary_key=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.CASCADE,
        db_column="legajo_graduado",
        related_name="datos_nacimiento"
    )

    id_provincia = models.ForeignKey(
        Provincia,
        on_delete=models.PROTECT,
        db_column="id_provincia",
        related_name="datos_nacimiento"
    )

    class Meta:
        db_table = "DATOS_NACIMIENTO"


# ==========================================================
# SECUNDARIO
# ==========================================================

class Secundario(models.Model):
    id_secundario = models.AutoField(primary_key=True)
    nombre_secundario = models.CharField(max_length=200, unique=True)

    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.PROTECT,
        db_column="legajo_graduado",
        related_name="secundarios"
    )

    id_provincia = models.ForeignKey(
        Provincia,
        on_delete=models.PROTECT,
        db_column="id_provincia",
        related_name="secundarios"
    )

    class Meta:
        db_table = "SECUNDARIO"

    def __str__(self):
        return self.nombre_secundario


# ==========================================================
# USUARIO
# ==========================================================

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre_usuario = models.CharField(max_length=100, unique=True)
    email = models.EmailField(max_length=254, unique=True)

    # Recomendación: almacenar contraseñas mediante
    # el sistema de autenticación de Django, nunca como enteros.
    contrasenia = models.CharField(max_length=128)

    class Meta:
        db_table = "USUARIO"

    def __str__(self):
        return self.nombre_usuario


# ==========================================================
# RESOLUCION
# ==========================================================

class Resolucion(models.Model):
    resolucion = models.CharField(
        max_length=100,
        primary_key=True
    )

    class Meta:
        db_table = "RESOLUCION"

    def __str__(self):
        return self.resolucion


# ==========================================================
# GRADUADO_CARRERA
# Clave primaria compuesta
# ==========================================================

class GraduadoCarrera(models.Model):
    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.CASCADE,
        db_column="legajo_graduado",
        related_name="carreras_cursadas"
    )

    codigo_carrera = models.ForeignKey(
        Carrera,
        on_delete=models.PROTECT,
        db_column="codigo_carrera",
        related_name="graduados"
    )

    fecha_ingreso_carrera = models.DateField()
    fecha_egreso_carrera = models.DateField()
    promedio_con_aplazo = models.FloatField()
    promedio_sin_aplazo = models.FloatField()

    pk = models.CompositePrimaryKey(
        "legajo_graduado",
        "codigo_carrera"
    )

    class Meta:
        db_table = "GRADUADO_CARRERA"


# ==========================================================
# GRADUADO_EXAMEN
# Clave primaria compuesta
# ==========================================================

class GraduadoExamen(models.Model):
    acta_respaldatoria = models.ForeignKey(
        Examen,
        on_delete=models.PROTECT,
        db_column="acta_respaldatoria",
        related_name="resultados_graduados"
    )

    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.CASCADE,
        db_column="legajo_graduado",
        related_name="examenes"
    )

    nota = models.IntegerField()
    resultado = models.CharField(
        max_length=10,
        choices=ResultadoExamen.choices
    )

    pk = models.CompositePrimaryKey(
        "acta_respaldatoria",
        "legajo_graduado"
    )

    class Meta:
        db_table = "GRADUADO_EXAMEN"


# ==========================================================
# GRUPO OPTATIVO
# ==========================================================

class GrupoOptativo(models.Model):
    id_grupo_optativo = models.AutoField(primary_key=True)
    nombre_grupo = models.CharField(max_length=150)

    class Meta:
        db_table = "GRUPO_OPTATIVO"

    def __str__(self):
        return self.nombre_grupo


# ==========================================================
# PLAN_ESTUDIOS_MATERIA
# Clave primaria compuesta
# ==========================================================

class PlanEstudiosMateria(models.Model):
    codigo_plan = models.ForeignKey(
        PlanEstudios,
        on_delete=models.CASCADE,
        db_column="codigo_plan",
        related_name="materias_plan"
    )

    codigo_materia = models.ForeignKey(
        Materia,
        on_delete=models.PROTECT,
        db_column="codigo_materia",
        related_name="planes"
    )

    anio_materia = models.IntegerField()

    cuatrimestre_materia = models.CharField(
        max_length=3,
        choices=Cuatrimestre.choices
    )

    orden_materia = models.IntegerField()
    materia_requisito = models.BooleanField()

    id_grupo_optativo = models.ForeignKey(
        GrupoOptativo,
        on_delete=models.SET_NULL,
        db_column="id_grupo_optativo",
        null=True,
        blank=True,
        related_name="materias"
    )

    pk = models.CompositePrimaryKey(
        "codigo_plan",
        "codigo_materia"
    )

    class Meta:
        db_table = "PLAN_ESTUDIOS_MATERIA"


# ==========================================================
# CARRERA_RESOLUCION
# Clave primaria compuesta
# ==========================================================

class CarreraResolucion(models.Model):
    resolucion = models.ForeignKey(
        Resolucion,
        on_delete=models.CASCADE,
        db_column="resolucion",
        related_name="carreras_resolucion"
    )

    codigo_carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE,
        db_column="codigo_carrera",
        related_name="resoluciones"
    )

    pk = models.CompositePrimaryKey(
        "resolucion",
        "codigo_carrera"
    )

    class Meta:
        db_table = "CARRERA_RESOLUCION"
