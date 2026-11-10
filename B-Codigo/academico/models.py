
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


class TipoResolucion(models.TextChoices):
    INSTITUCIONAL = "institucional", "Institucional"
    MINISTERIAL_NACIONAL = "ministerial_nacional", "Ministerio / Nación"
    OTRO_INSTRUMENTO = "otro_instrumento", "Otro instrumento legal"


class TipoDocumentoAnalitico(models.TextChoices):
    TITULO = "titulo", "Analítico (Título)"
    EN_TRAMITE = "en_tramite", "Analítico (Título en trámite)"


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
    id_examen = models.AutoField(primary_key=True)

    # El acta no es única por sí sola: una resolución abarca
    # varias materias, por eso la unicidad es (acta, materia).
    acta_respaldatoria = models.CharField(max_length=50)

    tipo_examen = models.CharField(max_length=100, blank=True)
    fecha_examen = models.DateField(null=True, blank=True)

    codigo_materia = models.ForeignKey(
        Materia,
        on_delete=models.PROTECT,
        db_column="codigo_materia",
        related_name="examenes"
    )

    class Meta:
        db_table = "EXAMEN"
        constraints = [
            models.UniqueConstraint(
                fields=["acta_respaldatoria", "codigo_materia"],
                name="uniq_examen_acta_materia",
            ),
        ]

    def __str__(self):
        return f"{self.acta_respaldatoria} ({self.codigo_materia})"


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
        related_name="datos_nacimiento",
        null=True,
    )

    id_ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        db_column="id_ciudad",
        related_name="datos_nacimiento",
        null=True,
    )

    class Meta:
        db_table = "DATOS_NACIMIENTO"


# ==========================================================
# SECUNDARIO
# ==========================================================

class Secundario(models.Model):
    id_secundario = models.AutoField(primary_key=True)
    nombre_secundario = models.CharField(max_length=200, unique=True)

    titulo_secundario = models.CharField(
        max_length=200,
        default="",
        blank=True,
    )

    anio_egreso_secundario = models.IntegerField(
        null=True,
        blank=True,
    )

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
        related_name="secundarios",
        null=True,
    )

    id_ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        db_column="id_ciudad",
        related_name="secundarios",
        null=True,
    )

    class Meta:
        db_table = "SECUNDARIO"

    def __str__(self):
        return self.nombre_secundario


# ==========================================================
# ROL Y USUARIO
# ==========================================================

class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=100, unique=True)

    # Un rol administrador accede, además de las pantallas
    # básicas, al ABM de usuarios y roles.
    puede_administrar = models.BooleanField(default=False)

    class Meta:
        db_table = "ROL"

    def __str__(self):
        return self.nombre_rol


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre_usuario = models.CharField(max_length=100, unique=True)
    email = models.EmailField(max_length=254, unique=True)

    # El código de acceso de 6 caracteres se almacena
    # hasheado mediante make_password / check_password.
    codigo_acceso = models.CharField(max_length=128)

    id_rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="id_rol",
        related_name="usuarios"
    )

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

    tipo_resolucion = models.CharField(
        max_length=20,
        choices=TipoResolucion.choices,
        default=TipoResolucion.INSTITUCIONAL,
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
    promedio_con_aplazo = models.FloatField(null=True, blank=True)
    promedio_sin_aplazo = models.FloatField(null=True, blank=True)

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
    id_graduado_examen = models.AutoField(primary_key=True)

    id_examen = models.ForeignKey(
        Examen,
        on_delete=models.CASCADE,
        db_column="id_examen",
        related_name="resultados_graduados"
    )

    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.CASCADE,
        db_column="legajo_graduado",
        related_name="examenes"
    )

    nota = models.IntegerField(null=True, blank=True)

    resultado = models.CharField(
        max_length=10,
        choices=ResultadoExamen.choices
    )

    class Meta:
        db_table = "GRADUADO_EXAMEN"
        constraints = [
            models.UniqueConstraint(
                fields=["id_examen", "legajo_graduado"],
                name="uniq_graduado_examen",
            ),
        ]


# ==========================================================
# GRUPO OPTATIVO
# ==========================================================

class GrupoOptativo(models.Model):
    id_grupo_optativo = models.AutoField(primary_key=True)
    nombre_grupo = models.CharField(max_length=150)

    codigo_plan = models.ForeignKey(
        PlanEstudios,
        on_delete=models.CASCADE,
        db_column="codigo_plan",
        related_name="grupos_optativos",
    )

    class Meta:
        db_table = "GRUPO_OPTATIVO"
        constraints = [
            models.UniqueConstraint(
                fields=["codigo_plan", "nombre_grupo"],
                name="uniq_grupo_optativo_por_plan",
            ),
        ]

    def __str__(self):
        return self.nombre_grupo


class PlanEstudiosGrupoOptativo(models.Model):
    """
    Ubicación de un grupo optativo dentro del cronograma de
    un plan de estudios (se comporta como una materia más).
    """

    codigo_plan = models.ForeignKey(
        PlanEstudios,
        on_delete=models.CASCADE,
        db_column="codigo_plan",
        related_name="grupos_ubicados",
    )

    id_grupo_optativo = models.ForeignKey(
        GrupoOptativo,
        on_delete=models.PROTECT,
        db_column="id_grupo_optativo",
        related_name="ubicaciones",
    )

    anio_materia = models.IntegerField()
    cuatrimestre_materia = models.CharField(
        max_length=3,
        choices=Cuatrimestre.choices,
    )
    orden_materia = models.IntegerField()

    pk = models.CompositePrimaryKey(
        "codigo_plan",
        "id_grupo_optativo",
    )

    class Meta:
        db_table = "PLAN_ESTUDIOS_GRUPO_OPTATIVO"


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

    anio_materia = models.IntegerField(null=True, blank=True)

    cuatrimestre_materia = models.CharField(
        max_length=3,
        choices=Cuatrimestre.choices,
        null=True,
        blank=True,
    )

    orden_materia = models.IntegerField(null=True, blank=True)
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

# ==========================================================
# ANALITICO
# Registro de los analíticos generados/validados.
# Se guardan los DATOS (fuente: BD), no el documento.
# ==========================================================

class Analitico(models.Model):
    id_analitico = models.AutoField(primary_key=True)

    legajo_graduado = models.ForeignKey(
        Graduado,
        on_delete=models.CASCADE,
        db_column="legajo_graduado",
        related_name="analiticos",
    )

    codigo_carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE,
        db_column="codigo_carrera",
        related_name="analiticos",
    )

    tipo_documento = models.CharField(
        max_length=20,
        choices=TipoDocumentoAnalitico.choices,
        default=TipoDocumentoAnalitico.TITULO,
    )

    anio_ingreso_uarg = models.IntegerField(null=True, blank=True)

    fecha_validacion = models.DateTimeField(auto_now_add=True)

    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        db_column="id_usuario",
        related_name="analiticos_validados",
    )

    class Meta:
        db_table = "ANALITICO"
        constraints = [
            models.UniqueConstraint(
                fields=["legajo_graduado", "codigo_carrera", "tipo_documento"],
                name="uniq_analitico_por_documento",
            ),
        ]

    def __str__(self):
        return (
            f"{self.legajo_graduado_id} - {self.codigo_carrera_id}"
            f" ({self.get_tipo_documento_display()})"
        )
