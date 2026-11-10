"""
Vincula cada fila de GRADUADO_EXAMEN a una carrera concreta
(legajo + carrera). Antes sólo se vinculaba por legajo, lo que
permitía que las notas de una carrera aparecieran en otra.

Las 49 filas existentes pertenecen al graduado 1-46189053/24 y
vienen del certificado Lincoln de la carrera LSI (Sistemas), así
que se asignan a LSI en el backfill y luego la columna queda
obligatoria.
"""

from django.db import migrations, models
import django.db.models.deletion


def backfill_carrera(apps, schema_editor):
    GraduadoExamen = apps.get_model("academico", "GraduadoExamen")
    GraduadoExamen.objects.filter(codigo_carrera_id=None).update(
        codigo_carrera_id="LSI"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0007_examen_id_examen"),
    ]

    operations = [
        migrations.AddField(
            model_name="GraduadoExamen",
            name="codigo_carrera",
            field=models.ForeignKey(
                db_column="codigo_carrera",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="examenes_carrera",
                to="academico.carrera",
            ),
        ),
        migrations.RunPython(backfill_carrera, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="GraduadoExamen",
            name="codigo_carrera",
            field=models.ForeignKey(
                db_column="codigo_carrera",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="examenes_carrera",
                to="academico.carrera",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="GraduadoExamen",
            name="uniq_graduado_examen",
        ),
        migrations.AddConstraint(
            model_name="GraduadoExamen",
            constraint=models.UniqueConstraint(
                fields=("id_examen", "legajo_graduado", "codigo_carrera"),
                name="uniq_graduado_examen",
            ),
        ),
    ]
