# Planes de estudio y materias

Los planes de estudio y las materias ya están cargados en MySQL. La carga
se aplicó el **2026-11-22** desde el Excel de construcción, que reemplazó a
los datos de ejemplo y al antiguo flujo de extracción desde PDF.

## Estado actual de la base

| Tabla | Registros |
|---|---:|
| `CARRERA` | 30 |
| `PLAN_ESTUDIOS` | 28 |
| `DETALLE_PLAN_ESTUDIOS` | 28 |
| `MATERIA` | 499 |
| `PLAN_ESTUDIOS_MATERIA` | 850 |
| `EXAMEN` | 18 (sin cambios) |

`MATERIA` incluye 498 códigos del Excel más `453`
(`Idioma Moderno (Inglés)`), que no figura en el Excel pero sigue referida
por un examen y por eso se conserva. Hay 30 nombres con más de un código
real (por ejemplo `Análisis y Diseño de Software` → `1658`, `2706`), y
ningún código con más de un nombre.

Las carreras sin plan vigente son `046`, `047`, `085` y `915`.

## Archivos fuente y respaldo

- Excel de origen: `..\A-Documentacion\C-Construccion\eGraduados_Construccion_PlanesEstudio.xlsx`
  (29 hojas, 856 filas de materias).
- Respaldo de la base anterior a la carga:
  `C:\Users\Usuario\Documents\eGraduados\backups\respaldo_antes_planes_excel_2026-11-22.sql`.

**No hay script de recarga en el repositorio.** Los scripts, CSV y SQL
intermedios usados para la carga se eliminaron después de aplicarla; si
hace falta una nueva carga, se genera desde el Excel y se valida antes de
ejecutarla. El respaldo indicado arriba permite volver al estado previo.

## Modelo de datos

- `DetallePlanEstudios` (OneToOne con `PlanEstudios`): año, tipo
  (`VIGENTE`/`HISTORICO`/`MODIFICATORIA`), PDF, hash, resolución y
  observaciones.
- `Carrera.plan_vigente` (OneToOne): garantiza un único plan vigente
  por carrera en MySQL.
- La UI en **Gestión Académica → Carreras** permite cambiar el plan
  vigente; al hacerlo se actualiza también `DetallePlanEstudios.tipo`.

## Analíticos y promedios

Cada fila del Lincoln se contrasta con `PlanEstudiosMateria` del plan
**vigente** de la carrera (`Carrera.plan_vigente`):

- Se compara el código leído del Lincoln (numérico con 4 cifras,
  `901` → `0901`) y el nombre normalizado (sin acentos, caso ni espacios).
  El aviso muestra siempre los valores originales del certificado.
- Estados posibles: `ok`, `nombre_distinto` (el código está en el plan
  pero el nombre no), `codigo_no_en_plan` (con sugerencias por nombre),
  `sin_codigo`, `plan_incompleto` (la fila del plan no tiene año u orden)
  y `sin_plan`.
- **Ninguna discrepancia bloquea**: se muestra en la previsualización
  (grilla editable y vista de sólo lectura) y se puede validar, generar
  y descargar el analítico igual.
- El **Orden** y el **Año** salen de `orden_materia` y `anio_materia`
  del plan (el año se imprime como `1°`, `2°`...), no del año de
  calendario del Lincoln. El número de Orden de la grilla sigue siendo
  editable y se usa **sólo para desempatar** filas con el mismo orden
  del plan o sin orden de plan.
- Las filas sin materia en el plan (o de carreras sin plan vigente) van
  al final y quedan con el año vacío, con su aviso correspondiente. No
  se busca un plan alternativo.
- `GraduadoExamen.anio_cursado` y `GraduadoExamen.orden` se reutilizan
  para guardar estos valores; no hicieron falta migraciones.

## Promedios

- **Promedio sin aplazo**: sólo aprobados (nota ≥ 6), una vez por
  materia, excluyendo equivalencias y las materias marcadas como
  requisito en el analítico.
- **Promedio con aplazo**: todas las notas (aprobadas y reprobadas),
  incluidas equivalencias con nota y materias requisito.
- El requisito es un marcado manual por fila; el plan no participa del
  cálculo de promedios.
