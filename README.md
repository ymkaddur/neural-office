# Neural Office

Neural Office busca ofrecer una oficina de agentes que trabaje con un modelo local: el usuario descarga la aplicación, elige un modelo compatible y encarga una tarea. La aplicación coordina planificación, herramientas, revisión, memoria y skills, con progreso recuperable y límites visibles.

**Estado actual: V5.1 documental. Este repositorio contiene especificaciones y criterios de aceptación. No incluye todavía una aplicación instalable, agentes ejecutables ni pesos de modelos.**

## Los tres entregables de V5.1

| Documento | Decisión que permite tomar |
| --- | --- |
| [Contrato de autoridad y contadores](docs/V5_1_AUTHORITY_AND_COUNTERS.md) | Quién puede activar trabajo, cómo se contabilizan los intentos y qué ocurre al detener o reanudar una ejecución. |
| [Especificación de integración completa](docs/V5_1_INTEGRATION_SPEC.md) | Cómo se conectarán interfaz, modelo, gateway, herramientas, roles, memoria, skills y verificación. |
| [Expediente de procedencia y publicación](docs/V5_1_PROVENANCE_AND_PUBLICATION.md) | Qué se puede distribuir ahora y qué evidencia falta antes de publicar código, dependencias o una aplicación. |

El [índice de evidencias](docs/evidence/SOURCE_INDEX.md) vincula las observaciones con fuentes históricas mediante rutas relativas, líneas y hashes. Esas fuentes operativas permanecen fuera del repositorio público.

## Experiencia prevista

1. Descargar Neural Office para una plataforma soportada.
2. Descargar o seleccionar un modelo local compatible mediante un asistente.
3. Elegir una carpeta de trabajo, describir el resultado esperado y comenzar.

La interfaz mostrará la tarea en curso, el presupuesto restante, las evidencias obtenidas y las acciones que requieren una decisión del usuario. Los loops y autoprompts tendrán objetivos, límites y condiciones de parada; no podrán ampliar sus permisos.

La primera implementación se validará con CPU, una inferencia simultánea y un producto piloto. La compatibilidad con modelos adicionales dependerá de pruebas de herramientas, contexto, calidad y consumo.

## Qué acredita esta entrega

La revisión del legado distinguió un origen con CrewAI, una ejecución histórica del director de Plus y varias capas posteriores de control, pruebas y simulación. La versión numérica más reciente no sustituyó toda la autoridad anterior.

Las palabras **observado**, **propuesto** y **pendiente de aceptación** tienen significados distintos en los documentos. Los casos de aceptación enumerados son trabajo futuro; no son resultados de pruebas ejecutadas.

El [registro de revisión crítica](docs/V5_1_REVIEW_REPORT.md) documenta contraejemplos, correcciones y límites de las tres pasadas documentales. El [manifiesto SHA-256](PUBLICATION_MANIFEST.sha256) identifica los archivos de esta entrega. Ninguno acredita ausencia total de defectos o cumplimiento jurídico universal.

La publicación de estas especificaciones no activa el sistema local ni cambia su código. Tampoco acredita que la experiencia prevista ya funcione.

## Desarrollo y distribución

La [hoja de ruta hasta V10](ROADMAP.md) organiza el trabajo por capacidades demostradas. La siguiente fase técnica es un ciclo completo de un solo producto, con artefacto y verificación independiente.

La licencia del futuro software sigue pendiente de la revisión de titularidad y dependencias. Esta entrega documental no concede una licencia open source adicional: consulta [el estado de licencias](LICENSING.md).

No se incluyen bases de datos de usuarios, conversaciones, credenciales, vídeos, entornos virtuales, paquetes históricos ni modelos.
