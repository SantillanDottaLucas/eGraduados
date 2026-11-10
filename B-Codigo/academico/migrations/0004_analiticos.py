"""
Preparación del dominio para la generación de analíticos:

- Resolución tipada (institucional / ministerial nacional /
  otro instrumento). La columna RESOLUCION.tipo_resolucion ya
  existe en la base (aplicada en un intento anterior), por lo
  que sólo se registra en el estado de las migraciones.
- Ciudad de nacimiento (DATOS_NACIMIENTO) y ciudad del
  secundario (SECUNDARIO), además del título secundario y el
  año de egreso del secundario.
- Nuevo modelo ANALITICO: registro del analítico validado
  (se guardan los datos, no el documento).

Las tablas involucradas están vacías, por lo que los FKs sin
default se agregan sin necesidad de backfill.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0003_grupo_optativo_por_plan"),
    ]

    operations = [
        # 1. Resolución tipada.
        migrations.AddField(
            model_name="Resolucion",
            name="tipo_resolucion",
            field=models.CharField(
                choices=[
                    ("institucional", "Institucional"),
                    ("ministerial_nacional", "Ministerio / Nación"),
                    ("otro_instrumento", "Otro instrumento legal"),
                ],
                default="institucional",
                max_length=20,
            ),
        ),

        # 2. Ciudad de nacimiento.
        migrations.AddField(
            model_name="DatosNacimiento",
            name="id_ciudad",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                db_column="id_ciudad",
                related_name="datos_nacimiento",
                to="academico.ciudad",
            ),
        ),

        # 3. Datos del secundario.
        migrations.AddField(
            model_name="Secundario",
            name="titulo_secundario",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="Secundario",
            name="anio_egreso_secundario",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="Secundario",
            name="id_ciudad",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                db_column="id_ciudad",
                related_name="secundarios",
                to="academico.ciudad",
            ),
        ),

        # 4. Registro del analítico validado.
        migrations.CreateModel(
            name="Analitico",
            fields=[
                (
                    "id_analitico",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "legajo_graduado",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        db_column="legajo_graduado",
                        related_name="analiticos",
                        to="academico.graduado",
                    ),
                ),
                (
                    "codigo_carrera",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        db_column="codigo_carrera",
                        related_name="analiticos",
                        to="academico.carrera",
                    ),
                ),
                (
                    "tipo_documento",
                    models.CharField(
                        choices=[
                            ("titulo", "Analítico (Título)"),
                            ("en_tramite", "Analítico (Título en trámite)"),
                        ],
                        default="titulo",
                        max_length=20,
                    ),
                ),
                (
                    "anio_ingreso_uarg",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "fecha_validacion",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "id_usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        db_column="id_usuario",
                        related_name="analiticos_validados",
                        to="academico.usuario",
                    ),
                ),
            ],
            options={
                "db_table": "ANALITICO",
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "legajo_graduado",
                            "codigo_carrera",
                            "tipo_documento",
                        ),
                        name="uniq_analitico_por_documento",
                    ),
                ],
            },
        ),
    ]
