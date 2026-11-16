"""
Registro de auditoría de acciones sensibles.

El registro nunca debe romper el flujo principal: si la escritura
falla, se deja constancia en el log y la operación continúa.
"""

import logging

from academico.models import Auditoria


logger = logging.getLogger("academico")


def registrar_auditoria(
    usuario,
    accion,
    entidad="",
    entidad_id="",
    detalle=None,
):
    """Guarda una entrada de auditoría y la devuelve (o None)."""

    try:
        return Auditoria.objects.create(
            id_usuario=usuario if getattr(usuario, "pk", None) else None,
            accion=accion,
            entidad=str(entidad or "")[:100],
            entidad_id=str(entidad_id or "")[:100],
            detalle=detalle or {},
        )
    except Exception:  # pragma: no cover - defensivo
        logger.exception(
            "No se pudo registrar la auditoría de la acción %s",
            accion,
        )
        return None
