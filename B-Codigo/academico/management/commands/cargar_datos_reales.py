"""
Reemplaza los datos demo (graduados, escuelas y carreras) por los
datos reales de scripts/datos_reales_*.csv.

Por defecto sólo simula la operación. Para ejecutar:

    python manage.py cargar_datos_reales --apply

Antes de borrar, guarda un respaldo JSON de todas las tablas
afectadas en scripts/respaldo_antes_carga.json.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academico.models import (
    Analitico,
    Auditoria,
    Carrera,
    CarreraResolucion,
    DatosNacimiento,
    DetallePlanEstudios,
    Escuela,
    Examen,
    Graduado,
    GraduadoCarrera,
    GraduadoExamen,
    GrupoOptativo,
    PlanEstudios,
    PlanEstudiosGrupoOptativo,
    PlanEstudiosMateria,
    Resolucion,
    Secundario,
    Titulo,
)

BASE = Path(__file__).resolve().parents[3]
ESCULAS_CSV = BASE / "scripts" / "datos_reales_escuelas.csv"
CARRERAS_CSV = BASE / "scripts" / "datos_reales_carreras.csv"
RESPALDO = BASE / "scripts" / "respaldo_antes_carga.json"

# Orden en que se borran: primero las tablas que referencian
# a las demás. Usuarios, roles, provincias y ciudades NO se tocan.
A_LIMPIAR = [
    Analitico,
    Auditoria,
    GraduadoExamen,
    Examen,
    GraduadoCarrera,
    DatosNacimiento,
    Secundario,
    Graduado,
    PlanEstudiosMateria,
    PlanEstudiosGrupoOptativo,
    GrupoOptativo,
    CarreraResolucion,
    Titulo,
    DetallePlanEstudios,
    PlanEstudios,
    Carrera,
    Resolucion,
    Escuela,
]


def leer_csv(ruta: Path):
    if not ruta.exists():
        raise CommandError(f"No se encontró {ruta}.")

    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


class Command(BaseCommand):
    help = "Reemplaza datos demo por las escuelas y carreras reales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecuta el borrado y la carga (por defecto es dry-run).",
        )
        parser.add_argument(
            "--escuelas",
            default=str(ESCULAS_CSV),
            help="CSV de escuelas.",
        )
        parser.add_argument(
            "--carreras",
            default=str(CARRERAS_CSV),
            help="CSV de carreras.",
        )
        parser.add_argument(
            "--sin-respaldo",
            action="store_true",
            help="No genera el respaldo JSON (no recomendado).",
        )

    def handle(self, *args, **options):
        escuelas = leer_csv(Path(options["escuelas"]))
        carreras = leer_csv(Path(options["carreras"]))

        codigos = [fila["codigo_carrera"].strip() for fila in carreras]
        if len(codigos) != len(set(codigos)):
            raise CommandError("Hay códigos de carrera repetidos en el CSV.")

        ids_escuela = {fila["id_escuela"].strip() for fila in escuelas}
        for fila in carreras:
            if fila["id_escuela"].strip() not in ids_escuela:
                raise CommandError(
                    f"La carrera {fila['codigo_carrera']} referencia una "
                    f"escuela inexistente: {fila['id_escuela']}."
                )

        self.stdout.write(
            f"Escuelas a cargar: {len(escuelas)}. "
            f"Carreras a cargar: {len(carreras)}."
        )
        self.stdout.write(
            f"Datos demo actuales: {Graduado.objects.count()} graduados, "
            f"{Carrera.objects.count()} carreras, "
            f"{Escuela.objects.count()} escuelas."
        )

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no se modificó nada. Ejecutá con --apply."
                )
            )
            return

        if not options["sin_respaldo"]:
            self._respaldar()

        with transaction.atomic():
            for modelo in A_LIMPIAR:
                cantidad = modelo.objects.count()
                modelo.objects.all().delete()
                if cantidad:
                    self.stdout.write(f"  Borrados {cantidad} {modelo.__name__}.")

            for fila in escuelas:
                Escuela.objects.update_or_create(
                    id_escuela=int(fila["id_escuela"]),
                    defaults={
                        "nombre_escuela": fila["nombre_escuela"].strip()
                    },
                )

            for fila in carreras:
                Carrera.objects.update_or_create(
                    codigo_carrera=fila["codigo_carrera"].strip(),
                    defaults={
                        "nombre_carrera": fila["nombre_carrera"].strip(),
                        "id_escuela_id": int(fila["id_escuela"]),
                        "plan_vigente": None,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga completada: {Escuela.objects.count()} escuelas, "
                f"{Carrera.objects.count()} carreras."
            )
        )

    def _respaldar(self):
        datos = []

        for modelo in A_LIMPIAR:
            objetos = modelo.objects.all()
            if objetos.exists():
                datos.extend(serializers.serialize("python", objetos))

        RESPALDO.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        self.stdout.write(f"Respaldo escrito en {RESPALDO.relative_to(BASE)}.")
