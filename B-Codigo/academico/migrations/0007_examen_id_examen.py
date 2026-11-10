"""
Reestructura los exámenes del sistema.

La acta ya no es clave primaria: una misma resolución puede
respaldar varias materias (p. ej. «Equivalencia T» con res_final
087/23-CS-UNPA). Las nuevas claves permiten:

- EXAMEN: un registro por (acta, materia).
- GRADUADO_EXAMEN: un registro por (examen, graduado).

Las tablas están vacías, por lo que se recrean completas
conservando sus datos (ninguno).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0006_alter_datosnacimiento_id_ciudad_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="GraduadoExamen",
        ),
        migrations.DeleteModel(
            name="Examen",
        ),

        migrations.CreateModel(
            name="Examen",
            fields=[
                (
                    "id_examen",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("acta_respaldatoria", models.CharField(max_length=50)),
                (
                    "tipo_examen",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "fecha_examen",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "codigo_materia",
                    models.ForeignKey(
                        db_column="codigo_materia",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="examenes",
                        to="academico.materia",
                    ),
                ),
            ],
            options={
                "db_table": "EXAMEN",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("acta_respaldatoria", "codigo_materia"),
                        name="uniq_examen_acta_materia",
                    ),
                ],
            },
        ),

        migrations.CreateModel(
            name="GraduadoExamen",
            fields=[
                (
                    "id_graduado_examen",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "id_examen",
                    models.ForeignKey(
                        db_column="id_examen",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resultados_graduados",
                        to="academico.examen",
                    ),
                ),
                (
                    "nota",
                    models.IntegerField(blank=True, null=True),
                ),
                (
                    "resultado",
                    models.CharField(
                        choices=[
                            ("Aprobado", "Aprobado"),
                            ("Reprobado", "Reprobado"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "legajo_graduado",
                    models.ForeignKey(
                        db_column="legajo_graduado",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="examenes",
                        to="academico.graduado",
                    ),
                ),
            ],
            options={
                "db_table": "GRADUADO_EXAMEN",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("id_examen", "legajo_graduado"),
                        name="uniq_graduado_examen",
                    ),
                ],
            },
        ),
    ]
