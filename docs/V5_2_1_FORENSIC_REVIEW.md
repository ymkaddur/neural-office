# V5.2.1 — revisión forense y cierre delimitado

Fecha: 2026-11-16. Base pública: `4acf3198f3c9f889dc37abde6d1328471838f07e`. **Resultado:** conciliación histórica y restauración verificadas en su dominio; R14 reproducido y corregido; R13 investigado e instrumentado, con causa todavía **DESCONOCIDA**. No se declara ausencia total de errores.

## Fase 0 — propiedades investigadas

| Caso | Incidente y propiedad esperada |
| --- | --- |
| A07/A10 | Al incorporar trabajo histórico a un ledger independiente, no se debe confundir contador certificado con consumo ni conceder más autoridad que las fuentes originales. V5.2 anunciaba esta integración como pendiente. |
| A17 | Tres intentos cancelados, seguidos de una copia antigua del ledger, mostraban uno. Propiedad: restaurar no devuelve presupuesto ni elimina evidencia posterior retenida. |
| R14 | Un token incorrecto podía producir `WinError 10053` al leer la línea de estado, en vez del rechazo HTTP 401. Propiedad: entregar el rechazo bajo el fraccionamiento de petición probado, sin contactar al proveedor. |
| R13 | El primer arranque histórico terminó en `OWNED_BACKEND_START_TIMEOUT`. Propiedad: diagnosticar qué etapa impidió iniciar y confirmar limpieza, antes de atribuir una causa o cambiar plazos. |

Los experimentos de red usaron clientes locales sintéticos, sin prompts ni inferencias. La prueba real de esta revisión usó exclusivamente el HTML público incluido, un rol y un intento independiente. Fuentes, contadores, resultados y hashes de logs depurados están en [V5_2_1_EVIDENCE.json](evidence/V5_2_1_EVIDENCE.json).

## Diario de reconstrucción

| Paso | Escenario y predicción discriminante | Experimento / observación | Conclusión |
| --- | --- | --- | --- |
| 1 | Si cero certificados implica cero consumo, no debe haber una invocación anterior en Plus. | OBSERVADO: secuencia DIRECTOR_MESSAGE → RUN_STARTED → ANSWER → RUN_RECEIPT; certificados V1/V4 a cero. | Se refuta esa equivalencia. Una operación se carga conservadoramente; no se certifica como resultado nuevo. |
| 2 | Si V5.2 ya concilia la autoridad, una divergencia V1 activo/V4 aparcado debe impedir reservar. | VERIFICADO por inspección: la base pública carecía de adaptador histórico. Fixtures nuevos cubren ambas divergencias, cambio de fuente y permisos parciales. | Se añade un adaptador cerrado; importar nunca activa. |
| 3 | Si el cálculo de presupuesto es el defecto de A17, el archivo antiguo debería contener los tres intentos. | OBSERVADO: el archivo antiguo solo contiene uno; SQLite es legible. Restaurarlo reproduce 3 → 1. | La primera pérdida es reemplazar el único registro por una revisión vieja, no sumar mal sus filas. |
| 4 | Un testigo retenido debe detectar la copia vieja y conservar el estado reciente. | VERIFICADO: copia posterior al primer intento, otros dos, sustitución, bloqueo, restauración, consumo 3; cuarto intento denegado. | Cierra A17 dentro del dominio del testigo retenido. |
| 5 | R14: cierre con cuerpo pendiente, frente a fallo del entorno o rechazo mal calculado. | Un único cambio de timing: cuerpo 100 bytes retrasado 0/1/10/50 ms. Cierre original: 1/40 errores a 0 ms, 40/40 en cada retraso restante. | El orden cuerpo/cierre discrimina el escenario de transporte. |
| 6 | Si el cierre gradual explica R14, variarlo debe preservar 401 sin cambiar token, petición o proveedor. | Contrafactual: 160/160 respuestas 401. Parche final: 80/80 solicitudes con esos retrasos, más cuerpo ausente/excesivo, aborto y ruta health. El mismo test falla en el original con 10053. | Escenario dominante confirmado para el entorno ensayado. |
| 7 | R13: arranque/listener lento, consulta de propietario lenta o entorno. | Doce arranques reales seriales sin inferencia: todos correctos y cero procesos propios tras terminar. Primero 26,31 s; los restantes aproximadamente 4,86–6,98 s. | No reproduce la firma. Lentitud observada no prueba la causa del fallo histórico. |
| 8 | La instrumentación debe distinguir metadata, propiedad e identidad sin filtrar prompts. | Fixtures de éxito/timeout y un arranque real instrumentado. Eventos ordenados de alta resolución; 6,87 s incluyendo limpieza en la comprobación adicional. | Instrumento verificado; no se amplía timeout ni se anuncia R13 resuelto. |
| 9 | Un controlador anterior puede reservar entre la comprobación de inactividad y el bloqueo de migración. | Inyección de una admisión en esa ventana; la segunda comprobación dentro de BEGIN IMMEDIATE deniega la adopción y conserva el estado anterior. | Se impide sellar como inactiva una oficina que ya cambió. |
| 10 | Presentación popular puede ocultar límites o atribuir exclusividad falsa. | Revisión editorial de 91 README: precedentes de oficina, presupuestos y verificación; distintos estados de mantenimiento. | Se separan alcance actual, visión y evidencia; no se transfieren promesas ajenas. |

## Escenarios dominantes y matices

**A07/A10 — VERIFICADO:** falta de puente entre autoridades y unidades distintas. La captura y el mapeo están en [legacy.py:55](../neural_office/legacy.py#L55) y [legacy.py:109](../neural_office/legacy.py#L109); admisión en [legacy.py:221](../neural_office/legacy.py#L221). `completed=3` puede significar último ordinal aceptado con un solo éxito; la [regresión](../tests/test_maintenance.py#L99) lo conserva sin presentarlo como tres certificados. Las cinco identidades propias se importaron aparcadas; se reconoció un consumo en web-auditor y cero en las otras cuatro. Cinco archivos originales main/WAL conservaron sus hashes. El proyecto externo tower-defense queda excluido.

Una regresión adicional reprodujo otro matiz propio: dos RUN_STARTED bajo una autorización se deduplicaban como un único cargo. Ahora se bloquea ese grupo hasta mapear roles y reintentos; no se adivina si fueron una tarea o varias. La regresión falló antes del cambio y se integra en la suite final.

Los permisos V4 parciales no se amplían a tres intentos: se bloquean hasta definir su equivalencia. Historial mixto no mapeado, grafos con trabajo y certificados originales no cero también bloquean. Esto cierra el historial instalado examinado; no certifica una migración universal. La capacidad futura no se deduce de un nombre de versión.

**A17 — VERIFICADO:** archivo antiguo válido sin memoria del futuro. La intervención incorpora testigo y revisión conjunta; [sellado](../neural_office/continuity.py#L94), [adopción](../neural_office/continuity.py#L107), [restauración](../neural_office/continuity.py#L177). La [regresión 3 → 1 → 3](../tests/test_continuity.py#L30) cubre el síntoma; otras cubren testigo ausente, copia ajena/alterada, informes retenidos, lease activo, rollback y muerte del proceso antes de commit. La [prueba adversarial de reversión total](../tests/test_continuity.py#L136) demuestra el límite, no una garantía adicional.

**R14 — VERIFICADO:** headers → rechazo temprano → cierre con bytes entrantes pendientes → reset → fallo al leer status. El cambio más temprano necesario es el cierre de respuestas rechazadas: half-close y drenaje limitado a 0,25 s/1 MiB. Se preserva autorización, normalización y ruta de éxito. [Diff exacto](legacy/V5_2_1_GATEWAY_FIX.patch) y [regresión](legacy/test_gateway_close.py#L45). El mecanismo coincide con [RFC 9112, sección 9.6](https://www.rfc-editor.org/rfc/rfc9112.html#section-9.6). No se garantiza entrega a un emisor que exceda ambos límites o aborte arbitrariamente.

**R13 — DESCONOCIDO:** no hay escenario confirmado. Orden provisional: disponibilidad del backend; latencia de consultas de metadata/propietario; diferencias de entorno. Las 12 ejecuciones correctas no eliminan ninguno para la firma histórica. [Instrumentación](../neural_office/ollama.py#L57) y [pruebas de fases](../tests/test_maintenance.py#L129) permiten un siguiente experimento discriminante. Se conserva intacta la política de timeout; la ventana de sondeo no es una promesa de plazo absoluto incluyendo todas las operaciones del sistema.

## Registro de evidencia y revisión de calidad

- **VERIFICADO:** 103 pruebas públicas locales; 200 pruebas del paquete histórico con el gateway candidato comprobado por hash; siete regresiones anteriores y cinco nuevas del gateway. No se suman como una única suite ni como cobertura exhaustiva. CI pública ejecuta únicamente las 103 pruebas del repositorio.
- **VERIFICADO:** una ejecución real de un rol, un intento, informe aceptado, verificador estático correcto y lease liberado. La captura muestra lectura posterior del informe, no una simulación de inferencia.
- **VERIFICADO:** lanzador Windows desde ruta con espacios y Unicode, directorio de trabajo distinto y salida de error propagada.
- **OBSERVADO:** alias de modelo con DeepSeek/64k en su nombre. La ejecución usa CPU y contexto 8.192; el alias no demuestra familia, contexto ni licencia. No se redistribuyen pesos.
- **INFERIDO:** el nuevo orden del README y el recorrido corto facilitan entender el producto. No hay experimento de conversión ni evidencia de aumento de estrellas.
- **DESCONOCIDO:** causa histórica de R13, comportamiento ante todos los discos/fallos eléctricos, titularidad jurídica universal y disponibilidad del nombre como marca.

Tres pasadas corrigieron errores propios antes de publicar: desajuste de placeholders SQL, handles abiertos en fixtures de restauración y ejemplos PowerShell sin prefijo de carpeta actual. Se descartó como evidencia una corrida de 200 tests que había usado el candidato anterior por un error de ruta al copiar; la corrida acreditada usa el gateway comprobado por hash. La revisión posterior añadió el caso de migración concurrente y el bloqueo de permisos parciales. El generador privado de evidencias también requirió corregir el nombre de una codificación antes de emitir el expediente; un fallo del generador no se contó como validación.

El manifiesto publica código propio, pruebas sintéticas, documentos, diff y captura revisada. Los logs brutos, bases, sesiones, prompts privados, vídeos y paquetes históricos permanecen fuera. [Componentes de esta revisión](evidence/V5_2_1_COMPONENTS.json) · [investigación editorial](README_RESEARCH_91.md).

## Duda residual más relevante

La principal duda técnica abierta es R13. La principal condición de restauración es conservar el testigo vigente: su ubicación predeterminada junto al ledger no protege contra pérdida o rollback de la carpeta completa. Fuentes históricas quiescentes son requisito; la captura no controla programas externos ni puede bloquear como archivo una fuente opcional todavía inexistente. Los demás límites están en el [manual](V5_2_1_OPERATIONS.md).

## Siguiente acción concreta

Capturar **un arranque que falle** con las nuevas etapas y el commit exacto, sin repetir automáticamente la inferencia, y comparar con un arranque correcto en el mismo entorno. Si no aparece, mantener R13 abierto y reunir evidencia en la siguiente sesión real. No se publica una corrección causal inventada.

## Confianza e incertidumbre restante

Estimación técnica subjetiva, no probabilidad estadística ni certificación: conciliación del historial examinado **95%**, restauración en el dominio declarado **95%**, mecanismo/corrección R14 en Windows ensayado **98%**, atribución causal R13 **20%**. Supuestos críticos: fuentes completas y quiescentes, testigo no revertido junto al ledger, entorno de transporte comparable y captura original de R13 insuficiente. Su falsedad obliga a reabrir el caso correspondiente.

A07/A10 y A17 quedan verificados con estas condiciones; R14 cierra su firma reproducida; R13 continúa abierto. La publicación de diagnóstico verificado es compatible con conservar un incidente sin resolver.
