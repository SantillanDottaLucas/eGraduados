"""
Crea los roles base del sistema (Administrador y Titulos) y,
opcionalmente, un usuario administrador inicial.

Uso:
    python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Nombre"

Los valores también pueden definirse en el entorno (o en .env):

    EGRADUADOS_ADMIN_EMAIL=admin@gmail.com
    EGRADUADOS_ADMIN_NOMBRE=Administrador

Los argumentos de línea de comandos tienen prioridad. Si no hay
email, sólo se crean o actualizan los roles. El código aleatorio
de 6 caracteres se guarda hasheado y se imprime una única vez.
"""

import os

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from academico.autenticacion import (
    codigo_valido,
    generar_codigo_acceso,
)
from academico.models import Rol, Usuario


ROLES_BASE = [
    ("Administrador", True),
    ("Titulos", False),
]


class Command(BaseCommand):
    help = (
        "Crea los roles base y un usuario administrador inicial."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=os.environ.get("EGRADUADOS_ADMIN_EMAIL", "").strip(),
            help=(
                "Email de Gmail del administrador. Por defecto:"
                " EGRADUADOS_ADMIN_EMAIL."
            ),
        )
        parser.add_argument(
            "--nombre",
            default=(
                os.environ.get("EGRADUADOS_ADMIN_NOMBRE", "").strip()
                or "Administrador"
            ),
            help=(
                "Nombre visible del usuario. Por defecto:"
                " EGRADUADOS_ADMIN_NOMBRE o 'Administrador'."
            ),
        )

    def handle(self, *args, **options):
        # 1. Crear o actualizar los roles base.
        for nombre, puede_administrar in ROLES_BASE:
            rol, creado = Rol.objects.update_or_create(
                nombre_rol=nombre,
                defaults={"puede_administrar": puede_administrar},
            )

            estado = "creado" if creado else "actualizado"
            self.stdout.write(
                f"Rol {rol.nombre_rol}: {estado}."
            )

        email = (options.get("email") or "").strip().lower()
        nombre = (options.get("nombre") or "Administrador").strip()

        if not email:
            self.stdout.write(
                self.style.SUCCESS(
                    "Roles listos. Para crear un usuario admin "
                    "ejecutá el comando con --email."
                )
            )
            return

        if not email.endswith("@gmail.com"):
            raise CommandError(
                "El email debe ser una cuenta de Gmail (@gmail.com)."
            )

        rol_admin = Rol.objects.get(nombre_rol="Administrador")

        if Usuario.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f"Ya existe un usuario con el email {email}."
            )

        codigo = generar_codigo_acceso()

        if not codigo_valido(codigo):
            raise CommandError(
                "No se pudo generar un código válido."
            )

        Usuario.objects.create(
            nombre_usuario=nombre,
            email=email,
            codigo_acceso=make_password(codigo),
            id_rol=rol_admin,
        )

        self.stdout.write(self.style.SUCCESS(""))
        self.stdout.write(
            self.style.SUCCESS("Usuario administrador creado.")
        )
        self.stdout.write(f"  Email:  {email}")
        self.stdout.write(f"  Nombre: {nombre}")
        self.stdout.write(f"  Rol:    Administrador")
        self.stdout.write(
            self.style.WARNING(
                f"  Código: {codigo}  "
                "(copialo ahora; se muestra una sola vez)"
            )
        )
