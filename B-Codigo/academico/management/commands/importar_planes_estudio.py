"""
Importa planes de estudio y sus materias desde los CSV revisables.

Uso típico:

    python manage.py importar_planes_estudio
    python manage.py importar_planes_estudio --apply

Por defecto es dry-run. Los CSV se generan con:

    python scripts/preparar_carga.py
    python scripts/extraer_materias.py
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academico.models import (
    Carrera,
    DetallePlanEstudios,
    Materia,
    PlanEstudios,
    PlanEstudiosMateria,
    TipoPlanEstudios,
)

BASE = Path(__file__).resolve().parents[3]
CATALOGO = BASE / "scripts" / "planes_estudio_catalogo.csv"
MATERIAS = BASE / "scripts" / "materias_por_plan.csv"
DIRECTORIO_PDF = BASE / "PlanesEstudio"


def leer_csv(ruta: Path):
    if not ruta.exists():
        raise CommandError(f"No se encontró {ruta}.")

    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def normalizar_nombre(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def entero(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def clave_cuatrimestre(valor):
    texto = str(valor or "").strip().upper()

    if not texto:
        return None

    if texto.startswith("1") or texto.startswith("PRIMERO"):
        return "1er"

    if texto.startswith("2") or texto.startswith("SEGUNDO"):
        return "2do"

    if texto == "A" or "ANUAL" in texto:
        return "A"

    return None


def es_requisito(valor):
    return str(valor or "").strip().upper() in {"SI", "S", "TRUE", "1", "YES"}


class Command(BaseCommand):
    help = "Importa planes, metadatos y materias desde CSV revisables."

    def add_arguments(self, parser):
        parser.add_argument("--catalogo", default=str(CATALOGO))
        parser.add_argument("--materias", default=str(MATERIAS))
        parser.add_argument("--directorio", default=str(DIRECTORIO_PDF))
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecuta la carga (por defecto es dry-run).",
        )
        parser.add_argument("--solo-catalogo", action="store_true")
        parser.add_argument("--solo-materias", action="store_true")
        parser.add_argument(
            "--no-copiar-pdfs",
            action="store_true",
            help="No copia los PDF a media/ (guarda sólo la ruta original).",
        )

    def handle(self, *args, **options):
        catalogo = leer_csv(Path(options["catalogo"]))
        directorio = Path(options["directorio"])
        aplicar = options["apply"]

        if options["solo_materias"]:
            planes = {
                plan.codigo_plan: plan for plan in PlanEstudios.objects.all()
            }
            por_archivo = {}
            modificatorias = {}
        else:
            planes, por_archivo, modificatorias = self._cargar_catalogo(
                catalogo, directorio, aplicar, options["no_copiar_pdfs"]
            )

        if not options["solo_catalogo"]:
            filas_materias = leer_csv(Path(options["materias"]))
            self._cargar_materias(
                filas_materias,
                planes,
                por_archivo,
                catalogo,
                aplicar,
            )

        if not aplicar:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no se modificó nada. Ejecutá con --apply."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Importación completada."))

    def _cargar_catalogo(self, catalogo, directorio, aplicar, no_copiar):
        planes = {}
        por_archivo = {}
        modificatorias = {}
        creados = actualizados = 0
        vigentes = {}

        with transaction.atomic() if aplicar else _noop():
            for fila in catalogo:
                tipo = fila["tipo"].strip().upper()

                if tipo in {"NO_PLAN", "DUPLICADO"}:
                    continue

                carrera_codigo = fila["codigo_carrera"].strip()
                anio = entero(fila["anio"])

                if tipo == "MODIFICATORIA":
                    modificatorias.setdefault(
                        (carrera_codigo, anio), []
                    ).append(fila.get("resolucion", ""))
                    continue

                if not Carrera.objects.filter(
                    codigo_carrera=carrera_codigo
                ).exists():
                    raise CommandError(
                        f"No existe la carrera {carrera_codigo} "
                        f"({fila['archivo']}). Cargá primero los datos reales."
                    )

                codigo_plan = fila["codigo_plan"].strip()
                if not codigo_plan:
                    codigo_plan = f"{carrera_codigo}-{anio}"

                valores_plan = {
                    "codigo_carrera_id": carrera_codigo,
                }
                if aplicar:
                    plan, creado = PlanEstudios.objects.update_or_create(
                        codigo_plan=codigo_plan,
                        defaults=valores_plan,
                    )
                    if creado:
                        creados += 1
                    else:
                        actualizados += 1
                else:
                    plan = PlanEstudios(
                        codigo_plan=codigo_plan,
                        codigo_carrera_id=carrera_codigo,
                    )
                    creado = not PlanEstudios.objects.filter(
                        codigo_plan=codigo_plan
                    ).exists()

                planes[codigo_plan] = plan
                por_archivo[fila["archivo_real"]] = codigo_plan

                resolucion = fila.get("resolucion", "").strip()
                observaciones = fila.get("observaciones", "").strip()

                tipo_detalle = (
                    TipoPlanEstudios.VIGENTE
                    if fila.get("vigente", "").strip().upper() == "SI"
                    else TipoPlanEstudios.HISTORICO
                )

                archivo_relativo = ""

                if not no_copiar and fila.get("archivo_real"):
                    ruta_origen = directorio / fila["archivo_real"]

                    if not ruta_origen.exists():
                        raise CommandError(
                            f"No se encontró el PDF {ruta_origen}."
                        )

                    if aplicar:
                        archivo_relativo = self._copiar_pdf(
                            ruta_origen,
                            fila["hash_sha256"],
                        )
                    else:
                        archivo_relativo = (
                            "planes_estudio/"
                            + fila["hash_sha256"][:10]
                            + "_"
                            + fila["archivo_real"]
                        )

                if aplicar:
                    DetallePlanEstudios.objects.update_or_create(
                        codigo_plan=plan,
                        defaults={
                            "anio": anio,
                            "tipo": tipo_detalle,
                            "archivo": archivo_relativo,
                            "nombre_original": fila["archivo_real"],
                            "hash_archivo": fila.get("hash_sha256", ""),
                            "resolucion": resolucion,
                            "observaciones": observaciones,
                        },
                    )

                if tipo_detalle == TipoPlanEstudios.VIGENTE:
                    vigentes[carrera_codigo] = plan

            if aplicar:
                for carrera_codigo, plan in vigentes.items():
                    Carrera.objects.filter(
                        codigo_carrera=carrera_codigo
                    ).update(plan_vigente=plan)

        self.stdout.write(
            f"Planes: {creados} creados, {actualizados} actualizados, "
            f"{len(vigentes)} vigentes, "
            f"{len(modificatorias)} grupos de modificatorias."
        )

        return planes, por_archivo, modificatorias

    def _copiar_pdf(self, ruta_origen, hash_sha256):
        nombre = (
            "planes_estudio/"
            + hash_sha256[:10]
            + "_"
            + ruta_origen.name.replace("?", "")
        )

        if default_storage.exists(nombre):
            return nombre

        with ruta_origen.open("rb") as archivo:
            return default_storage.save(nombre, File(archivo))

    def _cargar_materias(
        self,
        filas,
        planes,
        por_archivo,
        catalogo,
        aplicar,
    ):
        if not filas:
            self.stdout.write("No hay filas de materias para cargar.")
            return

        # El CSV de extracción puede tener códigos viejos si se
        # regeneró el catálogo; el nombre de archivo es la fuente
        # confiable para identificar el plan.
        codigos_por_archivo = {
            fila["archivo_real"]: fila["codigo_plan"]
            for fila in catalogo
        }

        materias = {}
        codigos_usados = set()

        for materia in Materia.objects.all():
            materias[normalizar_nombre(materia.nombre_materia)] = materia
            codigos_usados.add(materia.codigo_materia)

        contador = 1
        creadas = 0
        asociadas = 0
        omitidas = 0
        errores = []

        with transaction.atomic() if aplicar else _noop():
            for indice, fila in enumerate(filas, start=2):
                nombre = fila.get("nombre_materia", "").strip()

                if not nombre:
                    omitidas += 1
                    continue

                codigo_plan = (
                    codigos_por_archivo.get(fila.get("archivo", ""))
                    or fila.get("codigo_plan", "")
                )

                if codigo_plan not in planes:
                    errores.append(
                        f"Fila {indice}: plan «{codigo_plan}» inexistente."
                    )
                    continue

                clave = normalizar_nombre(nombre)
                materia = materias.get(clave)

                if materia is None:
                    while f"GEN-{contador:05d}" in codigos_usados:
                        contador += 1
                    codigo = f"GEN-{contador:05d}"
                    contador += 1
                    codigos_usados.add(codigo)

                    if aplicar:
                        materia = Materia.objects.create(
                            codigo_materia=codigo,
                            nombre_materia=nombre,
                        )
                        creadas += 1
                    else:
                        materia = Materia(
                            codigo_materia=codigo,
                            nombre_materia=nombre,
                        )

                    materias[clave] = materia

                anio = entero(fila.get("anio_materia"))
                orden = entero(fila.get("orden_materia")) or indice

                defaults = {
                    "anio_materia": anio,
                    "cuatrimestre_materia": clave_cuatrimestre(
                        fila.get("cuatrimestre_materia")
                    ),
                    "orden_materia": orden,
                    "materia_requisito": es_requisito(
                        fila.get("materia_requisito")
                    ),
                }

                if aplicar:
                    PlanEstudiosMateria.objects.update_or_create(
                        codigo_plan=planes[codigo_plan],
                        codigo_materia=materia,
                        defaults=defaults,
                    )
                    asociadas += 1

        self.stdout.write(
            f"Materias: {creadas} creadas, {asociadas} asociadas a planes, "
            f"{omitidas} filas vacías omitidas."
        )

        for error in errores[:20]:
            self.stdout.write(self.style.ERROR(error))

        if len(errores) > 20:
            self.stdout.write(
                self.style.ERROR(f"... y {len(errores) - 20} errores más.")
            )


class _noop:
    """Context manager vacío para no repetir el branch de dry-run."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
