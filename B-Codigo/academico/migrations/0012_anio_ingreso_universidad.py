from datetime import date

from django.db import migrations, models


def anio_desde_fecha(apps, schema_editor):
    """Conserva únicamente el año de la fecha de ingreso original."""

    Graduado = apps.get_model("academico", "Graduado")

    for graduado in Graduado.objects.all().iterator():
        fecha = getattr(graduado, "fecha_ingreso_universidad", None)

        if fecha is not None:
            graduado.anio_ingreso_universidad = fecha.year
            graduado.save(update_fields=["anio_ingreso_universidad"])


def fecha_desde_anio(apps, schema_editor):
    """
    Rollback: reconstruye una fecha a partir del año.

    El día y el mes originales ya no existen: se usa el 1 de marzo
    (mismo criterio que el generador de analíticos).
    """

    Graduado = apps.get_model("academico", "Graduado")

    for graduado in Graduado.objects.all().iterator():
        anio = graduado.anio_ingreso_universidad

        if not anio or not 1900 <= anio <= 2100:
            continue

        graduado.fecha_ingreso_universidad = date(anio, 3, 1)
        graduado.save(update_fields=["fecha_ingreso_universidad"])


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0011_graduadoexamen_requisito_anio_orden"),
    ]

    operations = [
        migrations.AlterField(
            model_name="graduado",
            name="fecha_ingreso_universidad",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="graduado",
            name="anio_ingreso_universidad",
            field=models.IntegerField(null=True),
        ),
        migrations.RunPython(anio_desde_fecha, fecha_desde_anio),
        migrations.RemoveField(
            model_name="graduado",
            name="fecha_ingreso_universidad",
        ),
        migrations.AlterField(
            model_name="graduado",
            name="anio_ingreso_universidad",
            field=models.IntegerField(),
        ),
    ]
