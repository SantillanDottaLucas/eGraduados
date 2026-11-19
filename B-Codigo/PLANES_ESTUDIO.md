# Planes de estudio y materias

Este documento describe cómo se cargan los planes de estudio reales
de UNPA (PDFs en `PlanesEstudio/`) y sus materias, reemplazando los
datos demo de la base.

## Artefactos editables

Antes de tocar la base se generan archivos CSV/SQL que **se pueden
y deben revisar a mano**:

| Archivo | Contenido |
|---|---|
| `scripts/datos_reales_escuelas.csv` | 13 escuelas reales |
| `scripts/datos_reales_carreras.csv` | 27 carreras reales |
| `scripts/datos_reales.sql` | Versión SQL de lo anterior |
| `scripts/planes_estudio_catalogo.csv` | 40 documentos (36 planes, 3 modificatorias, 1 no-plan) |
| `scripts/plan_duplicados.csv` | 3 PDFs duplicados exactos (por hash) |
| `scripts/materias_por_plan.csv` | Materias extraídas, con año/cuatrimestre/orden |
| `scripts/extraccion_reporte.csv` | Resumen por PDF (método, cantidad, años, cuatris) |

Se regeneran con:

```powershell
& '.\venv\Scripts\python.exe' scripts\preparar_carga.py --forzar
& '.\venv\Scripts\python.exe' scripts\extraer_materias.py --forzar --max-paginas 14
```

`--forzar` es necesario para sobrescribir archivos ya existentes
(protección para no perder revisiones manuales).

## Criterios del catálogo

- **Vigente** = año más alto del plan dentro de cada carrera.
- Desempate en `913` (ambos de 2001): se prefiere la versión **sin**
  homologación.
- Las modificatorias de `072` (Res. 159/23, 160/23 y 163/23) se
  registran como metadatos, no como planes separados.
- `401` (Programa de Movilidad Estudiantil) se marca `NO_PLAN`.
- Los 3 duplicados por hash se excluyen.
- Los PDFs se copian a `media/planes_estudio/` y se guarda la ruta y
  el hash SHA-256 en `DetallePlanEstudios`.

## Extracción de materias

`scripts/extraer_materias.py` usa PyMuPDF para PDFs con texto y
RapidOCR para los escaneados. El parser es **posicional**: procesa
los items `(x, y, texto)` en orden de coordenada Y, actualizando el
contexto de año/cuatrimestre cuando encuentra un encabezado, y arma
cada fila juntando el número de orden con el nombre a su derecha.

Puntos a revisar en `materias_por_plan.csv`:

- **Nombres con errores de OCR**: se corrigen a mano en el CSV.
- **`materia_requisito`**: hoy sale `NO` para todas; completar `SI`
  en las que corresponda (el promedio "sin aplazo" las excluye).
- **`anio_materia` / `cuatrimestre_materia`**: `A` = anual,
  `1er` / `2do` = cuatrimestre.
- **Páginas sin planilla cronológica**: algunos PDFs traen primero
  tablas por áreas temáticas (sin números de orden); el parser las
  ignora y toma la planilla con "PRIMER AÑO / SEGUNDO AÑO…".

Los códigos de materias son genéricos por ahora: `GEN-00001`, etc.

## Modelo de datos

- `DetallePlanEstudios` (OneToOne con `PlanEstudios`): año, tipo
  (`VIGENTE`/`HISTORICO`/`MODIFICATORIA`), PDF, hash, resolución y
  observaciones.
- `Carrera.plan_vigente` (OneToOne): garantiza un único plan vigente
  por carrera en MySQL.
- La UI en **Gestión Académica → Carreras** permite cambiar el plan
  vigente; al hacerlo se actualiza también `DetallePlanEstudios.tipo`.

## Carga en la base

La base destino es MySQL (configurada en `.env`). Los comandos son
**dry-run por defecto**:

```powershell
& '.\venv\Scripts\python.exe' manage.py migrate
& '.\venv\Scripts\python.exe' manage.py cargar_datos_reales
& '.\venv\Scripts\python.exe' manage.py cargar_datos_reales --apply
& '.\venv\Scripts\python.exe' manage.py importar_planes_estudio
& '.\venv\Scripts\python.exe' manage.py importar_planes_estudio --apply
```

`cargar_datos_reales` guarda un respaldo JSON en
`scripts/respaldo_antes_carga.json` antes de borrar. No toca
`Usuario`, `Rol`, `Provincia` ni `Ciudad`.

## Analíticos y promedios

- El orden de los exámenes y el match con el Lincoln usan el plan
  vigente de la carrera.
- **Promedio sin aplazo**: sólo aprobados (nota ≥ 6), una vez por
  materia, excluyendo las materias requisito del plan.
- **Promedio con aplazo**: todas las notas (aprobadas y reprobadas),
  incluidas las materias requisito y equivalencias con nota.
- Si el Lincoln tiene asignaturas que no coinciden con el plan, se
  muestra una **aclaración** en pantalla y hay que seleccionar la
  materia equivalente en cada fila para poder validar.
