# V5.2: diario de reconstrucción y revisión adversarial

Fecha de revisión: 16 de noviembre de 2026. Un mismo revisor asistido realizó pasadas sucesivas; no son auditorías independientes. Las correcciones del legado se limitan a cinco archivos. El núcleo nuevo es un piloto separado, sin sustitución de producción histórica.

## Fase 0: incidente y propiedad esperada

**OBSERVADO.** En el contexto de preparar una ejecución local y una publicación reproducible, el histórico contiene rutas de empaquetado que no encuentran sus destinos, una consulta de estado que puede crear una base inexistente y un traspaso de roles sin contenido suficiente. La propuesta documental V5.1 no demuestra una integración ejecutada. Se exige preservar autoridad e historial, reservar antes de inferir, no aceptar afirmaciones del modelo como verificaciones y demostrar la terminación antes de liberar exclusión.

La firma de cada incidente se delimita por separado. No existe una única excepción de producción que explique todos ellos. Los fallos introducidos durante esta implementación también se registran; no se presume correcto el código recién escrito.

## Diario de reconstrucción

| ID / orden causal | Escenario, predicción y experimento | Observación y decisión |
| --- | --- | --- |
| R01 — localizar antes de ejecutar | H1: el operador conserva rutas del paquete de instalación; H2: faltan los componentes; H3: el directorio de ejecución es incorrecto. Comparar `Join-Path $PSScriptRoot`, archivo instalado y staging histórico. | VERIFICADO: los componentes existen en `profiles` y `runtime`, pero los operadores los buscan en otros destinos. Cambio de ruta local. Gate B `VerifyDefinition` y Gate C `Plan` funcionan; no crean modelos ni aplican configuración. [Diff](legacy/V5_2_LEGACY_FIXES.patch). |
| R02 — resolver ruta → construir argv | Tras corregir Gate C, `Plan` seguía fallando con aprobación vacía. H1: PowerShell omite el argumento vacío; H2: falta el motor; H3: el plan requiere aprobación. Mantener el valor vacío y pasar `--approval=` como un solo argumento. | VERIFICADO: esa forma permite el plan sin aplicar cambios. Se conserva la aprobación para la acción que realmente la exige. No se modifica la configuración OpenCode. [Diff](legacy/V5_2_LEGACY_FIXES.patch). |
| R03 — consulta → apertura SQLite → archivo nuevo | H1: `sqlite3.connect` crea una base antes de que falle la consulta; H2: ya existía; H3: la inicialización era explícita. Usar un directorio temporal nuevo y ejecutar solo `status`. | VERIFICADO: la regresión detecta creación no solicitada. Se usa modo URI `rw` en lecturas y `rwc` solo en inicialización explícita. La prueba posterior confirma ausencia del archivo. [Diff](legacy/V5_2_LEGACY_FIXES.patch). |
| R04 — evidencia → digest → consumidor | H1: se transmite solo identidad, no contenido; H2: el consumidor lo recupera por otra vía; H3: es un problema de longitud. Introducir una frase de evidencia y buscarla en el prompt consumidor; después cambiar hash y exceder el límite. | VERIFICADO en el contrato de función: el prompt histórico omitía la frase. Se añade contenido de dependencias, revalidación de hash y rechazo por tamaño, sin truncamiento. Tres pruebas específicas distinguen transferencia válida, alterada y excesiva. [Diff](legacy/V5_2_LEGACY_FIXES.patch). |
| R05 — rechazo → éxito posterior → contador | Nuestra hipótesis inicial interpretó `completed` como número de éxitos. La prueba histórica `test_30_success_after_rejected_version_remains_ordered` esperaba `(attempted, completed)=(2,2)` y obtuvo `(2,1)`. | REFUTADO el cambio inicial. Se restituye el ordinal histórico y se añaden campos explícitos. La secuencia éxito solo en el segundo de tres intentos produce `verified_count=1`, `completed=2`, `attempted=3`. No se reescribe el historial. |
| R06 — inferencia admitida → revocación → espera | H1: el watcher mira cancelación, pero no revocación; H2: la revocación no se persiste; H3: el backend ignora la señal. Fixture bloqueante con evento de parada y revocación persistida. | VERIFICADO: la prueba falló con «Revocation did not reach the in-flight backend». El watcher consulta ahora autoridad y límite monotónico; el mismo ensayo pasa y el intento termina FAILED conservando consumo. [Vigilancia](../neural_office/runner.py#L57), [test_revocation_interrupts_inflight_call](../tests/test_v52_boundaries.py#L128). |
| R07 — JSON → comparación Python → aceptación | H1: igualdad numérica de Python confunde booleanos, enteros y floats; H2: solo falla el parseo; H3: el verificador ya compara representación. Sustituir versión por `true` y línea por `true` o `1.0`. | VERIFICADO: tres aserciones fallaron antes del cambio. Se exige versión entera y se comparan hallazgos canónicos. Los casos negativos y positivos pasan. [Verificador](../neural_office/audit.py#L65), [test_boolean_is_not_schema_version_one](../tests/test_v52.py#L225), [test_boolean_or_float_is_not_a_line_number](../tests/test_v52.py#L228). |
| R08 — tercer terminal → repetición CLI → activación | H1: la CLI activa antes de reconocer el duplicado; H2: el ledger perdió la clave; H3: el resultado es incompatible. Repetir por CLI la tercera solicitud idéntica ya aceptada. | VERIFICADO: falló con `ATTEMPT_BUDGET_EXHAUSTED`. La admisión se integra en la transacción de reserva después de reconocer el duplicado. Se evita además separar consulta y activación mediante una ventana de carrera. El replay no reactiva ni renueva permisos. [Reserva](../neural_office/ledger.py#L168), [test_cli_terminal_replay_after_exhausting_budget](../tests/test_v52_boundaries.py#L71). |
| R09 — POST → cancelación → fin del job → liberación | H1: basta cerrar HTTP; H2: hay que terminar el árbol propio; H3: expirar el lease demuestra fin. Instrumentar envío real y observar el Job Object antes de liberar. | VERIFICADO para este backend: se envió un POST, se canceló y se observaron cero procesos propios con lease aún retenido; después quedó libre y el puerto dejó de responder. El diseño no adopta H1/H3 como pruebas de terminación. [Recibo](evidence/V5_2_EXECUTION.json). |
| R10 — POST → muerte abrupta del propietario | Alternativa adversarial: podrían sobrevivir descendientes o devolverse presupuesto al reiniciar. Terminar solo el controlador del ensayo después del envío y recuperar desde otro contexto. | VERIFICADO: el job quedó vacío; el ledger conservó RUNNING y lease hasta la reconciliación explícita, que terminó FAILED con un intento consumido. No se reenvió el POST. [Recibo](evidence/V5_2_EXECUTION.json), [test_abrupt_owner_exit_terminates_descendants](../tests/test_v52_boundaries.py#L160). |
| R11 — interfaz → reserva → identificación → parada | SOSPECHA por inspección: pulsar Detener antes de que la UI reciba el identificador podía perder la intención. Conservar la intención y aplicarla al recibir el evento. | VERIFICADO acotado: parada inmediata manual observó STOPPING y después CANCELLED, tercer intento conservado y proyecto aparcado. La prueba visual no enumera todos los tiempos posibles previos a la reserva. [UI](../neural_office/ui.py#L86). |
| R12 — alias → atribución de familia/contexto | H1: el alias describe el modelo real; H2: es un nombre personalizado; H3: el contexto nominal coincide con la asignación. Consultar tags/show/ps y contrastar digest y ejecución. | OBSERVADO: el alias menciona DeepSeek/64k, la metadata declara `qwen35` 9B y el contexto de ejecución fue 8.192. Se corrige la descripción; no se renombran modelos históricos ni se atribuye una licencia desconocida. [Procedencia](V5_2_PROVENANCE.md). |

## Incidencias que no se cierran por repetición exitosa

**R13 — arranque dedicado intermitente.** La primera ejecución real terminó con `OWNED_BACKEND_START_TIMEOUT`, sin admisión de llamada de modelo. El intento quedó FAILED y consumido. Escenarios provisionales ordenados por poder discriminante: H1, el proceso hijo no llega a responder dentro de la ventana; H2, las comprobaciones de metadatos/propiedad no completan; H3, falta una variable de entorno necesaria. La instrumentación confirmó entrada del bootstrap al job. Arranques con entorno mínimo y completo respondieron; otro arranque completo tardó 5,375 s y terminó limpiamente. H3 no obtuvo apoyo. No hay traza suficiente para distinguir H1 de H2 en el primer fallo.

**DESCONOCIDO.** La causa del primer timeout sigue abierta. Se añadieron eventos privados de lanzamiento, disponibilidad, salida y timeout para que una recurrencia aporte evidencia. No se aumentó el plazo para ocultar el síntoma, ni se declara resuelto por éxitos posteriores. Observación que refutaría H1: listener propio disponible dentro del plazo mientras otra comprobación demora o rechaza el arranque.

**R14 — respuesta 401 intermitente del gateway histórico.** Una corrida de 200 tests tuvo un `ConnectionAbortedError`, WinError 10053, en `test_03_wrong_header_denied`, al leer la respuesta del gateway. No se admitió inferencia real en esa suite. El archivo `gateway45.py` no fue modificado por esta entrega.

Escenarios ordenados: H1, interacción temporal entre rechazo temprano, cuerpo pendiente y cierre TCP; H2, aborto introducido por el entorno de red local; H3, regresión directa de los cinco cambios. H3 pierde fuerza porque la ruta de autorización y el gateway conservan sus bytes. Un experimento con 300 solicitudes sobre baseline y 300 con drenaje diagnóstico del cuerpo devolvió 401 en todos los casos: **no discrimina H1/H2 ni prueba que el drenaje sea una corrección**. Se retiró esa intervención experimental y no se parcheó producción. La siguiente corrida completa pasó 200/200; se conserva el fallo anterior y la incidencia sigue abierta.

La siguiente acción para R14 es capturar orden de lectura/escritura/cierre en una reproducción aislada que conserve la firma, antes de cambiar el protocolo de respuesta. No se rebaja la aserción de 401 a «cualquier error sirve». Este gateway histórico no se activa como proveedor de V5.2.

## Registro de evidencia y límites

| Evidencia | Etiqueta y alcance |
| --- | --- |
| Comparación de 201 archivos de la línea base | VERIFICADO: solo cinco diferencias autorizadas en el legado; bases y resto de archivos incluidos conservan sus hashes. No cubre todos los archivos del equipo. [Cambios](evidence/V5_2_LEGACY_CHANGES.json). |
| Suite histórica restaurada desde el paquete pertinente | VERIFICADO: baseline 200/200; candidato final 200/200. Una corrida intermedia falló por R14 y no se oculta. Los primeros intentos con fixtures incompletos fueron errores del arnés, no defectos adjudicados al producto. |
| Regresiones específicas del V5 instalado | VERIFICADO: siete casos de rutas, consulta sin creación, ordinal/recuento, contenido, alteración y exceso de tamaño. [Recibo](evidence/V5_2_EXECUTION.json). |
| Suite pública del piloto | VERIFICADO en la ejecución registrada: casos unitarios y nativos Windows, con backend simulado donde corresponde. Reproducible desde el repositorio. No equivale a los 45 casos completos de V5.1. |
| Roles reales 1/3/7 | VERIFICADO acotado: mismo HTML sintético, objetivo, digest de modelo y perfil; respuestas y métricas persistidas. Una observación por variante no demuestra superioridad de calidad. |
| UI nativa | OBSERVADO: selección de archivo/modelo, ciclo de tres roles, lectura posterior del informe, parada inmediata y presupuesto aparcado. No es una auditoría de accesibilidad. |
| API ps y recibos de modelo | OBSERVADO: cero bytes de VRAM informados y contexto 8.192. No son una medición independiente del hardware ni prueba de compatibilidad universal. |
| Investigación audiovisual | OBSERVADO: se conserva la revisión parcial V5.1. No se afirma visionado completo en V5.2. |
| Publicación | La verificación remota se registra después del push, separada de este documento. No se anticipa el resultado. |

Los logs originales, copias antes/después, scripts de incidentes y bases de ensayo permanecen en el expediente privado. Los JSON públicos minimizan datos y fijan sus hashes cuando corresponde; no publican rutas personales ni respuestas brutas. La reproducción pública de la suite es independiente de esos archivos privados.

## Escenario causal dominante actual

**VERIFICADO en los defectos reproducidos R01–R08.** Las discrepancias estaban en fronteras concretas: ubicación instalada, construcción de argv, apertura con efectos colaterales, representación frente a contenido, ordinal frente a recuento, revocación durante una operación, igualdad de tipos y orden entre admisión e idempotencia. No existía una causa única que justificara reescribir módulos enteros.

**INFERIDO, límite del conjunto.** Las pruebas del piloto reducen la incertidumbre sobre su flujo acotado; no validan la oficina completa. R13/R14 no tienen todavía escenario causal dominante demostrado. La alternativa adversarial más fuerte es que otras rutas o estados omitidos permitan efectos no cubiertos. Se conserva como riesgo, especialmente para migración, clientes ajenos y herramientas futuras.

## Duda residual más relevante y siguiente acción

La principal duda de integración es la transferencia de autoridad histórica y su restauración sin perder presupuesto. No se resuelve creando una base nueva. Antes de admitir proyectos reales del legado, implementar un adaptador de conciliación con identidad estable, testigo conservado y casos A07/A10/A17, manteniendo las bases anteriores intactas durante el ensayo.

Para esta vista previa, conservar R13/R14 instrumentados, reproducir la suite en un entorno Windows separado y verificar los bytes publicados. No habilitar OpenCode, herramientas con efectos, memoria ni promoción de skills por el mero éxito de un informe HTML.

## Confianza e incertidumbre restante

**Confianza técnica: 90 %**, estimación de revisión no calibrada sobre las correcciones reproducidas y el flujo acotado aquí descrito; no es una probabilidad de ausencia de errores. La asunción crítica es que controlador, ledger, ejecutable del proveedor y sistema operativo son confiables y que los participantes usan el mismo dominio. Si no se cumple, las garantías de cuotas y exclusión no se extienden a esas rutas.

No se declara cierre total: permanecen incidencias intermitentes, aceptación parcial de la integración, restauración sin implementar y decisiones de derechos. La matriz evita transformar esos pendientes en éxitos nominales.
