# V5.3 — reconstrucción, matices y límites verificados

Fecha: 2026-11-16. Base pública: `2c20bfde43f36e7f4f58911bc4f324ae2e4bd3c2`. Entrega: medición optativa, contrato de escritorio y prototipo navegable. La política de inferencia, el ledger, los plazos de arranque y el aislamiento del piloto no se modifican.

## Fase 0 — incidentes y propiedades

**R13 histórico:** durante el arranque de un backend local propio se registró `OWNED_BACKEND_START_TIMEOUT`, en lugar de alcanzar disponibilidad o aportar una explicación de la etapa que lo impidió. La firma original no contiene resolución suficiente para atribuir la causa. [Expediente previo](V5_2_1_FORENSIC_REVIEW.md).

**Medición V5.3:** antes de comparar optimizaciones necesitamos que cada cifra tenga alcance, unidad y fuente; un fallo de observación no debe convertirse en cero consumo ni en una garantía de ahorro.

**Interfaz V5.3:** bajo cancelación, eventos tardíos o cambio del siguiente equipo, el estado mostrado debe conservar intento, fase y resultado correctos. La demo no debe presentarse como ejecución real ni otorgar autoridad al núcleo.

No se dispone de una reproducción estable de R13 original. Por ello se publica investigación y discriminantes, **no una corrección de la causa histórica**. El siguiente experimento de alta información es capturar la próxima firma fallida con etapas y el mismo código; no se necesita una pregunta especulativa al usuario ni modificar plazos para ocultarla.

## Diario de reconstrucción

| Paso | Predicción / experimento | Resultado y actualización |
| --- | --- | --- |
| D01 | Repetir la suite previa antes de añadir funcionalidad. | VERIFICADO: 103 pruebas, 16,111 s, sin modelos ni estado privado. |
| D02 | Seis arranques propios con reloj monotónico, fases y lectura del Job. | OBSERVADO: seis éxitos, cero inferencias, terminación confirmada. Primer total 34,08 s; restantes 5,83–6,32 s. No reproduce R13. |
| D03 | Un fallo de metadata frente a uno de identidad debería producir igual código pero distinta última fase. | VERIFICADO en escenarios controlados: ambos producen timeout y conservan `metadata` o `model_identity`. No atribuyen el histórico. |
| D04 | Si el timeout de PowerShell se confunde con el del bucle, tendría la misma firma. | VERIFICADO en escenario controlado: `TimeoutExpired` se propaga; no emite `START_TIMEOUT`. El rechazo de ownership también conserva una firma distinta. |
| D05 | Una operación admitida cerca del límite puede acabar después de la ventana. | OBSERVADO en D02 y VERIFICADO con reloj simulado: se permite READY tras 30 s. Es ventana de admisión de sondeos, no plazo absoluto. |
| D06 | El benchmark debe usar estado independiente. | OBSERVADO: la primera ubicación elegida bajo el árbol histórico activó `LEGACY_RECONCILE_REQUIRED` antes de inferir. Se conserva esa evidencia; se añade preflight al diagnóstico y se mueve el experimento a una carpeta nueva externa. La protección histórica no se desactiva. |
| D07 | Comparar 1/3/7 roles sin alterar perfil, backend o fixture. | OBSERVADO: seis intentos exploratorios aceptados, 22 llamadas y todos los Jobs terminados. Conservados privadamente; la referencia publicada se repite después de D13 y no mezcla las dos series. |
| D08 | Una lectura final fallida no puede reutilizar CPU acumulada anterior como total. | VERIFICADO: la prueba fuerza fallo de la última observación; el total se publica desconocido e incompleto. |
| D09 | Progreso tardío después de cancelar no debe resucitar trabajo ni atascar terminación. | VERIFICADO: el reducer avanza solo el cursor en ese evento; mantiene STOPPING, bloquea START y acepta después TERMINATED sin reembolso. |
| D10 | Cambiar roles tras un resultado no debe rotularlo como trabajo de otro equipo. | VERIFICADO: preparar otra configuración vuelve a READY y limpia progreso/error de la vista, conservando consumo e historial. |
| D11 | El sobre de escritorio debe rechazar autoridad introducida por el frontend. | VERIFICADO: métodos/campos desconocidos, claves repetidas, paths, booleanos como enteros, límites, Unicode inválido y mensajes excesivos son rechazados. Esto valida forma, no autorización real. |
| D12 | Verificar resultado final y recorrido de UI. | VERIFICADO: 125 pruebas Python, siete pruebas de estado frontend, TypeScript y build. OBSERVADO en navegador: informe, descarga JSON rotulada SIMULATION, teclado, cancelación, cuotas, recuperación, historial, modelos, skills, tema y mediciones. |
| D13 | Un PID enumerado puede haber sido reutilizado antes de abrirlo; no debe medirse un proceso fuera del Job. | VERIFICADO en fixture discriminante: antes de la corrección se observa `0 != 1` al esperar un PID rechazado; después pasa y no se llama al lector de memoria ajeno. Se añaden comprobación de pertenencia sobre el handle abierto y rechazo de la observación. Se repite la referencia real con el colector final: otros seis intentos aceptados y 22 llamadas, sin lecturas incompletas y con terminación confirmada. |

Las 125 pruebas incluyen las 103 anteriores; no se suman como 228. Los siete tests de frontend no prueban el transporte real, que no existe todavía. Los ensayos de inferencia no se ejecutan en CI.

## Línea temporal del primer arranque observado

Reloj relativo al colector, redondeado; fuente: `trials[0].events` de [V5_3_STARTUP.json](evidence/V5_3_STARTUP.json). El ensayo incluye limpieza; no incluye carga de pesos mediante inferencia.

| Tiempo relativo | Evento observado | Implicación acotada |
| --- | --- | --- |
| ~0,001 s | START_BEGIN | Inicio de la ventana medida |
| ~0,023 s | BOOTSTRAP_LAUNCHED | Se creó el proceso propio |
| ~6,060; 11,187; 16,293; 21,432; 26,566 s | Reintentos en metadata | Las peticiones de disponibilidad aún no completaron correctamente |
| ~26,666 s | Comienza el siguiente sondeo | Se admite dentro de la ventana del bucle |
| ~30,552 s | Metadata responde; empieza consulta del propietario | El sondeo admitido terminó después de 30 s |
| ~34,012 s | Propietario comprobado; empieza identidad | Se preservó ownership; no se saltó por rendimiento |
| ~34,075 s | OWNED_BACKEND_READY | Éxito, sin firma histórica de timeout |
| ~34,078 s | Terminación comprobada | Cero procesos activos del Job propio |

La demora está localizada en espera de metadata y consulta de propiedad; no se ha demostrado por qué el servicio tardó en responder. Orden temporal no basta para atribuirlo a disco, antivirus, CPU, puertos o caché.

## Escenario causal dominante actual y alternativas

| Prioridad | Escenario falsable | Evidencia a favor / contra | Observación que lo descartaría |
| --- | --- | --- | --- |
| 1 | Disponibilidad de metadata permanece fallando hasta agotar admisión de sondeos. | ESCENARIO: explica la firma en el código y el ensayo controlado. OBSERVADO: demoras en esa fase, pero el arranque lento terminó bien. | Una traza fallida íntegra que alcance metadata y termine en otra fase sin volver a ella. |
| 2 | Metadata de identidad falla después de comprobar el listener y se agota el bucle. | ESCENARIO: el test controlado produce el mismo código en otra fase. No hay una falla real capturada en esa etapa. | Una traza fallida que no alcance identidad y tenga únicamente reintentos en metadata. |
| 3 | Timeout de la consulta PowerShell de propiedad produce directamente R13. | CONTRAEVIDENCIA VERIFICADA para el código actual: la firma es `TimeoutExpired`, no `OWNED_BACKEND_START_TIMEOUT`. Menor prioridad para esa firma exacta. | La ausencia de `START_TIMEOUT` junto a `TimeoutExpired` refuta la equivalencia; para atribuir el histórico hay que comprobar también su versión exacta. |

No hay escenario confirmado. La alternativa adversarial más fuerte al primero es el segundo: mismo código exterior con distinto punto de fallo. Los éxitos nuevos no la eliminan. La [ventana](../neural_office/ollama.py#L81), [reintentos](../neural_office/ollama.py#L100) y [consulta de propiedad](../neural_office/ollama.py#L106) permanecen intactos. Los [cinco experimentos discriminantes](../tests/test_v53_startup_scenarios.py#L1) son fixtures, no una reproducción histórica.

## Registro de caza de matices

**PID obsoleto — escenario reproducido en fixture:** enumeración del Job → el identificador deja de referirse al proceso original → apertura del mismo número para otro proceso → lectura de memoria sin verificar pertenencia. La violación más temprana evitable está después de abrir el handle y antes de leer contadores. La prueba entrega el PID del controlador, ajeno al Job, como si viniera de una enumeración antigua. No espera que Windows reutilice espontáneamente un PID: controla exactamente esa frontera.

La intervención añade `IsProcessInJob` sobre ese handle; si falla o no pertenece, la suma pasa a desconocida, se registra proceso ilegible y se cierra el handle. La alternativa adversarial —que el proceso realmente pertenezca y se rechace siempre— queda contrastada por el ensayo del hijo real que asigna memoria y consume CPU dentro del Job. [Colector](../neural_office/measurements.py#L45), [regresión](../tests/test_v53_measurements.py#L89). Confianza subjetiva en esta frontera: 98%; no certifica todas las carreras de observación. Se conserva el log de fallo anterior en privado y su hash en la verificación pública.

**VERIFICADO:** lectura de recursos fallida → dato desconocido; cifra fraccionaria/no finita/booleana → métrica de Ollama inválida; clave repetida → mensaje rechazado; espacios cuentan para el límite del objetivo; un sustituto Unicode inválido no cruza el contrato. [Pruebas del colector](../tests/test_v53_measurements.py#L1), [pruebas del contrato](../tests/test_v53_contract.py#L1).

**VERIFICADO:** el reducer conserva cargo tras fallo, parada y recuperación; bloqueo mientras se confirma terminación; eventos antiguos/duplicados/huecos no avanzan fase; se requiere verificación antes del resultado. [Regresiones](../desktop/src/state.test.ts#L1). Son propiedades de la simulación; no certifican persistencia, seguridad o autoridad del futuro bridge.

**OBSERVADO:** el primer build falló por falta de declaraciones de importación CSS; se añadió `vite/client` y el build posterior pasó. Durante la comprobación de navegador, un selector esperaba el botón de exportación en la pestaña de actividad y otro retenía el nombre de navegación de escritorio en la vista estrecha; se corrigió el procedimiento usando el estado visible. No se contabilizan esos errores de automatización como defectos resueltos del motor.

**OBSERVADO:** se pidió un viewport de 390 px, pero el navegador integrado informó un ancho efectivo de 500 px. La revisión estrecha se acredita a 500 px, sin afirmar una prueba real a 390 px. No hubo errores/avisos de consola capturados en el recorrido. Esto no reemplaza una auditoría completa con lector de pantalla, otros navegadores o todas las resoluciones.

**VERIFICADO por alcance:** se publica código propio, dependencias declaradas/lockfile, pruebas sintéticas, métricas depuradas, documentos y captura de demo. No se publican logs nativos, prompts/respuestas de inferencia, bases, alias, credenciales, vídeos o frames. Los avisos de terceros del frontend se enumeran separadamente de MIT propio.

## Duda residual más relevante

R13 conserva causa **DESCONOCIDA**. La medición de referencia no tiene GPU, TTFT, energía, calidad comparada ni sobrecoste instrumental controlado. La GUI moderna es un prototipo sin motor. La lectura parcial de vídeos no acredita ocho horas de contenido ni sus afirmaciones de rendimiento en nuestro equipo.

## Siguiente acción concreta

V5.4: corpus sintético evaluable + experimento diferencial CPU/GPU/contexto/carga con una variable por comparación. Capturar el próximo arranque fallido con la instrumentación nueva; mantener la firma y evidencia, confirmar limpieza y no reintentar una inferencia automáticamente. La intervención en R13 requiere el escenario dominante y una reproducción contrastada antes de cambiar código de producción.

## Confianza e incertidumbre restante

Estimación técnica subjetiva: **95%** en los resultados y propiedades expresamente ensayados; **20%** en atribuir una causa al R13 histórico. No son probabilidades estadísticas de ausencia de errores. Supuesto crítico: los recibos corresponden al núcleo identificado y a la entrada sintética declarada. La referencia final identifica núcleo, colector y entrada por hash. La serie anterior de arranques solo conserva hashes del núcleo, no del colector completo; tampoco existe evaluación independiente en otra máquina. La entrega cierra el alcance V5.3, no todos los incidentes ni la optimización del producto.
