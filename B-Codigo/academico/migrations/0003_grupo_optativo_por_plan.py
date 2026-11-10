"""
Convierte a los grupos optativos en entidades propias de cada
plan de estudios y permite ubicarlos en el cronograma de un
plan como si fueran una materia más (año, cuatrimestre y orden).

La tabla GRUPO_OPTATIVO está vacía, por lo que la columna
codigo_plan se agrega como obligatoria sin pérdida de datos.
Los campos año/cuatrimestre/orden de PLAN_ESTUDIOS_MATERIA
pasan a ser opcionales: las materias miembro de un grupo
heredan esos valores del grupo.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0002_rol_y_usuario"),
    ]

    operations = [
        # 1. Relajar año/cuatrimestre/orden (materias miembro).
        migrations.AlterField(
            model_name="planestudiosmateria",
            name="anio_materia",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="planestudiosmateria",
            name="cuatrimestre_materia",
            field=models.CharField(
                blank=True,
                choices=[("1er", "1er"), ("2do", "2do"), ("A", "A")],
                max_length=3,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="planestudiosmateria",
            name="orden_materia",
            field=models.IntegerField(blank=True, null=True),
        ),

        # 2. El grupo optativo pasa a pertenecer a un plan.
        migrations.AddField(
            model_name="grupooptativo",
            name="codigo_plan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                db_column="codigo_plan",
                related_name="grupos_optativos",
                to="academico.planestudios",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupooptativo",
            constraint=models.UniqueConstraint(
                fields=("codigo_plan", "nombre_grupo"),
                name="uniq_grupo_optativo_por_plan",
            ),
        ),

        # 3. Ubicación del grupo en el cronograma del plan.
        migrations.CreateModel(
            name="PlanEstudiosGrupoOptativo",
            fields=[
                (
                    "codigo_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        db_column="codigo_plan",
                        related_name="grupos_ubicados",
                        to="academico.planestudios",
                    ),
                ),
                (
                    "id_grupo_optativo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        db_column="id_grupo_optativo",
                        related_name="ubicaciones",
                        to="academico.grupooptativo",
                    ),
                ),
                ("anio_materia", models.IntegerField()),
                (
                    "cuatrimestre_materia",
                    models.CharField(
                        choices=[("1er", "1er"), ("2do", "2do"), ("A", "A")],
                        max_length=3,
                    ),
                ),
                ("orden_materia", models.IntegerField()),
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "codigo_plan",
                        "id_grupo_optativo",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
            options={
                "db_table": "PLAN_ESTUDIOS_GRUPO_OPTATIVO",
            },
        ),
    ]
