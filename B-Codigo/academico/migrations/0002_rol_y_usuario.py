# Migración manual: crea el modelo Rol, renombra
# la contraseña del usuario a codigo_acceso y agrega
# la clave foránea del rol.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Rol",
            fields=[
                (
                    "id_rol",
                    models.AutoField(
                        primary_key=True, serialize=False
                    ),
                ),
                (
                    "nombre_rol",
                    models.CharField(max_length=100, unique=True),
                ),
                (
                    "puede_administrar",
                    models.BooleanField(default=False),
                ),
            ],
            options={
                "db_table": "ROL",
            },
        ),
        migrations.RenameField(
            model_name="usuario",
            old_name="contrasenia",
            new_name="codigo_acceso",
        ),
        migrations.AddField(
            model_name="usuario",
            name="id_rol",
            field=models.ForeignKey(
                db_column="id_rol",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="usuarios",
                to="academico.rol",
            ),
        ),
    ]
