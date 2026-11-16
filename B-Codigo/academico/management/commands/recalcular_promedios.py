"""
Recalcula los promedios de los graduados a partir de sus exámenes.

Se usa una única vez después de desplegar el cálculo automático de
promedios, para completar los registros que quedaron con el valor
importado del Excel.

Reglas:

* Los promedios con origen ``manual`` se conservan intactos (son
  ediciones deliberadas del usuario).
* Si el cálculo no devuelve un valor (sin exámenes promediables) se
  conserva el valor actual.
* Cada cambio se registra en la auditoría.

Uso:
    python manage.py recalcular_promedios
    python manage.py recalcular_promedios --legajo 1234
    python manage.py recalcular_promedios --carrera 12 --dry-run
"""

from django.core.management.base import BaseCommand

from academico.models import (
    GraduadoCarrera,
    OrigenPromedio,
)
from academico.servicios.auditoria import registrar_auditoria
from academico.servicios.moduloAnalitico.promedios import (
    calcular_promedios,
    mismo_promedio,
)


class Command(BaseCommand):
    help = "Recalcula los promedios de los graduados desde sus exámenes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--legajo",
            help="Limita el recálculo a un legajo.",
        )
        parser.add_argument(
            "--carrera",
            help="Limita el recálculo a una carrera.",
        )
        parser.add_argument(
            "--incluir-manuales",
            action="store_true",
            help=(
                "También recalcula los promedios editados a mano "
                "(por defecto se respetan)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los cambios sin guardarlos.",
        )

    def handle(self, *args, **options):
        filas = GraduadoCarrera.objects.select_related(
            "legajo_graduado",
            "codigo_carrera",
        ).order_by("legajo_graduado_id", "codigo_carrera_id")

        legajo = (options.get("legajo") or "").strip()

        if legajo:
            filas = filas.filter(legajo_graduado_id=legajo)

        carrera = (options.get("carrera") or "").strip()

        if carrera:
            filas = filas.filter(codigo_carrera_id=carrera)

        incluir_manuales = options.get("incluir_manuales", False)
        dry_run = options.get("dry_run", False)

        actualizados = 0
        omitidos_manual = 0
        sin_calculo = 0
        sin_cambios = 0

        for fila in filas.iterator(chunk_size=200):
            origenes = (
                fila.origen_promedio_sin_aplazo,
                fila.origen_promedio_con_aplazo,
            )

            if (
                not incluir_manuales
                and OrigenPromedio.MANUAL in origenes
            ):
                omitidos_manual += 1
                continue

            calculado = calcular_promedios(
                fila.legajo_graduado_id,
                fila.codigo_carrera_id,
            )

            nuevos = {}

            for campo, origen_campo, valor_calc in (
                (
                    "promedio_sin_aplazo",
                    "origen_promedio_sin_aplazo",
                    calculado.promedio_sin_aplazo,
                ),
                (
                    "promedio_con_aplazo",
                    "origen_promedio_con_aplazo",
                    calculado.promedio_con_aplazo,
                ),
            ):
                if (
                    not incluir_manuales
                    and getattr(fila, origen_campo) == OrigenPromedio.MANUAL
                ):
                    continue

                valor_actual = getattr(fila, campo)

                if valor_calc is None:
                    continue

                if mismo_promedio(valor_actual, valor_calc):
                    # Ya está calculado y coincide: sólo se corrige
                    # el origen si quedó marcado como importado.
                    if getattr(fila, origen_campo) != OrigenPromedio.CALCULADO:
                        nuevos[origen_campo] = OrigenPromedio.CALCULADO

                    continue

                nuevos[campo] = valor_calc
                nuevos[origen_campo] = OrigenPromedio.CALCULADO

            if not nuevos:
                if (
                    calculado.promedio_sin_aplazo is None
                    and calculado.promedio_con_aplazo is None
                ):
                    sin_calculo += 1
                else:
                    sin_cambios += 1

                continue

            self.stdout.write(
                f"Legajo {fila.legajo_graduado_id} / "
                f"carrera {fila.codigo_carrera_id}: "
                f"sin aplazo {fila.promedio_sin_aplazo} -> "
                f"{nuevos.get('promedio_sin_aplazo', fila.promedio_sin_aplazo)}; "
                f"con aplazo {fila.promedio_con_aplazo} -> "
                f"{nuevos.get('promedio_con_aplazo', fila.promedio_con_aplazo)}"
            )

            for advertencia in calculado.advertencias:
                self.stdout.write(f"  advertencia: {advertencia}")

            actualizados += 1

            if dry_run:
                continue

            for campo, valor in nuevos.items():
                setattr(fila, campo, valor)

            fila.save(update_fields=list(nuevos))

            registrar_auditoria(
                None,
                "promedios_recalculados",
                entidad="GraduadoCarrera",
                entidad_id=(
                    f"{fila.legajo_graduado_id}|{fila.codigo_carrera_id}"
                ),
                detalle={
                    "campos": {
                        campo: (
                            str(valor)
                            if campo.startswith("origen_")
                            else valor
                        )
                        for campo, valor in nuevos.items()
                    },
                    "advertencias": calculado.advertencias,
                },
            )

        prefijo = "[dry-run] " if dry_run else ""

        self.stdout.write(
            self.style.SUCCESS(
                f"{prefijo}Filas actualizadas: {actualizados}. "
                f"Sin cambios: {sin_cambios}. "
                f"Sin datos para calcular: {sin_calculo}. "
                f"Omitidas por promedio manual: {omitidos_manual}."
            )
        )
