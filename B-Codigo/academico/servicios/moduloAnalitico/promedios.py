"""
Cálculo de los promedios de un graduado para una carrera.

Reglas acordadas:

* **Con aplazo**: se promedian todas las notas de exámenes rendidos
  (aprobados y reprobados), excepto las equivalencias y las materias
  marcadas como requisito. Los exámenes sin nota no se pueden
  promediar y se informan como advertencia.
* **Sin aplazo (general)**: se promedian sólo los exámenes aprobados,
  una única vez por materia, excluyendo las equivalencias y las
  materias marcadas como requisito. Si una materia tiene más de una
  aprobación se usa la más reciente (desempate: la nota mayor) y se
  advierte.
* Las equivalencias nunca se promedian, tengan nota o no.
* El requisito es un dato del examen (``es_requisito``), no del plan
  de estudios. El plan no participa del cálculo.
* Si no hay notas para promediar se devuelve ``None`` (nunca se
  divide por cero).

El servicio no guarda nada: devuelve el resultado y el detalle para
que la vista decida qué persistir y qué auditar.
"""

from dataclasses import dataclass, field
from datetime import datetime
import re
import unicodedata

from academico.models import (
    GraduadoExamen,
    ResultadoExamen,
)


NOTA_MINIMA_APROBADO = 6

# Diferencia aceptada al comparar el promedio calculado con el valor
# que llega del formulario (evita falsos «manual» por redondeo).
TOLERANCIA_PROMEDIO = 0.005


@dataclass
class ResultadoPromedios:
    promedio_con_aplazo: float | None = None
    promedio_sin_aplazo: float | None = None
    advertencias: list = field(default_factory=list)
    duplicados: list = field(default_factory=list)
    equivalencias_sin_nota: list = field(default_factory=list)
    equivalencias_excluidas: list = field(default_factory=list)
    examenes_sin_nota: int = 0
    detalle: dict = field(default_factory=dict)


def _promedio(notas):
    if not notas:
        return None

    return round(sum(notas) / len(notas), 2)


def _es_aprobado(nota, resultado):
    if nota is not None:
        return nota >= NOTA_MINIMA_APROBADO

    return resultado == ResultadoExamen.APROBADO


def _es_equivalencia(tipo):
    return str(tipo or "").strip().lower().startswith("equivalencia")


def _clave_materia(codigo):
    return str(codigo or "").strip()


def _normalizar_nombre(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _clave_fecha(examen):
    """
    Clave comparable para ordenar por fecha.

    Desde la base llega un ``date``; desde la previsualización llega
    texto ISO (o, en archivos importados, ``dd-mm-aaaa``).
    """

    fecha = examen.get("fecha_examen")

    if hasattr(fecha, "toordinal"):
        return fecha.toordinal()

    if isinstance(fecha, str):
        texto = fecha.strip()

        for formato in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto, formato).toordinal()
            except ValueError:
                pass

    try:
        return int(fecha)
    except (TypeError, ValueError):
        return 0


def calcular_promedios(dni, carrera, examenes=None):
    """
    Calcula los promedios de ``dni`` en ``carrera``.

    ``examenes`` permite calcular a partir de una lista de filas aún
    no persistidas (preview). Cada fila debe tener ``nota``,
    ``materia_codigo``, ``resultado`` (opcional), ``tipo`` (opcional),
    ``fecha_examen`` (opcional) y ``acta_respaldatoria`` (opcional).
    Si se omite, se leen los exámenes guardados.
    """

    if examenes is None:
        examenes = [
            {
                "nota": fila.nota,
                "materia_codigo": fila.id_examen.codigo_materia_id,
                "resultado": fila.resultado,
                "tipo": fila.id_examen.tipo_examen,
                "fecha_examen": fila.id_examen.fecha_examen,
                "acta_respaldatoria": fila.id_examen.acta_respaldatoria,
                "nombre_materia": (
                    fila.id_examen.codigo_materia.nombre_materia
                ),
                "es_requisito": fila.es_requisito,
            }
            for fila in (
                GraduadoExamen.objects
                .filter(
                    dni_graduado=dni,
                    codigo_carrera=carrera,
                )
                .select_related("id_examen", "id_examen__codigo_materia")
            )
        ]

    resultado = ResultadoPromedios()

    notas_con_aplazo = []
    aprobados_por_materia = {}

    for examen in examenes:
        nota = examen.get("nota")
        codigo = _clave_materia(examen.get("materia_codigo"))
        nombre = examen.get("nombre_materia")
        tipo = examen.get("tipo")
        resultado_examen = examen.get("resultado")

        # Las equivalencias nunca se promedian (con o sin nota).
        if _es_equivalencia(tipo):
            resultado.equivalencias_excluidas.append(
                codigo or _normalizar_nombre(nombre) or "sin código"
            )

            if nota is None:
                resultado.equivalencias_sin_nota.append(
                    codigo or "sin código"
                )
                resultado.advertencias.append(
                    "La equivalencia de "
                    f"«{codigo or 'materia sin código'}» no tiene nota "
                    "y no se incluyó en los promedios."
                )

            continue

        # Las materias marcadas como requisito no participan de
        # ningún promedio.
        if examen.get("es_requisito"):
            continue

        if nota is None:
            resultado.examenes_sin_nota += 1
            continue

        notas_con_aplazo.append(nota)

        if not _es_aprobado(nota, resultado_examen):
            continue

        clave_agrupacion = codigo or _normalizar_nombre(nombre)
        aprobados_por_materia.setdefault(clave_agrupacion, []).append(examen)

    resultado.promedio_con_aplazo = _promedio(notas_con_aplazo)

    if resultado.examenes_sin_nota:
        resultado.advertencias.append(
            f"{resultado.examenes_sin_nota} examen(es) sin nota no se "
            "incluyeron en el promedio con aplazo."
        )

    notas_sin_aplazo = []

    for codigo, aprobados in aprobados_por_materia.items():
        if len(aprobados) > 1:
            # Más reciente por fecha; desempate por nota mayor.
            aprobados = sorted(
                aprobados,
                key=lambda examen: (
                    _clave_fecha(examen),
                    examen.get("nota") or 0,
                ),
                reverse=True,
            )

            resultado.duplicados.append({
                "materia_codigo": codigo,
                "intentos": len(aprobados),
                "nota_elegida": aprobados[0].get("nota"),
                "nota_descartada": aprobados[1].get("nota"),
            })
            resultado.advertencias.append(
                f"La materia «{codigo}» tiene {len(aprobados)} "
                "aprobaciones; se usó la más reciente "
                f"(nota {aprobados[0].get('nota')})."
            )

        notas_sin_aplazo.append(aprobados[0].get("nota"))

    resultado.promedio_sin_aplazo = _promedio(notas_sin_aplazo)

    if (
        resultado.promedio_sin_aplazo is None
        and resultado.promedio_con_aplazo is not None
    ):
        resultado.advertencias.append(
            "No hay materias aprobadas para calcular el promedio "
            "general (sin aplazo); sólo se informa el promedio con "
            "aplazo."
        )

    resultado.detalle = {
        "con_aplazo": {
            "notas": notas_con_aplazo,
            "cantidad": len(notas_con_aplazo),
        },
        "sin_aplazo": {
            "notas": notas_sin_aplazo,
            "cantidad": len(notas_sin_aplazo),
            "materias": sorted(aprobados_por_materia),
        },
        "examenes_sin_nota": resultado.examenes_sin_nota,
        "equivalencias_excluidas": resultado.equivalencias_excluidas,
    }

    return resultado


def promedios_desde_filas(filas, carrera):
    """
    Calcula los promedios a partir de las filas del formulario de
    previsualización (todavía no persistidas).
    """

    examenes = []

    for fila in filas:
        nota = fila.get("nota")

        if nota is not None:
            resultado = (
                ResultadoExamen.APROBADO
                if nota >= NOTA_MINIMA_APROBADO
                else ResultadoExamen.REPROBADO
            )
        else:
            resultado = None

        examenes.append({
            "nota": nota,
            "materia_codigo": fila.get("materia_codigo"),
            "nombre_materia": (
                fila.get("nombre_materia") or fila.get("espacio")
            ),
            "resultado": resultado,
            "tipo": fila.get("tipo"),
            "fecha_examen": fila.get("fecha_examen"),
            "anio_cursado": fila.get("anio") or fila.get("anio_cursado"),
            "acta_respaldatoria": fila.get("acta_respaldatoria"),
            "es_requisito": bool(fila.get("es_requisito")),
        })

    return calcular_promedios(None, carrera, examenes=examenes)


def mismo_promedio(valor_a, valor_b):
    """True si dos promedios son equivalentes (tolerancia de redondeo)."""

    if valor_a is None or valor_b is None:
        return valor_a is None and valor_b is None

    return abs(float(valor_a) - float(valor_b)) <= TOLERANCIA_PROMEDIO
